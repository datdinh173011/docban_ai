#!/usr/bin/env bash
set -euo pipefail

PROJECT_PATH="${PROJECT_PATH:?PROJECT_PATH is required}"

deploy_frontend() {
  cd "$PROJECT_PATH/fe"
  npm ci
  npm run build
  install -d -m 0755 /var/www/icivi.online
  cp -a dist/. /var/www/icivi.online/
}

deploy_backend() {
  cd "$PROJECT_PATH/be"
  docker compose up -d --build
  docker compose exec -T backend sh -c '
    test -f /app/data/dichvucong_xaydung/procedures.json
    test "$(find /app/data/dichvucong_xaydung/pdf_thu_tuc -type f -name "*.pdf" | wc -l)" -eq 207
  '
  docker compose exec -T backend alembic upgrade head
  docker compose exec -T postgres sh -c \
    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    < data/seeds/legal_knowledge_20260718.sql
  docker compose exec -T postgres sh -c \
    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"' -- "
      SELECT count(*) AS procedures FROM administrative_procedure;
      SELECT count(*) AS packages FROM knowledge_package;
      SELECT count(*) AS documents FROM knowledge_document;
      SELECT count(*) AS chunks FROM knowledge_chunk;
      SELECT count(*) AS facts FROM procedure_fact;
    "
}

cd "$PROJECT_PATH"
git pull --ff-only origin main
deploy_frontend
deploy_backend
