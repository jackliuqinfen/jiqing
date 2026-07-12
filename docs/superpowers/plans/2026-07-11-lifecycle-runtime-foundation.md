# Lifecycle Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the first production-safe lifecycle runtime slice so project stages cannot be arbitrarily overwritten and every accepted transition is validated, versioned, idempotent, and auditable.

**Architecture:** Keep SQLite and the existing Python HTTP service for this slice. Add a focused lifecycle domain module and immutable event table, expose dedicated lifecycle APIs, and make the Vue project detail use backend-provided transition decisions. Existing `project_status` remains the compatibility projection until the later canonical-stage migration.

**Tech Stack:** Python 3 standard library, SQLite, `unittest`, Vue 3, TypeScript, Arco Design Vue, existing request helpers.

## Global Constraints

- No mock or example business data.
- Preserve the current settlement acceptance gate changes in `server/audit_api.py` and `SettlementManagementWizard.vue`.
- `project_records.project_status` is the current project lifecycle source of truth; `audit_stage` is an audit-subflow projection.
- Only adjacent forward transitions are supported in this slice. Backward correction remains a separate future workflow.
- Contract signing requires contract date, positive contract amount, both contract parties, and a current contract attachment.
- Starting audit requires the project to have reached `pending_submission` or a later audit stage and have a positive submitted amount.
- Every write is backend-authorized; frontend visibility is not an authorization control.
- Existing records are never assigned invented dates, amounts, payment terms, or responsible people.

---

### Task 1: Lifecycle policy and unit tests

**Files:**
- Create: `server/lifecycle.py`
- Create: `server/tests/__init__.py`
- Create: `server/tests/test_lifecycle.py`

**Interfaces:**
- Produces: `STAGE_ORDER`, `stage_label(stage)`, `next_stage(stage)`, `validate_adjacent_transition(current, target)`, `contract_gate_failures(project, has_contract_file)`, and `audit_start_failures(project)`.

- [ ] **Step 1: Write failing policy tests**

Cover adjacent transition acceptance, jump rejection, terminal-stage rejection, missing contract date/amount/parties/file, and audit-start rejection before `pending_submission`.

- [ ] **Step 2: Run the tests and confirm import failure**

Run: `python -m unittest server.tests.test_lifecycle -v`

Expected: FAIL because `server.lifecycle` does not exist.

- [ ] **Step 3: Implement the pure policy module**

Use this compatibility order:

```python
STAGE_ORDER = (
    "awarded",
    "contract_signed",
    "under_construction",
    "completed_acceptance",
    "pending_submission",
    "first_audit",
    "second_audit",
    "conclusion",
    "archived",
)
```

Return structured failures as dictionaries containing `code`, `field`, and `message`; do not raise HTTP-specific exceptions from the domain module.

- [ ] **Step 4: Run the policy tests**

Run: `python -m unittest server.tests.test_lifecycle -v`

Expected: all lifecycle policy tests pass.

### Task 2: SQLite lifecycle schema and repository service

**Files:**
- Modify: `server/schema.sql`
- Create: `server/migrations.py`
- Create: `server/lifecycle_repository.py`
- Create: `server/tests/test_lifecycle_repository.py`

**Interfaces:**
- Consumes: policy functions from `server.lifecycle`.
- Produces: `apply_pending_migrations(conn)`, `lifecycle_snapshot(conn, project_id)`, and `transition_project(conn, project_id, target_stage, expected_version, idempotency_key, reason, actor)`.

- [ ] **Step 1: Write repository tests with temporary SQLite**

Verify migration idempotency, success, blocker rollback, idempotent replay, stale-version conflict, one immutable event per transition, and no partial status update when event insertion fails.

- [ ] **Step 2: Add schema**

Add `lifecycle_version INTEGER NOT NULL DEFAULT 0` to `project_records` and add:

```sql
CREATE TABLE IF NOT EXISTS project_lifecycle_events (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  from_stage TEXT NOT NULL,
  to_stage TEXT NOT NULL,
  transition_type TEXT NOT NULL DEFAULT 'forward',
  reason TEXT DEFAULT '',
  idempotency_key TEXT NOT NULL,
  lifecycle_version INTEGER NOT NULL,
  actor_id TEXT DEFAULT '',
  actor_name TEXT DEFAULT '',
  payload_json TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE,
  UNIQUE (project_id, idempotency_key)
);
```

Register this as migration `2026071101_lifecycle_runtime` in `schema_migrations`, with checksum, started/finished timestamps and success state. Running startup twice must not reapply the migration. Do not modify or switch to PostgreSQL in this batch; the existing PostgreSQL DDL is incomplete and requires a separate full parity migration project.

- [ ] **Step 3: Implement transactional transition**

