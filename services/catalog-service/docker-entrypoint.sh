#!/bin/sh
# Run migrations, then serve. See auth-service/docker-entrypoint.sh for the
# migration-on-start rationale.
set -e
alembic upgrade head
exec uvicorn catalog_service.main:app --host 0.0.0.0 --port 8000
