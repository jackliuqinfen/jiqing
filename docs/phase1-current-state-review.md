# Phase 1 Current State Review

Date: 2026-06-28

Target product: 江苏集庆·工程管理系统

This review is based on the current repository, production HTTP checks, production service configuration, and the latest production build.

## Executive Conclusion

The system is currently runnable as a database-backed internal engineering management application with audit management as the enabled business module. It has already moved beyond a static demo: login, SQLite persistence, audit project list/detail, kanban/gantt/table views, field configuration, option library, admin users, operation logs, Arco Design Vue runtime, VChart dashboard, attachment APIs, and a theme whitelist/current-theme API are present.

It is not yet the full "江苏集庆·工程管理系统" target. The product shell, login page, home dashboard, and attachment workflow have moved toward the engineering management system target. Remaining gaps include deeper module implementations beyond placeholders, fuller theme-management fields, a direct Arco component migration that removes the TDesign-compatible adapter layer, and continued production security hardening.

## Technology Stack

Frontend:

- Framework: Vue 3.5, Vue Router 4, Pinia 2.
- Build tool: Vite 6.
- UI library: Arco Design Vue is installed and used through `@arco-design/web-vue`.
- Theme package: `@arco-themes/vue-0000` is installed and globally imported.
- TDesign package: no TDesign dependency remains in `package.json`; however, source templates still use `t-*` component names through `src/ui/tdesignCompat.ts`.
- Chart libraries: VChart and `@visactor/vchart-arco-theme` are installed; ECharts/vue-echarts are not used.
- jQuery: installed and used by the scoped login background animation.
- Drag/drop: `sortablejs`.

Backend:

- Framework: Python standard library `ThreadingHTTPServer`, no Flask/FastAPI.
- Database: SQLite via Python `sqlite3`.
- Password hashing: PBKDF2-SHA256 with per-password salt.
- Token/session: HMAC-signed bearer token using `TOKEN_SECRET` or `SESSION_SECRET`.
- Local default DB path: `server/audit-kanban.sqlite3` unless `AUDIT_DB_PATH` is set.
- Production DB path: `/var/lib/shenjikanban/audit-kanban.sqlite3`.

Deployment:

- Static frontend root: `/www/wwwroot/shenjikanban`.
- API root: `/opt/shenjikanban/server`.
- API service: `audit-kanban.service`, bound to `127.0.0.1:3008`.
- Nginx public port: `8088`, proxying `/api/` to `127.0.0.1:3008`.
- Production URL checked: `http://121.4.36.112:8088/`.
- SQLite backups exist in `/var/backups/shenjikanban`.

## Current Functional Coverage

Implemented and verified from code:

- Login/logout and session restoration.
- Admin user management.
- Admin stats.
- Operation log table and read API.
- Audit project list, pagination, filters, create/update, detail, progress movement.
- Kanban, gantt, and table views.
- Field configuration and option library management.
- System settings for registration and login rules.
- Theme whitelist table `system_theme_configs`.
- Current theme setting in `system_settings`.
- Theme APIs:
  - `GET /api/system/theme/current`
  - `GET /api/system/theme/options`
  - `GET /api/system/theme/preview?themeKey=...`
  - `PUT /api/system/theme/current`
  - `POST /api/system/theme/reset`

Production checks performed:

- `GET /api/health` returned success.
- `GET /api/audit/dashboard/summary` returned 10 projects and valid summary totals.
- `GET /api/audit/dashboard/overview` returned structured dashboard data for the VChart home dashboard.
- `GET /api/system/theme/current` returned `arco-theme-0000`.
- `admin/admin` login on production returned `401`.
- Attachment upload/preview/download/reject/delete matrix passed on production after the 2026-06-28 deployment.
- Production service listens on public `8088` through Nginx and API `3008` only on localhost.

## Product Naming State

Already present:

- Backend default `system_name` is `江苏集庆·工程管理系统`.
- Browser title is `江苏集庆·工程管理系统`.
- Login page and app shell present the product as an engineering management system.
- Side navigation separates the enabled audit module from construction-state modules.

