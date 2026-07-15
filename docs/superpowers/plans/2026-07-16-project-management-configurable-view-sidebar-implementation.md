# Project Management Configurable View Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目管理左栏改造成“公共视图 + 个人视图”的工作视图目录，把审计看板并入项目管理，并提供受保护核心视图、后台草稿发布回滚和服务器端个人视图能力。

**Architecture:** 新增独立的项目视图领域层、版本化配置仓储和挂载式 HTTP API，不把配置逻辑继续堆入 `server/audit_api.py`。前端以 Pinia 视图运行时统一解析 URL、公共配置与个人视图，`AppLayout.vue` 只负责渲染视图侧栏，`ProjectManagementView.vue` 继续持有现有项目弹窗和详情上下文，并按稳定 `viewKey` 切换现有台账、新增待办/生命周期组件及嵌入式审计看板。

**Tech Stack:** Vue 3、Pinia、Vue Router、Arco Design Vue、TypeScript、Python 3 标准库 HTTP 服务、SQLite、PostgreSQL 镜像 schema、Node `node:test`、Python `unittest`。

## Global Constraints

- 顶部平台导航固定为：`工作台 / 招投标 / 项目管理 / 资料 / 结算`，不再出现独立“审计”入口。
- `project.my-work`、`project.lifecycle`、`project.ledger` 是受保护核心视图，任何配置都不能隐藏、删除或改变内部标识。
- 业务动作不进入左栏；“上传合同创建项目”保留在项目管理页面主操作区。
- 视图配置只能组织现有项目数据，不得改变生命周期准入、资料判定、审计判定、金额计算或数据权限。
- 无真实数据时只展示空状态，不写入或生成示例项目。
- 第一阶段只支持表格、看板、任务列表；不增加甘特、自由字段、公式、跨表关联和自动化编排。
- 第一阶段的企业公共视图就是六个受控系统视图；后台可以改名、分组、排序、筛选、显示控制和默认入口，但不开放任意公共视图创建，避免演变为低代码平台。
- 当前账号模型仍为 `admin | editor | viewer`；本计划不夹带多角色权限模型重构。
- 管理端配置必须经过草稿、预览、发布；回滚通过创建新发布版本完成，不能篡改历史版本。
- 公共视图与个人视图的筛选字段必须使用后端白名单，不能接受任意 SQL、表达式或前端传入的权限范围。
- 保留 `/audit` 旧链接兼容，但只做重定向，不再作为顶部模块或独立业务入口。
- 不修改现有未提交的 `vite.config.ts`、`.scatter/`、`.superpowers/`、`design-audits/`、`reports/`、`review_results.json` 和既有未跟踪计划文件。

## File Structure

### Backend files

- Create `server/project_view_domain.py`: 默认配置、稳定键、白名单、保护规则和纯校验函数。
- Create `server/project_view_repository.py`: 配置版本、个人视图、发布和回滚的 SQLite 仓储。
- Create `server/project_view_api.py`: `/api/project-views` 与 `/api/admin/project-views/*` 的挂载式 HTTP 路由。
- Modify `server/migrations.py`: 增加 `2026071601_project_view_runtime` 迁移和校验和。
- Modify `server/schema.sql`: 新安装环境的 SQLite 表和索引。
- Modify `server/postgres_schema.sql`: PostgreSQL 镜像表和索引。
- Modify `server/audit_api.py`: 挂载 `ProjectViewApi`，移除顶部导航顺序中的 `/audit`，复用系统操作日志。
- Create `server/tests/test_project_view_domain.py`: 核心保护和白名单测试。
- Create `server/tests/test_project_view_repository.py`: 迁移、版本、个人视图和回滚测试。
- Create `server/tests/test_project_view_api_contract.py`: 路由、权限和响应契约测试。

### Frontend files

- Create `src/types/projectViews.ts`: 公共配置、个人视图、版本摘要和运行时类型。
- Create `src/utils/projectViewRuntime.ts`: URL 解析、配置规范化、视图筛选映射和旧审计链接迁移纯函数。
- Create `src/api/projectViews.ts`: 项目视图 API 客户端。
- Create `src/store/projectViews.ts`: 公共配置、个人视图、活动视图和 URL 同步状态。
- Create `src/components/project/ProjectViewSidebar.vue`: 项目管理视图目录。
- Create `src/components/project/ProjectWorkList.vue`: “我的工作”任务列表。
- Create `src/components/project/ProjectLifecycleBoard.vue`: 项目生命周期看板。
- Create `src/components/project/ProjectAuditProgressView.vue`: 固定看板模式的嵌入式审计进度。
- Create `src/components/project/ProjectPersonalViewDialog.vue`: 保存/重命名个人视图。
- Create `src/views/admin/AdminProjectViews.vue`: 三栏后台配置、预览、发布和回滚。
- Modify `src/views/AppLayout.vue`: 顶部移除审计；项目模块改用 `ProjectViewSidebar`；后台增加配置入口。
- Modify `src/views/ProjectManagementView.vue`: 以 `viewKey` 切换四种渲染器，复用现有项目详情与合同建档。
- Modify `src/views/KanbanView.vue`: 支持固定嵌入模式，隐藏重复视图切换。
- Modify `src/router/index.ts`: 增加后台路由并兼容 `/audit` 旧链接。
- Modify `src/api/projects.ts`: 项目查询支持后端拥有的 `viewKey` 语义。
- Modify `src/types/index.ts`: `ProjectFilters` 增加 `viewKey`，不新增系统设置键。
- Modify `src/styles/arco-premium-workbench.css`: 统一项目视图左栏和后台三栏编辑器的现有设计令牌。
- Create `test/projectViewRuntime.test.ts`: 配置保护、URL 和筛选映射测试。

---

### Task 1: Project view domain contract and protected defaults

**Files:**
- Create: `server/project_view_domain.py`
- Test: `server/tests/test_project_view_domain.py`

**Interfaces:**
- Produces: `CORE_PROJECT_VIEW_KEYS`, `SYSTEM_PROJECT_VIEW_KEYS`, `default_project_view_config()`, `normalize_project_view_config(payload)`, `normalize_personal_view_payload(payload)`.
- Consumes: no database or HTTP dependencies.

- [ ] **Step 1: Write the failing domain tests**

