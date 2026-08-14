# Electron Desktop Client Design

> Status: approved for implementation planning
>
> Date: 2026-07-27
>
> Scope: Windows desktop client, central-server access, optional read-only local file synchronization

## 1. Decision Summary

The Windows application will use Electron as a secure desktop shell for the
existing engineering ERP.

The first release has two responsibilities:

1. Load the current production web application from the central server.
2. Optionally mirror authorized Material Center files to a user-selected local
   folder in read-only synchronization mode.

The server remains the only authoritative source for projects, contracts,
documents, permissions, OCR results, lifecycle state, and audit logs.

The desktop client must not bundle or create a second business database,
Python API service, OCR worker, or independent upload repository.

## 2. Goals

- Provide a familiar Windows application entry point for employees.
- Allow web UI releases to appear without reinstalling the desktop client.
- Preserve the central ERP as the single source of truth.
- Support existing login, upload, download, preview, and printing workflows.
- Allow administrators to enable or disable local file synchronization.
- Allow authorized users to select projects for local read-only mirroring.
- Make synchronization status and errors understandable to non-technical users.
- Use the existing enterprise SVG logo as the sole brand source for application
  and installer icons.
- Produce an installer that works on supported Windows devices without requiring
  local database or backend setup.

## 3. Non-Goals For The First Release

- Offline business data editing.
- Local lifecycle, contract, audit, or settlement processing.
- Automatic upload of files added or changed in the local synchronization folder.
- Propagation of local deletion or rename operations to the server.
- File locking or collaborative document editing.
- Windows Explorer virtual-drive or placeholder-file integration.
- Background OCR on employee devices.
- Automatic conflict merging.
- A separate desktop-only ERP interface.
- Guaranteed remote deletion of files that a user has copied outside the managed
  synchronization folder.

## 4. Architecture

```text
Windows EXE
├─ Electron main process
│  ├─ secure BrowserWindow
│  ├─ navigation and download policy
│  ├─ connectivity and health checks
│  ├─ optional read-only synchronization service
│  └─ local operational logs and synchronization index
├─ minimal preload bridge
│  └─ exposes client version and approved desktop actions only
├─ bundled local fallback pages
│  ├─ connecting
│  ├─ server unavailable
│  └─ incompatible client
└─ central HTTPS ERP
   ├─ current Vue application
   ├─ authenticated API
   ├─ central database
   ├─ document storage
   └─ OCR services
```

The normal application view loads the central web application. Bundled HTML is
used only before connection succeeds or when the server cannot be reached.

### 4.1 Repository Boundary

Desktop-specific code should live under a new top-level `desktop/` directory.
It must not be mixed into lifecycle, audit, settlement, or OCR domain modules.

The web application remains buildable and deployable without Electron.

The desktop package may depend on the web server, but the web server must not
depend on Electron.

## 5. Environment And Endpoint Configuration

The packaged client supports explicit environment profiles:

| Profile | Purpose | Endpoint rule |
| --- | --- | --- |
| development | Local engineering | Configurable localhost URL |
| internal-test | Controlled employee acceptance | Explicit test server URL |
| production | Formal use | HTTPS URL only |

Production builds must reject plain HTTP origins. An internal-test build may
temporarily allow a specifically configured HTTP origin, but it must display
an environment label and must never be distributed as the production build.

The production origin is compiled into the signed desktop release. It must not
be freely editable through an unprotected text field.

At startup the client calls the existing health endpoint before loading the
remote application. A successful TCP connection without a valid ERP health
response is not considered ready.

## 6. Desktop Window Experience

### 6.1 Startup States

1. Display the enterprise logo and `正在连接工程管理系统`.
2. Call the server health endpoint with a bounded timeout.
3. Load the login page or last authorized route when healthy.
4. Display the local server-unavailable page when the health check fails.

The unavailable page shows:

- A plain-language status.
- The target environment name, not credentials or tokens.
- `重新连接`.
- `打开网络诊断`.
- Client version.
- A support-facing error code.

### 6.2 Window Rules