Still inconsistent:

- `package.json` name is still `cost-audit-kanban`.
- Several storage keys and legacy source comments still use cost-audit/audit-kanban naming.

## Arco And TDesign Migration State

Current state:

- Arco runtime is installed and production build works.
- `@arco-themes/vue-0000/css/arco.css` is globally imported.
- A compatibility layer maps existing `t-*` components to Arco components.
- Arco icons are imported on demand from `@arco-design/web-vue/es/icon`.
- No TDesign package dependency remains.

Remaining gap:

- Templates still use TDesign-style component names and props.
- The compatibility layer is still named `tdesignCompat`.
- Native inputs/selects remain in core audit views.
- Arco is not yet loaded through a true component/style on-demand strategy.
- The full Arco theme CSS is still bundled as `vendor-arco` CSS.

## Current Theme Capability

Implemented:

- Default theme: `@arco-themes/vue-0000`.
- Fallback theme: `@arco-design/web-vue`.
- Built-in whitelist themes:
  - `arco-theme-0000`
  - `arco-default`
  - `jiqing-blue`
  - `engineering-green`
  - `gov-gray-blue`
  - `dark-command`
- Theme selection persists in DB.
- Runtime CSS tokens are applied by `src/ui/theme.ts`.
- Admin theme selection exists in system settings.
- No arbitrary npm package input or runtime dynamic package loading exists.

Remaining gap:

- Theme settings page does not yet expose full theme management fields such as apply-scope editing, enable/default management, or chart theme preview.
- Dark and compact mode are token/dataset-level foundations, not a full density/dark styling pass.
- Chart theme following is implemented through `@visactor/vchart-arco-theme`, but should be visually regression-tested after each theme expansion.

## Dashboard And Chart State

Current state:

- Existing `GET /api/audit/dashboard/summary` returns summary counts and stage counts.
- `GET /api/audit/dashboard/overview` returns structured dashboard data for summary cards, status distribution, stage distribution, trend data, risk rows, amount rows, and card sparklines.
- The home route uses a "稳态指挥台" dashboard with VChart panels, responsive layout, date range controls, risk queue, module-state status, and theme-linked colors.
- VChart and `@visactor/vchart-arco-theme` are installed; ECharts/vue-echarts are not used.

Gap:

- Continue visual regression testing as themes expand.
- Keep chart code and dashboard route split from the main app chunk.
- The date range control is currently a visual/control foundation and is ready for later real filtering.

## Attachment State

Current state:

- DB table `audit_project_attachments` stores attachment metadata and soft-delete state.
- Project detail has upload, list, preview, download, and delete controls.
- Backend APIs exist for list/upload/preview/download/delete:
  - `GET /api/audit/projects/:id/attachments`
  - `POST /api/audit/projects/:id/attachments`
  - `GET /api/audit/attachments/:id/preview`
  - `GET /api/audit/attachments/:id/download`
  - `DELETE /api/audit/attachments/:id`
- Files are stored under the configured upload root, currently `/data/jiqing-engineering/uploads`.
- Preview supports text, image, and PDF files. Unknown files return a non-preview response and remain downloadable.
- Compressed archives and path-like filenames are rejected by the backend.
- Production acceptance on 2026-06-28 verified text/image/PDF/unknown upload behavior, preview/download, unauthenticated preview blocking, archive rejection, path traversal filename rejection, deletion, and cleanup.

Missing:

- Office online preview is intentionally not implemented; Office/unknown files should show download-oriented fallback.
- Folder upload is blocked by filename/path validation and no directory upload control is intentionally exposed, but browser-specific drag-folder edge cases should remain in manual QA.

## Security State

Positive:

- Production `admin/admin` login is rejected.
- Passwords are not stored in plaintext.
- Admin user and settings APIs require admin role.
- Audit create/update/progress requires admin/editor role.
- Theme update/reset requires admin role.
- Attachment list/upload/preview/download/delete require authenticated access, with upload/delete limited by role.
- Operation logs capture login, user, project, setting, field, option, and theme actions.

