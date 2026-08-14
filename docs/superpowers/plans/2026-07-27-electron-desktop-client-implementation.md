# Electron Desktop Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a Windows Electron client that securely loads the central ERP and optionally mirrors authorized Material Center files to a local folder without automatic upload.

**Architecture:** The Electron shell loads the production Vue application from an allowlisted central origin and keeps all business data on the server. A main-process synchronization engine receives a short-lived in-memory bearer token from the authenticated web application, fetches an effective server policy and incremental manifest, verifies content hashes, and writes a read-only local mirror. The backend adapts the existing `project_files` and `audit_project_attachments` sources so the desktop manifest matches Material Center.

**Tech Stack:** Vue 3.5, TypeScript 5.7, Python standard-library HTTP API, SQLite/PostgreSQL schemas, Electron 43.2.0, electron-builder 26.15.3, `@electron/fuses` 2.1.3, Sharp 0.34.5, png-to-ico 3.0.1, Node test runner.

## Global Constraints

- Windows target is Windows 10 and Windows 11 x64.
- The central server remains the only authoritative business data source.
- The first release synchronizes server to local only; it never watches local files for upload.
- Local delete, rename, or edit must not mutate the server.
- Synchronization is disabled by default and requires server-side authorization.
- Every manifest and download request must re-evaluate the authenticated user's current access.
- Production builds load HTTPS only and never bypass certificate errors.
- Internal HTTP acceptance builds must display an `内部测试` environment marker.
- Electron remote renderers use `nodeIntegration: false`, `contextIsolation: true`, `sandbox: true`, and `webSecurity: true`.
- Bearer tokens exist in memory only and must not be written to disk or logs.
- The enterprise SVG at `public/aoqiang-construction-logo.svg` is the only icon source unless the brand owner replaces that source asset.
- Empty states use real empty results; no sample projects, files, users, or fake synchronization data may be added.
- The web application must remain independently buildable and deployable without Electron.
- Formal production distribution is blocked until the server has a valid HTTPS origin and the Windows installer is code signed.

---

### Task 1: Add The Server-Side Desktop Policy And Bootstrap Contract

**Files:**
- Create: `server/desktop_sync_policy.py`
- Create: `server/tests/test_desktop_sync_policy.py`
- Modify: `server/audit_api.py`

**Interfaces:**
- Produces: `normalize_desktop_sync_policy(value: object) -> dict`
- Produces: `effective_desktop_sync_policy(value: object, user: Mapping) -> dict`
- Produces: `GET /api/desktop/bootstrap`
- Produces: `GET /api/desktop/policy`
- Consumes later: Tasks 2, 3, 5, and 6 use the normalized policy keys exactly as defined here.

- [ ] **Step 1: Write failing policy normalization tests**

```python
import unittest

from server.desktop_sync_policy import (
    DEFAULT_DESKTOP_SYNC_POLICY,
    effective_desktop_sync_policy,
    normalize_desktop_sync_policy,
)


class DesktopSyncPolicyTest(unittest.TestCase):
    def test_default_policy_is_disabled(self):
        policy = normalize_desktop_sync_policy({})
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["allowedRoles"], ["admin"])
        self.assertEqual(policy["projectSelectionMode"], "user_select")
        self.assertEqual(policy["pollIntervalSeconds"], 300)
        self.assertEqual(policy["maxFileSizeBytes"], 100 * 1024 * 1024)
        self.assertEqual(policy["maxLocalStorageBytes"], 10 * 1024 * 1024 * 1024)

    def test_normalizer_clamps_and_filters_untrusted_values(self):
        policy = normalize_desktop_sync_policy({
            "enabled": True,
            "allowedRoles": ["admin", "root", "viewer"],
            "allowedUserIds": [" user-1 ", "", 5],
            "allowedExtensions": ["PDF", ".docx", "../exe"],
            "pollIntervalSeconds": 1,
            "maxFileSizeMb": 9000,
            "maxLocalStorageGb": -1,
        })
        self.assertEqual(policy["allowedRoles"], ["admin", "viewer"])
        self.assertEqual(policy["allowedUserIds"], ["user-1"])
        self.assertEqual(policy["allowedExtensions"], [".pdf", ".docx"])
        self.assertEqual(policy["pollIntervalSeconds"], 60)
        self.assertEqual(policy["maxFileSizeBytes"], 500 * 1024 * 1024)
        self.assertEqual(policy["maxLocalStorageBytes"], 1 * 1024 * 1024 * 1024)

    def test_effective_policy_requires_role_or_user_allowance(self):
        stored = {**DEFAULT_DESKTOP_SYNC_POLICY, "enabled": True}
        viewer = effective_desktop_sync_policy(stored, {"id": "u1", "role": "viewer"})
        admin = effective_desktop_sync_policy(stored, {"id": "u2", "role": "admin"})
        self.assertFalse(viewer["enabledForCurrentUser"])
        self.assertTrue(admin["enabledForCurrentUser"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the policy tests and verify they fail**

Run:

```powershell
python -m unittest server.tests.test_desktop_sync_policy -v
```

Expected: `ModuleNotFoundError: No module named 'server.desktop_sync_policy'`.

- [ ] **Step 3: Implement the policy module**

Create constants and pure validation in `server/desktop_sync_policy.py`:

```python
DEFAULT_DESKTOP_SYNC_POLICY = {
    "enabled": False,
    "enabledByDefault": False,
    "allowedRoles": ["admin"],
    "allowedUserIds": [],
    "projectSelectionMode": "user_select",
    "allowedProjectRefs": [],
    "allowedCategoryKeys": [],
    "allowedExtensions": [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".jpg", ".jpeg", ".png", ".webp", ".txt",
    ],
    "maxFileSizeBytes": 100 * 1024 * 1024,
    "maxLocalStorageBytes": 10 * 1024 * 1024 * 1024,
    "pollIntervalSeconds": 300,
    "allowFolderSelection": True,
    "removeLocalFilesOnRevocation": False,
    "policyVersion": 1,
}

ALLOWED_ROLES = {"admin", "editor", "viewer"}
ALLOWED_PROJECT_MODES = {"user_select", "admin_assigned"}


