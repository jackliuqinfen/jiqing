# Manual Project Contract PDF Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the existing four-step manual project wizard, add an authenticated on-demand contract PDF preview beside it, and create formal projects atomically through the existing contract-confirmation boundary without OCR or server-side page rendering.

**Architecture:** The existing project wizard remains the host UI. A focused PDF.js component loads the immutable original PDF through authenticated HTTP Range requests, while an extended owner-scoped intake draft stores contract facts, project fields, wizard state, page and zoom. A new manual-intake application service creates manual review provenance, records human-confirmed values, calls the existing contract fact writer inside the same transaction, links the original to project materials, writes whitelisted project fields, and completes the draft.

**Tech Stack:** Vue 3, TypeScript, Arco Design Vue, `pdfjs-dist@6.2.108`, Vite 6, Python 3 standard library HTTP server, SQLite, Node test runner, Python `unittest`.

## Global Constraints

- Keep the four steps and their order exactly: `基础信息 → 项目阶段 → 资料目录 → 确认生成`.
- Add no OCR, external-AI import, recognition polling, or 300 DPI page rendering to the new path.
- Require project name, contract signed date, contractor, owner, positive contract amount, payment terms, and a saved PDF before formal confirmation.
- Keep `buildProjectMutationPayload('create')` blocked; formal records must still come from contract confirmation.
- Treat lifecycle status, lifecycle version, audit linkage, creator and updater identities as backend-owned fields.
- Make retries idempotent and reject a contract hash that has already created a project.
- Keep existing formal projects, document versions and historical review records unchanged.
- Work only in the isolated worktree on branch `docs/manual-project-pdf-preview-design`; do not touch the dirty main checkout.
- Do not push or deploy production until the release candidate passes all checks and the user explicitly authorizes deployment.

---

## File Map

**New files**

- `server/manual_project_intake_service.py`: atomic manual contract confirmation and project-material linking.
- `server/tests/test_manual_project_intake_service.py`: service transaction, whitelist, replay and rollback tests.
- `src/components/project/ContractPdfPreview.vue`: upload/replace, page render, zoom, collapse and download UI.
- `src/utils/contractPdfPreview.ts`: pure page/zoom/cache helpers.
- `src/utils/manualProjectIntake.ts`: form mapping, exact-money conversion and protected-field filtering.
- `src/composables/useManualProjectIntakeDraft.ts`: draft list, resume, optimistic autosave and flush behavior.
- `test/manualProjectIntake.test.ts`: pure mapping and source-level wizard regression tests.
- `test/contractPdfPreview.test.ts`: preview state and neighbor-prefetch tests.

**Modified files**

- `server/migrations.py`, `server/schema.sql`, `server/postgres_schema.sql`: draft project/UI state and optimistic revision.
- `server/project_intake_drafts.py`: validation and compare-and-swap saves.
- `server/document_review_service.py`: transaction-neutral save/confirm helpers reused by the application service.
- `server/document_api.py`: version metadata, original PDF Range endpoint, manual project confirmation endpoint and error mapping.
- `server/audit_api.py`: enforce project-scope authorization when previewing the linked contract material.
- `server/tests/test_project_intake_drafts.py`, `server/tests/test_document_migrations.py`, `server/tests/test_document_api_contract.py`: focused backend coverage.
- `src/types/documentReview.ts`, `src/api/documentReview.ts`: draft, metadata, PDF source and manual-confirmation contracts.
- `src/views/ProjectManagementView.vue`: restore the old create entry, add the right preview panel and submit through manual confirmation.
- `test/task4bLifecycleSafety.test.ts`: replace the temporary independent-review expectation with the new protected manual-wizard expectation.
- `package.json`, `package-lock.json`, `vite.config.ts`: pinned PDF.js dependency and separate PDF vendor chunk.
- `docs/superpowers/specs/2026-08-13-manual-project-contract-pdf-preview-design.md`: mark the approved design as implementation-ready.

---

### Task 1: Persist Complete Manual-Intake Draft State with Optimistic Concurrency

**Files:**
- Modify: `server/migrations.py`
- Modify: `server/schema.sql`
- Modify: `server/postgres_schema.sql`
- Modify: `server/project_intake_drafts.py`
- Modify: `server/document_api.py`
- Modify: `server/tests/test_document_migrations.py`
- Modify: `server/tests/test_project_intake_drafts.py`
- Modify: `server/tests/test_document_api_contract.py`