Risks:

- `token_secret()` falls back to `dev-only-change-me` if no secret env is set.
- `seed_admin_user()` can create `admin/admin` when `VITE_DEV_SERVER_URL` is present or `VITE_LOCAL_ADMIN_PASSWORD` is set; this should be hardened behind an explicit `ENABLE_DEV_ADMIN_FALLBACK=true`.
- Some read APIs are intentionally public/guest-accessible today, including audit project list/detail/meta. The target production system may require login-only access.
- Theme option/current read APIs are public; this is probably acceptable for UI bootstrapping, but should be explicitly classified.
- No role-permission matrix beyond `admin/editor/viewer`.

## Database And Migration State

Current state:

- SQLite is used in production.
- Deployment script backs up the SQLite file before deployment.
- Schema includes users, settings, operation logs, theme configs, field configs/options, projects, stages, logs, and placeholder attachments.

Gaps:

- Standalone SQLite backup script exists at `scripts/backup-sqlite.sh`.
- Guarded SQLite restore script exists at `scripts/restore-sqlite.sh`.
- PostgreSQL target schema exists at `server/postgres_schema.sql`.
- Migration notes are documented in `docs/postgresql-migration-plan.md`.
- Attachment metadata schema is represented in SQLite and PostgreSQL schema files.
- Restore and attachment backup policy is documented in `docs/backup-restore-runbook.md`.

## Tencent Cloud / Nginx State

Current state:

- Nginx serves static assets with immutable cache.
- Nginx proxies `/api/`.
- API is not directly public; it binds to `127.0.0.1`.
- Disk has sufficient free space at the time of review.
- No public static attachment directory is configured.

Gaps:

- `client_max_body_size 25m` is configured in the generated Nginx app config.
- `UPLOAD_ROOT`/`MAX_UPLOAD_SIZE` service env defaults are created by the deployment script.
- `/data/jiqing-engineering/uploads/audit-projects` is created with restricted permissions.
- gzip/brotli was not explicitly configured in the app-specific Nginx conf.

## Build And Chunk State

Current production build succeeded.

Important build output:

- Main app JS: about 17.37 kB, gzip about 6.51 kB.
- Kanban view JS: about 22.13 kB, gzip about 7.54 kB.
- Arco JS chunk: about 293.02 kB, gzip about 74.24 kB.
- Arco CSS chunk: about 369.06 kB, gzip about 47.89 kB.
- Vue vendor chunk: about 110.81 kB, gzip about 43.13 kB.

Warnings:

- Vite/esbuild reports CSS minify warnings for Arco table selectors containing `-scroll-position-*`.
- The warning does not block build, but it should be tracked as an upstream/Arco CSS compatibility warning.

Performance conclusion:

- The original main chunk problem has been reduced by route splitting and manual chunks.
- The next risks are full Arco CSS, future chart library size, and whether dashboard/gantt/admin modules stay split.

## Priority For Next Work

Recommended order:

1. Lock the product shell: rename product surfaces, add enterprise module navigation, and make unavailable modules show "模块建设中".
2. Continue the direction 1 "稳态指挥台" visual refinement across audit detail, admin settings, and responsive states.
3. Expand the theme settings page with apply-scope editing, default/enabled management, and chart theme preview.
4. Harden production security flags: explicit dev fallback, required secret in production, tighter route policy, and role/permission coverage.
5. Implement the PostgreSQL adapter/import command after the SQLite backup and restore baseline is accepted.
6. Continue chunk optimization after chart, admin, gantt, and attachment modules settle.

## Product Design Brief Playback

The next visual pass should treat this as a formal B-end engineering management platform, not a single audit kanban. The design direction is professional, restrained, engineering-oriented, and Arco-theme-driven: blue/cyan/green, dense but readable enterprise navigation, animated data dashboard, usable audit workspace, and a more polished login page with lightweight jQuery background motion.

Visual direction selected: direction 1, "稳态指挥台". The UI should prioritize dense but readable operations telemetry, muted enterprise surfaces, clear risk queues, and low-noise chart motion.
