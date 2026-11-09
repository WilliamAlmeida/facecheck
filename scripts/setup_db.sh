#!/usr/bin/env bash
# Cria o banco "facecheck" (com a extensão pgvector) num container Postgres já existente
# e gera o .env a partir do .env.example usando a senha do container.
#
# Uso:  PG_CONTAINER=nome_do_container bash scripts/setup_db.sh
#       (padrão: PG_CONTAINER=postgres; o container precisa ter a imagem pgvector/pgvector)
set -euo pipefail
cd "$(dirname "$0")/.."

PG="${PG_CONTAINER:-postgres}"
PW="$(docker exec "$PG" printenv POSTGRES_PASSWORD)"
if ! docker exec "$PG" psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='facecheck'" | grep -q 1; then
  docker exec "$PG" psql -U postgres -c "CREATE DATABASE facecheck"
  echo "banco facecheck criado"
else
  echo "banco facecheck já existe"
fi
docker exec "$PG" psql -U postgres -d facecheck -c "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null
echo "extensão vector ok"

if [ ! -f .env ]; then
  sed "s|TROQUE_AQUI|${PW}|" .env.example > .env
  echo ".env gerado (confira DATABASE_URL e DOCKER_NETWORK)"
else
  echo ".env já existe (não alterado)"
fi