- Single application instance.
- Restore the last valid window size and position.
- Enforce a minimum usable window size.
- Use the standard Windows minimize, maximize, restore, and close behavior.
- Hide the default Electron application menu.
- Do not add a system tray process in the first release.
- Closing the main window exits the client and synchronization process.
- External links open in the operating system browser.
- Internal allowlisted links remain in the application.
- Popup windows are blocked unless a specific ERP workflow has been reviewed
  and allowlisted.

### 6.3 Login And Logout

The existing server authentication remains authoritative.

The desktop client does not receive user passwords through IPC. Login happens
inside the sandboxed web application.

On logout, the web session is invalidated through the existing server endpoint
and desktop-scoped session data is cleared. Synchronization stops immediately.

## 7. Read-Only Local File Synchronization

### 7.1 Product Meaning

Synchronization is an authorized local mirror of Material Center files. It is
not a second document repository and not a local editing channel.

```text
Central Material Center
        |
        | authenticated download and incremental manifest
        v
Electron synchronization service
        |
        v
User-selected local folder
```

The direction in release one is server to local only.

Users continue to upload new files and new versions through the ERP upload
workflow. This preserves classification, version history, permissions, file
size validation, and operation logs.

### 7.2 Administrator Policy

An administrator can configure:

- Whether desktop synchronization is available.
- Whether it is enabled by default.
- Allowed roles and individual users.
- Allowed synchronization project references or project data scopes.
- Allowed document categories.
- Allowed file types.
- Maximum synchronized file size.
- Maximum total local storage.
- Whether synchronization is allowed outside the company network.
- Whether users may select their own local folder.
- Whether users may select projects or must follow an assigned project set.
- Polling interval within approved bounds.
- Whether local copies should be removed on logout or permission revocation.

The default policy is synchronization disabled.

Changing policy on the server must take effect at the next policy refresh.
Every synchronization cycle revalidates the current policy and user scope.

Local removal after revocation is best effort. The system must not claim that
it can erase files the user copied to an unmanaged location.

### 7.3 User Settings

When allowed by policy, the user can:

- Enable or disable synchronization.
- Select the local root folder.
- Select authorized projects for synchronization.
- Start, pause, or resume synchronization.
- View current status, progress, last successful time, and storage usage.
- Retry failed files.
- Open the synchronized folder.

The settings page must explain that local edits are not uploaded automatically.

### 7.4 Folder Structure

The default folder name is `集庆工程资料`.

```text
集庆工程资料/
└─ <项目编号>_<项目名称>/
   ├─ 01_合同文件/
   ├─ 02_施工资料/
   ├─ 03_竣工验收/
   ├─ 04_一审资料/
   ├─ 05_二审资料/
   ├─ 06_定案归档/
   └─ 99_其他资料/
```

Actual category folders come from the server document-category configuration.
The client must not infer project lifecycle rules from folder names.

Unsafe Windows filename characters are replaced deterministically. Reserved
names, trailing spaces, trailing periods, path traversal segments, and excessive
path length must be rejected or normalized before filesystem writes.

The visible filename includes the server filename. Version identity is kept in
the local synchronization index rather than appended to every filename unless
two server files would otherwise map to the same local path.

### 7.5 Required Server APIs

The implementation adds authenticated desktop endpoints with the same permission
model as Material Center:

#### `GET /api/desktop/policy`

Returns the effective policy for the current user, including:

- `enabled`
- `allowFolderSelection`
- `projectSelectionMode`
- `allowedProjectIds`
- `allowedCategoryIds`
- `allowedExtensions`
- `maxFileSizeBytes`
- `maxLocalStorageBytes`
- `networkPolicy`
- `pollIntervalSeconds`
- `removeLocalFilesOnRevocation`
- `policyVersion`

#### `GET /api/desktop/sync/projects`

Returns the synchronization roots visible to the current user:

- `projectRef`
- canonical project-record ID when available
- audit-project ID when the record has not yet been linked
- project code and name
- available file count
- available byte count

`projectRef` is an opaque stable value. When an audit project is linked to a
project record, its audit attachments and project files use the same project
root. An unlinked historical audit project remains a separate synchronization
root and must not be silently attached to a similarly named project.

#### `GET /api/desktop/sync/manifest`

Query parameters:

- `cursor`
- `projectRefs`
- `limit`

Returns only files the current user can read:

- stable source type and source ID
- stable source revision
- project ID, code, and name
- category ID and name
- original filename
- MIME type
- byte size
- content hash
- uploaded timestamp
- version number
- download URL or download resource ID
- next cursor
- current policy version

The first-release manifest adapts the same file sources used by Material Center:

- `project_files`
- `audit_project_attachments`

New document-repository sources can be added to the adapter when they are
visible in Material Center. The desktop client must not invent a third,
independent definition of which files belong to Material Center.

Legacy source rows without a stored content hash are hashed through a server-side
cache keyed by source type, source ID, and immutable revision fingerprint.

The cursor is opaque. Ordering must be stable. Pagination must not skip items
when files are added during a synchronization run.

#### Existing authenticated download route

The synchronization service reuses the server's authorized version-download
behavior. It must not read files directly from server filesystem paths or expose
storage paths to the client.

Every download rechecks permission. A manifest entry is not a permanent
authorization grant.

### 7.6 Local Synchronization Index

The local index is operational metadata, not business data. It records:

- user ID
- server environment ID
- project reference
- source type
- source ID
- source revision
- content hash
- local relative path
- byte size
- last verified timestamp
- synchronization status
- last error code

The index is stored under the Electron application data directory, not inside
the visible synchronized project folders.

Index writes must be atomic. Corruption must cause a safe rescan, never deletion
of remote or local files.

The index must be partitioned by server environment and user identity so that
one user's authorization state cannot be reused by another.

### 7.7 Synchronization Algorithm

1. Verify an authenticated web session is available.
2. Fetch the effective desktop policy.
3. Stop if synchronization is disabled or the user is not authorized.
4. Validate the selected local root and available disk space.
5. Request an incremental manifest for selected authorized projects.
6. Compare stable version ID and content hash with the local index.
7. Download missing or changed versions to a temporary file.
8. Enforce size limits while streaming.
9. Verify byte count and content hash.
10. Atomically move the verified temporary file to its final path.
11. Update the local index.
12. Continue from the server cursor until complete.
13. Report counts for synchronized, skipped, failed, and policy-blocked files.

Downloads use bounded concurrency and resumable range requests only if the
server download route supports them. Otherwise interrupted temporary files are
discarded and retried.

### 7.8 Local Change Behavior

The first release does not watch the local folder for upload.

- A locally edited mirrored file remains local and is marked `本地已修改`.
- The application does not overwrite a locally modified file silently.
- When a newer server version exists, it is downloaded as a separate file with
  a clear `服务器新版` suffix.
- Local rename does not rename the server file.
- Local deletion does not delete or archive the server file.
- A missing local file may be restored from the server after user confirmation.
- New local files are ignored by synchronization and can be uploaded manually
  through the ERP.

This behavior prevents accidental data loss while keeping the server record
authoritative.

### 7.9 Synchronization Status

User-facing states:

- 未启用
- 等待登录
- 正在检查权限
- 同步中
- 已暂停
- 已完成
- 本地文件已修改
- 存储空间不足
- 权限已变更
- 网络不可用
- 部分文件失败

Errors must identify the affected project and filename when authorized, but must
not expose server paths, tokens, or stack traces.

## 8. Security

Electron settings:

- `nodeIntegration: false`
- `contextIsolation: true`
- `sandbox: true`
- `webSecurity: true`
- no remote module
- minimal, typed preload bridge
- strict production-origin allowlist
- explicit permission-request denial unless reviewed
- popup and navigation interception
- external URLs opened in the system browser

Production requirements:

- HTTPS is mandatory.
- Certificates must be valid; certificate errors are not bypassed.
- Release artifacts should be code signed before organization-wide rollout.
- Authentication tokens must not be written to logs or synchronization metadata.
- Temporary downloads use restrictive local paths and are removed after failure.
- Synchronization authorization is evaluated server-side.
- Local files inherit the Windows user's filesystem access; the application
  must not advertise this as digital-rights management.

## 9. Brand And Icon Pipeline

The current enterprise SVG asset is the design source. No alternate icon artwork
is introduced for the first release.

The build pipeline generates:

- Windows multi-resolution `.ico`: 16, 24, 32, 48, 64, 128, and 256 pixels.
- Installer icon.
- Uninstaller icon.
- Application window icon.
- Shortcut icon.
- High-resolution PNG assets for splash and installer UI.

