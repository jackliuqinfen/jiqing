#!/usr/bin/env bash
set -euo pipefail

DB_PATH=${AUDIT_DB_PATH:-/var/lib/shenjikanban/audit-kanban.sqlite3}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/shenjikanban}
UPLOAD_ROOT=${UPLOAD_ROOT:-/data/jiqing-engineering/uploads}
STAMP=$(date +%Y%m%d%H%M%S)
DB_NAME=$(basename "$DB_PATH")
BACKUP_PATH="${BACKUP_DIR}/${DB_NAME%.sqlite3}.${STAMP}.sqlite3"

printf '[backup] Starting SQLite backup\n'
printf '[backup] Source database: %s\n' "$DB_PATH"
printf '[backup] Backup directory: %s\n' "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
  printf '[backup] ERROR: database file not found: %s\n' "$DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB_PATH" ".backup '${BACKUP_PATH}'"
else
  cp -a "$DB_PATH" "$BACKUP_PATH"
fi

chmod 600 "$BACKUP_PATH"

printf '[backup] SQLite backup complete: %s\n' "$BACKUP_PATH"

if [ -d "$UPLOAD_ROOT" ]; then
  printf '[backup] Attachment directory found: %s\n' "$UPLOAD_ROOT"
  printf '[backup] Attachment files are not copied by this DB backup. Back them up with rsync/tar before major releases.\n'
else
  printf '[backup] Attachment directory not found yet: %s\n' "$UPLOAD_ROOT"
fi

