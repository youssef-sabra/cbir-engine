#!/usr/bin/env bash
# Restore the local stack's PostgreSQL database from a db_backup.sh dump.
# See docs/RUNBOOK_BACKUP_RESTORE.md for the full procedure.
#
#   ./scripts/db_restore.sh backups/cbir-20260703-120000.dump
#
# Uses pg_restore --clean --if-exists so it is safe to run against an existing
# database: it drops and recreates each object from the dump. Runs inside the
# postgres container (no local client required).
set -euo pipefail

FILE="${1:-}"
if [ -z "${FILE}" ] || [ ! -f "${FILE}" ]; then
    echo "usage: $0 <path-to-.dump>" >&2
    exit 1
fi

POSTGRES_USER="${POSTGRES_USER:-cbir}"
POSTGRES_DB="${POSTGRES_DB:-cbir}"
SERVICE="${POSTGRES_SERVICE:-postgres}"

echo "Restoring '${FILE}' into database '${POSTGRES_DB}'..."
docker compose exec -T "${SERVICE}" \
    pg_restore -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --clean --if-exists --no-owner \
    < "${FILE}"

echo "Restore complete."
