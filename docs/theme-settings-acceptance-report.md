# Theme Settings Acceptance Report

Date: 2026-06-28

Target: 江苏集庆·工程管理系统 admin theme settings

## Result

The backend theme whitelist and current-theme APIs were already present. This pass expands the admin theme settings surface into a productized theme control panel while keeping the whitelist-only safety model.

## Implemented

- Theme cards show theme name, package identifier, theme key, enabled/default status, and preview colors.
- Theme selection continues to save through `PUT /api/system/theme/current`.
- Restore default continues to use `POST /api/system/theme/reset`.
- Dark mode and compact mode toggles remain available and persist through the current-theme setting.
- Apply scope selector now supports:
  - Global
  - 首页数据看板
  - 审计看板
  - 后台管理
- Current theme preview shows a small shell mock that uses the selected whitelist color set.
- Chart theme preview uses VChart and the current whitelist color set.
- There is still no arbitrary package-name input and no runtime dynamic npm package loading.

## Safety Model

- Theme options are read from `GET /api/system/theme/options`.
- Only enabled whitelist themes can be selected.
- The default theme remains `@arco-themes/vue-0000`.
- Arco fallback remains represented by the `arco-default` whitelist option.
- Theme update/reset requires admin permissions on the backend.

## Build Evidence

`npm run build` passed after the change.

Relevant build shape:

- `AdminSystemSettings` remains an async route chunk.
- `VChartPanel` is emitted as a small separate component chunk.
- VChart vendor chunks remain split from the main app chunk.
- The known Arco CSS minify warnings for `-scroll-position-*` still appear and remain non-blocking.

## Remaining Work

- Enable/default management is displayed but not editable in the admin UI.
- Dark and compact mode foundations are present, but a full dark/density pass across every page remains future work.
- Visual browser regression should be run after deployment for the admin settings page on desktop and mobile.