**Interfaces:**
- Produces: `create_draft(..., project_values=None, ui_state=None)` returning `project_values`, `ui_state`, and `revision=0`.
- Produces: `save_draft(..., expected_revision, project_values=None, ui_state=None)` using compare-and-swap and returning the incremented revision.
- Produces API fields: `projectValues`, `uiState`, `revision`, and request field `expectedRevision`.
- Consumed later by: `useManualProjectIntakeDraft` and `confirm_manual_project_intake`.

- [ ] **Step 1: Add failing migration and repository tests**

Add tests proving the migration creates these columns on `project_intake_drafts`:

```python
expected = {
    "project_values_json",
    "ui_state_json",
    "revision",
}
self.assertTrue(expected.issubset(columns))
```

Add repository tests with exact accepted payloads:

```python
draft = create_draft(
    self.conn,
    owner_user_id="editor-1",
    values={"project.name": "大洋湾小瀛台翻新改造项目"},
    project_values={
        "contractorName": "徐华",
        "contractorContact": "13800000000",
        "companyRole": "施工单位",
        "settlementStatus": "not_started",
        "submittedAmount": 0,
        "paidAmount": 0,
        "paymentTerms": "验收合格后付至80%",
        "plannedStartDate": "2026-01-05",
        "plannedEndDate": "2026-02-03",
        "description": "维修项目",
    },
    ui_state={"wizardStep": 1, "pdfPage": 28, "pdfScale": 1.1, "previewCollapsed": False},
    fallback_reason="manual_selected",
)
self.assertEqual(draft["revision"], 0)
self.assertEqual(draft["ui_state"]["pdfPage"], 28)
```

Add a stale-write test expecting `draft_version_conflict` when `expected_revision=0` is submitted after the draft has advanced to revision 1.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
python -m unittest server.tests.test_document_migrations server.tests.test_project_intake_drafts server.tests.test_document_api_contract.DocumentApiContractTests.test_draft_state_round_trips_and_rejects_stale_revision -v
```

Expected: FAIL because the columns, returned fields and optimistic revision do not exist.

- [ ] **Step 3: Add the ordered migration and baseline schema**

Add migration constant `MANUAL_PROJECT_INTAKE_STATE_MIGRATION = "2026081301_manual_project_intake_state"`. Its prepare function must add these columns only when missing:

```sql
ALTER TABLE project_intake_drafts ADD COLUMN project_values_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE project_intake_drafts ADD COLUMN ui_state_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE project_intake_drafts ADD COLUMN revision INTEGER NOT NULL DEFAULT 0;
```

Mirror the columns in both schema baseline files and register the migration after `PROJECT_DOCUMENT_STAGE_MIGRATION`.

- [ ] **Step 4: Validate project/UI state and implement compare-and-swap**

Use these exact whitelists in `project_intake_drafts.py`:

```python
_PROJECT_VALUE_KEYS = frozenset({
    "contractorName", "contractorContact", "companyRole", "settlementStatus",
    "submittedAmount", "paidAmount", "paymentTerms", "plannedStartDate",
    "plannedEndDate", "description",
})
_UI_STATE_KEYS = frozenset({"wizardStep", "pdfPage", "pdfScale", "previewCollapsed"})
```

Reject unknown keys, booleans used as numbers, non-finite numbers, wizard steps outside `0..3`, PDF pages below 1, PDF scales outside `0.5..2.5`, and non-boolean `previewCollapsed`.

Update drafts with:

```sql
UPDATE project_intake_drafts
SET ..., revision = revision + 1, updated_at = ?
WHERE id = ? AND owner_user_id = ? AND revision = ?
```

If `rowcount != 1`, raise `ProjectIntakeDraftError("draft_version_conflict", "草稿已在其他窗口更新，请刷新后继续。")`.

- [ ] **Step 5: Extend API payload mapping and conflict response**

Map `draft_version_conflict` to HTTP 409. Accept `projectValues`, `uiState`, and required `expectedRevision` on updates. Return:

```json
{
  "projectValues": {},
  "uiState": {"wizardStep": 0, "pdfPage": 1, "pdfScale": 1, "previewCollapsed": false},
  "revision": 0
}
```

Keep `values` limited to `contract.v1` semantic keys.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests PASS.

- [ ] **Step 7: Commit Task 1**

```powershell
git add server/migrations.py server/schema.sql server/postgres_schema.sql server/project_intake_drafts.py server/document_api.py server/tests/test_document_migrations.py server/tests/test_project_intake_drafts.py server/tests/test_document_api_contract.py
git commit -m "feat: persist manual project intake state"
```

---

### Task 2: Expose Transaction-Neutral Review Operations

**Files:**
- Modify: `server/document_review_service.py`
- Modify: `server/tests/test_document_review_service.py`

**Interfaces:**
- Produces: `save_decisions_in_transaction(conn, *, review_id, expected_review_version, decisions, actor, bulk=False, now=None)`; no begin/commit/rollback.
- Produces: `confirm_review_in_transaction(conn, *, review_id, expected_review_version, idempotency_key, actor, allowed_project_ids, form_template_version, project_id=None, project_code_generator=None, now=None)`; no begin/commit/rollback.
- Keeps: public `save_decisions` and `confirm_review` behavior and response contracts unchanged.
- Consumed later by: `confirm_manual_project_intake`.

- [ ] **Step 1: Write failing rollback-ownership tests**

Create a test that starts a transaction, calls `save_decisions_in_transaction`, then rolls back and proves no decision persists. Create a second test that starts a transaction, calls `confirm_review_in_transaction`, rolls back and proves no project, contract, snapshot or lifecycle event persists.

```python
self.conn.execute("BEGIN IMMEDIATE")
save_decisions_in_transaction(...)
self.conn.rollback()
self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM review_decisions").fetchone()[0], 0)
```

Add a regression proving a `manual` field accepted without anchors does not receive `evidence_anchor_missing`.

- [ ] **Step 2: Run the focused service test and verify RED**

Run:

```powershell
python -m unittest server.tests.test_document_review_service -v
```

Expected: FAIL because the transaction-neutral functions are not exported.

- [ ] **Step 3: Extract bodies without changing public semantics**

Move the logic currently inside each public transaction wrapper into the exact new functions. Public wrappers retain:

```python
try:
    conn.execute("BEGIN IMMEDIATE")
    result = confirm_review_in_transaction(conn, ...)
    conn.commit()
    return result
