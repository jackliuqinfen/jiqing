# Contract Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three safe contract-intake paths: system OCR, externally generated structured suggestions, and manual entry with resumable drafts.

**Architecture:** Keep the uploaded contract document and the existing `DocumentReviewWorkspace` as the only path to formal project creation. A focused fallback service creates review-ready jobs with no synthetic OCR coordinates; an external-import parser accepts exactly one fenced JSON object and validates every semantic key against `contract.v1`. Fileless manual work is persisted as an owner-scoped intake draft and cannot create project facts.

**Tech Stack:** Python 3 standard library, SQLite migration plus PostgreSQL parity DDL, `unittest`, Vue 3 Composition API, TypeScript, Arco Design Vue, existing authenticated document API.

## Global Constraints

- No contract file means draft only: do not create `projects`, contract facts, project codes, or lifecycle events.
- External AI output and system OCR output are suggestions only; critical fields require individual human confirmation.
- External import accepts `schemaVersion = contract.v1` and semantic keys from the existing contract schema only.
- Do not persist provider credentials or raw third-party responses outside the submitted Markdown draft payload.
- Do not invent OCR text blocks, bounding boxes, coordinates, confidence, or evidence anchors.
- Existing AI recognition, contract confirmation, and project lifecycle gates must remain unchanged.
- No sample business records or synthetic project data.

---

### Task 1: Versioned Draft And Fallback Provenance Schema

**Files:**
- Modify: `server/migrations.py`
- Modify: `server/schema.sql`
- Modify: `server/postgres_schema.sql`
- Modify: `server/tests/test_document_migrations.py`

**Interfaces:**
- Produces table `project_intake_drafts` and nullable column `recognition_jobs.source_recognition_job_id`.
- Draft statuses are `draft`, `document_attached`, `completed`, and `abandoned`.

- [ ] **Step 1: Write the failing migration tests**

Add assertions that a migrated database contains `project_intake_drafts`, that owner and status indexes exist, and that `recognition_jobs` exposes `source_recognition_job_id`. Insert a source job and a fallback job to verify the self-reference, then verify invalid source IDs fail under foreign-key enforcement.

- [ ] **Step 2: Run the migration tests and verify RED**

Run:

```powershell
& $env:CODEX_PYTHON -m unittest server.tests.test_document_migrations -v
```

Expected: FAIL because the draft table and provenance column do not exist.

- [ ] **Step 3: Add an ordered migration and canonical parity DDL**

Add `2026071501_contract_fallback` with an additive `ALTER TABLE recognition_jobs ADD COLUMN source_recognition_job_id TEXT REFERENCES recognition_jobs(id)` and the draft table:

```sql
CREATE TABLE IF NOT EXISTS project_intake_drafts (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  document_id TEXT,
  document_version_id TEXT,
  schema_version TEXT NOT NULL DEFAULT 'contract.v1',
  values_json TEXT NOT NULL DEFAULT '{}',
  fallback_reason TEXT NOT NULL DEFAULT '',
  fallback_note TEXT NOT NULL DEFAULT '',
  completed_project_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id),
  FOREIGN KEY (completed_project_id) REFERENCES project_records(id)
)
```

Mirror the schema in SQLite and PostgreSQL canonical files and add owner/status indexes.

- [ ] **Step 4: Run migration tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit the schema unit**

```powershell
git add server/migrations.py server/schema.sql server/postgres_schema.sql server/tests/test_document_migrations.py
git commit -m "feat: add contract intake fallback schema"
```

### Task 2: Strict External AI Parser And Review-Ready Fallback Service

**Files:**
- Create: `server/contract_fallback_service.py`
- Create: `server/tests/test_contract_fallback_service.py`
- Modify: `server/document_repository.py`

**Interfaces:**
- Produces `parse_external_contract_markdown(markdown: str) -> list[dict]`.
- Produces `create_fallback_review(conn, *, source_job_id, adapter_key, idempotency_key, fields, actor, fallback_reason, fallback_note='') -> dict`.
- `adapter_key` is limited to `manual-entry` or `external-ai-paste`.

- [ ] **Step 1: Write parser tests and verify RED**

