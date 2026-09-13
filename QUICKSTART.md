# SHOWROOM

**Hosted studio:** [showroom-q4s4.onrender.com](https://showroom-q4s4.onrender.com) · open without sign-in. See the [Render deployment guide](docs/deploy-render.md).

**Design the room. Keep the decisions.**

SHOWROOM brings a room photo, a spending limit, live visual direction and a sourced shopping list into one workspace. The intended journey is: upload a room → set preferences and what stays → start Orbis → steer twice → inspect products → approve an Ambiguous design brief and shopping-list handoff.

**Verified:** real Orbis frames and two visibly different directions; live Neo4j recommendations; 52 backend tests, including five written by Qoder. An approved Ambiguous document containing the exact brief and $219.97 shopping list was saved and read back successfully. [Inspect the saved document](https://app.ambiguous.ai/docs/4adbc629-1359-4b19-bb75-74e9f38d26a3) (workspace access required); see [save evidence](docs/evidence/approved-save.json).

![Actual live SHOWROOM workspace](artifacts/screenshots/live-change-2-final.png)

Generated video is an illustrative preview. Source URLs, reference images, dimensions and quoted prices support purchasing decisions; the application does not infer that a rendered object is an exact purchasable SKU. Prices are source quotes or catalog snapshots and exclude tax and shipping unless indicated.

## Run locally

Requires Python 3.11+, Node 20.19+ or 22.12+ (tested with 24.18), and Docker Desktop for the local Neo4j database. Default ports: frontend **5190**, backend **8190**, Neo4j **7474 / 7687**.

```bash
test -f .env || cp .env.example .env
# Add your authorized integration credentials to .env.
docker compose up -d
bash scripts/start-backend.sh
```

In another terminal:

```bash
bash scripts/start-frontend.sh
```

Open [SHOWROOM](http://localhost:5190). Check the backend at [health](http://localhost:8190/api/health) and [interactive API documentation](http://localhost:8190/docs).

The frontend displays actual integration availability. A missing credential, model capacity error or unsuccessful save is shown explicitly. An unavailable integration does not become a simulated successful operation.

## Direct, pause, and search

Use the maximize control to keep the room, direction box, microphone and Pause/Resume controls together. Pause holds the visible frame immediately and asks Orbis to pause generation at the next chunk boundary. You can type or dictate another direction while paused, then resume generation from the held preview. Exit fullscreen or press Escape without losing your draft. [Actual live pause/resume evidence](docs/evidence/player-live-verification.json).

Furniture search defaults to **Amazon through Exa**. Add `EXA_API_KEY` to the server `.env`; the explicit source selector also offers the original curated IKEA catalog. Search requests four results in Exa fast mode. Page content can be reused for six hours, and normalized searches are cached in memory for fifteen minutes. Repeated frame identification is cached for ten minutes. Only Amazon product pages are admitted. Source-quoted USD prices contribute to the subtotal; missing prices show “Check price” and are excluded, so the subtotal is not a complete budget estimate when prices are missing. Confirm prices, availability and dimensions at Amazon.

The microphone beside either input records up to 45 seconds. Stop to transcribe with OpenAI, review the text, then send the direction or run the search. Add `OPENAI_API_KEY` to `.env`. Audio goes through the backend to OpenAI's `gpt-4o-mini-transcribe`; the app does not persist recordings. Cancel discards an active recording. Permission failures leave typing available. [Actual OpenAI → Exa → Neo4j verification](docs/evidence/voice-and-player.md).

Browser checks for these controls: `node scripts/test-player-controls.cjs` after installing `tooling`. This uses a mocked provider and synthetic video, never disguised as live integration evidence. The separate `node scripts/test-live-player.cjs --live` command explicitly uses one paid Orbis session and ends it after checking pause, paused steering and resume.

## Shop the frame and replay your room

Click a piece in the live, paused or replayed room. SHOWROOM sends that selected frame and point to OpenAI vision, then uses Exa to find visually similar Amazon products within the room brief. OpenAI extracts item type, colors, apparent material and shape; a brand is included only with a readable marking. These attributes guide the query and rank listing-title matches. Matches open inside the player, including fullscreen; click a match to open Amazon. These are visual alternatives, not exact SKU identifications. Inspecting a piece does not replace the shopping list. Ambiguous/background clicks and provider failures have recoverable messages.

New Orbis sessions record the room automatically in the browser, at up to 1280 pixels wide. **Save & rewind** finishes a clip and opens its replay timeline. Drag the timeline, rewind ten seconds, choose a saved clip, or **Download video**. Saving a clip does not end the Orbis session; **Return to live** brings back live direction controls, and **Record next clip** starts another recording. Ending or disconnecting a session also finalizes its recording.

Clips are saved in IndexedDB on this browser and origin, not in Ambiguous or on the server. Recordings contain the room video only, with no microphone audio or interface overlays. Download a file to keep it independently of browser storage. Each clip is limited to ten minutes or approximately 120 MB; storage failures preserve the download option. Save before closing the tab. The browser chooses WebM or MP4 according to supported recording codecs. Background tabs may record fewer frames.

The existing two-minute pitch video predates these controls. The new [frame-shopping and replay verification](docs/evidence/video-shopping.md) distinguishes actual provider evidence from synthetic browser tests.

## Render hosting

The [Render deployment guide](docs/deploy-render.md) includes the reviewed Docker setup, persistent private Neo4j, optional studio sign-in, costs and deployment commands.

## Integration access

All service credentials belong in the root `.env`, which is ignored by Git. Use `.env.example` for the precise variable names. Never put a service key in a `VITE_*` variable.

- **Reactor / Orbis:** authorized Reactor API key and access to the Orbis model. The backend issues scoped access for the browser streaming SDK. A real browser session and two visible direction changes are recorded in the verification evidence.
- **Exa / Amazon:** `EXA_API_KEY` enables real Amazon product discovery with source links and quoted prices where available.
- **OpenAI:** `OPENAI_API_KEY` enables speech-to-text for both room directions and furniture searches.
- **Neo4j:** use the local Docker instance or configure an accessible server. The graph stores connected room and product context. UI and health responses distinguish Neo4j from any local fallback.
- **Ambiguous:** authorized workspace access for reads and approved document writes containing the design brief and shopping table. A successful save must return inspectable identifiers/links.
- **Qoder:** optional developer tooling, not a browser dependency. Create a token at [Qoder integrations](https://qoder.com/account/integrations). Qoder authored five independently passing journey tests; see [engineering evidence](docs/evidence/qoder.md).

## What is delivered

| Artifact | Location |
|---|---|
| Five-page pitch deck | [PDF](artifacts/showroom-deck.pdf), [editable HTML](docs/deck/showroom-deck.html) |
| Two-minute demonstration | [MP4](artifacts/video/showroom-demo.mp4), [captions](artifacts/video/showroom-demo.srt), [poster](artifacts/video/poster.jpg) |
| Application screenshots | [Desktop](artifacts/screenshots/desktop.png), [mobile](artifacts/screenshots/mobile.png), [shopping](artifacts/screenshots/shopping.png) |
| Architecture | [Editable SVG](docs/architecture.svg) |
| Verification and limitations | [Evidence record](docs/evidence/verification.md) |
| Event and disclosure record | [Eligibility](docs/evidence/event-eligibility.md) |
| Three publication packages | [Publication index](docs/publication.md) |

![SHOWROOM architecture](docs/architecture.svg)

## Verify the application

With all local services started, install the browser-check dependencies from the repository root:

```bash
npm ci --prefix tooling
```

The browser checks use Google Chrome at its default macOS application path, or an executable selected with `export CHROME_PATH="/absolute/path/to/chrome"`. If neither is available, install Playwright Chromium:

```bash
node tooling/node_modules/playwright/cli.js install chromium
```

Then run:

```bash
.venv/bin/python -m pytest backend -q
node scripts/smoke-browser.cjs
```

The browser smoke uses the actual application and local Neo4j. It does not perform external writes.

## Reproduce artifacts

The main MP4 contains an actual Orbis session. [Recovery footage](artifacts/video/showroom-recovery.mp4) is the separately labeled earlier local recording while credentials were unavailable; it is not live-provider evidence. Generated geometry, camera position and furniture can drift from the input photo, so the preview is illustrative.

The capture tools require Chrome plus `ffmpeg`/`ffprobe` on your PATH. They record actual browser behavior against the local application. Run captures only with the sample room or with permission to include the uploaded image in published material.

```bash
npm ci --prefix tooling
node scripts/capture-demo.cjs
node scripts/build-deck.cjs
python3 scripts/build-publication.py
```

The deck has exactly five slides: hero photograph with SHOWROOM title only; problem / why; demo-video placeholder; architecture focused on Ambiguous, OpenAI, Exa, Neo4j, Qoder and VISKO / Orbis; and a QR code for the Render studio. The demo placeholder links to the existing two-minute MP4 until a YouTube URL is supplied. Edit `docs/deck/showroom-deck.html` to change the copy or video link. To change the QR destination, install `tooling/deck-requirements.txt`, run `python scripts/set-deck-url.py https://your-studio.onrender.com`, then rebuild the deck.

## One codebase, three presentations

The live-video, Ambiguous-coworker and Qoder/Neo4j packages are README variants of this **same SHOWROOM monorepo**. Each package includes its source digest, proposed repository description and topics in `publication.json`. None is represented as a separate independent build. Cross-event eligibility was explicitly confirmed by the participant on September 12, 2026; see the [source and confirmation record](docs/evidence/event-eligibility.md).

This project was created as a fresh SHOWROOM application during the sprint. It uses public libraries and SDKs. The sample room’s provenance is recorded in [frontend/ASSETS.md](frontend/ASSETS.md). No prize, adoption target, DGX hardware execution or successful third-party integration is claimed without evidence.

## Public repository presentations

[Canonical live video](https://github.com/KaushikSiva/showroom), [Ambiguous coworker](https://github.com/KaushikSiva/showroom-coworker), and [Qoder / Neo4j](https://github.com/KaushikSiva/showroom-graph) present this same codebase with focused READMEs. See [publication status and source disclosure](docs/publication.md).

### Automatic Ambiguous sharing

Set the server-only `SHOWROOM_SHARE_EMAIL` to the intended recipient. New save previews show that address; approving a save authorizes viewer access to that document. The recipient is frozen in the approval, so later configuration changes cannot redirect it. The app verifies the saved content, requests an invitation and checks permissions. It displays confirmed access, a pending invitation, or a sharing problem separately from document-save success. Use **Check sharing** / **Retry sharing** on the saved result to recover without creating another document. Invitations may require the recipient to accept by email. No whole-workspace access is granted. Old approvals without a sharing recipient stay unchanged.
