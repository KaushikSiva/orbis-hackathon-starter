# Three presentations of SHOWROOM

All three packages contain the same canonical SHOWROOM frontend and backend. Their source SHA-256 and repository metadata are recorded in each generated `publication.json`.

| Presentation | Editable README | Repository metadata |
|---|---|---|
| Live video | [Live rooms](readme-variants/live-video.md) | [Description and topics](readme-variants/live-video.json) |
| Ambiguous coworker | [Design coworker](readme-variants/ambiguous-coworker.md) | [Description and topics](readme-variants/ambiguous-coworker.json) |
| Qoder / Neo4j | [Connected memory](readme-variants/qoder-neo4j.md) | [Description and topics](readme-variants/qoder-neo4j.json) |

Run `python3 scripts/build-publication.py` from the canonical repository to produce clean standalone directories and zip files under `publication/`. Each includes code, startup instructions, screenshots, architecture, the deck and two-minute video. The script verifies image paths and scans for configured service credentials before packaging.

The literal local Docker development password `showroom-local-dev` is an intentional public default. Its ports bind to 127.0.0.1. It is the only credential-value exception in the publication scan; configured Reactor, Ambiguous, Qoder, Exa, OpenAI or custom database secrets are never exempt.

Cross-event eligibility was confirmed by the participant on September 12, 2026. See the [confirmation and sources](evidence/event-eligibility.md). The participant approved these three public GitHub destinations, and all three repositories were published on September 12, 2026. Remote `main` references were verified after successful pushes; see the [publication evidence](evidence/github-publication.json). Nothing in these presentation variants implies three independent builds, award wins or hosted application deployment.

| Presentation | Published public repository |
|---|---|
| Canonical live video | [KaushikSiva/showroom](https://github.com/KaushikSiva/showroom) |
| Ambiguous coworker | [KaushikSiva/showroom-coworker](https://github.com/KaushikSiva/showroom-coworker) |
| Qoder / Neo4j | [KaushikSiva/showroom-graph](https://github.com/KaushikSiva/showroom-graph) |

The canonical local monorepo remains the development source. Separate Git checkouts publish its presentation packages; their README is the appropriate variant and `QUICKSTART.md` is the canonical README. Generated Reactor WASM assets and TypeScript build metadata are excluded from packages and source manifests, matching Git ignores. Vite regenerates the runtime from the locked SDK installation. No event or social submission is authorized by repository publication. The participant separately approved the exact Ambiguous brief; its saved document and verified read-back are recorded in [save evidence](evidence/approved-save.json).
