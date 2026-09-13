# SHOWROOM import into the Orbis starter fork

SHOWROOM was developed independently, then imported into [this fork](https://github.com/KaushikSiva/orbis-hackathon-starter) of [Visko-Platform/orbis-hackathon-starter](https://github.com/Visko-Platform/orbis-hackathon-starter). This import does not imply that SHOWROOM originally began from the starter.

All 19 files from upstream commit `cbdc70c0ee286e8b7770575b14bb955655ce3139` are retained byte for byte under `starter/`. Git ancestry remains intact. The full SHOWROOM app and deliverables live at the root.

The 39 imported backend/frontend files match canonical SHOWROOM commit `8b11a8fb360b592998d3a1dfb23aae0f0678e097` and have SHA-256 `6363d8f53fc725dc6e2f56d88f0f0384d2fb4365d7e45f4b732dafea8e6f41a2`. The backend suite passes 52 tests in this checkout. A fresh `npm ci` and production frontend build pass. These checks do not create live provider sessions, documents or invitations.

The root README, publication metadata and deployment repository targets identify this fork. The existing Render deployment continues using the canonical repository; importing the source did not deploy or modify hosted services.