except Exception:
    conn.rollback()
    raise
```

`save_decisions_in_transaction` returns `review_detail`; `confirm_review_in_transaction` returns the same result object as `confirm_review`.

While extracting `_field_state`, preserve `source_kind` in `validator_fields`:

```python
validator_fields.append({
    "semantic_key": row["semantic_key"],
    "normalized_value": normalized,
    "validation_status": row["validation_status"],
    "source_kind": row["source_kind"],
    "anchors": item["anchors"],
})
```

This is required so accepted `manual` fields do not incorrectly require OCR evidence anchors.

- [ ] **Step 4: Run focused and existing review tests**

Run:

```powershell
python -m unittest server.tests.test_document_review_service server.tests.test_stage_fact_service -v
```

Expected: PASS with existing confirmation idempotency and blocker behavior unchanged.

- [ ] **Step 5: Commit Task 2**

```powershell
git add server/document_review_service.py server/tests/test_document_review_service.py
git commit -m "refactor: expose transactional review operations"
```

---

### Task 3: Build Atomic Manual Project Confirmation Service

**Files:**
- Create: `server/manual_project_intake_service.py`
- Create: `server/tests/test_manual_project_intake_service.py`
- Modify: `server/stage_fact_service.py`
- Modify: `server/audit_api.py`

**Interfaces:**
- Produces:

```python
confirm_manual_project_intake(
    conn,
    *,
    document_version_id,
    contract_values,
    project_values,
    draft_id,
    expected_draft_revision,
    idempotency_key,
    form_template_version,
    actor,
    project_code_generator,
    operation_logger,
    now=None,
) -> dict
```

- Raises: `ManualProjectIntakeError(code, message, field=None)` for request/domain validation that is not already represented by review blockers.
- Consumes: Task 1 draft repository and Task 2 transaction-neutral review operations.
- Returns: existing confirmation keys plus `project` and `replayed`.

- [ ] **Step 1: Write the failing happy-path integration test**

Use a stored PDF version with no rendered pages and this payload:

```python
contract_values = {
    "project.name": "大洋湾小瀛台翻新改造项目",
    "party.owner": "盐城大洋湾组团开发有限公司",
    "party.contractor": "盐城太悦装配建筑工程有限公司",
    "contract.amount": 26_505_729,
    "contract.signed_date": "2026-02-03",
    "contract.start_date": "2026-01-05",
    "contract.end_date": "2026-02-03",
    "project.manager": "徐华",
    "contract.payment_terms": [
        "全部工程完成且验收合格后付至已完成工程量价款的80%",
        "竣工结算完成后支付至审定价款的97%",
        "余款为质保金，质保期两年后结清",
    ],
}
project_values = {
    "contractorName": "徐华",
    "contractorContact": "",
    "companyRole": "施工单位",
    "settlementStatus": "not_started",
    "submittedAmount": 0,
    "paidAmount": 0,
    "paymentTerms": "全部工程完成且验收合格后付至80%\n竣工结算后付至97%\n余款质保两年",
    "plannedStartDate": "2026-01-05",
    "plannedEndDate": "2026-02-03",
    "description": "维修项目",
}
```

Assert one row each in `project_records`, `project_contracts`, `stage_form_snapshots`, and `project_lifecycle_events`; one `project_files` row in category `contract`; zero `document_pages`; no `ocr_blocks` or evidence anchors for the manual job; the draft is completed; and contractor text contains `太悦`, not `大悦`.

- [ ] **Step 2: Write failing security, replay and rollback tests**

Cover all of these independently:

- missing owner, zero amount, empty payment terms and non-PDF MIME block creation;
- an unknown project field such as `projectStatus` is rejected;
- same idempotency key returns the same project with `replayed=True`;
- a different key with the same PDF SHA is blocked as `duplicate_contract_document`;
- stale draft revision returns `draft_version_conflict`;
- an injected failure after project creation rolls back project, contract, file, review, event and draft completion together.

- [ ] **Step 3: Run the new service tests and verify RED**

Run:

```powershell
python -m unittest server.tests.test_manual_project_intake_service -v
```

Expected: FAIL because the service does not exist.

- [ ] **Step 4: Implement exact payload validation and manual provenance**

Validate contract values through `manual_contract_fields` and `contract.v1`; require the six critical values; require MIME `application/pdf`; and reject project keys outside Task 1's whitelist.

Inside one `BEGIN IMMEDIATE` transaction:

1. Resolve/replay the manual fallback job with idempotency key `manual-project-review:<idempotencyKey>`.
2. Create or reuse its review without calling `_ensure_rendered_pages`.
3. If that review is already confirmed with `manual-project-confirm:<idempotencyKey>`, return `confirmation_result` immediately; do this before validating the now-completed draft so a network-timeout retry succeeds.
4. Call `save_decisions_in_transaction` once per non-empty manual field, each as a single `accepted` decision with its current review version.
5. Call `confirm_review_in_transaction` with confirmation key `manual-project-confirm:<idempotencyKey>`.
6. Link the immutable original to `project_files` as category `contract` without copying bytes.
7. Compute only `document_completion` and `missing_required_count` from enabled contract-stage categories; do not reuse a rollup helper that would overwrite the wizard's `paidAmount` from settlement rows.
8. Update only the whitelisted project columns after document rollup calculation so `paidAmount` and the other user-entered values are preserved.
9. Complete the owner draft with compare-and-swap.
10. Call the injected operation logger before commit.

On any error, rollback the whole transaction.

- [ ] **Step 5: Preserve human-friendly payment terms and return the project**

Keep `project_contracts.payment_terms_json` and the snapshot as a string list. Update `project_records.payment_terms` from the original textarea string in `project_values["paymentTerms"]`. Extend the confirmation result to include the complete project row without changing existing `_map_confirmation` keys.

When inserting `project_files`, reuse the immutable document version's relative path and metadata; do not copy or delete bytes. Update `preview_project_file` in `audit_api.py` to call `current_user` and `source_project_allowed` before resolving or returning the file, matching the existing download authorization boundary.

- [ ] **Step 6: Run service and regression tests**

Run:

```powershell
python -m unittest server.tests.test_manual_project_intake_service server.tests.test_document_review_service server.tests.test_stage_fact_service -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```powershell
git add server/manual_project_intake_service.py server/stage_fact_service.py server/audit_api.py server/tests/test_manual_project_intake_service.py
git commit -m "feat: atomically confirm manual project intake"
```