def _unique_strings(values):
    result = []
    for value in values if isinstance(values, list) else []:
        normalized = str(value).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def normalize_desktop_sync_policy(value):
    raw = value if isinstance(value, dict) else {}
    roles = [role for role in _unique_strings(raw.get("allowedRoles")) if role in ALLOWED_ROLES]
    extensions = []
    for item in _unique_strings(raw.get("allowedExtensions")):
        suffix = item.lower()
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        if suffix[1:].isalnum() and suffix not in extensions:
            extensions.append(suffix)
    file_mb = max(1, min(500, int(raw.get("maxFileSizeMb", 100) or 100)))
    storage_gb = max(1, min(500, int(raw.get("maxLocalStorageGb", 10) or 10)))
    interval = max(60, min(3600, int(raw.get("pollIntervalSeconds", 300) or 300)))
    return {
        **DEFAULT_DESKTOP_SYNC_POLICY,
        "enabled": bool(raw.get("enabled", False)),
        "enabledByDefault": bool(raw.get("enabledByDefault", False)),
        "allowedRoles": roles or ["admin"],
        "allowedUserIds": _unique_strings(raw.get("allowedUserIds")),
        "projectSelectionMode": (
            raw.get("projectSelectionMode")
            if raw.get("projectSelectionMode") in ALLOWED_PROJECT_MODES
            else "user_select"
        ),
        "allowedProjectRefs": _unique_strings(raw.get("allowedProjectRefs")),
        "allowedCategoryKeys": _unique_strings(raw.get("allowedCategoryKeys")),
        "allowedExtensions": extensions or list(DEFAULT_DESKTOP_SYNC_POLICY["allowedExtensions"]),
        "maxFileSizeBytes": file_mb * 1024 * 1024,
        "maxLocalStorageBytes": storage_gb * 1024 * 1024 * 1024,
        "pollIntervalSeconds": interval,
        "allowFolderSelection": bool(raw.get("allowFolderSelection", True)),
        "removeLocalFilesOnRevocation": bool(raw.get("removeLocalFilesOnRevocation", False)),
        "policyVersion": max(1, int(raw.get("policyVersion", 1) or 1)),
    }


def effective_desktop_sync_policy(value, user):
    policy = normalize_desktop_sync_policy(value)
    user_id = str(user.get("id") or "")
    role = str(user.get("role") or "")
    allowed = role in policy["allowedRoles"] or user_id in policy["allowedUserIds"]
    return {**policy, "enabledForCurrentUser": bool(policy["enabled"] and allowed)}
```

- [ ] **Step 4: Seed and validate the policy in the existing settings flow**

In `seed_system_settings`, add:

```python
(
    "desktop_sync_policy",
    {
        "enabled": False,
        "allowedRoles": ["admin"],
        "allowedUserIds": [],
        "projectSelectionMode": "user_select",
        "allowedProjectRefs": [],
        "allowedCategoryKeys": [],
        "allowedExtensions": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg", ".png", ".webp", ".txt"],
        "maxFileSizeMb": 100,
        "maxLocalStorageGb": 10,
        "pollIntervalSeconds": 300,
        "allowFolderSelection": True,
        "removeLocalFilesOnRevocation": False,
        "policyVersion": 1,
    },
    "system",
    "Windows 客户端本地只读同步策略",
),
```

In `set_system_setting`, normalize `desktop_sync_policy`, increment the prior
`policyVersion`, and store display units (`maxFileSizeMb`, `maxLocalStorageGb`)
while returning byte values only from `/api/desktop/policy`.

- [ ] **Step 5: Add bootstrap and effective policy handlers**

Add methods to `Handler`:

```python
def desktop_bootstrap(self, conn):
    row = conn.execute(
        "SELECT setting_value FROM system_settings WHERE setting_key = 'desktop_sync_policy'"
    ).fetchone()
    value = json.loads(row["setting_value"] or "{}") if row else {}
    policy = normalize_desktop_sync_policy(value)
    self.respond(200, {"success": True, "data": {
        "environmentName": os.environ.get("APP_ENV_NAME", "工程管理系统"),
        "minimumDesktopVersion": os.environ.get("MINIMUM_DESKTOP_VERSION", "1.0.0"),
        "syncPolicyVersion": policy["policyVersion"],
    }})

def desktop_policy(self, conn):
    user = self.require_user(conn)
    if not user:
        return
    row = conn.execute(
        "SELECT setting_value FROM system_settings WHERE setting_key = 'desktop_sync_policy'"
    ).fetchone()
    value = json.loads(row["setting_value"] or "{}") if row else {}
    self.respond(200, {
        "success": True,
        "data": effective_desktop_sync_policy(value, row_dict(user)),
    })
```

Route `GET /api/desktop/bootstrap` before authenticated desktop routes and route
`GET /api/desktop/policy` through `desktop_policy`.

- [ ] **Step 6: Add API contract tests**

Extend `server/tests/test_desktop_sync_policy.py` with an in-process Handler test
matching the existing `test_document_api_contract.py` request helper:

```python
def test_bootstrap_is_public_but_policy_requires_authentication(self):
    status, _headers, bootstrap = self.request("GET", "/api/desktop/bootstrap")
    self.assertEqual(status, 200)
    self.assertEqual(bootstrap["data"]["minimumDesktopVersion"], "1.0.0")

    status, _headers, payload = self.request("GET", "/api/desktop/policy")
    self.assertEqual(status, 401)
    self.assertFalse(payload["success"])
```

- [ ] **Step 7: Run policy tests and the full backend suite**

Run:

```powershell
python -m unittest server.tests.test_desktop_sync_policy -v
python -m unittest discover -s server/tests -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit the policy contract**

```powershell
git add server/desktop_sync_policy.py server/audit_api.py server/tests/test_desktop_sync_policy.py
git commit -m "feat: add desktop sync policy contract"
```

---

### Task 2: Build The Unified Material Center Synchronization Manifest

**Files:**
- Create: `server/desktop_sync_repository.py`
- Create: `server/tests/test_desktop_sync_repository.py`
- Create: `server/tests/test_desktop_sync_api.py`
- Modify: `server/migrations.py`
- Modify: `server/schema.sql`
- Modify: `server/postgres_schema.sql`
- Modify: `server/audit_api.py`

**Interfaces:**
- Consumes: `effective_desktop_sync_policy` from Task 1.
- Produces: `list_sync_project_roots(conn, policy) -> list[dict]`
- Produces: `list_sync_manifest(conn, policy, project_refs, cursor, limit, path_resolver) -> dict`
- Produces: `GET /api/desktop/sync/projects`
- Produces: `GET /api/desktop/sync/manifest`
- Consumes later: Electron Task 6 uses the response shape exactly.

- [ ] **Step 1: Write failing repository tests for source merging**

Create fixtures with one `project_files` row, one linked audit attachment, and
one unlinked audit attachment:

```python
class DesktopSyncRepositoryTest(unittest.TestCase):
    def test_linked_audit_attachment_merges_into_project_root(self):
        roots = list_sync_project_roots(self.conn, self.policy)
        project = next(item for item in roots if item["projectRef"] == "project:project-1")
        self.assertEqual(project["fileCount"], 2)
        self.assertEqual(project["projectName"], "区直学校维修")

    def test_unlinked_audit_project_keeps_an_independent_root(self):
        roots = list_sync_project_roots(self.conn, self.policy)
        item = next(item for item in roots if item["projectRef"] == "audit:audit-2")
        self.assertIsNone(item["canonicalProjectId"])
        self.assertEqual(item["auditProjectId"], "audit-2")

    def test_manifest_has_stable_source_revision_and_hash(self):
        result = list_sync_manifest(
            self.conn,
            self.policy,
            ["project:project-1"],
            cursor="",
            limit=200,
            path_resolver=self.path_resolver,
        )
        entries = result["items"]
        self.assertEqual({item["sourceType"] for item in entries}, {
            "project_file", "audit_attachment",
        })
        self.assertTrue(all(len(item["sha256"]) == 64 for item in entries))
        self.assertTrue(all(item["downloadPath"].startswith("/api/") for item in entries))
```

