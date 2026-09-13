# Qoder engineering evidence

Status: **actual Qoder implementation completed and independently verified**. Authenticated Qoder CLI **1.1.51** created `backend/test_qoder_journey.py` and exited successfully. Its five new tests pass; the complete backend suite now passes 52 tests (18 at the original Qoder verification).

Create a Personal Access Token at [Qoder account integrations](https://qoder.com/account/integrations), then place it in the ignored root `.env` as `QODER_PERSONAL_ACCESS_TOKEN`. Do not paste the value into an issue, README, recording, or terminal transcript.

Official references checked September 12, 2026:

- [Installation](https://docs.qoder.com/cli/installation): npm package `@qoder-ai/qodercli`, Node 20 or newer.
- [Authentication](https://docs.qoder.com/cli/authentication): `QODER_PERSONAL_ACCESS_TOKEN` for headless execution.
- [Run in scripts](https://docs.qoder.com/cli/run-in-scripts): `--print`, `--max-turns`, and scoped tool permissions.

Completed bounded task: inspect the implemented SHOWROOM API and write an executable integration test that verifies budget / keep-constraint persistence across two design instructions. The exact task is in [qoder-task.txt](qoder-task.txt). Run `python3 scripts/run-qoder-task.py` after configuring the token. It restricts external tools, keeps the token out of command arguments and preserves a sanitized transcript. Independently execute and review the produced `backend/test_qoder_journey.py` before updating this usage claim. Credentials and room uploads must be excluded.

## Inspect the contribution

- [Exact task prompt](qoder-task.txt)
- [Sanitized CLI result transcript](qoder-transcript.txt): successful exit, eight turns; credentials and the local absolute workspace path removed.
- [Produced file](../../backend/test_qoder_journey.py) and [reviewed new-file diff](qoder-test.diff)
- [Independent execution result and file digest](qoder-result.json)

The five tests cover two successive directions with persistent budget and keep constraints, catalog-referenced prices and export totals, rejection before unapproved provider calls, missing-integration retry behavior, and temporary SQLite isolation. They reuse the existing local fixture, which prevents external service calls. These are contract tests; live Orbis and Neo4j verification is recorded separately. No application source was edited by Qoder.

The tooling pins a `sharp` 0.35.4 override for the Qoder CLI dependency after npm reported vulnerabilities in the older bundled image dependency. `npm audit --prefix tooling` reports zero vulnerabilities and the CLI completed this task with the override.
