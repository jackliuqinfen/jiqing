# Stage Form Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the field-list-first admin experience with a versioned, Tencent-Questionnaire-style stage form builder whose required/optional rules are controlled by authorized business configurators and honored by runtime submissions and lifecycle gates.

**Architecture:** Add a separate form-template bounded context beside the legacy audit field configuration: versioned SQLite/PostgreSQL persistence, pure schema validation/evaluation, repositories, an authenticated API adapter, and a typed runtime submission service. The Vue frontend consumes that API through a dedicated store and focused builder components; legacy field configuration becomes an advanced field library and display settings remain separate.

**Tech Stack:** Vue 3.5.13, TypeScript 5.7.3, Pinia 2.3.0, Arco Design Vue 2.58.0, SortableJS 1.15.6, Python standard library HTTP server, SQLite, mirrored PostgreSQL DDL, Python `unittest`, Node built-in test runner.

## Global Constraints

- Do not add frontend or Python dependencies; reuse Arco Design, Pinia, SortableJS, Python stdlib, and existing request/auth helpers.
- First version supports exactly `company` standard templates and `project_type` overrides; no single-project form overrides.
- Every field, including a protected core field, can be required or optional; a visible optional field with an empty value must not block submission or lifecycle advancement.
- Protected core placements cannot be removed from their applicable stage template and system field definitions cannot change semantic key, type, unit, precision, or binding.
- Fixed lifecycle stage order and document/file gates remain protected; only field-value gates become template-aware.
- A project-type published template overrides the company template for the same stage; if no applicable published template exists, retain legacy runtime gates until a template is explicitly published.
- New fields default to optional.
- Hidden or role-inaccessible fields do not participate in required validation and are not accepted through the API.
- Published versions are immutable; started submissions keep their bound version; rollback copies an old version into a new draft and republishes it.
- Preserve real empty states and never seed mock projects, fake impact counts, or example business records.
- Keep `schema.sql`, `postgres_schema.sql`, and versioned SQLite migrations behaviorally equivalent.
- Preserve unrelated dirty-worktree files and stage only files named by the current task.

---

## File Map

### Backend domain and persistence

- `server/migrations.py`: ordered SQLite migration and checksum for form-template tables and `project_records.project_type`.
- `server/schema.sql`: canonical SQLite cold-start schema.
- `server/postgres_schema.sql`: PostgreSQL parity schema.
- `server/form_template_domain.py`: pure schema normalization, dependency validation, visibility evaluation, and typed-value validation.
- `server/form_template_repository.py`: draft/version transactions, scope resolution, optimistic locking, and legacy draft seeding.
- `server/form_template_api.py`: authenticated admin and runtime HTTP routes.
- `server/stage_form_service.py`: bind a project stage to a published version and save/submit typed values.
- `server/lifecycle.py`: field gates accept a required-semantic-key set while retaining file and stage-order gates.
- `server/lifecycle_repository.py`: resolve template requirements before lifecycle validation/transition.
- `server/audit_api.py`: mount `FormTemplateApi`, persist `projectType`, and expose operation-log callbacks.

### Backend tests

- `server/tests/test_form_template_migrations.py`: SQLite/PostgreSQL schema parity and migration idempotency.
- `server/tests/test_form_template_domain.py`: schema, cycle, role, visibility, and typed-value rules.
- `server/tests/test_form_template_repository.py`: draft revisions, publish immutability, fallback resolution, and legacy seed behavior.
- `server/tests/test_form_template_api_contract.py`: auth, admin/editor permissions, validation, preview, publish, versions, and error payloads.
- `server/tests/test_project_type_api_contract.py`: dedicated project-type persistence through project create/read API.
- `server/tests/test_stage_form_service.py`: version binding, typed values, optional/required behavior, and idempotent submit.
- `server/tests/test_lifecycle.py`: template-aware pure gate functions.
- `server/tests/test_lifecycle_repository.py`: published-template requirements versus legacy fallback.
- `server/tests/test_lifecycle_api_contract.py`: API-level transition regression.

### Frontend model and state

- `src/types/formTemplate.ts`: stable API/domain types.
- `src/api/formTemplates.ts`: authenticated form-template and stage-form client.
- `src/utils/formTemplateDesigner.ts`: pure immutable builder operations and local validation.
- `src/store/formTemplates.ts`: list/draft loading, autosave state, preview, publish, and version actions.
- `test/formTemplateDesigner.test.ts`: pure designer-state tests.
- `test/formTemplateValidation.test.ts`: local validation and visibility tests.

### Frontend screens and components

- `src/views/admin/AdminFormTemplates.vue`: company/project-type/stage template list.
- `src/views/admin/AdminFormTemplateBuilder.vue`: top context plus three-column orchestration.
- `src/components/form-builder/FormBuilderPalette.vue`: add common/system fields and layout blocks.
- `src/components/form-builder/FormBuilderOutline.vue`: section/field outline, keyboard reorder, required toggle.
- `src/components/form-builder/FormBuilderCanvas.vue`: WYSIWYG form canvas.
- `src/components/form-builder/FormFieldProperties.vue`: business-language field properties only.
- `src/components/form-builder/FormConditionEditor.vue`: no-script `all`/`any` condition groups.
- `src/components/form-builder/FormPreviewDrawer.vue`: role-scoped, no-write filling preview.
- `src/components/form-builder/FormPublishDialog.vue`: validation and business-language change summary.
- `src/components/form-builder/FormVersionDrawer.vue`: immutable version history and copy-to-draft.
- `src/views/admin/AdminDisplayFieldSettings.vue`: card/table/detail/Gantt display flags and width.
- `src/views/admin/AdminFieldConfigs.vue`: renamed advanced system field library; remove form-required/display responsibilities.
- `src/router/index.ts`, `src/views/AppLayout.vue`, `src/store/auth.ts`: editor/admin access and navigation.
- `src/types/index.ts`, `src/api/projects.ts`, `src/views/ProjectManagementView.vue`: dedicated `projectType` persistence.

---

### Task 1: Add form-template persistence and project type

**Files:**
- Modify: `server/migrations.py`
- Modify: `server/schema.sql`
- Modify: `server/postgres_schema.sql`
- Create: `server/tests/test_form_template_migrations.py`

**Interfaces:**
- Produces tables: `form_field_definitions`, `form_templates`, `form_template_drafts`, `form_template_versions`, `stage_form_submissions`, `stage_form_submission_values`.
- Produces column: `project_records.project_type TEXT NOT NULL DEFAULT ''`.
- Produces migration constants: `FORM_TEMPLATES_MIGRATION`, `FORM_TEMPLATES_CHECKSUM`.

- [ ] **Step 1: Write the failing migration tests**