- [ ] **Step 2: Run repository tests and verify they fail**

Run:

```powershell
python -m unittest server.tests.test_desktop_sync_repository -v
```

Expected: `ModuleNotFoundError: No module named 'server.desktop_sync_repository'`.

- [ ] **Step 3: Add the hash-cache migration**

Add the same table to SQLite migration SQL, `server/schema.sql`, and
`server/postgres_schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS desktop_sync_hash_cache (
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  revision_key TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (source_type, source_id, revision_key)
);

CREATE INDEX IF NOT EXISTS idx_desktop_sync_hash_updated
  ON desktop_sync_hash_cache(updated_at);
```

Register a checksum-backed migration in `server/migrations.py`. The migration
must be additive and must not rewrite `project_files`,
`audit_project_attachments`, uploads, or project data.

- [ ] **Step 4: Implement unified project references**

Use these rules in `server/desktop_sync_repository.py`:

```python
def project_record_ref(project_id):
    return f"project:{project_id}"


def audit_project_ref(audit_project_id):
    return f"audit:{audit_project_id}"


def effective_project_ref(canonical_project_id, audit_project_id):
    return (
        project_record_ref(canonical_project_id)
        if canonical_project_id
        else audit_project_ref(audit_project_id)
    )
```

Query current, non-deleted `project_files` and non-deleted
`audit_project_attachments`. Join audit attachments through `audit_projects` to
`project_records`; linked audit files use `project:<project_record_id>`.

Do not merge unlinked audit projects by name or code.

- [ ] **Step 5: Implement stable revision and hash caching**

Use immutable source revisions:

```python
def source_revision(source_type, row):
    if source_type == "project_file":
        return f"{row['id']}:{row['version_no']}:{row['file_size']}:{row['uploaded_at']}"
    return f"{row['id']}:{row['file_size']}:{row['created_at'] or row['uploaded_at']}"
```

Resolve each relative path through the existing safe attachment-path helper.
Read files in 1 MiB chunks. Cache SHA-256 by `(source_type, source_id,
revision_key)`. Missing files remain visible in roots but manifest entries return
`availability: "missing"` and no download path; they must not crash the page.

- [ ] **Step 6: Implement opaque cursor pagination**

Sort ascending by `(uploadedAt, sourceType, sourceId)` and encode the last key as
URL-safe base64 JSON:

```python
def encode_cursor(item):
    payload = json.dumps([
        item["uploadedAt"], item["sourceType"], item["sourceId"]
    ], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
```

Decode defensively. Invalid cursors return a structured `400` response with code
`invalid_sync_cursor`. Clamp `limit` to `1..200`.

- [ ] **Step 7: Add authenticated routes**

Add:

```text
GET /api/desktop/sync/projects
GET /api/desktop/sync/manifest?projectRefs=project%3A1&cursor=&limit=200
```

Rules:

- Require a logged-in user.
- Require `enabledForCurrentUser`.
- Intersect requested project refs with effective policy.
- For `admin_assigned`, accept only `allowedProjectRefs`.
- Reuse existing authenticated download routes:
  - `/api/project-files/{id}/download`
  - `/api/audit/attachments/{id}/download`
- Write no business or operation-log rows for read-only manifest reads.

- [ ] **Step 8: Write API authorization and pagination tests**

Cover:

```python
def test_disabled_policy_returns_403(self):
    status, _headers, payload = self.request(
        "GET", "/api/desktop/sync/projects", user_id="editor-user"
    )
    self.assertEqual(status, 403)
    self.assertEqual(payload["code"], "desktop_sync_disabled")

def test_manifest_intersects_admin_assigned_projects(self):
    self.enable_policy(
        allowedRoles=["editor"],
        projectSelectionMode="admin_assigned",
        allowedProjectRefs=["project:project-1"],
    )
    status, _headers, payload = self.request(
        "GET",
        "/api/desktop/sync/manifest?projectRefs=project%3Aproject-1,project%3Aproject-2",
        user_id="editor-user",
    )
    self.assertEqual(status, 200)
    self.assertEqual(
        {item["projectRef"] for item in payload["data"]["items"]},
        {"project:project-1"},
    )

def test_next_cursor_does_not_duplicate_rows(self):
    first = self.manifest(limit=1)
    second = self.manifest(limit=1, cursor=first["nextCursor"])
    self.assertNotEqual(first["items"][0]["sourceId"], second["items"][0]["sourceId"])
```

- [ ] **Step 9: Run migration, repository, API, and full backend tests**

```powershell
python -m unittest server.tests.test_desktop_sync_repository -v
python -m unittest server.tests.test_desktop_sync_api -v
python -m unittest server.tests.test_document_migrations -v
python -m unittest discover -s server/tests -v
```

Expected: all tests pass.

- [ ] **Step 10: Commit the manifest**

```powershell
git add server/desktop_sync_repository.py server/migrations.py server/schema.sql server/postgres_schema.sql server/audit_api.py server/tests/test_desktop_sync_repository.py server/tests/test_desktop_sync_api.py
git commit -m "feat: expose authorized desktop sync manifest"
```

---

### Task 3: Add Administrator Desktop Synchronization Settings

**Files:**
- Create: `scripts/verify-desktop-sync-settings.mjs`
- Modify: `src/types/index.ts`
- Modify: `src/views/admin/AdminSystemSettings.vue`
- Modify: `package.json`

**Interfaces:**
- Consumes: generic `getSystemSetting` and `setSystemSetting`.
- Produces: `DesktopSyncPolicySetting` in `src/types/index.ts`.
- Produces: administrator controls for the exact Task 1 setting fields.
- Consumes later: Task 7 relies on the same labels and policy semantics.

- [ ] **Step 1: Add a failing settings contract verifier**

```javascript
import { readFileSync } from 'node:fs'

const settings = readFileSync('src/views/admin/AdminSystemSettings.vue', 'utf8')
const types = readFileSync('src/types/index.ts', 'utf8')

for (const marker of [
  '本地资料同步',
  '服务器到本地只读同步',
  'allowedRoles',
  'projectSelectionMode',
  'maxLocalStorageGb',
  'pollIntervalSeconds',
  'removeLocalFilesOnRevocation',
]) {
  if (!settings.includes(marker)) throw new Error(`Missing settings marker: ${marker}`)
}

if (!types.includes("'desktop_sync_policy'")) {
  throw new Error('desktop_sync_policy is missing from SystemSettingKey')
}
if (!types.includes('interface DesktopSyncPolicySetting')) {
  throw new Error('DesktopSyncPolicySetting is missing')
}
```

Add:

