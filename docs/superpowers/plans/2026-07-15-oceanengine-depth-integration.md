# OceanEngine-Inspired Workbench Depth Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the existing Jiqing ERP workbench so its background, navigation chrome, control surfaces, and solid business panels form the same clear visual hierarchy as a mature OceanEngine-style B-side console without copying third-party brand assets.

**Architecture:** Keep all visual rules in the existing global Arco skin and use `AppLayout.vue` only for semantic shell structure. Add a small source-level contract test that prevents future CSS changes from collapsing the four-layer hierarchy. Business views, API calls, permissions, routes, and real empty states remain unchanged.

**Tech Stack:** Vue 3, TypeScript, Arco Design, CSS custom properties, Node.js source-contract test, Vite production build.

## Global Constraints

- Do not modify business fields, APIs, permissions, workflows, or data models.
- Do not add sample projects, sample amounts, or simulated dashboard records.
- Do not copy OceanEngine background images, logos, illustrations, icons, or proprietary component code.
- Keep page panels and cards at 8px radius or less.
- Use backdrop blur only for navigation, statistics, and query/control surfaces.
- Keep tables, forms, ledgers, modals, and detail panels on opaque white surfaces.
- Preserve the existing ERP table density and current responsive sidebar behavior.

---

### Task 1: Add a source-level visual hierarchy contract

**Files:**
- Create: `scripts/verify-premium-theme.mjs`
- Modify: `package.json`
- Test: `scripts/verify-premium-theme.mjs`

**Interfaces:**
- Consumes: `src/styles/arco-premium-workbench.css` and `src/views/AppLayout.vue` as UTF-8 source text.
- Produces: `npm run test:premium-theme`, exiting `0` when the four visual layers and shell semantics remain present.

- [ ] **Step 1: Create the failing source-contract test**

```js
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const css = await readFile(new URL('../src/styles/arco-premium-workbench.css', import.meta.url), 'utf8')
const layout = await readFile(new URL('../src/views/AppLayout.vue', import.meta.url), 'utf8')

const requiredTokens = [
  '--workspace-bg-top',
  '--workspace-bg-mid',
  '--workspace-bg-bottom',
  '--workspace-grid',
  '--premium-shadow-ambient',
  '--premium-shadow-card',
  '--premium-shadow-float',
]

for (const token of requiredTokens) {
  assert.match(css, new RegExp(token), `missing visual token: ${token}`)
}

assert.match(css, /\.system-shell::before/)
assert.match(css, /\.platform-topbar[\s\S]*backdrop-filter/)
assert.match(css, /\.arco-table[\s\S]*background:\s*#fff/)
assert.match(css, /\.arco-modal[\s\S]*background:\s*#fff/)
assert.match(layout, /aria-label="平台级模块"/)
assert.match(layout, /aria-label="当前模块业务功能"/)

console.log('premium theme contract: PASS')
```

- [ ] **Step 2: Add the npm script**

Add this entry to `package.json` under `scripts`:

```json
"test:premium-theme": "node scripts/verify-premium-theme.mjs"
```

- [ ] **Step 3: Run the contract and verify it fails before implementation**

Run: `npm.cmd run test:premium-theme`

Expected: FAIL with `missing visual token: --workspace-bg-top`.

- [ ] **Step 4: Commit the test contract**

```bash
git add package.json scripts/verify-premium-theme.mjs
git commit -m "test: define premium workbench visual contract"
```

---

### Task 2: Implement the layered workspace background and shell chrome

**Files:**
- Modify: `src/styles/arco-premium-workbench.css:13-280`
- Modify: `src/views/AppLayout.vue:1-128`
- Test: `scripts/verify-premium-theme.mjs`

**Interfaces:**
- Consumes: existing classes `.system-shell`, `.platform-topbar`, `.platform-nav`, `.system-sidebar`, `.system-main`, and `.system-content`.
- Produces: shared CSS tokens and four visually distinct layers without changing route or sidebar state APIs.

- [ ] **Step 1: Replace the single page gradient with explicit environment tokens**

Update the root tokens to include:

