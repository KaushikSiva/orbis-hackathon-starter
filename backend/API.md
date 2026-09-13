# SHOWROOM backend contract

Start from the repository root with `./scripts/start-backend.sh`. FastAPI binds `127.0.0.1:8190`; OpenAPI is available at `/docs`. Secrets are read from the root `.env` for each provider request so updating credentials needs no restart. Local room data and uploads live in ignored `backend/data/`. This is a local single-user prototype, not a multi-user deployment.

| Endpoint | Request | Result |
| --- | --- | --- |
| GET `/api/health` | — | Provider configured/status booleans and Neo4j connectivity; no credentials |
| POST `/api/rooms` | `{name,budget,preferences:[],keep:[]}` | Persisted room, HTTP 201 |
| GET/PATCH `/api/rooms/{id}` | Patch any room constraints | Persisted room; patch invalidates old shopping selection |
| POST `/api/rooms/{id}/image` | multipart `file` | Decoded JPEG preview, letterboxed to preserve complete composition |
| POST `/api/reactor/token` | `{room_id}` | `{jwt,model,api_url,prompt,expires_after}` scoped to one Orbis session for 900 seconds |
| POST `/api/rooms/{id}/directives` | `{instruction}` | `{directive,room}`, pending instruction and full constraint-aware prompt |
| POST `/api/rooms/{id}/directives/{did}/ack` | `{status:"accepted"|"failed",message?}` | Persisted browser SDK acknowledgement audit |
| POST `/api/rooms/{id}/recommendations` | — | Selected products, cents-summed total and graph explanation |
| GET `/api/ambiguous/documents` | — | Real workspace document summaries |
| GET `/api/ambiguous/documents/{id}` | — | Real selected document content |
| POST `/api/rooms/{id}/export-preview` | — | `{approval_id,title,content,shopping_rows}`; no external write |
| POST `/api/rooms/{id}/export` | `{approval_id,approved:true}` | Approved private Ambiguous doc containing brief and shopping list, receipt and verified readback |
| POST `/api/rooms/{id}/export-reconcile` | `{approval_id,approved:true}` | Explicit recovery of an uncertain save only when complete real document and document-activity lists are empty; performs no external write |

Curated catalog prices are an **IKEA US snapshot checked September 12, 2026**, not live inventory or a checkout quote. Product source URLs, dimensions, and checked dates are stored in `catalog.json`. Editorial style tags are SHOWROOM metadata. Merchandise totals exclude tax, shipping, bulbs, and rug underlay. Reference images are retailer imagery; IKEA Estonia/Turkey/Portugal references show the same named design where US media extraction was unavailable. Follow the US product source to verify the purchasable variant.

Neo4j ranking traverses `Room -[:PREFERS]-> Style <-[:HAS_STYLE]- Product`, orders by matching relationship count then price, and selects within the remaining budget. Kept furniture categories are excluded. If Neo4j cannot execute the query, the result explicitly says `graph.status="fallback"` and uses local catalog tag ranking. Connectivity health does not certify a successful recommendation query.

Export approval is bound to the reviewed room, accepted instruction history, and selected catalog items. A per-approval asynchronous lock prevents concurrent duplicate writes. Returned identifiers are persisted before readback; repeated saves retry verification rather than create another document. A network/server failure with an unknown create outcome blocks automatic retry. Retrieval checks the returned identifier, exact title and every authored text part after Markdown-to-ProseMirror conversion. A receipt can exist with `verified:false`; the UI must retain that distinction. Documents are private and no email, chat, or sharing operation is performed.

SDK acknowledgements are reported by the local browser; this audit is not cryptographically attested provider evidence. Actual video playback must be observed in the browser to claim a live stream.

Provider failures preserve upstream HTTP status and sanitized error fields in the local approval receipt. Definitive input/access rejection can be retried after correcting its cause; network/server uncertainty remains blocked. The explicit reconciliation endpoint requires the same unchanged approval, an uncertain terminal request, no returned identifier, and two complete empty provider lists. Existing documents, pagination, missing fields, or read errors leave the write blocked. Successful reconciliation records its GET evidence and enables a separate retry of the same approved content; it never creates a document itself.

Provider references used for implementation:

