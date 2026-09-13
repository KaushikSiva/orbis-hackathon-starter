"""SHOWROOM local backend. Live providers are never replaced by simulated success."""
from __future__ import annotations
import asyncio
import hashlib
import io
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from dotenv import dotenv_values
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from neo4j import GraphDatabase
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from backend.discovery import search_amazon, transcribe_audio
from backend.vision import identify_furniture, rank_visual_matches
from backend.hosting import install_access_gate
from backend.sharing import share_document

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("SHOWROOM_DATA_DIR", ROOT / "backend/data"))
DATA.mkdir(parents=True, exist_ok=True)
(DATA / "uploads").mkdir(exist_ok=True)
CATALOG = json.loads((ROOT / "backend/catalog.json").read_text())
MODEL = "reactor/visko-orbis-dynamic"
LOCK = threading.RLock()
EXPORT_LOCKS: dict[str, asyncio.Lock] = {}
PROVIDER_STATUS = {"reactor": "not_verified", "ambiguous": "not_verified"}


def setting(name: str, default: str = "") -> str:
    # Re-read the local file so keys can be pasted while the demo is running.
    return str(os.environ.get(name) or dotenv_values(ROOT / ".env").get(name) or default)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db():
    con = sqlite3.connect(DATA / "showroom.db", timeout=15)
    con.execute("CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, room_id TEXT, body TEXT NOT NULL)")
    return con


def save_room(room):
    room["updated_at"] = now()
    with db() as con:
        con.execute("INSERT OR REPLACE INTO rooms VALUES (?,?)", (room["id"], json.dumps(room)))
    return room


