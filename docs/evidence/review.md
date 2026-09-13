# Independent implementation review

Reviewed backend persistence, image handling, recommendation query, provider boundaries, exact export approval, frontend state/stream handling, source catalog, and browser behavior on September 12, 2026. Scope is the local single-user prototype. This is the initial local review; later actual Orbis, Qoder and Ambiguous evidence is consolidated in [verification.md](verification.md).

Material issues found and addressed:

- **Saving after furniture retrieval cleared the shopping list.** Frontend `ensureRoom` sent an unconditional PATCH and the backend invalidated products even for identical fields. Frontend now compares actual brief values; backend now returns the existing room unchanged on a no-op patch. A regression test verifies recommendations remain reviewable. Initial browser execution also confirmed review opens after retrieval and after reload.
- **Mobile save/workspace icon buttons lost their accessible names.** The responsive layout hides their text. Explicit `aria-label` values were added. Final mobile regression is included in `scripts/smoke-browser.cjs`.
- **Stream startup/stop races and premature live status.** Frontend owner added session-epoch guards and waits for a decoded video frame before claiming LIVE. Actual provider/frame behavior still requires Reactor access; code inspection alone is not live evidence.
- **SDK dynamic WASM asset resolution.** Frontend owner corrected the SDK's dynamically loaded browser runtime path. Independent production preview verification passed: JavaScript and WASM both HTTP200 with correct MIME types; the 651458-byte WASM initialized in Chrome and exports `ReactorClient`. This establishes local runtime readiness without claiming provider access.

Positive checks:

- Credentials are server-side and health only exposes configuration/status. Provider error responses are normalized; tests confirm rejected credentials are absent from responses. Browser only receives a scoped short-lived session JWT when configured.
- The backend binds loopback, CORS is limited to the two local frontend origins, and Neo4j ports bind loopback. Runtime data, uploads, credentials, virtual environments and dependency trees are ignored by git.
- Decoded upload format, size and pixel bounds are checked before saving a normalized image. Database queries bind parameters.
- Neo4j recommendation status is set from successful query execution, not merely a connectivity check. Failed graph queries produce an explicit fallback label. An actual Neo4j relationship query and changed recommendation are recorded in `http-verification.json`.
- Export approval is tied to the reviewed snapshot and room. Concurrent identical approvals are serialized. Returned document IDs are saved before verification, and a failed readback retries retrieval rather than POST. An unknown POST outcome prevents automatic duplicate writes. Three concurrent mock requests were tested together.
- Export verification compares title, identifier and all authored text parts after content normalization. A mismatching document is explicitly unverified. This is stronger than treating any successful POST as a verified save.
- Four catalog prices and dimensions match primary retailer sources; editorial style tags and illustrative video are distinguished from purchasing evidence.

Known limits affecting acceptance:

- Credentials were absent during the initial local smoke verification. Later actual Orbis frames and two visible changes, plus Qoder-generated tests and the subsequently approved Ambiguous save with verified read-back, are recorded in the consolidated verification report. No fixture or static reference photograph is presented as generated output.
- The SDK acknowledgement log is browser-reported, not cryptographic provider attestation. Local synthetic acknowledgement tests are contract tests only.
- The recommendation catalog contains four curated products and category-level keep exclusion. It is not an inventory search engine or geometric fit solver.
- Export serialization is in-process and the application is explicitly one local user/one backend process. Multi-worker deployment would require cross-process write coordination and authentication.
- Installation alone would not establish Qoder usage. The later authenticated task produced five independently passing tests; see its dedicated evidence file.

No unrelated refactor or cosmetic rewrite was made by the reviewer. Added `backend/test_verification.py` and a reproducible browser smoke; changed backend no-op PATCH behavior in coordination with the implementation owner.
