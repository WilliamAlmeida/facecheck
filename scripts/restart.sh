#!/usr/bin/env bash
# Recria o container e espera ficar pronto. Funciona com "docker compose" (v2) ou "docker-compose" (v1);
# no v1, "up -d" não recria direto depois de mudar o .env (KeyError 'ContainerConfig'), por isso down + up.
# Uso: bash scripts/restart.sh [--test]
set -u
cd "$(dirname "$0")/.."
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi
PORT="$(grep -E '^APP_PORT=' .env 2>/dev/null | cut -d= -f2)"; PORT="${PORT:-8090}"

$DC down 2>&1 | tail -1
$DC up -d 2>&1 | tail -1
for _ in $(seq 1 60); do
  curl -sf "localhost:$PORT/api/health" >/dev/null && break
  sleep 1
done
curl -s "localhost:$PORT/api/health"; echo
if [ "${1:-}" = "--test" ]; then
  docker exec -i facecheck_api python - < scripts/liveness_test.py 2>&1 \
    | grep -v -E "Applied providers|find model|model ignore|set det-size"
fi
