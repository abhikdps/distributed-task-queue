#!/usr/bin/env bash
# Run Docker Compose or Podman Compose. Prefer Docker, then Podman.
set -e
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  exec docker compose -f "$COMPOSE_FILE" "$@"
elif command -v docker >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
  exec docker-compose -f "$COMPOSE_FILE" "$@"
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
  exec podman compose -f "$COMPOSE_FILE" "$@"
elif command -v podman-compose >/dev/null 2>&1; then
  exec podman-compose -f "$COMPOSE_FILE" "$@"
else
  echo "Need Docker Compose or Podman Compose. Install one of:" >&2
  echo "  - Docker Engine + Compose plugin (docker compose)" >&2
  echo "  - Podman + Compose plugin (podman compose) or podman-compose" >&2
  exit 1
fi
