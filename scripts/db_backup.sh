#!/usr/bin/env bash
# PostgreSQL logical backup of the local stack's database.
# See docs/RUNBOOK_BACKUP_RESTORE.md for the full procedure and RPO/RTO notes.
#
# Produces a timestamped custom-format dump under backups/, which
# db_restore.sh consumes. Runs pg_dump INSIDE the postgres container so no
# local PostgreSQL client is required.
set -euo pipefail

POSTGRES_USER="${POSTGRES_USER:-cbir}"
POSTGRES_DB="${POSTGRES_DB:-cbir}"
SERVICE="${POSTGRES_SERVICE:-postgres}"

mkdir -p backups
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="backups/${POSTGRES_DB}-${STAMP}.dump"

echo "Backing up database '${POSTGRES_DB}' -> ${OUT}"
docker compose exec -T "${SERVICE}" \
    pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc > "${OUT}"

echo "Backup complete: ${OUT} ($(wc -c < "${OUT}") bytes)"