```python
from server.migrations import FORM_TEMPLATES_MIGRATION, apply_pending_migrations

EXPECTED = {
    "form_field_definitions",
    "form_templates",
    "form_template_drafts",
    "form_template_versions",
    "stage_form_submissions",
    "stage_form_submission_values",
}

def test_form_template_migration_creates_tables_and_project_type(self):
    apply_pending_migrations(self.conn)
    tables = {
        row["name"]
        for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    self.assertTrue(EXPECTED.issubset(tables))
    columns = {
        row["name"]
        for row in self.conn.execute("PRAGMA table_info(project_records)")
    }
    self.assertIn("project_type", columns)
    recorded = self.conn.execute(
        "SELECT success FROM schema_migrations WHERE version = ?",
        (FORM_TEMPLATES_MIGRATION,),
    ).fetchone()
    self.assertEqual(recorded["success"], 1)
```

- [ ] **Step 2: Run the migration test and verify the missing constant/table failure**

Run:

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_migrations -v
```

Expected: `ERROR` importing `FORM_TEMPLATES_MIGRATION` or `FAIL` because the tables do not exist.

- [ ] **Step 3: Add the ordered SQLite migration and canonical DDL**

Add a migration with version `20260720_form_templates_v1`. Use the same columns in both canonical schemas; PostgreSQL changes only JSON/timestamp types and foreign-key syntax.

```python
FORM_TEMPLATES_MIGRATION = "20260720_form_templates_v1"