```json
"test:desktop-settings": "node scripts/verify-desktop-sync-settings.mjs"
```

- [ ] **Step 2: Run the verifier and confirm failure**

```powershell
npm run test:desktop-settings
```

Expected: failure for missing `本地资料同步`.

- [ ] **Step 3: Add the policy type**

```typescript
export interface DesktopSyncPolicySetting {
  enabled: boolean
  enabledByDefault: boolean
  allowedRoles: AdminRole[]
  allowedUserIds: string[]
  projectSelectionMode: 'user_select' | 'admin_assigned'
  allowedProjectRefs: string[]
  allowedCategoryKeys: string[]
  allowedExtensions: string[]
  maxFileSizeMb: number
  maxLocalStorageGb: number
  pollIntervalSeconds: number
  allowFolderSelection: boolean
  removeLocalFilesOnRevocation: boolean
  policyVersion: number
}
```

Add `'desktop_sync_policy'` to `SystemSettingKey` and
`DesktopSyncPolicySetting` to `SystemSettingValue`.

- [ ] **Step 4: Add the administrator settings card**

Add an Arco card titled `本地资料同步` with:

- Master switch, default off.
- Fixed explanation: `服务器到本地只读同步，本地新增或修改不会自动上传。`
- Role checkboxes for administrator, editor, and viewer.
- User allowlist populated by existing `getAdminUsers`.
- `user_select` and `admin_assigned` segmented choice.
- Assigned project multi-select populated from `/api/desktop/sync/projects` when
  the current admin is sync-authorized; otherwise use project records with
  `project:<id>` values.
- Category multi-select populated from `fetchProjectMeta`.
- Extension tag input normalized to lowercase dot-prefixed suffixes.
- File limit `1..500 MB`.
- Local storage limit `1..500 GB`.
- Poll interval `60..3600 seconds`.
- Folder-selection switch.
- Best-effort local removal switch with a warning that copied files cannot be
  remotely recalled.

Save through:

```typescript
await setSystemSetting(
  'desktop_sync_policy',
  { ...desktopSyncSettings },
  authStore.user?.username || 'admin',
)
```

Never render mock users, projects, or categories.

- [ ] **Step 5: Run the verifier and frontend build**

```powershell
npm run test:desktop-settings
npm run build
```

Expected: both pass.

- [ ] **Step 6: Commit administrator settings**

```powershell
git add scripts/verify-desktop-sync-settings.mjs src/types/index.ts src/views/admin/AdminSystemSettings.vue package.json
git commit -m "feat: configure desktop file synchronization"
```

---

### Task 4: Scaffold The Secure Electron Shell

**Files:**
- Create: `desktop/package.json`
- Create: `desktop/src/config.mjs`
- Create: `desktop/src/security.mjs`
- Create: `desktop/src/main.mjs`
- Create: `desktop/src/preload.mjs`
- Create: `desktop/src/app-protocol.mjs`
- Create: `desktop/ui/connecting.html`
- Create: `desktop/ui/unavailable.html`
- Create: `desktop/ui/incompatible.html`
- Create: `desktop/test/config.test.mjs`
- Create: `desktop/test/security.test.mjs`
- Create: `desktop/test/app-protocol.test.mjs`
- Modify: `package.json`

**Interfaces:**
- Produces: `loadDesktopConfig(env)`.
- Produces: `isAllowedNavigation(target, origin)`.
- Produces: `assertTrustedSender(frameUrl, origin)`.
- Produces: `app://connecting`, `app://unavailable`, and `app://incompatible`.
- Consumes later: Tasks 5, 6, 8, and 9 extend the shell.

- [ ] **Step 1: Add the desktop package with pinned dependencies**

```json
{
  "name": "jiqing-erp-desktop",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "main": "src/main.mjs",
  "scripts": {
    "start": "electron .",
    "test": "node --test test/*.test.mjs",
    "icons": "node scripts/build-icons.mjs",
    "pack:dir": "electron-builder --dir --win",
    "dist:win": "electron-builder --win nsis"
  },
  "devDependencies": {
    "@electron/fuses": "2.1.3",
    "electron": "43.2.0",
    "electron-builder": "26.15.3",
    "png-to-ico": "3.0.1",
    "sharp": "0.34.5"
  }
}
```

Add root scripts:

```json
"desktop:install": "npm --prefix desktop ci",
"desktop:test": "npm --prefix desktop test",
"desktop:start": "npm --prefix desktop start",
"desktop:pack": "npm --prefix desktop run dist:win"
```

- [ ] **Step 2: Write failing config and security tests**

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import { loadDesktopConfig } from '../src/config.mjs'
import { assertTrustedSender, isAllowedNavigation } from '../src/security.mjs'

test('production requires https', () => {
  assert.throws(
    () => loadDesktopConfig({
      DESKTOP_RELEASE_CHANNEL: 'production',
      DESKTOP_SERVER_URL: 'http://121.4.36.112:8088',
    }),
    /HTTPS/,
  )
})

test('internal test permits only its exact configured http origin', () => {
  const config = loadDesktopConfig({
    DESKTOP_RELEASE_CHANNEL: 'internal-test',
    DESKTOP_SERVER_URL: 'http://127.0.0.1:5173',
  })
  assert.equal(config.origin, 'http://127.0.0.1:5173')
  assert.equal(isAllowedNavigation('http://127.0.0.1:5173/#/finance', config.origin), true)
  assert.equal(isAllowedNavigation('https://example.com/', config.origin), false)
})

test('ipc rejects an untrusted sender', () => {
  assert.throws(
    () => assertTrustedSender('https://example.com/', 'https://erp.example.cn'),
    /untrusted ipc sender/,
  )
})
```

- [ ] **Step 3: Run desktop tests and verify failure**

```powershell
npm --prefix desktop install
npm --prefix desktop test
```

Expected: module-not-found failures for `config.mjs` and `security.mjs`.

- [ ] **Step 4: Implement strict environment configuration**

`loadDesktopConfig` must:

- Accept `development`, `internal-test`, or `production`.
- Parse one absolute HTTP(S) URL.
- Require HTTPS for production.
- Strip path, query, and hash to an origin.
- Return `environmentLabel: "内部测试"` for internal-test.
- Return `environmentLabel: ""` for production.
- Use bounded health timeout `8000`.

- [ ] **Step 5: Implement navigation and IPC validation**

```javascript
export function isAllowedNavigation(target, allowedOrigin) {
  try {
    const url = new URL(target)
    return url.origin === allowedOrigin
  } catch {
    return false
  }
}