---

### Task 4: Add Authenticated Version Metadata, Original PDF Range and Confirmation Endpoints

**Files:**
- Modify: `server/document_api.py`
- Modify: `server/tests/test_document_api_contract.py`

**Interfaces:**
- Produces: `GET /api/document-versions/{versionId}` returning safe version metadata.
- Produces: `GET /api/document-versions/{versionId}/original` returning authenticated `200`, `206`, or `416` PDF bytes.
- Produces: `POST /api/document-versions/{versionId}/manual-project-confirmation` consuming:

```json
{
  "idempotencyKey": "manual-project:<stable-client-key>",
  "formTemplateVersion": "manual-project-wizard.v1",
  "draftId": "draft-id",
  "expectedDraftRevision": 2,
  "contractValues": {},
  "projectValues": {}
}
```

- Consumes: `confirm_manual_project_intake` from Task 3.

- [ ] **Step 1: Add routes to the authentication contract test**

Add all three routes to `test_all_document_and_intake_routes_require_authentication`. Add tests proving an unbound document is readable only by its uploader (or admin), and viewer may read the original but cannot confirm.

- [ ] **Step 2: Add failing Range and metadata tests**

Assert metadata omits `relative_path` and includes `id`, `documentId`, `name`, `mimeType`, `fileSize`, `uploadedAt`, `documentType`, and `alreadyConfirmedProjectId`.

