# PostgreSQL Migration Preparation

Date: 2026-06-27

The current production system still runs on SQLite. PostgreSQL is the recommended next database once concurrent editing, attachment activity, or multi-user audit workflows grow beyond a light internal workload.

## Current SQLite Source

- Local default: `server/audit-kanban.sqlite3`
- Production: `/var/lib/shenjikanban/audit-kanban.sqlite3`
- Configured by: `AUDIT_DB_PATH`
- Deployment backup directory: `/var/backups/shenjikanban`

## Prepared PostgreSQL Schema

The baseline PostgreSQL DDL lives at:

`server/postgres_schema.sql`

It covers:

- Audit projects, stages, logs, field configs, option library, custom field values.
- Users, settings, operation logs, theme whitelist.
- Planned attachment metadata fields, including original file name, stored name, relative path, uploader, deleted flag, and timestamps.

## Future Environment Variables

The application should move to a `DATABASE_URL` model before switching the running service:

```text
DATABASE_URL=postgresql://jiqing_app:<password>@127.0.0.1:5432/jiqing_engineering
AUDIT_DB_PATH=/var/lib/shenjikanban/audit-kanban.sqlite3
```

During migration, keep `AUDIT_DB_PATH` until the Python API has a PostgreSQL adapter. Do not hardcode database passwords in source code, deployment scripts, or systemd units.

## Recommended Migration Flow

1. Backup SQLite:

   ```bash
   AUDIT_DB_PATH=/var/lib/shenjikanban/audit-kanban.sqlite3 \
   BACKUP_DIR=/var/backups/shenjikanban \
   scripts/backup-sqlite.sh
   ```

2. Backup attachments if they exist:

   ```bash
   tar -C /data/jiqing-engineering -czf /var/backups/shenjikanban/uploads.$(date +%Y%m%d%H%M%S).tar.gz uploads
   ```

3. Create PostgreSQL database and app user.

4. Apply schema:

   ```bash
   psql "$DATABASE_URL" -f server/postgres_schema.sql
   ```

5. Export SQLite data to newline-delimited JSON or CSV with a one-table-at-a-time migration script.

6. Import in dependency order:

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

7. Run parity checks:

   - Row counts per table.
   - A few project detail payloads.
   - Login with an existing admin.
   - Theme current/options APIs.
   - Audit dashboard summary totals.

8. Switch API to PostgreSQL only after the backend database adapter has been implemented and tested.

## Notes

- SQLite stores booleans as integers. PostgreSQL schema uses `BOOLEAN`; migration scripts must convert `0/1` values.
- SQLite stores JSON as text. PostgreSQL schema uses `JSONB` for settings and log snapshots; migration scripts must validate JSON before insert.
- Attachment files remain on disk. PostgreSQL stores metadata only.
- Theme configs, operation logs, users, and attachment metadata are part of the migration scope and must be included in backups.