def get_room(room_id):
    with db() as con:
        row = con.execute("SELECT body FROM rooms WHERE id=?", (room_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Room not found.")
    return json.loads(row[0])


def fingerprint(room):
    fields = {k: room[k] for k in ("name", "budget", "preferences", "keep", "image_url", "directives", "products")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def prompt_for(room, instruction=""):
    accepted = [d["instruction"] for d in room["directives"] if d["status"] == "accepted"]
    # Lead with the requested visual change. The rest re-establishes the same
    # room and retained constraints so a live morph stays grounded in its brief.
    current = instruction or (accepted[-1] if accepted else "A warm, considered living space with realistic furniture and soft natural light")
    history = accepted[-2:] if instruction else accepted[-3:-1]
    return (
        f"{current}. "
        "Photorealistic redesign of the same living room, a continuous static wide shot. "
        "Preserve room geometry, camera position, doors and windows. "
        f"Keep unchanged: {', '.join(room['keep']) or 'the existing architectural layout'}. "
        f"Style: {', '.join(room['preferences']) or 'warm, natural, calm'}. "
        f"Furniture budget: USD {room['budget']:.2f}. "
        f"Prior design context: {'; '.join(history) or 'original room photograph'}. "
        "Physically plausible furniture and lighting, no cuts."
    )


def tags_for(room):
    text = " ".join(room["preferences"] + [d["instruction"] for d in room["directives"] if d["status"] == "accepted"]).lower()
    known = {tag for p in CATALOG for tag in p["tags"]}
    tags = {tag for tag in known if tag in text}
    if any(word in text for word in ("cozy", "cosy", "warmer")): tags.add("warm")
    if "japandi" in text: tags.update(("natural", "minimal", "neutral"))
    return sorted(tags)


def kept_categories(room):
    text = " ".join(room["keep"]).lower()
    aliases = {"sofa": ("sofa", "couch", "loveseat"), "table": ("table",), "rug": ("rug", "carpet"), "lighting": ("lamp", "lighting")}
    return [category for category, names in aliases.items() if any(n in text for n in names)]


def graph_driver():
    return GraphDatabase.driver(setting("NEO4J_URI", f"bolt://{setting('NEO4J_HOST', 'localhost')}:7687"), auth=(setting("NEO4J_USER", "neo4j"), setting("NEO4J_PASSWORD", "showroom-local-dev")), connection_timeout=2, connection_acquisition_timeout=3, max_transaction_retry_time=2)


def rank_products(room, candidates=None):
    candidates = CATALOG if candidates is None else candidates
    tags, excluded = tags_for(room), kept_categories(room)
    try:
        with graph_driver() as driver, driver.session() as session:
            # Product tags are editorial catalog metadata, explicitly distinct from retailer facts.
            for p in candidates:
                session.run("MERGE (p:Product {id:$id}) SET p.name=$name,p.price=$price,p.category=$category WITH p UNWIND $tags AS tag MERGE (t:Style {name:tag}) MERGE (p)-[:HAS_STYLE]->(t)", **{k:p[k] for k in ("id","name","price","category","tags")}).consume()
            session.run("MERGE (r:Room {id:$id}) SET r.budget=$budget,r.keep=$keep,r.preferences=$preferences WITH r OPTIONAL MATCH (r)-[old:PREFERS]->() DELETE old", id=room["id"], budget=room["budget"], keep=room["keep"], preferences=room["preferences"]).consume()
            session.run("MATCH (r:Room {id:$id}) UNWIND $tags AS tag MERGE (t:Style {name:tag}) MERGE (r)-[:PREFERS]->(t)", id=room["id"], tags=tags).consume()
            rows = list(session.run("MATCH (r:Room {id:$id}), (p:Product) WHERE p.id IN $ids AND (p.price IS NULL OR p.price <= r.budget) AND NOT p.category IN $excluded OPTIONAL MATCH (r)-[:PREFERS]->(t:Style)<-[:HAS_STYLE]-(p) RETURN p.id AS id, p.price AS price, count(t) AS score, collect(t.name) AS matches ORDER BY p.price IS NULL, score DESC, price ASC, id ASC", id=room["id"], excluded=excluded, ids=[p["id"] for p in candidates]))
            ranked = [(dict(row)["id"], dict(row)["score"], dict(row)["matches"]) for row in rows]
        status = "connected"
        explanation = "Neo4j ranks Product → HAS_STYLE → Style ← PREFERS ← Room paths, then respects the remaining budget and keep constraints."
    except Exception:
        ranked = [(p["id"], len(set(p["tags"]) & set(tags)), sorted(set(p["tags"]) & set(tags))) for p in candidates if p["category"] not in excluded and (p["price"] is None or p["price"] <= room["budget"])]
        ranked.sort(key=lambda item: (-item[1], next(p["price"] if p["price"] is not None else float("inf") for p in candidates if p["id"] == item[0]), item[0]))
        status = "fallback"
        explanation = "Neo4j is unavailable. Recommendations currently use local tag ranking over the retrieved candidates; no live graph query is claimed."
    selected, remaining, categories = [], round(room["budget"] * 100), set()
    for product_id, score, matches in ranked:
        p = dict(next(p for p in candidates if p["id"] == product_id))
        cents = round(p["price"] * 100) if p["price"] is not None else 0
        if cents > remaining or (p.get("source") != "exa_amazon" and p["category"] in categories): continue
        remaining -= cents
        categories.add(p["category"])
        p.update(score=score, matched_styles=matches, selected=True, reason=(f"Matches {', '.join(matches)} through {'Neo4j style relationships' if status == 'connected' else 'local catalog tags'}." if matches else "Fits the available budget and does not replace a kept item."))
        if p["price"] is None: p["reason"] = "Price unavailable; check the Amazon listing before budgeting. " + p["reason"].replace("Fits the available budget and does not replace a kept item.", "Does not replace a kept item.")
        selected.append(p)
        if len(selected) >= 6: break
    return selected, {"status": status, "explanation": explanation, "matched_tags": tags, "excluded_categories": excluded, "relationship_count": sum(p["score"] for p in selected)}


class RoomInput(BaseModel):
    name: str = Field(default="My living room", min_length=1, max_length=120)
    budget: float = Field(default=1500, ge=0, le=1000000, allow_inf_nan=False)
    preferences: list[str] = Field(default_factory=lambda:["Warm minimalism"], max_length=20)
    keep: list[str] = Field(default_factory=list, max_length=20)


class RoomPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    budget: float | None = Field(default=None, ge=0, le=1000000, allow_inf_nan=False)
    preferences: list[str] | None = Field(default=None, max_length=20)
    keep: list[str] | None = Field(default=None, max_length=20)


class DirectiveInput(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class AckInput(BaseModel):
    status: Literal["accepted", "failed"]
    message: str | None = Field(default=None, max_length=500)


class TokenInput(BaseModel):
    room_id: str


class RecommendationInput(BaseModel):
    source: Literal["catalog", "amazon"] = "catalog"
    query: str = Field(default="", max_length=1600)


class ExportInput(BaseModel):
    approval_id: str
    approved: bool = False


app = FastAPI(title="SHOWROOM", version="0.1.0")
install_access_gate(app)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5190", "http://127.0.0.1:5190"], allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])
app.mount("/uploads", StaticFiles(directory=DATA / "uploads"), name="uploads")


@app.get("/api/health")
def health():
    try:
        with graph_driver() as driver: driver.verify_connectivity()
        graph_status = "connected"
    except Exception: graph_status = "unavailable"
    return {"status":"ok", "integrations":{
        "reactor":{"configured": bool(setting("REACTOR_API_KEY")), "status": PROVIDER_STATUS["reactor"] if setting("REACTOR_API_KEY") else "missing_key"},
        "ambiguous":{"configured": bool(setting("AMBIGUOUS_API_KEY")), "status": PROVIDER_STATUS["ambiguous"] if setting("AMBIGUOUS_API_KEY") else "missing_key"},
        "exa":{"configured": bool(setting("EXA_API_KEY")), "status":"configured" if setting("EXA_API_KEY") else "missing_key"},
        "openai":{"configured": bool(setting("OPENAI_API_KEY")), "status":"configured" if setting("OPENAI_API_KEY") else "missing_key"},
        "neo4j":{"configured": True, "status": graph_status}}, "catalog":{"count":len(CATALOG),"price_checked_at":"2026-09-12","mode":"curated merchant snapshot"}}


@app.post("/api/rooms", status_code=201)
def create_room(body: RoomInput):
    room = {**body.model_dump(), "id":str(uuid.uuid4()), "image_url":None, "directives":[], "products":[], "total":0, "graph":{"status":"not_queried","explanation":"Retrieve furniture to query the room's graph context."}, "exports":[], "created_at":now()}
    return save_room(room)


@app.get("/api/rooms/{room_id}")
def read_room(room_id: str):
    return get_room(room_id)


@app.patch("/api/rooms/{room_id}")
def patch_room(room_id: str, body: RoomPatch):
    with LOCK:
        room = get_room(room_id)
        changes = body.model_dump(exclude_none=True)
        if all(room.get(key) == value for key, value in changes.items()):
            return room
        room.update(changes)
        # A changed budget or keep constraint invalidates the old shopping selection.
        room["products"], room["total"] = [], 0
        room["unpriced_count"] = 0
        room.pop("product_source", None)
        room.pop("search", None)
        room["graph"] = {"status":"not_queried","explanation":"Room constraints changed. Retrieve furniture again."}
        return save_room(room)


@app.post("/api/rooms/{room_id}/image")
async def upload_image(room_id: str, file: UploadFile = File(...)):
    content = await file.read(12 * 1024 * 1024 + 1)
    if len(content) > 12 * 1024 * 1024: raise HTTPException(413, "Choose an image smaller than 12 MB.")
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.width * source.height > 40_000_000: raise HTTPException(413, "Choose an image below 40 megapixels.")
            picture = ImageOps.exif_transpose(source).convert("RGB")
            picture.thumbnail((1920,1920))
            # Neutral letterboxing preserves the complete room instead of hiding constraints.
            preview = ImageOps.pad(picture, (1280,720), color="#e7e2d9")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(415, "This file could not be decoded as an image.")
    with LOCK:
        room = get_room(room_id)
        name = f"{room_id}-{uuid.uuid4().hex[:8]}.jpg"
        preview.save(DATA / "uploads" / name, quality=90)
        room["image_url"] = f"/uploads/{name}"
        return save_room(room)


@app.post("/api/rooms/{room_id}/directives")
def create_directive(room_id: str, body: DirectiveInput):
    with LOCK:
        room = get_room(room_id)
        directive = {"id":str(uuid.uuid4()),"instruction":body.instruction.strip(),"prompt":prompt_for(room, body.instruction),"status":"pending","created_at":now()}
        room["directives"].append(directive)
        save_room(room)
        return {"directive":directive,"room":room}


@app.post("/api/rooms/{room_id}/directives/{directive_id}/ack")
def acknowledge(room_id: str, directive_id: str, body: AckInput):
    with LOCK:
        room = get_room(room_id)
        directive = next((d for d in room["directives"] if d["id"] == directive_id), None)
        if not directive: raise HTTPException(404,"Instruction not found.")
        directive.update(status=body.status, message=body.message, acknowledged_at=now(), acknowledgement_source="browser Reactor SDK event")
        return save_room(room)


@app.post("/api/transcriptions")
async def transcription(file: UploadFile = File(...)):
    content = await file.read(12 * 1024 * 1024 + 1)
    return await transcribe_audio(setting("OPENAI_API_KEY"), content, file.content_type or "")


@app.post("/api/rooms/{room_id}/visual-search")
async def visual_search(room_id: str, file: UploadFile = File(...), x: float = Form(..., ge=0, le=1), y: float = Form(..., ge=0, le=1)):
    room = get_room(room_id)
    before = fingerprint(room)
    content = await file.read(8 * 1024 * 1024 + 1)
    started = time.perf_counter()
    vision_metrics, search_metrics = {}, {}
    selection = await identify_furniture(setting("OPENAI_API_KEY"), content, x, y, vision_metrics)
    products, query = await search_amazon(setting("EXA_API_KEY"), selection["query"], room, search_metrics)
    graph_started = time.perf_counter()
    for product in products:
        product["tags"] = [tag for tag in tags_for(room) if tag in product["name"].lower()]
    with LOCK:
        if fingerprint(get_room(room_id)) != before:
            raise HTTPException(409, "Your brief changed during visual search. Select the piece again.")
        products, graph = rank_products(room, products)
    if not products:
        raise HTTPException(404, f"Identified {selection['label']}, but no Amazon matches fit your current budget and keep constraints. Try another piece or adjust the brief.")
    products = rank_visual_matches(products, selection)
    # Inspecting a piece does not replace the approved shopping list or saved brief.
    return {"selection":selection, "products":products, "graph":graph, "query":query, "performance":{"vision":vision_metrics,"search":search_metrics,"graph_ms":round((time.perf_counter()-graph_started)*1000,2),"total_ms":round((time.perf_counter()-started)*1000,2)}}


@app.post("/api/rooms/{room_id}/recommendations")
async def recommend(room_id: str, body: RecommendationInput = RecommendationInput()):
    room = get_room(room_id)
    before = fingerprint(room)
    candidates = None
    search_metrics = {}
    if body.source == "amazon":
        candidates, query = await search_amazon(setting("EXA_API_KEY"), body.query, room, search_metrics)
        excluded = kept_categories(room)
        candidates = [p for p in candidates if p['category'] not in excluded and not any(alias in p['name'].lower() for category in excluded for alias in {'sofa':['sofa','couch','loveseat'],'table':['table'],'rug':['rug','carpet'],'lighting':['lamp','lighting']}.get(category,[]))]
        for p in candidates:
            p['tags'] = [tag for tag in tags_for(room) if tag in p['name'].lower()]
        if not candidates: raise HTTPException(404, 'Exa returned no usable Amazon product listings for this request. Try a different search; your shopping list is unchanged.')
    with LOCK:
        current = get_room(room_id)
        if fingerprint(current) != before: raise HTTPException(409, 'Your brief changed during search. Search again with the updated brief.')
        room = current  # Preserve concurrent export receipts outside the brief fingerprint.
        room["products"], room["graph"] = rank_products(room, candidates)
        if not room["products"]: raise HTTPException(404, "No retrieved items fit the current budget and keep constraints. Try a different search.")
        room["total"] = sum(round(p["price"] * 100) for p in room["products"] if p["price"] is not None) / 100
        room["unpriced_count"] = sum(p["price"] is None for p in room["products"])
        room["product_source"] = body.source
        if body.source == "amazon":
            room["search"] = {"query":query,"provider":"exa","domain":"amazon.com","retrieved_at":now(),"performance":search_metrics}
            room["graph"]["explanation"] += " Amazon listings were retrieved through Exa. Only source-quoted prices enter the subtotal; missing prices require checking Amazon."
        return save_room(room)


class ProviderHTTPError(HTTPException):
    """Keep safe upstream diagnostics without confusing rejection with transport failure."""
    def __init__(self, status_code, detail, upstream_status, diagnostics):
        super().__init__(status_code, detail)
        self.upstream_status = upstream_status
        self.diagnostics = diagnostics


def provider_diagnostics(response, key):
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    secrets = [key] + [str(value) for name, value in dotenv_values(ROOT / ".env").items()
                       if value and any(part in name for part in ("KEY", "TOKEN", "PASSWORD", "SECRET"))]
    result = {"upstream_status": response.status_code}
    for name in ("error", "code", "message", "request_id"):
        if isinstance(payload.get(name), str):
            value = payload[name]
            for secret in secrets:
                value = value.replace(secret, "[REDACTED]")
            value = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", value, flags=re.I)
            result[name] = " ".join(value.split())[:1000]
    return result


async def provider_request(provider, method, path, **kwargs):
    key_name = "REACTOR_API_KEY" if provider == "reactor" else "AMBIGUOUS_API_KEY"
    key = setting(key_name)
    if not key: raise HTTPException(503, f"{provider.capitalize()} access is not configured. Add {key_name} to the server .env file and retry.")
    base = "https://api.reactor.inc" if provider == "reactor" else "https://app.ambiguous.ai"
    headers = {"Reactor-API-Key":key} if provider == "reactor" else {"Authorization":f"Bearer {key}","API-Version":"1"}
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.request(method, base+path, headers=headers, **kwargs)
        if response.status_code >= 400:
            PROVIDER_STATUS[provider] = "capacity" if response.status_code == 429 else "error"
            code = 429 if response.status_code == 429 else 503 if response.status_code in (401,403) else 502
            message = "No capacity is available. Wait briefly and retry." if code == 429 else "Access was rejected. Check the server credential and permissions." if code == 503 else "The provider could not complete this request. Retry without changing your room."
            diagnostics = provider_diagnostics(response, key)
            diagnostic = diagnostics.get("error") or diagnostics.get("code") or message
            raise ProviderHTTPError(code, f"{provider.capitalize()} (HTTP {response.status_code}): {diagnostic}", response.status_code, diagnostics)
        PROVIDER_STATUS[provider] = "connected"
        return response.json()
    except (httpx.RequestError, ValueError):
        PROVIDER_STATUS[provider] = "unavailable"
        raise HTTPException(502, f"{provider.capitalize()} could not be reached. Your room is saved locally; please retry.")


@app.post("/api/reactor/token")
async def reactor_token(body: TokenInput):
    room = get_room(body.room_id)
    if not room["image_url"]: raise HTTPException(409,"Upload a room photo before starting Orbis.")
    data = await provider_request("reactor", "POST", "/tokens", json={"expires_after":900,"authorization_details":[{"type":"session","resources":{"models":{"match":[MODEL]}},"constraints":{"max_sessions":1}}]})
    jwt = data.get("jwt")
    if not jwt: raise HTTPException(502,"Reactor did not return a scoped session token.")
    return {"jwt":jwt,"model":MODEL,"api_url":"https://api.reactor.inc","prompt":prompt_for(room),"expires_after":900}


@app.get("/api/ambiguous/documents")
async def ambiguous_documents():
    data = await provider_request("ambiguous", "GET", "/api/documents", params={"limit":20})
    # Return only fields useful to this design journey, not owner emails or unrelated full content.
    rows = data.get("data", []) if isinstance(data,dict) else data
    return {"documents":[{k:d.get(k) for k in ("id","title","type","updated_at")} for d in rows], "status":"connected"}


@app.get("/api/ambiguous/documents/{document_id}")
async def ambiguous_document(document_id: str):
    if not re.fullmatch(r"[\w-]+", document_id): raise HTTPException(400,"Invalid document identifier.")
    data = await provider_request("ambiguous", "GET", f"/api/documents/{document_id}")
    return {k:data.get(k) for k in ("id","title","type","content")}


def export_content(room):
    lines = [f"# SHOWROOM — {room['name']}", "", f"Budget: USD {room['budget']:.2f}", f"Preferences: {', '.join(room['preferences'])}", f"Keep unchanged: {', '.join(room['keep']) or 'Original room geometry'}", "", "## Accepted design instructions"]
    lines += [f"- {d['instruction']}" for d in room['directives'] if d['status']=='accepted'] or ["No live instructions have been acknowledged."]
    lines += ["", "## Shopping list", "", "| Product | Price (USD) | Dimensions | Source |", "| --- | ---: | --- | --- |"]
    rows = [["Product","Price (USD)","Dimensions","Retailer source"]]
    for p in room["products"]:
        price_text = f"{p['price']:.2f}" if p["price"] is not None else "Not quoted"
        lines.append(f"| {p['name']} | {price_text} | {p['dimensions']} | {p['source_url']} |")
        rows.append([p["name"],p["price"] if p["price"] is not None else "Not quoted",p["dimensions"],p["source_url"]])
    rows.append(["Priced subtotal" if room.get("unpriced_count") else "Total",room["total"],"Excludes unquoted items, tax, shipping and accessories",""])
    lines += ["",f"{'Priced subtotal' if room.get('unpriced_count') else 'Merchandise total'}: USD {room['total']:.2f}. Tax, shipping, bulbs and rug underlay are not included.","", (f"Amazon listings retrieved through Exa. {room.get('unpriced_count',0)} items have no quoted price and are excluded from the subtotal. Confirm current price, availability and dimensions on each Amazon listing." if room.get("product_source")=="amazon" else "Prices are a curated IKEA US snapshot checked 2026-09-12. Confirm current prices, availability and dimensions before purchase."), "", "Generated video is an illustrative preview, not a dimensionally accurate rendering or proof that a depicted product exists.", "", room["graph"]["explanation"]]
    return "\n".join(lines), rows


@app.post("/api/rooms/{room_id}/export-preview")
def export_preview(room_id: str):
    with LOCK:
        room = get_room(room_id)
        if not room["products"]: raise HTTPException(409,"Retrieve a shopping list before reviewing the export.")
        content, rows = export_content(room)
        recipient = setting("SHOWROOM_SHARE_EMAIL").strip()
        if recipient and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient):
            raise HTTPException(503, "The configured sharing email is invalid. Correct SHOWROOM_SHARE_EMAIL on the server.")
        approval = {"approval_id":str(uuid.uuid4()),"room_id":room_id,"fingerprint":fingerprint(room),"title":f"SHOWROOM — {room['name']}","content":content,"shopping_rows":rows,"created_at":now(),"completed":False,"exports":[]}
        approval["share_recipient"] = recipient or None
        with db() as con: con.execute("INSERT INTO approvals VALUES (?,?,?)",(approval["approval_id"],room_id,json.dumps(approval)))
        return {k:approval[k] for k in ("approval_id","title","content","shopping_rows","share_recipient")}


@app.post("/api/rooms/{room_id}/export")
async def export_approved(room_id: str, body: ExportInput):
    async with EXPORT_LOCKS.setdefault(body.approval_id, asyncio.Lock()):
        return await perform_export(room_id, body)


@app.post("/api/rooms/{room_id}/export-reconcile")
async def reconcile_export(room_id: str, body: ExportInput):
    """Explicit recovery only when complete live lists prove an empty workspace.

    Does not create anything. Existing/partial listings remain blocked for inspection.
    """
    if body.approved is not True:
        raise HTTPException(403, "Approval is required to reconcile this reviewed export.")
    async with EXPORT_LOCKS.setdefault(body.approval_id, asyncio.Lock()):
        with db() as con:
            record = con.execute("SELECT body FROM approvals WHERE id=? AND room_id=?", (body.approval_id, room_id)).fetchone()
        if not record:
            raise HTTPException(404, "Approval preview not found.")
        approval = json.loads(record[0])
        if approval.get("write_status") != "uncertain" or approval["exports"]:
            raise HTTPException(409, "Only an uncertain save without a returned identifier can be reconciled this way.")
        if approval["fingerprint"] != fingerprint(get_room(room_id)):
            raise HTTPException(409, "The reviewed room changed; this recovery cannot authorize new content.")
        receipts = []
        for path, params in (("/api/documents", {"limit": 200}), ("/api/activity", {"resource_type": "document", "limit": 100})):
            data = await provider_request("ambiguous", "GET", path, params=params)
            if not isinstance(data, dict) or data.get("data") != [] or data.get("has_more") is not False or data.get("total") != 0:
                raise HTTPException(409, "The workspace is not provably empty. Inspect existing documents; no retry has been enabled.")
            receipts.append({"path": path, "checked_at": now(), "total": 0, "has_more": False})
        approval["write_status"] = "reconciled_empty"
        approval["reconciliation"] = {"reason": "Complete document and document-activity lists are empty after the failed request", "reads": receipts}
        with db() as con:
            con.execute("UPDATE approvals SET body=? WHERE id=?", (json.dumps(approval), body.approval_id))
        return {"approval_id": body.approval_id, "write_status": approval["write_status"], "reconciliation": approval["reconciliation"], "external_write_performed": False}


async def perform_export(room_id: str, body: ExportInput):
    if body.approved is not True: raise HTTPException(403,"Review and approve the exact design brief and shopping list before saving to Ambiguous.")
    with LOCK:
        room = get_room(room_id)
        with db() as con: record = con.execute("SELECT body FROM approvals WHERE id=? AND room_id=?",(body.approval_id,room_id)).fetchone()
        if not record: raise HTTPException(404,"Approval preview not found.")
        approval = json.loads(record[0])
        if not approval["exports"] and approval["fingerprint"] != fingerprint(room): raise HTTPException(409,"This room changed after review. Review a fresh export before approving.")
        if approval.get("write_status") in ("in_flight", "uncertain") and not approval["exports"]:
            raise HTTPException(409,"A previous save has an uncertain outcome. Inspect your Ambiguous workspace before creating another preview; automatic duplicate writes are blocked.")
    if approval["completed"]:
        return await finish_export_sharing(room_id, approval)
    # One approved document contains both the design brief and the complete shopping list.
    # This avoids an undocumented spreadsheet authoring schema and is inspectable via the real API.
    if not approval["exports"]:
        # Check access before recording an outbound write intent.
        if not setting("AMBIGUOUS_API_KEY"):
            raise HTTPException(503,"Ambiguous access is not configured. Add AMBIGUOUS_API_KEY to the server .env file and retry.")
        approval["write_status"] = "in_flight"
        with db() as con: con.execute("UPDATE approvals SET body=? WHERE id=?",(json.dumps(approval),body.approval_id))
        try:
            created = await provider_request("ambiguous","POST","/api/documents",json={"type":"doc","title":approval["title"],"content":approval["content"],"visibility":"restricted","labels":["showroom"]})
        except HTTPException as exc:
            # A transport/server failure can occur after the provider committed the document.
            upstream = getattr(exc, "upstream_status", None)
            rejected = (400 <= upstream < 500 and upstream not in (408, 425)) if upstream else exc.status_code in (429,503)
            approval["write_status"] = "rejected" if rejected else "uncertain"
            approval["last_error"] = getattr(exc, "diagnostics", {"local_status": exc.status_code})
            with db() as con: con.execute("UPDATE approvals SET body=? WHERE id=?",(json.dumps(approval),body.approval_id))
            raise
        doc_id = created.get("id")
        if not doc_id: raise HTTPException(502,"Ambiguous returned no document identifier. Inspect your workspace before retrying.")
        exported = {"id":doc_id,"title":created.get("title",approval["title"]),"type":"doc","url":created.get("url") or f"https://app.ambiguous.ai/docs/{doc_id}","api_url":f"https://app.ambiguous.ai/api/documents/{doc_id}","verified":False,"created_at":now(),"approval_id":body.approval_id}
        approval["exports"] = [exported]
        approval["write_status"] = "created"
        # Persist the returned identifier before readback so a read failure cannot duplicate the write.
        with LOCK:
            room=get_room(room_id);room["exports"].append(exported);save_room(room)
            with db() as con: con.execute("UPDATE approvals SET body=? WHERE id=?",(json.dumps(approval),body.approval_id))
    exported = approval["exports"][0]
    readback = await provider_request("ambiguous","GET",f"/api/documents/{exported['id']}")
    raw_content = readback.get("content") or ""
    # Ambiguous normalizes Markdown to ProseMirror. Verify every authored text cell/line,
    # including source URLs and prices, against its rendered text rather than truthiness.
    try:
        doc_tree = json.loads(raw_content)
        def text_nodes(node):
            if isinstance(node,dict):
                return ([node["text"]] if isinstance(node.get("text"),str) else []) + [t for child in node.get("content",[]) for t in text_nodes(child)]
            return []
        actual_text = " ".join(text_nodes(doc_tree))
    except (ValueError, TypeError): actual_text = raw_content
    normalize = lambda text: " ".join(text.split())
    actual_text = normalize(actual_text)
    expected_parts = [piece.strip().lstrip("#- ") for line in approval["content"].splitlines() for piece in (line.split("|") if line.startswith("|") else [line]) if piece.strip() and not re.fullmatch(r"[\s|:-]+",piece)]
    exported["verified"] = readback.get("id") == exported["id"] and readback.get("title") == approval["title"] and all(normalize(piece) in actual_text for piece in expected_parts)
    exported["verification"] = "title and all authored text verified" if exported["verified"] else "document retrieved, content verification incomplete"
    exported["verified_at"] = now()
    approval["completed"] = exported["verified"]
    with LOCK:
        room=get_room(room_id)
        room["exports"] = [exported if e["id"]==exported["id"] else e for e in room["exports"]]
        save_room(room)
        with db() as con: con.execute("UPDATE approvals SET body=? WHERE id=?",(json.dumps(approval),body.approval_id))
    return await finish_export_sharing(room_id, approval)


async def finish_export_sharing(room_id, approval):
    def persist():
        with LOCK:
            room = get_room(room_id)
            by_id = {item["id"]: item for item in approval["exports"]}
            room["exports"] = [by_id.get(item["id"], item) for item in room["exports"]]
            save_room(room)
            with db() as con:
                con.execute("UPDATE approvals SET body=? WHERE id=?", (json.dumps(approval), approval["approval_id"]))
    for exported in approval["exports"]:
        await share_document(exported, approval.get("share_recipient"), provider_request, persist)
    return {"exports":approval["exports"], "room":get_room(room_id)}


# Last route: production frontend and pinned Reactor runtime share the API origin.
if (ROOT / "frontend/dist/index.html").is_file():
    app.mount("/", StaticFiles(directory=ROOT / "frontend/dist", html=True), name="frontend")