For original bytes, assert:

```python
self.assertEqual(status, 206)
self.assertEqual(body, original[2:6])
self.assertEqual(headers["Content-Range"], f"bytes 2-5/{len(original)}")
self.assertEqual(headers["Accept-Ranges"], "bytes")
self.assertEqual(headers["Content-Type"], "application/pdf")
```

Add an invalid range assertion for HTTP 416.

- [ ] **Step 3: Add failing manual-confirm endpoint tests**

Assert HTTP 201 on first create, HTTP 200 on replay, HTTP 422 with blockers for missing critical facts, HTTP 409 for stale draft or duplicate contract, and HTTP 403 for viewer/outsider. Patch `render_document_pages` and assert it is never called.

- [ ] **Step 4: Run focused API tests and verify RED**

Run:

```powershell
python -m unittest server.tests.test_document_api_contract -v
```

Expected: FAIL because the new routes are absent.

- [ ] **Step 5: Implement safe metadata and original file responses**

Resolve the version with `_DocumentReadRepository.version`, call `_require_resource_access`, reject non-PDF originals for the preview endpoint, resolve only through `DocumentStorage._resolve`, and reuse `_respond_file_range`. Never return `relative_path`.

- [ ] **Step 6: Dispatch manual confirmation and map errors**

Require confirmer role, verify resource access before reading the body, call Task 3's service, and map:

- validation: 422;
- stale draft/idempotency conflict/duplicate contract: 409;
- missing version: 404;
- unauthorized scope: 403;
- transient database/file errors: existing 503 mapping.

Return `_map_confirmation(result)` plus a safe `project` payload.

- [ ] **Step 7: Run API and backend document tests**

Run:

```powershell
python -m unittest server.tests.test_document_api_contract server.tests.test_document_repository server.tests.test_document_storage -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

```powershell
git add server/document_api.py server/tests/test_document_api_contract.py
git commit -m "feat: expose manual intake PDF and confirmation APIs"
```

---

### Task 5: Add Typed Frontend Mapping, Draft and PDF API Contracts

**Files:**
- Create: `src/utils/manualProjectIntake.ts`
- Create: `test/manualProjectIntake.test.ts`
- Modify: `src/types/documentReview.ts`
- Modify: `src/api/documentReview.ts`

**Interfaces:**
- Produces: `buildManualContractValues(form)` returning `ContractDraftValues` with amount in integer fen and payment terms as trimmed non-empty lines.
- Produces: `buildManualProjectValues(form, creationFlow)` returning only Task 1's project whitelist.
- Produces: `newManualProjectIntakeKey()` returning a stable key kept until success/reset.
- Produces: `fetchDocumentVersion(versionId)`, `originalPdfRequest(versionId)`, `downloadOriginalPdf(versionId)`, and `confirmManualProjectIntake(versionId, request)`.
- Produces extended draft types with `projectValues`, `uiState`, `revision`, `expectedRevision`.

- [ ] **Step 1: Write failing mapping tests**

Assert this exact conversion:

```typescript
assert.deepEqual(buildManualContractValues({
  projectName: '大洋湾小瀛台翻新改造项目',
  ownerUnit: '盐城大洋湾组团开发有限公司',
  constructionUnit: '盐城太悦装配建筑工程有限公司',
  contractAmount: 265057.29,
  contractDate: '2026-02-03',
  managerName: '徐华',
  plannedStartDate: '2026-01-05',
  plannedEndDate: '2026-02-03',
  paymentTerms: '验收后付80%\n\n结算后付97%',
}), {
  'project.name': '大洋湾小瀛台翻新改造项目',
  'party.owner': '盐城大洋湾组团开发有限公司',
  'party.contractor': '盐城太悦装配建筑工程有限公司',
  'contract.amount': 26505729,
  'contract.signed_date': '2026-02-03',
  'project.manager': '徐华',
  'contract.start_date': '2026-01-05',
  'contract.end_date': '2026-02-03',
  'contract.payment_terms': ['验收后付80%', '结算后付97%'],
})
```

Assert a number with more than two decimal places is rejected, protected keys never appear in project values, and project type/location are appended to description using the existing note format.

- [ ] **Step 2: Run Node test and verify RED**

Run:

```powershell
node --test test/manualProjectIntake.test.ts
```

Expected: FAIL because the utility does not exist.

- [ ] **Step 3: Implement pure mappings and exact-money conversion**

Convert RMB using string normalization, not binary multiplication alone. Reject non-finite, non-positive or sub-cent values before returning integer fen. Preserve Chinese company names exactly; do not normalize `太悦` to any dictionary suggestion.

- [ ] **Step 4: Add typed API calls**

`originalPdfRequest` returns:

```typescript
{
  url: `${API_BASE}/document-versions/${encodeURIComponent(versionId)}/original`,
  httpHeaders: token ? { Authorization: `Bearer ${token}` } : {},
}
```

`confirmManualProjectIntake` uses the existing structured `DocumentReviewApiError`. `downloadOriginalPdf` uses the same auth header and preserves non-JSON upstream errors.

- [ ] **Step 5: Run the utility test and TypeScript check**

Run:

```powershell
node --test test/manualProjectIntake.test.ts
npx.cmd vue-tsc --noEmit
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```powershell
git add src/utils/manualProjectIntake.ts src/types/documentReview.ts src/api/documentReview.ts test/manualProjectIntake.test.ts
git commit -m "feat: add manual project intake frontend contracts"
```

