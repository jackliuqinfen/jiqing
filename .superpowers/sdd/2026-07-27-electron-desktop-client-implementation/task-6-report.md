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

---

# Fix Round 1/5

## Status

`DONE_WITH_CONCERNS`

All independent review findings were addressed without changing the six-method
renderer API, `sandbox: true`, `desktop/src/preload.cjs`, or Task 7 UI.

## TDD Evidence

### Red

The first focused regression run covered cancellation/replacement, part/final
path collisions, trusted-baseline preservation, quota recounting, and read-only
publication:

```text
node --test test/sync-engine.test.mjs
tests 21, pass 14, fail 7
```

The combined review regression run additionally covered authoritative identity,
Windows-safe index partitions, junction containment, conflict path bounds,
progress-aware timeouts, bounded redirects, initial-emission cleanup, and
manifest pagination validation:

```text
node --test test/api-client.test.mjs test/index-store.test.mjs test/path-policy.test.mjs test/sync-engine.test.mjs
tests 45, pass 28, fail 17
```

An explicit post-index-commit cancellation test was then added and observed
failing before persisted rollback was implemented:

```text
node --test --test-name-pattern="pause after an awaited index commit" test/sync-engine.test.mjs
tests 1, pass 0, fail 1
actual persisted files contained project_file:doc-1; expected {}
```

A malformed manifest item with a non-SHA-256 digest was also observed reaching
the download before item validation was tightened:

```text
node --test --test-name-pattern="fails closed on malformed manifest page shapes" test/sync-engine.test.mjs
tests 1, pass 0, fail 1
downloadCalls was 1; expected 0
```

### Green

Focused review suite:

```text
node --test test/api-client.test.mjs test/index-store.test.mjs test/path-policy.test.mjs test/sync-engine.test.mjs
tests 52, pass 52, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 1035.233
```

Full desktop suite:

```text
npm.cmd --prefix desktop test
tests 96, pass 96, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 1390.2288
```

Final static and contract verification:

```text
node --check desktop/src/sync/api-client.mjs
node --check desktop/src/sync/index-store.mjs
node --check desktop/src/sync/path-policy.mjs
node --check desktop/src/sync/sync-engine.mjs
node scripts/verify-desktop-ipc.mjs
git diff --check
all exited 0; Desktop IPC contract verified; no diff errors
```

## Fixes Delivered

- Bound each run to `GET /api/auth/me` and `data.id`; missing, inactive, or
  renderer-mismatched identities fail closed as `permission_changed`.
- Partitioned indexes by a full SHA-256 user hash and switched atomic writes to
  unique temporary files with a cancellation check immediately before commit.
- Serialized runs and publication/index mutation per authoritative user and
  physical root. Replaced runs cannot publish or advance cursors after
  cancellation; persisted state is rolled back if cancellation is observed
  after an awaited index commit.
- Added unique UUID part files, serialized final-path allocation, and indexed
  physical-file history so sanitized IDs, same-name workers, and older server
  conflicts cannot collide or escape quota accounting.
- Preserved the last trusted revision/hash/path when a server update fails.
  Failed update metadata is retained separately for the next explicit retry.
- Recounted quota from every indexed physical file at serialized publication
  time and added reservations for concurrent new files. A local change during
  transfer is reclassified before publication and cannot bypass the limit.
- Added physical containment checks that reject existing symbolic-link/junction
  ancestors and revalidate the physical path immediately before publication.
  Conflict suffixing now enforces the final 220-code-point path budget.
- Prepared part files as read-only before exposing the final path. Failed
  preparation leaves no visible file or index entry; replacement publication
  restores the prior file and persisted index on failure.
- Replaced the fixed download wall-clock timeout with an idle timeout reset by
  progress. Redirects are limited to three, require HTTPS, remain exact-origin,
  and resend authentication only after every hop is revalidated.
