# Deploy SHOWROOM on Render

**Deployed:** [SHOWROOM studio](https://showroom-q4s4.onrender.com). Username: `showroom`. For this API deployment, the password is the private `RENDER_STUDIO_PASSWORD` value in the local ignored `.env` (also `SHOWROOM_ACCESS_PASSWORD` in the Render web service environment). Never place the password in the deck, QR code or repository.

Both services are live. Hosted desktop/mobile, private Neo4j recommendations, Ambiguous reads, OpenAI item identification and Exa Amazon results passed. A repeated visual search measured 198 ms end-to-end versus 16.5 seconds cold. The hosted Orbis attempt reached Reactor but was rejected with HTTP 429 because the account already had its one allowed concurrent session; hosted frames were not verified. The UI displayed the capacity error. Earlier actual local Orbis streaming remains separately verified. See [HTTP evidence](evidence/render-http-verification.json) and [browser evidence](evidence/render-browser-verification.json).

The production Docker image serves the React frontend, Python API and Reactor WASM runtime on one HTTPS origin. `PORT` controls the listening port. SQLite state and uploads use `/var/data/showroom`; a private Neo4j service uses its own `/data` disk. The hosted studio requires HTTP Basic sign-in (username `showroom`) because it can use paid APIs and read the connected Ambiguous workspace.

The reviewed [Render Blueprint](../render.yaml) creates:

| Service | Plan | Persistent disk | Base monthly cost |
| --- | --- | --- | --- |
| SHOWROOM web/API | 0.5 CPU, 512 MB | 1 GB | $7 + $0.25 |
| Private Neo4j | 1 CPU, 2 GB | 1 GB | $25 + $0.25 |

About **$32.50/month**, excluding provider API usage, excess bandwidth/build usage, tax, and any existing workspace subscription. Rates were checked September 12, 2026 against [Render pricing](https://render.com/pricing). Disks require paid services; free ephemeral hosting would lose room and graph data on restarts. See [persistent disk behavior](https://render.com/docs/disks).

For Dashboard deployment, create a Blueprint from the [SHOWROOM starter fork](https://github.com/KaushikSiva/orbis-hackathon-starter) and enter the four provider keys when prompted. Render generates private passwords and connects the graph hostname/password between services. Obtain the generated studio password from the web service's private environment settings.

For the authorized API deployment, put `RENDER_API_KEY` in the ignored local `.env`, then run:

```sh
.venv/bin/python scripts/deploy-render.py --deploy
```

The helper creates the two services only after checking access and required provider keys. It generates separate `RENDER_NEO4J_PASSWORD` and `RENDER_STUDIO_PASSWORD` values in local `.env`, leaving the local Neo4j password unchanged. The Render control key and Qoder token are never sent to the running service. The helper preserves service/deploy IDs in ignored runtime storage and refuses to overwrite an unrelated existing service. If multiple workspaces are available, set `RENDER_OWNER_ID` explicitly.

After Render finishes building, verify public health, authenticated frontend and WASM delivery, anonymous access rejection, Neo4j recommendations and repeat-search cache behavior. Repository publication alone does not prove a completed deployment. Clips saved on localhost stay on that browser origin; the Render site maintains its own browser clip storage. No previous local room uploads or workspace data are automatically copied to Render.

Local production verification:

```sh
docker build -t showroom-render:local .
docker build -t showroom-neo4j-render:local -f deploy/neo4j/Dockerfile .
.venv/bin/python scripts/verify-render-local.py
```

The check uses isolated containers, a private Docker network and temporary data. It supplies no provider keys and verifies sign-in, graph connectivity, static runtime delivery and room persistence across a restart.

Set `SHOWROOM_SHARE_EMAIL` in the Render web service environment to automatically share new approved documents with that recipient. The deployment helper includes this optional value from local `.env` when creating a service. The review screen discloses the recipient before approval. Keep the address out of public configuration files; `.env.example` intentionally leaves it blank. Sharing gives document viewer access and does not add workspace members.
