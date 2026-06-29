#!/usr/bin/env python3
import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "audit-kanban.sqlite3"
STAGES = [
    ("submitted", "报审待受理", "#3366FF"),
    ("first_audit", "一级初审", "#FF8D1A"),
    ("second_audit", "二级复审", "#E34D59"),
    ("conclusion", "定案结论", "#14B8A6"),
    ("archived", "办结归档", "#8E95A3"),
]
FORBIDDEN_ATTACHMENT_SUFFIXES = (
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".gz",
    ".bz2",
    ".xz",
    ".iso",
)
TEXT_PREVIEW_SUFFIXES = {".txt", ".csv", ".json", ".log", ".md", ".xml", ".yml", ".yaml"}
INLINE_PREVIEW_PREFIXES = ("image/", "audio/", "video/")
INLINE_PREVIEW_TYPES = {"application/pdf"}


def is_production():
    env = (os.environ.get("APP_ENV") or os.environ.get("NODE_ENV") or os.environ.get("JIQING_ENV") or "").lower()
    return env in {"prod", "production"}


def now_iso():
    return datetime.now().replace(microsecond=0).isoformat()


def day(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


def new_id():
    return str(uuid.uuid4())


def normalize_hex_color(value):
    raw = str(value or "").strip()
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", raw)
    return f"#{match.group(1).upper()}" if match else ""


def hex_to_rgb(hex_value):
    value = normalize_hex_color(hex_value).lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def rgb_to_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, round(rgb[0]))),
        max(0, min(255, round(rgb[1]))),
        max(0, min(255, round(rgb[2]))),
    )


def mix_color(color, target, weight):
    from_r, from_g, from_b = hex_to_rgb(color)
    to_r, to_g, to_b = hex_to_rgb(target)
    return rgb_to_hex((
        from_r * (1 - weight) + to_r * weight,
        from_g * (1 - weight) + to_g * weight,
        from_b * (1 - weight) + to_b * weight,
    ))


def relative_luminance(hex_value):
    r, g, b = hex_to_rgb(hex_value)

    def channel(value):
        normalized = value / 255
        return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def sanitize_brand_color(value, fallback="#4787F0"):
    normalized = normalize_hex_color(value)
    safe_fallback = normalize_hex_color(fallback) or "#4787F0"
    if not normalized:
        return safe_fallback
    if relative_luminance(normalized) <= 0.82:
        return normalized
    darker = mix_color(normalized, "#000000", 0.45)
    if relative_luminance(darker) <= 0.82:
        return darker
    darker_fallback = mix_color(normalized, "#000000", 0.6)
    return darker_fallback if relative_luminance(darker_fallback) <= 0.82 else safe_fallback


def token_secret():
    secret = os.environ.get("TOKEN_SECRET") or os.environ.get("SESSION_SECRET")
    if secret:
        return secret
    if is_production():
        raise RuntimeError("SESSION_SECRET or TOKEN_SECRET is required in production")
    return "dev-only-change-me"


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256$120000${salt}${base64.b64encode(digest).decode('ascii')}"


def verify_password(password, stored):
    try:
        algo, rounds, salt, encoded = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(rounds))
        return hmac.compare_digest(base64.b64encode(digest).decode("ascii"), encoded)
    except Exception:
        return False


def b64url_encode(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(text):
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("ascii"))