Cover one valid fenced `json` block, unknown semantic key, wrong schema version, duplicate JSON blocks, malformed JSON, non-object fields, oversized Markdown, and excessive field counts. Assert valid fields retain `value`, optional `evidence`, and optional positive `page`, but never produce anchors or confidence.

- [ ] **Step 2: Implement the strict parser and verify GREEN**

Extract exactly one code block matching ```` ```json ... ``` ````. Require this shape:

```python
{
    "schemaVersion": "contract.v1",
    "fields": {
        "project.name": {"value": "...", "evidence": "...", "page": 1}
    },
}
```

Reject unknown top-level keys, unknown semantic keys, nested unbounded values, booleans as page numbers, and values that cannot be represented by the existing normalizer.

- [ ] **Step 3: Write fallback service tests and verify RED**

Create a failed source job. Assert manual fallback materializes all `contract.v1` fields with `source_kind = manual`, external fallback stores only normalized suggestions plus empty schema fields, both create an open review, both reuse idempotency keys, source and fallback jobs reference the same immutable version, and source jobs outside `failed` or `manual_required` are rejected.

- [ ] **Step 4: Implement fallback review creation and verify GREEN**

Create the fallback recognition job via `document_repository.create_recognition_job`, store `source_recognition_job_id`, normalize/materialize fields, persist them without blocks or anchors, mark the job `review_ready`, and call `create_review`. Wrap the writes in the caller transaction and return a recognition snapshot-compatible mapping.

- [ ] **Step 5: Run focused tests**

```powershell
& $env:CODEX_PYTHON -m unittest server.tests.test_contract_fallback_service server.tests.test_document_repository -v
```

Expected: PASS.

- [ ] **Step 6: Commit the service unit**

```powershell
git add server/contract_fallback_service.py server/document_repository.py server/tests/test_contract_fallback_service.py
git commit -m "feat: create safe contract fallback reviews"
```

### Task 3: Owner-Scoped Draft Repository And Authenticated APIs

**Files:**
- Create: `server/project_intake_drafts.py`
- Create: `server/tests/test_project_intake_drafts.py`
- Modify: `server/document_api.py`
- Modify: `server/tests/test_document_api_contract.py`

**Interfaces:**
- Produces repository functions `create_draft`, `list_drafts`, `get_draft`, `save_draft`, and `abandon_draft`.
- Adds `GET/POST /api/project-intake-drafts`, `GET/POST /api/project-intake-drafts/{id}`, and `POST /api/project-intake-drafts/{id}/abandon`.
- Adds `POST /api/document-recognition-jobs/{jobId}/manual-review` and `/external-import`.

- [ ] **Step 1: Write draft repository tests and verify RED**

Assert owner-scoped listing, admin lookup support, status transitions, JSON semantic-key whitelist, document/version pairing, completed/abandoned immutability, and no project rows created by draft operations.

- [ ] **Step 2: Implement the draft repository and verify GREEN**

Store values only under `contract.v1` semantic keys. Serialize deterministically. Require the referenced version to belong to the referenced document. Do not create business facts or project IDs.

- [ ] **Step 3: Write API contract tests and verify RED**

Add authentication and role coverage for every new route. Verify normal users can only access their own drafts, viewers cannot write, manual review requires a failed/manual-required source job, external import rejects unsafe Markdown, both review routes are idempotent, and successful calls return `reviewId` without creating a project.

- [ ] **Step 4: Implement APIs and operation logging**

Register the new GET/POST routes in `DocumentApi`, reuse `_require_writer` and `_require_resource_access`, and record actions in `system_operation_logs` using actor ID/name, target type and ID, reason, and source job ID. Do not log the pasted Markdown or contract values.

- [ ] **Step 5: Run focused and full backend tests**

```powershell
& $env:CODEX_PYTHON -m unittest server.tests.test_project_intake_drafts server.tests.test_document_api_contract -v
& $env:CODEX_PYTHON -m unittest discover -s server/tests -v
```

Expected: PASS.

- [ ] **Step 6: Commit the API unit**

```powershell
git add server/project_intake_drafts.py server/document_api.py server/tests/test_project_intake_drafts.py server/tests/test_document_api_contract.py
git commit -m "feat: expose contract fallback intake APIs"
```

### Task 4: Three-Path Contract Intake UI