- Moved initial state emission inside token-cleanup control flow.
- Validated manifest page type, item shape, policy version, cursor presence, and
  forward progress, with a bounded page count to prevent malformed loops.

## Changed Files

- `.superpowers/sdd/2026-07-27-electron-desktop-client-implementation/task-6-report.md`
- `desktop/src/sync/api-client.mjs`
- `desktop/src/sync/index-store.mjs`
- `desktop/src/sync/path-policy.mjs`
- `desktop/src/sync/sync-engine.mjs`
- `desktop/test/api-client.test.mjs`
- `desktop/test/index-store.test.mjs`
- `desktop/test/path-policy.test.mjs`
- `desktop/test/sync-engine.test.mjs`

## Self-Review

- Authentication remains memory-only. Tokens are neither persisted nor emitted,
  and each run owns its token so a replacement cannot accidentally use a newer
  session token.
- Every policy, identity, project-root, manifest, redirect, and download request
  remains authenticated and exact-origin. Production HTTPS rules are unchanged.
- The server remains authoritative and the implementation has no upload,
  server-side delete, rename, mutation, watcher, fabricated data, or automatic
  missing-file repair.
- Publication checks cancellation at awaited hash, path, quota, index, and
  cursor boundaries. File/index rollback covers failures before and after an
  awaited index commit.
- Quota is derived from actual sizes of all indexed physical files, including
  prior conflicts, and final paths are allocated under the same mutation lock.
- The exact six request methods and one state event remain unchanged. Task 7 UI,
  the sandbox-compatible preload, and renderer code were not modified.

## Concerns

- Tests use temporary NTFS directories and controlled API responses; this round
  did not perform authenticated end-to-end synchronization against a live
  central server.
- A packaged Electron build was not manually exercised for real Office/PDF
  read-only behavior or adversarial junction replacement timing.

---

# Fix Round 2/5

## Status

`DONE_WITH_CONCERNS`

All round 2 findings were addressed without changing the exact six-method IPC
surface, preload sandboxing, GET-only synchronization direction, or Task 7 UI.

## TDD Evidence

### Red

The first round 2 regression batch used cursor-honest manifests, a real
`DesktopApiClient`/`AbortController` cancellation path, cross-root replacement,
and exact-boundary quota:

```text
node --test test/index-store.test.mjs test/sync-engine.test.mjs
tests 40, pass 33, fail 7
```

The failures demonstrated:

- a deleted indexed file was not restored when the committed resume cursor
  returned no old row;
- one valid `availability: "missing"` item rejected the whole page and blocked
  its available sibling;
- an unselected failed project was retried while a selected missing file was
  ignored;
- real request abort surfaced `RunPausedError` from `emitIfActive`;
- a root replacement completed before the old root transaction unwound;
- two concurrent five-byte files failed to fill an exact ten-byte quota.

Replacement transaction tests failed before the commit point and explicit
rollback handling were moved:

```text
node --test --test-name-pattern="trusted-backup cleanup|failed replacement rollback" test/sync-engine.test.mjs
tests 2, pass 0, fail 2
```

A surrounding first-publication rollback test also failed before visible
unindexed content was displaced to a hidden rollback path:

```text
node --test --test-name-pattern="failed first publication" test/sync-engine.test.mjs
tests 1, pass 0, fail 1
```

The strengthened concurrent-index test was mutation-checked with save
serialization disabled:

```text
node --test --test-name-pattern="concurrent saves commit" test/index-store.test.mjs
tests 1, pass 0, fail 1
actual ordering "completed"; expected "waiting"
```

### Green

Focused synchronization and boundary suite:

```text
node --test test/api-client.test.mjs test/index-store.test.mjs test/path-policy.test.mjs test/sync-engine.test.mjs
tests 61, pass 61, fail 0, cancelled 0, skipped 0, todo 0
```

Final required desktop suite:

```text
npm.cmd --prefix desktop test
tests 104, pass 104, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 1955.5543
```