_FORM_TEMPLATE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS form_field_definitions (
      id TEXT PRIMARY KEY,
      semantic_key TEXT NOT NULL UNIQUE,
      default_label TEXT NOT NULL,
      field_type TEXT NOT NULL,
      value_type TEXT NOT NULL,
      binding TEXT NOT NULL DEFAULT '',
      option_group TEXT NOT NULL DEFAULT '',
      unit TEXT NOT NULL DEFAULT '',
      precision_scale INTEGER NOT NULL DEFAULT 0,
      system_managed INTEGER NOT NULL DEFAULT 0,
      protected_core INTEGER NOT NULL DEFAULT 0,
      enabled INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS form_templates (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      scope_type TEXT NOT NULL CHECK (scope_type IN ('company', 'project_type')),
      scope_key TEXT NOT NULL DEFAULT '',
      stage_key TEXT NOT NULL,
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE(scope_type, scope_key, stage_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS form_template_drafts (
      template_id TEXT PRIMARY KEY,
      base_version_no INTEGER NOT NULL DEFAULT 0,
      revision INTEGER NOT NULL DEFAULT 1,
      schema_json TEXT NOT NULL,
      updated_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (template_id) REFERENCES form_templates(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS form_template_versions (
      id TEXT PRIMARY KEY,
      template_id TEXT NOT NULL,
      version_no INTEGER NOT NULL,
      schema_json TEXT NOT NULL,
      change_summary_json TEXT NOT NULL,
      published_by TEXT NOT NULL,
      published_by_name TEXT NOT NULL,
      published_at TEXT NOT NULL,
      UNIQUE(template_id, version_no),
      FOREIGN KEY (template_id) REFERENCES form_templates(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stage_form_submissions (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL,
      stage_key TEXT NOT NULL,
      template_version_id TEXT NOT NULL,
      status TEXT NOT NULL CHECK (status IN ('draft', 'submitted')),
      revision INTEGER NOT NULL DEFAULT 1,
      submit_idempotency_key TEXT NOT NULL DEFAULT '',
      submitted_by TEXT NOT NULL DEFAULT '',
      submitted_by_name TEXT NOT NULL DEFAULT '',
      submitted_at TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE(project_id, stage_key),
      FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE,
      FOREIGN KEY (template_version_id) REFERENCES form_template_versions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stage_form_submission_values (
      submission_id TEXT NOT NULL,
      field_definition_id TEXT NOT NULL,
      value_type TEXT NOT NULL,
      text_value TEXT,
      integer_value INTEGER,
      decimal_value TEXT,
      date_value TEXT,
      boolean_value INTEGER,
      json_value TEXT,
      source TEXT NOT NULL DEFAULT 'manual',
      updated_at TEXT NOT NULL,
      PRIMARY KEY (submission_id, field_definition_id),
      FOREIGN KEY (submission_id) REFERENCES stage_form_submissions(id) ON DELETE CASCADE,
      FOREIGN KEY (field_definition_id) REFERENCES form_field_definitions(id)
    )
    """,
)
```

Add `ALTER TABLE project_records ADD COLUMN project_type TEXT NOT NULL DEFAULT ''` in a prepare function guarded by `_column_exists`. Add the same column to both canonical schemas and add indexes on `(scope_type, scope_key, stage_key)`, `template_id`, and `(project_id, stage_key)`.

- [ ] **Step 4: Run migration and existing migration suites**

Run:

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_migrations server.tests.test_document_migrations -v
```

Expected: all tests pass; repeated `apply_pending_migrations` records `20260720_form_templates_v1` exactly once and `PRAGMA foreign_key_check` returns no rows.

- [ ] **Step 5: Commit the persistence boundary**

```bash
git add server/migrations.py server/schema.sql server/postgres_schema.sql server/tests/test_form_template_migrations.py
git commit -m "feat: add form template persistence"
```

---

### Task 2: Implement pure template schema and validation rules

**Files:**
- Create: `server/form_template_domain.py`
- Create: `server/tests/test_form_template_domain.py`

**Interfaces:**
- Produces: `empty_schema() -> dict`.
- Produces: `normalize_schema(schema: dict) -> dict`.
- Produces: `validate_schema(schema: dict, definitions: dict[str, dict], active_roles: set[str]) -> list[dict]`.
- Produces: `visible_placements(schema: dict, values: dict, actor_roles: set[str]) -> list[dict]`.
- Produces: `validate_submission(schema, definitions, values, actor_roles) -> list[dict]`.
- Produces error dict shape: `{code, fieldId, message}`.

- [ ] **Step 1: Write failing tests for optional core fields, hidden required fields, and condition cycles**

```python
def test_core_field_can_be_optional():
    schema = sample_schema(required=False, semantic_key="contract.amount")
    blockers = validate_schema(schema, definitions(), {"editor"})
    self.assertEqual(blockers, [])

def test_hidden_required_field_does_not_block_submission():
    schema = conditional_schema(required=True, expected="yes")
    blockers = validate_submission(
        schema,
        definitions(),
        {"hasContract": "no", "contractAmount": ""},
        {"editor"},
    )
    self.assertEqual(blockers, [])

def test_condition_cycle_is_rejected():
    blockers = validate_schema(cyclic_schema(), definitions(), {"editor"})
    self.assertEqual(blockers[0]["code"], "display_rule_cycle")
```

- [ ] **Step 2: Run tests and verify the module-not-found failure**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_domain -v
```

Expected: `ModuleNotFoundError: No module named 'server.form_template_domain'`.

- [ ] **Step 3: Implement the `stage-form.v1` schema contract**

```python
SCHEMA_VERSION = "stage-form.v1"
FIELD_TYPES = frozenset({
    "text", "textarea", "number", "money", "date", "select",
    "multi_select", "person", "boolean", "attachment",
})
CONDITION_OPERATORS = frozenset({"eq", "neq", "contains", "empty", "not_empty"})

def empty_schema():
    return {"schemaVersion": SCHEMA_VERSION, "sections": []}

def validate_submission(schema, definitions, values, actor_roles):
    blockers = []
    visible = visible_placements(schema, values, actor_roles)
    for placement in visible:
        if placement.get("required") and _is_empty(values.get(placement["fieldId"])):
            blockers.append({
                "code": "required_field_missing",
                "fieldId": placement["fieldId"],
                "message": f"请填写{placement['label']}。",
            })
        blockers.extend(_validate_typed_value(placement, definitions, values))
    return blockers
```

`validate_schema` must reject duplicate placement IDs, missing field definitions, deletion of `protected_core` placements inherited into the draft, invalid role names, references to removed fields, and cyclic display-rule dependencies. It must not create a blocker solely because a protected core placement has `required=False`.

- [ ] **Step 4: Run the domain tests**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_domain -v
```

Expected: all tests pass, including `all`/`any`, `eq`/`neq`/`contains`/`empty`/`not_empty`, role visibility, and money/date/boolean value validation.

- [ ] **Step 5: Commit the domain rules**

```bash
git add server/form_template_domain.py server/tests/test_form_template_domain.py
git commit -m "feat: validate stage form schemas"
```

---

### Task 3: Add template repository, versioning, scope resolution, and legacy draft seed

**Files:**
- Create: `server/form_template_repository.py`
- Create: `server/tests/test_form_template_repository.py`
- Modify: `server/audit_api.py:1232-1248`

**Interfaces:**
- Consumes: `normalize_schema`, `validate_schema` from Task 2.
- Produces: `list_templates(conn)`, `create_template(conn, ...)`, `get_or_create_draft(conn, template_id, actor)`, `save_draft(conn, template_id, schema, expected_revision, actor)`, `publish_draft(conn, template_id, expected_revision, actor)`, `list_versions(conn, template_id)`, `copy_version_to_draft(conn, template_id, version_id, actor)`, `resolve_published_version(conn, stage_key, project_type)`.
- Produces errors: `TemplateNotFoundError`, `DraftRevisionConflictError`, `TemplateValidationError`, `ProtectedPlacementRemovedError`.

- [ ] **Step 1: Write failing repository tests**

```python
def test_project_type_version_overrides_company_version(self):
    company = publish(self.conn, scope_type="company", scope_key="", stage="contract_signed")
    typed = publish(self.conn, scope_type="project_type", scope_key="房建", stage="contract_signed")
    resolved = resolve_published_version(self.conn, "contract_signed", "房建")
    self.assertEqual(resolved["id"], typed["id"])
    self.assertNotEqual(resolved["id"], company["id"])

def test_stale_draft_revision_is_rejected(self):
    with self.assertRaises(DraftRevisionConflictError):
        save_draft(self.conn, self.template_id, empty_schema(), 0, self.actor)

def test_legacy_fields_create_unpublished_company_drafts_only(self):
    seed_legacy_field_drafts(self.conn, self.actor)
    self.assertGreater(self.conn.execute("SELECT COUNT(*) FROM form_template_drafts").fetchone()[0], 0)
    self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM form_template_versions").fetchone()[0], 0)
```

- [ ] **Step 2: Run tests and verify repository import failure**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_repository -v
```

Expected: import failure for `server.form_template_repository`.

- [ ] **Step 3: Implement transactions and immutable publish**

```python
def resolve_published_version(conn, stage_key, project_type):
    scopes = []
    if str(project_type or "").strip():
        scopes.append(("project_type", str(project_type).strip()))
    scopes.append(("company", ""))
    for scope_type, scope_key in scopes:
        row = conn.execute(
            """
            SELECT v.* FROM form_template_versions v
            JOIN form_templates t ON t.id = v.template_id
            WHERE t.scope_type = ? AND t.scope_key = ? AND t.stage_key = ?
            ORDER BY v.version_no DESC LIMIT 1
            """,
            (scope_type, scope_key, stage_key),
        ).fetchone()
        if row:
            return _version_payload(row)
    return None
```

`save_draft` must update with `WHERE template_id = ? AND revision = ?`, increment `revision`, and raise `DraftRevisionConflictError` if `rowcount != 1`. `publish_draft` must validate inside `BEGIN IMMEDIATE`, insert version `MAX(version_no)+1`, leave the version row immutable, update the draft base version/revision, and return a business-language change summary.

`seed_legacy_field_drafts` must map existing `visible_in_form=1` rows by `stage_key`, create/reuse `FieldDefinition` rows, preserve legacy `required` as draft initial state, and never publish automatically. It creates a migrated company draft only when that scope/stage has no template, draft, or version; subsequent boots must never rewrite an administrator-edited draft. If `stage_key` or binding is ambiguous, skip that field and return a named `unresolved` list; do not infer from labels.

- [ ] **Step 4: Mount the legacy draft seed during bootstrap without mock data**

Call `seed_legacy_field_drafts(conn, {"id": "system", "name": "系统迁移"})` after `seed_field_configs(conn)` and before commit. The seed must be idempotent by the unique template scope/stage key and must return the same unchanged draft revision on a second bootstrap.

- [ ] **Step 5: Run repository and migration tests**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_repository server.tests.test_form_template_migrations -v
```

Expected: all tests pass; versions remain unchanged after draft edits and legacy seed creates no published version.

- [ ] **Step 6: Commit the repository boundary**

```bash
git add server/form_template_repository.py server/tests/test_form_template_repository.py server/audit_api.py
git commit -m "feat: add form template repository"
```

---

### Task 4: Expose authenticated form-template admin APIs

**Files:**
- Create: `server/form_template_api.py`
- Create: `server/tests/test_form_template_api_contract.py`
- Modify: `server/audit_api.py:41-42,4106-4135,4298-4410`

**Interfaces:**
- Consumes Task 3 repository functions.
- Produces routes:
  - `GET /api/form-template-meta`
  - `GET /api/form-field-definitions`
  - `GET|POST /api/form-templates`
  - `GET|PUT /api/form-templates/{id}/draft`
  - `POST /api/form-templates/{id}/validate`
  - `POST /api/form-templates/{id}/preview`
  - `POST /api/form-templates/{id}/publish`
  - `GET /api/form-templates/{id}/versions`
  - `POST /api/form-templates/{id}/versions/{versionId}/copy`
- Admin and editor can read/write/publish; viewer receives `403`.

- [ ] **Step 1: Write API contract tests for auth, revisions, validation, and publish**

```python
def test_editor_can_publish_optional_core_field(self):
    template_id = self.create_template(user_id="editor-user")
    draft = self.get(f"/api/form-templates/{template_id}/draft", "editor-user")[1]["data"]
    schema = draft["schema"]
    schema["sections"][0]["fields"][0]["required"] = False
    status, _ = self.put(
        f"/api/form-templates/{template_id}/draft",
        {"schema": schema, "expectedRevision": draft["revision"]},
        "editor-user",
    )
    self.assertEqual(status, 200)
    status, payload = self.post(
        f"/api/form-templates/{template_id}/publish",
        {"expectedRevision": draft["revision"] + 1},
        "editor-user",
    )
    self.assertEqual(status, 200)
    self.assertFalse(payload["data"]["schema"]["sections"][0]["fields"][0]["required"])

def test_viewer_cannot_save_draft(self):
    status, payload = self.put("/api/form-templates/t1/draft", {}, "viewer-user")
    self.assertEqual(status, 403)
    self.assertEqual(payload["code"], "form_template_write_forbidden")
```

- [ ] **Step 2: Run tests and verify route 404 failures**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_api_contract -v
```

Expected: requests return `404` because routes are not mounted.

- [ ] **Step 3: Implement `FormTemplateApi` with structured error responses**

```python
WRITE_ROLES = frozenset({"admin", "editor"})

class FormTemplateApiError(RuntimeError):
    def __init__(self, status, code, message, **details):
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

def _error(self, exc):
    self.handler.respond(exc.status, {
        "success": False,
        "error": exc.message,
        "code": exc.code,
        **exc.details,
    })
```

The meta route returns real stages from `STAGES`, active roles from `system_users`, and distinct non-empty `project_records.project_type` values. Preview calls domain validation/evaluation only and must assert that counts for `stage_form_submissions` and lifecycle events remain unchanged.

- [ ] **Step 4: Mount GET/POST/PUT dispatch before legacy route chains**

Add `mounted_form_template_api` beside `mounted_document_api`. Check `FormTemplateApi.is_route(method, path)` before generic `/api/audit/*` authentication and before `read_json` is consumed by legacy handlers.

- [ ] **Step 5: Run API and operation-log tests**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_api_contract server.tests.test_lifecycle_api_contract -v
```

Expected: all tests pass; publish and copy actions create `system_operation_logs` rows with `form_template.publish` and `form_template.version.copy`.

- [ ] **Step 6: Commit the admin API**

```bash
git add server/form_template_api.py server/tests/test_form_template_api_contract.py server/audit_api.py
git commit -m "feat: expose form template APIs"
```

---

### Task 5: Bind runtime stage forms and store typed values

**Files:**
- Create: `server/stage_form_service.py`
- Create: `server/tests/test_stage_form_service.py`
- Modify: `server/form_template_api.py`

**Interfaces:**
- Produces: `get_stage_form(conn, project_id, stage_key, actor_roles)`.
- Produces: `save_stage_form_draft(conn, project_id, stage_key, values, expected_revision, actor)`.
- Produces: `submit_stage_form(conn, project_id, stage_key, values, expected_revision, idempotency_key, actor)`.
- Produces routes:
  - `GET /api/projects/{projectId}/stages/{stageKey}/form`
  - `PUT /api/projects/{projectId}/stages/{stageKey}/form/draft`
  - `POST /api/projects/{projectId}/stages/{stageKey}/form/submit`

- [ ] **Step 1: Write failing tests for version binding and typed optional values**

```python
def test_started_submission_keeps_original_template_version(self):
    first = publish_template(self.conn, required=False)
    form = get_stage_form(self.conn, "project-1", "contract_signed", {"editor"})
    publish_template(self.conn, required=True)
    again = get_stage_form(self.conn, "project-1", "contract_signed", {"editor"})
    self.assertEqual(form["templateVersionId"], first["id"])
    self.assertEqual(again["templateVersionId"], first["id"])

def test_optional_money_can_be_empty(self):
    result = submit_stage_form(
        self.conn,
        "project-1",
        "contract_signed",
        {"contractAmount": ""},
        expected_revision=1,
        idempotency_key="submit-1",
        actor=self.actor,
    )
    self.assertEqual(result["status"], "submitted")

def test_same_idempotency_key_returns_original_submit_result(self):
    first = submit_stage_form(
        self.conn, "project-1", "contract_signed", {}, 1, "submit-1", self.actor
    )
    repeated = submit_stage_form(
        self.conn, "project-1", "contract_signed", {}, 1, "submit-1", self.actor
    )
    self.assertEqual(repeated, first)

def test_different_key_cannot_replace_submitted_values(self):
    submit_stage_form(
        self.conn, "project-1", "contract_signed", {}, 1, "submit-1", self.actor
    )
    with self.assertRaises(SubmissionAlreadyFinalError):
        submit_stage_form(
            self.conn, "project-1", "contract_signed", {}, 1, "submit-2", self.actor
        )
```

- [ ] **Step 2: Run tests and verify missing service failure**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_stage_form_service -v
```

Expected: import failure for `server.stage_form_service`.

- [ ] **Step 3: Implement version binding and typed writes**

```python
VALUE_COLUMNS = {
    "text": "text_value",
    "date": "date_value",
    "boolean": "boolean_value",
    "integer": "integer_value",
    "decimal": "decimal_value",
    "json": "json_value",
}

def _value_row(submission_id, definition, raw_value, now):
    value_type, encoded = encode_typed_value(definition, raw_value)
    columns = {name: None for name in VALUE_COLUMNS.values()}
    columns[VALUE_COLUMNS[value_type]] = encoded
    return {
        "submission_id": submission_id,
        "field_definition_id": definition["id"],
        "value_type": value_type,
        **columns,
        "source": "manual",
        "updated_at": now,
    }
```

Create the submission on first GET using the currently resolved published version, then always reuse its `template_version_id`. Save only fields visible to the actor role. On final submit, evaluate display conditions server-side, reject only visible required missing fields, and delete stored values for fields that are no longer visible.

For money, store integer fen in `integer_value`; dates use ISO `YYYY-MM-DD`; booleans use `0/1`; multi-select/person-reference arrays use canonical JSON in `json_value`.

- [ ] **Step 4: Add runtime routes and idempotent submission**

Use `Idempotency-Key` or body `idempotencyKey` and persist it as `submit_idempotency_key` on the submission row. Once submitted, the same key returns the original submission payload without rewriting values; a different key returns `submission_already_final` and cannot replace the submitted values. The submission primary key remains the single project/stage business boundary in version 1.

- [ ] **Step 5: Run service and API contract tests**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_stage_form_service server.tests.test_form_template_api_contract -v
```

Expected: all tests pass; typed columns are populated exclusively and preview writes remain zero.

- [ ] **Step 6: Commit runtime forms**

```bash
git add server/stage_form_service.py server/form_template_api.py server/tests/test_stage_form_service.py server/tests/test_form_template_api_contract.py
git commit -m "feat: run versioned stage forms"
```

---

### Task 6: Make lifecycle field gates template-aware

**Files:**
- Modify: `server/lifecycle.py:82-134`
- Modify: `server/lifecycle_repository.py:17-170`
- Modify: `server/tests/test_lifecycle.py`
- Modify: `server/tests/test_lifecycle_repository.py`
- Modify: `server/tests/test_lifecycle_api_contract.py`

**Interfaces:**
- Consumes: `resolve_published_version` from Task 3.
- Produces: `required_semantic_keys_for_project_stage(conn, project, stage_key) -> set[str] | None`.
- Changes: `contract_gate_failures(project, has_contract_file, required_semantic_keys=None)`.
- Changes: `audit_start_failures(project, required_semantic_keys=None)`.
- `None` means legacy field gates; an empty set means no field-value gates.

- [ ] **Step 1: Write failing pure and repository tests**

```python
def test_optional_contract_fields_do_not_block_but_contract_file_still_does(self):
    failures = contract_gate_failures(
        {},
        has_contract_file=False,
        required_semantic_keys=set(),
    )
    self.assertEqual(
        [(item["code"], item["field"]) for item in failures],
        [("contract_file_required", "contractFile")],
    )

def test_no_published_template_uses_legacy_contract_field_gates(self):
    blockers = lifecycle_snapshot(self.conn, "project-empty-contract")["blockers"]
    self.assertIn("contract_amount_required", {item["code"] for item in blockers})
```

- [ ] **Step 2: Run lifecycle tests and verify signature/behavior failure**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_lifecycle server.tests.test_lifecycle_repository server.tests.test_lifecycle_api_contract -v
```

Expected: the new optional-template tests fail because field gates are hard-coded.

- [ ] **Step 3: Gate only semantic keys marked required by the published template**

```python
CONTRACT_FIELD_RULES = (
    ("contract.signed_date", "contract_date", "contractDate", "contract_date_required", "签订合同前必须填写合同日期。"),
    ("contract.amount", "contract_amount", "contractAmount", "contract_amount_required", "签订合同前必须填写大于 0 的合同金额。"),
    ("party.owner", "owner_unit", "ownerUnit", "owner_unit_required", "签订合同前必须填写建设单位。"),
    ("party.contractor", "construction_unit", "constructionUnit", "construction_unit_required", "签订合同前必须填写施工单位。"),
)

def _required(required_semantic_keys, semantic_key):
    return required_semantic_keys is None or semantic_key in required_semantic_keys
```

Keep `contract_file_required`, adjacent-stage validation, audit-link checks, and document gates independent of form-field required state. Map `audit.submitted_amount` to the existing submitted-amount gate.

- [ ] **Step 4: Resolve requirements inside lifecycle repository transactions**

Parse the resolved immutable schema and return only placement semantic keys with `required=True`. If no published template exists, return `None` so existing projects keep legacy safety. Use the same helper for snapshot, validate, and transition to avoid inconsistent gates.

- [ ] **Step 5: Run lifecycle regression suites**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_lifecycle server.tests.test_lifecycle_repository server.tests.test_lifecycle_api_contract -v
```

Expected: all tests pass; optional core values no longer block after a template is published, while fixed order and contract-file/audit-link gates still block.

- [ ] **Step 6: Commit template-aware lifecycle rules**

```bash
git add server/lifecycle.py server/lifecycle_repository.py server/tests/test_lifecycle.py server/tests/test_lifecycle_repository.py server/tests/test_lifecycle_api_contract.py
git commit -m "feat: honor template required fields in lifecycle"
```

---

### Task 7: Add frontend types, API client, pure designer operations, and store

**Files:**
- Create: `src/types/formTemplate.ts`
- Create: `src/api/formTemplates.ts`
- Create: `src/utils/formTemplateDesigner.ts`
- Create: `src/store/formTemplates.ts`
- Create: `test/formTemplateDesigner.test.ts`
- Create: `test/formTemplateValidation.test.ts`

**Interfaces:**
- Produces types: `FormTemplateSummary`, `FormTemplateDraft`, `FormTemplateSchema`, `FormSection`, `FormFieldPlacement`, `FormDisplayRule`, `FormTemplateVersion`, `FormValidationIssue`.
- Produces designer functions: `addPlacement`, `movePlacement`, `removePlacement`, `setRequired`, `updatePlacement`, `validateDesignerSchema`, `evaluateVisibility`.
- Store ID: `form-templates`.

- [ ] **Step 1: Write failing immutable designer tests**

```typescript
test('new fields default to optional and do not mutate the source schema', () => {
  const source = emptySchema()
  const next = addPlacement(source, 'section-1', definition('contract.amount'))
  assert.equal(next.sections[0].fields[0].required, false)
  assert.equal(source.sections[0].fields.length, 0)
})

test('required state stays addressable from outline and properties', () => {
  const next = setRequired(schemaWithField(), 'field-1', true)
  assert.equal(findPlacement(next, 'field-1')?.required, true)
})
```

- [ ] **Step 2: Run Node tests and verify missing-module failures**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --test test/formTemplateDesigner.test.ts test/formTemplateValidation.test.ts
```

Expected: module-not-found errors for `formTemplateDesigner.ts`.

- [ ] **Step 3: Define the exact TypeScript schema**

```typescript
export type FormScopeType = 'company' | 'project_type'
export type FormFieldType = 'text' | 'textarea' | 'number' | 'money' | 'date' | 'select' | 'multi_select' | 'person' | 'boolean' | 'attachment'

export interface FormCondition {
  sourceFieldId: string
  operator: 'eq' | 'neq' | 'contains' | 'empty' | 'not_empty'
  value?: unknown
}

export interface FormDisplayRule {
  mode: 'all' | 'any'
  conditions: FormCondition[]
}

export interface FormFieldPlacement {
  id: string
  fieldDefinitionId: string
  semanticKey: string
  label: string
  helpText: string
  required: boolean
  fillerRoles: string[]
  displayRule: FormDisplayRule | null
}

export interface FormTemplateSchema {
  schemaVersion: 'stage-form.v1'
  sections: Array<{ id: string; title: string; description: string; fields: FormFieldPlacement[] }>
}
```

- [ ] **Step 4: Implement the API client and Pinia store**

`src/api/formTemplates.ts` must reuse `getAuthToken`, parse structured error payloads, and export one function per backend route. The store keeps `templates`, `meta`, `fieldDefinitions`, `draft`, `saveState: 'idle'|'saving'|'saved'|'error'`, `validationIssues`, and `versions`.

Use a single `scheduleAutosave()` timer owned by the builder view; the store exposes only deterministic `saveDraft(expectedRevision)` and updates revision from the response.

- [ ] **Step 5: Run designer tests and type-check**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --test test/formTemplateDesigner.test.ts test/formTemplateValidation.test.ts
npm.cmd run build
```

Expected: Node tests pass and `vue-tsc`/Vite build exits `0`.

- [ ] **Step 6: Commit frontend domain/state**

```bash
git add src/types/formTemplate.ts src/api/formTemplates.ts src/utils/formTemplateDesigner.ts src/store/formTemplates.ts test/formTemplateDesigner.test.ts test/formTemplateValidation.test.ts
git commit -m "feat: add form builder frontend state"
```

---

### Task 8: Persist project type and add form-template access/navigation/list

**Files:**
- Modify: `server/audit_api.py:680-930,1377-1451,1680-1740,2850-2960`
- Modify: `src/types/index.ts:490-529`
- Modify: `src/api/projects.ts`
- Modify: `src/views/ProjectManagementView.vue:778-782,1528-1550,1880-1895,2100-2145`
- Modify: `src/store/auth.ts`
- Modify: `src/router/index.ts:75-145,160-195`
- Modify: `src/views/AppLayout.vue:210-280`
- Create: `src/views/admin/AdminFormTemplates.vue`
- Create: `server/tests/test_project_type_api_contract.py`

**Interfaces:**
- Produces `ProjectRecord.projectType: string` and API payload `projectType`.
- Produces `authStore.canConfigureForms`, true for admin or editor.
- Produces routes `/admin/form-templates` and `/admin/form-templates/:id/builder`.

- [ ] **Step 1: Add a failing API contract test for dedicated project type persistence**

```python
def test_project_type_is_persisted_as_a_column(self):
    status, payload = self.request(
        "POST",
        "/api/projects",
        {"projectName": "类型项目", "projectType": "房建"},
        "admin-user",
    )
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["projectType"], "房建")
    with audit_api.connect() as conn:
        row = conn.execute(
            "SELECT project_type, description FROM project_records WHERE id = ?",
            (payload["data"]["id"],),
        ).fetchone()
    self.assertEqual(row["project_type"], "房建")
    self.assertNotIn("项目类型：房建", row["description"] or "")
```

- [ ] **Step 2: Run the contract test and verify failure**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_project_type_api_contract -v
```

Expected: `FAIL` because `projectType` is missing from the response or `project_type` is empty in SQLite.

- [ ] **Step 3: Persist and return `project_type` without inferring historical values**

Add `project_type` to `project_columns_from_payload`, update columns, `project_record_payload`, and compatibility columns. Remove `appendProjectCreationNotes` usage for project type; keep project location behavior unchanged. Existing rows with empty `project_type` resolve company-standard templates and must not be backfilled from free-text descriptions.

- [ ] **Step 4: Generalize route permission and add template list**

```typescript
const canConfigureForms = computed(() => isAdmin.value || isEditor.value)

if (Array.isArray(to.meta.allowedRoles) && !to.meta.allowedRoles.includes(authStore.userRole)) {
  next({ name: 'HomeDashboard' })
  return
}
```

Remove `requiresAdmin` from the `/admin` parent route so its guard does not reject editor children. Put `requiresAdmin: true` explicitly on users, settings, logs, display-settings, and field-library routes. Set only the form-template list and builder routes to `meta: { allowedRoles: ['admin', 'editor'] }`. The AppLayout shows “表单管理” to `canConfigureForms` and does not expose unrelated admin links to editors.

`AdminFormTemplates.vue` lists only real company/project-type/stage rows, shows an honest empty state, and links edit actions to the builder route. Project-type choices come from `/api/form-template-meta` with an allow-create input, never hard-coded examples.

- [ ] **Step 5: Run API tests and frontend build**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_project_type_api_contract server.tests.test_form_template_api_contract -v
npm.cmd run build
```

Expected: project type round-trips through SQLite/API/UI types; editor can reach form templates but not user management; build exits `0`.

- [ ] **Step 6: Commit project type and navigation**

```bash
git add server/audit_api.py server/tests/test_project_type_api_contract.py src/types/index.ts src/api/projects.ts src/views/ProjectManagementView.vue src/store/auth.ts src/router/index.ts src/views/AppLayout.vue src/views/admin/AdminFormTemplates.vue
git commit -m "feat: add form template management entry"
```

---

### Task 9: Build the three-column form editor core

**Files:**
- Create: `src/views/admin/AdminFormTemplateBuilder.vue`
- Create: `src/components/form-builder/FormBuilderPalette.vue`
- Create: `src/components/form-builder/FormBuilderOutline.vue`
- Create: `src/components/form-builder/FormBuilderCanvas.vue`
- Create: `src/components/form-builder/FormFieldProperties.vue`
- Modify: `src/router/index.ts`
- Modify: `test/formTemplateDesigner.test.ts`

**Interfaces:**
- Palette emits `add-definition` and `add-layout-block`.
- Outline emits `select`, `move`, `toggle-required`, `rename-section`.
- Canvas emits `select`, `move`, `remove-custom-placement`.
- Properties emits `update-placement`.
- Builder owns autosave timer and selected placement ID.

- [ ] **Step 1: Extend failing designer tests for protected deletion and keyboard reorder**

```typescript
test('protected core placement cannot be removed but can become optional', () => {
  const source = schemaWithProtectedCore()
  assert.throws(() => removePlacement(source, 'core-1'), /protected_core/)
  assert.equal(findPlacement(setRequired(source, 'core-1', false), 'core-1')?.required, false)
})

test('keyboard move uses the same immutable operation as drag move', () => {
  const next = movePlacement(schemaWithThreeFields(), 'field-2', 'section-1', 0)
  assert.deepEqual(next.sections[0].fields.map(field => field.id), ['field-2', 'field-1', 'field-3'])
})
```

- [ ] **Step 2: Run tests and verify the protected/reorder tests fail**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --test test/formTemplateDesigner.test.ts
```

Expected: new assertions fail until operations enforce protected placement behavior.

- [ ] **Step 3: Implement component contracts with business-language properties**

The builder layout is:

```vue
<template>
  <div class="form-builder-page">
    <FormBuilderHeader
      :template="store.currentTemplate"
      :draft="store.draft"
      :save-state="store.saveState"
      @preview="previewVisible = true"
      @publish="publishVisible = true"
    />
    <div class="form-builder-grid">
      <FormBuilderPalette
        :definitions="store.fieldDefinitions"
        @add-definition="addDefinition"
      />
      <div class="form-builder-main">
        <FormBuilderOutline
          :schema="schema"
          :selected-id="selectedId"
          @select="selectedId = $event"
          @move="moveField"
          @toggle-required="toggleRequired"
        />
        <FormBuilderCanvas
          :schema="schema"
          :selected-id="selectedId"
          @select="selectedId = $event"
          @move="moveField"
        />
      </div>
      <FormFieldProperties
        :placement="selectedPlacement"
        :roles="store.meta.roles"
        @update-placement="updateSelected"
      />
    </div>
  </div>
</template>
```

The right panel exposes only label, help text, required, filler roles, display condition entry, and options for select fields. It must not render semantic key, binding, precision, table width, or visibility-in-card/table controls.

- [ ] **Step 4: Add autosave and accessible reorder**

Debounce autosave by 600 ms after a deterministic schema change. Display `正在保存 / 已保存 / 保存失败`. A save conflict freezes autosave and shows “配置已被其他人更新，请刷新后查看差异。”

Outline rows include labeled buttons “上移”“下移”“移入上一分组”“移入下一分组”; SortableJS drag calls the same `movePlacement` function.

- [ ] **Step 5: Run designer tests and build**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --test test/formTemplateDesigner.test.ts
npm.cmd run build
```

Expected: tests and build pass; no TypeScript error and no legacy technical property appears in `FormFieldProperties.vue`.

- [ ] **Step 6: Commit the editor core**

```bash
git add src/views/admin/AdminFormTemplateBuilder.vue src/components/form-builder src/router/index.ts test/formTemplateDesigner.test.ts
git commit -m "feat: build stage form editor"
```

---

### Task 10: Add display conditions, role preview, and no-write preview validation

**Files:**
- Create: `src/components/form-builder/FormConditionEditor.vue`
- Create: `src/components/form-builder/FormPreviewDrawer.vue`
- Modify: `src/components/form-builder/FormFieldProperties.vue`
- Modify: `src/views/admin/AdminFormTemplateBuilder.vue`
- Modify: `test/formTemplateValidation.test.ts`
- Modify: `server/tests/test_form_template_api_contract.py`

**Interfaces:**
- `FormConditionEditor` emits a complete `FormDisplayRule | null`.
- `FormPreviewDrawer` accepts schema, definitions, role, and local values; it never calls draft/save/submit endpoints.
- Backend preview returns `{visibleFields, validationIssues}` and writes nothing.

- [ ] **Step 1: Add failing visibility tests**

```typescript
test('any mode shows a field when one condition matches', () => {
  const rule = {
    mode: 'any' as const,
    conditions: [
      { sourceFieldId: 'a', operator: 'eq' as const, value: 'yes' },
      { sourceFieldId: 'b', operator: 'not_empty' as const },
    ],
  }
  assert.equal(evaluateDisplayRule(rule, { a: 'no', b: 'value' }), true)
})

test('field hidden from selected role is excluded from required issues', () => {
  const issues = validatePreview(roleRestrictedSchema(), {}, ['viewer'])
  assert.deepEqual(issues, [])
})
```

- [ ] **Step 2: Run frontend/backend preview tests and verify failures**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --test test/formTemplateValidation.test.ts
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_api_contract -v
```

Expected: new visibility tests or no-write preview assertion fails.

- [ ] **Step 3: Implement business-language conditions**

Render controls in this order: source field, operator, value when required, “全部满足/任一满足”, add condition, remove condition. Exclude the current field from source choices. Disable removed/unsupported sources and show an inline error that blocks publish.

Operator copy:

```typescript
export const conditionOperatorOptions = [
  { label: '等于', value: 'eq' },
  { label: '不等于', value: 'neq' },
  { label: '包含', value: 'contains' },
  { label: '为空', value: 'empty' },
  { label: '不为空', value: 'not_empty' },
]
```

- [ ] **Step 4: Implement role-scoped preview with explicit no-write copy**

The drawer header shows “预览模式，不会保存业务数据”. Role selection recalculates visible fields locally and may optionally call backend `/preview` for parity validation; it must never call stage-form draft or submit routes. Add a backend contract test that snapshots submission/event counts before and after preview.

- [ ] **Step 5: Run tests and build**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --test test/formTemplateValidation.test.ts
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_api_contract -v
npm.cmd run build
```

Expected: all pass; preview creates zero database rows.

- [ ] **Step 6: Commit conditions and preview**

```bash
git add src/components/form-builder/FormConditionEditor.vue src/components/form-builder/FormPreviewDrawer.vue src/components/form-builder/FormFieldProperties.vue src/views/admin/AdminFormTemplateBuilder.vue test/formTemplateValidation.test.ts server/tests/test_form_template_api_contract.py
git commit -m "feat: preview conditional stage forms"
```

---

### Task 11: Add publish summary and immutable version history

**Files:**
- Create: `src/components/form-builder/FormPublishDialog.vue`
- Create: `src/components/form-builder/FormVersionDrawer.vue`
- Modify: `src/views/admin/AdminFormTemplateBuilder.vue`
- Modify: `src/store/formTemplates.ts`
- Modify: `server/tests/test_form_template_repository.py`
- Modify: `server/tests/test_form_template_api_contract.py`

**Interfaces:**
- Publish response: `{version, schema, changeSummary, impact}`.
- Impact shape: `{status: 'calculated'|'no_verified_data', projectCount?: number, startedSubmissionCount?: number}`.
- Copy action creates a new draft revision; it never mutates an old version.

- [ ] **Step 1: Add failing repository/API tests for summary and version immutability**

```python
def test_publish_summary_reports_required_change(self):
    first = publish(self.conn, schema_with(required=True))
    save(self.conn, schema_with(required=False))
    second = publish(self.conn)
    self.assertIn(
        {"fieldLabel": "合同金额", "change": "required_to_optional"},
        second["changeSummary"]["fields"],
    )
    self.assertNotEqual(first["id"], second["id"])

def test_copy_version_does_not_update_version_row(self):
    before = version_row(self.conn, self.version_id)
    copy_version_to_draft(self.conn, self.template_id, self.version_id, self.actor)
    self.assertEqual(version_row(self.conn, self.version_id), before)
```

- [ ] **Step 2: Run repository/API tests and verify summary assertion failure**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_repository server.tests.test_form_template_api_contract -v
```

Expected: the required-change summary or copy action test fails until implemented.

- [ ] **Step 3: Implement deterministic change summary and real impact calculation**

Compare draft against base version by placement ID and emit additions, removals, label changes, required changes, role/condition changes, and order changes. Impact counts query only real `project_records` and started submissions matching scope/stage; if there are no verifiable project rows, return `{status: 'no_verified_data'}` and display “暂无可计算的在办项目影响”。

- [ ] **Step 4: Build publish and version UI**

Publish dialog order: validation issues, scope/stage, business change list, impact state, cancel, confirm publish. Version drawer displays version number, publisher, published time, and summary; “恢复此版本” calls copy-to-draft and clearly states it creates a new draft.

- [ ] **Step 5: Run tests and build**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_repository server.tests.test_form_template_api_contract -v
npm.cmd run build
```

Expected: all pass; old version JSON is byte-for-byte unchanged after copy/publish.

- [ ] **Step 6: Commit publish/version UI**

```bash
git add src/components/form-builder/FormPublishDialog.vue src/components/form-builder/FormVersionDrawer.vue src/views/admin/AdminFormTemplateBuilder.vue src/store/formTemplates.ts server/tests/test_form_template_repository.py server/tests/test_form_template_api_contract.py
git commit -m "feat: publish versioned form templates"
```

---

### Task 12: Separate the system field library from display settings

**Files:**
- Modify: `src/views/admin/AdminFieldConfigs.vue`
- Create: `src/views/admin/AdminDisplayFieldSettings.vue`
- Modify: `src/router/index.ts`
- Modify: `src/views/AppLayout.vue`
- Modify: `src/api/audit.ts`
- Modify: `server/audit_api.py:4241-4259,4356-4363,4397-4406`
- Create: `test/fieldConfigurationBoundaries.test.ts`

**Interfaces:**
- System field library owns label, type, semantic/binding metadata, option group, enabled state.
- Display settings own `visibleInCard`, `visibleInTable`, `visibleInDetail`, `visibleInGantt`, `tableWidth`.
- Form builder exclusively owns form placement, required, roles, conditions, and order.

- [ ] **Step 1: Write a failing static-boundary test**

```typescript
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('system field library does not expose form-required or display controls', async () => {
  const source = await readFile(new URL('../src/views/admin/AdminFieldConfigs.vue', import.meta.url), 'utf8')
  assert.equal(source.includes('visibleInForm'), false)
  assert.equal(source.includes('必填项'), false)
  assert.equal(source.includes('表格列宽'), false)
})

test('display settings owns table and card flags', async () => {
  const source = await readFile(new URL('../src/views/admin/AdminDisplayFieldSettings.vue', import.meta.url), 'utf8')
  assert.equal(source.includes('visibleInTable'), true)
  assert.equal(source.includes('visibleInCard'), true)
})
```

- [ ] **Step 2: Run the boundary test and verify failure**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --test test/fieldConfigurationBoundaries.test.ts
```

Expected: current `AdminFieldConfigs.vue` still contains required/form/display controls and the display page is missing.

- [ ] **Step 3: Split routes and payload ownership**

Rename copy to “系统字段库”. Remove `required`, `visibleInForm`, table/card/detail/Gantt flags, and table width from that edit form. Add `/admin/display-field-settings` with only display controls. Add narrow API methods so a display update cannot change semantic key/type/binding and a field-library update cannot change form required state.

Retain `/admin/field-configs` as a redirect to `/admin/system-fields` for old bookmarks. Do not delete legacy columns yet; compatibility reads remain until a later cleanup migration.

- [ ] **Step 4: Run boundary tests, API regression, and build**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --test test/fieldConfigurationBoundaries.test.ts
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_api_contract -v
npm.cmd run build
```

Expected: all pass; three configuration concerns have distinct screens and payloads.

- [ ] **Step 5: Commit configuration-boundary cleanup**

```bash
git add src/views/admin/AdminFieldConfigs.vue src/views/admin/AdminDisplayFieldSettings.vue src/router/index.ts src/views/AppLayout.vue src/api/audit.ts server/audit_api.py test/fieldConfigurationBoundaries.test.ts
git commit -m "refactor: separate form and display configuration"
```

---

### Task 13: Run full regression, document rollout, and verify clean scope

**Files:**
- Create: `docs/runbooks/stage-form-builder-rollout.md`
- Modify only if tests expose regressions: files already named in Tasks 1-12

**Interfaces:**
- Produces rollout order: backup, migrate, seed drafts, admin review, first publish, smoke test, rollback procedure.
- Produces no code feature beyond fixes required by full verification.

- [ ] **Step 1: Write the rollout runbook with exact safe states**

The runbook must state:

```text
1. Back up the SQLite database and verify the backup can be opened.
2. Deploy schema/API/UI while no template is published; legacy field gates remain active.
3. Open migrated company drafts and resolve every named unresolved field.
4. Preview each stage as editor and viewer; preview must write no records.
5. Publish one low-risk stage first and verify a newly created stage form binds that version.
6. Verify an already-started form remains bound to its original version.
7. Publish contract/audit stages only after required/optional choices are reviewed.
8. Roll back by copying the previous version and publishing it; never update version rows.
```

- [ ] **Step 2: Run all backend tests**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s server/tests -p "test_*.py" -v
```

Expected: `OK`, zero failures and zero errors.

- [ ] **Step 3: Run all frontend pure tests**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --test test/*.test.ts
```

Expected: all Node tests pass.

- [ ] **Step 4: Run production build**

```powershell
npm.cmd run build
```

Expected: `vue-tsc` and Vite exit `0`; no TypeScript or bundling errors.

- [ ] **Step 5: Verify migration and runtime invariants with targeted tests**

```powershell
C:\Users\liu-j\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest server.tests.test_form_template_migrations server.tests.test_form_template_repository server.tests.test_stage_form_service server.tests.test_lifecycle_repository server.tests.test_lifecycle_api_contract -v
```

Expected: all pass, explicitly covering legacy fallback, optional core fields, immutable versions, and typed values.

- [ ] **Step 6: Verify diff scope before committing**

```bash
git diff --check
git status --short
```

Expected: `git diff --check` produces no output; status contains only intended feature/runbook files plus any pre-existing unrelated dirty files, which remain unstaged.

- [ ] **Step 7: Commit rollout documentation and any verified regression fixes**

```bash
git add docs/runbooks/stage-form-builder-rollout.md
git commit -m "docs: add stage form rollout runbook"
```

---

## Plan Acceptance Checklist

- Every approved spec section maps to at least one task.
- Company/project-type scope is implemented; single-project override is absent.
- Required/optional autonomy reaches builder, preview, runtime submit, and lifecycle gates.
- Fixed stage order and document/file gates remain protected.
- Legacy field configs seed unpublished drafts and preserve old gates until explicit publish.
- Started submissions retain immutable version bindings.
- System field library, form design, and display configuration are separate.
- Preview writes no data and impact counts use only verified rows.
- SQLite migration, canonical SQLite schema, and PostgreSQL schema remain equivalent.
- Every task has a failing test, a passing test command, and a focused commit.
