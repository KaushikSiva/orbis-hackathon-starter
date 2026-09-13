#!/bin/bash
set -euo pipefail
: "${NEO4J_PASSWORD:?Set the private database password}"
export NEO4J_AUTH="neo4j/${NEO4J_PASSWORD}"
# The official entrypoint maps remaining NEO4J_* variables to settings.
unset NEO4J_PASSWORD
exec /startup/docker-entrypoint.sh "$@"