Required static and contract verification:

```text
node scripts/verify-desktop-ipc.mjs
Desktop IPC contract verified

node --check desktop/src/sync/api-client.mjs
node --check desktop/src/sync/index-store.mjs
node --check desktop/src/sync/path-policy.mjs
node --check desktop/src/sync/sync-engine.mjs
all exited 0

git diff --check
exit 0, no diff errors
```

## Fixes Delivered

- Manifest validation now accepts the server’s valid missing-source shape:
  `availability: "missing"`, empty `sha256`, and `downloadPath: null`.
  Missing sources are recorded as `server_missing`, count as unavailable, do not
  block available siblings, and do not prevent page cursor advancement.
- Explicit starts inspect selected-project index records before requesting the
  manifest cursor. Missing local files in `synced` or `local_modified` records
  are restored from their trusted indexed metadata; failed records from
  unselected projects are not retried.
- The standard fake API now enforces committed resume cursors. Restoration tests
  return an empty page after the terminal cursor instead of replaying old rows.
- Pause and session clear now outrank the `offline` error produced by a real
  aborted fetch. Start resolves with the already-emitted paused/cleared state
  and cannot call `emitIfActive` for a canceled run.
- Engine mutation locks are keyed by environment and authoritative user index
  partition rather than root. A root replacement may authenticate and prepare
  its directory, but policy, index, publication, and cursor work wait until the
  canceled root transaction has rolled back and released the partition lock.
- Index-store saves are serialized by physical partition path in invocation
  order. Temporary names remain unique, but a delayed earlier save can no longer
  overwrite a later committed save.
- Replacement publication has an explicit commit point. Before commit, rollback
  restores the trusted backup. After commit, backup cleanup is outside rollback,
  so cancellation cannot delete the replacement after deleting the only old
  copy.
- Rollback failures are explicit `publication_rollback_failed` or
  `index_rollback_failed` errors. Failed restoration preserves trusted and new
  physical copies on hidden backup/rollback paths; failed first publication
  cannot leave an unindexed final path visible.
- Successful publication consumes its quota reservation while still holding the
  publication mutex. The next worker sees either reserved bytes or indexed used
  bytes, never both, so exact-boundary concurrent downloads succeed.

## Changed Files

- `.superpowers/sdd/2026-07-27-electron-desktop-client-implementation/task-6-report.md`
- `desktop/src/sync/index-store.mjs`
- `desktop/src/sync/sync-engine.mjs`
- `desktop/test/index-store.test.mjs`
- `desktop/test/sync-engine.test.mjs`

## Self-Review

- The renderer bridge remains exactly six request methods and one state event;
  `desktop/src/ipc-contract.mjs`, `desktop/src/preload.cjs`, and all Task 7
  renderer files are unchanged.
- All network operations remain authenticated GET requests. No upload, DELETE,
  server rename, watcher, fabricated project/file, or server mutation was added.
- Tokens remain per-run, memory-only, unlogged, and cleared by pause, logout,
  replacement, renderer destruction through the existing controller, and app
  exit.
- Missing server sources advance only after the index has recorded their
  unavailable status. Missing local files are inspected only on an explicit
  start and only for selected projects.
- Index and cursor mutations share the authoritative user partition lock across
  root changes; final-path mutation, quota transition, and per-run reservations
  share the publication mutex.
- Replacement rollback never discards the new copy until the old trusted backup
  is restored. Any failed rollback remains visible to the engine as an explicit
  failure code and preserves recoverable physical copies.

## Concerns

- Tests use temporary NTFS directories and controlled HTTP responses. This round
  did not run an authenticated end-to-end synchronization against a live central
  server.
- A packaged Electron build was not manually exercised for Office/PDF read-only
  behavior or adversarial process-level filesystem interference.

---

# Fix Round 3/5

## Status

`DONE_WITH_CONCERNS`

