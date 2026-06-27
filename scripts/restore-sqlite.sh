#!/usr/bin/env bash
set -euo pipefail

DB_PATH=${AUDIT_DB_PATH:-/var/lib/shenjikanban/audit-kanban.sqlite3}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/shenjikanban}
UPLOAD_ROOT=${UPLOAD_ROOT:-/data/jiqing-engineering/uploads}
SYSTEMD_SERVICE=${SYSTEMD_SERVICE:-audit-kanban}
RESTORE_DB_BACKUP=${RESTORE_DB_BACKUP:-}
RESTORE_UPLOAD_BACKUP=${RESTORE_UPLOAD_BACKUP:-}
CONFIRM_RESTORE=${CONFIRM_RESTORE:-}
STAMP=$(date +%Y%m%d%H%M%S)
PRE_RESTORE_DB="${BACKUP_DIR}/pre-restore.$(basename "${DB_PATH%.sqlite3}").${STAMP}.sqlite3"

safe_dir() {
  local path="$1"
  if [ -z "$path" ] || [ "$path" = "/" ]; then
    printf '[restore] ERROR: unsafe directory path: %s\n' "$path" >&2
    exit 1
  fi
}

if [ "$CONFIRM_RESTORE" != "yes" ]; then
  printf '[restore] ERROR: set CONFIRM_RESTORE=yes to restore data\n' >&2
  exit 1
fi

if [ -z "$RESTORE_DB_BACKUP" ] || [ ! -f "$RESTORE_DB_BACKUP" ]; then
  printf '[restore] ERROR: RESTORE_DB_BACKUP must point to an existing SQLite backup\n' >&2
  exit 1
fi

safe_dir "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR" "$(dirname "$DB_PATH")"
chmod 700 "$BACKUP_DIR"

printf '[restore] Restore started\n'
printf '[restore] Target database: %s\n' "$DB_PATH"
printf '[restore] SQLite backup: %s\n' "$RESTORE_DB_BACKUP"

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$SYSTEMD_SERVICE.service" >/dev/null 2>&1; then
  printf '[restore] Stopping service: %s\n' "$SYSTEMD_SERVICE"
  systemctl stop "$SYSTEMD_SERVICE"
fi

if [ -f "$DB_PATH" ]; then
  printf '[restore] Backing up current database before restore: %s\n' "$PRE_RESTORE_DB"
  cp -a "$DB_PATH" "$PRE_RESTORE_DB"
  chmod 600 "$PRE_RESTORE_DB"
fi

cp -a "$RESTORE_DB_BACKUP" "$DB_PATH"
chmod 600 "$DB_PATH"

if command -v sqlite3 >/dev/null 2>&1; then
  CHECK_RESULT=$(sqlite3 "$DB_PATH" 'PRAGMA quick_check;')
  if [ "$CHECK_RESULT" != "ok" ]; then
    printf '[restore] ERROR: restored SQLite quick_check failed: %s\n' "$CHECK_RESULT" >&2
    exit 1
  fi
  printf '[restore] SQLite quick_check: ok\n'
else
  printf '[restore] sqlite3 not found, skipped quick_check\n'
fi

if [ -n "$RESTORE_UPLOAD_BACKUP" ]; then
  if [ ! -f "$RESTORE_UPLOAD_BACKUP" ]; then
    printf '[restore] ERROR: RESTORE_UPLOAD_BACKUP not found: %s\n' "$RESTORE_UPLOAD_BACKUP" >&2
    exit 1
  fi
  safe_dir "$UPLOAD_ROOT"
  mkdir -p "$(dirname "$UPLOAD_ROOT")"
  printf '[restore] Restoring attachment archive into: %s\n' "$(dirname "$UPLOAD_ROOT")"
  if [ -d "$UPLOAD_ROOT" ]; then
    mv "$UPLOAD_ROOT" "${UPLOAD_ROOT}.pre-restore.${STAMP}"
  fi
  tar -C "$(dirname "$UPLOAD_ROOT")" -xzf "$RESTORE_UPLOAD_BACKUP"
  chmod 750 "$UPLOAD_ROOT" || true
fi

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$SYSTEMD_SERVICE.service" >/dev/null 2>&1; then
  printf '[restore] Starting service: %s\n' "$SYSTEMD_SERVICE"
  systemctl start "$SYSTEMD_SERVICE"
fi

printf '[restore] Restore finished successfully\n'
