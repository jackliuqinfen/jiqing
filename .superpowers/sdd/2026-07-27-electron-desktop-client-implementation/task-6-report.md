# Task 6 Implementation Report

## Status

`DONE_WITH_CONCERNS`

The read-only Electron synchronization engine is implemented, integrated with
the existing trusted IPC bridge, covered by TDD, and committed with the required
message. No Task 7 renderer UI was implemented.

## Commit

- `feat: add read-only desktop file synchronization`
- This report is included in that task commit. The exact SHA is reported by the
  task response after Git creates the commit.

## Delivered

- Added deterministic Windows-safe path construction with 80-code-point segment
  bounds, a 220-code-point relative-path bound, reserved-name handling, extension
  preservation, root-containment checks, and bounded server-conflict filenames.
- Added an atomic JSON synchronization index partitioned by SHA-256 of the
  environment origin and by bounded user identity. Writes use a synced `.tmp`
  file followed by rename. Invalid JSON or ownership/schema data is quarantined
  as `.corrupt-<timestamp>` without touching visible synchronized files.
- Added an authenticated same-origin API client for policy, project roots,
  manifest pagination, and downloads. It rejects cross-origin and credentialed
  URLs, rejects redirects, sends bearer authentication on every request, covers
  response bodies with an abort timeout, and maps `401`/`403` to the required
  synchronization states.
- Added the `SyncEngine` state machine with a maximum of two concurrent
  downloads, policy-version rechecks, file and local-storage limits, atomic part
  publication, byte-count and SHA-256 verification, read-only completed files,
  progress snapshots, pause/run-generation guards, and per-selection resume
  cursors.
- Added local-modification protection. An indexed file is hashed before
  replacement; changed local content is retained while the server revision is
  written as `_服务器新版`, `_服务器新版_2`, and so on.
- Added later-run restoration for indexed missing files. No watcher or automatic
  repair runs; restoration occurs only after a later explicit start.
- Integrated one engine through the Task 5 controller and existing six-request,
  one-event IPC surface. Async state is resolved before emission.
- Created the engine only after Electron is ready. Tokens remain memory-only and
  are cleared on completion, pause, logout signal, renderer destruction, window
  close, application exit, and replacement by another explicit run.
- Kept `sandbox: true` and `desktop/src/preload.cjs` unchanged.
- Added no production dependency, upload path, delete path, local watcher,
  simulated project, simulated file, or fabricated success state.

## TDD Evidence

### Red

1. Path/index red:

   ```text
   npm.cmd test -- --test-name-pattern="normalizes unsafe|partitions and atomically"
   tests 43, pass 41, fail 2
   ERR_MODULE_NOT_FOUND: desktop/src/sync/index-store.mjs
   ERR_MODULE_NOT_FOUND: desktop/src/sync/path-policy.mjs
   ```

2. API/engine red:

   ```text
   node --test test/api-client.test.mjs test/sync-engine.test.mjs
   tests 2, pass 0, fail 2
   ERR_MODULE_NOT_FOUND: desktop/src/sync/api-client.mjs
   ```

3. IPC integration red:

   ```text
   node --test test/ipc-contract.test.mjs test/main-ipc-wiring.test.mjs
   tests 15, pass 12, fail 3
   ```

   The failures proved that the placeholder controller did not delegate, async
   state emitted a `Promise`, and `main.mjs` did not create a real engine.

4. Security/progress hardening red:

   ```text
   node --test test/api-client.test.mjs test/sync-engine.test.mjs
   tests 21, pass 17, fail 4
   ```

   The failures covered credentialed URLs, stalled response bodies,
   in-progress byte emission, and stale policy-version rechecks.

5. Windows index filename red:

   ```text
   node --test test/index-store.test.mjs
   tests 5, pass 4, fail 1
   ENOENT for an overlong encoded user filename
   ```

6. Final path hardening red:

   ```text
   node --test test/path-policy.test.mjs test/sync-engine.test.mjs
   tests 18, pass 16, fail 2
   ```

   The failures covered reserved names with a space before the extension and an
   overlong `_服务器新版` conflict filename.

### Green

Focused green runs:

```text
node --test test/path-policy.test.mjs test/index-store.test.mjs
tests 8, pass 8, fail 0

node --test test/api-client.test.mjs test/sync-engine.test.mjs
tests 21, pass 21, fail 0

node --test test/ipc-contract.test.mjs test/main-ipc-wiring.test.mjs
tests 15, pass 15, fail 0

node --test test/path-policy.test.mjs test/sync-engine.test.mjs
tests 18, pass 18, fail 0
```

Final required desktop command:

```text
npm.cmd test
tests 74, pass 74, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 798.6575
```

Additional verification:

```text
node --check src/sync/api-client.mjs
node --check src/sync/index-store.mjs
node --check src/sync/path-policy.mjs
node --check src/sync/sync-engine.mjs
all exited 0

node scripts/verify-desktop-ipc.mjs
Desktop IPC contract verified

git diff --check
exit 0, no errors
```

## Changed Files

- `.superpowers/sdd/2026-07-27-electron-desktop-client-implementation/task-6-report.md`
- `desktop/src/ipc-contract.mjs`
- `desktop/src/main.mjs`
- `desktop/src/sync/api-client.mjs`
- `desktop/src/sync/index-store.mjs`
- `desktop/src/sync/path-policy.mjs`
- `desktop/src/sync/sync-engine.mjs`
- `desktop/test/api-client.test.mjs`
- `desktop/test/index-store.test.mjs`
- `desktop/test/ipc-contract.test.mjs`
- `desktop/test/main-ipc-wiring.test.mjs`
- `desktop/test/path-policy.test.mjs`
- `desktop/test/sync-engine.test.mjs`

## Self-Review

- Authentication: bearer tokens are passed only as method arguments or held in
  the active engine field; they are not serialized, persisted, emitted, or
  logged. Every lifecycle clearing path aborts active API operations.
- Authorization/origin: every policy, roots, manifest, and download request is
  exact-origin and authenticated. Manifest download paths cannot redirect or
  supply credentials. Permission changes fail closed.
- Read-only direction: the client contains no upload, `DELETE`, rename-on-server,
  or server mutation operation. Local edits, deletes, and renames never create a
  server call.
- File integrity: publication follows part download, byte-count verification,
  SHA-256 verification, active-run confirmation, atomic rename, and read-only
  marking. Failed or paused transfers remove their part file.
- Local safety: indexed files are re-hashed before replacement. Unindexed or
  locally changed targets are never overwritten. Every derived/indexed path is
  containment-checked against the selected root.
- Pagination/recovery: every successful page is indexed atomically; the terminal
  `hasMore:false` resume cursor is persisted per sorted selected scope. Failed
  records retain authorized download metadata for a later explicit retry.
- Concurrency/quota: the two workers share synchronous byte reservations, so
  concurrent starts cannot exceed the configured local-storage limit.
- IPC: the renderer API remains unchanged, trusted-sender checks remain in front
  of every operation, state emissions target only the trusted main window, and
  no token is present in the public state.
- Scope: no Task 7 Vue component, dialog, polling UI, or background automatic
  synchronization was added.

## Concerns

- Verification used Node tests, temporary NTFS directories, complete fake API
  responses, and the repository IPC artifact verifier. It did not run an
  authenticated end-to-end synchronization against a live central server.
- A packaged Electron window was not launched for manual acceptance of native
  dialog behavior, NTFS read-only behavior in common Office/PDF applications, or
  renderer-destruction timing.
- Task 7 still needs to present these emitted states and user-start controls.