---

### Task 6: Build the On-Demand Contract PDF Preview

**Files:**
- Create: `src/utils/contractPdfPreview.ts`
- Create: `src/components/project/ContractPdfPreview.vue`
- Create: `test/contractPdfPreview.test.ts`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `vite.config.ts`

**Interfaces:**
- `ContractPdfPreview.vue` props:

```typescript
type ContractDocumentRef = {
  documentId: string
  versionId: string
  name: string
  mimeType: string
  fileSize: number
}

defineProps<{
  document: ContractDocumentRef | null
  maxFileSizeMb: number
  page: number
  scale: number
  collapsed: boolean
}>()
```

- Emits: `uploaded(document)`, `update:page`, `update:scale`, `update:collapsed`, `uploading(boolean)`, `error(message)`.
- Consumes: Task 5 PDF API helpers and existing `uploadDocument`.

- [ ] **Step 1: Install the exact PDF.js dependency**

Run:

```powershell
npm.cmd install pdfjs-dist@6.2.108 --save --cache C:\Users\liu-j\WorkBuddy\.npm-cache-manual-preview
```

Expected: package and lockfile contain exactly `pdfjs-dist@6.2.108`.

- [ ] **Step 2: Write failing pure preview-state tests**

Cover:

```typescript
assert.deepEqual(neighborPages(1, 57), [1, 2])
assert.deepEqual(neighborPages(28, 57), [27, 28, 29])
assert.equal(clampPage(99, 57), 57)
assert.equal(clampScale(0.1), 0.5)
assert.equal(clampScale(3), 2.5)
```

Also test a monotonically increasing render token so an older async render cannot publish after a newer page request.

- [ ] **Step 3: Run preview tests and verify RED**

Run:

```powershell
node --test test/contractPdfPreview.test.ts
```

Expected: FAIL because the utility does not exist.

- [ ] **Step 4: Implement the pure helpers and PDF worker chunk**

Use `pdfjs-dist/build/pdf.worker.min.mjs` through Vite's URL import. Add a separate `vendor-pdfjs` manual chunk before the generic vendor branch so project-management initial code does not absorb PDF.js into unrelated routes.

- [ ] **Step 5: Implement component lifecycle and local loading states**

Load with:

```typescript
const task = getDocument({
  ...originalPdfRequest(props.document.versionId),
  rangeChunkSize: 256 * 1024,
  disableAutoFetch: true,
  disableStream: true,
})
```

Render only the current page to canvas. Prefetch only `neighborPages(current, total)` during `requestIdleCallback` (or a zero-delay fallback). Cancel prior render tasks on page/scale changes. Destroy render task, PDF document, resize observer and canvas state on replacement/unmount.

- [ ] **Step 6: Implement upload, safe replacement, download and responsive collapse**

Accept only `.pdf` with signature validation still owned by the server. New upload omits `documentId`; replacement includes the current `documentId`, and emits the new version only after upload succeeds. Keep the old document on failure. The component's error/loading overlay must cover only the right pane.

At narrow widths, render a compact `查看合同原文` button and use an Arco right drawer; do not reorder the form.

- [ ] **Step 7: Run tests, type-check and production build**

Run:

```powershell
node --test test/contractPdfPreview.test.ts
npx.cmd vue-tsc --noEmit
npm.cmd run build
```

Expected: PASS; build output contains a separate PDF.js chunk and worker asset.

- [ ] **Step 8: Commit Task 6**

