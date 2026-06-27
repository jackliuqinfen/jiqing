# PostgreSQL Migration Preparation

Date: 2026-06-27

The production system currently runs on SQLite at `/var/lib/shenjikanban/audit-kanban.sqlite3`. PostgreSQL is the recommended next database once concurrent editing, attachment activity, or multi-user audit workflows grow beyond a light internal workload.

## Current SQLite Source

- Local default: `server/audit-kanban.sqlite3`
- Production: `/var/lib/shenjikanban/audit-kanban.sqlite3`
- Runtime variable: `AUDIT_DB_PATH`
- Deployment backup directory: `/var/backups/shenjikanban`
- Attachment root: `/data/jiqing-engineering/uploads`
- Attachment runtime variable: `UPLOAD_ROOT`

## Prepared PostgreSQL Schema

The baseline PostgreSQL DDL lives at:

`server/postgres_schema.sql`

It covers:

- Audit projects, stages, logs, field configs, option library, and custom field values.
- Users, settings, operation logs, and theme whitelist.
- Attachment metadata fields: original file name, stored name, extension, MIME type, byte size, relative path, uploader, deleted flag, and timestamps.

Attachment binaries remain on disk. PostgreSQL stores metadata only.

## Future Environment Variables

The backend should move to a `DATABASE_URL` model before switching the running service:

```text
DATABASE_URL=postgresql://jiqing_app:<password>@127.0.0.1:5432/jiqing_engineering
AUDIT_DB_PATH=/var/lib/shenjikanban/audit-kanban.sqlite3
UPLOAD_ROOT=/data/jiqing-engineering/uploads
MAX_UPLOAD_SIZE=26214400
```

During migration, keep `AUDIT_DB_PATH` until the Python API has a PostgreSQL adapter. Do not hardcode database passwords in source code, deployment scripts, or systemd units.

## Recommended Migration Flow

1. Freeze writes for a short maintenance window.

2. Backup SQLite and attachments:

   ```bash
   AUDIT_DB_PATH=/var/lib/shenjikanban/audit-kanban.sqlite3 \
   UPLOAD_ROOT=/data/jiqing-engineering/uploads \
   BACKUP_DIR=/var/backups/shenjikanban \
   INCLUDE_UPLOADS=1 \
   /opt/shenjikanban/scripts/backup-sqlite.sh
   ```

   Keep the generated `backup-manifest.<timestamp>.json` with the backup files.

3. Create PostgreSQL database and app user:

   ```bash
   sudo -u postgres psql <<'SQL'
   CREATE DATABASE jiqing_engineering;
   CREATE USER jiqing_app WITH PASSWORD '<replace-with-secret>';
   GRANT ALL PRIVILEGES ON DATABASE jiqing_engineering TO jiqing_app;
   SQL
   ```

4. Apply schema:

   ```bash
   psql "$DATABASE_URL" -f server/postgres_schema.sql
   ```

5. Export SQLite data one table at a time to JSON or CSV.

   Required table scope:

   - `system_users`
   - `system_settings`
   - `system_theme_configs`
   - `audit_projects`
   - `audit_project_stages`
   - `audit_project_logs`
   - `audit_project_attachments`
   - `audit_field_configs`
   - `audit_field_options`
   - `audit_project_field_values`
   - `audit_stage_field_values`
   - `system_operation_logs`

6. Convert SQLite values during import:

   - `0/1` integer flags to PostgreSQL `BOOLEAN`.
   - JSON text fields to `JSONB`: `before_json`, `after_json`, `detail_json`, `setting_value`, `preview_colors`.
   - Empty timestamp strings to `NULL` for nullable timestamp columns.
   - Attachment metadata only; copy no binary file into PostgreSQL.

7. Run parity checks before switching traffic:

   - Row counts per table.
   - Dashboard summary totals.
   - A few project detail payloads, including attachments.
   - Admin login.
   - Theme current/options APIs.
   - Operation log query.

8. Switch API to PostgreSQL only after the backend database adapter has been implemented and tested.

## Rollback Rule

Until the PostgreSQL adapter is proven in production, keep the SQLite database and `UPLOAD_ROOT` untouched. Roll back by restoring the pre-migration SQLite backup and attachment archive with:

```bash
CONFIRM_RESTORE=yes \
RESTORE_DB_BACKUP=/var/backups/shenjikanban/audit-kanban.<timestamp>.sqlite3 \
RESTORE_UPLOAD_BACKUP=/var/backups/shenjikanban/uploads.<timestamp>.tar.gz \
/opt/shenjikanban/scripts/restore-sqlite.sh
```

## Notes

- Theme configs, operation logs, users, and attachment metadata are part of the migration scope and must be included in backups.
- The current service does not yet read `DATABASE_URL`; that is a planned adapter change, not a current runtime switch.
- Keep backup directories outside Nginx roots and set permissions to `700` for directories and `600` for backup files.