- [Reactor Orbis Dynamic API](https://www.reactor.inc/models/visko-orbis-dynamic/api): scoped `POST /tokens`, model resource match and short-lived token.
- [Ambiguous OpenAPI](https://app.ambiguous.ai/api/openapi.json): `POST /api/documents`, Markdown string content, `restricted` visibility (the provider's private document mode, documented by document visibility/revoke-link endpoints), `GET /api/documents/{id}`.
- [Ambiguous recipes](https://www.ambiguous.ai/agents/recipes): inspectable `https://app.ambiguous.ai/docs/{id}` links.

Run local contract tests with `.venv/bin/python -m pytest backend -q`. Mocked provider tests prove contract and failure handling only; they are not evidence of real provider access.

## Amazon search and voice input

`POST /api/rooms/{id}/recommendations` accepts `{ "source": "amazon", "query": "wood side table" }` for live Exa search. Omitting source preserves the curated catalog contract; the browser defaults to Amazon explicitly. Search uses `EXA_API_KEY`, only admits Amazon ASIN product URLs, filters unrelated item types/kept furniture, and routes candidates through the same budget/graph selection. `products[].price` may be null. `unpriced_count` identifies prices omitted from `total`; neither zero cost nor complete budget fit is inferred. Source URL, quote and retrieval time travel with each result. A changed brief invalidates in-flight results.

`POST /api/transcriptions` accepts multipart `file` audio (WebM, MP4, MP3, WAV or Ogg), at most 12 MB, and returns `{text, provider, model}`. `OPENAI_API_KEY` remains server-side; recordings are passed in memory to OpenAI and are not persisted. The browser limits recordings to 45 seconds and lets the user review text before search/direction. Missing keys, denied access, rate limits and malformed responses are explicit errors.

References: [Exa search contract](https://exa.ai/docs/reference/search-api-guide-for-coding-agents), [OpenAI transcription](https://developers.openai.com/api/docs/guides/speech-to-text).

### Click-to-search

`POST /api/rooms/{id}/visual-search` accepts multipart `file` (decoded image, maximum 8 MB), and normalized `x` / `y` coordinates in `[0,1]`. OpenAI Responses (`gpt-4.1-mini`, `store:false`, strict JSON output) describes the marked furnishing. Exa retrieves Amazon alternatives, and existing budget/keep/Neo4j rules rank candidates. The result contains `selection`, `products`, `graph` and `query`; it does not replace the shopping list or write an external document. A changed brief returns 409, unclear selection 422, no eligible listings 404, and provider failures remain explicit. Frames are processed transiently and are not persisted by the server. Requires the existing OpenAI and Exa keys.

### Caching and matching details

Exa uses `type:fast`, `numResults:4` and `contents.maxAgeHours:6`. Successful product results are cached in memory for 900 seconds, with at most 128 entries, scoped by API-key digest and the normalized query/preferences/budget payload. Current keep rules and graph ranking are reapplied on every request; cached objects are deep-copied before room-specific mutation and preserve original product retrieval timestamps. Concurrent identical requests share a provider task. Failures/empty results are not cached. Exact processed frame/point identification has a separate 600-second cache with the same bounds and credential isolation; frames themselves are not retained in the cache. Restarting the server clears both caches.

Visual selection adds `item_type`, `colors`, `material`, `shape`, nullable `brand`, `brand_evidence` and `brand_status`. A brand enters the query only with readable marking evidence; unclear brands stay null. Listing-title attribute agreement reranks graph-eligible matches. This is not image-embedding similarity. Visual responses include `performance` stage timings/cache metadata; text-search performance is under the saved room's `search.performance`.

## Automatic sharing of approved exports

`POST /api/rooms/{id}/export-preview` includes optional `share_recipient`, read from `SHOWROOM_SHARE_EMAIL` and stored in the approval. `POST /api/rooms/{id}/export` with explicit approval shares only that frozen recipient after content verification. Saved exports expose `sharing.recipient`, `role`, `status` and `message`. `pending` means an invitation awaits acceptance; `shared` means the permissions API confirms access. `failed`, `uncertain` and `unverified` preserve a successful document save while reporting the separate sharing outcome. Repeating the same approved export checks/retries sharing without duplicating the document. A timeout is reconciled by permission reads; an uncertain invitation is never blindly resent. Missing configuration retains private-document behavior.