```powershell
git add package.json package-lock.json vite.config.ts src/utils/contractPdfPreview.ts src/components/project/ContractPdfPreview.vue test/contractPdfPreview.test.ts
git commit -m "feat: add on-demand contract PDF preview"
```

---

### Task 7: Integrate Draft Resume and Protected Confirmation into the Existing Wizard

**Files:**
- Create: `src/composables/useManualProjectIntakeDraft.ts`
- Modify: `src/views/ProjectManagementView.vue`
- Modify: `test/manualProjectIntake.test.ts`
- Modify: `test/task4bLifecycleSafety.test.ts`

**Interfaces:**
- Produces composable:

```typescript
useManualProjectIntakeDraft({
  snapshot: () => ManualProjectIntakeDraftSnapshot,
  restore: (snapshot: ManualProjectIntakeDraftSnapshot) => void,
  onError: (message: string) => void,
})
```

- Returns: `drafts`, `activeDraft`, `loadingDrafts`, `savingDraft`, `loadDrafts`, `resumeDraft`, `scheduleSave`, `flushSave`, `attachDocument`, `completeAndReset`.
- Consumes: Task 1 draft API, Task 5 mappings, Task 6 preview component.

- [ ] **Step 1: Replace the old source-level regression with failing new expectations**

Update tests to assert:

```typescript
assert.doesNotMatch(source, /<DocumentDrivenEntry/)
assert.match(source, /<ContractPdfPreview/)
assert.match(source, /confirmManualProjectIntake/)
assert.match(source, /if\s*\(!record\)[\s\S]*?projectDialog\.mode\s*=\s*'create'/)
assert.match(source, /label="建设单位"[\s\S]*?required/)
assert.match(source, /label="合同金额"[\s\S]*?required/)
assert.match(source, /label="付款条款"[\s\S]*?required/)
```

Keep the test proving `buildProjectMutationPayload('create')` throws.

- [ ] **Step 2: Run Node tests and verify RED**

Run:

```powershell
node --test test/manualProjectIntake.test.ts test/task4bLifecycleSafety.test.ts
```

Expected: FAIL because the view still opens `DocumentDrivenEntry`.

- [ ] **Step 3: Implement owner-scoped draft autosave and resume**

Debounce saves by 800 ms. Persist semantic contract values, whitelisted project values, current wizard step, PDF page, scale and collapsed state. Send `expectedRevision`; on HTTP 409 stop autosave and show `草稿已在其他窗口更新，请重新载入后继续。`.

The right pane lists current-user unfinished drafts ordered by update time. Clicking one restores the form and opens its document. If route query `intakeDocumentVersionId` is present, call the metadata endpoint and resume the matching draft; if none exists, attach that version to a new owner draft without uploading again.

- [ ] **Step 4: Restore the create entry and preserve the four-step structure**

Remove `DocumentDrivenEntry`, `contractCreationVisible`, and `handleContractProjectCreated`. For a missing record, `openProjectForm` must reset creation state, load drafts, set mode `create`, and open the existing modal.

Wrap the existing wizard in a two-column shell. Keep the stepper, step sections and footer in their current order on the left. Mount `ContractPdfPreview` on the right. Editing an existing project continues to render only the old edit form.

- [ ] **Step 5: Enforce backend-required base fields**

Add `required` and error bindings for owner and contract amount. Add a required `ATextarea` for `paymentTerms` in the base step. In `validateProjectWizardStep` and `validateProjectForm`, set exact errors:

```typescript
if (!projectForm.ownerUnit.trim()) projectFormErrors.ownerUnit = '请填写建设单位。'
if (Number(projectForm.contractAmount || 0) <= 0) projectFormErrors.contractAmount = '合同金额必须大于零。'
if (!projectForm.paymentTerms.trim()) projectFormErrors.paymentTerms = '请对照合同填写付款条款。'
```

Block leaving the base step until these pass.

- [ ] **Step 6: Submit create mode through manual confirmation**

At the final step, require an uploaded document version. Build contract and project values using Task 5. Reuse the same client idempotency key across timeout retries. Call `confirmManualProjectIntake`; never call `createProjectRecord` in create mode.

On success, mark/reset the draft state, close the modal, refresh summary/work items/list, and select the returned project. On timeout, preserve the key, form and document so retry resolves the same result.

- [ ] **Step 7: Keep edit mode unchanged and remove dead imports**

`saveProject()` becomes edit-only and continues to call `buildProjectMutationPayload('edit')` plus `updateProjectRecord`. Remove the now-unused `createProjectRecord` import. Keep lifecycle and audit linkage filtering unchanged.

- [ ] **Step 8: Add layout styling without global page changes**