export function assertTrustedSender(frameUrl, allowedOrigin) {
  if (!isAllowedNavigation(frameUrl, allowedOrigin)) {
    throw new Error('untrusted ipc sender')
  }
}
```

Also reject `javascript:`, `data:`, `file:`, and custom remote schemes.

- [ ] **Step 6: Register safe local fallback pages**

Use a privileged custom `app` scheme registered before ready. Serve only three
known bundled resources; do not map arbitrary paths:

```javascript
const PAGE_MAP = new Map([
  ['connecting', join(uiRoot, 'connecting.html')],
  ['unavailable', join(uiRoot, 'unavailable.html')],
  ['incompatible', join(uiRoot, 'incompatible.html')],
])
```

- [ ] **Step 7: Create BrowserWindow with the required security preferences**

```javascript
const window = new BrowserWindow({
  width: 1440,
  height: 900,
  minWidth: 1100,
  minHeight: 720,
  autoHideMenuBar: true,
  show: false,
  icon: join(app.getAppPath(), 'assets', 'icon.ico'),
  webPreferences: {
    preload: join(import.meta.dirname, 'preload.mjs'),
    nodeIntegration: false,
    contextIsolation: true,
    sandbox: true,
    webSecurity: true,
    allowRunningInsecureContent: false,
  },
})
```

Set:

- `session.setPermissionRequestHandler((_wc, _permission, callback) => callback(false))`
- `will-navigate` origin check.
- `setWindowOpenHandler` returning `{ action: 'deny' }` after opening reviewed
  `https:` external URLs in the system browser.
- Certificate error rejection.
- Single-instance lock and focus behavior.
- Health check before loading remote UI.
- Last valid window bounds stored without credentials.

- [ ] **Step 8: Run shell unit tests**

```powershell
npm --prefix desktop test
```

Expected: all shell tests pass.

- [ ] **Step 9: Commit the secure shell**

```powershell
git add desktop package.json
git commit -m "feat: scaffold secure Electron desktop shell"
```

---

### Task 5: Define A Minimal Versioned Desktop IPC Contract

**Files:**
- Create: `src/types/desktop.d.ts`
- Create: `src/composables/useDesktopClient.ts`
- Create: `scripts/verify-desktop-ipc.mjs`
- Modify: `desktop/src/preload.mjs`
- Modify: `desktop/src/main.mjs`
- Modify: `desktop/src/security.mjs`
- Modify: `package.json`

**Interfaces:**
- Produces: `window.jiqingDesktop`.
- Produces: IPC channels under the `desktop:` prefix only.
- Produces: `DesktopSyncState` and `DesktopSyncStartRequest`.
- Consumes later: Tasks 6 and 7 implement synchronization behind this contract.

- [ ] **Step 1: Write the failing IPC contract verifier**

```javascript
import { readFileSync } from 'node:fs'

const preload = readFileSync('desktop/src/preload.mjs', 'utf8')
const declaration = readFileSync('src/types/desktop.d.ts', 'utf8')

for (const channel of [
  'desktop:get-capabilities',
  'desktop:select-sync-folder',
  'desktop:get-sync-state',
  'desktop:start-sync',
  'desktop:pause-sync',
  'desktop:open-sync-folder',
]) {
  if (!preload.includes(channel)) throw new Error(`Missing IPC channel ${channel}`)
}

if (!declaration.includes('jiqingDesktop: JiqingDesktopBridge')) {
  throw new Error('Window bridge declaration is missing')
}
```

- [ ] **Step 2: Run the verifier and confirm failure**

```powershell
node scripts/verify-desktop-ipc.mjs
```

Expected: failure for the first missing IPC channel.

- [ ] **Step 3: Declare the bridge types**

```typescript
export type DesktopSyncStatus =
  | 'disabled'
  | 'waiting_for_login'
  | 'checking_policy'
  | 'syncing'
  | 'paused'
  | 'completed'
  | 'partial_failure'
  | 'permission_changed'
  | 'offline'

export interface DesktopSyncState {
  status: DesktopSyncStatus
  localRoot: string
  selectedProjectRefs: string[]
  completedFiles: number
  totalFiles: number
  failedFiles: number
  bytesDownloaded: number
  lastSuccessAt: string
  message: string
}

export interface DesktopSyncStartRequest {
  authToken: string
  userId: string
  projectRefs: string[]
}

export interface JiqingDesktopBridge {
  getCapabilities(): Promise<{
    desktop: true
    protocolVersion: 1
    clientVersion: string
    releaseChannel: 'development' | 'internal-test' | 'production'
  }>
  selectSyncFolder(): Promise<string>
  getSyncState(): Promise<DesktopSyncState>
  startSync(request: DesktopSyncStartRequest): Promise<DesktopSyncState>
  pauseSync(): Promise<DesktopSyncState>
  openSyncFolder(): Promise<void>
  onSyncState(listener: (state: DesktopSyncState) => void): () => void
}

declare global {
  interface Window {
    jiqingDesktop?: JiqingDesktopBridge
  }
}
```

- [ ] **Step 4: Expose narrow preload methods**

Use `contextBridge.exposeInMainWorld`. Do not expose `ipcRenderer`, filesystem,
shell, `process`, or a generic send method.

For `onSyncState`, subscribe to one channel and return a cleanup function.

- [ ] **Step 5: Validate every main-process IPC request**

For each `ipcMain.handle`, call:

```javascript
assertTrustedSender(event.senderFrame?.url || '', config.origin)
```

Validate:

- token is a non-empty string no longer than 8192 characters.
- user ID is a non-empty string no longer than 128 characters.
- project refs are unique strings matching `^(project|audit):[A-Za-z0-9-]+$`.
- no more than 500 project refs.

Keep the token in an in-memory sync-session object only.

- [ ] **Step 6: Add the Vue capability composable**

```typescript
import { computed, onMounted, ref } from 'vue'

export function useDesktopClient() {
  const capabilities = ref<Awaited<ReturnType<NonNullable<Window['jiqingDesktop']>['getCapabilities']>> | null>(null)
  const isDesktop = computed(() => capabilities.value?.desktop === true)

  onMounted(async () => {
    capabilities.value = window.jiqingDesktop
      ? await window.jiqingDesktop.getCapabilities()
      : null
  })

  return { capabilities, isDesktop }
}
```

- [ ] **Step 7: Run IPC verifier, desktop tests, and web build**

```powershell
node scripts/verify-desktop-ipc.mjs
npm --prefix desktop test
npm run build
```

Expected: all pass.

- [ ] **Step 8: Commit the IPC contract**

```powershell
git add desktop/src src/types/desktop.d.ts src/composables/useDesktopClient.ts scripts/verify-desktop-ipc.mjs package.json
git commit -m "feat: add versioned desktop bridge"
```

---

### Task 6: Implement The Read-Only Synchronization Engine

**Files:**
- Create: `desktop/src/sync/path-policy.mjs`
- Create: `desktop/src/sync/index-store.mjs`
- Create: `desktop/src/sync/api-client.mjs`
- Create: `desktop/src/sync/sync-engine.mjs`
- Create: `desktop/test/path-policy.test.mjs`
- Create: `desktop/test/index-store.test.mjs`
- Create: `desktop/test/sync-engine.test.mjs`
- Modify: `desktop/src/main.mjs`

**Interfaces:**
- Consumes: Task 2 project roots and manifest.
- Consumes: Task 5 validated in-memory token and selected project refs.
- Produces: `SyncEngine.start`, `SyncEngine.pause`, `SyncEngine.getState`.
- Produces: atomic local index partitioned by environment and user.
- Consumes later: Task 7 displays emitted state.

- [ ] **Step 1: Write failing Windows path-policy tests**

```javascript
test('normalizes unsafe Windows names deterministically', () => {
  assert.equal(safeSegment('合同:最终版?.pdf'), '合同_最终版_.pdf')
  assert.equal(safeSegment('CON'), '_CON')
  assert.equal(safeSegment('项目. '), '项目')
  assert.equal(safeSegment('../合同'), '_合同')
})