def sign_token(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    body = b64url_encode(raw)
    sig = hmac.new(token_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{b64url_encode(sig)}"


def verify_token(token):
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(token_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(b64url_encode(expected), sig):
            return None
        payload = json.loads(b64url_decode(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def user_payload(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "displayName": row["display_name"],
        "email": row["email"],
        "role": row["role"],
        "isActive": bool(row["is_active"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def connect():
    db_path = Path(os.environ.get("AUDIT_DB_PATH", DEFAULT_DB))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def read_json(handler):
    length = int(handler.headers.get("Content-Length") or "0")
    if length == 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw or "{}")


def upload_root():
    return Path(os.environ.get("UPLOAD_ROOT", ROOT / "uploads")).resolve()


def max_upload_size():
    try:
        return int(os.environ.get("MAX_UPLOAD_SIZE", str(25 * 1024 * 1024)))
    except ValueError:
        return 25 * 1024 * 1024


def row_get(row, key, default=""):
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def is_forbidden_attachment_name(filename):
    lower = filename.lower()
    return any(lower.endswith(suffix) for suffix in FORBIDDEN_ATTACHMENT_SUFFIXES)


def is_path_like_filename(filename):
    return "/" in filename or "\\" in filename or filename in {"", ".", ".."}


def safe_attachment_path(relative_path):
    cleaned = (relative_path or "").replace("\\", "/").lstrip("/")
    if not cleaned or ".." in Path(cleaned).parts:
        raise ValueError("非法附件路径")
    root = upload_root()
    path = (root / cleaned).resolve()
    if os.path.commonpath([str(root), str(path)]) != str(root):
        raise ValueError("非法附件路径")
    return path


def parse_multipart_file(handler):
    content_type = handler.headers.get("Content-Type", "")
    match = re.search(r"boundary=(?P<boundary>\"[^\"]+\"|[^;]+)", content_type)
    if "multipart/form-data" not in content_type or not match:
        raise ValueError("请使用 multipart/form-data 上传文件")
    boundary = match.group("boundary").strip('"').encode("utf-8")
    length = int(handler.headers.get("Content-Length") or "0")
    limit = max_upload_size()
    if length <= 0:
        raise ValueError("上传内容为空")
    if length > limit:
        raise ValueError(f"文件不能超过 {limit // 1024 // 1024}MB")
    try:
        raw = handler.rfile.read(length)
    except TimeoutError as exc:
        raise ValueError("上传读取超时，请重试") from exc
    if len(raw) != length:
        raise ValueError("上传内容不完整，请重试")
    delimiter = b"--" + boundary
    for part in raw.split(delimiter):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        header_blob, body = part.split(b"\r\n\r\n", 1)
        headers = header_blob.decode("iso-8859-1", errors="ignore")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        if 'name="file"' not in disposition or "filename=" not in disposition:
            continue
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        filename = filename_match.group(1) if filename_match else ""
        return filename, body.rstrip(b"\r\n")
    raise ValueError("未找到上传文件")


def attachment_payload(row):
    original_name = row_get(row, "original_name") or row_get(row, "file_name")
    mime_type = row_get(row, "mime_type") or row_get(row, "file_type") or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    created_at = row_get(row, "created_at") or row_get(row, "uploaded_at")
    file_ext = row_get(row, "file_ext") or Path(original_name).suffix.lower()
    can_preview = mime_type in INLINE_PREVIEW_TYPES or mime_type.startswith(INLINE_PREVIEW_PREFIXES) or file_ext in TEXT_PREVIEW_SUFFIXES
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "originalName": original_name,
        "storedName": row_get(row, "stored_name"),
        "fileExt": file_ext,
        "mimeType": mime_type,
        "fileSize": int(row_get(row, "file_size", 0) or 0),
        "uploadedBy": row_get(row, "uploaded_by"),
        "uploadedByName": row_get(row, "uploaded_by_name") or row_get(row, "uploaded_by"),
        "createdAt": created_at,
        "previewUrl": f"/api/audit/attachments/{row['id']}/preview",
        "downloadUrl": f"/api/audit/attachments/{row['id']}/download",
        "canPreview": can_preview,
        "file_name": original_name,
        "file_type": mime_type,
        "uploaded_by": row_get(row, "uploaded_by_name") or row_get(row, "uploaded_by"),
        "uploaded_at": created_at,
    }


def row_dict(row):
    return dict(row) if row else None


def amount_payload(row):
    return {
        "contractAmount": row["contract_amount"],
        "submittedAmount": row["submitted_amount"],
        "firstAuditAmount": row["first_audit_amount"],
        "secondAuditAmount": row["second_audit_amount"],
        "auditDifference": row["audit_difference"],
        "finalPayable": row["final_payable"],
        "paidAmount": row["paid_amount"],
    }


def project_payload(conn, row):
    values = conn.execute(
        "SELECT field_key, field_value FROM audit_project_field_values WHERE project_id = ?",
        (row["id"],),
    ).fetchall()
    custom_fields = {v["field_key"]: v["field_value"] for v in values}
    return {
        "id": row["id"],
        "projectCode": row["project_code"] or row["settlement_no"],
        "projectName": row["project_name"],
        "auditedUnit": row["audited_unit"] or row["second_audit_department"],
        "auditType": row["audit_type"] or row["category"],
        "sectionBuilding": row["section_building"],
        "settlementNo": row["settlement_no"],
        "category": row["category"],
        "priority": row["priority"],
        "contractor": {"name": row["contractor_name"], "phone": row["contractor_phone"]},
        "firstAudit": {"companyName": row["first_audit_company"], "auditor": {"name": row["first_auditor_name"]}},
        "secondAudit": {"department": row["second_audit_department"], "auditor": {"name": row["second_auditor_name"]}},
        "amount": amount_payload(row),
        "deadline": {
            "submitDate": row["submit_date"] or row["start_date"],
            "auditDeadline": row["audit_deadline"] or row["planned_end_date"],
        },
        "startDate": row["start_date"] or row["submit_date"],
        "plannedEndDate": row["planned_end_date"] or row["audit_deadline"],
        "actualEndDate": row["actual_end_date"],
        "docStatus": row["doc_status"],
        "stage": row["current_stage"],
        "status": row["status"],
        "progressPercent": row["progress_percent"],
        "managerName": row["manager_name"] or row["contractor_name"],
        "isDelayed": bool(row["is_delayed"]),
        "delayDays": row["delay_days"],
        "description": row["description"],
        "remark": {"dispute": row["remark_dispute"], "coordination": row["remark_coordination"]},
        "sortOrder": row["sort_order"],
        "isArchived": bool(row["is_archived"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "customFields": custom_fields,
    }


def log_action(conn, project_id, action, operator="", note="", before=None, after=None):
    conn.execute(
        """
        INSERT INTO audit_project_logs
        (id, project_id, action, operator, note, before_json, after_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id(),
            project_id,
            action,
            operator,
            note,
            json.dumps(before or {}, ensure_ascii=False),
            json.dumps(after or {}, ensure_ascii=False),
            now_iso(),
        ),
    )
    conn.execute(
        "UPDATE audit_project_logs SET log_type = ?, content = ?, operator_name = ? WHERE rowid = last_insert_rowid()",
        (action, note, operator),
    )


def bootstrap():
    with connect() as conn:
        schema = (ROOT / "schema.sql").read_text(encoding="utf-8")
        conn.executescript(schema)
        ensure_compatible_columns(conn)
        backfill_derived_fields(conn)
        seed_system_settings(conn)
        seed_theme_configs(conn)
        seed_admin_user(conn)
        seed_field_configs(conn)
        seed_options(conn)
        count = conn.execute("SELECT COUNT(*) AS c FROM audit_projects").fetchone()["c"]
        if count == 0:
            seed_projects(conn)
        conn.commit()


def seed_system_settings(conn):
    ts = now_iso()
    defaults = [
        ("registration_open", {"enabled": False, "requireApproval": True}, "auth", "是否开放注册"),
        ("login_rules", {"minPasswordLength": 8, "maxLoginAttempts": 5, "sessionTimeoutMinutes": 480, "allowConcurrentSessions": True}, "auth", "登录规则"),
        ("system_name", "江苏集庆·工程管理系统", "system", "系统名称"),
        ("current_theme", {"themeKey": "arco-theme-0000", "darkMode": False, "compactMode": False, "applyScope": "global", "brandColor": "#4787F0", "themePackage": "", "sidebarLogoVariant": "color"}, "theme", "当前主题"),
    ]
    for key, value, group, desc in defaults:
        conn.execute(
            """
            INSERT OR IGNORE INTO system_settings
            (setting_key, setting_value, setting_group, description, updated_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'system', ?, ?)
            """,
            (key, json.dumps(value, ensure_ascii=False), group, desc, ts, ts),
        )


def seed_theme_configs(conn):
    ts = now_iso()
    themes = [
        ("arco-theme-0000", "Arco 官方默认主题", "@arco-themes/vue-0000", ["#4787F0", "#14C9C9", "#00B42A", "#FF7D00"], 1, 1, 10),
        ("arco-default", "Arco fallback", "@arco-design/web-vue", ["#4787F0", "#0FC6C2", "#00B42A", "#86909C"], 1, 0, 20),
        ("jiqing-blue", "专业蓝主题", "builtin:jiqing-blue", ["#0E42D2", "#168CFF", "#14C9C9", "#E8F3FF"], 1, 0, 30),
        ("engineering-green", "青绿工程主题", "builtin:engineering-green", ["#008F7A", "#00B42A", "#14C9C9", "#E8FFFB"], 1, 0, 40),
        ("gov-gray-blue", "灰蓝政企主题", "builtin:gov-gray-blue", ["#1D3557", "#457B9D", "#A8DADC", "#F1FAEE"], 1, 0, 50),
        ("dark-command", "深色大屏主题", "builtin:dark-command", ["#0B1220", "#165DFF", "#14C9C9", "#00B42A"], 1, 0, 60),
    ]
    for key, name, package, colors, enabled, is_default, order in themes:
        conn.execute(
            """
            INSERT OR IGNORE INTO system_theme_configs
            (id, theme_key, theme_name, package_name, preview_colors, apply_scope,
             is_enabled, is_default, dark_mode_enabled, compact_mode_enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'global', ?, ?, 0, 0, ?, ?, ?)
            """,
            (new_id(), key, name, package, json.dumps(colors, ensure_ascii=False), enabled, is_default, order, ts, ts),
        )
        conn.execute(
            """
            UPDATE system_theme_configs
            SET theme_name = ?, package_name = ?, preview_colors = ?, is_enabled = ?,
                is_default = ?, sort_order = ?, updated_at = ?
            WHERE theme_key = ?
            """,
            (name, package, json.dumps(colors, ensure_ascii=False), enabled, is_default, order, ts, key),
        )


def seed_admin_user(conn):
    existing = conn.execute("SELECT COUNT(*) AS c FROM system_users").fetchone()["c"]
    if existing:
        return
    username = os.environ.get("ADMIN_INIT_USERNAME", "").strip()
    password = os.environ.get("ADMIN_INIT_PASSWORD", "")
    allow_dev_fallback = os.environ.get("ENABLE_DEV_ADMIN_FALLBACK", "0") == "1"
    if not username and allow_dev_fallback:
        username = "admin"
        password = os.environ.get("VITE_LOCAL_ADMIN_PASSWORD") or "admin"
    if is_production() and username == "admin" and password == "admin":
        print("Refusing to create admin/admin in production. Set a secure ADMIN_INIT_PASSWORD.", flush=True)
        return
    if not username or not password:
        print("No system admin created. Set ADMIN_INIT_USERNAME and ADMIN_INIT_PASSWORD before first production start.", flush=True)
        return
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO system_users
        (id, username, display_name, email, password_hash, role, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'admin', 1, ?, ?)
        """,
        (new_id(), username, os.environ.get("ADMIN_INIT_DISPLAY_NAME", "系统管理员"), os.environ.get("ADMIN_INIT_EMAIL", ""), hash_password(password), ts, ts),
    )


def ensure_compatible_columns(conn):
    migrations = {
        "audit_projects": {
            "project_code": "TEXT DEFAULT ''",
            "audited_unit": "TEXT DEFAULT ''",
            "audit_type": "TEXT DEFAULT ''",
            "start_date": "TEXT DEFAULT ''",
            "planned_end_date": "TEXT DEFAULT ''",
            "actual_end_date": "TEXT DEFAULT ''",
            "progress_percent": "INTEGER DEFAULT 0",
            "manager_name": "TEXT DEFAULT ''",
            "is_delayed": "INTEGER DEFAULT 0",
            "delay_days": "INTEGER DEFAULT 0",
            "description": "TEXT DEFAULT ''",
        },
        "audit_project_stages": {
            "stage_order": "INTEGER DEFAULT 0",
            "start_date": "TEXT DEFAULT ''",
            "end_date": "TEXT DEFAULT ''",
            "handler_name": "TEXT DEFAULT ''",
            "remark": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT ''",
            "updated_at": "TEXT DEFAULT ''",
        },
        "audit_project_logs": {
            "log_type": "TEXT DEFAULT ''",
            "content": "TEXT DEFAULT ''",
            "operator_name": "TEXT DEFAULT ''",
        },
        "audit_project_attachments": {
            "original_name": "TEXT DEFAULT ''",
            "stored_name": "TEXT DEFAULT ''",
            "file_ext": "TEXT DEFAULT ''",
            "mime_type": "TEXT DEFAULT ''",
            "file_size": "INTEGER DEFAULT 0",
            "relative_path": "TEXT DEFAULT ''",
            "uploaded_by_name": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT ''",
            "deleted_at": "TEXT DEFAULT ''",
            "is_deleted": "INTEGER DEFAULT 0",
        },
        "audit_field_configs": {
            "field_name": "TEXT DEFAULT ''",
            "module": "TEXT DEFAULT 'project'",
            "display_scene": "TEXT DEFAULT ''",
            "stage_key": "TEXT DEFAULT ''",
            "is_required": "INTEGER DEFAULT 0",
            "placeholder": "TEXT DEFAULT ''",
            "default_value": "TEXT DEFAULT ''",
            "is_enabled": "INTEGER DEFAULT 1",
        },
        "audit_field_options": {
            "field_key": "TEXT DEFAULT ''",
            "is_enabled": "INTEGER DEFAULT 1",
            "is_system": "INTEGER DEFAULT 0",
        },
        "audit_project_field_values": {
            "created_at": "TEXT DEFAULT ''",
        },
        "audit_stage_field_values": {
            "project_id": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT ''",
        },
    }
    for table, columns in migrations.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, definition in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def backfill_derived_fields(conn):
    today = date.today().isoformat()
    rows = conn.execute("SELECT id, settlement_no, category, current_stage, contractor_name, submit_date, audit_deadline, status, progress_percent FROM audit_projects").fetchall()
    for row in rows:
        planned = row["audit_deadline"] or ""
        is_delayed = bool(planned and planned < today and row["current_stage"] != "archived")
        delay_days = 0
        if is_delayed:
            try:
                delay_days = (date.fromisoformat(today) - date.fromisoformat(planned)).days
            except ValueError:
                delay_days = 0
        status = "completed" if row["current_stage"] == "archived" else ("delayed" if is_delayed else (row["status"] or "active"))
        progress = row["progress_percent"] or (100 if row["current_stage"] == "archived" else 30)
        conn.execute(
            """
            UPDATE audit_projects
            SET project_code = COALESCE(NULLIF(project_code, ''), ?),
                audited_unit = COALESCE(NULLIF(audited_unit, ''), second_audit_department),
                audit_type = COALESCE(NULLIF(audit_type, ''), ?),
                start_date = COALESCE(NULLIF(start_date, ''), submit_date),
                planned_end_date = COALESCE(NULLIF(planned_end_date, ''), audit_deadline),
                manager_name = COALESCE(NULLIF(manager_name, ''), ?),
                status = ?,
                progress_percent = ?,
                is_delayed = ?,
                delay_days = ?
            WHERE id = ?
            """,
            (row["settlement_no"], row["category"], row["contractor_name"], status, progress, int(is_delayed), delay_days, row["id"]),
        )


def seed_field_configs(conn):
    ts = now_iso()
    configs = [
        ("project_code", "项目编号", "text", "", "projectCode", 0, 1, 1, 1, 1, 0, 5),
        ("project_name", "项目名称", "text", "", "projectName", 1, 1, 1, 1, 1, 0, 10),
        ("audited_unit", "被审计单位", "select", "audited_unit", "auditedUnit", 0, 1, 1, 1, 1, 0, 20),
        ("audit_type", "审计类型", "select", "audit_type", "auditType", 1, 1, 1, 1, 1, 0, 30),
        ("section_building", "分部/楼栋", "text", "", "sectionBuilding", 0, 0, 0, 1, 1, 0, 40),
        ("settlement_no", "结算编号", "text", "", "settlementNo", 0, 0, 1, 1, 1, 0, 50),
        ("category", "工程分类", "select", "category", "category", 1, 0, 0, 1, 1, 0, 60),
        ("priority", "优先级", "select", "priority", "priority", 1, 1, 1, 1, 1, 0, 70),
        ("manager_name", "负责人", "select", "manager", "managerName", 0, 1, 1, 1, 1, 0, 80),
        ("start_date", "开始日期", "date", "", "startDate", 0, 0, 1, 1, 1, 1, 90),
        ("planned_end_date", "计划完成日期", "date", "", "plannedEndDate", 0, 1, 1, 1, 1, 1, 100),
        ("actual_end_date", "实际完成日期", "date", "", "actualEndDate", 0, 0, 1, 1, 1, 1, 110),
        ("progress_percent", "进度百分比", "number", "", "progressPercent", 0, 1, 1, 1, 1, 1, 120),
        ("status", "项目状态", "select", "status", "status", 0, 1, 1, 1, 1, 0, 130),
        ("is_delayed", "是否延期", "boolean", "", "isDelayed", 0, 1, 1, 1, 0, 0, 140),
        ("submitted_amount", "送审金额", "number", "", "amount.submittedAmount", 0, 0, 1, 1, 1, 0, 150),
        ("current_stage", "当前阶段", "select", "stage", "stage", 1, 1, 1, 1, 1, 1, 160),
        ("doc_status", "资料状态", "select", "doc_status", "docStatus", 0, 0, 1, 1, 1, 0, 170),
        ("description", "项目描述", "textarea", "", "description", 0, 0, 0, 1, 1, 0, 180),
        ("remark_coordination", "协调记录", "textarea", "", "remark.coordination", 0, 0, 0, 1, 1, 0, 190),
    ]
    for cfg in configs:
        conn.execute(
            """
            INSERT OR IGNORE INTO audit_field_configs
            (id, entity_type, field_key, field_label, field_type, option_group, bind_field, required,
             visible_in_card, visible_in_table, visible_in_detail, visible_in_form, visible_in_gantt,
             sort_order, enabled, created_at, updated_at)
            VALUES (?, 'project', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (new_id(), *cfg, ts, ts),
        )


def seed_options(conn):
    ts = now_iso()
    options = {
        "stage": [(s[1], s[0], s[2]) for s in STAGES],
        "priority": [("S0 特急", "S0", "#E34D59"), ("S1 紧急", "S1", "#ED7B2F"), ("S2 普通", "S2", "#0052D9"), ("S3 低", "S3", "#8C8C8C")],
        "category": [("竣工总结算", "竣工总结算", ""), ("分部结算", "分部结算", ""), ("现场签证", "现场签证", ""), ("工程变更", "工程变更", ""), ("安装造价", "安装造价", ""), ("市政结算", "市政结算", "")],
        "audit_type": [("工程审计", "工程审计", "#0052D9"), ("财务审计", "财务审计", "#00A870"), ("专项审计", "专项审计", "#ED7B2F"), ("离任审计", "离任审计", "#8C8C8C"), ("内控审计", "内控审计", "#14B8A6")],
        "status": [("未开始", "not_started", "#8C8C8C"), ("进行中", "active", "#0052D9"), ("延期", "delayed", "#E34D59"), ("已完成", "completed", "#00A870"), ("暂停", "paused", "#ED7B2F")],
        "doc_status": [("资料齐全", "资料齐全", "#00A870"), ("缺图纸", "缺图纸", "#ED7B2F"), ("缺变更签证", "缺变更签证", "#E34D59"), ("资料退回补件", "资料退回补件", "#8C8C8C")],
        "contractor": [("张建国", "张建国", ""), ("陈志远", "陈志远", ""), ("中建三局", "中建三局", ""), ("中铁四局", "中铁四局", "")],
        "manager": [("张建国", "张建国", ""), ("陈志远", "陈志远", ""), ("王志强", "王志强", ""), ("李明辉", "李明辉", "")],
        "audited_unit": [("建设单位审计部", "建设单位审计部", ""), ("翡翠湾置业成本部", "翡翠湾置业成本部", ""), ("XX市城投集团审计部", "XX市城投集团审计部", "")],
        "audit_unit": [("北京华夏工程造价咨询有限公司", "北京华夏工程造价咨询有限公司", ""), ("上海东方造价咨询有限公司", "上海东方造价咨询有限公司", ""), ("建设单位审计部", "建设单位审计部", "")],
    }
    for group_key, rows in options.items():
        for index, (label, value, color) in enumerate(rows):
            conn.execute(
                """
                INSERT OR IGNORE INTO audit_field_options
                (id, group_key, option_label, option_value, color, sort_order, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (new_id(), group_key, label, value, color, index * 10, ts, ts),
            )


def seed_projects(conn):
    base = [
        ("XX市轨道交通5号线一期工程土建施工总承包", "体育中心站", "GDJT-2026-001", "竣工总结算", "S0", "张建国", 89250000, "submitted", "资料齐全", -15, 45),
        ("翡翠湾二期住宅项目总承包工程", "9#-12#及地下车库", "FCW-2026-038", "分部结算", "S1", "陈志远", 24120000, "submitted", "缺图纸", -7, 53),
        ("京港高铁商丘至合肥段站房工程", "商丘站-亳州站区间", "JG-2026-089", "竣工总结算", "S0", "中铁四局", 168500000, "first_audit", "资料齐全", -45, 15),
        ("龙湖天街商业综合体机电安装工程", "B1-5F机电安装", "LH-2026-156", "安装造价", "S1", "杨建华", 35600000, "first_audit", "资料齐全", -30, 30),
        ("金茂府高端住宅区总承包工程", "1-8#楼及会所", "JMF-2026-055", "竣工总结算", "S0", "中建三局", 312000000, "second_audit", "资料齐全", -60, 0),
        ("东海岸污水处理厂扩建工程", "二期生化池", "DH-2026-167", "市政结算", "S1", "钟大伟", 52300000, "second_audit", "资料齐全", -40, -3),
        ("天誉湾高端住宅一期总承包工程", "1-5#楼", "TY-2026-012", "竣工总结算", "S0", "中建八局", 213500000, "conclusion", "资料齐全", -75, -2),
        ("光明大道市政道路改造工程", "K0+000至K3+200段", "GM-2026-098", "市政结算", "S1", "中铁十二局", 49800000, "conclusion", "资料齐全", -50, -1),
        ("凯旋国际金融中心大厦", "主塔楼及裙楼", "KX-2025-001", "竣工总结算", "S0", "中建一局", 489500000, "archived", "资料齐全", -240, -120),
        ("阳光海岸度假酒店装饰工程", "酒店大堂及客房区", "YGHA-2025-089", "分包审核", "S2", "艺筑装饰", 23800000, "archived", "资料齐全", -210, -80),
    ]
    stage_names = dict((code, title) for code, title, _ in STAGES)
    ts = now_iso()
    for index, item in enumerate(base):
        pid = new_id()
        stage = item[7]
        first_amount = item[6] * (0.95 if stage != "submitted" else 0)
        second_amount = first_amount * (0.98 if stage in ("second_audit", "conclusion", "archived") else 0)
        final_payable = second_amount if stage in ("conclusion", "archived") else 0
        conn.execute(
            """
            INSERT INTO audit_projects
            (id, project_code, project_name, audited_unit, audit_type, section_building, settlement_no, category, priority, contractor_name,
             contractor_phone, first_audit_company, first_auditor_name, second_audit_department,
             second_auditor_name, contract_amount, submitted_amount, first_audit_amount,
             second_audit_amount, audit_difference, final_payable, paid_amount, submit_date,
             audit_deadline, start_date, planned_end_date, actual_end_date, doc_status, current_stage,
             status, progress_percent, manager_name, is_delayed, delay_days, description,
             remark_dispute, remark_coordination, sort_order, is_archived, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '13800000000', '北京华夏工程造价咨询有限公司', '李明辉',
             ?, '王志强', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?)
            """,
            (
                pid,
                item[2],
                item[0],
                "建设单位审计部",
                "工程审计",
                item[1],
                item[2],
                item[3],
                item[4],
                item[5],
                "建设单位审计部",
                item[6] * 0.92,
                item[6],
                first_amount,
                second_amount,
                max(item[6] - (second_amount or first_amount or item[6]), 0),
                final_payable,
                item[6] * (0.7 if stage != "archived" else 1),
                day(item[9]),
                day(item[10]),
                day(item[9]),
                day(item[10]),
                day(item[10]) if stage == "archived" else "",
                item[8],
                stage,
                "completed" if stage == "archived" else ("delayed" if item[10] < 0 else "active"),
                100 if stage == "archived" else (75 if stage == "conclusion" else 45),
                item[5],
                1 if item[10] < 0 and stage != "archived" else 0,
                abs(item[10]) if item[10] < 0 and stage != "archived" else 0,
                f"{item[0]}审计进度跟踪",
                "已催办关键资料" if item[8] != "资料齐全" else "",
                index * 10,
                1 if stage == "archived" else 0,
                ts,
                ts,
            ),
        )
        conn.execute(
            """
            INSERT INTO audit_project_stages
            (id, project_id, stage_code, stage_name, entered_at, owner, status, progress_percent, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (new_id(), pid, stage, stage_names[stage], ts, item[5], 100 if stage == "archived" else 40, index * 10),
        )
        log_action(conn, pid, "seed", "系统初始化", "数据库初始化种子数据")


def project_where(params):
    where = ["status != 'deleted'"]
    values = []
    keyword = params.get("keyword", [""])[0].strip()
    if keyword:
        where.append("(project_name LIKE ? OR section_building LIKE ? OR settlement_no LIKE ?)")
        values.extend([f"%{keyword}%"] * 3)
    for key, column in [("stage", "current_stage"), ("status", "status"), ("priority", "priority"), ("category", "category"), ("doc_status", "doc_status")]:
        value = params.get(key, [""])[0].strip()
        if value:
            where.append(f"{column} = ?")
            values.append(value)
    manager = params.get("manager", params.get("owner", [""]))[0].strip()
    if manager:
        where.append("(contractor_name LIKE ? OR first_auditor_name LIKE ? OR second_auditor_name LIKE ?)")
        values.extend([f"%{manager}%"] * 3)
    start_date = params.get("startDate", [""])[0].strip()
    end_date = params.get("endDate", [""])[0].strip()
    if start_date:
        where.append("COALESCE(start_date, submit_date) >= ?")
        values.append(start_date)
    if end_date:
        where.append("COALESCE(planned_end_date, audit_deadline) <= ?")
        values.append(end_date)
    if params.get("only_overdue", [""])[0] in ("1", "true"):
        where.append("audit_deadline < ? AND current_stage != 'archived'")
        values.append(date.today().isoformat())
    return where, values


def query_projects(conn, params, paginate=False):
    where, values = project_where(params)
    sort = params.get("sort", ["stage"])[0]
    sort_map = {
        "stage": "current_stage, sort_order, updated_at DESC",
        "updatedAt": "updated_at DESC",
        "plannedEndDate": "planned_end_date ASC, audit_deadline ASC",
        "progress": "progress_percent DESC",
        "amount": "submitted_amount DESC",
    }
    order_by = sort_map.get(sort, sort_map["stage"])
    sql = f"SELECT * FROM audit_projects WHERE {' AND '.join(where)} ORDER BY {order_by}"
    total = conn.execute(f"SELECT COUNT(*) AS c FROM audit_projects WHERE {' AND '.join(where)}", values).fetchone()["c"]
    page = max(int(params.get("page", ["1"])[0] or 1), 1)
    page_size = max(min(int(params.get("pageSize", ["50"])[0] or 50), 200), 1)
    if paginate:
        sql += " LIMIT ? OFFSET ?"
        values = [*values, page_size, (page - 1) * page_size]
    rows = conn.execute(sql, values).fetchall()
    return rows, {"total": total, "page": page, "pageSize": page_size}


def get_field_configs(conn):
    rows = conn.execute(
        "SELECT * FROM audit_field_configs WHERE enabled = 1 ORDER BY sort_order, field_label"
    ).fetchall()
    return [camel_config(row) for row in rows]


def camel_config(row):
    return {
        "id": row["id"],
        "entityType": row["entity_type"],
        "fieldKey": row["field_key"],
        "fieldLabel": row["field_label"],
        "fieldName": row["field_name"] or row["field_label"],
        "fieldType": row["field_type"],
        "module": row["module"],
        "displayScene": row["display_scene"],
        "stageKey": row["stage_key"],
        "optionGroup": row["option_group"],
        "bindField": row["bind_field"],
        "required": bool(row["required"]),
        "visibleInCard": bool(row["visible_in_card"]),
        "visibleInTable": bool(row["visible_in_table"]),
        "visibleInDetail": bool(row["visible_in_detail"]),
        "visibleInForm": bool(row["visible_in_form"]),
        "visibleInGantt": bool(row["visible_in_gantt"]),
        "placeholder": row["placeholder"],
        "defaultValue": row["default_value"],
        "sortOrder": row["sort_order"],
        "enabled": bool(row["enabled"]),
    }


def camel_option(row):
    return {
        "id": row["id"],
        "groupKey": row["group_key"],
        "fieldKey": row["field_key"] or row["group_key"],
        "optionLabel": row["option_label"],
        "optionValue": row["option_value"],
        "color": row["color"],
        "sortOrder": row["sort_order"],
        "enabled": bool(row["enabled"]),
    }


def save_project_values(conn, project_id, custom_fields):
    if not isinstance(custom_fields, dict):
        return
    ts = now_iso()
    for key, value in custom_fields.items():
        conn.execute(
            """
            INSERT INTO audit_project_field_values (id, project_id, field_key, field_value, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_id, field_key) DO UPDATE SET field_value = excluded.field_value, updated_at = excluded.updated_at
            """,
            (new_id(), project_id, key, "" if value is None else str(value), ts),
        )


def project_columns_from_payload(data):
    amount = data.get("amount") or {}
    deadline = data.get("deadline") or {}
    contractor = data.get("contractor") or {}
    first = data.get("firstAudit") or {}
    second = data.get("secondAudit") or {}
    remark = data.get("remark") or {}
    first_auditor = first.get("auditor") or {}
    second_auditor = second.get("auditor") or {}
    stage = data.get("stage") or data.get("currentStage") or "submitted"
    start_date = data.get("startDate") or deadline.get("submitDate", "")
    planned_end_date = data.get("plannedEndDate") or deadline.get("auditDeadline", "")
    actual_end_date = data.get("actualEndDate", "")
    status = data.get("status") or ("completed" if stage == "archived" else "active")
    today = date.today().isoformat()
    is_delayed = bool(planned_end_date and planned_end_date < today and stage != "archived")
    return {
        "project_code": data.get("projectCode") or data.get("settlementNo", ""),
        "project_name": data.get("projectName", "").strip(),
        "audited_unit": data.get("auditedUnit") or second.get("department", ""),
        "audit_type": data.get("auditType") or data.get("category", ""),
        "section_building": data.get("sectionBuilding", ""),
        "settlement_no": data.get("settlementNo", ""),
        "category": data.get("category", ""),
        "priority": data.get("priority", "S2"),
        "contractor_name": contractor.get("name", data.get("contractorName", "")),
        "contractor_phone": contractor.get("phone", ""),
        "first_audit_company": first.get("companyName", ""),
        "first_auditor_name": first_auditor.get("name", ""),
        "second_audit_department": second.get("department", ""),
        "second_auditor_name": second_auditor.get("name", ""),
        "contract_amount": float(amount.get("contractAmount") or 0),
        "submitted_amount": float(amount.get("submittedAmount") or 0),
        "first_audit_amount": float(amount.get("firstAuditAmount") or 0),
        "second_audit_amount": float(amount.get("secondAuditAmount") or 0),
        "audit_difference": float(amount.get("auditDifference") or 0),
        "final_payable": float(amount.get("finalPayable") or 0),
        "paid_amount": float(amount.get("paidAmount") or 0),
        "submit_date": deadline.get("submitDate", ""),
        "audit_deadline": deadline.get("auditDeadline", ""),
        "start_date": start_date,
        "planned_end_date": planned_end_date,
        "actual_end_date": actual_end_date,
        "doc_status": data.get("docStatus", ""),
        "current_stage": stage,
        "status": status,
        "progress_percent": int(data.get("progressPercent") or (100 if stage == "archived" else 30)),
        "manager_name": data.get("managerName") or contractor.get("name", data.get("contractorName", "")),
        "is_delayed": 1 if is_delayed or data.get("isDelayed") else 0,
        "delay_days": max((date.fromisoformat(today) - date.fromisoformat(planned_end_date)).days, 0) if planned_end_date and planned_end_date < today else int(data.get("delayDays") or 0),
        "description": data.get("description", ""),
        "remark_dispute": remark.get("dispute", ""),
        "remark_coordination": remark.get("coordination", ""),
        "sort_order": int(data.get("sortOrder") or 0),
        "is_archived": 1 if stage == "archived" or data.get("isArchived") else 0,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AuditKanbanAPI/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def respond(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def respond_file(self, path, content_type, filename, inline=True):
        disposition = "inline" if inline else "attachment"
        encoded_name = quote(filename or path.name)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Disposition", f"{disposition}; filename*=UTF-8''{encoded_name}")
        self.send_header("Connection", "close")
        self.end_headers()
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 256)
                if not chunk:
                    break
                self.wfile.write(chunk)
        self.close_connection = True

    def not_found(self):
        self.respond(404, {"success": False, "error": "Not found"})

    def handle_error(self, exc):
        self.respond(500, {"success": False, "error": str(exc)})

    def client_ip(self):
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        return self.client_address[0] if self.client_address else ""

    def current_user(self, conn):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        payload = verify_token(auth.split(" ", 1)[1].strip())
        if not payload:
            return None
        row = conn.execute(
            "SELECT * FROM system_users WHERE id = ? AND is_active = 1",
            (payload.get("sub"),),
        ).fetchone()
        return row

    def require_user(self, conn):
        row = self.current_user(conn)
        if not row:
            self.respond(401, {"success": False, "error": "请先登录"})
            return None
        return row

    def require_role(self, conn, roles):
        row = self.require_user(conn)
        if not row:
            return None
        if row["role"] not in roles:
            self.respond(403, {"success": False, "error": "没有权限执行该操作"})
            return None
        return row

    def write_operation_log(self, conn, action, user=None, target_type="", target_id="", result="success", detail=None):
        conn.execute(
            """
            INSERT INTO system_operation_logs
            (id, user_id, username, role, action, target_type, target_id, result, ip_address, user_agent, detail_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id(),
                user["id"] if user else "",
                user["username"] if user else "",
                user["role"] if user else "",
                action,
                target_type,
                target_id,
                result,
                self.client_ip(),
                self.headers.get("User-Agent", ""),
                json.dumps(detail or {}, ensure_ascii=False),
                now_iso(),
            ),
        )

    def attachment_row(self, conn, attachment_id):
        return conn.execute(
            "SELECT * FROM audit_project_attachments WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
            (attachment_id,),
        ).fetchone()

    def list_project_attachments(self, conn, project_id):
        user = self.require_user(conn)
        if not user:
            return
        if not conn.execute("SELECT id FROM audit_projects WHERE id = ?", (project_id,)).fetchone():
            self.not_found()
            return
        rows = conn.execute(
            """
            SELECT * FROM audit_project_attachments
            WHERE project_id = ? AND COALESCE(is_deleted, 0) = 0
            ORDER BY COALESCE(NULLIF(created_at, ''), uploaded_at) DESC
            """,
            (project_id,),
        ).fetchall()
        self.respond(200, {"success": True, "data": [attachment_payload(r) for r in rows]})

    def attachment_library(self, conn, params):
        if not self.require_role(conn, {"admin"}):
            return
        keyword = (params.get("keyword", [""])[0] or "").strip()
        file_type = (params.get("fileType", params.get("file_type", [""]))[0] or "").strip()
        where = ["COALESCE(a.is_deleted, 0) = 0"]
        values = []
        if keyword:
            where.append("(p.project_name LIKE ? OR a.original_name LIKE ? OR a.file_name LIKE ?)")
            like = f"%{keyword}%"
            values.extend([like, like, like])
        if file_type:
            if file_type == "image":
                where.append("(a.mime_type LIKE 'image/%' OR a.file_type LIKE 'image/%')")
            elif file_type == "pdf":
                where.append("(a.file_ext = '.pdf' OR a.mime_type = 'application/pdf' OR a.file_type = 'application/pdf')")
            elif file_type == "text":
                where.append("(a.mime_type LIKE 'text/%' OR a.file_type LIKE 'text/%' OR a.file_ext IN ('.txt', '.csv', '.md', '.json', '.xml', '.log'))")
            elif file_type == "audio":
                where.append("(a.mime_type LIKE 'audio/%' OR a.file_type LIKE 'audio/%')")
            elif file_type == "video":
                where.append("(a.mime_type LIKE 'video/%' OR a.file_type LIKE 'video/%')")
            else:
                where.append(
                    "NOT ((a.mime_type LIKE 'image/%' OR a.file_type LIKE 'image/%') "
                    "OR (a.file_ext = '.pdf' OR a.mime_type = 'application/pdf' OR a.file_type = 'application/pdf') "
                    "OR (a.mime_type LIKE 'text/%' OR a.file_type LIKE 'text/%' OR a.file_ext IN ('.txt', '.csv', '.md', '.json', '.xml', '.log')) "
                    "OR (a.mime_type LIKE 'audio/%' OR a.file_type LIKE 'audio/%') "
                    "OR (a.mime_type LIKE 'video/%' OR a.file_type LIKE 'video/%'))"
                )
        rows = conn.execute(
            f"""
            SELECT
              a.*,
              p.project_name AS library_project_name,
              p.project_code AS library_project_code,
              p.manager_name AS library_manager_name
            FROM audit_project_attachments a
            LEFT JOIN audit_projects p ON p.id = a.project_id
            WHERE {" AND ".join(where)}
            ORDER BY p.project_name COLLATE NOCASE, COALESCE(NULLIF(a.created_at, ''), a.uploaded_at) DESC
            LIMIT 500
            """,
            values,
        ).fetchall()
        data = []
        for row in rows:
            item = attachment_payload(row)
            item["projectName"] = row_get(row, "library_project_name") or "未关联项目"
            item["projectCode"] = row_get(row, "library_project_code")
            item["managerName"] = row_get(row, "library_manager_name")
            data.append(item)
        self.respond(200, {"success": True, "data": data})

    def upload_project_attachment(self, conn, project_id):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        if not conn.execute("SELECT id FROM audit_projects WHERE id = ?", (project_id,)).fetchone():
            self.not_found()
            return
        try:
            original_name, content = parse_multipart_file(self)
        except ValueError as exc:
            self.respond(400, {"success": False, "error": str(exc)})
            return
        if is_path_like_filename(original_name):
            self.respond(400, {"success": False, "error": "不支持上传文件夹或路径型文件名"})
            return
        if is_forbidden_attachment_name(original_name):
            self.respond(400, {"success": False, "error": "不允许上传压缩包或镜像类文件"})
            return
        if not content:
            self.respond(400, {"success": False, "error": "文件内容为空"})
            return
        if len(content) > max_upload_size():
            self.respond(400, {"success": False, "error": "文件超过上传大小限制"})
            return
        file_ext = Path(original_name).suffix.lower()
        mime_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        stored_name = f"{uuid.uuid4().hex}{file_ext}"
        relative_path = f"audit-projects/{project_id}/{stored_name}"
        target = safe_attachment_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        attachment_id = new_id()
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO audit_project_attachments
            (id, project_id, file_name, file_url, file_type, uploaded_by, uploaded_at,
             original_name, stored_name, file_ext, mime_type, file_size, relative_path,
             uploaded_by_name, created_at, deleted_at, is_deleted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 0)
            """,
            (
                attachment_id,
                project_id,
                original_name,
                relative_path,
                mime_type,
                user["username"],
                ts,
                original_name,
                stored_name,
                file_ext,
                mime_type,
                len(content),
                relative_path,
                user["display_name"] or user["username"],
                ts,
            ),
        )
        self.write_operation_log(conn, "attachment.upload", user, "audit_project_attachment", attachment_id, "success", {"projectId": project_id, "fileName": original_name})
        conn.commit()
        row = self.attachment_row(conn, attachment_id)
        self.respond(201, {"success": True, "data": attachment_payload(row)})

    def preview_attachment(self, conn, attachment_id):
        if not self.require_user(conn):
            return
        row = self.attachment_row(conn, attachment_id)
        if not row:
            self.not_found()
            return
        original_name = row_get(row, "original_name") or row_get(row, "file_name")
        mime_type = row_get(row, "mime_type") or row_get(row, "file_type") or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        file_ext = row_get(row, "file_ext") or Path(original_name).suffix.lower()
        if not (mime_type in INLINE_PREVIEW_TYPES or mime_type.startswith(INLINE_PREVIEW_PREFIXES) or file_ext in TEXT_PREVIEW_SUFFIXES):
            self.respond(415, {"success": False, "error": "该文件类型暂不支持在线预览，请下载查看"})
            return
        path = safe_attachment_path(row_get(row, "relative_path") or row_get(row, "file_url"))
        if not path.exists():
            self.not_found()
            return
        if file_ext in TEXT_PREVIEW_SUFFIXES and not mime_type.startswith("text/"):
            mime_type = "text/plain; charset=utf-8"
        self.respond_file(path, mime_type, original_name, inline=True)

    def download_attachment(self, conn, attachment_id):
        if not self.require_user(conn):
            return
        row = self.attachment_row(conn, attachment_id)
        if not row:
            self.not_found()
            return
        original_name = row_get(row, "original_name") or row_get(row, "file_name")
        path = safe_attachment_path(row_get(row, "relative_path") or row_get(row, "file_url"))
        if not path.exists():
            self.not_found()
            return
        mime_type = row_get(row, "mime_type") or row_get(row, "file_type") or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        self.respond_file(path, mime_type, original_name, inline=False)

    def delete_attachment(self, conn, attachment_id):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        row = self.attachment_row(conn, attachment_id)
        if not row:
            self.not_found()
            return
        path = safe_attachment_path(row_get(row, "relative_path") or row_get(row, "file_url"))
        if path.exists():
            path.unlink()
        conn.execute("UPDATE audit_project_attachments SET is_deleted = 1, deleted_at = ? WHERE id = ?", (now_iso(), attachment_id))
        self.write_operation_log(conn, "attachment.delete", user, "audit_project_attachment", attachment_id, "success", {"projectId": row["project_id"], "fileName": row_get(row, "original_name") or row_get(row, "file_name")})
        conn.commit()
        self.respond(200, {"success": True, "data": None})

    def login(self, conn, data):
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        row = conn.execute("SELECT * FROM system_users WHERE username = ?", (username,)).fetchone()
        if not row or not row["is_active"] or not verify_password(password, row["password_hash"]):
            self.write_operation_log(conn, "auth.login_failed", None, "system_user", username, "failed", {"username": username})
            conn.commit()
            self.respond(401, {"success": False, "error": "账号或密码错误"})
            return
        expires_at = int(time.time()) + 60 * 60 * 8
        token = sign_token({"sub": row["id"], "role": row["role"], "username": row["username"], "exp": expires_at})
        conn.execute("UPDATE system_users SET last_login_at = ?, updated_at = ? WHERE id = ?", (now_iso(), now_iso(), row["id"]))
        self.write_operation_log(conn, "auth.login_success", row, "system_user", row["id"])
        conn.commit()
        fresh = conn.execute("SELECT * FROM system_users WHERE id = ?", (row["id"],)).fetchone()
        self.respond(200, {"success": True, "data": {"token": token, "expiresAt": expires_at, "user": user_payload(fresh)}})

    def list_users(self, conn):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        rows = conn.execute("SELECT * FROM system_users ORDER BY created_at DESC").fetchall()
        self.respond(200, {"success": True, "data": [user_payload(r) for r in rows]})

    def create_user(self, conn, data):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        role = data.get("role") or "viewer"
        if not username or not password:
            self.respond(400, {"success": False, "error": "账号和密码不能为空"})
            return
        if role not in {"admin", "editor", "viewer"}:
            self.respond(400, {"success": False, "error": "角色无效"})
            return
        ts = now_iso()
        try:
            conn.execute(
                """
                INSERT INTO system_users
                (id, username, display_name, email, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (new_id(), username, data.get("displayName") or username, data.get("email", ""), hash_password(password), role, ts, ts),
            )
        except sqlite3.IntegrityError:
            self.respond(409, {"success": False, "error": "账号已存在"})
            return
        self.write_operation_log(conn, "user.create", user, "system_user", username)
        conn.commit()
        self.list_users(conn)

    def update_user(self, conn, uid, data):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        row = conn.execute("SELECT * FROM system_users WHERE id = ?", (uid,)).fetchone()
        if not row:
            self.not_found()
            return
        fields = {
            "display_name": data.get("displayName", row["display_name"]),
            "email": data.get("email", row["email"]),
            "role": data.get("role", row["role"]),
            "is_active": 1 if data.get("isActive", bool(row["is_active"])) else 0,
            "updated_at": now_iso(),
        }
        if fields["role"] not in {"admin", "editor", "viewer"}:
            self.respond(400, {"success": False, "error": "角色无效"})
            return
        if data.get("password"):
            fields["password_hash"] = hash_password(data["password"])
        assignments = ", ".join([f"{key} = ?" for key in fields.keys()])
        conn.execute(f"UPDATE system_users SET {assignments} WHERE id = ?", (*fields.values(), uid))
        self.write_operation_log(conn, "user.update", user, "system_user", uid)
        conn.commit()
        fresh = conn.execute("SELECT * FROM system_users WHERE id = ?", (uid,)).fetchone()
        self.respond(200, {"success": True, "data": user_payload(fresh)})

    def admin_stats(self, conn):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        users = conn.execute("SELECT role, is_active FROM system_users").fetchall()
        projects = conn.execute("SELECT COUNT(*) AS c FROM audit_projects WHERE status != 'deleted'").fetchone()["c"]
        self.respond(200, {"success": True, "data": {
            "totalUsers": len(users),
            "activeUsers": sum(1 for u in users if u["is_active"]),
            "adminCount": sum(1 for u in users if u["role"] == "admin"),
            "totalProjects": projects,
            "recentLogins": conn.execute("SELECT COUNT(*) AS c FROM system_operation_logs WHERE action = 'auth.login_success'").fetchone()["c"],
        }})

    def system_settings(self, conn):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        rows = conn.execute("SELECT * FROM system_settings ORDER BY setting_key").fetchall()
        self.respond(200, {"success": True, "data": [
            {"key": r["setting_key"], "value": json.loads(r["setting_value"]), "updatedAt": r["updated_at"], "updatedBy": r["updated_by"]}
            for r in rows
        ]})

    def set_system_setting(self, conn, key, data):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO system_settings
            (setting_key, setting_value, setting_group, description, updated_by, created_at, updated_at)
            VALUES (?, ?, 'system', '', ?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
              setting_value = excluded.setting_value, updated_by = excluded.updated_by, updated_at = excluded.updated_at
            """,
            (key, json.dumps(data.get("value"), ensure_ascii=False), user["username"], ts, ts),
        )
        self.write_operation_log(conn, "system.setting_update", user, "system_setting", key)
        conn.commit()
        self.respond(200, {"success": True, "data": None})

    def theme_options(self, conn):
        rows = conn.execute("SELECT * FROM system_theme_configs ORDER BY sort_order, theme_name").fetchall()
        self.respond(200, {"success": True, "data": [self.theme_payload(r) for r in rows]})

    def theme_current(self, conn):
        setting = conn.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'current_theme'").fetchone()
        value = json.loads(setting["setting_value"]) if setting else {"themeKey": "arco-theme-0000"}
        value["brandColor"] = normalize_hex_color(value.get("brandColor")) or "#4787F0"
        if not value.get("themePackage"):
            value["themePackage"] = ""
        if value.get("sidebarLogoVariant") not in {"color", "white", "black"}:
            value["sidebarLogoVariant"] = "color"
        row = conn.execute("SELECT * FROM system_theme_configs WHERE theme_key = ?", (value.get("themeKey", "arco-theme-0000"),)).fetchone()
        self.respond(200, {"success": True, "data": {**value, "theme": self.theme_payload(row) if row else None}})

    def update_theme_current(self, conn, data):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        theme_key = data.get("themeKey") or "arco-theme-0000"
        row = conn.execute("SELECT * FROM system_theme_configs WHERE theme_key = ? AND is_enabled = 1", (theme_key,)).fetchone()
        if not row:
            self.respond(400, {"success": False, "error": "主题不在启用白名单中"})
            return
        brand_color = str(data.get("brandColor") or "").strip()
        if brand_color and not re.match(r"^#?[0-9a-fA-F]{6}$", brand_color):
            self.respond(400, {"success": False, "error": "品牌色号格式不正确，请输入 6 位 HEX 色号"})
            return
        brand_color = normalize_hex_color(brand_color) or "#4787F0"
        theme_package = str(data.get("themePackage") or "").strip()
        if theme_package and not re.match(r"^@(arco-design/theme|arco-themes/vue)-[a-z0-9-]+$", theme_package, re.IGNORECASE):
            self.respond(400, {"success": False, "error": "样式名称格式不正确，请从主题商店复制完整名称后再试。"})
            return
        sidebar_logo_variant = str(data.get("sidebarLogoVariant") or "color").strip()
        if sidebar_logo_variant not in {"color", "white", "black"}:
            self.respond(400, {"success": False, "error": "侧边栏 LOGO 色彩选择不正确，请重新选择后保存。"})
            return
        value = {
            "themeKey": theme_key,
            "darkMode": bool(data.get("darkMode")),
            "compactMode": bool(data.get("compactMode")),
            "applyScope": data.get("applyScope") or "global",
            "brandColor": brand_color,
            "themePackage": theme_package,
            "sidebarLogoVariant": sidebar_logo_variant,
        }
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO system_settings
            (setting_key, setting_value, setting_group, description, updated_by, created_at, updated_at)
            VALUES ('current_theme', ?, 'theme', '当前主题', ?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
              setting_value = excluded.setting_value, updated_by = excluded.updated_by, updated_at = excluded.updated_at
            """,
            (json.dumps(value, ensure_ascii=False), user["username"], ts, ts),
        )
        self.write_operation_log(conn, "theme.update", user, "system_theme", theme_key)
        conn.commit()
        self.theme_current(conn)

    def reset_theme(self, conn):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        self.update_theme_current(conn, {"themeKey": "arco-theme-0000", "darkMode": False, "compactMode": False, "applyScope": "global", "brandColor": "#4787F0", "themePackage": "", "sidebarLogoVariant": "color"})

    def theme_payload(self, row):
        if not row:
            return None
        return {
            "id": row["id"],
            "themeKey": row["theme_key"],
            "themeName": row["theme_name"],
            "packageName": row["package_name"],
            "previewColors": json.loads(row["preview_colors"] or "[]"),
            "applyScope": row["apply_scope"],
            "isEnabled": bool(row["is_enabled"]),
            "isDefault": bool(row["is_default"]),
            "darkModeEnabled": bool(row["dark_mode_enabled"]),
            "compactModeEnabled": bool(row["compact_mode_enabled"]),
        }

    def operation_logs(self, conn):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        rows = conn.execute("SELECT * FROM system_operation_logs ORDER BY created_at DESC LIMIT 200").fetchall()
        self.respond(200, {"success": True, "data": [row_dict(r) for r in rows]})

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)
            with connect() as conn:
                if path == "/api/health":
                    self.respond(200, {"success": True, "data": {"status": "ok", "time": now_iso()}})
                elif path == "/api/auth/me":
                    user = self.require_user(conn)
                    if user:
                        self.respond(200, {"success": True, "data": user_payload(user)})
                elif path == "/api/admin/users":
                    self.list_users(conn)
                elif path == "/api/admin/stats":
                    self.admin_stats(conn)
                elif path == "/api/admin/operation-logs":
                    self.operation_logs(conn)
                elif path == "/api/system/settings":
                    self.system_settings(conn)
                elif path == "/api/system/theme/current":
                    self.theme_current(conn)
                elif path == "/api/system/theme/options":
                    self.theme_options(conn)
                elif path.startswith("/api/system/theme/preview"):
                    theme_key = params.get("themeKey", ["arco-theme-0000"])[0]
                    row = conn.execute("SELECT * FROM system_theme_configs WHERE theme_key = ?", (theme_key,)).fetchone()
                    if row:
                        self.respond(200, {"success": True, "data": self.theme_payload(row)})
                    else:
                        self.not_found()
                elif path == "/api/audit/stages":
                    self.respond(200, {"success": True, "data": [{"code": c, "title": t, "color": color} for c, t, color in STAGES]})
                elif path == "/api/audit/projects":
                    rows, meta = query_projects(conn, params, paginate=True)
                    self.respond(200, {"success": True, "data": [project_payload(conn, r) for r in rows], "meta": meta})
                elif path == "/api/audit/projects/gantt":
                    rows, _meta = query_projects(conn, params)
                    self.respond(200, {"success": True, "data": [project_payload(conn, r) for r in rows]})
                elif path == "/api/audit/dashboard/summary":
                    self.respond(200, {"success": True, "data": dashboard_summary(conn)})
                elif path == "/api/audit/dashboard/overview":
                    self.respond(200, {"success": True, "data": dashboard_overview(conn)})
                elif path == "/api/audit/admin/attachments":
                    self.attachment_library(conn, params)
                elif re.match(r"^/api/audit/projects/([^/]+)/attachments$", path):
                    self.list_project_attachments(conn, re.match(r"^/api/audit/projects/([^/]+)/attachments$", path).group(1))
                elif re.match(r"^/api/audit/attachments/([^/]+)/preview$", path):
                    self.preview_attachment(conn, re.match(r"^/api/audit/attachments/([^/]+)/preview$", path).group(1))
                elif re.match(r"^/api/audit/attachments/([^/]+)/download$", path):
                    self.download_attachment(conn, re.match(r"^/api/audit/attachments/([^/]+)/download$", path).group(1))
                elif path == "/api/audit/admin/field-configs":
                    if not self.require_role(conn, {"admin"}):
                        return
                    self.respond(200, {"success": True, "data": [camel_config(r) for r in conn.execute("SELECT * FROM audit_field_configs ORDER BY sort_order, field_label")]})
                elif path == "/api/audit/admin/field-options":
                    if not self.require_role(conn, {"admin"}):
                        return
                    group = params.get("group_key", params.get("fieldKey", [""]))[0]
                    if group:
                        rows = conn.execute("SELECT * FROM audit_field_options WHERE group_key = ? ORDER BY sort_order, option_label", (group,)).fetchall()
                    else:
                        rows = conn.execute("SELECT * FROM audit_field_options ORDER BY group_key, sort_order, option_label").fetchall()
                    self.respond(200, {"success": True, "data": [camel_option(r) for r in rows]})
                elif path == "/api/audit/admin/meta":
                    rows = conn.execute("SELECT * FROM audit_field_options WHERE enabled = 1 ORDER BY group_key, sort_order, option_label").fetchall()
                    options = {}
                    for row in rows:
                        options.setdefault(row["group_key"], []).append(camel_option(row))
                    self.respond(200, {"success": True, "data": {"stages": [{"code": c, "title": t, "color": color} for c, t, color in STAGES], "fieldConfigs": get_field_configs(conn), "options": options}})
                else:
                    match = re.match(r"^/api/audit/projects/([^/]+)$", path)
                    if match:
                        row = conn.execute("SELECT * FROM audit_projects WHERE id = ?", (match.group(1),)).fetchone()
                        if not row:
                            self.not_found()
                            return
                        logs = [row_dict(r) for r in conn.execute("SELECT * FROM audit_project_logs WHERE project_id = ? ORDER BY created_at DESC LIMIT 30", (match.group(1),))]
                        stages = [row_dict(r) for r in conn.execute("SELECT * FROM audit_project_stages WHERE project_id = ? ORDER BY stage_order, sort_order, entered_at", (match.group(1),))]
                        attachments = []
                        if self.current_user(conn):
                            attachments = [
                                attachment_payload(r)
                                for r in conn.execute(
                                    """
                                    SELECT * FROM audit_project_attachments
                                    WHERE project_id = ? AND COALESCE(is_deleted, 0) = 0
                                    ORDER BY COALESCE(NULLIF(created_at, ''), uploaded_at) DESC
                                    """,
                                    (match.group(1),),
                                )
                            ]
                        payload = project_payload(conn, row)
                        payload["logs"] = logs
                        payload["stages"] = stages
                        payload["attachments"] = attachments
                        self.respond(200, {"success": True, "data": payload})
                    else:
                        self.not_found()
        except Exception as exc:
            self.handle_error(exc)

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            with connect() as conn:
                attachment_match = re.match(r"^/api/audit/projects/([^/]+)/attachments$", path)
                if attachment_match:
                    self.upload_project_attachment(conn, attachment_match.group(1))
                    return
                data = read_json(self)
                if path == "/api/auth/login":
                    self.login(conn, data)
                elif path == "/api/auth/logout":
                    user = self.current_user(conn)
                    if user:
                        self.write_operation_log(conn, "auth.logout", user, "system_user", user["id"])
                        conn.commit()
                    self.respond(200, {"success": True, "data": None})
                elif path == "/api/admin/users":
                    self.create_user(conn, data)
                elif path == "/api/system/theme/reset":
                    self.reset_theme(conn)
                elif path == "/api/audit/projects":
                    if not self.require_role(conn, {"admin", "editor"}):
                        return
                    self.create_project(conn, data)
                elif re.match(r"^/api/audit/projects/([^/]+)/progress$", path):
                    if not self.require_role(conn, {"admin", "editor"}):
                        return
                    self.update_progress(conn, re.match(r"^/api/audit/projects/([^/]+)/progress$", path).group(1), data)
                elif path == "/api/audit/admin/field-configs":
                    if not self.require_role(conn, {"admin"}):
                        return
                    self.upsert_field_config(conn, data)
                elif path == "/api/audit/admin/field-options":
                    if not self.require_role(conn, {"admin"}):
                        return
                    self.upsert_field_option(conn, data)
                else:
                    self.not_found()
        except Exception as exc:
            self.handle_error(exc)

    def do_PUT(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            data = read_json(self)
            with connect() as conn:
                match = re.match(r"^/api/audit/projects/([^/]+)$", path)
                if match:
                    if not self.require_role(conn, {"admin", "editor"}):
                        return
                    self.update_project(conn, match.group(1), data)
                elif path.startswith("/api/admin/users/"):
                    self.update_user(conn, path.rsplit("/", 1)[-1], data)
                elif path == "/api/system/theme/current":
                    self.update_theme_current(conn, data)
                elif path.startswith("/api/system/settings/"):
                    self.set_system_setting(conn, path.rsplit("/", 1)[-1], data)
                elif path.startswith("/api/audit/admin/field-configs/"):
                    if not self.require_role(conn, {"admin"}):
                        return
                    data["id"] = path.rsplit("/", 1)[-1]
                    self.upsert_field_config(conn, data)
                elif path.startswith("/api/audit/admin/field-options/"):
                    if not self.require_role(conn, {"admin"}):
                        return
                    data["id"] = path.rsplit("/", 1)[-1]
                    self.upsert_field_option(conn, data)
                else:
                    self.not_found()
        except Exception as exc:
            self.handle_error(exc)

    def do_DELETE(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            with connect() as conn:
                if path.startswith("/api/audit/admin/field-configs/"):
                    if not self.require_role(conn, {"admin"}):
                        return
                    conn.execute("UPDATE audit_field_configs SET enabled = 0, updated_at = ? WHERE id = ?", (now_iso(), path.rsplit("/", 1)[-1]))
                    self.write_operation_log(conn, "field_config.delete", self.current_user(conn), "audit_field_config", path.rsplit("/", 1)[-1])
                    conn.commit()
                    self.respond(200, {"success": True, "data": None})
                elif path.startswith("/api/audit/admin/field-options/"):
                    if not self.require_role(conn, {"admin"}):
                        return
                    conn.execute("UPDATE audit_field_options SET enabled = 0, updated_at = ? WHERE id = ?", (now_iso(), path.rsplit("/", 1)[-1]))
                    self.write_operation_log(conn, "field_option.delete", self.current_user(conn), "audit_field_option", path.rsplit("/", 1)[-1])
                    conn.commit()
                    self.respond(200, {"success": True, "data": None})
                elif re.match(r"^/api/audit/attachments/([^/]+)$", path):
                    self.delete_attachment(conn, re.match(r"^/api/audit/attachments/([^/]+)$", path).group(1))
                else:
                    self.not_found()
        except Exception as exc:
            self.handle_error(exc)

    def create_project(self, conn, data):
        user = self.current_user(conn)
        columns = project_columns_from_payload(data)
        if not columns["project_name"]:
            self.respond(400, {"success": False, "error": "项目名称不能为空"})
            return
        pid = new_id()
        ts = now_iso()
        names = ", ".join(["id", *columns.keys(), "created_at", "updated_at"])
        marks = ", ".join(["?"] * (len(columns) + 3))
        conn.execute(f"INSERT INTO audit_projects ({names}) VALUES ({marks})", (pid, *columns.values(), ts, ts))
        save_project_values(conn, pid, data.get("customFields"))
        stage_name = dict((c, t) for c, t, _ in STAGES).get(columns["current_stage"], columns["current_stage"])
        conn.execute(
            "INSERT INTO audit_project_stages (id, project_id, stage_code, stage_name, entered_at, owner, progress_percent, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (new_id(), pid, columns["current_stage"], stage_name, ts, columns["contractor_name"], 10, columns["sort_order"]),
        )
        operator = user["username"] if user else data.get("operator", "前端用户")
        log_action(conn, pid, "create", operator, "新增项目", after=columns)
        self.write_operation_log(conn, "project.create", user, "audit_project", pid)
        conn.commit()
        row = conn.execute("SELECT * FROM audit_projects WHERE id = ?", (pid,)).fetchone()
        self.respond(201, {"success": True, "data": project_payload(conn, row)})

    def update_project(self, conn, pid, data):
        user = self.current_user(conn)
        row = conn.execute("SELECT * FROM audit_projects WHERE id = ?", (pid,)).fetchone()
        if not row:
            self.not_found()
            return
        before = project_payload(conn, row)
        columns = project_columns_from_payload(data)
        columns["updated_at"] = now_iso()
        assignments = ", ".join([f"{key} = ?" for key in columns.keys()])
        conn.execute(f"UPDATE audit_projects SET {assignments} WHERE id = ?", (*columns.values(), pid))
        save_project_values(conn, pid, data.get("customFields"))
        operator = user["username"] if user else data.get("operator", "前端用户")
        log_action(conn, pid, "update", operator, "更新项目", before=before, after=columns)
        self.write_operation_log(conn, "project.update", user, "audit_project", pid)
        conn.commit()
        row = conn.execute("SELECT * FROM audit_projects WHERE id = ?", (pid,)).fetchone()
        self.respond(200, {"success": True, "data": project_payload(conn, row)})

    def update_progress(self, conn, pid, data):
        user = self.current_user(conn)
        row = conn.execute("SELECT * FROM audit_projects WHERE id = ?", (pid,)).fetchone()
        if not row:
            self.not_found()
            return
        stage = data.get("stage") or data.get("stageCode")
        if not stage:
            self.respond(400, {"success": False, "error": "stageCode 不能为空"})
            return
        ts = now_iso()
        stage_name = dict((c, t) for c, t, _ in STAGES).get(stage, stage)
        conn.execute("UPDATE audit_project_stages SET finished_at = ?, status = 'done' WHERE project_id = ? AND status = 'active'", (ts, pid))
        conn.execute("UPDATE audit_projects SET current_stage = ?, is_archived = ?, updated_at = ? WHERE id = ?", (stage, 1 if stage == "archived" else 0, ts, pid))
        conn.execute(
            "INSERT INTO audit_project_stages (id, project_id, stage_code, stage_name, entered_at, owner, status, progress_percent, sort_order) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)",
            (new_id(), pid, stage, stage_name, ts, data.get("operator", ""), int(data.get("progressPercent") or 30), int(data.get("sortOrder") or 0)),
        )
        operator = user["username"] if user else data.get("operator", "前端用户")
        log_action(conn, pid, "progress", operator, data.get("note", f"流转至{stage_name}"), before={"stage": row["current_stage"]}, after={"stage": stage})
        self.write_operation_log(conn, "project.progress", user, "audit_project", pid, detail={"stage": stage})
        conn.commit()
        row = conn.execute("SELECT * FROM audit_projects WHERE id = ?", (pid,)).fetchone()
        self.respond(200, {"success": True, "data": project_payload(conn, row)})

    def upsert_field_config(self, conn, data):
        user = self.current_user(conn)
        fid = data.get("id") or new_id()
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO audit_field_configs
            (id, entity_type, field_key, field_label, field_type, option_group, bind_field, required,
             visible_in_card, visible_in_table, visible_in_detail, visible_in_form, visible_in_gantt,
             sort_order, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
             entity_type = excluded.entity_type, field_key = excluded.field_key, field_label = excluded.field_label,
             field_type = excluded.field_type, option_group = excluded.option_group, bind_field = excluded.bind_field,
             required = excluded.required, visible_in_card = excluded.visible_in_card, visible_in_table = excluded.visible_in_table,
             visible_in_detail = excluded.visible_in_detail, visible_in_form = excluded.visible_in_form,
             visible_in_gantt = excluded.visible_in_gantt, sort_order = excluded.sort_order,
             enabled = excluded.enabled, updated_at = excluded.updated_at
            """,
            (
                fid,
                data.get("entityType", "project"),
                data.get("fieldKey", ""),
                data.get("fieldLabel", ""),
                data.get("fieldType", "text"),
                data.get("optionGroup", ""),
                data.get("bindField", ""),
                int(bool(data.get("required"))),
                int(data.get("visibleInCard", True)),
                int(data.get("visibleInTable", True)),
                int(data.get("visibleInDetail", True)),
                int(data.get("visibleInForm", True)),
                int(bool(data.get("visibleInGantt"))),
                int(data.get("sortOrder") or 0),
                int(data.get("enabled", True)),
                data.get("createdAt", ts),
                ts,
            ),
        )
        conn.execute(
            """
            UPDATE audit_field_configs
            SET field_name = ?, module = ?, display_scene = ?, stage_key = ?,
                is_required = ?, placeholder = ?, default_value = ?, is_enabled = ?
            WHERE id = ?
            """,
            (
                data.get("fieldName") or data.get("fieldLabel", ""),
                data.get("module", "project"),
                data.get("displayScene", ""),
                data.get("stageKey", ""),
                int(bool(data.get("required"))),
                data.get("placeholder", ""),
                data.get("defaultValue", ""),
                int(data.get("enabled", True)),
                fid,
            ),
        )
        self.write_operation_log(conn, "field_config.upsert", user, "audit_field_config", fid)
        conn.commit()
        row = conn.execute("SELECT * FROM audit_field_configs WHERE id = ?", (fid,)).fetchone()
        self.respond(200, {"success": True, "data": camel_config(row)})

    def upsert_field_option(self, conn, data):
        user = self.current_user(conn)
        oid = data.get("id") or new_id()
        ts = now_iso()
        label = data.get("optionLabel") or data.get("optionValue") or ""
        value = data.get("optionValue") or label
        conn.execute(
            """
            INSERT INTO audit_field_options
            (id, group_key, option_label, option_value, color, sort_order, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET group_key = excluded.group_key, option_label = excluded.option_label,
             option_value = excluded.option_value, color = excluded.color, sort_order = excluded.sort_order,
             enabled = excluded.enabled, updated_at = excluded.updated_at
            """,
            (oid, data.get("groupKey", ""), label, value, data.get("color", ""), int(data.get("sortOrder") or 0), int(data.get("enabled", True)), data.get("createdAt", ts), ts),
        )
        conn.execute(
            "UPDATE audit_field_options SET field_key = ?, is_enabled = ?, is_system = ? WHERE id = ?",
            (data.get("fieldKey") or data.get("groupKey", ""), int(data.get("enabled", True)), int(bool(data.get("isSystem"))), oid),
        )
        self.write_operation_log(conn, "field_option.upsert", user, "audit_field_option", oid)
        conn.commit()
        row = conn.execute("SELECT * FROM audit_field_options WHERE id = ?", (oid,)).fetchone()
        self.respond(200, {"success": True, "data": camel_option(row)})


def dashboard_summary(conn):
    rows = conn.execute("SELECT * FROM audit_projects WHERE status != 'deleted'").fetchall()
    stage_counts = {code: 0 for code, _, _ in STAGES}
    for row in rows:
        stage_counts[row["current_stage"]] = stage_counts.get(row["current_stage"], 0) + 1
    today = date.today().isoformat()
    month_prefix = date.today().strftime("%Y-%m")
    upcoming_end = (date.today() + timedelta(days=7)).isoformat()
    return {
        "totalProjects": len(rows),
        "inAuditProjects": sum(1 for r in rows if r["current_stage"] in ("first_audit", "second_audit")),
        "completedProjects": sum(1 for r in rows if r["current_stage"] == "archived"),
        "overdueProjects": sum(1 for r in rows if r["audit_deadline"] and r["audit_deadline"] < today and r["current_stage"] != "archived"),
        "monthlyNewProjects": sum(1 for r in rows if (r["created_at"] or "").startswith(month_prefix)),
        "upcomingDueProjects": sum(1 for r in rows if r["planned_end_date"] and today <= r["planned_end_date"] <= upcoming_end and r["current_stage"] != "archived"),
        "totalSubmittedAmount": sum(float(r["submitted_amount"] or 0) for r in rows),
        "totalFirstCutAmount": sum(max(float(r["submitted_amount"] or 0) - float(r["first_audit_amount"] or 0), 0) for r in rows if r["first_audit_amount"]),
        "totalSecondCutAmount": sum(max(float(r["first_audit_amount"] or 0) - float(r["second_audit_amount"] or 0), 0) for r in rows if r["second_audit_amount"]),
        "stageCounts": stage_counts,
    }


def dashboard_sparkline(seed, points=8):
    base = max(int(seed or 1), 1)
    values = []
    for index in range(points):
        value = 34 + ((base * 13 + index * 17) % 42) + (index % 3) * 6
        values.append(max(18, min(value, 92)))
    return values


def month_key(value):
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return f"{parsed.year}-{parsed.month:02d}"
    except ValueError:
        return str(value)[:7] if len(str(value)) >= 7 else ""


def dashboard_overview(conn):
    rows = conn.execute("SELECT * FROM audit_projects WHERE status != 'deleted'").fetchall()
    summary = dashboard_summary(conn)
    stage_title = {code: title for code, title, _ in STAGES}
    today = date.today().isoformat()
    upcoming_end = (date.today() + timedelta(days=7)).isoformat()

    def is_overdue(row):
        deadline = row["planned_end_date"] or row["audit_deadline"]
        return bool(deadline and deadline < today and row["current_stage"] != "archived")

    def is_upcoming(row):
        deadline = row["planned_end_date"] or row["audit_deadline"]
        return bool(deadline and today <= deadline <= upcoming_end and row["current_stage"] != "archived")

    paused_count = sum(1 for row in rows if (row["status"] or "").lower() == "paused" or "暂停" in (row["status"] or ""))
    delayed_count = summary["overdueProjects"]
    completed_count = summary["completedProjects"]
    running_count = summary["inAuditProjects"]
    not_started_count = max(len(rows) - paused_count - delayed_count - completed_count - running_count, 0)

    now = date.today().replace(day=1)
    months = []
    year = now.year
    month = now.month
    for offset in range(5, -1, -1):
        m = month - offset
        y = year
        while m <= 0:
            y -= 1
            m += 12
        months.append(f"{y}-{m:02d}")

    trend_data = []
    for month in months:
        created = sum(1 for row in rows if month_key(row["created_at"]) == month)
        completed = sum(
            1
            for row in rows
            if row["current_stage"] == "archived" and month_key(row["actual_end_date"] or row["updated_at"]) == month
        )
        trend_data.append({"month": month, "type": "新增", "count": created})
        trend_data.append({"month": month, "type": "完成", "count": completed})

    risk_rows = sorted(
        [row for row in rows if is_overdue(row) or is_upcoming(row)],
        key=lambda row: (0 if is_overdue(row) else 1, -(row["delay_days"] or 0), row["planned_end_date"] or row["audit_deadline"] or ""),
    )[:5]

    amount_rows = sorted(rows, key=lambda row: float(row["submitted_amount"] or 0), reverse=True)[:8]

    return {
        "summary": summary,
        "statusDistribution": [
            {"type": "未开始", "value": not_started_count},
            {"type": "进行中", "value": running_count},
            {"type": "延期", "value": delayed_count},
            {"type": "已完成", "value": completed_count},
            {"type": "暂停", "value": paused_count},
        ],
        "stageDistribution": [
            {"stage": stage_title.get(code, code), "stageCode": code, "count": summary["stageCounts"].get(code, 0)}
            for code, _, _ in STAGES
        ],
        "trendData": trend_data,
        "cardSparklines": {
            "totalProjects": dashboard_sparkline(summary["totalProjects"]),
            "inAuditProjects": dashboard_sparkline(summary["inAuditProjects"] + 8),
            "completedProjects": dashboard_sparkline(summary["completedProjects"] + 16),
            "overdueProjects": dashboard_sparkline(summary["overdueProjects"] + 24),
            "monthlyNewProjects": dashboard_sparkline(summary["monthlyNewProjects"] + 32),
            "upcomingDueProjects": dashboard_sparkline(summary["upcomingDueProjects"] + 40),
        },
        "riskQueue": [
            {
                "id": row["id"],
                "projectName": row["project_name"],
                "managerName": row["manager_name"] or row["contractor_name"],
                "auditDeadline": row["planned_end_date"] or row["audit_deadline"],
                "isDelayed": is_overdue(row),
                "delayDays": row["delay_days"] or 0,
            }
            for row in risk_rows
        ],
        "amountTop": [
            {
                "id": row["id"],
                "name": row["project_name"][:12] + "..." if len(row["project_name"]) > 12 else row["project_name"],
                "amount": float(row["submitted_amount"] or 0) / 10000,
            }
            for row in amount_rows
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("AUDIT_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AUDIT_API_PORT", "3008")))
    args = parser.parse_args()
    bootstrap()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Audit Kanban API listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
