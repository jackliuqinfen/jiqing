# Phase 1 Current State Review

Date: 2026-06-27

Target product: 江苏集庆·工程管理系统

This review is based on the current repository, production HTTP checks, production service configuration, and the latest production build.

## Executive Conclusion

The system is currently runnable as a database-backed internal audit project application. It has already moved beyond a static demo: login, SQLite persistence, audit project list/detail, kanban/gantt/table views, field configuration, option library, admin users, operation logs, Arco Design Vue runtime, and a theme whitelist/current-theme API are present.

It is not yet the full "江苏集庆·工程管理系统" target. The product shell still presents the app as an audit kanban, the login page is not redesigned, there is no animated dashboard, no chart library, no real upload/preview/download/delete attachment workflow, no module navigation for project/bidding/finance placeholders, and the Arco migration still relies on a TDesign-compatible adapter layer.

## Technology Stack

Frontend:

- Framework: Vue 3.5, Vue Router 4, Pinia 2.
- Build tool: Vite 6.
- UI library: Arco Design Vue is installed and used through `@arco-design/web-vue`.
- Theme package: `@arco-themes/vue-0000` is installed and globally imported.
- TDesign package: no TDesign dependency remains in `package.json`; however, source templates still use `t-*` component names through `src/ui/tdesignCompat.ts`.
- Chart libraries: no VChart, `@visactor/vchart-arco-theme`, ECharts, or vue-echarts dependency is installed.
- jQuery: not installed.
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
- `GET /api/system/theme/current` returned `arco-theme-0000`.
- `admin/admin` login on production returned `401`.
- Production service listens on public `8088` through Nginx and API `3008` only on localhost.

## Product Naming State

Already present:

- Backend default `system_name` is `江苏集庆·工程管理系统`.

Still inconsistent:

- `package.json` name is still `cost-audit-kanban`.
- Browser title still says `造价结算审计拖拽看板`.
- Login page still says `造价结算审计看板`.
- Main audit page brand still says `审计工程看板`.
- Admin layout brand still says `系统管理 / Admin Console`.
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
- Chart theme following cannot be verified because no chart library is installed yet.

## Dashboard And Chart State

Current state:

- Existing `GET /api/audit/dashboard/summary` returns summary counts and stage counts.
- Current audit page has simple summary cards.
- No animated dashboard page exists.
- No VChart/ECharts dependency exists.
- No `@visactor/vchart-arco-theme` dependency exists.

Gap:

- Need a new dashboard route and module.
- Need structured endpoint such as `/api/audit/dashboard/overview`.
- Need chart-vendor chunk and dashboard-chart chunk.
- Need animation, responsiveness, theme-linked chart colors, date range controls, and card sparklines.

## Attachment State

Current state:

- DB table `audit_project_attachments` exists, but it is an early placeholder schema:
  - `file_name`
  - `file_url`
  - `file_type`
  - `uploaded_by`
  - `uploaded_at`
- Project detail reads existing attachment rows and displays a simple list.
- UI says `暂无附件，已预留上传扩展位`.

Missing:

- No upload API.
- No preview API.
- No download API.
- No delete API.
- No front-end upload control.
- No file validation for compressed files or folders.
- No `UPLOAD_ROOT` environment variable.
- No cloud-disk upload directory exists in service config.
- No server-side MIME/ext/size validation.
- No secure relative-path storage model.
- No authenticated attachment streaming implementation.

## Security State

Positive:

- Production `admin/admin` login is rejected.
- Passwords are not stored in plaintext.
- Admin user and settings APIs require admin role.
- Audit create/update/progress requires admin/editor role.
- Theme update/reset requires admin role.
- Operation logs capture login, user, project, setting, field, option, and theme actions.

Risks:

- `token_secret()` falls back to `dev-only-change-me` if no secret env is set.
- `seed_admin_user()` can create `admin/admin` when `VITE_DEV_SERVER_URL` is present or `VITE_LOCAL_ADMIN_PASSWORD` is set; this should be hardened behind an explicit `ENABLE_DEV_ADMIN_FALLBACK=true`.
- Some read APIs are intentionally public/guest-accessible today, including audit project list/detail/meta. The target production system may require login-only access.
- Theme option/current read APIs are public; this is probably acceptable for UI bootstrapping, but should be explicitly classified.
- No role-permission matrix beyond `admin/editor/viewer`.
- No attachment authorization exists because attachment APIs are not implemented.

## Database And Migration State

Current state:

- SQLite is used in production.
- Deployment script backs up the SQLite file before deployment.
- Schema includes users, settings, operation logs, theme configs, field configs/options, projects, stages, logs, and placeholder attachments.

Gaps:

- No standalone backup script.
- No PostgreSQL migration SQL or migration notes.
- No attachment metadata final schema.
- No documented restore command.
- No attachment backup policy.

## Tencent Cloud / Nginx State

Current state:

- Nginx serves static assets with immutable cache.
- Nginx proxies `/api/`.
- API is not directly public; it binds to `127.0.0.1`.
- Disk has sufficient free space at the time of review.
- No public static attachment directory is configured.

Gaps:

- No `client_max_body_size` upload limit is configured.
- No `UPLOAD_ROOT`/`MAX_UPLOAD_SIZE` service env exists.
- No `/data/jiqing-engineering/uploads` or equivalent upload root is configured in service.
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
2. Create the new home data dashboard route and choose VChart first, with `@visactor/vchart-arco-theme` evaluated before ECharts.
3. Implement the attachment backend properly before polishing attachment UI.
4. Redesign login page with a scoped jQuery animation background after visual direction is approved.
5. Harden production security flags: explicit dev fallback, required secret in production, tighter route policy, and role/permission coverage.
6. Add backup/restore scripts and PostgreSQL migration notes.
7. Continue chunk optimization after chart and attachment modules land.

## Product Design Brief Playback

The next visual pass should treat this as a formal B-end engineering management platform, not a single audit kanban. The design direction is professional, restrained, engineering-oriented, and Arco-theme-driven: blue/cyan/green, dense but readable enterprise navigation, animated data dashboard, usable audit workspace, and a more polished login page with lightweight jQuery background motion.

Because there is no external Figma/screenshot target, the Product Design workflow should generate three visual directions before implementing the major UI redesign.