All round 3 findings were addressed without changing the six-method IPC
surface, preload sandbox, GET-only synchronization, server authority, or Task 7
UI.

## TDD Evidence

### Red

The recovery regressions injected an index rollback save failure after
filesystem restoration and a committed-backup cleanup failure:

```text
node --test --test-name-pattern="index rollback failure preserves|cleanup-pending backups|concurrent new files exactly" test/sync-engine.test.mjs
tests 3, pass 1, fail 2
```

The failures showed that:

- the displaced replacement had already been deleted when index rollback failed;
- no durable recovery entry existed for the retained backup after cleanup
  failure.

The exact-boundary quota test passed because round 2’s behavior was already
correct, but the test was strengthened to wait on an explicit two-download
barrier. Reaching that barrier proves both workers completed reservation before
either publication was released.

The new recovery ledger trust-boundary test failed before structural validation
was added:

```text
node --test --test-name-pattern="malformed recovery ledger" test/index-store.test.mjs
tests 1, pass 0, fail 1
malformed physicalFiles string was accepted instead of quarantined
```

### Green

Focused synchronization and storage suite:

```text
node --test test/api-client.test.mjs test/index-store.test.mjs test/path-policy.test.mjs test/sync-engine.test.mjs
tests 64, pass 64, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 1714.0634
```

Final required desktop suite:

```text
npm.cmd --prefix desktop test
tests 107, pass 107, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 1978.5474
```

Required static and contract verification:

```text
node scripts/verify-desktop-ipc.mjs
Desktop IPC contract verified

node --check desktop/src/sync/api-client.mjs
node --check desktop/src/sync/index-store.mjs
node --check desktop/src/sync/path-policy.mjs
node --check desktop/src/sync/sync-engine.mjs
all exited 0

git diff --check
exit 0, no diff errors
```

## Fixes Delivered

- Added a validated `recoveryEntries` ledger to the per-user index. Existing
  indexes without the optional ledger remain readable; new/rewritten indexes
  persist it. Malformed recovery entries quarantine the index rather than
  contributing unsafe quota paths.
- Replacement rollback now moves the verified replacement to a deterministic
  `.jiqing-rollback-<transaction>` path and restores the prior trusted file
  without deleting either copy. The restored index and recovery metadata are
  persisted together.
- If index rollback fails after filesystem restoration, the in-memory recovery
  entry survives into the subsequent failure-record save. Both old and new
  bytes remain recoverable, and the ledger accounts the hidden replacement.
- Filesystem rollback failures produce `manual_recovery` entries that never
  auto-delete either copy. Successful rollback produces `cleanup_pending`
  entries for later explicit-start cleanup.
- Post-commit backup cleanup failure persists a `cleanup_pending` entry before
  returning `backup_cleanup_failed`. The backup remains quota-accounted.
- Every explicit start retries cleanup-pending deletions before failed-file
  retries or manifest pagination. Failed cleanup retains the ledger and counts
  as a partial failure; successful cleanup removes the ledger atomically.
- Quota de-duplicates and stats both synchronized record paths and recovery
  ledger paths. A retained five-byte backup plus a five-byte current file blocks
  an additional five-byte file under a ten-byte policy until cleanup succeeds.
- The exact-boundary concurrent quota test now uses latches: both fake downloads
  must be active after reservation, then one release allows both publications.
  No scheduler timing or fixed sleep is used.

## Changed Files

- `.superpowers/sdd/2026-07-27-electron-desktop-client-implementation/task-6-report.md`
- `desktop/src/sync/index-store.mjs`
- `desktop/src/sync/sync-engine.mjs`
- `desktop/test/index-store.test.mjs`
- `desktop/test/sync-engine.test.mjs`

## Self-Review

- Recovery never deletes the displaced replacement during rollback. Automatic
  deletion occurs only on a later explicit start after the restored index and
  cleanup ledger have committed.
- Recovery paths use a stable transaction hash derived from source identity and
  old/new revisions. Existing recovery-path collisions fail closed.
