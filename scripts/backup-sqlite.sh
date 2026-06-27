#!/usr/bin/env bash
set -euo pipefail

DB_PATH=${AUDIT_DB_PATH:-/var/lib/shenjikanban/audit-kanban.sqlite3}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/shenjikanban}
UPLOAD_ROOT=${UPLOAD_ROOT:-/data/jiqing-engineering/uploads}
INCLUDE_UPLOADS=${INCLUDE_UPLOADS:-1}
STAMP=$(date +%Y%m%d%H%M%S)
DB_NAME=$(basename "$DB_PATH")
DB_BACKUP_PATH="${BACKUP_DIR}/${DB_NAME%.sqlite3}.${STAMP}.sqlite3"
UPLOAD_BACKUP_PATH="${BACKUP_DIR}/uploads.${STAMP}.tar.gz"
MANIFEST_PATH="${BACKUP_DIR}/backup-manifest.${STAMP}.json"

safe_dir() {
  local path="$1"
  if [ -z "$path" ] || [ "$path" = "/" ]; then
    printf '[backup] ERROR: unsafe directory path: %s\n' "$path" >&2
    exit 1
  fi
}

file_sha256() {
  local path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  else
    python3 - "$path" <<'PY'
import hashlib
import sys
path = sys.argv[1]
h = hashlib.sha256()
with open(path, "rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        h.update(chunk)
print(h.hexdigest())
PY
  fi
}

printf '[backup] 江苏集庆·工程管理系统 backup started\n'
printf '[backup] Source SQLite database: %s\n' "$DB_PATH"
printf '[backup] Backup directory: %s\n' "$BACKUP_DIR"
printf '[backup] Upload root: %s\n' "$UPLOAD_ROOT"

if [ ! -f "$DB_PATH" ]; then
  printf '[backup] ERROR: database file not found: %s\n' "$DB_PATH" >&2
  exit 1
fi

safe_dir "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if command -v sqlite3 >/dev/null 2>&1; then
  printf '[backup] Creating online SQLite backup with sqlite3 .backup\n'
  sqlite3 "$DB_PATH" ".backup '${DB_BACKUP_PATH}'"
  printf '[backup] Running SQLite integrity check\n'
  CHECK_RESULT=$(sqlite3 "$DB_BACKUP_PATH" 'PRAGMA quick_check;')
  if [ "$CHECK_RESULT" != "ok" ]; then
    printf '[backup] ERROR: SQLite quick_check failed: %s\n' "$CHECK_RESULT" >&2
    exit 1
  fi
else
  printf '[backup] sqlite3 not found, falling back to file copy\n'
  cp -a "$DB_PATH" "$DB_BACKUP_PATH"
  CHECK_RESULT="sqlite3 unavailable; copied file only"
fi

chmod 600 "$DB_BACKUP_PATH"
DB_SIZE=$(wc -c <"$DB_BACKUP_PATH" | tr -d ' ')
DB_SHA256=$(file_sha256 "$DB_BACKUP_PATH")
printf '[backup] SQLite backup complete: %s\n' "$DB_BACKUP_PATH"

UPLOAD_INCLUDED=false
UPLOAD_SIZE=0
UPLOAD_SHA256=""
if [ "$INCLUDE_UPLOADS" = "1" ] && [ -d "$UPLOAD_ROOT" ]; then
  safe_dir "$UPLOAD_ROOT"
  printf '[backup] Creating attachment archive: %s\n' "$UPLOAD_BACKUP_PATH"
  tar -C "$(dirname "$UPLOAD_ROOT")" -czf "$UPLOAD_BACKUP_PATH" "$(basename "$UPLOAD_ROOT")"
  chmod 600 "$UPLOAD_BACKUP_PATH"
  UPLOAD_INCLUDED=true
  UPLOAD_SIZE=$(wc -c <"$UPLOAD_BACKUP_PATH" | tr -d ' ')
  UPLOAD_SHA256=$(file_sha256 "$UPLOAD_BACKUP_PATH")
  printf '[backup] Attachment backup complete: %s\n' "$UPLOAD_BACKUP_PATH"
elif [ "$INCLUDE_UPLOADS" = "1" ]; then
  printf '[backup] Attachment directory not found, skipped: %s\n' "$UPLOAD_ROOT"
else
  printf '[backup] Attachment backup disabled by INCLUDE_UPLOADS=%s\n' "$INCLUDE_UPLOADS"
fi

python3 - "$MANIFEST_PATH" <<PY
import json
import os
import sys
manifest_path = sys.argv[1]
uploads_included = "${UPLOAD_INCLUDED}" == "true"
manifest = {
    "generatedAt": "${STAMP}",
    "system": "江苏集庆·工程管理系统",
    "database": {
        "source": "${DB_PATH}",
        "backupPath": "${DB_BACKUP_PATH}",
        "bytes": int("${DB_SIZE}"),
        "sha256": "${DB_SHA256}",
        "quickCheck": "${CHECK_RESULT}",
    },
    "attachments": {
        "source": "${UPLOAD_ROOT}",
        "included": uploads_included,
        "backupPath": "${UPLOAD_BACKUP_PATH}" if uploads_included else "",
        "bytes": int("${UPLOAD_SIZE}"),
        "sha256": "${UPLOAD_SHA256}",
    },
    "restoreHint": "Use scripts/restore-sqlite.sh with CONFIRM_RESTORE=yes after stopping the service.",
}
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
os.chmod(manifest_path, 0o600)
PY

printf '[backup] Manifest written: %s\n' "$MANIFEST_PATH"
printf '[backup] Backup finished successfully\n'
