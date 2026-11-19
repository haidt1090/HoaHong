#!/bin/bash
# Production deploy script — run on the server from the repo root.
set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"

echo "==> Pulling latest code"
git pull origin main

echo "==> Building production images (backend + frontend)"
$COMPOSE build

echo "==> Starting stack"
$COMPOSE up -d

echo "==> Running migrations"
$COMPOSE exec -T web python src/manage.py migrate --noinput

echo "==> Seeding report templates (idempotent)"
$COMPOSE exec -T web python src/manage.py seed_report_templates

echo "==> Collecting Django static"
$COMPOSE exec -T web python src/manage.py collectstatic --noinput

echo "==> Cleaning up dangling images"
docker image prune -f

echo "==> Done. Stack status:"
$COMPOSE ps