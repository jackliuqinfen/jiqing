# Backup, Restore, And Rollback Runbook

Date: 2026-06-27

This runbook covers the current Tencent Cloud deployment of 江苏集庆·工程管理系统.

## Production Paths

- Frontend root: `/www/wwwroot/shenjikanban`
- API root: `/opt/shenjikanban/server`
- Script root: `/opt/shenjikanban/scripts`
- SQLite database: `/var/lib/shenjikanban/audit-kanban.sqlite3`
- Backup directory: `/var/backups/shenjikanban`
- Attachment root: `/data/jiqing-engineering/uploads`
- systemd service: `audit-kanban.service`
- API port: `127.0.0.1:3008`
- Public Nginx port: `8088`

The attachment directory must not be served directly by Nginx. Attachment access must continue through authenticated backend APIs.

## Backup Before Releases

Run before every major deployment, database change, attachment storage change, or PostgreSQL migration rehearsal:

```bash
AUDIT_DB_PATH=/var/lib/shenjikanban/audit-kanban.sqlite3 \
UPLOAD_ROOT=/data/jiqing-engineering/uploads \
BACKUP_DIR=/var/backups/shenjikanban \
INCLUDE_UPLOADS=1 \
/opt/shenjikanban/scripts/backup-sqlite.sh
```

Expected output:

- Starts with `[backup] 江苏集庆·工程管理系统 backup started`.
- Writes a timestamped SQLite backup.
- Runs `PRAGMA quick_check` when `sqlite3` exists.
- Writes a timestamped attachment archive when `UPLOAD_ROOT` exists.
- Writes `backup-manifest.<timestamp>.json`.
- Ends with `[backup] Backup finished successfully`.

The backup directory is intentionally outside the public web root and should stay permissioned as `700`; backup files should stay `600`.

## Restore SQLite

Restore is intentionally guarded. It will not run unless `CONFIRM_RESTORE=yes` is set.

```bash
CONFIRM_RESTORE=yes \
AUDIT_DB_PATH=/var/lib/shenjikanban/audit-kanban.sqlite3 \
BACKUP_DIR=/var/backups/shenjikanban \
RESTORE_DB_BACKUP=/var/backups/shenjikanban/audit-kanban.<timestamp>.sqlite3 \
/opt/shenjikanban/scripts/restore-sqlite.sh
```

Restore behavior:

- Stops `audit-kanban.service` when systemd is available.
- Copies the current database to `pre-restore.<name>.<timestamp>.sqlite3`.
- Restores the selected SQLite backup.
- Runs `PRAGMA quick_check` when `sqlite3` exists.
- Starts the service again.

## Restore Attachments

Use only when the attachment archive belongs to the same backup set as the SQLite file.

```bash
CONFIRM_RESTORE=yes \
RESTORE_DB_BACKUP=/var/backups/shenjikanban/audit-kanban.<timestamp>.sqlite3 \
RESTORE_UPLOAD_BACKUP=/var/backups/shenjikanban/uploads.<timestamp>.tar.gz \
UPLOAD_ROOT=/data/jiqing-engineering/uploads \
/opt/shenjikanban/scripts/restore-sqlite.sh
```

The script moves the existing upload directory to `uploads.pre-restore.<timestamp>` before extracting the archive.

## Deployment Rollback

For frontend/API rollback after a failed release:

1. Identify the latest static backup directory:

   ```bash
   ls -dt /www/wwwroot/shenjikanban.bak.* | head -1
   ```

2. Restore frontend static files:

   ```bash
   rm -rf /www/wwwroot/shenjikanban
   cp -a /www/wwwroot/shenjikanban.bak.<timestamp> /www/wwwroot/shenjikanban
   systemctl reload nginx
   ```

3. Restore API code by redeploying the previous Git commit package, then restart:

   ```bash
   systemctl restart audit-kanban
   curl -fsS http://127.0.0.1:3008/api/health
   ```

4. Restore SQLite only if the release changed data or schema and a data rollback is required.

## Verification After Backup Or Restore

Run:

```bash
systemctl status audit-kanban --no-pager -l | sed -n '1,14p'
curl -fsS http://127.0.0.1:3008/api/health
curl -fsS http://127.0.0.1:8088/api/audit/dashboard/summary
```

Application-level smoke checks:

- Login works.
- 首页数据看板 loads.
- 审计看板 / 甘特图 / 表格视图 load.
- Project detail opens.
- Attachment list loads on project detail.
- Theme settings page reads the current whitelist.
- Operation logs page loads for admin.

## Backup Scope

The SQLite backup includes:

- Audit projects, stages, logs, field configs, field options, and custom field values.
- Users, roles, password hashes, settings, current theme, theme whitelist, and operation logs.
- Attachment metadata table.

The attachment archive includes file binaries under `UPLOAD_ROOT`.

## Remaining PostgreSQL Work

`server/postgres_schema.sql` and `docs/postgresql-migration-plan.md` are prepared. The running Python API still uses SQLite and needs a PostgreSQL adapter before `DATABASE_URL` can become the active database source.