```python
import unittest

from server.project_view_domain import (
    CORE_PROJECT_VIEW_KEYS,
    ProjectViewValidationError,
    default_project_view_config,
    normalize_personal_view_payload,
    normalize_project_view_config,
)


class ProjectViewDomainTests(unittest.TestCase):
    def test_default_config_contains_every_protected_core_view(self):
        config = default_project_view_config()
        views = {item["viewKey"]: item for item in config["views"]}
        self.assertEqual(set(CORE_PROJECT_VIEW_KEYS), {
            "project.my-work", "project.lifecycle", "project.ledger"
        })
        for key in CORE_PROJECT_VIEW_KEYS:
            self.assertIn(key, views)
            self.assertTrue(views[key]["visible"])
            self.assertTrue(views[key]["protected"])

    def test_normalizer_restores_hidden_or_missing_core_views(self):
        payload = default_project_view_config()
        payload["views"] = [
            {**item, "visible": False}
            for item in payload["views"]
            if item["viewKey"] != "project.ledger"
        ]
        normalized = normalize_project_view_config(payload)
        views = {item["viewKey"]: item for item in normalized["views"]}
        self.assertTrue(views["project.my-work"]["visible"])
        self.assertTrue(views["project.lifecycle"]["visible"])
        self.assertTrue(views["project.ledger"]["visible"])

    def test_personal_view_rejects_unapproved_filters_and_system_keys(self):
        with self.assertRaises(ProjectViewValidationError):
            normalize_personal_view_payload({
                "name": "越权视图",
                "viewKey": "project.ledger",
                "presentation": "table",
                "filters": {"rawSql": "DELETE FROM project_records"},
            })

    def test_personal_view_keeps_only_supported_presentation_and_filters(self):
        normalized = normalize_personal_view_payload({
            "name": "我的资料缺口",
            "presentation": "table",
            "filters": {"onlyMissingDocuments": True, "sort": "updatedAt"},
            "groupBy": "projectStatus",
            "columns": ["project", "status", "docs", "manager"],
        })
        self.assertEqual(normalized["presentation"], "table")
        self.assertEqual(normalized["filters"], {
            "onlyMissingDocuments": True,
            "sort": "updatedAt",
        })


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run: `python -m unittest server.tests.test_project_view_domain -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'server.project_view_domain'`.

- [ ] **Step 3: Implement the domain contract**

Create `server/project_view_domain.py` with these exact public constants, exception and normalizers:

```python
from __future__ import annotations

from copy import deepcopy


CORE_PROJECT_VIEW_KEYS = (
    "project.my-work",
    "project.lifecycle",
    "project.ledger",
)
SYSTEM_PROJECT_VIEW_KEYS = CORE_PROJECT_VIEW_KEYS + (
    "project.blocked",
    "project.document-gaps",
    "project.audit-progress",
)
ALLOWED_PRESENTATIONS = {"table", "board", "task_list"}
ALLOWED_GROUP_BY = {"none", "projectStatus", "managerName", "auditStage"}
ALLOWED_FILTER_KEYS = {
    "keyword", "projectStatus", "settlementStatus", "managerName",
    "onlyMissingDocuments", "onlyAuditLinked", "onlyBlocked",
    "onlyRisk", "onlyUpcomingDue", "onlyMonthlyNew", "sort",
}
ALLOWED_ROLES = {"admin", "editor", "viewer"}
ALLOWED_COLUMNS = {
    "select", "project", "status", "docs", "amount", "manager",
    "audit", "plannedEndDate", "actions",
}


class ProjectViewValidationError(ValueError):
    pass


def _system_views():
    return [
        {"viewKey": "project.my-work", "label": "我的工作", "icon": "list", "groupKey": "my-work", "presentation": "task_list", "renderer": "work_items", "visible": True, "protected": True, "systemOwned": True, "filters": {}, "groupBy": "none", "sort": "dueDate", "columns": [], "countRule": "work_items", "accessRoles": ["admin", "editor", "viewer"], "canCopy": False},
        {"viewKey": "project.lifecycle", "label": "生命周期看板", "icon": "view-module", "groupKey": "overview", "presentation": "board", "renderer": "lifecycle", "visible": True, "protected": True, "systemOwned": True, "filters": {}, "groupBy": "projectStatus", "sort": "updatedAt", "columns": ["project", "manager", "docs"], "countRule": "none", "accessRoles": ["admin", "editor", "viewer"], "canCopy": False},
        {"viewKey": "project.ledger", "label": "项目台账", "icon": "task", "groupKey": "overview", "presentation": "table", "renderer": "ledger", "visible": True, "protected": True, "systemOwned": True, "filters": {}, "groupBy": "none", "sort": "updatedAt", "columns": ["select", "project", "status", "docs", "amount", "audit", "actions"], "countRule": "none", "accessRoles": ["admin", "editor", "viewer"], "canCopy": True},
        {"viewKey": "project.blocked", "label": "阶段阻塞", "icon": "exclamation-circle", "groupKey": "specialty", "presentation": "table", "renderer": "ledger", "visible": True, "protected": False, "systemOwned": True, "filters": {"onlyBlocked": True}, "groupBy": "projectStatus", "sort": "updatedAt", "columns": ["project", "status", "docs", "manager", "actions"], "countRule": "blocked", "accessRoles": ["admin", "editor", "viewer"], "canCopy": True},
        {"viewKey": "project.document-gaps", "label": "资料缺口", "icon": "folder", "groupKey": "specialty", "presentation": "table", "renderer": "ledger", "visible": True, "protected": False, "systemOwned": True, "filters": {"onlyMissingDocuments": True}, "groupBy": "projectStatus", "sort": "updatedAt", "columns": ["project", "status", "docs", "manager", "actions"], "countRule": "document_gaps", "accessRoles": ["admin", "editor", "viewer"], "canCopy": True},
        {"viewKey": "project.audit-progress", "label": "审计进度", "icon": "view-module", "groupKey": "specialty", "presentation": "board", "renderer": "audit_progress", "visible": True, "protected": False, "systemOwned": True, "filters": {"onlyAuditLinked": True}, "groupBy": "auditStage", "sort": "updatedAt", "columns": ["project", "status", "amount", "manager"], "countRule": "audit_open", "accessRoles": ["admin", "editor", "viewer"], "canCopy": False},
    ]


def default_project_view_config():
    return {
        "schemaVersion": 1,
        "enterpriseDefaultViewKey": "project.my-work",
        "personalViewsEnabled": True,
        "personalViewLimit": 8,
        "groups": [
            {"groupKey": "my-work", "label": "我的工作", "sortOrder": 10, "collapsed": False},
            {"groupKey": "overview", "label": "项目全景", "sortOrder": 20, "collapsed": False},
            {"groupKey": "specialty", "label": "专项视角", "sortOrder": 30, "collapsed": False},
            {"groupKey": "personal", "label": "我的视图", "sortOrder": 40, "collapsed": False},
        ],
        "views": _system_views(),
    }


def _clean_filters(value):
    if not isinstance(value, dict):
        return {}
    unknown = set(value) - ALLOWED_FILTER_KEYS
    if unknown:
        raise ProjectViewValidationError(f"Unsupported filters: {', '.join(sorted(unknown))}")
    return {key: value[key] for key in ALLOWED_FILTER_KEYS if key in value}


def normalize_personal_view_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    name = str(payload.get("name") or "").strip()
    if not name or len(name) > 30:
        raise ProjectViewValidationError("Personal view name must contain 1-30 characters")
    if payload.get("viewKey") in SYSTEM_PROJECT_VIEW_KEYS:
        raise ProjectViewValidationError("Personal view cannot reuse a system view key")
    presentation = str(payload.get("presentation") or "table")
    if presentation not in ALLOWED_PRESENTATIONS:
        raise ProjectViewValidationError("Unsupported presentation")
    group_by = str(payload.get("groupBy") or "none")
    if group_by not in ALLOWED_GROUP_BY:
        raise ProjectViewValidationError("Unsupported groupBy")
    columns = [str(item) for item in payload.get("columns") or [] if str(item) in ALLOWED_COLUMNS]
    return {"name": name, "presentation": presentation, "filters": _clean_filters(payload.get("filters")), "groupBy": group_by, "columns": columns, "isDefault": bool(payload.get("isDefault"))}