```css
:root {
  --workspace-bg-top: #eaf4ff;
  --workspace-bg-mid: #f4f8fd;
  --workspace-bg-bottom: #ffffff;
  --workspace-grid: rgba(50, 100, 190, 0.026);
  --premium-shadow-ambient: 0 4px 16px rgba(31, 64, 108, 0.045);
  --premium-shadow-card: 0 8px 24px rgba(31, 64, 108, 0.065);
  --premium-shadow-float: 0 16px 40px rgba(25, 54, 96, 0.13);
  --premium-page-gradient: linear-gradient(
    180deg,
    var(--workspace-bg-top) 0,
    var(--workspace-bg-mid) 260px,
    #f8fafc 560px,
    var(--workspace-bg-bottom) 100%
  );
}
```

- [ ] **Step 2: Add the fixed top texture and environment wash**

```css
.system-shell::before {
  content: '';
  position: fixed;
  z-index: -1;
  inset: var(--premium-header-height) 0 auto 0;
  height: 360px;
  pointer-events: none;
  background:
    linear-gradient(105deg, rgba(255, 255, 255, 0.3), rgba(184, 221, 255, 0.12)),
    repeating-linear-gradient(126deg, var(--workspace-grid) 0 1px, transparent 1px 13px);
  mask-image: linear-gradient(180deg, #000 0, rgba(0, 0, 0, 0.62) 62%, transparent 100%);
}
```

- [ ] **Step 3: Tune the platform topbar material**

```css
.platform-topbar {
  background: rgba(255, 255, 255, 0.76) !important;
  border-bottom: 1px solid rgba(202, 215, 234, 0.72) !important;
  box-shadow: 0 5px 18px rgba(31, 64, 108, 0.035) !important;
  backdrop-filter: blur(14px) saturate(128%);
  -webkit-backdrop-filter: blur(14px) saturate(128%);
}
```

- [ ] **Step 4: Keep the second-level sidebar light and anchored**

```css
.system-sidebar {
  background: rgba(248, 251, 255, 0.72) !important;
  border-right: 1px solid rgba(210, 221, 236, 0.74) !important;
  box-shadow: 8px 0 30px rgba(31, 64, 108, 0.025) !important;
}

.module-link--active {
  background: rgba(255, 255, 255, 0.94) !important;
  box-shadow: var(--premium-shadow-ambient) !important;
}
```

- [ ] **Step 5: Add semantic current-page state without changing navigation behavior**

Add `:aria-current="isTopNavActive(item.path) ? 'page' : undefined"` to platform links and `:aria-current="isSideNavActive(item) ? 'page' : undefined"` to module links.

- [ ] **Step 6: Run the source contract**

Run: `npm.cmd run test:premium-theme`

Expected: `premium theme contract: PASS`.

- [ ] **Step 7: Commit the shell layer**

```bash
git add src/styles/arco-premium-workbench.css src/views/AppLayout.vue
git commit -m "style: deepen workbench shell atmosphere"
```

---

### Task 3: Separate translucent control surfaces from solid business surfaces

**Files:**
- Modify: `src/styles/arco-premium-workbench.css:450-900`
- Test: `scripts/verify-premium-theme.mjs`

**Interfaces:**
- Consumes: existing page-level classes for summary cards, filter panels, library toolbars, ledgers, audit boards, finance panels, bidding panels, and admin tables.
- Produces: translucent L2 control surfaces and opaque L3 business surfaces with stable 8px/6px radii.

- [ ] **Step 1: Define the L2 control-surface group**

```css
.summary-card,
.kpi-card,
.project-management .filter-panel,
.file-library .library-toolbar,
.audit-main .filter-panel,
.admin-filter-bar {
  background: rgba(255, 255, 255, 0.68) !important;
  border: 1px solid rgba(206, 219, 236, 0.78) !important;
  box-shadow: var(--premium-shadow-ambient) !important;
  backdrop-filter: blur(12px) saturate(118%);
  -webkit-backdrop-filter: blur(12px) saturate(118%);
}
```

- [ ] **Step 2: Define the L3 solid-surface group**