Use `BEGIN IMMEDIATE`, compare `expected_version`, run policy gates, conditionally update `project_records`, insert the event, and commit once. Return `{projectId, currentStage, currentStageLabel, lifecycleVersion, event}`. Replaying the same idempotency key returns the existing event result.

- [ ] **Step 4: Run repository tests**

Run: `python -m unittest server.tests.test_lifecycle_repository -v`

Expected: success, rollback, idempotency, and conflict tests pass.

### Task 3: Backend API and compatibility hardening

**Files:**
- Modify: `server/audit_api.py`
- Modify: `server/tests/test_lifecycle_api_contract.py`

**Interfaces:**
- Produces:
  - `GET /api/projects/:id/lifecycle`
  - `POST /api/projects/:id/lifecycle/validate`
  - `POST /api/projects/:id/lifecycle/transitions`

- [ ] **Step 1: Add API contract tests**

Test unauthenticated rejection, role rejection, validation response, successful transition, `409` stale version, `422` gate failure, and idempotent replay.

- [ ] **Step 2: Wire schema initialization and SQLite connection safety**

Call `apply_pending_migrations(conn)` during startup before lifecycle APIs are served. Configure `PRAGMA busy_timeout = 5000`. Do not change the current production DB path.

- [ ] **Step 3: Add lifecycle handlers and routes**

Lifecycle snapshot returns current stage, version, next transition, blocker list, and recent events. Transition requires `admin` or `editor`, `toStage`, `expectedVersion`, and `idempotencyKey`.

- [ ] **Step 4: Harden existing writes**

When `update_project_record()` receives a different `projectStatus`, reject it with `422` and direct the caller to the lifecycle transition endpoint. Add the same server-side audit-start gate to `start_project_audit()`. Keep all current settlement validation changes intact.

- [ ] **Step 5: Remove invented migration facts**

In `backfill_project_records()`, do not generate the payment term text `按合同约定节点付款`; preserve empty source values and leave uncertain facts for manual confirmation.

- [ ] **Step 6: Run backend tests and syntax verification**

Run:

```text
python -m unittest discover -s server/tests -v
python -m py_compile server/audit_api.py server/lifecycle.py server/lifecycle_repository.py
```

Expected: all tests pass and compilation exits with code 0.

### Task 4: Frontend lifecycle API and focused transition UI

**Files:**
- Create: `src/types/projectLifecycle.ts`
- Create: `src/api/projectLifecycle.ts`
- Create: `src/components/project/ProjectLifecycleStatus.vue`
- Create: `src/components/project/ProjectStageTransitionModal.vue`
- Modify: `src/views/ProjectManagementView.vue`

**Interfaces:**
- Consumes: lifecycle API contract from Task 3.
- Emits: `transitioned` with the updated lifecycle snapshot.

- [ ] **Step 1: Add TypeScript contracts and API helpers**

Define stage, blocker, event, snapshot, validate request, and transition request/response types. Generate the idempotency key with `crypto.randomUUID()` once per submission attempt.

- [ ] **Step 2: Build the status component**

Display current stage, lifecycle version, the next backend-provided stage, and a `推进阶段` command. Do not derive allowed transitions from a frontend stage array.

- [ ] **Step 3: Build the transition modal**

Use an Arco modal with current/target stage, backend blocker checklist, reason field, explicit confirmation sentence, locked submitting state, and retained input after network failure. Disable confirmation when blockers exist.

- [ ] **Step 4: Integrate with project detail**

Mount the lifecycle status beside the existing project status. On success, keep project detail open and refresh project detail, list, summary, work items, and lifecycle snapshot. Replace the edit-form status selector with a read-only label so normal edits cannot bypass lifecycle APIs.

- [ ] **Step 5: Verify frontend build**

Run: `npm.cmd run build`

Expected: `vue-tsc` and Vite finish with exit code 0; only the already-known upstream Arco CSS minify warnings may remain.

### Task 5: End-to-end acceptance and release readiness

**Files:**
- Create: `docs/lifecycle-runtime-acceptance-report.md`

- [ ] **Step 1: Exercise the first real transition on a temporary database**

Create a project with contract facts and a current contract attachment, validate `awarded -> contract_signed`, execute it, retry with the same idempotency key, and verify one event row.

- [ ] **Step 2: Verify critical rejections**

Confirm missing contract attachment returns `422`, stale version returns `409`, direct status update returns `422`, and audit start before `pending_submission` returns `422`.

- [ ] **Step 3: Re-run the full verification set**

Run backend tests, Python compilation, and `npm.cmd run build`. Record exact command outputs and known warnings in the acceptance report.

- [ ] **Step 4: Review scope before deployment**

Inspect Git status and diff. Stage only lifecycle files plus the already-reviewed settlement gate and design document when explicitly releasing; do not include unrelated `design-audits/`, `reports/`, or generated archives.