def normalize_project_view_config(payload):
    source = deepcopy(payload) if isinstance(payload, dict) else default_project_view_config()
    defaults = default_project_view_config()
    groups = source.get("groups") if isinstance(source.get("groups"), list) else defaults["groups"]
    normalized_groups = []
    seen_groups = set()
    for index, group in enumerate(groups):
        key = str(group.get("groupKey") or "").strip()
        if not key or key in seen_groups:
            continue
        seen_groups.add(key)
        normalized_groups.append({"groupKey": key, "label": str(group.get("label") or key)[:30], "sortOrder": int(group.get("sortOrder") or (index + 1) * 10), "collapsed": bool(group.get("collapsed"))})
    default_by_key = {item["viewKey"]: item for item in defaults["views"]}
    supplied_by_key = {str(item.get("viewKey")): item for item in source.get("views") or [] if isinstance(item, dict)}
    normalized_views = []
    for key, base in default_by_key.items():
        submitted = supplied_by_key.get(key, {})
        next_view = {**base, **{field: submitted[field] for field in ("label", "icon", "groupKey", "visible", "filters", "groupBy", "sort", "columns", "countRule", "accessRoles", "canCopy") if field in submitted}}
        next_view["filters"] = _clean_filters(next_view.get("filters"))
        next_view["accessRoles"] = [role for role in next_view.get("accessRoles") or [] if role in ALLOWED_ROLES] or list(ALLOWED_ROLES)
        if key in CORE_PROJECT_VIEW_KEYS:
            next_view["visible"] = True
            next_view["protected"] = True
            next_view["systemOwned"] = True
            next_view["renderer"] = base["renderer"]
            next_view["presentation"] = base["presentation"]
        normalized_views.append(next_view)
    assigned_groups = {item["groupKey"] for item in normalized_views}
    missing_groups = assigned_groups - {item["groupKey"] for item in normalized_groups}
    for key in sorted(missing_groups):
        normalized_groups.append({"groupKey": key, "label": key, "sortOrder": (len(normalized_groups) + 1) * 10, "collapsed": False})
    requested_default = str(source.get("enterpriseDefaultViewKey") or "project.my-work")
    visible_keys = {item["viewKey"] for item in normalized_views if item["visible"]}
    if requested_default not in visible_keys:
        requested_default = "project.my-work"
    return {"schemaVersion": 1, "enterpriseDefaultViewKey": requested_default, "personalViewsEnabled": bool(source.get("personalViewsEnabled", True)), "personalViewLimit": min(20, max(1, int(source.get("personalViewLimit") or 8))), "groups": normalized_groups or defaults["groups"], "views": normalized_views}
```

- [ ] **Step 4: Run the domain tests**

Run: `python -m unittest server.tests.test_project_view_domain -v`

Expected: 4 tests PASS.

- [ ] **Step 5: Commit the domain contract**

```powershell
git add server/project_view_domain.py server/tests/test_project_view_domain.py
git commit -m "feat: define protected project view domain"
```

### Task 2: Versioned persistence, migration and personal views

**Files:**
- Create: `server/project_view_repository.py`
- Modify: `server/migrations.py`
- Modify: `server/schema.sql`
- Modify: `server/postgres_schema.sql`
- Test: `server/tests/test_project_view_repository.py`

**Interfaces:**
- Consumes: `normalize_project_view_config()` and `normalize_personal_view_payload()` from Task 1.
- Produces: `ensure_project_view_defaults(conn)`, `get_published_project_view_config(conn)`, `get_project_view_admin_state(conn)`, `save_project_view_draft(conn, payload, actor)`, `publish_project_view_draft(conn, draft_id, actor)`, `rollback_project_view_config(conn, version_id, actor)`, `list_personal_project_views(conn, user_id)`, `create_personal_project_view(conn, user_id, payload)`, `update_personal_project_view(conn, user_id, view_id, payload)`, `delete_personal_project_view(conn, user_id, view_id)`.

- [ ] **Step 1: Add failing migration and repository tests**

Create `server/tests/test_project_view_repository.py` with an in-memory `system_users` table, call `apply_pending_migrations(conn)`, then assert:

```python
def test_migration_creates_project_view_tables(self):
    tables = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    self.assertIn("project_view_config_versions", tables)
    self.assertIn("project_personal_views", tables)

def test_publishing_and_rollback_are_append_only(self):
    initial = ensure_project_view_defaults(self.conn)
    draft = save_project_view_draft(self.conn, {
        **initial["config"],
        "enterpriseDefaultViewKey": "project.ledger",
    }, self.actor)
    published = publish_project_view_draft(self.conn, draft["id"], self.actor)
    rolled_back = rollback_project_view_config(self.conn, initial["id"], self.actor)
    self.assertGreater(published["versionNo"], initial["versionNo"])
    self.assertGreater(rolled_back["versionNo"], published["versionNo"])
    self.assertEqual(rolled_back["config"]["enterpriseDefaultViewKey"], "project.my-work")

def test_personal_default_is_unique_per_user(self):
    first = create_personal_project_view(self.conn, "u1", {"name": "A", "presentation": "table", "filters": {}, "isDefault": True})
    second = create_personal_project_view(self.conn, "u1", {"name": "B", "presentation": "table", "filters": {}, "isDefault": True})
    rows = list_personal_project_views(self.conn, "u1")
    self.assertFalse(next(row for row in rows if row["id"] == first["id"])["isDefault"])
    self.assertTrue(next(row for row in rows if row["id"] == second["id"])["isDefault"])
```

- [ ] **Step 2: Run the repository tests and verify failure**

Run: `python -m unittest server.tests.test_project_view_repository -v`

Expected: FAIL because the migration constant and repository do not exist.

- [ ] **Step 3: Add the migration**

In `server/migrations.py`, add `PROJECT_VIEW_RUNTIME_MIGRATION = "2026071601_project_view_runtime"`, a checksum over these statements, and register it after `CONTRACT_FALLBACK_PROVENANCE_MIGRATION`:

```sql
CREATE TABLE IF NOT EXISTS project_view_config_versions (
  id TEXT PRIMARY KEY,
  version_no INTEGER NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'archived')),
  schema_version INTEGER NOT NULL DEFAULT 1,
  config_json TEXT NOT NULL,
  created_by_user_id TEXT NOT NULL DEFAULT '',
  created_by_name TEXT NOT NULL DEFAULT '',
  published_by_user_id TEXT NOT NULL DEFAULT '',
  published_by_name TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  published_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_project_view_config_status
ON project_view_config_versions(status, version_no DESC);