test('builds a bounded relative project path', () => {
  const path = buildRelativePath({
    projectCode: '20260727-JQ-001',
    projectName: '区直学校维修',
    categoryName: '合同文件',
    originalName: '施工合同.pdf',
  })
  assert.equal(
    path,
    '20260727-JQ-001_区直学校维修/合同文件/施工合同.pdf',
  )
  assert.ok(path.length < 220)
})
```

- [ ] **Step 2: Write failing synchronization behavior tests**

Use a temporary directory and fake API client:

```javascript
test('downloads a verified file atomically and skips it on rerun', async () => {
  const engine = createTestEngine({
    manifest: [entry('doc-1', Buffer.from('contract'))],
  })
  await engine.start(session())
  assert.equal(readFileSync(engine.output('施工合同.pdf'), 'utf8'), 'contract')
  assert.equal(engine.api.downloadCalls, 1)

  await engine.start(session())
  assert.equal(engine.api.downloadCalls, 1)
})

test('never overwrites a locally modified file', async () => {
  const engine = createTestEngine({
    manifests: [
      [entry('doc-1-v1', Buffer.from('server-v1'))],
      [entry('doc-1-v2', Buffer.from('server-v2'))],
    ],
  })
  await engine.start(session())
  writeFileSync(engine.output('施工合同.pdf'), 'local-change')
  await engine.start(session())
  assert.equal(readFileSync(engine.output('施工合同.pdf'), 'utf8'), 'local-change')
  assert.equal(
    readFileSync(engine.output('施工合同_服务器新版.pdf'), 'utf8'),
    'server-v2',
  )
})

test('hash mismatch leaves no completed file', async () => {
  const engine = createTestEngine({
    manifest: [{ ...entry('doc-1', Buffer.from('expected')), sha256: '0'.repeat(64) }],
  })
  await engine.start(session())
  assert.equal(existsSync(engine.output('施工合同.pdf')), false)
  assert.equal(engine.getState().failedFiles, 1)
})
```

- [ ] **Step 3: Run desktop tests and verify failure**

```powershell
npm --prefix desktop test
```

Expected: module-not-found failures under `desktop/src/sync`.

- [ ] **Step 4: Implement safe path construction**

Rules:

- Replace `< > : " / \ | ? *` and control characters with `_`.
- Prefix Windows reserved names with `_`.
- Strip trailing periods and spaces.
- Collapse repeated `_`.
- Bound each segment to 80 Unicode code points.
- Bound the relative path to 220 code points.
- Reject any resolved path that escapes the selected root.
- Preserve the final file extension where possible.

- [ ] **Step 5: Implement an atomic JSON index**

Store under:

```text
<appData>/sync-index/<sha256(environmentOrigin)>/<userId>.json
```

Shape:

```json
{
  "schemaVersion": 1,
  "environmentOrigin": "https://erp.example.cn",
  "userId": "user-1",
  "cursorBySelection": {},
  "files": {
    "project_file:file-1": {
      "sourceRevision": "file-1:1:1024:2026-07-27T10:00:00",
      "sha256": "hex",
      "relativePath": "project/category/file.pdf",
      "fileSize": 1024,
      "lastVerifiedAt": "2026-07-27T10:05:00",
      "status": "synced"
    }
  }
}
```

Write `<name>.tmp`, `fsync`, then rename. On invalid JSON, rename the corrupt file
to `.corrupt-<timestamp>` and start an empty index. Never delete synchronized
files during index recovery.

- [ ] **Step 6: Implement the authenticated API client**

Methods:

```javascript
getPolicy(token)
getProjectRoots(token)
getManifest(token, { projectRefs, cursor, limit: 200 })
download(token, downloadPath, destinationPartPath, onProgress)
```

Every request:

- Resolves against the configured origin.
- Rejects URLs outside that origin.
- Sends `Authorization: Bearer <token>`.
- Uses an abort timeout.
- Converts `401` to `waiting_for_login`.
- Converts `403` to `permission_changed`.
- Never logs request headers.

- [ ] **Step 7: Implement the synchronization state machine**

State transitions:

```text
waiting_for_login -> checking_policy
checking_policy -> disabled | syncing | permission_changed | offline
syncing -> completed | partial_failure | paused | permission_changed | offline
paused -> checking_policy
```

Process a maximum of two downloads concurrently. Before each page and download:

- Confirm the current run was not paused.
- Re-fetch policy when policy version changes.
- Enforce maximum file and total storage sizes.
- Download to `.jiqing-part-<sourceId>`.
- Verify bytes and SHA-256.
- Atomically rename.
- Mark the final file read-only.
- Emit a serializable state snapshot through `desktop:sync-state`.

- [ ] **Step 8: Implement local modification protection**

When an indexed local file exists:

- Hash it before replacing.
- If its hash differs from the index hash, mark `local_modified`.
- Keep the local file unchanged.
- Download a new server revision with `_服务器新版` before the extension.
- If that suffix exists, append `_2`, `_3`, and so on deterministically.

Missing local files are restored only after the user starts synchronization
again. Local deletes never call a DELETE endpoint.

- [ ] **Step 9: Connect IPC handlers to one SyncEngine instance**

The main process:

- Creates one engine after app ready.
- Passes token and project refs only to `start`.
- Clears token on pause, logout signal, renderer destruction, and app quit.
- Uses `dialog.showOpenDialog({ properties: ['openDirectory', 'createDirectory'] })`.
- Opens only the configured root through `shell.openPath`.
- Emits state only to the trusted main window.

- [ ] **Step 10: Run all desktop sync tests**

```powershell
npm --prefix desktop test
```

Expected: path, index, security, configuration, and synchronization tests pass.

- [ ] **Step 11: Commit the synchronization engine**

```powershell
git add desktop/src/sync desktop/src/main.mjs desktop/test
git commit -m "feat: add read-only desktop file synchronization"
```

---

### Task 7: Add The Material Center Synchronization Experience

**Files:**
- Create: `src/components/desktop/DesktopSyncDialog.vue`
- Create: `src/composables/useDesktopSync.ts`
- Create: `scripts/verify-desktop-sync-ui.mjs`
- Modify: `src/views/admin/AdminFileLibrary.vue`
- Modify: `src/api/system.ts`
- Modify: `package.json`

