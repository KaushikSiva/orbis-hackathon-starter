# SHOWROOM verification

Independent verification on September 12, 2026. This report separates real local execution from provider contract tests. No external document write or live generation was performed by the verification agent. Subsequent authenticated live execution is recorded below: actual Orbis frames and two visibly effective directions were verified; Ambiguous reads and the explicitly approved document write are live; the saved title and authored content were verified by read-back.

| Acceptance item | Result | Evidence |
| --- | --- | --- |
| Python API runs locally on 8190 | Passed | HTTP `/api/health` returned 200; detached local Uvicorn process |
| Decoded image upload and retrieval | Passed | Real multipart sample JPEG upload, returned image URL fetched successfully; invalid file returns 415 |
| Budget and keep constraints persist | Passed | HTTP/Python checks; recommendations exclude kept sofa; changed constraints invalidate shopping selection |
| Neo4j relationships affect recommendations | Passed, real Neo4j | Same $150 budget/kept sofa: `natural` returns LOHALS rug ($129.99); `minimal` returns LACK table + RANARP lamp ($89.98). Both report `connected`; an independent Bolt query retrieved the actual Room–Style–Product path |
| Cents-based shopping total | Passed | Sum of source snapshot prices equals saved total and fits budget |
| Export requires exact approval | Passed locally | Missing approval returns 403; changed room returns 409; approval for a different room returns 404 |
| Concurrent/retried save avoids duplicate creation | Passed in mocked contract tests | Three simultaneous approved requests produce one mocked POST and one GET; returned identifier is persisted before readback; uncertain create outcomes block blind retry |
| Upload starts real Orbis video | Passed, actual provider | Authorized Reactor session produced 2560 × 1440 decoded WebRTC frames from the uploaded room. See [live capture](live-capture.json), the MP4 and screenshots |
| Two subsequent live directions visibly steer video | Passed, actual visible changes | Deep olive wall followed by cobalt rug and amber lighting; both real SDK prompt acknowledgments, independently viewed screenshots and advancing decoded frames |
| Real Ambiguous read/write and retrievable link | Passed, actual approved write and read-back | Exact approved $219.97 brief saved as one document with shopping table; title and authored text verified. [Document](https://app.ambiguous.ai/docs/4adbc629-1359-4b19-bb75-74e9f38d26a3), [save evidence](approved-save.json), [recovery record](ambiguous-save-recovery.json) |
| Desktop/mobile UI | Passed, real browser at 1280×900 and 391×844 | Actual upload; budget400; kept lamp/sofa excluded; real graph returns rug/table159.98; review opens after retrieval and reload; missing-key errors are honest; no horizontal overflow or uncaught browser errors; mobile review reachable |
| Production SDK runtime delivery | Passed without provider access | Production build passed; preview5191 serves SDK JavaScript200 with `text/javascript`, WASM200 with `application/wasm` (651458 bytes). Browser module initialization succeeded and exports `ReactorClient`; zero provider calls |
| Qoder implementation/testing contribution | Passed, actual authenticated CLI task | [Qoder evidence](qoder.md): new file, sanitized successful transcript, five independently passing tests |
| PDF/video/publication artifacts | Passed, final artifact checks | Five-page PDF; exact 120-second H.264 / yuv420p MP4, full decode; source and Markdown-link checks in [artifact verification](artifact-verification.json) and [publication audit](publication-audit.md) |

With the backend, frontend, and Neo4j started, install browser-check dependencies from the repository root:

```sh
npm ci --prefix tooling
```

Both browser scripts use Google Chrome at its default macOS application path, or an executable selected with `export CHROME_PATH="/absolute/path/to/chrome"`. If neither is available, install Playwright Chromium:

```sh
node tooling/node_modules/playwright/cli.js install chromium
```

Then run:

```sh
.venv/bin/python -m pytest backend -q
node scripts/smoke-browser.cjs
cd frontend && npm run build && cd ..
node scripts/verify-sdk-runtime.cjs
```

The backend suite currently passes **52 tests**, including five authored by authenticated Qoder CLI 1.1.51. The browser smoke uses actual HTTP/application behavior and creates a local test room. It never clicks external approval; an explicit network route also blocks external-export API calls. If keys are configured, missing-credential tests are skipped rather than starting a paid session. It requires Neo4j connectivity.

Detailed local graph/HTTP results: [http-verification.json](http-verification.json). Browser results: [browser-verification.json](browser-verification.json), with desktop, mobile and approval-review screenshots. Production SDK initialization: [wasm-verification.json](wasm-verification.json). These checks demonstrate local SDK readiness, not live provider acceptance or generated video.

All four catalog prices and dimensions were independently checked against primary IKEA US product pages on September 12, 2026: [LOHALS $129.99, 63 × 91 × 0.5 inches](https://www.ikea.com/us/en/p/lohals-rug-flatwoven-natural-50277393/), [RANARP $59.99, 17-inch height, 7-inch shade, 59-inch cord](https://www.ikea.com/us/en/p/ranarp-work-lamp-off-white-50231319/), [LACK $29.99, 35⅜ × 21⅝ × 17¾ inches](https://www.ikea.com/us/en/p/lack-coffee-table-white-90449905/), and [GLOSTAD $169, 47⅝-inch width, 30¾-inch depth, 26¾-inch backrest](https://www.ikea.com/us/en/p/glostad-loveseat-knisa-dark-gray-70489011/). These are sourced snapshots, not live stock, checkout totals, or measured placement guarantees.

## Final live-media evidence

The final two-minute recording captures the same existing authorized Orbis session, with no second stream or synthetic video frames. Decoded frames advanced from 4,022 to 6,166 while 1,175 actual browser screen frames were recorded over two minutes. The two final directives retained the $900 budget and existing-sofa / windows-and-layout constraints in application state and model prompts. All reviewers observed the requested olive wall and cobalt rug.

**Visual limitation:** Orbis changes room geometry, furniture details and camera position despite preservation requests. The preview cannot establish exact furniture placement or SKU fidelity. Product references and dimensions remain the basis for purchase decisions. The separately labeled recovery recording shows the earlier missing-credential UI and is not live-provider evidence.

## Approved Ambiguous handoff

The participant approved the exact $219.97 brief. The first provider request returned an error without an identifier. Complete document and document-activity reads both showed an empty workspace before the same reviewed approval was retried once with the documented `restricted` visibility. The saved document was then read back: its title, all accepted directions, budget, product names, prices, dimensions and source URLs matched the approved brief. A separate independent retrieval confirmed exactly one matching document in the workspace. See [save evidence](approved-save.json) and [recovery evidence](ambiguous-save-recovery.json).

The final MP4 retains the first 100 seconds of the actual Orbis recording and appends 20 seconds of the later actual save in the same room. The document link requires workspace access; public API credentials and private workspace-claim links are excluded from publication.

## Fullscreen, Amazon discovery and voice follow-up

The completed follow-up adds fullscreen direction entry, frame hold with actual Orbis pause/resume acknowledgments, Amazon discovery through Exa and OpenAI speech transcription. Real provider calls and browser controls were verified separately; see the [feature verification record](voice-and-player.md). The two-minute demo remains the historical sprint demonstration. The deck was revised to the participant’s five-slide sequence with the deployed Render QR code. The new screenshots show the added controls and real Amazon results.

## Frame shopping and saved video

Click-to-search and automatic browser recording extend the existing journey. See [recording and frame-shopping verification](video-shopping.md) for source identification, Amazon matches, seekable downloads, reload recovery and their limits.

## Search latency and hosting preparation

[Measured search caching](search-latency-live.json) reduced the repeated identical frame request from 14,829 ms to 45 ms in one actual OpenAI/Exa test. This is a warm-cache measurement, not a guarantee for new searches. The first request still waited for provider extraction. Search now requests four results, allows six-hour page reuse and caches successful results for fifteen minutes; frame descriptions have a ten-minute cache. Cache isolation, expiry, cancellation, concurrency and attribute ranking have dedicated tests. Hosted packaging and its private access gate are documented in the [Render guide](../deploy-render.md).

## Hosted Render deployment and revised deck

[The hosted studio](https://showroom-q4s4.onrender.com) is live with a password gate and private persistent Neo4j. [Hosted HTTP checks](render-http-verification.json) verify graph-based recommendations, Ambiguous reads, actual OpenAI/Exa visual search and a repeat request using both caches (198 ms end-to-end, 16.5 s cold). [Browser checks](render-browser-verification.json) verify desktop/mobile with no page errors or horizontal overflow. The hosted Orbis attempt returned an honest 429 capacity error for the account’s occupied single-session quota; no hosted frames are claimed. No new external documents were written.

The deck now follows the requested sequence: hero + SHOWROOM only; problem / why; demo-video placeholder; Ambiguous / OpenAI / Exa / Neo4j / Qoder / VISKO architecture; deployed Render QR code. Qoder’s contribution is explicitly development/testing. The QR was decoded from the rendered final slide to verify its destination. The PDF has exactly five pages; the existing two-minute MP4 remains the historical demo.

## Automatic document sharing

The 52-test backend suite includes six sharing cases: recipient binding and approval, concurrent saves, uncertain invitation recovery, rejected-request retry, content-verification gating, and sharing readback recovery. [Browser verification](sharing-browser.json) uses intercepted API responses to prove recipient disclosure, failure/retry, pending/confirmed states and mobile layout. [Actual permission readback](sharing-provider-readback.json) validates the helper against the three previously authorized invitations without creating documents or sending more invitations.

## Public studio access

The participant subsequently requested removal of the Render sign-in requirement. The live web service now runs without `SHOWROOM_ACCESS_PASSWORD` or `SHOWROOM_REQUIRE_AUTH`. Earlier 401/authentication receipts describe the prior protected configuration. New public-access verification is recorded in [the public access receipt](render-public-access.json). The deck’s QR slide and current READMEs no longer request sign-in. New deployments can still opt into the existing password gate.