- `manual_recovery` entries preserve every known copy and remain quota-accounted;
  only `cleanup_pending` entries are eligible for automatic deletion.
- Normal indexed paths and recovery paths share one de-duplicated actual-size
  quota scan under the publication lock.
- Cleanup failure cannot advance recovery metadata removal. If physical cleanup
  succeeds but ledger removal fails, the retained ledger safely overstates
  storage until the next explicit start.
- IPC/preload/renderer files are unchanged. Network operations remain
  authenticated GET requests with no upload, DELETE, rename-on-server, watcher,
  fabricated project, or fabricated success.

## Concerns

- `manual_recovery` entries intentionally require later operational/manual
  resolution; Task 6 has no renderer recovery-management UI.
- Tests use temporary NTFS directories and controlled HTTP responses. This round
  did not run authenticated synchronization against a live central server or a
  packaged Electron client.

---

# Fix Round 4/5

## Status

`DONE_WITH_CONCERNS`

All round 4 findings were addressed without changing the six-method IPC
surface, sandboxed preload, authenticated GET-only synchronization, server
authority, or Task 7 UI.

## TDD Evidence

### Red

The initial round 4 regression run was:

```text
node --test desktop/test/index-store.test.mjs desktop/test/sync-engine.test.mjs
tests 58, pass 46, fail 12, cancelled 0, skipped 0, todo 0
duration_ms 1674.9368
```

Eleven failures demonstrated the intended production defects:

- cancellation during index rollback or failed backup cleanup left zero durable
  recovery entries;
- permissive ledger validation accepted unexpected keys, relative/noncanonical
  roots, traversal/arbitrary paths, transaction-name mismatches, and cleanup
  paths outside `physicalFiles`;
- a malformed ledger deleted `keep.txt` from the selected root.

One additional failure was a test-fixture setup error (`realpathSync` before the
temporary root existed); the root was created explicitly before the production
implementation was changed.

### Green

Final focused recovery/index suite:

```text
node --test desktop/test/index-store.test.mjs desktop/test/sync-engine.test.mjs
tests 58, pass 58, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 2158.0609
```

Final required desktop suite:

```text
npm.cmd --prefix desktop test
tests 119, pass 119, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 1902.6308
```

Required contract and static verification:

```text
node scripts/verify-desktop-ipc.mjs
Desktop IPC contract verified

node --check desktop/src/sync/api-client.mjs
node --check desktop/src/sync/index-store.mjs
node --check desktop/src/sync/path-policy.mjs
node --check desktop/src/sync/sync-engine.mjs
all exited 0

git diff --check
exit 0, no diff errors
Git emitted only existing LF-to-CRLF working-copy notices
```

## Fixes Delivered

- Added a recovery-only durable index transaction. It reloads the latest
  per-user index and mutates only `recoveryEntries`, so cancellation cannot
  prevent already-created artifacts from being recorded and the path cannot
  advance a cursor or publish success.
- Kept recovery-only writes inside the existing authoritative-user partition
  lock. A replacement run waits until the canceled run has completed its
  recovery write.
- Added cancellation-boundary tests for both an index rollback save failure
  followed by pause and a committed-backup cleanup failure followed by local
  root replacement. Both prove the retained bytes and ledger survive.
- Bound every recovery entry to the canonical physical root returned by
  `realpath`. Cleanup revalidates that exact root and applies physical
  containment checks before removing a reserved artifact.
- Changed recovery quota scans to account each entry against its bound root.
  Missing or inaccessible recovery paths conservatively retain
  `accountedBytes`.
- Added a root A to root B regression with an identically named root B
  sentinel. Cleanup remains directed at root A, root B is untouched, the ledger
  remains present after deferred cleanup, and root A bytes continue to block an
  over-quota publication under root B.