**Interfaces:**
- Consumes: `window.jiqingDesktop` from Task 5.
- Consumes: Task 6 state snapshots.
- Produces: visible file-center controls only when running in Electron.

- [ ] **Step 1: Write a failing UI contract verifier**

```javascript
import { readFileSync } from 'node:fs'

const library = readFileSync('src/views/admin/AdminFileLibrary.vue', 'utf8')
const dialog = readFileSync('src/components/desktop/DesktopSyncDialog.vue', 'utf8')

for (const marker of ['本地同步', 'DesktopSyncDialog', 'isDesktop']) {
  if (!library.includes(marker)) throw new Error(`Missing file-center marker: ${marker}`)
}

for (const marker of [
  '服务器到本地只读同步',
  '选择本地文件夹',
  '立即同步',
  '暂停同步',
  '打开本地文件夹',
  '本地新增或修改不会自动上传',
]) {
  if (!dialog.includes(marker)) throw new Error(`Missing dialog marker: ${marker}`)
}
```

Add root script:

```json
"test:desktop-sync-ui": "node scripts/verify-desktop-sync-ui.mjs"
```

- [ ] **Step 2: Run the verifier and confirm failure**

```powershell
npm run test:desktop-sync-ui
```

Expected: missing `DesktopSyncDialog.vue`.

- [ ] **Step 3: Implement the sync composable**

The composable:

- Detects `window.jiqingDesktop`.
- Loads capabilities and current state.
- Subscribes once to state updates and unsubscribes on unmount.
- Fetches sync project roots only after an authenticated desktop user opens the
  dialog.
- Calls `getAuthToken()` immediately before `startSync`.
- Passes `authStore.user.id`; does not persist the token.
- Exposes `chooseFolder`, `start`, `pause`, and `openFolder`.

If the web page runs in a normal browser, `isDesktop` is false and no desktop
control renders.

- [ ] **Step 4: Build the dialog UI**

Use one Arco large modal with:

- Status header and environment/client version.
- Policy-disabled empty state.
- Local folder row.
- Searchable project multi-select using real project roots.
- File and byte totals from the server.
- Progress bar and synchronized/failed counts.
- Last successful synchronization time.
- Expandable failed-file list.
- Fixed warning that local changes are not uploaded.
- `选择本地文件夹`, `立即同步`, `暂停同步`, and `打开本地文件夹`.

Disable `立即同步` until the user has a folder, at least one allowed project,
and an authenticated session.

- [ ] **Step 5: Add the Material Center entry point**

In the existing header actions:

```vue
<AButton v-if="isDesktop" variant="outline" @click="syncDialogVisible = true">
  <template #icon><AIcon name="cloud-download" /></template>
  本地同步
</AButton>
```

Keep the existing upload and refresh actions unchanged.

- [ ] **Step 6: Handle logout and permission changes**

When `logoutSession` succeeds, call `window.jiqingDesktop?.pauseSync()` before
clearing the web token. If the renderer receives `permission_changed`, close
project selection, retain the explanatory state, and require a fresh policy
check before another run.

- [ ] **Step 7: Run UI verifier and frontend build**

```powershell
npm run test:desktop-sync-ui
npm run test:desktop-settings
npm run build
```

Expected: all pass.

- [ ] **Step 8: Commit the Material Center experience**

```powershell
git add src/components/desktop src/composables/useDesktopSync.ts src/views/admin/AdminFileLibrary.vue src/api/system.ts scripts/verify-desktop-sync-ui.mjs package.json
git commit -m "feat: add Material Center desktop sync controls"
```

---

### Task 8: Generate Enterprise Icons And Build The Windows Installer

**Files:**
- Create: `desktop/scripts/build-icons.mjs`
- Create: `desktop/scripts/after-pack.mjs`
- Create: `desktop/test/icons.test.mjs`
- Create: `desktop/electron-builder.yml`
- Create: `desktop/assets/.gitkeep`
- Modify: `desktop/package.json`

**Interfaces:**
- Consumes: `public/aoqiang-construction-logo.svg`.
- Produces: `desktop/assets/icon.ico`.
- Produces: installer under `desktop/dist/`.
- Produces: hardened Electron fuses before signing.

- [ ] **Step 1: Write a failing icon test**

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

test('build generates a Windows ICO from the enterprise SVG', () => {
  assert.equal(existsSync(new URL('../assets/icon.ico', import.meta.url)), true)
  const ico = readFileSync(new URL('../assets/icon.ico', import.meta.url))
  assert.equal(ico[0], 0)
  assert.equal(ico[1], 0)
  assert.equal(ico[2], 1)
  assert.equal(ico[3], 0)
  assert.ok(ico.length > 1024)
})
```

- [ ] **Step 2: Run the icon test and verify failure**

```powershell
npm --prefix desktop test
```

Expected: icon test fails because `desktop/assets/icon.ico` does not exist.

- [ ] **Step 3: Implement icon generation**

The script:

1. Reads `../public/aoqiang-construction-logo.svg`.
2. Uses Sharp to trim transparent padding.
3. Places the trimmed logo with `contain` inside a transparent square.
4. Generates PNG sizes `16, 24, 32, 48, 64, 128, 256`.
5. Uses png-to-ico to create `desktop/assets/icon.ico`.
6. Writes `desktop/assets/splash-logo.png` at 512 px.

Do not recolor or distort the logo. Keep generated PNG files under
`desktop/assets/generated/`.

- [ ] **Step 4: Configure electron-builder**

```yaml
appId: cn.jiqing.erp.desktop
productName: 集庆工程管理
asar: true
files:
  - src/**/*
  - ui/**/*
  - assets/**/*
directories:
  output: dist
win:
  target:
    - target: nsis
      arch:
        - x64
  icon: assets/icon.ico
  artifactName: JiqingERP-${version}-${arch}-Setup.${ext}
nsis:
  oneClick: false
  perMachine: false
  allowToChangeInstallationDirectory: true
  createDesktopShortcut: true
  createStartMenuShortcut: true
  runAfterFinish: true
  deleteAppDataOnUninstall: false