**Files:**
- Create: `src/components/document-review/ContractEntryMode.vue`
- Create: `src/components/document-review/ExternalAiImportPanel.vue`
- Create: `src/components/document-review/ManualContractDraftPanel.vue`
- Modify: `src/components/document-review/DocumentDrivenEntry.vue`
- Modify: `src/api/documentReview.ts`
- Modify: `src/types/documentReview.ts`

**Interfaces:**
- `ContractEntryMode` emits `system-ai`, `external-ai`, or `manual`.
- `ExternalAiImportPanel` emits a `reviewId` after upload/import.
- `ManualContractDraftPanel` emits a `reviewId` after file-backed manual review or `saved` after fileless draft persistence.

- [ ] **Step 1: Add typed API contracts**

Define `ProjectIntakeDraft`, `ExternalImportRequest`, and `ManualReviewRequest`. Add API helpers for draft list/create/save/abandon, manual review, and external import.

- [ ] **Step 2: Build the three-mode chooser**

Use three restrained Arco-compatible cards with concise copy. System AI remains recommended. External AI includes the privacy warning. Manual mode states clearly that no-file work is saved as “待补合同” and cannot create a formal project.

- [ ] **Step 3: Build external import flow**

Require contract upload first, provide a “复制提示词” action using `navigator.clipboard.writeText`, display the fixed `contract.v1` prompt, accept pasted Markdown, submit it to the backend, and move to the existing review workspace using the returned `reviewId`.

- [ ] **Step 4: Build manual fallback flow**

Collect fallback reason/note and an optional contract file. With a file, upload it, create a recognition job only as the source reference if needed, then request manual review. Without a file, save the critical semantic fields as a draft and show “草稿已保存，待补合同” without creating a project.

- [ ] **Step 5: Wire failure actions into existing AI path**

For upload failures, show “保存手动草稿”. For file-saved recognition failures, show “进入手动复核” and “导入外部 AI 结果” alongside “重新识别”. Preserve the selected file, uploaded version, and entered values when switching modes.

- [ ] **Step 6: Run TypeScript and production build**

```powershell
npm.cmd run build
```

Expected: Vue type-check and Vite build succeed. Existing Arco vendor CSS warnings may remain unchanged.

- [ ] **Step 7: Commit the frontend unit**

```powershell
git add src/components/document-review/ContractEntryMode.vue src/components/document-review/ExternalAiImportPanel.vue src/components/document-review/ManualContractDraftPanel.vue src/components/document-review/DocumentDrivenEntry.vue src/api/documentReview.ts src/types/documentReview.ts
git commit -m "feat: add resilient contract intake paths"
```

### Task 5: Regression, Documentation, And Release

**Files:**
- Modify: `docs/superpowers/specs/2026-07-15-contract-manual-fallback-design.md`
- Create: `docs/contract-fallback-acceptance-report.md`

**Interfaces:**
- Produces a release-ready verification record; no new runtime interface.

- [ ] **Step 1: Run all automated verification**

```powershell
& $env:CODEX_PYTHON -m unittest discover -s server/tests -v
npm.cmd run build
git diff --check
```

Expected: all backend tests pass, frontend build succeeds, and diff check is clean.

- [ ] **Step 2: Review the change surface**

Verify no unrelated untracked files are staged, no credentials or pasted contract values appear in diffs, API error responses identify the actual failing boundary, and every formal project creation still originates from confirmed document review.

- [ ] **Step 3: Write acceptance evidence**

Record test counts and these scenarios: system OCR success, file-saved OCR failure to manual review, file-saved external import to review, fileless manual draft, viewer rejection, idempotent replay, and unsafe Markdown rejection.

- [ ] **Step 4: Commit documentation**

```powershell
git add docs/superpowers/specs/2026-07-15-contract-manual-fallback-design.md docs/superpowers/plans/2026-07-15-contract-fallback-implementation.md docs/contract-fallback-acceptance-report.md
git commit -m "docs: record contract fallback acceptance"
```

- [ ] **Step 5: Deploy with the repository release workflow**

Package only committed tracked files, deploy to the configured production host, run database migration, restart the service, verify `/api/health` and public application load, then report the deployed commit. Do not push to public GitHub until the user gives the required explicit post-warning confirmation.