CREATE TABLE IF NOT EXISTS project_personal_views (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  presentation TEXT NOT NULL,
  config_json TEXT NOT NULL,
  is_default INTEGER NOT NULL DEFAULT 0,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES system_users(id) ON DELETE CASCADE,
  UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_project_personal_views_user
ON project_personal_views(user_id, sort_order, updated_at DESC);
```

Copy the same logical tables to `server/schema.sql`; in `server/postgres_schema.sql` use `INTEGER`, `TEXT`, `TIMESTAMPTZ` and `REFERENCES system_users(id) ON DELETE CASCADE`, preserving identical column names.

- [ ] **Step 4: Implement the repository**

Implement `server/project_view_repository.py` using `uuid.uuid4()`, UTC ISO timestamps and JSON with `ensure_ascii=False`. Required behavior:

```python
def ensure_project_view_defaults(conn):
    row = conn.execute(
        "SELECT * FROM project_view_config_versions WHERE status = 'published' ORDER BY version_no DESC LIMIT 1"
    ).fetchone()
    if row:
        return _version_payload(row)
    return _insert_version(conn, default_project_view_config(), "published", {"id": "system", "displayName": "系统"})


def save_project_view_draft(conn, payload, actor):
    config = normalize_project_view_config(payload)
    conn.execute("UPDATE project_view_config_versions SET status = 'archived', updated_at = ? WHERE status = 'draft'", (_now_iso(),))
    return _insert_version(conn, config, "draft", actor)


def publish_project_view_draft(conn, draft_id, actor):
    draft = _require_version(conn, draft_id, "draft")
    conn.execute("UPDATE project_view_config_versions SET status = 'archived', updated_at = ? WHERE status = 'published'", (_now_iso(),))
    published = _insert_version(conn, json.loads(draft["config_json"]), "published", actor, published=True)
    conn.execute("UPDATE project_view_config_versions SET status = 'archived', updated_at = ? WHERE id = ?", (_now_iso(), draft_id))
    conn.commit()
    return published


def rollback_project_view_config(conn, version_id, actor):
    source = _require_version(conn, version_id)
    config = normalize_project_view_config(json.loads(source["config_json"]))
    conn.execute("UPDATE project_view_config_versions SET status = 'archived', updated_at = ? WHERE status IN ('published', 'draft')", (_now_iso(),))
    rolled_back = _insert_version(conn, config, "published", actor, published=True)
    conn.commit()
    return rolled_back
```

Personal view creation and update must call `normalize_personal_view_payload`, enforce the published `personalViewLimit`, clear the previous default in the same transaction when `isDefault` is true, and require both `id` and `user_id` for update/delete.

- [ ] **Step 5: Run migration and repository tests**

Run: `python -m unittest server.tests.test_project_view_repository -v`

Expected: all tests PASS, including the existing migration checksum tests.

- [ ] **Step 6: Run the full migration safety suite**

Run: `python -m unittest server.tests.test_document_migrations server.tests.test_lifecycle_repository -v`

Expected: PASS with no checksum mismatch.

- [ ] **Step 7: Commit persistence**

```powershell
git add server/project_view_repository.py server/migrations.py server/schema.sql server/postgres_schema.sql server/tests/test_project_view_repository.py
git commit -m "feat: persist versioned project views"
```

### Task 3: Mounted project view API and server-owned view semantics

**Files:**
- Create: `server/project_view_api.py`
- Modify: `server/audit_api.py`
- Modify: `src/api/projects.ts`
- Modify: `src/types/index.ts`
- Test: `server/tests/test_project_view_api_contract.py`

**Interfaces:**
- Consumes: repository functions from Task 2 and `Handler.write_operation_log` callback.
- Produces HTTP routes:
  - `GET /api/project-views`
  - `GET /api/admin/project-views`
  - `PUT /api/admin/project-views/draft`
  - `POST /api/admin/project-views/publish`
  - `POST /api/admin/project-views/rollback`
  - `POST /api/project-views/personal`
  - `PUT /api/project-views/personal/{id}`
  - `DELETE /api/project-views/personal/{id}`
- Extends `GET /api/projects` with `viewKey=project.blocked|project.document-gaps|project.audit-progress`.

- [ ] **Step 1: Write failing API contract tests**

In `server/tests/test_project_view_api_contract.py`, mirror the repository-backed API fixture used by `test_document_api_contract.py` and assert:

```python
def test_any_authenticated_user_gets_effective_views_and_own_personal_views(self):
    response = self.request("GET", "/api/project-views", user=self.viewer)
    self.assertEqual(response.status, 200)
    self.assertEqual(response.json["data"]["config"]["enterpriseDefaultViewKey"], "project.my-work")
    self.assertEqual(response.json["data"]["personalViews"], [])

def test_non_admin_cannot_write_public_view_draft(self):
    response = self.request("PUT", "/api/admin/project-views/draft", user=self.editor, json={"config": {}})
    self.assertEqual(response.status, 403)

def test_personal_view_cannot_be_modified_by_another_user(self):
    created = self.request("POST", "/api/project-views/personal", user=self.editor, json={"name": "我的筛选", "presentation": "table", "filters": {}})
    response = self.request("DELETE", f"/api/project-views/personal/{created.json['data']['id']}", user=self.viewer)
    self.assertEqual(response.status, 404)

def test_blocked_view_is_decided_by_backend_not_client_filter(self):
    response = self.request("GET", "/api/projects?viewKey=project.blocked", user=self.viewer)
    self.assertTrue(all(item["lifecycleBlockerCount"] > 0 for item in response.json["data"]))
```

- [ ] **Step 2: Run the API test and verify failure**

Run: `python -m unittest server.tests.test_project_view_api_contract -v`

Expected: FAIL because `ProjectViewApi` is not mounted.

- [ ] **Step 3: Implement `ProjectViewApi`**

Use the mounted-router pattern already used by `DocumentApi`. The public surface must be:

```python
class ProjectViewApi:
    ROUTE_PREFIXES = ("/api/project-views", "/api/admin/project-views")

    @classmethod
    def is_route(cls, method, path):
        return any(path == prefix or path.startswith(prefix + "/") for prefix in cls.ROUTE_PREFIXES)

    def __init__(self, handler, conn, user, require_role, write_log):
        self.handler = handler
        self.conn = conn
        self.user = user
        self.require_role = require_role
        self.write_log = write_log

    def dispatch(self, method, path, data=None):
        data = data or {}
        if method == "GET" and path == "/api/project-views":
            return self._effective()
        if method == "GET" and path == "/api/admin/project-views":
            self.require_role({"admin"})
            return self._admin_state()
        if method == "PUT" and path == "/api/admin/project-views/draft":
            self.require_role({"admin"})
            return self._save_draft(data)
        if method == "POST" and path == "/api/admin/project-views/publish":
            self.require_role({"admin"})
            return self._publish(data)
        if method == "POST" and path == "/api/admin/project-views/rollback":
            self.require_role({"admin"})
            return self._rollback(data)
        if method == "POST" and path == "/api/project-views/personal":
            return self._create_personal(data)
        match = re.match(r"^/api/project-views/personal/([^/]+)$", path)
        if match and method == "PUT":
            return self._update_personal(match.group(1), data)
        if match and method == "DELETE":
            return self._delete_personal(match.group(1))
        self.handler.not_found()
```

Each mutation writes `project_view.draft_save`, `project_view.publish`, `project_view.rollback`, `project_view.personal_create`, `project_view.personal_update` or `project_view.personal_delete`, commits exactly once, and returns repository payloads unchanged under `{success, data}`.

`GET /api/project-views` also returns backend-calculated meaningful counts. `work_items` counts unfinished real work items, `blocked` counts lifecycle snapshots with blockers, `document_gaps` counts projects with `missing_required_count > 0`, and `audit_open` counts linked audit records not in the archived stage. Counts are computed after the same user data-permission predicate used by the list API; a zero count is returned as `0` and hidden by the client.

- [ ] **Step 4: Mount the API in `server/audit_api.py`**

Import `ProjectViewApi`, instantiate it with the authenticated user, and dispatch it before the legacy route chain in each HTTP verb. Keep `read_json(self)` only for methods with JSON bodies. Add a small adapter:

```python
def mounted_project_view_api(self, conn, user):
    def require_roles(roles):
        if user.get("role") not in roles:
            self.respond(403, {"success": False, "error": "权限不足"})
            raise PermissionError("project view role denied")
    return ProjectViewApi(self, conn, user, require_roles, self.write_operation_log)
```

Catch that specific `PermissionError` inside the mount path so it does not emit a second 500 response.

- [ ] **Step 5: Add server-owned `viewKey` filtering**

Add `viewKey?: string` and `onlyBlocked?: boolean` to `ProjectFilters`, serialize `viewKey` in `src/api/projects.ts`, and in `list_project_records` map only these stable keys:

```python
view_key = first_param(params, "viewKey")
if view_key == "project.document-gaps":
    filters["only_missing_documents"] = True
elif view_key == "project.audit-progress":
    filters["only_audit_linked"] = True
elif view_key == "project.blocked":
    filters["only_blocked"] = True
```

For blocked projects, compute candidate IDs with the existing lifecycle policy/repository before SQL pagination, add `lifecycleBlockerCount` and `lifecycleBlockers` to each matching `ProjectRecord`, and never trust a client-provided blocker count.

Update newly generated audit work-item `actionPath` values from `/audit?...` to `/project-management?view=project.audit-progress&...`. Existing stored or computed `/audit` paths remain safe because Task 5 keeps the compatibility redirect.

- [ ] **Step 6: Run API and existing lifecycle tests**

Run: `python -m unittest server.tests.test_project_view_api_contract server.tests.test_lifecycle_api_contract -v`

Expected: PASS.

- [ ] **Step 7: Commit the API**

```powershell
git add server/project_view_api.py server/audit_api.py server/tests/test_project_view_api_contract.py src/api/projects.ts src/types/index.ts
git commit -m "feat: expose secure project view APIs"
```

### Task 4: Frontend view runtime, API client and URL contract

**Files:**
- Create: `src/types/projectViews.ts`
- Create: `src/utils/projectViewRuntime.ts`
- Create: `src/api/projectViews.ts`
- Create: `src/store/projectViews.ts`
- Test: `test/projectViewRuntime.test.ts`

**Interfaces:**
- Consumes: Task 3 HTTP routes.
- Produces: `useProjectViewsStore()`, `resolveProjectViewKey()`, `projectViewLocation()`, `legacyAuditLocation()`, `filtersForProjectView()`.

- [ ] **Step 1: Write failing frontend runtime tests**

```typescript
import assert from 'node:assert/strict'
import test from 'node:test'
import {
  filtersForProjectView,
  legacyAuditLocation,
  normalizeProjectViewConfig,
  resolveProjectViewKey,
} from '../src/utils/projectViewRuntime.ts'

test('restores every protected core view when remote config hides or removes it', () => {
  const config = normalizeProjectViewConfig({
    schemaVersion: 1,
    enterpriseDefaultViewKey: 'project.ledger',
    personalViewsEnabled: true,
    personalViewLimit: 8,
    groups: [],
    views: [{ viewKey: 'project.my-work', label: '待办', visible: false }],
  })
  const visible = config.views.filter((item) => item.visible).map((item) => item.viewKey)
  assert.deepEqual(visible.slice(0, 3), ['project.my-work', 'project.lifecycle', 'project.ledger'])
})

test('falls back to enterprise default when URL view is unavailable', () => {
  assert.equal(resolveProjectViewKey('project.hidden', {
    enterpriseDefaultViewKey: 'project.ledger',
    views: [{ viewKey: 'project.ledger', visible: true }],
  }), 'project.ledger')
})

test('maps legacy audit links to the project audit progress view', () => {
  assert.deepEqual(legacyAuditLocation({ projectId: 'a1', focus: 'work-items', mode: 'table' }), {
    path: '/project-management',
    query: { view: 'project.audit-progress', projectId: 'a1', focus: 'work-items', auditMode: 'table' },
  })
})

test('uses server-owned view key for system specialty views', () => {
  assert.deepEqual(filtersForProjectView({ viewKey: 'project.blocked', filters: { onlyMissingDocuments: true } }), {
    viewKey: 'project.blocked',
  })
})
```

- [ ] **Step 2: Run the frontend test and verify failure**

Run: `node --experimental-strip-types --test test/projectViewRuntime.test.ts`

Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Define exact frontend types**

Create `src/types/projectViews.ts` with:

```typescript
import type { AdminRole, ProjectFilters } from '@/types'

export type ProjectViewPresentation = 'table' | 'board' | 'task_list'
export type ProjectViewRenderer = 'ledger' | 'lifecycle' | 'work_items' | 'audit_progress'
export type ProjectViewCountRule = 'none' | 'work_items' | 'blocked' | 'document_gaps' | 'audit_open'

export interface ProjectViewGroup { groupKey: string; label: string; sortOrder: number; collapsed: boolean }
export interface ProjectViewDefinition {
  viewKey: string
  label: string
  icon: string
  groupKey: string
  presentation: ProjectViewPresentation
  renderer: ProjectViewRenderer
  visible: boolean
  protected: boolean
  systemOwned: boolean
  filters: Partial<ProjectFilters>
  groupBy: 'none' | 'projectStatus' | 'managerName' | 'auditStage'
  sort: string
  columns: string[]
  countRule: ProjectViewCountRule
  accessRoles: AdminRole[]
  canCopy: boolean
}
export interface ProjectViewConfig { schemaVersion: 1; enterpriseDefaultViewKey: string; personalViewsEnabled: boolean; personalViewLimit: number; groups: ProjectViewGroup[]; views: ProjectViewDefinition[] }
export interface PersonalProjectView { id: string; name: string; presentation: ProjectViewPresentation; filters: Partial<ProjectFilters>; groupBy: ProjectViewDefinition['groupBy']; columns: string[]; isDefault: boolean; sortOrder: number; createdAt: string; updatedAt: string }
export interface ProjectViewVersion { id: string; versionNo: number; status: 'draft' | 'published' | 'archived'; config: ProjectViewConfig; createdByName: string; publishedByName: string; createdAt: string; publishedAt: string }
export interface EffectiveProjectViews { publishedVersion: ProjectViewVersion; config: ProjectViewConfig; personalViews: PersonalProjectView[]; counts: Record<string, number>; permissions: { canManagePublicViews: boolean; canSavePersonalViews: boolean } }
export interface ProjectViewAdminState { publishedVersion: ProjectViewVersion; draftVersion: ProjectViewVersion | null; versions: ProjectViewVersion[] }
```

- [ ] **Step 4: Implement runtime helpers, API and store**

`projectViewRuntime.ts` must duplicate the protected defaults as a defensive client fallback, but the backend remains authoritative. `filtersForProjectView()` must return only `{viewKey}` for system-owned specialty views and merge whitelisted filters for personal views. `legacyAuditLocation()` must preserve `projectId` and `focus`, rename `mode` to `auditMode`, and discard unrelated query keys.

`src/api/projectViews.ts` exports authenticated request functions for every Task 3 route. `src/store/projectViews.ts` must expose:

```typescript
export const useProjectViewsStore = defineStore('projectViews', () => {
  const config = ref<ProjectViewConfig>(fallbackProjectViewConfig())
  const personalViews = ref<PersonalProjectView[]>([])
  const counts = ref<Record<string, number>>({})
  const publishedVersionNo = ref(0)
  const activeViewKey = ref('project.my-work')
  const loading = ref(false)
  const loadError = ref('')

  const activeView = computed(() =>
    config.value.views.find((item) => item.viewKey === activeViewKey.value)
    || personalViews.value.find((item) => `personal:${item.id}` === activeViewKey.value)
  )

  async function load(queryView?: unknown) {
    loading.value = true
    loadError.value = ''
    try {
      const result = await fetchEffectiveProjectViews()
      config.value = normalizeProjectViewConfig(result.config)
      personalViews.value = result.personalViews
      counts.value = result.counts
      publishedVersionNo.value = result.publishedVersion.versionNo
      activeViewKey.value = resolveProjectViewKey(String(queryView || ''), config.value, personalViews.value)
    } catch (error) {
      loadError.value = error instanceof Error ? error.message : '项目视图加载失败'
      activeViewKey.value = resolveProjectViewKey(String(queryView || ''), config.value, [])
    } finally {
      loading.value = false
    }
  }

  return { config, personalViews, counts, publishedVersionNo, activeViewKey, activeView, loading, loadError, load }
})
```

Register a `window.focus` listener while project management is mounted. On focus, re-fetch the effective config; when `publishedVersionNo` changes, keep the current workspace state and show “项目视图配置已更新，刷新后应用” with an explicit refresh action. Do not force-reload or discard unsaved filters.

- [ ] **Step 5: Run the runtime tests**

Run: `node --experimental-strip-types --test test/projectViewRuntime.test.ts`

Expected: all tests PASS.

- [ ] **Step 6: Commit the frontend runtime**

```powershell
git add src/types/projectViews.ts src/utils/projectViewRuntime.ts src/api/projectViews.ts src/store/projectViews.ts test/projectViewRuntime.test.ts
git commit -m "feat: add project view runtime"
```

### Task 5: Top navigation cleanup, project view sidebar and legacy audit route

**Files:**
- Create: `src/components/project/ProjectViewSidebar.vue`
- Modify: `src/views/AppLayout.vue`
- Modify: `src/router/index.ts`
- Modify: `server/audit_api.py`
- Modify: `src/styles/arco-premium-workbench.css`
- Test: `test/projectViewRuntime.test.ts`

**Interfaces:**
- Consumes: Task 4 store and URL helpers.
- Produces: project-management-only view sidebar; `/audit` compatibility redirect; five-item top navigation.

- [ ] **Step 1: Extend route tests before UI changes**

Add assertions to `test/projectViewRuntime.test.ts` that a missing/hidden specialty view falls back to `project.my-work`, while all three protected views remain addressable by stable URL.

- [ ] **Step 2: Run the route tests and verify the new assertion fails**

Run: `node --experimental-strip-types --test test/projectViewRuntime.test.ts`

Expected: the new unavailable-view fallback assertion FAILS until resolver behavior is complete.

- [ ] **Step 3: Build `ProjectViewSidebar.vue`**

The component must accept only navigation state and emit intent; it must not fetch projects or perform business actions:

```vue
<template>
  <nav class="project-view-sidebar" aria-label="项目管理视图">
    <section v-for="group in orderedGroups" :key="group.groupKey" class="project-view-group">
      <h3>{{ group.label }}</h3>
      <button
        v-for="view in viewsByGroup(group.groupKey)"
        :key="view.viewKey"
        type="button"
        class="project-view-link"
        :class="{ active: view.viewKey === activeViewKey }"
        :aria-current="view.viewKey === activeViewKey ? 'page' : undefined"
        @click="$emit('select', view.viewKey)"
      >
        <Icon :name="view.icon" />
        <span>{{ view.label }}</span>
        <b v-if="meaningfulCount(view.viewKey) > 0">{{ meaningfulCount(view.viewKey) }}</b>
        <Icon v-if="view.protected" name="lock" class="protected-mark" title="核心视图" />
      </button>
    </section>
    <section v-if="config.personalViewsEnabled" class="project-view-group">
      <h3>我的视图</h3>
      <button v-for="view in personalViews" :key="view.id" type="button" class="project-view-link" :class="{ active: `personal:${view.id}` === activeViewKey }" @click="$emit('select', `personal:${view.id}`)">
        <Icon name="bookmark" />
        <span>{{ view.name }}</span>
      </button>
      <button type="button" class="project-view-save" @click="$emit('save-current')">+ 保存当前视图</button>
    </section>
  </nav>
</template>
```

Use existing `Icon.vue`, spacing, radius and color variables; no colored module dots, system-status blocks or upload buttons.

- [ ] **Step 4: Integrate the sidebar and remove duplicate audit module**

In `AppLayout.vue`:

- remove `/audit` from `mainNav`, `moduleDescriptions` and `sideNavMap`;
- render `<ProjectViewSidebar>` when `activeModule.path === '/project-management'`;
- keep existing generic side navigation for the other four modules and admin;
- on selection, call `router.push({ path: '/project-management', query: { ...route.query, view: viewKey } })` and remove stale `onlyMissingDocuments`, `onlyAuditLinked` and legacy `mode` query keys;
- keep “上传合同创建项目” in the project page header event path, not the sidebar.
- when a requested view is hidden or role-inaccessible, navigate to `project.my-work` and show the store's exact fallback reason once.

In `server/audit_api.py`, change the allowed top order to `['/', '/bidding', '/project-management', '/materials', '/finance']`; normalize persisted orders by dropping `/audit` without failing.

- [ ] **Step 5: Add the legacy audit redirect**

Replace the `/audit` component route with:

```typescript
{
  path: 'audit',
  name: 'LegacyAuditRedirect',
  redirect: (to) => legacyAuditLocation(to.query),
},
```

Do not remove backend `/api/audit/*` routes; only merge the product navigation and frontend route.

- [ ] **Step 6: Verify tests and production build**

Run:

```powershell
node --experimental-strip-types --test test/projectViewRuntime.test.ts
npm.cmd run build
```

Expected: tests PASS and Vite build completes with no TypeScript/Vue errors.

- [ ] **Step 7: Commit navigation integration**

```powershell
git add src/components/project/ProjectViewSidebar.vue src/views/AppLayout.vue src/router/index.ts server/audit_api.py src/styles/arco-premium-workbench.css test/projectViewRuntime.test.ts
git commit -m "feat: replace project menu with view sidebar"
```

### Task 6: Core and specialty project view renderers

**Files:**
- Create: `src/components/project/ProjectWorkList.vue`
- Create: `src/components/project/ProjectLifecycleBoard.vue`
- Create: `src/components/project/ProjectAuditProgressView.vue`
- Modify: `src/views/ProjectManagementView.vue`
- Modify: `src/views/KanbanView.vue`
- Modify: `src/api/projects.ts`
- Test: `test/projectViewRuntime.test.ts`

**Interfaces:**
- Consumes: Task 4 active view/store and existing `fetchWorkItems`, `fetchProjectRecords`, `KanbanView`.
- Produces: working `project.my-work`, `project.lifecycle`, `project.ledger`, `project.blocked`, `project.document-gaps`, `project.audit-progress` views.

- [ ] **Step 1: Add failing renderer mapping tests**

Add one table-driven test for all six system keys:

```typescript
test('maps every system view to its fixed renderer and backend-owned filters', () => {
  const cases = [
    ['project.my-work', 'work_items'],
    ['project.lifecycle', 'lifecycle'],
    ['project.ledger', 'ledger'],
    ['project.blocked', 'ledger'],
    ['project.document-gaps', 'ledger'],
    ['project.audit-progress', 'audit_progress'],
  ] as const
  for (const [viewKey, renderer] of cases) {
    assert.equal(systemViewDefinition(viewKey).renderer, renderer)
  }
})
```

- [ ] **Step 2: Run test and verify failure**

Run: `node --experimental-strip-types --test test/projectViewRuntime.test.ts`

Expected: FAIL because `systemViewDefinition` is not exported.

- [ ] **Step 3: Implement `ProjectWorkList.vue`**

Render `WorkItem[]` with project name, actionable description, due date only when present, level tag and one action button. Emit `open-project` and `open-path`; show the honest empty state “当前没有需要处理的项目事项”. Do not synthesize counts or tasks.

- [ ] **Step 4: Implement `ProjectLifecycleBoard.vue`**

Use the real project status options from `ProjectMeta` and real `ProjectRecord[]`. Group by `projectStatus`; each card shows project name, construction unit, manager, current document gap and contract amount via `MoneyDisplay`. Emit `open-project`; do not change lifecycle state by drag-and-drop in this phase.

- [ ] **Step 5: Implement fixed embedded audit progress**

`ProjectAuditProgressView.vue` must contain only:

```vue
<template>
  <KanbanView embedded fixed-view-mode="kanban" />
</template>

<script setup lang="ts">
import KanbanView from '@/views/KanbanView.vue'
</script>
```

Update `KanbanView.vue` props to:

```typescript
const props = defineProps<{ embedded?: boolean; fixedViewMode?: AuditViewMode }>()
const viewMode = ref<AuditViewMode>(props.fixedViewMode || 'kanban')
```

Hide its local “看板/甘特/表格” switch and layout selector when `fixedViewMode` is present, and do not write audit mode back to the route in fixed mode.

- [ ] **Step 6: Switch the project workspace by renderer**

In `ProjectManagementView.vue`, keep current dialogs/details mounted and replace only the main ledger body with:

```vue
<ProjectWorkList
  v-if="activeProjectView.renderer === 'work_items'"
  :items="workItems"
  :loading="workItemsLoading"
  @open-project="openProjectById"
  @open-path="openWorkItemPath"
/>
<ProjectLifecycleBoard
  v-else-if="activeProjectView.renderer === 'lifecycle'"
  :records="records"
  :statuses="meta.projectStatuses"
  :loading="recordsLoading"
  @open-project="openProjectById"
/>
<ProjectAuditProgressView v-else-if="activeProjectView.renderer === 'audit_progress'" />
<section v-else class="project-ledger-workspace">
  <!-- retain the existing project ledger toolbar, summary and table markup here -->
</section>
```

When the active view changes, assign filters from `filtersForProjectView(activeProjectView)`, reset page to 1 and call the existing `loadRecords()`. For lifecycle, load all records page-by-page using the real API total rather than increasing page size beyond the server limit. For audit progress, do not make a duplicate project-list request.

- [ ] **Step 7: Replace old audit links inside project management**

Update `goAudit`, work-item route handling and post-start-audit navigation to:

```typescript
router.push({
  path: '/project-management',
  query: { view: 'project.audit-progress', projectId: auditProjectId },
})
```

Keep `startProjectAudit()` and its lifecycle eligibility unchanged.

- [ ] **Step 8: Run frontend and lifecycle tests, then build**

```powershell
node --experimental-strip-types --test test/projectViewRuntime.test.ts test/auditEligibility.test.ts test/task4bLifecycleSafety.test.ts
python -m unittest server.tests.test_lifecycle server.tests.test_lifecycle_api_contract -v
npm.cmd run build
```

Expected: all tests PASS and build succeeds.

- [ ] **Step 9: Commit view renderers**

```powershell
git add src/components/project/ProjectWorkList.vue src/components/project/ProjectLifecycleBoard.vue src/components/project/ProjectAuditProgressView.vue src/views/ProjectManagementView.vue src/views/KanbanView.vue src/api/projects.ts test/projectViewRuntime.test.ts
git commit -m "feat: render project work views"
```

### Task 7: Server-backed personal views

**Files:**
- Create: `src/components/project/ProjectPersonalViewDialog.vue`
- Modify: `src/store/projectViews.ts`
- Modify: `src/views/ProjectManagementView.vue`
- Modify: `src/components/project/ProjectViewSidebar.vue`
- Test: `test/projectViewRuntime.test.ts`

**Interfaces:**
- Consumes: personal-view API from Task 3 and current project filters from the ledger.
- Produces: save, rename, set default and delete personal views without local-only authority.

- [ ] **Step 1: Add failing personal view serialization tests**

Test that serialization includes only name, presentation, whitelisted filters, groupBy, columns and `isDefault`; it must drop page, pageSize, projectId and data-scope fields.

- [ ] **Step 2: Run test and verify failure**

Run: `node --experimental-strip-types --test test/projectViewRuntime.test.ts`

Expected: FAIL because `personalViewPayloadFromWorkspace` does not exist.

- [ ] **Step 3: Implement the personal view dialog**

The modal contains: personal view name, display type segmented control (`表格 / 看板`), “设为我的默认入口” checkbox, a read-only summary of current filters, cancel and save. It must not expose field creation or permission scope.

- [ ] **Step 4: Connect personal view mutations**

In the Pinia store, add `createPersonal`, `updatePersonal`, `removePersonal` and `setPersonalDefault`; after every mutation re-fetch `/api/project-views` to use server truth. In `ProjectManagementView.vue`, open the dialog from the sidebar event with the exact current filters and visible columns. After successful save, navigate to `view=personal:{id}`.

- [ ] **Step 5: Remove localStorage as the source of truth**

Read `project-management-saved-filters` only once when the server has no personal views. Offer an explicit “导入本机已有筛选” action; do not silently upload browser data. After a successful import, remove the old key. Existing local filters remain untouched when import is cancelled or fails.

- [ ] **Step 6: Verify and build**

```powershell
node --experimental-strip-types --test test/projectViewRuntime.test.ts
npm.cmd run build
```

Expected: tests PASS; personal views survive refresh because they are returned by the server.

- [ ] **Step 7: Commit personal views**

```powershell
git add src/components/project/ProjectPersonalViewDialog.vue src/store/projectViews.ts src/views/ProjectManagementView.vue src/components/project/ProjectViewSidebar.vue test/projectViewRuntime.test.ts
git commit -m "feat: save personal project views"
```

### Task 8: Three-pane admin editor with publish and rollback

**Files:**
- Create: `src/views/admin/AdminProjectViews.vue`
- Modify: `src/router/index.ts`
- Modify: `src/views/AppLayout.vue`
- Modify: `src/api/projectViews.ts`
- Modify: `src/styles/arco-premium-workbench.css`
- Test: `test/projectViewRuntime.test.ts`

**Interfaces:**
- Consumes: admin API and normalized config.
- Produces: `/admin/project-views` editor with draft preview, publish and rollback.

- [ ] **Step 1: Add failing admin guard tests to the runtime suite**

Add tests for `canHideProjectView(viewKey)`, `canDeleteProjectView(viewKey)` and `sanitizeAdminViewMutation()`; assert all three core keys return false for hide/delete and their `viewKey`, `renderer`, `presentation`, `protected` values cannot be overwritten.

- [ ] **Step 2: Run the tests and verify failure**

Run: `node --experimental-strip-types --test test/projectViewRuntime.test.ts`

Expected: FAIL because admin guard helpers do not exist.

- [ ] **Step 3: Add the admin route and navigation entry**

Add child route:

```typescript
{
  path: 'project-views',
  name: 'AdminProjectViews',
  component: () => import('@/views/admin/AdminProjectViews.vue'),
},
```

Add `项目管理设置` or `左栏与公共视图` to the admin side navigation with path `/admin/project-views`.

- [ ] **Step 4: Implement the three-pane editor**

`AdminProjectViews.vue` layout:

```vue
<div class="project-view-admin">
  <PageHeader title="项目管理视图" description="配置项目管理左栏、公共视图和默认入口">
    <template #actions>
      <AButton variant="outline" :disabled="!dirty" @click="saveDraft">保存草稿</AButton>
      <AButton theme="primary" :disabled="!draftVersion" @click="confirmPublish">发布配置</AButton>
      <AButton variant="outline" @click="historyVisible = true">版本记录</AButton>
    </template>
  </PageHeader>
  <div class="project-view-editor-grid">
    <section class="preview-pane"><ProjectViewSidebar :config="draft" :personal-views="[]" :counts="{}" :active-view-key="draft.enterpriseDefaultViewKey" /></section>
    <section class="tree-pane"><ProjectViewTree v-model="draft" @select="selectedKey = $event" /></section>
    <section class="properties-pane"><ProjectViewProperties v-model="draft" :selected-key="selectedKey" /></section>
  </div>
</div>
```

The middle pane uses native drag events to reorder groups/views. Core rows show a lock, disable visibility/delete controls and keep their stable key read-only. A group containing any core view cannot be deleted until those views are moved into another existing group. The property pane supports label, icon, group, specialty-view visibility, default entry, whitelisted filters, grouping, sorting, columns, count rule, current roles, personal-view enablement and limit.

The preview pane includes a role selector with the existing values `管理员 / 编辑者 / 查看者`. It filters only specialty-view entry visibility and action affordances; all three protected core views remain visible in every role preview. The selector is preview state only and is never written as the current administrator's role.

- [ ] **Step 5: Implement preview, publish and rollback confirmation**

- Preview always renders the normalized draft, never the raw mutable object.
- Publish confirmation lists renamed, moved, hidden and default-view changes.
- Rollback confirmation states that rollback creates a new version.
- Failed publish keeps the local draft and displays the exact server error.
- Successful publish refreshes admin state and the project-view store.
- Closing or navigating away with an unsaved local draft requires a second confirmation; saving a server draft clears that local dirty state.

- [ ] **Step 6: Verify guards and build**

```powershell
node --experimental-strip-types --test test/projectViewRuntime.test.ts
npm.cmd run build
npm.cmd run test:premium-theme
```

Expected: runtime tests PASS, build succeeds and premium-theme verification passes.

- [ ] **Step 7: Commit the admin editor**

```powershell
git add src/views/admin/AdminProjectViews.vue src/router/index.ts src/views/AppLayout.vue src/api/projectViews.ts src/utils/projectViewRuntime.ts src/styles/arco-premium-workbench.css test/projectViewRuntime.test.ts
git commit -m "feat: manage project view configuration"
```

### Task 9: Integrated verification, honest empty states and release readiness

**Files:**
- Modify: `docs/superpowers/specs/2026-07-16-project-management-configurable-view-sidebar-design.md`
- Create: `docs/superpowers/verification/2026-07-16-project-view-sidebar-checklist.md`
- Modify only if tests expose defects: files introduced or explicitly modified in Tasks 1-8.

**Interfaces:**
- Consumes: complete feature.
- Produces: repeatable release gate and traceability from spec to implementation.

- [ ] **Step 1: Run all focused backend tests**

```powershell
python -m unittest `
  server.tests.test_project_view_domain `
  server.tests.test_project_view_repository `
  server.tests.test_project_view_api_contract `
  server.tests.test_lifecycle `
  server.tests.test_lifecycle_repository `
  server.tests.test_lifecycle_api_contract -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run focused frontend tests and build**

```powershell
node --experimental-strip-types --test `
  test/projectViewRuntime.test.ts `
  test/auditEligibility.test.ts `
  test/task4bLifecycleSafety.test.ts
npm.cmd run build
npm.cmd run test:premium-theme
```

Expected: all tests PASS; build exits 0; premium theme verification exits 0.

- [ ] **Step 3: Run repository hygiene checks**

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors. `git status` may still show pre-existing unrelated files; only this feature's files may be staged in subsequent commits.

- [ ] **Step 4: Complete authenticated browser acceptance**

Use a clean authenticated local session and verify the desktop view system at width 1440, then verify the existing mobile project route at width 390 remains usable:

1. Top navigation has exactly five modules and no audit module.
2. Project left sidebar has the four groups and contains no upload/start/status controls.
3. Core views remain visible after an administrator attempts to hide/delete them.
4. Every view URL survives refresh and back/forward navigation.
5. Old `#/audit?projectId=...` opens `project.audit-progress` with the same project context.
6. Empty datasets show honest empty states and no sample records.
7. Editor/viewer permissions change available actions but not the core sidebar skeleton.
8. Personal view save, refresh, rename, default and delete use server persistence.
9. Admin draft does not affect users before publish; publish updates after refresh; rollback creates a newer version.
10. Project details return to the source view and preserve `view` plus project context.
11. At 390px, `/project-management` still redirects to the existing mobile project page; the desktop view sidebar is not squeezed into the mobile layout.

- [ ] **Step 5: Record verification evidence**

Create `docs/superpowers/verification/2026-07-16-project-view-sidebar-checklist.md` with a table containing `检查项 / 结果 / 证据 / 备注`, the commands above, the tested viewport sizes, and exact URLs. Do not paste credentials or tokens.

- [ ] **Step 6: Update the design spec status**

Change the spec header from `状态：已确认` to `状态：已实现，待生产验收` only after Steps 1-5 pass. Add an implementation section listing the stable routes and migrations; do not claim deployment.

- [ ] **Step 7: Commit verification artifacts**

```powershell
git add docs/superpowers/specs/2026-07-16-project-management-configurable-view-sidebar-design.md docs/superpowers/verification/2026-07-16-project-view-sidebar-checklist.md
git commit -m "docs: verify project view sidebar"
```

## Final Release Gate

Before any push or deployment, run:

```powershell
git log --oneline -10
git status --short
git diff --stat HEAD~9..HEAD
```

Review that the feature commits contain only the planned files. Deployment must then use the repository's `deploy-shenjikanban` skill, selectively stage any final release fix, push `main`, deploy to `121.4.36.112`, and verify both service health and the authenticated production UI. Do not deploy from a worktree containing unrelated staged files.