afterPack: scripts/after-pack.mjs
```

- [ ] **Step 5: Harden packaged Electron fuses**

Use `@electron/fuses` in the `afterPack` hook:

```javascript
await flipFuses(executablePath, {
  version: FuseVersion.V1,
  strictlyRequireAllFuses: true,
  [FuseV1Options.RunAsNode]: false,
  [FuseV1Options.EnableCookieEncryption]: true,
  [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
  [FuseV1Options.EnableNodeCliInspectArguments]: false,
  [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
  [FuseV1Options.OnlyLoadAppFromAsar]: true,
})
```

- [ ] **Step 6: Generate icons and run tests**

```powershell
npm --prefix desktop run icons
npm --prefix desktop test
```

Expected: all icon and desktop tests pass.

- [ ] **Step 7: Build an unpacked application**

```powershell
$env:DESKTOP_RELEASE_CHANNEL='internal-test'
$env:DESKTOP_SERVER_URL='http://127.0.0.1:5173'
npm --prefix desktop run pack:dir
```

Expected: `desktop/dist/win-unpacked/JiqingERP.exe` exists.

- [ ] **Step 8: Build the NSIS installer**

```powershell
$env:DESKTOP_RELEASE_CHANNEL='internal-test'
$env:DESKTOP_SERVER_URL='http://127.0.0.1:5173'
npm --prefix desktop run dist:win
```

Expected: `desktop/dist/JiqingERP-1.0.0-x64-Setup.exe` exists.

- [ ] **Step 9: Commit packaging**

Do not commit `desktop/dist/` or installed dependencies.

```powershell
git add desktop/package.json desktop/package-lock.json desktop/scripts desktop/test/icons.test.mjs desktop/electron-builder.yml desktop/assets .gitignore
git commit -m "build: package Windows desktop client"
```

---

### Task 9: Add End-To-End Smoke Tests, Release Workflow, And Operating Guide

**Files:**
- Create: `desktop/test/smoke-app.mjs`
- Create: `desktop/scripts/smoke-runner.mjs`
- Create: `.github/workflows/windows-desktop.yml`
- Create: `docs/desktop-client-runbook.md`
- Modify: `desktop/src/main.mjs`
- Modify: `desktop/package.json`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: repeatable local acceptance.
- Produces: internal-test installer artifact.
- Produces: production package gate requiring HTTPS and signing credentials.

- [ ] **Step 1: Write the smoke runner**

Start a local Node HTTP server that serves:

- `/api/health`
- `/api/desktop/bootstrap`
- a login-like HTML page at `/`

Launch the unpacked Electron app with:

```text
DESKTOP_RELEASE_CHANNEL=internal-test
DESKTOP_SERVER_URL=http://127.0.0.1:<random-port>
DESKTOP_SMOKE_RESULT=<temporary-json-path>
```

In smoke mode the main process records:

```json
{
  "healthReady": true,
  "remoteLoaded": true,
  "nodeIntegration": false,
  "contextIsolation": true,
  "sandbox": true,
  "loadedOrigin": "http://127.0.0.1:<port>"
}
```

Then it exits. The runner asserts every value and removes the temporary result.

- [ ] **Step 2: Add failure-path smoke cases**

Cover:

- Server unavailable loads `app://unavailable`.
- External navigation is denied.
- Production HTTP configuration exits with a configuration error.
- A second instance exits and focuses the first.

- [ ] **Step 3: Add desktop scripts**

```json
"smoke": "node scripts/smoke-runner.mjs",
"verify": "npm run test && npm run icons && npm run pack:dir && npm run smoke"
```

- [ ] **Step 4: Run the complete local verification**

```powershell
python -m unittest discover -s server/tests -v
npm ci
npm run test:premium-theme
npm run test:desktop-settings
npm run test:desktop-sync-ui
npm run build
npm --prefix desktop ci
npm --prefix desktop run verify
```

Expected: backend tests, frontend verification, Vue build, desktop unit tests,
icon generation, unpacked packaging, and Electron smoke tests all pass.

- [ ] **Step 5: Add the Windows build workflow**

Use `windows-latest` and Node LTS. Steps:

1. Checkout.
2. Install root dependencies with `npm ci`.
3. Install desktop dependencies with `npm --prefix desktop ci`.
4. Run backend and frontend verification.
5. Run desktop verification.
6. Build `internal-test` from repository variable `DESKTOP_TEST_URL`.
7. Upload the NSIS installer artifact.

For a production tag:

- Read origin from repository variable `DESKTOP_PRODUCTION_URL`.
- Require it to start with `https://`.
- Require `WINDOWS_CERTIFICATE_BASE64` and `WINDOWS_CERTIFICATE_PASSWORD`.
- Decode the certificate only into the runner temporary directory.
- Set `CSC_LINK` and `CSC_KEY_PASSWORD`.
- Build and upload the signed installer.
- Delete the decoded certificate in an `always()` step.

The workflow must fail rather than emit an unsigned production artifact.

- [ ] **Step 6: Write the operating guide**

Document exact procedures for:

- Local development.
- Internal-test packaging.
- Production prerequisites.
- Setting repository variables and secrets without recording their values.
- Enabling synchronization for one acceptance user.
- Reading sanitized desktop diagnostics.
- Rolling back to the previous installer.
- Pausing synchronization centrally.
- Uninstall behavior and retained synchronized files.
- Verifying server health and HTTPS.

State explicitly that the current plain-HTTP server can support only an
internal-test build and cannot satisfy the production release gate.

- [ ] **Step 7: Perform a clean installer acceptance**

On a Windows acceptance account:

1. Install without administrator rights.
2. Confirm Start menu, desktop, and taskbar icons.
3. Launch and log in.
4. Confirm normal browser use is unchanged.
5. Enable one real authorized project for read-only synchronization.
6. Download files and compare byte count and SHA-256 with the server manifest.
7. Modify a local test copy and confirm it is not overwritten.
8. Confirm local delete does not remove server content.
9. Revoke policy and confirm subsequent sync stops.
10. Uninstall and confirm synchronized files are retained with a clear notice.

Do not use fabricated business records. Use an explicitly authorized existing
project or a non-business technical fixture in a non-production database.

- [ ] **Step 8: Commit release automation and documentation**

```powershell
git add desktop/test/smoke-app.mjs desktop/scripts/smoke-runner.mjs desktop/src/main.mjs desktop/package.json .github/workflows/windows-desktop.yml docs/desktop-client-runbook.md
git commit -m "test: verify Windows desktop release"
```

---

## Final Verification Gate

Run from a clean checkout:

```powershell
python -m unittest discover -s server/tests -v
npm ci
npm run test:premium-theme
npm run test:desktop-settings
npm run test:desktop-sync-ui
npm run build
npm --prefix desktop ci
npm --prefix desktop run verify
git status --short
```

Required result:

- All backend tests pass.
- Frontend contract verifiers pass.
- Vue production build passes.
- All desktop unit and smoke tests pass.
- The unpacked EXE and internal-test NSIS installer are created.
- `git status --short` is empty.
- No credentials, tokens, synchronized files, installer outputs, or certificate
  files are tracked.

Production release additionally requires:

- A valid HTTPS production origin.
- A valid Windows code-signing certificate available only through CI secrets.
- A signed installer that passes Windows signature inspection.
- Logged-in acceptance of login, download, preview, print, synchronization,
  permission revocation, and server-side UI update without reinstall.

## Primary References

- Electron security checklist: https://www.electronjs.org/docs/latest/tutorial/security
- Electron context isolation: https://www.electronjs.org/docs/latest/tutorial/context-isolation
- Electron process sandboxing: https://www.electronjs.org/docs/latest/tutorial/sandbox
- Electron package: https://www.npmjs.com/package/electron
- electron-builder package: https://www.npmjs.com/package/electron-builder
- Electron fuses package: https://www.npmjs.com/package/@electron/fuses