Use a viewport-bounded modal (maximum 1480 px, `calc(100vw - 48px)`), left/right independent scroll areas, 60/40 columns, and a collapsed single-column state. Preserve existing field grids and footer positions inside the left pane.

- [ ] **Step 9: Run all frontend tests, type-check and build**

Run:

```powershell
node --test test/*.test.ts
npx.cmd vue-tsc --noEmit
npm.cmd run build
```

Expected: all tests PASS and the production build completes.

- [ ] **Step 10: Commit Task 7**

```powershell
git add src/composables/useManualProjectIntakeDraft.ts src/views/ProjectManagementView.vue test/manualProjectIntake.test.ts test/task4bLifecycleSafety.test.ts
git commit -m "feat: restore manual wizard with contract preview"
```

---

### Task 8: Full Verification and Local Acceptance

**Files:**
- Modify only if verification reveals a scoped defect in files already listed above.

**Interfaces:**
- Verifies all prior task contracts together.

- [ ] **Step 1: Run the complete backend suite**

```powershell
python -m unittest discover -s server/tests -p "test_*.py" -v
```

Expected: all backend tests PASS.

- [ ] **Step 2: Run the complete frontend suite and static checks**

```powershell
node --test test/*.test.ts
npx.cmd vue-tsc --noEmit
npm.cmd run build
git diff --check
```

Expected: all tests and checks PASS with no whitespace errors.

- [ ] **Step 3: Verify the no-OCR/no-render contract in code and tests**

```powershell
rg -n "startRecognition|startDirectManualReview|render_document_pages|_ensure_rendered_pages" src/views/ProjectManagementView.vue src/components/project/ContractPdfPreview.vue server/manual_project_intake_service.py server/document_api.py
```

Expected: the new frontend path and service contain no recognition call; `render_document_pages` remains only in legacy recognition/review code, and the manual-confirm test proves it is not invoked.

- [ ] **Step 4: Run a local browser acceptance pass**

Start the API with a temporary database/upload root and run the built frontend or Vite proxy. Verify:

1. create opens the original four-step wizard;
2. owner, amount and payment terms block the base step when missing;
3. a 57-page PDF uploads without rendering all pages server-side;
4. preview page 1 appears, page 28 loads on demand, zoom/collapse retain form values;
5. refresh/resume restores draft page, scale, step and fields;
6. final confirmation creates exactly one project and one contract file;
7. a retry with the same key returns the same project;
8. edit mode has no preview and still saves normally.

- [ ] **Step 5: Inspect final scope and commit any verification-only fix**

```powershell
git status --short --branch
git diff --stat origin/main...HEAD
git log --oneline --decorate origin/main..HEAD
```

If a verification fix was required, commit only its scoped files with `fix: complete manual project intake verification`. Otherwise create no empty commit.

- [ ] **Step 6: Prepare the release handoff**

Report exact test counts, build result, changed files, branch and commits. Stop before pushing or production deployment and request explicit release approval.

---

### Task 9: Production Release and 大洋湾 Resume (Only After Explicit Release Approval)

**Files:**
- No source changes expected.

**Interfaces:**
- Consumes the verified release candidate from Task 8.

- [ ] **Step 1: Invoke the deployment workflow**

Read and follow `deploy-shenjikanban/SKILL.md`. Verify clean release scope, push the approved commits to `main`, package only intended source/build files, deploy, restart the service and verify health.

- [ ] **Step 2: Verify deployed assets and APIs**

Confirm the live build contains the new PDF.js chunk and worker asset. Authenticate and verify version metadata, original Range request and manual confirmation authorization without creating a disposable production project.

- [ ] **Step 3: Resume the existing 大洋湾 contract**

Open project management with the known unfinished contract version, verify no existing project uses the same contract, and restore the manual wizard without re-uploading. Confirm these contract facts before submission:

- 项目名称：`大洋湾小瀛台翻新改造项目`
- 建设单位：`盐城大洋湾组团开发有限公司`
- 施工单位：`盐城太悦装配建筑工程有限公司`
- 项目负责人：`徐华`
- 合同金额：`265057.29`
- 合同签订日期：`2026-02-03`

Use the payment terms already verified from the contract original. Do not submit if `大悦` appears anywhere in the contractor field.

- [ ] **Step 4: Confirm once and verify no duplicate**

Submit through the new manual confirmation endpoint, refresh the project ledger, and verify exactly one project links to the contract. Verify the original PDF opens from project materials and the lifecycle stage is the backend-returned `contract_signed` state.

- [ ] **Step 5: Report production evidence**

Report deployed commit, service/health result, project ID/name, contractor spelling, contract-file accessibility and duplicate check. Do not store or repeat credentials.