- Hardened recovery-ledger validation to require exact keys and types, a
  lowercase 32-hex transaction ID, a canonical absolute root, unique
  engine-reserved root-relative filenames correlated to the transaction ID,
  valid ISO time, and `cleanupFiles` as a subset of `physicalFiles`.
- Invalid ledger data quarantines the index before recovery processing. The
  adversarial engine test proves an arbitrary selected-root file is not
  deleted.
- Durable cleanup-ledger removal also reloads and mutates only recovery
  metadata. If persistence fails after physical cleanup, the existing ledger
  remains as a conservative quota reservation for a later explicit start.

## Changed Files

- `.superpowers/sdd/2026-07-27-electron-desktop-client-implementation/task-6-report.md`
- `desktop/src/sync/index-store.mjs`
- `desktop/src/sync/sync-engine.mjs`
- `desktop/test/index-store.test.mjs`
- `desktop/test/sync-engine.test.mjs`

## Self-Review

- Recovery-only persistence has no run-activity assertion and carries no token,
  network call, cursor mutation, file-success record, or state-success
  emission. It records only artifacts that filesystem rollback or failed
  cleanup already created.
- Automatic recovery deletion accepts only `.jiqing-backup-<transaction>` or
  `.jiqing-rollback-<transaction>` at the recorded physical root. Manual
  recovery entries remain nondeleting.
- Existing-root reparse/junction checks and realpath containment are applied
  again at cleanup time, not trusted from index validation alone.
- Old-root recovery entries remain in the same authoritative-user index across
  root selection changes and remain quota-accounted until deletion succeeds.
- `desktop/src/ipc-contract.mjs`, `desktop/src/preload.cjs`, main-process IPC,
  renderer files, and dependency manifests are unchanged.
- All synchronization network behavior remains authenticated GET-only. No
  upload, server delete, server rename, local watcher, fabricated business
  data, or fabricated success was added.

## Concerns

- `manual_recovery` entries intentionally remain durable and quota-accounted
  until an operator resolves them; Task 6 has no recovery-management UI.
- Tests use temporary NTFS directories and controlled HTTP responses. This round
  did not run authenticated synchronization against a live central server or a
  packaged Electron client.

---

# Fix Round 5/5

## Status

`DONE_WITH_CONCERNS`

The final allotted Task 6 fix round addresses both remaining findings without
changing the six-method IPC surface, sandboxed preload, authenticated GET-only
synchronization, server authority, or Task 7 UI.

## TDD Evidence

### Red

The first nested-name filter did not select the parent test and therefore was
not accepted as red evidence:

```text
node --test --test-name-pattern="cleanup with an extra physical file" desktop/test/index-store.test.mjs
tests 1, pass 1, fail 0
```

Rerunning the full index-store file exercised the new subtest and failed on the
intended validator defect:

```text
node --test desktop/test/index-store.test.mjs
tests 17, pass 15, fail 2, cancelled 0, skipped 0, todo 0
duration_ms 287.4239
```

The failing subtest showed that a `cleanup_pending` entry with one cleanup path
and two physical paths was loaded rather than quarantined. The second reported
failure is the containing parent test.

After the exact-shape validator was green, the repeated-attempt tests failed
against the deterministic recovery hash:

```text
node --test --test-name-pattern="repeated recovery" desktop/test/sync-engine.test.mjs
tests 2, pass 0, fail 2, cancelled 0, skipped 0, todo 0
duration_ms 338.0843
```

Both same-root and root-change cases expected two recovery entries after two
forced `r-1` to `r-2` rollback attempts but loaded only one.

### Green

Exact-shape validator cycle:

```text
node --test desktop/test/index-store.test.mjs
tests 17, pass 17, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 299.7471
```

Repeated-attempt transaction cycle:

```text
node --test --test-name-pattern="repeated recovery" desktop/test/sync-engine.test.mjs
tests 2, pass 2, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 395.1323
```

Final focused index and synchronization suite:

```text
node --test desktop/test/index-store.test.mjs desktop/test/sync-engine.test.mjs
tests 61, pass 61, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 2414.5543
```

Final required desktop suite:

```text
npm.cmd --prefix desktop test
tests 122, pass 122, fail 0, cancelled 0, skipped 0, todo 0
duration_ms 3248.4999
```

Required contract and static verification:

```text
node scripts/verify-desktop-ipc.mjs
Desktop IPC contract verified

node --check desktop/src/sync/api-client.mjs
node --check desktop/src/sync/index-store.mjs
node --check desktop/src/sync/path-policy.mjs
node --check desktop/src/sync/sync-engine.mjs
all exited 0

git diff --check
exit 0, no diff errors
Git emitted only existing LF-to-CRLF working-copy notices
```

## Fixes Delivered

- Replaced the deterministic source/revision hash with a cryptographically
  strong UUID-derived 32-hex transaction ID allocated for every publication
  attempt.
- Allocation checks the active authoritative-user index and retries UUID
  collisions. Durable recovery-only persistence also rejects any differing
  entry already using the ID, so neither in-memory nor on-disk ledger state can
  be overwritten on collision.
- Recovery filenames retain the bounded reserved forms
  `.jiqing-backup-<transaction>` and `.jiqing-rollback-<transaction>`, now with
  per-attempt identifiers.
- Every recovery entry now binds `rootPath`, `sourceKey`,
  `previousSourceRevision`, and `sourceRevision` to the unique transaction.
- Added a same-root repeated-failure regression. Two forced rollback attempts
  retain two IDs, two rollback files containing the server revision, and two
  ledger entries; their combined bytes block a later one-byte file at the
  exact quota boundary.
- Added the equivalent root A to root B regression. Both root-bound entries and
  artifacts survive, and quota accounting spans the two physical roots.
- Tightened `cleanup_pending` validation to exactly one `physicalFiles` path
  and one identical `cleanupFiles` path.
- Tightened `manual_recovery` validation to the engine's generated nondeleting
  forms: one backup path, or an ordered rollback-plus-backup pair, with an empty
  cleanup list.
- The adversarial multi-physical cleanup entry is quarantined before recovery
  processing and cannot authorize deletion.

## Changed Files

- `.superpowers/sdd/2026-07-27-electron-desktop-client-implementation/task-6-report.md`
- `desktop/src/sync/index-store.mjs`
- `desktop/src/sync/sync-engine.mjs`
- `desktop/test/index-store.test.mjs`
- `desktop/test/sync-engine.test.mjs`

## Self-Review

- Unique transaction allocation occurs under the existing authoritative-user
  partition lock and publication mutex, so simultaneous workers cannot observe
  or claim the same in-memory ledger key.
- Recovery-only durable merge remains independent of run cancellation and
  mutates no cursor, synchronized-file success, renderer state, or token.
- The UUID remains 32 lowercase hex characters after hyphen removal, preserving
  the existing Windows-safe reserved filename bounds and validator correlation.
- Cleanup remains restricted to one strictly validated, root-bound reserved
  artifact. Manual recovery remains nondeleting and quota-accounted.
- Repeated-attempt quota tests use real files and explicit forced index-save and
  cleanup failures; they verify durable entries, physical bytes, root bindings,
  revision bindings, and a later quota rejection.
- Adjacent rollback, pause/logout abort, root replacement, cleanup retry,
  malformed-ledger, and exact-boundary quota tests all pass in the full suite.
- IPC/preload/main-process/renderer files and dependency manifests are
  unchanged. No upload, server delete, server rename, watcher, fabricated data,
  or fabricated success was added.

## Concerns

- `manual_recovery` entries remain intentionally durable and quota-accounted
  until operational resolution; Task 6 has no recovery-management UI.
- Tests use temporary NTFS directories and controlled HTTP responses. This
  final round did not run authenticated synchronization against a live central
  server or a packaged Electron client.
