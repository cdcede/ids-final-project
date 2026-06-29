#!/usr/bin/env bash
# First-boot bootstrap for the demo Superset instance:
# migrate the metadata DB, create the admin user, init roles, then serve.
set -e

superset db upgrade

# Idempotent: ignore "already exists" on restarts.
superset fab create-admin \
  --username admin --firstname Admin --lastname User \
  --email admin@superset.local --password admin || true

superset init

exec gunicorn --bind 0.0.0.0:8088 --workers 1 --timeout 120 \
  "superset.app:create_app()"