```css
.ledger-panel,
.file-panel,
.kanban-column,
.stage-table-card,
.finance-section,
.bidding-section,
.admin-table-card,
.arco-table,
.arco-table-container,
.arco-modal {
  background: #fff !important;
  border: 1px solid var(--premium-line) !important;
  border-radius: var(--premium-radius) !important;
  box-shadow: var(--premium-shadow-ambient) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}
```

- [ ] **Step 3: Normalize table hierarchy**

```css
.arco-table-th {
  background: #f6f8fb !important;
  border-bottom-color: #e2e8f2 !important;
}

.arco-table-td {
  background: #fff !important;
  border-bottom-color: #edf1f6 !important;
}

.arco-table-tr:hover .arco-table-td {
  background: #f7faff !important;
}
```

- [ ] **Step 4: Normalize hover and focus states without layout movement**

```css
.summary-card:hover,
.kpi-card:hover,
.project-card:hover {
  border-color: rgba(22, 93, 255, 0.22) !important;
  box-shadow: var(--premium-shadow-card) !important;
  transform: none !important;
}

.arco-input-wrapper:focus-within,
.arco-select-view-focus,
.arco-picker-focused {
  border-color: rgba(22, 93, 255, 0.72) !important;
  box-shadow: 0 0 0 2px rgba(22, 93, 255, 0.08) !important;
}
```

- [ ] **Step 5: Run the contract and production build**

Run:

```bash
npm.cmd run test:premium-theme
npm.cmd run build
```

Expected: contract prints `PASS`; Vue type-check and Vite build exit `0`.

- [ ] **Step 6: Commit the component material system**

```bash
git add src/styles/arco-premium-workbench.css
git commit -m "style: separate control and business surfaces"
```

---

### Task 4: Perform desktop and responsive visual regression

**Files:**
- Modify only if a mismatch is found: `src/styles/arco-premium-workbench.css`
- Modify only if shell semantics are wrong: `src/views/AppLayout.vue`
- Test: local pages at `/`, `/project-management`, `/audit`, `/materials`, `/finance`, `/bidding`, `/admin/field-configs`

**Interfaces:**
- Consumes: authenticated local QA environment and the visual tokens from Tasks 2-3.
- Produces: accepted screenshots at 1560×960 and one narrow desktop viewport, with no layout overlap or false data.

- [ ] **Step 1: Start the local API and Vite server using the existing isolated QA database**

Start the API in one PowerShell session:

```powershell
$env:AUDIT_DB_PATH=(Resolve-Path '.tmp/ui-review-20260715-b.sqlite3').Path
$env:AUDIT_API_HOST='127.0.0.1'
$env:AUDIT_API_PORT='3010'
python server/audit_api.py
```

Start Vite in a second PowerShell session:

```powershell
$env:VITE_API_PROXY_TARGET='http://127.0.0.1:3010'
npm.cmd exec vite -- --configLoader runner --port 5183 --host 127.0.0.1
```

Expected: Vite prints a local URL and API requests return `200` after login.

- [ ] **Step 2: Capture the representative pages at 1560×960**

Capture these routes after authenticated data requests settle:

```text
/
/project-management
/audit
/materials
/finance
/bidding
/admin/field-configs
```

Expected: every screenshot shows the same blue-to-white environment, translucent controls, and solid white business surfaces.

- [ ] **Step 3: Verify the shell at 1100×800**

Expected: platform navigation remains usable, the sidebar enters its narrow behavior without text overflow, and fixed-format controls do not resize.

- [ ] **Step 4: Check acceptance conditions**

Verify all of the following:

```text
no blue fill between cards
no dotted outer frame
no text overlap or vertical character stacking
no business table with backdrop blur
no fake project, amount, or reminder data
sidebar resizer invisible at rest
```

- [ ] **Step 5: Re-run final checks**

Run:

```bash
npm.cmd run test:premium-theme
npm.cmd run build
git diff --check
git status --short
```

Expected: tests/build pass; `git diff --check` has no output; status contains only the intended theme files plus pre-existing unrelated untracked paths.

- [ ] **Step 6: Commit any final visual corrections**

```bash
git add src/styles/arco-premium-workbench.css src/views/AppLayout.vue
git commit -m "fix: polish premium workbench visual hierarchy"
```
