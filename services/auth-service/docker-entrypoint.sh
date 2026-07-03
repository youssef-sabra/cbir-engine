#!/bin/sh
# Run migrations, then serve. `alembic upgrade head` is idempotent, so every
# container start converges the schema — sufficient for the local stack; a
# real cluster deployment runs migrations as a separate job before rollout.
set -e
alembic upgrade head
exec uvicorn auth_service.main:app --host 0.0.0.0 --port 8000
