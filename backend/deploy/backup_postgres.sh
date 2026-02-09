#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/easya/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

TS="$(date -u +%Y-%m-%dT%H%M%SZ)"
OUT_TMP="$BACKUP_DIR/backup_${TS}.dump.tmp"
OUT="$BACKUP_DIR/backup_${TS}.dump"

# Requires: postgresql-client (pg_dump)
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file "$OUT_TMP" \
  "$DATABASE_URL"

mv "$OUT_TMP" "$OUT"

echo "[backup_postgres] wrote $OUT"

# Retention
find "$BACKUP_DIR" -type f -name 'backup_*.dump' -mtime "+$RETENTION_DAYS" -print -delete || true