The SVG aspect ratio must be preserved. Transparent padding may be normalized so
the logo appears optically centered at small sizes, but logo geometry and brand
colors must not be redrawn without brand-owner approval.

Proposed product name: `集庆工程管理`.

Proposed executable name: `JiqingERP.exe`.

## 10. Packaging And Updating

The implementation uses Electron with `electron-builder` and an NSIS installer.

First-release installer behavior:

- Per-user installation by default.
- No administrator permission required for normal installation.
- Desktop shortcut enabled by default.
- Start menu shortcut enabled.
- Launch-after-install option enabled.
- No automatic start with Windows by default.
- Clean uninstall of application binaries and settings.
- Synchronized business files are not silently deleted during uninstall.

The remote web UI updates independently from the desktop shell.

The first release uses controlled manual desktop client updates. Automatic client
updates are deferred until a signed artifact feed and rollback procedure exist.

The client checks a server-provided minimum desktop version. When the installed
shell is incompatible, it shows a local upgrade-required page instead of loading
an unsafe or broken workflow.

## 11. Logging And Support

Local logs contain:

- client version
- environment identifier
- startup and health-check status
- synchronization counts
- stable error codes
- policy version
- durations without document contents

Local logs must not contain:

- passwords
- bearer tokens
- cookies
- contract text
- OCR output
- personal phone numbers or email addresses
- raw server filesystem paths

Users can export a sanitized diagnostic package from the error page or desktop
settings. Export requires explicit user action.

## 12. Acceptance Criteria

### 12.1 Desktop Shell

- Installs and launches on supported Windows 10 and Windows 11 devices.
- Opens the central ERP login page.
- Existing login and logout behavior works.
- Existing upload, download, preview, and print workflows remain functional.
- A server-side web deployment is visible after reload without reinstalling the
  client.
- Unknown origins cannot navigate inside the application.
- External links open in the default browser.
- A server outage produces the bundled retry page.
- A second launch focuses the existing application instance.

### 12.2 Security

- Production builds reject HTTP server origins.
- Node APIs are unavailable to remote web content.
- Certificate errors are not bypassed.
- Navigation, popup, and permission-request tests pass.
- Logs and synchronization metadata contain no credentials or document content.

### 12.3 File Synchronization

- Synchronization is disabled by default.
- An administrator can enable it for a permitted test user.
- An unauthorized user cannot retrieve a manifest or download a file.
- A permitted user can select an authorized project and local folder.
- Existing remote files download to deterministic project/category folders.
- Re-running synchronization skips unchanged versions.
- Interrupted downloads never appear as completed files.
- Hash mismatches are rejected and reported.
- Local edits are not overwritten silently.
- Local deletion does not delete the server document.
- New local files are not uploaded automatically.
- Permission revocation stops subsequent synchronization.
- Storage and file-size limits produce clear user-facing errors.

### 12.4 Brand

- Installer, application window, Start menu, taskbar, and desktop shortcut use
  icons generated from the enterprise SVG.
- Icons remain clear at standard Windows scale factors.
- The logo is optically centered without changing its geometry or brand colors.

## 13. Rollout

### Phase 1: Engineering Validation

- Local development profile.
- Desktop security tests.
- Server policy and manifest API tests.
- Synchronization against non-production document fixtures.

### Phase 2: Internal Acceptance

- Signed or explicitly test-labeled internal package.
- Small authorized user group.
- Read-only synchronization disabled by default and enabled per user.
- Validate large files, long Chinese filenames, network interruption, and
  permission revocation.

### Phase 3: Formal Rollout

- Production HTTPS endpoint.
- Code-signed installer.
- Documented client version and rollback package.
- Administrator operating guide.
- User guide for read-only synchronization and manual upload.
- Production health, login, upload, download, and synchronization acceptance.

## 14. Deferred Evolution

Two-way synchronization is a separate future project. It requires:

- local filesystem watcher
- upload queue and retry semantics
- server-side idempotency keys
- rename and delete contracts
- conflict resolution UX
- server recycle bin
- malware scanning
- file-lock or optimistic concurrency rules
- stronger endpoint and device policy
- expanded audit logs

It must not be enabled by changing a feature flag on the first-release
read-only implementation. It requires a separate design and acceptance gate.
