#!/usr/bin/env python3
import argparse
from contextlib import contextmanager
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

SERVER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SERVER_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.lifecycle import (
    audit_start_failures,
    contract_gate_failures,
    next_stage as lifecycle_next_stage,
    stage_label as lifecycle_stage_label,
    validate_adjacent_transition,
)
from server.lifecycle_repository import (
    LifecycleBlockedError,
    LifecycleConflictError,
    LifecycleIdempotencyConflictError,
    LifecycleNotFoundError,
    lifecycle_snapshot,
    transition_project,
)
from server.document_api import DocumentApi
from server.migrations import apply_pending_migrations
from server.recognition.registry import (
    build_recognition_adapter,
    recognition_settings_configured,
)
from server.recognition_service import recognition_health_payload
from server.recognition_worker import RecognitionWorker

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "audit-kanban.sqlite3"
RECOGNITION_WORKER = None
STAGES = [
    ("submitted", "报审待受理", "#3366FF"),
    ("first_audit", "一级初审", "#FF8D1A"),
    ("second_audit", "二级复审", "#E34D59"),
    ("conclusion", "定案结论", "#14B8A6"),
    ("archived", "办结归档", "#8E95A3"),
]
PROJECT_DOCUMENT_CATEGORIES = [
    ("contract", "合同文件", "合同、补充协议、合同清单等", 1),
    ("drawing", "图纸资料", "施工图、竣工图、设计变更图纸等", 1),
    ("settlement_book", "竣工结算书", "施工单位报送的结算书和汇总表", 1),
    ("visa_change", "变更签证", "现场签证、工程变更、联系单等", 1),
    ("first_audit", "一审资料", "一审过程材料、审核意见和确认资料", 1),
    ("second_audit", "二审资料", "二审复核材料、复核意见和确认资料", 1),
    ("payment", "付款资料", "付款申请、付款凭证、付款节点资料", 0),
    ("other", "其他资料", "项目相关补充资料", 0),
]
PROJECT_STATUSES = {
    "awarded": "已中标",
    "contract_signed": "已签订合同",
    "under_construction": "已进场施工中",
    "completed_acceptance": "已竣工验收",
    "pending_submission": "待报审",
    "first_audit": "一审中",
    "second_audit": "二审中",
    "conclusion": "已定案结论",
    "archived": "已归档",
}
SETTLEMENT_STATUSES = {
    "not_started": "未开始",
    "partially_paid": "已付款（部分未结清）",
    "settled": "已结清",
}
PROJECT_DICTIONARY_GROUPS = {
    "construction_unit",
    "owner_unit",
    "contractor_name",
    "manager_name",
    "company_role",
}
AUDIT_STATUSES = {
    "not_started": "未开始",
    "active": "进行中",
    "delayed": "已逾期",
    "completed": "已完成",
    "paused": "已暂停",
    "archived": "已归档",
    "deleted": "已删除",
}
EVIDENCE_STATUSES = {
    "pending": "待补资料",
    "submitted": "已提交",
    "confirmed": "资料齐全",
    "rework": "需更正",
}
RISK_LEVELS = {
    "danger": "高风险",
    "warning": "需关注",
    "primary": "待处理",
    "normal": "正常",
}
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
MAX_WORKSPACE_BACKGROUND_BYTES = 2 * 1024 * 1024
WORKSPACE_BACKGROUND_DATA_URL_RE = re.compile(
    r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$",
    re.IGNORECASE,
)


def normalize_workspace_background_image(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    match = WORKSPACE_BACKGROUND_DATA_URL_RE.fullmatch(raw)
    if not match:
        raise ValueError("工作台背景仅支持 PNG、JPG 或 WebP 图片")
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("工作台背景文件内容无法识别，请重新选择图片") from exc
    if len(content) > MAX_WORKSPACE_BACKGROUND_BYTES:
        raise ValueError("工作台背景不能超过 2 MB")

    mime_type = match.group(1).lower()
    signatures_valid = {
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
    }
    if not signatures_valid[mime_type]:
        raise ValueError("工作台背景文件内容与图片格式不一致，请重新选择图片")
    return raw


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


def sanitize_brand_color(value, fallback="#165DFF"):
    normalized = normalize_hex_color(value)
    safe_fallback = normalize_hex_color(fallback) or "#165DFF"
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


@contextmanager
def connect():
    db_path = Path(os.environ.get("AUDIT_DB_PATH", DEFAULT_DB))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def read_json(handler):
    length = int(handler.headers.get("Content-Length") or "0")
    if length == 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw or "{}")


def upload_root():
    return Path(os.environ.get("UPLOAD_ROOT", ROOT / "uploads")).resolve()


def recognition_configured():
    return recognition_settings_configured()


DEFAULT_MAX_UPLOAD_SIZE_MB = 100
MIN_UPLOAD_SIZE_MB = 1
MAX_UPLOAD_SIZE_MB = 500


def clamp_upload_size_mb(value):
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = DEFAULT_MAX_UPLOAD_SIZE_MB
    return max(MIN_UPLOAD_SIZE_MB, min(MAX_UPLOAD_SIZE_MB, size))


def upload_settings_payload(conn):
    row = conn.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'upload_settings'").fetchone()
    if not row:
        return {"maxFileSizeMb": DEFAULT_MAX_UPLOAD_SIZE_MB}
    try:
        value = json.loads(row["setting_value"] or "{}")
    except (TypeError, ValueError):
        value = {}
    return {"maxFileSizeMb": clamp_upload_size_mb(value.get("maxFileSizeMb"))}


def max_upload_size():
    try:
        with connect() as conn:
            return upload_settings_payload(conn)["maxFileSizeMb"] * 1024 * 1024
    except Exception:
        pass
    try:
        return int(os.environ.get("MAX_UPLOAD_SIZE", str(DEFAULT_MAX_UPLOAD_SIZE_MB * 1024 * 1024)))
    except ValueError:
        return DEFAULT_MAX_UPLOAD_SIZE_MB * 1024 * 1024


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
        raise ValueError(f"文件超过上传大小限制，当前上限为 {limit // 1024 // 1024}MB")
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
        if 'name="file"' not in disposition or "filename" not in disposition:
            continue
        filename = multipart_filename(disposition)
        return filename, body.rstrip(b"\r\n")
    raise ValueError("未找到上传文件")


def parse_multipart_form(handler):
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
        raise ValueError(f"文件超过上传大小限制，当前上限为 {limit // 1024 // 1024}MB")
    raw = handler.rfile.read(length)
    if len(raw) != length:
        raise ValueError("上传内容不完整，请重试")

    fields = {}
    file_part = None
    delimiter = b"--" + boundary
    for part in raw.split(delimiter):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        header_blob, body = part.split(b"\r\n\r\n", 1)
        headers = header_blob.decode("iso-8859-1", errors="ignore")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        name_match = re.search(r'name="([^"]*)"', disposition)
        if not name_match:
            continue
        field_name = name_match.group(1)
        filename = multipart_filename(disposition)
        if filename:
            file_part = (filename, body.rstrip(b"\r\n"))
        else:
            fields[field_name] = body.rstrip(b"\r\n").decode("utf-8", errors="replace").strip()
    if not file_part:
        raise ValueError("未找到上传文件")
    return fields, file_part


def repair_mojibake_filename(value):
    if not value:
        return value
    try:
        repaired = value.encode("iso-8859-1").decode("utf-8")
    except UnicodeError:
        return value
    return repaired or value


def multipart_filename(disposition):
    filename_star = re.search(r"filename\*=([^']*)''([^;]+)", disposition)
    if filename_star:
        try:
            return unquote(filename_star.group(2), encoding=filename_star.group(1) or "utf-8")
        except LookupError:
            return unquote(filename_star.group(2))
    filename_match = re.search(r'filename="([^"]*)"', disposition)
    return repair_mojibake_filename(filename_match.group(1)) if filename_match else ""


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


def stage_label(value):
    return dict((code, title) for code, title, _ in STAGES).get(value or "", value or "未设置")


def project_status_label(value):
    return PROJECT_STATUSES.get(value or "", value or "未设置")


def settlement_status_label(value):
    return SETTLEMENT_STATUSES.get(value or "", value or "未设置")


def chinese_initial(char):
    if not char:
        return ""
    if char.isascii() and char.isalnum():
        return char.upper()
    try:
        code = int.from_bytes(char.encode("gb2312"), "big")
    except UnicodeEncodeError:
        return ""
    ranges = [
        (0xB0A1, "A"), (0xB0C5, "B"), (0xB2C1, "C"), (0xB4EE, "D"), (0xB6EA, "E"), (0xB7A2, "F"),
        (0xB8C1, "G"), (0xB9FE, "H"), (0xBBF7, "J"), (0xBFA6, "K"), (0xC0AC, "L"), (0xC2E8, "M"),
        (0xC4C3, "N"), (0xC5B6, "O"), (0xC5BE, "P"), (0xC6DA, "Q"), (0xC8BB, "R"), (0xC8F6, "S"),
        (0xCBFA, "T"), (0xCDDA, "W"), (0xCEF4, "X"), (0xD1B9, "Y"), (0xD4D1, "Z"),
    ]
    for index, (start, letter) in enumerate(ranges):
        end = ranges[index + 1][0] if index + 1 < len(ranges) else 0xD7FA
        if start <= code < end:
            return letter
    return ""


def pinyin_initials(value):
    letters = [chinese_initial(char) for char in str(value or "").strip()]
    compact = "".join(char for char in letters if char)
    return compact[:8] or "XM"


def company_core_name(value):
    name = re.sub(r"[\s（）()·,，.。-]+", "", str(value or ""))
    if name.startswith(("江苏省", "江苏")):
        name = re.sub(r"^江苏省?", "", name)
    suffixes = [
        "建设工程有限公司",
        "建筑工程有限公司",
        "工程建设有限公司",
        "建设有限公司",
        "工程有限公司",
        "有限公司",
        "有限责任公司",
        "股份有限公司",
        "集团有限公司",
        "公司",
    ]
    changed = True
    while changed and name:
        changed = False
        for suffix in suffixes:
            if name.endswith(suffix) and len(name) > len(suffix):
                name = name[:-len(suffix)]
                changed = True
                break
    return name or str(value or "").strip()


def generate_project_code(conn, contract_date, construction_unit):
    date_part = re.sub(r"\D", "", str(contract_date or ""))[:8] or datetime.now().strftime("%Y%m%d")
    unit_part = pinyin_initials(company_core_name(construction_unit))
    prefix = f"{date_part}-{unit_part}"
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM project_records WHERE project_code LIKE ?",
        (f"{prefix}-%",),
    ).fetchone()
    serial = int(row["c"] or 0) + 1
    while True:
        code = f"{prefix}-{serial:03d}"
        exists = conn.execute("SELECT id FROM project_records WHERE project_code = ?", (code,)).fetchone()
        if not exists:
            return code
        serial += 1


def audit_status_label(value):
    return AUDIT_STATUSES.get(value or "", value or "未设置")


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
        "projectId": row["project_id"] or "",
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
        "stageLabel": stage_label(row["current_stage"]),
        "status": row["status"],
        "statusText": audit_status_label(row["status"]),
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


def category_payload(row):
    return {
        "id": row["id"],
        "categoryKey": row["category_key"],
        "categoryName": row["category_name"],
        "description": row["description"],
        "required": bool(row["required"]),
        "sortOrder": row["sort_order"],
        "enabled": bool(row["enabled"]),
    }


def project_file_payload(row):
    original_name = repair_mojibake_filename(row_get(row, "original_name") or row_get(row, "display_name"))
    mime_type = row_get(row, "mime_type") or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    file_ext = row_get(row, "file_ext") or Path(original_name).suffix.lower()
    can_preview = mime_type in INLINE_PREVIEW_TYPES or mime_type.startswith(INLINE_PREVIEW_PREFIXES) or file_ext in TEXT_PREVIEW_SUFFIXES
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "projectName": row_get(row, "project_name"),
        "projectCode": row_get(row, "project_code"),
        "categoryKey": row["category_key"],
        "categoryName": row_get(row, "category_name") or row["category_key"],
        "displayName": row["display_name"],
        "originalName": original_name,
        "storedName": row["stored_name"],
        "fileExt": file_ext,
        "mimeType": mime_type,
        "fileSize": int(row_get(row, "file_size", 0) or 0),
        "versionNo": int(row_get(row, "version_no", 1) or 1),
        "isCurrent": bool(row_get(row, "is_current", 1)),
        "uploadedBy": row_get(row, "uploaded_by"),
        "uploadedByName": row_get(row, "uploaded_by_name") or row_get(row, "uploaded_by"),
        "uploadedAt": row_get(row, "uploaded_at"),
        "previewUrl": f"/api/project-files/{row['id']}/preview",
        "downloadUrl": f"/api/project-files/{row['id']}/download",
        "canPreview": can_preview,
    }


def settlement_payload(row):
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "projectName": row_get(row, "project_name"),
        "projectCode": row_get(row, "project_code"),
        "settlementName": row["settlement_name"],
        "settlementType": row["settlement_type"],
        "settlementStatus": row["settlement_status"],
        "applyAmount": row["apply_amount"],
        "approvedAmount": row["approved_amount"],
        "paidAmount": row["paid_amount"],
        "applyDate": row["apply_date"],
        "expectedPayDate": row["expected_pay_date"],
        "paidDate": row["paid_date"],
        "remark": row["remark"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def settlement_finance_payload(row, payment_nodes=None):
    return {
        **settlement_payload(row),
        "ownerUnit": row_get(row, "owner_unit"),
        "constructionUnit": row_get(row, "construction_unit"),
        "managerName": row_get(row, "manager_name"),
        "projectStatus": row_get(row, "project_status"),
        "contractName": row_get(row, "contract_name"),
        "contractNo": row_get(row, "contract_no"),
        "contractAmount": row_get(row, "contract_amount", 0),
        "provisionalAmount": row_get(row, "provisional_amount", 0),
        "estimatedAmount": row_get(row, "estimated_amount", 0),
        "ownerSuppliedAmount": row_get(row, "owner_supplied_amount", 0),
        "otherDeductionAmount": row_get(row, "other_deduction_amount", 0),
        "paymentBaseAmount": row_get(row, "payment_base_amount", 0),
        "taxRate": row_get(row, "tax_rate", 0),
        "contractDate": row_get(row, "contract_date"),
        "paymentTerms": row_get(row, "payment_terms"),
        "acceptanceStatus": row_get(row, "acceptance_status"),
        "acceptanceDate": row_get(row, "acceptance_date"),
        "auditStatus": row_get(row, "audit_status"),
        "submittedAmount": row_get(row, "submitted_amount", 0),
        "firstAuditAmount": row_get(row, "first_audit_amount", 0),
        "firstAuditDate": row_get(row, "first_audit_date"),
        "secondAuditAmount": row_get(row, "second_audit_amount", 0),
        "secondAuditDate": row_get(row, "second_audit_date"),
        "finalAuditAmount": row_get(row, "final_audit_amount", 0),
        "finalAuditDate": row_get(row, "final_audit_date"),
        "hasInvoice": bool(row_get(row, "has_invoice", 0)),
        "invoicedAmount": row_get(row, "invoiced_amount", 0),
        "hasReceived": bool(row_get(row, "has_received", 0)),
        "receivedAmount": row_get(row, "received_amount", 0),
        "hasPayment": bool(row_get(row, "has_payment", 0)),
        "historicalPaidAmount": row_get(row, "historical_paid_amount", 0),
        "hasRetention": bool(row_get(row, "has_retention", 0)),
        "retentionRatio": row_get(row, "retention_ratio", 0),
        "retentionAmount": row_get(row, "retention_amount", 0),
        "warrantyStartDate": row_get(row, "warranty_start_date"),
        "warrantyEndDate": row_get(row, "warranty_end_date"),
        "paymentTemplateId": row_get(row, "payment_template_id"),
        "documentsMissing": bool(row_get(row, "documents_missing", 0)),
        "documentNote": row_get(row, "document_note"),
        "isDraft": bool(row_get(row, "is_draft", 0)),
        "paymentNodes": payment_nodes or [],
    }


def settlement_payment_node_payload(row):
    try:
        required_documents = json.loads(row_get(row, "required_documents_json") or "[]")
    except (TypeError, ValueError):
        required_documents = []
    return {
        "id": row["id"],
        "nodeName": row["node_name"],
        "nodeOrder": row["node_order"],
        "triggerCondition": row["trigger_condition"],
        "baseType": row["base_type"],
        "paymentRatio": row["payment_ratio"],
        "baseAmount": row["base_amount"],
        "calculatedAmount": row["calculated_amount"],
        "isCumulative": bool(row["is_cumulative"]),
        "deductExisting": bool(row["deduct_existing"]),
        "requiredDocuments": required_documents,
        "dueDays": row["due_days"],
        "reminderEnabled": bool(row["reminder_enabled"]),
        "nodeStatus": row["node_status"],
    }


def variation_payload(row):
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "variationName": row["variation_name"],
        "variationType": row["variation_type"],
        "variationStatus": row["variation_status"],
        "amount": row["amount"],
        "occurredDate": row["occurred_date"],
        "approvedDate": row["approved_date"],
        "remark": row["remark"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def project_log_payload(row):
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "action": row["action"],
        "content": row["content"],
        "operatorName": row["operator_name"],
        "createdAt": row["created_at"],
    }


def project_record_payload(conn, row, include_detail=False):
    files = conn.execute(
        """
        SELECT f.*, c.category_name, p.project_name, p.project_code
        FROM project_files f
        LEFT JOIN project_document_categories c ON c.category_key = f.category_key
        LEFT JOIN project_records p ON p.id = f.project_id
        WHERE f.project_id = ? AND COALESCE(f.is_deleted, 0) = 0
        ORDER BY c.sort_order, f.uploaded_at DESC
        """,
        (row["id"],),
    ).fetchall()
    required_categories = conn.execute(
        "SELECT category_key FROM project_document_categories WHERE enabled = 1 AND required = 1"
    ).fetchall()
    current_categories = {f["category_key"] for f in files if f["is_current"]}
    missing_count = sum(1 for category in required_categories if category["category_key"] not in current_categories)
    total_required = max(len(required_categories), 1)
    completion = round((total_required - missing_count) / total_required * 100)
    payload = {
        "id": row["id"],
        "projectCode": row["project_code"],
        "projectName": row["project_name"],
        "contractDate": row_get(row, "contract_date"),
        "constructionUnit": row["construction_unit"],
        "contractorName": row["contractor_name"],
        "contractorContact": row["contractor_contact"],
        "ownerUnit": row["owner_unit"],
        "companyRole": row["company_role"],
        "managerName": row["manager_name"],
        "projectStatus": row["project_status"],
        "projectStatusText": project_status_label(row["project_status"]),
        "settlementStatus": row["settlement_status"],
        "settlementStatusText": settlement_status_label(row["settlement_status"]),
        "auditStage": row["audit_stage"],
        "auditStageText": stage_label(row["audit_stage"]) if row["audit_stage"] and row["audit_stage"] != "not_linked" else "未进入审计",
        "contractAmount": row["contract_amount"],
        "submittedAmount": row["submitted_amount"],
        "paidAmount": row["paid_amount"],
        "paymentTerms": row["payment_terms"],
        "plannedStartDate": row["planned_start_date"],
        "plannedEndDate": row["planned_end_date"],
        "description": row["description"],
        "documentCompletion": completion,
        "missingRequiredCount": missing_count,
        "settlementBookStatus": row["settlement_book_status"],
        "firstAuditMaterialStatus": row["first_audit_material_status"],
        "secondAuditMaterialStatus": row["second_audit_material_status"],
        "variationCount": row["variation_count"],
        "variationAmount": row["variation_amount"],
        "auditProjectId": row["audit_project_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
    if include_detail:
        payload["files"] = [project_file_payload(file) for file in files]
        payload["settlements"] = [
            settlement_payload(item)
            for item in conn.execute(
                """
                SELECT s.*, p.project_name, p.project_code
                FROM project_settlements s
                LEFT JOIN project_records p ON p.id = s.project_id
                WHERE s.project_id = ? AND COALESCE(s.is_deleted, 0) = 0
                ORDER BY s.updated_at DESC
                """,
                (row["id"],),
            ).fetchall()
        ]
        payload["variations"] = [
            variation_payload(item)
            for item in conn.execute(
                "SELECT * FROM project_variations WHERE project_id = ? AND COALESCE(is_deleted, 0) = 0 ORDER BY updated_at DESC",
                (row["id"],),
            ).fetchall()
        ]
        payload["logs"] = [
            project_log_payload(item)
            for item in conn.execute(
                "SELECT * FROM project_operation_logs WHERE project_id = ? ORDER BY created_at DESC LIMIT 80",
                (row["id"],),
            ).fetchall()
        ]
    return payload


def project_record_columns_from_payload(data):
    return {
        "project_code": (data.get("projectCode") or "").strip(),
        "project_name": (data.get("projectName") or "").strip(),
        "contract_date": data.get("contractDate") or "",
        "construction_unit": (data.get("constructionUnit") or "").strip(),
        "contractor_name": (data.get("contractorName") or "").strip(),
        "contractor_contact": (data.get("contractorContact") or "").strip(),
        "owner_unit": (data.get("ownerUnit") or "").strip(),
        "company_role": (data.get("companyRole") or "工程咨询").strip(),
        "manager_name": (data.get("managerName") or "").strip(),
        "project_status": data.get("projectStatus") or "awarded",
        "settlement_status": data.get("settlementStatus") or "not_started",
        "audit_stage": data.get("auditStage") or "not_linked",
        "contract_amount": float(data.get("contractAmount") or 0),
        "submitted_amount": float(data.get("submittedAmount") or 0),
        "paid_amount": float(data.get("paidAmount") or 0),
        "payment_terms": data.get("paymentTerms") or "",
        "planned_start_date": data.get("plannedStartDate") or "",
        "planned_end_date": data.get("plannedEndDate") or "",
        "description": data.get("description") or "",
        "settlement_book_status": data.get("settlementBookStatus") or "missing",
        "first_audit_material_status": data.get("firstAuditMaterialStatus") or "missing",
        "second_audit_material_status": data.get("secondAuditMaterialStatus") or "missing",
        "audit_project_id": (data.get("auditProjectId") or data.get("audit_project_id") or "").strip(),
    }


PROJECT_RECORD_PAYLOAD_KEYS = {
    "project_code": ("projectCode",),
    "project_name": ("projectName",),
    "contract_date": ("contractDate",),
    "construction_unit": ("constructionUnit",),
    "contractor_name": ("contractorName",),
    "contractor_contact": ("contractorContact",),
    "owner_unit": ("ownerUnit",),
    "company_role": ("companyRole",),
    "manager_name": ("managerName",),
    "project_status": ("projectStatus",),
    "settlement_status": ("settlementStatus",),
    "audit_stage": ("auditStage",),
    "contract_amount": ("contractAmount",),
    "submitted_amount": ("submittedAmount",),
    "paid_amount": ("paidAmount",),
    "payment_terms": ("paymentTerms",),
    "planned_start_date": ("plannedStartDate",),
    "planned_end_date": ("plannedEndDate",),
    "description": ("description",),
    "settlement_book_status": ("settlementBookStatus",),
    "first_audit_material_status": ("firstAuditMaterialStatus",),
    "second_audit_material_status": ("secondAuditMaterialStatus",),
    "audit_project_id": ("auditProjectId", "audit_project_id"),
}


def project_record_update_columns(data, existing):
    """Build partial-update columns while preserving omitted persisted fields."""
    columns = project_record_columns_from_payload(data)
    for column, payload_keys in PROJECT_RECORD_PAYLOAD_KEYS.items():
        if not any(key in data for key in payload_keys):
            columns[column] = existing[column]
    return columns


def project_dictionary_options(conn):
    rows = conn.execute(
        """
        SELECT group_key, option_label, option_value
        FROM audit_field_options
        WHERE group_key IN (?, ?, ?, ?, ?) AND COALESCE(enabled, is_enabled, 1) = 1
        ORDER BY group_key, sort_order, option_label
        """,
        tuple(PROJECT_DICTIONARY_GROUPS),
    ).fetchall()
    grouped = {key: [] for key in PROJECT_DICTIONARY_GROUPS}
    seen = {key: set() for key in PROJECT_DICTIONARY_GROUPS}
    for row in rows:
        group_key = row["group_key"]
        label = row["option_label"] or row["option_value"] or ""
        value = row["option_value"] or label
        if not label or value in seen[group_key]:
            continue
        grouped[group_key].append({"label": label, "value": value})
        seen[group_key].add(value)
    return grouped


def save_project_dictionary_values(conn, data):
    ts = now_iso()
    field_map = {
        "construction_unit": data.get("constructionUnit"),
        "owner_unit": data.get("ownerUnit"),
        "contractor_name": data.get("contractorName"),
        "manager_name": data.get("managerName"),
        "company_role": data.get("companyRole"),
    }
    for group_key, raw_value in field_map.items():
        label = str(raw_value or "").strip()
        if not label:
            continue
        exists = conn.execute(
            "SELECT id FROM audit_field_options WHERE group_key = ? AND option_value = ? AND COALESCE(enabled, is_enabled, 1) = 1",
            (group_key, label),
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO audit_field_options
            (id, group_key, field_key, option_label, option_value, color, sort_order, enabled, is_enabled, is_system, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, '', ?, 1, 1, 0, ?, ?)
            """,
            (new_id(), group_key, group_key, label, label, 999, ts, ts),
        )


def project_log(conn, project_id, action, content, user=None, before=None, after=None):
    conn.execute(
        """
        INSERT INTO project_operation_logs
        (id, project_id, action, content, operator_id, operator_name, before_json, after_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id(),
            project_id,
            action,
            content,
            user["id"] if user else "",
            (user["display_name"] or user["username"]) if user else "系统",
            json.dumps(before or {}, ensure_ascii=False),
            json.dumps(after or {}, ensure_ascii=False),
            now_iso(),
        ),
    )


def evidence_status_from_project_file(row):
    if not bool(row_get(row, "is_current", 1)):
        return "需更正"
    category_key = row_get(row, "category_key", "")
    if category_key in {"first_audit", "second_audit", "settlement_book"}:
        return "已确认"
    return "已提交"


def work_item_payload(item_id, item_type, project_id, audit_project_id, project_name, owner, due_date, level, source, action, description):
    action_path = "/audit"
    if source in {"项目管理", "项目资料", "付款结算", "金额管理"}:
        action_path = f"/project-management?projectId={quote(project_id or '')}" if project_id else "/project-management"
    elif audit_project_id:
        action_path = f"/audit?projectId={quote(audit_project_id)}"
    return {
        "id": item_id,
        "type": item_type,
        "projectId": project_id or "",
        "auditProjectId": audit_project_id or "",
        "projectName": project_name or "未命名项目",
        "owner": owner or "未分配",
        "dueDate": due_date or "",
        "level": level,
        "levelText": RISK_LEVELS.get(level, "待处理"),
        "source": source,
        "action": action,
        "actionPath": action_path,
        "description": description,
        "status": "待处理",
        "statusText": "待处理",
    }


def query_work_items(conn, limit=80):
    today = date.today().isoformat()
    upcoming = (date.today() + timedelta(days=7)).isoformat()
    items = []

    for row in conn.execute("SELECT * FROM project_records WHERE COALESCE(is_deleted, 0) = 0").fetchall():
        project_id = row["id"]
        audit_project_id = row["audit_project_id"]
        name = row["project_name"]
        owner = row["manager_name"] or row["contractor_name"]
        planned_end = row["planned_end_date"]
        if int(row["missing_required_count"] or 0) > 0:
            items.append(work_item_payload(
                f"missing-doc-{project_id}",
                "资料缺失",
                project_id,
                audit_project_id,
                name,
                owner,
                planned_end,
                "warning",
                "项目资料",
                "补充资料",
                f"仍缺少 {int(row['missing_required_count'] or 0)} 类必填资料，请补齐后再推进审计。",
            ))
        if planned_end and planned_end < today and row["project_status"] != "completed":
            items.append(work_item_payload(
                f"project-overdue-{project_id}",
                "已逾期",
                project_id,
                audit_project_id,
                name,
                owner,
                planned_end,
                "danger",
                "项目管理",
                "查看项目",
                "项目计划完成日期已过，请确认当前进展和下一步处理人。",
            ))
        elif planned_end and today <= planned_end <= upcoming and row["project_status"] != "completed":
            items.append(work_item_payload(
                f"project-upcoming-{project_id}",
                "即将到期",
                project_id,
                audit_project_id,
                name,
                owner,
                planned_end,
                "warning",
                "项目管理",
                "查看项目",
                "项目即将到达计划完成日期，请提前确认资料和审批进展。",
            ))
        if row["settlement_status"] == "rejected":
            items.append(work_item_payload(
                f"rejected-{project_id}",
                "已驳回",
                project_id,
                audit_project_id,
                name,
                owner,
                planned_end,
                "danger",
                "付款结算",
                "处理退回",
                "结算事项已退回，请查看退回原因并补充说明或资料。",
            ))
        contract_amount = float(row["contract_amount"] or 0)
        submitted_amount = float(row["submitted_amount"] or 0)
        variation_amount = float(row["variation_amount"] or 0)
        if contract_amount and (submitted_amount > contract_amount * 1.2 or variation_amount > contract_amount * 0.1):
            items.append(work_item_payload(
                f"amount-risk-{project_id}",
                "金额异常",
                project_id,
                audit_project_id,
                name,
                owner,
                planned_end,
                "warning",
                "金额管理",
                "核对金额",
                "送审金额或变更签证金额偏高，请核对合同、签证和送审口径。",
            ))

    for row in conn.execute("SELECT * FROM audit_projects WHERE status != 'deleted'").fetchall():
        project_id = row["project_id"]
        audit_project_id = row["id"]
        name = row["project_name"]
        owner = row["manager_name"] or row["contractor_name"]
        deadline = row["planned_end_date"] or row["audit_deadline"]
        if deadline and deadline < today and row["current_stage"] != "archived":
            items.append(work_item_payload(
                f"audit-overdue-{audit_project_id}",
                "已逾期",
                project_id,
                audit_project_id,
                name,
                owner,
                deadline,
                "danger",
                "审计看板",
                "查看审计",
                "审计计划完成日期已过，请确认阶段责任人和处理进展。",
            ))
        if row["current_stage"] == "conclusion":
            items.append(work_item_payload(
                f"conclusion-{audit_project_id}",
                "待确认结论",
                project_id,
                audit_project_id,
                name,
                owner,
                deadline,
                "primary",
                "审计看板",
                "确认结论",
                "项目已进入定案结论阶段，请确认定案金额、附件和归档条件。",
            ))

    order = {"danger": 0, "warning": 1, "primary": 2, "normal": 3}
    return sorted(items, key=lambda item: (order.get(item["level"], 9), item["dueDate"] or "9999-99-99", item["projectName"]))[:limit]


def refresh_project_rollups(conn, project_id):
    cats = conn.execute("SELECT category_key FROM project_document_categories WHERE enabled = 1 AND required = 1").fetchall()
    current = conn.execute(
        "SELECT DISTINCT category_key FROM project_files WHERE project_id = ? AND is_current = 1 AND COALESCE(is_deleted, 0) = 0",
        (project_id,),
    ).fetchall()
    current_keys = {row["category_key"] for row in current}
    missing = sum(1 for cat in cats if cat["category_key"] not in current_keys)
    completion = round((max(len(cats), 1) - missing) / max(len(cats), 1) * 100)
    variation = conn.execute(
        "SELECT COUNT(*) AS c, COALESCE(SUM(amount), 0) AS amount FROM project_variations WHERE project_id = ? AND COALESCE(is_deleted, 0) = 0",
        (project_id,),
    ).fetchone()
    paid = conn.execute(
        "SELECT COALESCE(SUM(paid_amount), 0) AS paid FROM project_settlements WHERE project_id = ? AND COALESCE(is_deleted, 0) = 0",
        (project_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE project_records
        SET document_completion = ?, missing_required_count = ?, variation_count = ?,
            variation_amount = ?, paid_amount = ?, updated_at = ?
        WHERE id = ?
        """,
        (completion, missing, variation["c"], variation["amount"], paid["paid"], now_iso(), project_id),
    )


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
        apply_pending_migrations(conn)
        schema = (ROOT / "schema.sql").read_text(encoding="utf-8")
        conn.executescript(schema)
        ensure_compatible_columns(conn)
        backfill_derived_fields(conn)
        seed_system_settings(conn)
        seed_theme_configs(conn)
        seed_admin_user(conn)
        seed_project_document_categories(conn)
        seed_field_configs(conn)
        seed_options(conn)
        ensure_stage_field_defaults(conn)
        purge_seed_projects(conn)
        backfill_project_records(conn)
        conn.commit()


def purge_seed_projects(conn):
    rows = conn.execute(
        """
        SELECT DISTINCT p.id
        FROM audit_projects p
        JOIN audit_project_logs l ON l.project_id = p.id
        WHERE l.action = 'seed'
           OR l.log_type = 'seed'
           OR l.note LIKE '%数据库初始化种子数据%'
           OR l.content LIKE '%数据库初始化种子数据%'
        """
    ).fetchall()
    audit_ids = [row["id"] for row in rows]
    if not audit_ids:
        return

    placeholders = ",".join("?" for _ in audit_ids)
    project_rows = conn.execute(
        f"""
        SELECT id
        FROM project_records
        WHERE audit_project_id IN ({placeholders})
           OR created_by = '系统初始化'
           OR updated_by = '系统初始化'
        """,
        audit_ids,
    ).fetchall()
    project_ids = [row["id"] for row in project_rows]
    if project_ids:
        project_placeholders = ",".join("?" for _ in project_ids)
        conn.execute(f"DELETE FROM project_records WHERE id IN ({project_placeholders})", project_ids)
    conn.execute(f"DELETE FROM audit_projects WHERE id IN ({placeholders})", audit_ids)


def seed_system_settings(conn):
    ts = now_iso()
    defaults = [
        ("registration_open", {"enabled": False, "requireApproval": True}, "auth", "是否开放注册"),
        ("login_rules", {"minPasswordLength": 8, "maxLoginAttempts": 5, "sessionTimeoutMinutes": 480, "allowConcurrentSessions": True}, "auth", "登录规则"),
        ("system_name", "江苏集庆·工程管理系统", "system", "系统名称"),
        ("upload_settings", {"maxFileSizeMb": DEFAULT_MAX_UPLOAD_SIZE_MB}, "system", "文件上传设置"),
        ("sidebar_nav_order", {"order": ["/", "/bidding", "/project-management", "/audit", "/materials", "/finance"]}, "system", "侧边栏模块顺序"),
        ("current_theme", {"themeKey": "arco-theme-0000", "darkMode": False, "compactMode": False, "applyScope": "global", "brandColor": "#165DFF", "themePackage": "", "sidebarLogoVariant": "color", "workspaceBackgroundImage": ""}, "theme", "当前主题"),
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
    nav_row = conn.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'sidebar_nav_order'").fetchone()
    if nav_row:
        try:
            nav_value = json.loads(nav_row["setting_value"] or "{}")
        except (TypeError, ValueError):
            nav_value = {}
        old_default = ["/", "/project-management", "/materials", "/audit", "/bidding", "/finance"]
        new_default = ["/", "/bidding", "/project-management", "/audit", "/materials", "/finance"]
        if nav_value.get("order") == old_default:
            conn.execute(
                "UPDATE system_settings SET setting_value = ?, updated_by = 'system', updated_at = ? WHERE setting_key = 'sidebar_nav_order'",
                (json.dumps({"order": new_default}, ensure_ascii=False), ts),
            )


def seed_theme_configs(conn):
    ts = now_iso()
    themes = [
        ("arco-theme-0000", "Arco 官方默认主题", "@arco-themes/vue-0000", ["#165DFF", "#14C9C9", "#00B42A", "#FF7D00"], 1, 1, 10),
        ("arco-default", "Arco fallback", "@arco-design/web-vue", ["#165DFF", "#14C9C9", "#00B42A", "#86909C"], 1, 0, 20),
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
            "project_id": "TEXT DEFAULT ''",
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
            "table_width": "INTEGER DEFAULT 140",
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
        "project_records": {
            "contract_date": "TEXT DEFAULT ''",
            "construction_unit": "TEXT DEFAULT ''",
            "contractor_contact": "TEXT DEFAULT ''",
            "company_role": "TEXT DEFAULT ''",
            "submitted_amount": "REAL DEFAULT 0",
            "audit_project_id": "TEXT DEFAULT ''",
            "deleted_at": "TEXT DEFAULT ''",
            "is_deleted": "INTEGER DEFAULT 0",
        },
        "project_files": {
            "renamed_at": "TEXT DEFAULT ''",
            "deleted_at": "TEXT DEFAULT ''",
            "is_deleted": "INTEGER DEFAULT 0",
        },
        "project_settlements": {
            "contract_name": "TEXT DEFAULT ''",
            "contract_no": "TEXT DEFAULT ''",
            "contract_amount": "REAL DEFAULT 0",
            "provisional_amount": "REAL DEFAULT 0",
            "estimated_amount": "REAL DEFAULT 0",
            "owner_supplied_amount": "REAL DEFAULT 0",
            "other_deduction_amount": "REAL DEFAULT 0",
            "payment_base_amount": "REAL DEFAULT 0",
            "tax_rate": "REAL DEFAULT 0",
            "contract_date": "TEXT DEFAULT ''",
            "payment_terms": "TEXT DEFAULT ''",
            "acceptance_status": "TEXT DEFAULT ''",
            "acceptance_date": "TEXT DEFAULT ''",
            "audit_status": "TEXT DEFAULT ''",
            "submitted_amount": "REAL DEFAULT 0",
            "first_audit_amount": "REAL DEFAULT 0",
            "first_audit_date": "TEXT DEFAULT ''",
            "second_audit_amount": "REAL DEFAULT 0",
            "second_audit_date": "TEXT DEFAULT ''",
            "final_audit_amount": "REAL DEFAULT 0",
            "final_audit_date": "TEXT DEFAULT ''",
            "has_invoice": "INTEGER DEFAULT 0",
            "invoiced_amount": "REAL DEFAULT 0",
            "has_received": "INTEGER DEFAULT 0",
            "received_amount": "REAL DEFAULT 0",
            "has_payment": "INTEGER DEFAULT 0",
            "historical_paid_amount": "REAL DEFAULT 0",
            "has_retention": "INTEGER DEFAULT 0",
            "retention_ratio": "REAL DEFAULT 0",
            "retention_amount": "REAL DEFAULT 0",
            "warranty_start_date": "TEXT DEFAULT ''",
            "warranty_end_date": "TEXT DEFAULT ''",
            "payment_template_id": "TEXT DEFAULT ''",
            "documents_missing": "INTEGER DEFAULT 0",
            "document_note": "TEXT DEFAULT ''",
            "is_draft": "INTEGER DEFAULT 0",
            "deleted_at": "TEXT DEFAULT ''",
            "is_deleted": "INTEGER DEFAULT 0",
        },
        "project_variations": {
            "deleted_at": "TEXT DEFAULT ''",
            "is_deleted": "INTEGER DEFAULT 0",
        },
    }
    for table, columns in migrations.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, definition in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_projects_project_id ON audit_projects(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_project_records_audit_project_id ON project_records(audit_project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_settlement_payment_nodes_settlement ON settlement_payment_nodes(settlement_id, node_order)")


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
        ("first_audit_company", "一审审计单位名称", "select", "audit_unit", "firstAudit.companyName", 0, 0, 1, 1, 1, 0, 32),
        ("first_auditor_name", "一审负责人", "select", "manager", "firstAudit.auditor.name", 0, 0, 1, 1, 1, 0, 34),
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
        ("first_audit_amount", "初审金额", "number", "", "amount.firstAuditAmount", 0, 0, 1, 1, 1, 0, 152),
        ("second_audit_amount", "复审金额", "number", "", "amount.secondAuditAmount", 0, 0, 1, 1, 1, 0, 154),
        ("audit_difference", "核减金额", "number", "", "amount.auditDifference", 0, 0, 1, 1, 1, 0, 156),
        ("final_payable", "定案金额", "number", "", "amount.finalPayable", 0, 0, 1, 1, 1, 0, 158),
        ("paid_amount", "已付款金额", "number", "", "amount.paidAmount", 0, 0, 1, 1, 1, 0, 159),
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


def ensure_stage_field_defaults(conn):
    configured = conn.execute(
        "SELECT COUNT(*) AS c FROM audit_field_configs WHERE COALESCE(stage_key, '') != ''"
    ).fetchone()["c"]
    if configured:
        return
    stage_fields = {
        "submitted": {
            "audited_unit": 20,
            "submitted_amount": 30,
            "doc_status": 40,
            "start_date": 50,
            "manager_name": 60,
        },
        "first_audit": {
            "manager_name": 20,
            "first_audit_amount": 30,
            "audit_difference": 40,
            "remark_coordination": 50,
        },
        "second_audit": {
            "second_audit_amount": 30,
            "audit_difference": 40,
            "remark_coordination": 50,
        },
        "conclusion": {
            "final_payable": 30,
            "audit_difference": 40,
            "actual_end_date": 50,
            "doc_status": 60,
        },
        "archived": {
            "actual_end_date": 30,
            "doc_status": 40,
            "paid_amount": 50,
        },
    }
    for stage, fields in stage_fields.items():
        for field_key, sort_order in fields.items():
            conn.execute(
                """
                UPDATE audit_field_configs
                SET stage_key = ?, sort_order = ?, visible_in_table = 1
                WHERE field_key = ? AND COALESCE(stage_key, '') = ''
                """,
                (stage, sort_order, field_key),
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


def seed_project_document_categories(conn):
    ts = now_iso()
    for index, (key, name, desc, required) in enumerate(PROJECT_DOCUMENT_CATEGORIES):
        conn.execute(
            """
            INSERT OR IGNORE INTO project_document_categories
            (id, category_key, category_name, description, required, sort_order, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (new_id(), key, name, desc, int(required), index * 10, ts, ts),
        )


def backfill_project_records(conn):
    rows = conn.execute(
        """
        SELECT * FROM audit_projects
        WHERE status != 'deleted' AND COALESCE(project_id, '') = ''
        ORDER BY created_at
        """
    ).fetchall()
    for row in rows:
        project_code = row["project_code"] or ""
        if not project_code:
            # project_code is a required, unique business identifier. Do not fabricate one for historical rows.
            continue
        pid = new_id()
        created_at = row["created_at"] or ""
        updated_at = row["updated_at"] or ""
        stage_to_status = {
            "submitted": "pending_submission",
            "first_audit": "first_audit",
            "second_audit": "second_audit",
            "conclusion": "conclusion",
            "archived": "archived",
        }
        project_status = stage_to_status.get(row["current_stage"], "")
        conn.execute(
            """
            INSERT INTO project_records
            (id, project_code, project_name, construction_unit, contractor_name, contractor_contact,
             owner_unit, company_role, manager_name, project_status, settlement_status, audit_stage,
             contract_amount, submitted_amount, paid_amount, payment_terms, planned_start_date,
             planned_end_date, description, document_completion, missing_required_count,
             settlement_book_status, first_audit_material_status, second_audit_material_status,
             variation_count, variation_amount, audit_project_id, created_by, updated_by, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '系统初始化', '系统初始化', ?, ?)
            """,
            (
                pid,
                project_code,
                row["project_name"],
                "",
                row["contractor_name"],
                row["contractor_phone"],
                "",
                "",
                row["manager_name"] or "",
                project_status,
                "",
                row["current_stage"] or "",
                row["contract_amount"] or None,
                row["submitted_amount"] or None,
                row["paid_amount"] or None,
                row_get(row, "payment_terms"),
                "",
                row["planned_end_date"] or "",
                row["description"],
                None,
                None,
                "",
                "",
                "",
                None,
                None,
                row["id"],
                created_at,
                updated_at,
            ),
        )
        conn.execute("UPDATE audit_projects SET project_id = ? WHERE id = ?", (pid, row["id"]))
        conn.execute(
            """
            INSERT INTO project_operation_logs
            (id, project_id, action, content, operator_name, created_at)
            VALUES (?, ?, 'project.backfill', '从审计看板项目初始化主数据', '系统初始化', ?)
            """,
            (new_id(), pid, now_iso()),
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
    if params.get("only_upcoming_due", [""])[0] in ("1", "true"):
        today = date.today().isoformat()
        upcoming = (date.today() + timedelta(days=7)).isoformat()
        where.append("COALESCE(planned_end_date, audit_deadline) >= ? AND COALESCE(planned_end_date, audit_deadline) <= ? AND current_stage != 'archived'")
        values.extend([today, upcoming])
    if params.get("only_monthly_new", [""])[0] in ("1", "true"):
        month_prefix = date.today().strftime("%Y-%m")
        where.append("created_at LIKE ?")
        values.append(f"{month_prefix}%")
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
        "tableWidth": row["table_width"],
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
    document_max_upload_size = staticmethod(max_upload_size)
    # Administrators can operate globally. Other roles start with no project
    # scope until a deployment injects its real project-membership provider.
    document_project_scope_provider = staticmethod(
        lambda _conn, actor: None if actor.get("role") == "admin" else set()
    )

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Range")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def respond(self, status, data):
        if isinstance(data, dict) and data.get("success") is False:
            message = data.get("message") or data.get("error") or "操作失败，请稍后重试或联系管理员。"
            data.setdefault("error", message)
            data.setdefault("message", message)
            if status == 401:
                data.setdefault("action", "请重新登录后再继续操作。")
            elif status == 403:
                data.setdefault("action", "请联系管理员确认账号权限。")
            elif status == 404:
                data.setdefault("action", "请返回列表刷新数据后再试。")
            else:
                data.setdefault("action", "请检查填写内容后重试；如仍失败，请联系管理员。")
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
        self.respond(404, {"success": False, "error": "未找到相关记录，请确认数据是否已同步。"})

    def handle_error(self, exc):
        print(f"[audit_api] request failed: {exc}")
        self.respond(500, {"success": False, "error": "数据处理失败，请稍后重试或联系管理员。"})

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
        except ValueError:
            self.respond(400, {"success": False, "error": "文件上传失败，请重新选择文件后再试。"})
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

    def project_meta(self, conn):
        if not self.require_user(conn):
            return
        categories = conn.execute(
            "SELECT * FROM project_document_categories WHERE enabled = 1 ORDER BY sort_order, category_name"
        ).fetchall()
        self.respond(200, {
            "success": True,
            "data": {
                "categories": [category_payload(row) for row in categories],
                "projectStatuses": [{"label": label, "value": value} for value, label in PROJECT_STATUSES.items()],
                "settlementStatuses": [{"label": label, "value": value} for value, label in SETTLEMENT_STATUSES.items()],
                "dictionaryOptions": project_dictionary_options(conn),
                "auditStages": [{"label": title, "value": code} for code, title, _ in STAGES],
                "auditStatuses": [{"label": label, "value": value} for value, label in AUDIT_STATUSES.items() if value != "deleted"],
                "evidenceStatuses": [{"label": label, "value": value} for value, label in EVIDENCE_STATUSES.items()],
                "riskLevels": [{"label": label, "value": value} for value, label in RISK_LEVELS.items()],
                "uploadSettings": upload_settings_payload(conn),
            },
        })

    def project_summary(self, conn):
        if not self.require_user(conn):
            return
        rows = conn.execute("SELECT * FROM project_records WHERE COALESCE(is_deleted, 0) = 0").fetchall()
        self.respond(200, {
            "success": True,
            "data": {
                "totalProjects": len(rows),
                "activeProjects": sum(1 for row in rows if row["project_status"] in {"under_construction", "pending_submission", "first_audit", "second_audit"}),
                "settlementProjects": sum(1 for row in rows if row["settlement_status"] == "partially_paid"),
                "auditLinkedProjects": sum(1 for row in rows if row["audit_project_id"]),
                "missingDocuments": sum(1 for row in rows if int(row["missing_required_count"] or 0) > 0),
                "contractMissing": sum(1 for row in rows if not float(row["contract_amount"] or 0)),
                "variationAmount": sum(float(row["variation_amount"] or 0) for row in rows),
            },
        })

    def update_project_document_category(self, conn, category_key, data):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        row = conn.execute("SELECT * FROM project_document_categories WHERE category_key = ?", (category_key,)).fetchone()
        if not row:
            self.not_found()
            return
        required = 1 if bool(data.get("required")) else 0
        conn.execute(
            """
            UPDATE project_document_categories
            SET required = ?, updated_at = ?
            WHERE category_key = ?
            """,
            (required, now_iso(), category_key),
        )
        project_ids = [item["id"] for item in conn.execute("SELECT id FROM project_records WHERE COALESCE(is_deleted, 0) = 0").fetchall()]
        for project_id in project_ids:
            refresh_project_rollups(conn, project_id)
        self.write_operation_log(
            conn,
            "project_document_category.update",
            user,
            "project_document_category",
            category_key,
            detail={"required": bool(required)},
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM project_document_categories WHERE category_key = ?", (category_key,)).fetchone()
        self.respond(200, {"success": True, "data": category_payload(updated)})

    def create_project_dictionary_option(self, conn, data):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        group_key = str(data.get("groupKey") or "").strip()
        label = str(data.get("label") or data.get("value") or "").strip()
        if group_key not in PROJECT_DICTIONARY_GROUPS:
            self.respond(400, {"success": False, "error": "不支持的项目字典类型"})
            return
        if not label:
            self.respond(400, {"success": False, "error": "选项内容不能为空"})
            return
        existing = conn.execute(
            "SELECT option_label, option_value FROM audit_field_options WHERE group_key = ? AND option_value = ? AND COALESCE(enabled, is_enabled, 1) = 1",
            (group_key, label),
        ).fetchone()
        if not existing:
            ts = now_iso()
            conn.execute(
                """
                INSERT INTO audit_field_options
                (id, group_key, field_key, option_label, option_value, color, sort_order, enabled, is_enabled, is_system, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, '', ?, 1, 1, 0, ?, ?)
                """,
                (new_id(), group_key, group_key, label, label, 999, ts, ts),
            )
            self.write_operation_log(conn, "field_option.upsert", user, "audit_field_option", group_key, detail={"label": label})
            conn.commit()
        self.respond(201, {"success": True, "data": {"label": label, "value": label}})

    def work_items(self, conn, params):
        if not self.require_user(conn):
            return
        limit = max(min(int(params.get("limit", ["80"])[0] or 80), 200), 1)
        self.respond(200, {"success": True, "data": query_work_items(conn, limit)})

    def project_evidence_library(self, conn, params):
        if not self.require_user(conn):
            return
        keyword = (params.get("keyword", [""])[0] or "").strip()
        file_type = (params.get("fileType", params.get("file_type", [""]))[0] or "").strip()
        stage = (params.get("stage", [""])[0] or "").strip()
        uploader = (params.get("uploader", [""])[0] or "").strip()
        stage_title = {code: title for code, title, _ in STAGES}
        evidence = []

        file_where = ["COALESCE(f.is_deleted, 0) = 0"]
        file_values = []
        if keyword:
            like = f"%{keyword}%"
            file_where.append("(p.project_name LIKE ? OR p.project_code LIKE ? OR f.display_name LIKE ? OR f.original_name LIKE ?)")
            file_values.extend([like, like, like, like])
        if uploader:
            file_where.append("(f.uploaded_by_name LIKE ? OR f.uploaded_by LIKE ?)")
            file_values.extend([f"%{uploader}%", f"%{uploader}%"])
        if file_type:
            if file_type == "image":
                file_where.append("f.mime_type LIKE 'image/%'")
            elif file_type == "pdf":
                file_where.append("(f.file_ext = '.pdf' OR f.mime_type = 'application/pdf')")
            elif file_type == "text":
                file_where.append("(f.mime_type LIKE 'text/%' OR f.file_ext IN ('.txt', '.csv', '.md', '.json', '.xml', '.log'))")
            elif file_type == "audio":
                file_where.append("f.mime_type LIKE 'audio/%'")
            elif file_type == "video":
                file_where.append("f.mime_type LIKE 'video/%'")
            else:
                file_where.append(
                    "NOT (f.mime_type LIKE 'image/%' OR f.file_ext = '.pdf' OR f.mime_type = 'application/pdf' "
                    "OR f.mime_type LIKE 'text/%' OR f.file_ext IN ('.txt', '.csv', '.md', '.json', '.xml', '.log') "
                    "OR f.mime_type LIKE 'audio/%' OR f.mime_type LIKE 'video/%')"
                )
        rows = conn.execute(
            f"""
            SELECT f.*, p.project_name, p.project_code, p.audit_stage, p.audit_project_id, p.manager_name, c.category_name
            FROM project_files f
            LEFT JOIN project_records p ON p.id = f.project_id
            LEFT JOIN project_document_categories c ON c.category_key = f.category_key
            WHERE {" AND ".join(file_where)}
            ORDER BY p.project_name COLLATE NOCASE, f.uploaded_at DESC
            LIMIT 500
            """,
            file_values,
        ).fetchall()
        for row in rows:
            if stage and row_get(row, "audit_stage") != stage:
                continue
            item = project_file_payload(row)
            evidence.append({
                **item,
                "source": "project",
                "sourceLabel": "项目资料",
                "stage": row_get(row, "audit_stage") or "",
                "stageLabel": stage_title.get(row_get(row, "audit_stage"), "项目资料"),
                "managerName": row_get(row, "manager_name"),
                "evidenceStatus": evidence_status_from_project_file(row),
            })

        audit_where = ["COALESCE(a.is_deleted, 0) = 0"]
        audit_values = []
        if keyword:
            like = f"%{keyword}%"
            audit_where.append("(p.project_name LIKE ? OR p.project_code LIKE ? OR a.original_name LIKE ? OR a.file_name LIKE ?)")
            audit_values.extend([like, like, like, like])
        if uploader:
            audit_where.append("(a.uploaded_by_name LIKE ? OR a.uploaded_by LIKE ?)")
            audit_values.extend([f"%{uploader}%", f"%{uploader}%"])
        if stage:
            audit_where.append("p.current_stage = ?")
            audit_values.append(stage)
        rows = conn.execute(
            f"""
            SELECT a.*, p.project_name AS library_project_name, p.project_code AS library_project_code,
                   p.manager_name AS library_manager_name, p.current_stage
            FROM audit_project_attachments a
            LEFT JOIN audit_projects p ON p.id = a.project_id
            WHERE {" AND ".join(audit_where)}
            ORDER BY p.project_name COLLATE NOCASE, COALESCE(NULLIF(a.created_at, ''), a.uploaded_at) DESC
            LIMIT 500
            """,
            audit_values,
        ).fetchall()
        for row in rows:
            item = attachment_payload(row)
            if file_type:
                ext = (item.get("fileExt") or "").lower()
                mime = item.get("mimeType") or ""
                category = "image" if mime.startswith("image/") else ("pdf" if ext == ".pdf" or mime == "application/pdf" else ("text" if mime.startswith("text/") or ext in TEXT_PREVIEW_SUFFIXES else "other"))
                if category != file_type:
                    continue
            evidence.append({
                **item,
                "projectName": row_get(row, "library_project_name") or "未关联项目",
                "projectCode": row_get(row, "library_project_code"),
                "managerName": row_get(row, "library_manager_name"),
                "displayName": item.get("originalName") or item.get("file_name") or "审计附件",
                "categoryKey": "audit_attachment",
                "categoryName": "审计附件",
                "uploadedAt": item.get("createdAt") or item.get("uploaded_at") or "",
                "source": "audit",
                "sourceLabel": "审计证据",
                "stage": row_get(row, "current_stage") or "",
                "stageLabel": stage_title.get(row_get(row, "current_stage"), "审计阶段"),
                "evidenceStatus": "已提交",
            })

        evidence.sort(key=lambda item: (item.get("projectName") or "", item.get("uploadedAt") or item.get("createdAt") or ""), reverse=True)
        self.respond(200, {"success": True, "data": evidence[:500]})

    def list_project_records(self, conn, params):
        if not self.require_user(conn):
            return
        where = ["COALESCE(is_deleted, 0) = 0"]
        values = []
        keyword = (params.get("keyword", [""])[0] or "").strip()
        if keyword:
            where.append("(project_name LIKE ? OR project_code LIKE ? OR contractor_name LIKE ? OR construction_unit LIKE ?)")
            values.extend([f"%{keyword}%"] * 4)
        for key, column in [
            ("projectStatus", "project_status"),
            ("settlementStatus", "settlement_status"),
            ("managerName", "manager_name"),
        ]:
            value = (params.get(key, params.get(key.replace("Status", "_status"), [""]))[0] or "").strip()
            if value:
                if key == "managerName":
                    where.append(f"{column} LIKE ?")
                    values.append(f"%{value}%")
                else:
                    where.append(f"{column} = ?")
                    values.append(value)
        if params.get("onlyMissingDocuments", [""])[0] in ("1", "true"):
            where.append("missing_required_count > 0")
        if params.get("onlyAuditLinked", [""])[0] in ("1", "true"):
            where.append("COALESCE(audit_project_id, '') != ''")
        if params.get("onlyRisk", [""])[0] in ("1", "true"):
            today = date.today().isoformat()
            where.append("(missing_required_count > 0 OR (planned_end_date != '' AND planned_end_date < ? AND project_status != 'archived') OR settlement_status = 'partially_paid')")
            values.append(today)
        if params.get("onlyUpcomingDue", [""])[0] in ("1", "true"):
            today = date.today().isoformat()
            upcoming = (date.today() + timedelta(days=7)).isoformat()
            where.append("(planned_end_date != '' AND planned_end_date >= ? AND planned_end_date <= ? AND project_status != 'archived')")
            values.extend([today, upcoming])
        if params.get("onlyMonthlyNew", [""])[0] in ("1", "true"):
            month_start = date.today().replace(day=1).isoformat()
            where.append("created_at >= ?")
            values.append(month_start)
        sort = params.get("sort", ["updatedAt"])[0]
        sort_map = {
            "updatedAt": "updated_at DESC",
            "projectName": "project_name COLLATE NOCASE",
            "contractAmount": "contract_amount DESC",
            "documentCompletion": "document_completion ASC, updated_at DESC",
            "plannedEndDate": "planned_end_date ASC",
        }
        order_by = sort_map.get(sort, sort_map["updatedAt"])
        page = max(int(params.get("page", ["1"])[0] or 1), 1)
        page_size = max(min(int(params.get("pageSize", ["20"])[0] or 20), 100), 1)
        total = conn.execute(f"SELECT COUNT(*) AS c FROM project_records WHERE {' AND '.join(where)}", values).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM project_records WHERE {' AND '.join(where)} ORDER BY {order_by} LIMIT ? OFFSET ?",
            [*values, page_size, (page - 1) * page_size],
        ).fetchall()
        self.respond(200, {
            "success": True,
            "data": [project_record_payload(conn, row) for row in rows],
            "meta": {"total": total, "page": page, "pageSize": page_size},
        })

    def get_project_record(self, conn, project_id):
        if not self.require_user(conn):
            return
        row = conn.execute("SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (project_id,)).fetchone()
        if not row:
            self.not_found()
            return
        self.respond(200, {"success": True, "data": project_record_payload(conn, row, include_detail=True)})

    def create_project_record(self, conn, data):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        self.respond(409, {
            "success": False,
            "error": "请先上传合同并完成施工合同识别复核，确认后系统将自动创建项目主档案。",
            "code": "contract_review_required",
        })

    def lifecycle_transition_blockers(self, conn, row, target_stage, from_audit_progress=False):
        project = dict(row)
        current_stage = project.get("project_status") or "awarded"
        blockers = validate_adjacent_transition(current_stage, target_stage)
        if blockers:
            return blockers
        if target_stage == "contract_signed":
            has_contract_file = conn.execute(
                """
                SELECT 1 FROM project_files
                WHERE project_id = ?
                  AND category_key = 'contract'
                  AND COALESCE(is_current, 1) = 1
                  AND COALESCE(is_deleted, 0) = 0
                LIMIT 1
                """,
                (project["id"],),
            ).fetchone() is not None
            blockers.extend(contract_gate_failures(project, has_contract_file))
        if target_stage == "first_audit":
            blockers.extend(audit_start_failures(project))
            if not from_audit_progress:
                if (project.get("audit_project_id") or "").strip():
                    blockers.append({
                        "code": "audit_progress_required",
                        "field": "projectStatus",
                        "message": "项目已关联审计流程，请从审计看板推进一审阶段。",
                    })
                else:
                    blockers.append({
                        "code": "audit_link_required",
                        "field": "auditProjectId",
                        "message": "进入一审前必须先从项目详情发起审计流程。",
                    })
        return blockers

    def project_lifecycle_snapshot(self, conn, project_id):
        if not self.require_user(conn):
            return
        try:
            snapshot = lifecycle_snapshot(conn, project_id)
        except LifecycleNotFoundError:
            self.respond(404, {"success": False, "error": "未找到项目生命周期记录", "code": "project_not_found"})
            return
        self.respond(200, {"success": True, "data": snapshot})

    def validate_project_lifecycle(self, conn, project_id, data):
        if not self.require_user(conn):
            return
        row = conn.execute(
            "SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
            (project_id,),
        ).fetchone()
        if not row:
            self.respond(404, {"success": False, "error": "未找到项目生命周期记录", "code": "project_not_found"})
            return
        current_stage = row["project_status"] or "awarded"
        target_stage = (data.get("toStage") or "").strip() or lifecycle_next_stage(current_stage)
        blockers = self.lifecycle_transition_blockers(conn, row, target_stage) if target_stage else [
            {
                "code": "terminal_stage",
                "field": "toStage",
                "message": "项目已归档，不能继续推进生命周期。",
            }
        ]
        self.respond(200, {
            "success": True,
            "data": {
                "currentStage": current_stage,
                "currentStageLabel": lifecycle_stage_label(current_stage),
                "currentVersion": int(row["lifecycle_version"] or 0),
                "targetStage": target_stage,
                "targetStageLabel": lifecycle_stage_label(target_stage),
                "blockers": blockers,
                "canTransition": not blockers,
            },
        })

    def transition_project_lifecycle(self, conn, project_id, data):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        missing = []
        target_stage = (data.get("toStage") or "").strip()
        idempotency_key = (data.get("idempotencyKey") or "").strip()
        if not target_stage:
            missing.append("toStage")
        if "expectedVersion" not in data or data.get("expectedVersion") is None:
            missing.append("expectedVersion")
        if not idempotency_key:
            missing.append("idempotencyKey")
        if missing:
            self.respond(400, {
                "success": False,
                "error": "缺少生命周期推进必填参数",
                "code": "lifecycle_transition_parameters_required",
                "missing": missing,
            })
            return
        try:
            expected_version = int(data["expectedVersion"])
        except (TypeError, ValueError):
            self.respond(400, {
                "success": False,
                "error": "expectedVersion 必须是整数",
                "code": "invalid_expected_version",
            })
            return
        actor_name = (user["display_name"] or user["username"] or "").strip()
        try:
            transition = transition_project(
                conn,
                project_id,
                target_stage,
                expected_version,
                idempotency_key,
                (data.get("reason") or "").strip(),
                {"id": user["id"], "name": actor_name},
            )
        except LifecycleNotFoundError:
            self.respond(404, {"success": False, "error": "未找到项目生命周期记录", "code": "project_not_found"})
            return
        except LifecycleConflictError as exc:
            self.respond(409, {
                "success": False,
                "error": "项目生命周期版本已变化，请刷新后重试",
                "code": exc.code,
                "currentVersion": exc.current_version,
                "expectedVersion": exc.expected_version,
            })
            return
        except LifecycleIdempotencyConflictError as exc:
            snapshot = lifecycle_snapshot(conn, project_id)
            self.respond(409, {
                "success": False,
                "error": "幂等键已用于不同的生命周期目标阶段",
                "code": exc.code,
                "idempotencyKey": exc.idempotency_key,
                "existingTargetStage": exc.existing_target_stage,
                "targetStage": exc.requested_target_stage,
                "currentVersion": snapshot["lifecycleVersion"],
            })
            return
        except LifecycleBlockedError as exc:
            snapshot = lifecycle_snapshot(conn, project_id)
            self.respond(422, {
                "success": False,
                "error": "项目暂不满足生命周期推进条件",
                "code": exc.code,
                "blockers": exc.blockers,
                "currentStage": snapshot["currentStage"],
                "currentVersion": snapshot["lifecycleVersion"],
            })
            return
        snapshot = lifecycle_snapshot(conn, project_id)
        # project_lifecycle_events is the immutable audit record for this operation.
        # transition_project has already committed it, including idempotent replays.
        self.respond(200, {"success": True, "data": {"transition": transition, "snapshot": snapshot}})

    def start_project_audit(self, conn, project_id, data):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (project_id,)).fetchone()
        if not row:
            self.not_found()
            return
        blockers = audit_start_failures(dict(row))
        if blockers:
            self.respond(422, {
                "success": False,
                "error": "项目暂不满足发起审计条件",
                "code": "audit_start_blocked",
                "blockers": blockers,
                "currentStage": row["project_status"] or "awarded",
                "currentVersion": int(row["lifecycle_version"] or 0),
            })
            return
        current_audit_id = (row["audit_project_id"] or "").strip()
        if current_audit_id and conn.execute("SELECT id FROM audit_projects WHERE id = ? AND status != 'deleted'", (current_audit_id,)).fetchone():
            self.respond(409, {"success": False, "error": "该项目已进入审计流程，请直接查看审计进度"})
            return
        existing_audit = conn.execute(
            "SELECT id FROM audit_projects WHERE project_id = ? AND status != 'deleted' LIMIT 1",
            (project_id,),
        ).fetchone()
        if existing_audit:
            conn.execute(
                "UPDATE project_records SET audit_project_id = ?, audit_stage = COALESCE(NULLIF(audit_stage, ''), 'submitted'), updated_at = ? WHERE id = ?",
                (existing_audit["id"], now_iso(), project_id),
            )
            conn.commit()
            self.respond(409, {"success": False, "error": "该项目已进入审计流程，请直接查看审计进度"})
            return
        ts = now_iso()
        audit_id = new_id()
        stage = "submitted"
        deadline = row["planned_end_date"] or data.get("auditDeadline") or ""
        conn.execute(
            """
            INSERT INTO audit_projects
            (id, project_id, project_code, project_name, audited_unit, audit_type, category, priority,
             contractor_name, contractor_phone, contract_amount, submitted_amount, paid_amount,
             submit_date, audit_deadline, start_date, planned_end_date, doc_status, current_stage,
             status, progress_percent, manager_name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                project_id,
                row["project_code"],
                row["project_name"],
                row["owner_unit"] or row["construction_unit"],
                data.get("auditType") or "工程审计",
                data.get("category") or "竣工总结算",
                data.get("priority") or "S2",
                row["contractor_name"],
                row["contractor_contact"],
                float(row["contract_amount"] or 0),
                float(row["submitted_amount"] or row["contract_amount"] or 0),
                float(row["paid_amount"] or 0),
                date.today().isoformat(),
                deadline,
                row["planned_start_date"] or date.today().isoformat(),
                deadline,
                "资料齐全" if int(row["missing_required_count"] or 0) == 0 else "资料待补充",
                stage,
                "active",
                10,
                row["manager_name"] or row["contractor_name"],
                row["description"],
                ts,
                ts,
            ),
        )
        conn.execute(
            "INSERT INTO audit_project_stages (id, project_id, stage_code, stage_name, entered_at, owner, status, progress_percent, sort_order) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)",
            (new_id(), audit_id, stage, "报审待受理", ts, row["manager_name"] or row["contractor_name"], 10, 10),
        )
        conn.execute(
            "UPDATE project_records SET audit_project_id = ?, audit_stage = ?, updated_at = ?, updated_by = ? WHERE id = ?",
            (audit_id, stage, ts, user["username"], project_id),
        )
        log_action(conn, audit_id, "create", user["username"], "从项目主档案发起审计", after={"projectId": project_id})
        project_log(conn, project_id, "audit.start", "发起审计流程", user, after={"auditProjectId": audit_id})
        self.write_operation_log(conn, "project.audit.start", user, "project_record", project_id, detail={"auditProjectId": audit_id})
        conn.commit()
        audit_row = conn.execute("SELECT * FROM audit_projects WHERE id = ?", (audit_id,)).fetchone()
        self.respond(201, {"success": True, "data": project_payload(conn, audit_row)})

    def update_project_record(self, conn, project_id, data):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        row = conn.execute("SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (project_id,)).fetchone()
        if not row:
            self.not_found()
            return
        if "projectStatus" in data and data["projectStatus"] != row["project_status"]:
            self.respond(422, {
                "success": False,
                "error": "项目阶段只能通过生命周期推进接口修改",
                "code": "lifecycle_transition_required",
                "currentStage": row["project_status"] or "awarded",
                "currentVersion": int(row["lifecycle_version"] or 0),
                "blockers": [{
                    "code": "lifecycle_transition_required",
                    "field": "projectStatus",
                    "message": "请使用 /api/projects/:id/lifecycle/transitions 推进项目阶段。",
                }],
            })
            return
        requested_audit_project_id = data.get("auditProjectId", data.get("audit_project_id"))
        audit_linkage_changed = (
            requested_audit_project_id is not None
            and str(requested_audit_project_id or "").strip() != (row["audit_project_id"] or "").strip()
        ) or (
            "auditStage" in data
            and str(data.get("auditStage") or "not_linked").strip() != (row["audit_stage"] or "not_linked").strip()
        )
        if audit_linkage_changed:
            self.respond(422, {
                "success": False,
                "error": "审计关联由发起审计和审计进度流程维护，不能通过项目基础信息编辑修改",
                "code": "audit_linkage_managed",
            })
            return
        before = project_record_payload(conn, row)
        columns = project_record_update_columns(data, row)
        if not columns["project_name"]:
            self.respond(400, {"success": False, "error": "请填写项目名称"})
            return
        columns["updated_by"] = user["username"]
        columns["updated_at"] = now_iso()
        old_audit_project_id = (row["audit_project_id"] or "").strip()
        new_audit_project_id = (columns.get("audit_project_id") or "").strip()
        if new_audit_project_id and not conn.execute("SELECT id FROM audit_projects WHERE id = ?", (new_audit_project_id,)).fetchone():
            self.respond(400, {"success": False, "error": "未找到关联审计项目，请返回后重新选择"})
            return
        if new_audit_project_id:
            linked_row = conn.execute(
                "SELECT project_id FROM audit_projects WHERE id = ?",
                (new_audit_project_id,),
            ).fetchone()
            linked_project_id = (linked_row["project_id"] or "").strip() if linked_row else ""
            if linked_project_id and linked_project_id != project_id:
                self.respond(400, {"success": False, "error": "该审计流程已关联其他项目，请勿重复绑定"})
                return
        assignments = ", ".join([f"{key} = ?" for key in columns.keys()])
        try:
            conn.execute(f"UPDATE project_records SET {assignments} WHERE id = ?", (*columns.values(), project_id))
        except sqlite3.IntegrityError:
            self.respond(400, {"success": False, "error": "项目编号已存在，请更换后再保存"})
            return
        if old_audit_project_id and old_audit_project_id != new_audit_project_id:
            conn.execute(
                "UPDATE audit_projects SET project_id = '' WHERE id = ? AND project_id = ?",
                (old_audit_project_id, project_id),
            )
        if new_audit_project_id:
            conn.execute(
                "UPDATE audit_projects SET project_id = ?, updated_at = ? WHERE id = ?",
                (project_id, columns["updated_at"], new_audit_project_id),
            )
        refresh_project_rollups(conn, project_id)
        project_log(conn, project_id, "project.update", "更新项目基础信息", user, before=before, after=columns)
        save_project_dictionary_values(conn, data)
        self.write_operation_log(conn, "project_record.update", user, "project_record", project_id)
        conn.commit()
        row = conn.execute("SELECT * FROM project_records WHERE id = ?", (project_id,)).fetchone()
        self.respond(200, {"success": True, "data": project_record_payload(conn, row, include_detail=True)})

    def delete_project_record(self, conn, project_id):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        row = conn.execute("SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (project_id,)).fetchone()
        if not row:
            self.not_found()
            return
        audit_project_id = (row["audit_project_id"] or "").strip()
        if audit_project_id and conn.execute("SELECT id FROM audit_projects WHERE id = ? AND status != 'deleted'", (audit_project_id,)).fetchone():
            self.respond(400, {"success": False, "error": "该项目已进入审计流程，不能直接删除。请先完成归档或联系管理员处理。"})
            return
        conn.execute("UPDATE project_records SET is_deleted = 1, deleted_at = ?, updated_at = ? WHERE id = ?", (now_iso(), now_iso(), project_id))
        if audit_project_id:
            conn.execute(
                "UPDATE audit_projects SET project_id = '' WHERE id = ? AND project_id = ?",
                (audit_project_id, project_id),
            )
        project_log(conn, project_id, "project.delete", "删除项目", user, before=project_record_payload(conn, row))
        self.write_operation_log(conn, "project_record.delete", user, "project_record", project_id)
        conn.commit()
        self.respond(200, {"success": True, "data": None})

    def list_project_files(self, conn, params):
        if not self.require_user(conn):
            return
        where = ["COALESCE(f.is_deleted, 0) = 0"]
        values = []
        keyword = (params.get("keyword", [""])[0] or "").strip()
        if keyword:
            where.append("(f.display_name LIKE ? OR f.original_name LIKE ? OR p.project_name LIKE ? OR p.project_code LIKE ?)")
            values.extend([f"%{keyword}%"] * 4)
        category = (params.get("categoryKey", params.get("category_key", [""]))[0] or "").strip()
        if category:
            where.append("f.category_key = ?")
            values.append(category)
        project_id = (params.get("projectId", params.get("project_id", [""]))[0] or "").strip()
        if project_id:
            where.append("f.project_id = ?")
            values.append(project_id)
        rows = conn.execute(
            f"""
            SELECT f.*, p.project_name, p.project_code, c.category_name
            FROM project_files f
            LEFT JOIN project_records p ON p.id = f.project_id
            LEFT JOIN project_document_categories c ON c.category_key = f.category_key
            WHERE {" AND ".join(where)}
            ORDER BY p.project_name COLLATE NOCASE, c.sort_order, f.uploaded_at DESC
            LIMIT 500
            """,
            values,
        ).fetchall()
        self.respond(200, {"success": True, "data": [project_file_payload(row) for row in rows]})

    def upload_project_file(self, conn, project_id):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        project = conn.execute("SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (project_id,)).fetchone()
        if not project:
            self.not_found()
            return
        try:
            fields, file_part = parse_multipart_form(self)
        except ValueError:
            self.respond(400, {"success": False, "error": "资料上传失败，请重新选择文件后再试。"})
            return
        original_name, content = file_part
        category_key = (fields.get("categoryKey") or fields.get("category_key") or "").strip()
        display_name = (fields.get("displayName") or fields.get("display_name") or "").strip()
        if not category_key:
            self.respond(400, {"success": False, "error": "请选择资料分类"})
            return
        if not display_name:
            self.respond(400, {"success": False, "error": "请填写资料名称，便于后续查找"})
            return
        if not conn.execute("SELECT id FROM project_document_categories WHERE category_key = ? AND enabled = 1", (category_key,)).fetchone():
            self.respond(400, {"success": False, "error": "资料分类不存在，请刷新页面后重试"})
            return
        if is_path_like_filename(original_name):
            self.respond(400, {"success": False, "error": "不支持上传文件夹或路径型文件名"})
            return
        if is_forbidden_attachment_name(original_name):
            self.respond(400, {"success": False, "error": "不允许上传压缩包或镜像类文件"})
            return
        if not content:
            self.respond(400, {"success": False, "error": "文件内容为空，请重新选择文件"})
            return
        file_ext = Path(original_name).suffix.lower()
        mime_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        current = conn.execute(
            """
            SELECT COALESCE(MAX(version_no), 0) AS version
            FROM project_files
            WHERE project_id = ? AND category_key = ? AND display_name = ? AND COALESCE(is_deleted, 0) = 0
            """,
            (project_id, category_key, display_name),
        ).fetchone()
        version_no = int(current["version"] or 0) + 1
        if version_no > 1:
            conn.execute(
                """
                UPDATE project_files SET is_current = 0
                WHERE project_id = ? AND category_key = ? AND display_name = ?
                """,
                (project_id, category_key, display_name),
            )
        stored_name = f"{uuid.uuid4().hex}{file_ext}"
        relative_path = f"project-records/{project_id}/{stored_name}"
        target = safe_attachment_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        file_id = new_id()
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO project_files
            (id, project_id, category_key, display_name, original_name, stored_name, file_ext,
             mime_type, file_size, relative_path, version_no, is_current, uploaded_by,
             uploaded_by_name, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                file_id,
                project_id,
                category_key,
                display_name,
                original_name,
                stored_name,
                file_ext,
                mime_type,
                len(content),
                relative_path,
                version_no,
                user["username"],
                user["display_name"] or user["username"],
                ts,
            ),
        )
        refresh_project_rollups(conn, project_id)
        project_log(conn, project_id, "project_file.upload", f"上传资料：{display_name}", user, after={"fileId": file_id, "categoryKey": category_key, "versionNo": version_no})
        self.write_operation_log(conn, "project_file.upload", user, "project_file", file_id, detail={"projectId": project_id})
        conn.commit()
        row = conn.execute(
            """
            SELECT f.*, p.project_name, p.project_code, c.category_name
            FROM project_files f
            LEFT JOIN project_records p ON p.id = f.project_id
            LEFT JOIN project_document_categories c ON c.category_key = f.category_key
            WHERE f.id = ?
            """,
            (file_id,),
        ).fetchone()
        self.respond(201, {"success": True, "data": project_file_payload(row)})

    def project_file_row(self, conn, file_id):
        return conn.execute(
            """
            SELECT f.*, p.project_name, p.project_code, c.category_name
            FROM project_files f
            LEFT JOIN project_records p ON p.id = f.project_id
            LEFT JOIN project_document_categories c ON c.category_key = f.category_key
            WHERE f.id = ? AND COALESCE(f.is_deleted, 0) = 0
            """,
            (file_id,),
        ).fetchone()

    def preview_project_file(self, conn, file_id):
        if not self.require_user(conn):
            return
        row = self.project_file_row(conn, file_id)
        if not row:
            self.not_found()
            return
        original_name = repair_mojibake_filename(row["original_name"])
        mime_type = row["mime_type"] or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        file_ext = row["file_ext"] or Path(original_name).suffix.lower()
        if not (mime_type in INLINE_PREVIEW_TYPES or mime_type.startswith(INLINE_PREVIEW_PREFIXES) or file_ext in TEXT_PREVIEW_SUFFIXES):
            self.respond(415, {"success": False, "error": "该文件暂不支持在线预览，请下载后查看"})
            return
        path = safe_attachment_path(row["relative_path"])
        if not path.exists():
            self.not_found()
            return
        if file_ext in TEXT_PREVIEW_SUFFIXES and not mime_type.startswith("text/"):
            mime_type = "text/plain; charset=utf-8"
        self.respond_file(path, mime_type, original_name, inline=True)

    def download_project_file(self, conn, file_id):
        if not self.require_user(conn):
            return
        row = self.project_file_row(conn, file_id)
        if not row:
            self.not_found()
            return
        path = safe_attachment_path(row["relative_path"])
        if not path.exists():
            self.not_found()
            return
        original_name = repair_mojibake_filename(row["original_name"])
        mime_type = row["mime_type"] or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        self.respond_file(path, mime_type, original_name, inline=False)

    def rename_project_file(self, conn, file_id, data):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        row = self.project_file_row(conn, file_id)
        if not row:
            self.not_found()
            return
        display_name = (data.get("displayName") or "").strip()
        if not display_name:
            self.respond(400, {"success": False, "error": "请填写资料名称"})
            return
        conn.execute("UPDATE project_files SET display_name = ?, renamed_at = ? WHERE id = ?", (display_name, now_iso(), file_id))
        project_log(conn, row["project_id"], "project_file.rename", f"重命名资料：{display_name}", user, before=project_file_payload(row), after={"displayName": display_name})
        self.write_operation_log(conn, "project_file.rename", user, "project_file", file_id)
        conn.commit()
        row = self.project_file_row(conn, file_id)
        self.respond(200, {"success": True, "data": project_file_payload(row)})

    def delete_project_file(self, conn, file_id):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        row = self.project_file_row(conn, file_id)
        if not row:
            self.not_found()
            return
        conn.execute("UPDATE project_files SET is_deleted = 1, deleted_at = ?, is_current = 0 WHERE id = ?", (now_iso(), file_id))
        refresh_project_rollups(conn, row["project_id"])
        project_log(conn, row["project_id"], "project_file.delete", f"删除资料：{row['display_name']}", user, before=project_file_payload(row))
        self.write_operation_log(conn, "project_file.delete", user, "project_file", file_id)
        conn.commit()
        self.respond(200, {"success": True, "data": None})

    def settlement_finance_rows(self, conn):
        return conn.execute(
            """
            SELECT s.*, p.project_name, p.project_code, p.owner_unit, p.construction_unit,
                   p.manager_name, p.project_status
            FROM project_settlements s
            JOIN project_records p ON p.id = s.project_id
            WHERE COALESCE(s.is_deleted, 0) = 0 AND COALESCE(p.is_deleted, 0) = 0
            ORDER BY s.updated_at DESC
            """
        ).fetchall()

    def settlement_nodes(self, conn, settlement_id):
        return [
            settlement_payment_node_payload(row)
            for row in conn.execute(
                "SELECT * FROM settlement_payment_nodes WHERE settlement_id = ? ORDER BY node_order, created_at",
                (settlement_id,),
            ).fetchall()
        ]

    def list_settlement_finance_projects(self, conn):
        if not self.require_user(conn):
            return
        rows = self.settlement_finance_rows(conn)
        self.respond(200, {
            "success": True,
            "data": [settlement_finance_payload(row, self.settlement_nodes(conn, row["id"])) for row in rows],
        })

    def settlement_boss_dashboard(self, conn):
        if not self.require_user(conn):
            return
        rows = [row for row in self.settlement_finance_rows(conn) if not row_get(row, "is_draft", 0)]
        contract_total = sum(float(row_get(row, "contract_amount", 0) or 0) for row in rows)
        audited_total = sum(float(row_get(row, "final_audit_amount", 0) or row_get(row, "approved_amount", 0) or 0) for row in rows)
        invoice_total = sum(float(row_get(row, "invoiced_amount", 0) or 0) for row in rows)
        received_total = sum(float(row_get(row, "received_amount", 0) or 0) for row in rows)
        retention_total = sum(float(row_get(row, "retention_amount", 0) or 0) for row in rows)
        collectible = conn.execute(
            """
            SELECT COALESCE(SUM(n.calculated_amount), 0) AS total
            FROM settlement_payment_nodes n
            JOIN project_settlements s ON s.id = n.settlement_id
            WHERE COALESCE(s.is_deleted, 0) = 0 AND COALESCE(s.is_draft, 0) = 0
              AND n.node_status IN ('待开票', '待收款', '部分收款', '逾期')
            """
        ).fetchone()["total"]
        self.respond(200, {"success": True, "data": {
            "contractTotalAmount": contract_total,
            "auditedTotalAmount": audited_total,
            "invoiceTotalAmount": invoice_total,
            "receivedTotalAmount": received_total,
            "receivableAmount": max((audited_total or contract_total) - received_total, 0),
            "overdueReceivableAmount": None,
            "retentionAmount": retention_total,
            "collectibleAmount": collectible,
            "settlementProjectCount": len(rows),
            "riskProjectCount": sum(1 for row in rows if row_get(row, "documents_missing", 0)),
        }})

    def settlement_finance_workbench(self, conn):
        if not self.require_user(conn):
            return
        items = []
        for row in self.settlement_finance_rows(conn):
            if row_get(row, "is_draft", 0):
                continue
            nodes = self.settlement_nodes(conn, row["id"])
            pending = next((node for node in nodes if node["nodeStatus"] != "已完成"), None)
            if not pending and not row_get(row, "documents_missing", 0):
                continue
            action = "补齐结算资料" if row_get(row, "documents_missing", 0) else pending["nodeStatus"]
            items.append({
                "id": pending["id"] if pending else f"{row['id']}-documents",
                "projectId": row["project_id"],
                "projectName": row_get(row, "project_name"),
                "ownerUnit": row_get(row, "owner_unit"),
                "currentNode": pending["nodeName"] if pending else "结算资料",
                "amount": pending["calculatedAmount"] if pending else 0,
                "paidAmount": row_get(row, "received_amount", 0),
                "remainingAmount": max((pending["calculatedAmount"] if pending else 0) - float(row_get(row, "received_amount", 0) or 0), 0),
                "invoiceStatus": "已开票" if row_get(row, "has_invoice", 0) else "未开票",
                "documentStatus": "资料缺失" if row_get(row, "documents_missing", 0) else "资料已确认",
                "dueDate": "",
                "isOverdue": pending["nodeStatus"] == "逾期" if pending else False,
                "action": action,
                "managerName": row_get(row, "manager_name"),
            })
        self.respond(200, {"success": True, "data": items})

    def settlement_invoice_records(self, conn):
        if not self.require_user(conn):
            return
        data = []
        for row in self.settlement_finance_rows(conn):
            amount = float(row_get(row, "invoiced_amount", 0) or 0)
            if amount <= 0:
                continue
            data.append({
                "id": f"{row['id']}-invoice-summary",
                "projectName": row_get(row, "project_name"),
                "contractName": row_get(row, "contract_name"),
                "invoiceAmount": amount,
                "taxRate": row_get(row, "tax_rate", 0),
                "invoiceStatus": "已开票",
                "collectionStatus": "已收款" if float(row_get(row, "received_amount", 0) or 0) >= amount else "待收款",
                "remark": "历史累计开票金额",
            })
        self.respond(200, {"success": True, "data": data})

    def settlement_payment_records(self, conn):
        if not self.require_user(conn):
            return
        data = []
        for row in self.settlement_finance_rows(conn):
            for record_type, amount_key in (("收款", "received_amount"), ("付款", "historical_paid_amount")):
                amount = float(row_get(row, amount_key, 0) or 0)
                if amount <= 0:
                    continue
                data.append({
                    "id": f"{row['id']}-{amount_key}",
                    "projectName": row_get(row, "project_name"),
                    "contractName": row_get(row, "contract_name"),
                    "recordType": record_type,
                    "amount": amount,
                    "remark": "纳入结算管理时录入的历史累计数据",
                })
        self.respond(200, {"success": True, "data": data})

    def settlement_retention_records(self, conn):
        if not self.require_user(conn):
            return
        today = date.today().isoformat()
        data = []
        for row in self.settlement_finance_rows(conn):
            amount = float(row_get(row, "retention_amount", 0) or 0)
            if amount <= 0:
                continue
            end_date = row_get(row, "warranty_end_date") or ""
            data.append({
                "id": f"{row['id']}-retention",
                "projectName": row_get(row, "project_name"),
                "contractName": row_get(row, "contract_name"),
                "retentionRatio": row_get(row, "retention_ratio", 0),
                "retentionAmount": amount,
                "warrantyStartDate": row_get(row, "warranty_start_date"),
                "warrantyEndDate": end_date,
                "isDue": bool(end_date and end_date <= today),
                "refundStatus": "待退还" if end_date and end_date <= today else "质保期内",
            })
        self.respond(200, {"success": True, "data": data})

    def create_settlement_finance_project(self, conn, data):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        project_id = str(data.get("projectId") or "").strip()
        project = conn.execute(
            "SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
            (project_id,),
        ).fetchone()
        if not project:
            self.respond(400, {"success": False, "error": "请选择项目管理中的真实项目"})
            return
        is_draft = bool(data.get("isDraft"))
        existing = conn.execute(
            "SELECT * FROM project_settlements WHERE project_id = ? AND COALESCE(is_deleted, 0) = 0 ORDER BY updated_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if existing and not row_get(existing, "is_draft", 0):
            self.respond(409, {"success": False, "error": "该项目已纳入结算管理，不能重复生成"})
            return
        contract_amount = float(data.get("contractAmount") or project["contract_amount"] or 0)
        provisional = float(data.get("provisionalAmount") or 0)
        estimated = float(data.get("estimatedAmount") or 0)
        owner_supplied = float(data.get("ownerSuppliedAmount") or 0)
        other_deduction = float(data.get("otherDeductionAmount") or 0)
        payment_base = contract_amount - provisional - estimated - owner_supplied - other_deduction
        if not is_draft and contract_amount <= 0:
            self.respond(400, {"success": False, "error": "当前项目缺少有效合同金额，请先补充合同信息"})
            return
        if min(provisional, estimated, owner_supplied, other_deduction) < 0 or payment_base < 0:
            self.respond(400, {"success": False, "error": "合同扣除项不能为负数，且付款基数不能小于 0"})
            return
        acceptance_status = str(data.get("acceptanceStatus") or "").strip()
        audit_status = str(data.get("auditStatus") or "not_submitted").strip()
        valid_acceptance_statuses = {"not_completed", "completed_not_accepted", "accepted"}
        valid_audit_statuses = {
            "not_submitted", "submitted", "first_in_progress", "first_completed",
            "second_in_progress", "second_completed", "government_audit", "final",
        }
        if acceptance_status and acceptance_status not in valid_acceptance_statuses:
            self.respond(400, {"success": False, "error": "竣工验收状态无效"})
            return
        if not is_draft and not acceptance_status:
            self.respond(400, {"success": False, "error": "请先确认项目竣工验收状态"})
            return
        if audit_status not in valid_audit_statuses:
            self.respond(400, {"success": False, "error": "送审状态无效"})
            return
        lifecycle_rank = {stage: index for index, stage in enumerate(PROJECT_STATUSES)}
        current_project_stage = project["project_status"] or "awarded"
        current_project_rank = lifecycle_rank.get(current_project_stage, -1)
        acceptance_rank = lifecycle_rank["completed_acceptance"]
        conflict = False
        if acceptance_status == "accepted" and current_project_rank < acceptance_rank:
            conflict = True
        elif acceptance_status in {"not_completed", "completed_not_accepted"} and current_project_rank >= acceptance_rank:
            conflict = True
        minimum_audit_stage = {
            "submitted": "pending_submission",
            "first_in_progress": "first_audit",
            "first_completed": "first_audit",
            "second_in_progress": "second_audit",
            "second_completed": "second_audit",
            "government_audit": "second_audit",
            "final": "conclusion",
        }.get(audit_status)
        if minimum_audit_stage and current_project_rank < lifecycle_rank[minimum_audit_stage]:
            conflict = True
        if conflict:
            self.respond(422, {
                "success": False,
                "error": "结算信息不能超前于项目当前生命周期，请先在项目管理中推进对应阶段",
                "code": "settlement_stage_conflict",
                "currentStage": current_project_stage,
            })
            return
        if acceptance_status != "accepted" and audit_status != "not_submitted":
            self.respond(400, {"success": False, "error": "项目竣工验收合格后才能进入送审流程"})
            return
        if acceptance_status == "accepted" and not is_draft and not str(data.get("acceptanceDate") or "").strip():
            self.respond(400, {"success": False, "error": "验收合格的项目必须填写竣工验收日期"})
            return
        acceptance_date = str(data.get("acceptanceDate") or "").strip() if acceptance_status == "accepted" else ""
        audit_rank = {
            "not_submitted": 0, "submitted": 1, "first_in_progress": 2, "first_completed": 3,
            "second_in_progress": 4, "second_completed": 5, "government_audit": 6, "final": 7,
        }.get(audit_status, 0) if acceptance_status == "accepted" else 0
        submitted_amount = float(data.get("submittedAmount") or 0) if audit_rank >= 1 else 0.0
        first_audit_amount = float(data.get("firstAuditAmount") or 0) if audit_rank >= 3 else 0.0
        first_audit_date = str(data.get("firstAuditDate") or "").strip() if audit_rank >= 3 else ""
        second_audit_amount = float(data.get("secondAuditAmount") or 0) if audit_rank >= 5 else 0.0
        second_audit_date = str(data.get("secondAuditDate") or "").strip() if audit_rank >= 5 else ""
        final_audit_amount = float(data.get("finalAuditAmount") or 0) if audit_rank >= 7 else 0.0
        final_audit_date = str(data.get("finalAuditDate") or "").strip() if audit_rank >= 7 else ""
        retention_ratio = float(data.get("retentionRatio") or 0) if audit_rank >= 7 else 0.0
        warranty_start_date = str(data.get("warrantyStartDate") or "").strip() if audit_rank >= 7 else ""
        warranty_end_date = str(data.get("warrantyEndDate") or "").strip() if audit_rank >= 7 else ""
        if not is_draft and audit_rank >= 1 and submitted_amount <= 0:
            self.respond(400, {"success": False, "error": "项目进入送审后必须填写送审金额"})
            return
        if not is_draft and audit_rank >= 3 and (first_audit_amount <= 0 or not first_audit_date):
            self.respond(400, {"success": False, "error": "一审完成时必须填写一审审定金额和完成日期"})
            return
        if not is_draft and audit_rank >= 5 and (second_audit_amount <= 0 or not second_audit_date):
            self.respond(400, {"success": False, "error": "二审完成时必须填写二审审定金额和完成日期"})
            return
        if not is_draft and audit_rank >= 7 and (final_audit_amount <= 0 or not final_audit_date):
            self.respond(400, {"success": False, "error": "最终定案时必须填写最终审定金额和定案日期"})
            return
        invoiced = float(data.get("invoicedAmount") or 0)
        received = float(data.get("receivedAmount") or 0)
        historical_paid = float(data.get("historicalPaidAmount") or 0)
        retention_amount = float(data.get("retentionAmount") or 0)
        audit_cap = float(final_audit_amount or contract_amount or 0)
        if invoiced > audit_cap or historical_paid > contract_amount or retention_amount > contract_amount:
            self.respond(400, {"success": False, "error": "历史开票、付款或质保金金额超过允许上限，请核对后再提交"})
            return
        if received > invoiced and not str(data.get("exceptionNote") or "").strip():
            self.respond(400, {"success": False, "error": "已收款金额大于已开票金额时必须填写特殊情况说明"})
            return
        payment_nodes = data.get("paymentNodes") or []
        if not is_draft and not payment_nodes:
            self.respond(400, {"success": False, "error": "请先生成至少一个付款节点"})
            return
        ts = now_iso()
        settlement_id = existing["id"] if existing else new_id()
        if is_draft:
            settlement_status = data.get("settlementStatus") or "草稿"
        elif acceptance_status == "not_completed":
            settlement_status = "未进入结算"
        elif acceptance_status == "completed_not_accepted":
            settlement_status = "待验收"
        else:
            settlement_status = data.get("settlementStatus") or "资料准备中"
        columns = {
            "project_id": project_id,
            "settlement_name": (data.get("settlementName") or f"{project['project_name']}结算管理").strip(),
            "settlement_type": "project_settlement",
            "settlement_status": settlement_status,
            "apply_amount": submitted_amount,
            "approved_amount": float(final_audit_amount or second_audit_amount or first_audit_amount or 0),
            "paid_amount": received,
            "apply_date": acceptance_date,
            "expected_pay_date": "",
            "paid_date": "",
            "remark": data.get("remark") or data.get("exceptionNote") or "",
            "contract_name": data.get("contractName") or f"{project['project_name']}合同",
            "contract_no": data.get("contractNo") or "",
            "contract_amount": contract_amount,
            "provisional_amount": provisional,
            "estimated_amount": estimated,
            "owner_supplied_amount": owner_supplied,
            "other_deduction_amount": other_deduction,
            "payment_base_amount": payment_base,
            "tax_rate": float(data.get("taxRate") or 0),
            "contract_date": data.get("contractDate") or project["contract_date"] or "",
            "payment_terms": data.get("paymentTerms") or project["payment_terms"] or "",
            "acceptance_status": acceptance_status,
            "acceptance_date": acceptance_date,
            "audit_status": audit_status,
            "submitted_amount": submitted_amount,
            "first_audit_amount": first_audit_amount,
            "first_audit_date": first_audit_date,
            "second_audit_amount": second_audit_amount,
            "second_audit_date": second_audit_date,
            "final_audit_amount": final_audit_amount,
            "final_audit_date": final_audit_date,
            "has_invoice": 1 if data.get("hasInvoice") else 0,
            "invoiced_amount": invoiced,
            "has_received": 1 if data.get("hasReceived") else 0,
            "received_amount": received,
            "has_payment": 1 if data.get("hasPayment") else 0,
            "historical_paid_amount": historical_paid,
            "has_retention": 1 if data.get("hasRetention") else 0,
            "retention_ratio": retention_ratio,
            "retention_amount": retention_amount,
            "warranty_start_date": warranty_start_date,
            "warranty_end_date": warranty_end_date,
            "payment_template_id": data.get("paymentTemplateId") or "",
            "documents_missing": 1 if data.get("documentsMissing") else 0,
            "document_note": data.get("documentNote") or "",
            "is_draft": 1 if is_draft else 0,
            "updated_by": user["username"],
            "updated_at": ts,
        }
        if existing:
            assignments = ", ".join(f"{key} = ?" for key in columns)
            conn.execute(f"UPDATE project_settlements SET {assignments} WHERE id = ?", (*columns.values(), settlement_id))
        else:
            columns["created_by"] = user["username"]
            columns["created_at"] = ts
            names = ", ".join(["id", *columns.keys()])
            marks = ", ".join(["?"] * (len(columns) + 1))
            conn.execute(f"INSERT INTO project_settlements ({names}) VALUES ({marks})", (settlement_id, *columns.values()))
        conn.execute("DELETE FROM settlement_payment_nodes WHERE settlement_id = ?", (settlement_id,))
        cumulative_amount = 0.0
        invoice_remaining = invoiced
        received_remaining = received
        trigger_rank = {
            "not_submitted": 0, "submitted": 1, "first_in_progress": 2, "first_completed": 3,
            "second_in_progress": 4, "second_completed": 5, "government_audit": 6, "final": 7,
        }
        required_rank = {"ACCEPTANCE_COMPLETED": 0, "FIRST_AUDIT_COMPLETED": 3, "SECOND_AUDIT_COMPLETED": 5, "FINAL_AUDIT_COMPLETED": 7}
        for index, node in enumerate(payment_nodes):
            base_type = node.get("baseType") or "CONTRACT_PAYMENT_BASE"
            base_amounts = {
                "CONTRACT_PAYMENT_BASE": payment_base,
                "FIRST_AUDIT_AMOUNT": first_audit_amount,
                "SECOND_AUDIT_AMOUNT": second_audit_amount,
                "FINAL_AUDIT_AMOUNT": final_audit_amount,
            }
            base_amount = base_amounts.get(base_type, payment_base)
            ratio = float(node.get("paymentRatio") or 0)
            target_amount = max(base_amount * ratio, 0)
            calculated = max(target_amount - cumulative_amount, 0) if node.get("isCumulative", True) else target_amount
            if node.get("isCumulative", True):
                cumulative_amount += calculated
            trigger = node.get("triggerCondition") or ""
            if trigger == "WARRANTY_EXPIRED":
                triggered = bool(columns["warranty_end_date"] and columns["warranty_end_date"] <= date.today().isoformat())
            elif trigger == "ACCEPTANCE_COMPLETED":
                triggered = columns["acceptance_status"] == "accepted"
            else:
                triggered = trigger_rank.get(columns["audit_status"], 0) >= required_rank.get(trigger, 99)
            invoice_used = min(invoice_remaining, calculated)
            received_used = min(received_remaining, calculated)
            invoice_remaining -= invoice_used
            received_remaining -= received_used
            if not triggered:
                node_status = "未满足"
            elif columns["documents_missing"]:
                node_status = "待补资料"
            elif invoice_used < calculated:
                node_status = "待开票"
            elif received_used <= 0:
                node_status = "待收款"
            elif received_used < calculated:
                node_status = "部分收款"
            else:
                node_status = "已完成"
            conn.execute(
                """
                INSERT INTO settlement_payment_nodes
                (id, settlement_id, project_id, node_name, node_order, trigger_condition, base_type,
                 payment_ratio, base_amount, calculated_amount, is_cumulative, deduct_existing,
                 required_documents_json, due_days, reminder_enabled, node_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id(), settlement_id, project_id, str(node.get("nodeName") or f"付款节点 {index + 1}"),
                    int(node.get("nodeOrder") or index + 1), trigger, base_type, ratio, base_amount, calculated,
                    1 if node.get("isCumulative", True) else 0, 1 if node.get("deductExisting", True) else 0,
                    json.dumps(node.get("requiredDocuments") or [], ensure_ascii=False), int(node.get("dueDays") or 30),
                    1 if node.get("reminderEnabled", True) else 0, node_status, ts, ts,
                ),
            )
        conn.execute(
            "UPDATE project_records SET settlement_status = ?, updated_at = ? WHERE id = ?",
            (columns["settlement_status"], ts, project_id),
        )
        refresh_project_rollups(conn, project_id)
        project_log(
            conn, project_id, "settlement_finance.draft" if is_draft else "settlement_finance.create",
            "保存结算草稿" if is_draft else "纳入结算管理", user, after=columns,
        )
        self.write_operation_log(
            conn, "settlement_finance.draft" if is_draft else "settlement_finance.create",
            user, "project_settlement", settlement_id,
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT s.*, p.project_name, p.project_code, p.owner_unit, p.construction_unit,
                   p.manager_name, p.project_status
            FROM project_settlements s JOIN project_records p ON p.id = s.project_id WHERE s.id = ?
            """,
            (settlement_id,),
        ).fetchone()
        self.respond(200 if existing else 201, {
            "success": True,
            "data": settlement_finance_payload(row, self.settlement_nodes(conn, settlement_id)),
        })

    def list_project_settlements(self, conn, params):
        if not self.require_user(conn):
            return
        where = ["COALESCE(s.is_deleted, 0) = 0"]
        values = []
        keyword = (params.get("keyword", [""])[0] or "").strip()
        if keyword:
            where.append("(s.settlement_name LIKE ? OR p.project_name LIKE ? OR p.project_code LIKE ?)")
            values.extend([f"%{keyword}%"] * 3)
        status = (params.get("settlementStatus", params.get("status", [""]))[0] or "").strip()
        if status:
            where.append("s.settlement_status = ?")
            values.append(status)
        project_id = (params.get("projectId", params.get("project_id", [""]))[0] or "").strip()
        if project_id:
            where.append("s.project_id = ?")
            values.append(project_id)
        rows = conn.execute(
            f"""
            SELECT s.*, p.project_name, p.project_code
            FROM project_settlements s
            LEFT JOIN project_records p ON p.id = s.project_id
            WHERE {" AND ".join(where)}
            ORDER BY s.updated_at DESC
            LIMIT 300
            """,
            values,
        ).fetchall()
        self.respond(200, {"success": True, "data": [settlement_payload(row) for row in rows]})

    def list_project_variations(self, conn, params):
        if not self.require_user(conn):
            return
        where = ["COALESCE(v.is_deleted, 0) = 0"]
        values = []
        project_id = (params.get("projectId", params.get("project_id", [""]))[0] or "").strip()
        if project_id:
            where.append("v.project_id = ?")
            values.append(project_id)
        keyword = (params.get("keyword", [""])[0] or "").strip()
        if keyword:
            where.append("(v.variation_name LIKE ? OR p.project_name LIKE ? OR p.project_code LIKE ?)")
            values.extend([f"%{keyword}%"] * 3)
        rows = conn.execute(
            f"""
            SELECT v.*, p.project_name, p.project_code
            FROM project_variations v
            LEFT JOIN project_records p ON p.id = v.project_id
            WHERE {" AND ".join(where)}
            ORDER BY v.updated_at DESC
            LIMIT 300
            """,
            values,
        ).fetchall()
        self.respond(200, {"success": True, "data": [variation_payload(row) for row in rows]})

    def get_project_variation(self, conn, variation_id):
        if not self.require_user(conn):
            return
        row = conn.execute(
            "SELECT * FROM project_variations WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
            (variation_id,),
        ).fetchone()
        if not row:
            self.not_found()
            return
        self.respond(200, {"success": True, "data": variation_payload(row)})

    def upsert_project_settlement(self, conn, data, settlement_id=None):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        project_id = data.get("projectId") or data.get("project_id") or ""
        if settlement_id:
            existing = conn.execute("SELECT * FROM project_settlements WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (settlement_id,)).fetchone()
            if not existing:
                self.not_found()
                return
            project_id = existing["project_id"]
        if not conn.execute("SELECT id FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (project_id,)).fetchone():
            self.respond(400, {"success": False, "error": "未找到关联项目，请返回项目台账重新选择"})
            return
        name = (data.get("settlementName") or "").strip()
        if not name:
            self.respond(400, {"success": False, "error": "请填写结算事项名称"})
            return
        ts = now_iso()
        columns = {
            "settlement_name": name,
            "settlement_type": data.get("settlementType") or "progress",
            "settlement_status": data.get("settlementStatus") or "not_started",
            "apply_amount": float(data.get("applyAmount") or 0),
            "approved_amount": float(data.get("approvedAmount") or 0),
            "paid_amount": float(data.get("paidAmount") or 0),
            "apply_date": data.get("applyDate") or "",
            "expected_pay_date": data.get("expectedPayDate") or "",
            "paid_date": data.get("paidDate") or "",
            "remark": data.get("remark") or "",
            "updated_by": user["username"],
            "updated_at": ts,
        }
        if settlement_id:
            assignments = ", ".join([f"{key} = ?" for key in columns.keys()])
            conn.execute(f"UPDATE project_settlements SET {assignments} WHERE id = ?", (*columns.values(), settlement_id))
            action = "project_settlement.update"
            content = f"更新结算：{name}"
        else:
            settlement_id = new_id()
            columns["project_id"] = project_id
            columns["created_by"] = user["username"]
            columns["created_at"] = ts
            names = ", ".join(["id", *columns.keys()])
            marks = ", ".join(["?"] * (len(columns) + 1))
            conn.execute(f"INSERT INTO project_settlements ({names}) VALUES ({marks})", (settlement_id, *columns.values()))
            action = "project_settlement.create"
            content = f"新增结算：{name}"
        conn.execute("UPDATE project_records SET settlement_status = ?, updated_at = ? WHERE id = ?", (columns["settlement_status"], ts, project_id))
        refresh_project_rollups(conn, project_id)
        project_log(conn, project_id, action, content, user, after=columns)
        self.write_operation_log(conn, action, user, "project_settlement", settlement_id)
        conn.commit()
        row = conn.execute(
            "SELECT s.*, p.project_name, p.project_code FROM project_settlements s LEFT JOIN project_records p ON p.id = s.project_id WHERE s.id = ?",
            (settlement_id,),
        ).fetchone()
        self.respond(200 if action.endswith("update") else 201, {"success": True, "data": settlement_payload(row)})

    def get_project_settlement(self, conn, settlement_id):
        if not self.require_user(conn):
            return
        row = conn.execute(
            "SELECT s.*, p.project_name, p.project_code FROM project_settlements s LEFT JOIN project_records p ON p.id = s.project_id WHERE s.id = ? AND COALESCE(s.is_deleted, 0) = 0",
            (settlement_id,),
        ).fetchone()
        if not row:
            self.not_found()
            return
        self.respond(200, {"success": True, "data": settlement_payload(row)})

    def upsert_project_variation(self, conn, data, variation_id=None):
        user = self.require_role(conn, {"admin", "editor"})
        if not user:
            return
        project_id = data.get("projectId") or data.get("project_id") or ""
        if variation_id:
            existing = conn.execute("SELECT * FROM project_variations WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (variation_id,)).fetchone()
            if not existing:
                self.not_found()
                return
            project_id = existing["project_id"]
        if not conn.execute("SELECT id FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (project_id,)).fetchone():
            self.respond(400, {"success": False, "error": "未找到关联项目，请返回项目台账重新选择"})
            return
        name = (data.get("variationName") or "").strip()
        if not name:
            self.respond(400, {"success": False, "error": "请填写变更签证名称"})
            return
        ts = now_iso()
        columns = {
            "variation_name": name,
            "variation_type": data.get("variationType") or "change",
            "variation_status": data.get("variationStatus") or "pending",
            "amount": float(data.get("amount") or 0),
            "occurred_date": data.get("occurredDate") or "",
            "approved_date": data.get("approvedDate") or "",
            "remark": data.get("remark") or "",
            "updated_by": user["username"],
            "updated_at": ts,
        }
        if variation_id:
            assignments = ", ".join([f"{key} = ?" for key in columns.keys()])
            conn.execute(f"UPDATE project_variations SET {assignments} WHERE id = ?", (*columns.values(), variation_id))
            action = "project_variation.update"
            content = f"更新变更签证：{name}"
        else:
            variation_id = new_id()
            columns["project_id"] = project_id
            columns["created_by"] = user["username"]
            columns["created_at"] = ts
            names = ", ".join(["id", *columns.keys()])
            marks = ", ".join(["?"] * (len(columns) + 1))
            conn.execute(f"INSERT INTO project_variations ({names}) VALUES ({marks})", (variation_id, *columns.values()))
            action = "project_variation.create"
            content = f"新增变更签证：{name}"
        refresh_project_rollups(conn, project_id)
        project_log(conn, project_id, action, content, user, after=columns)
        self.write_operation_log(conn, action, user, "project_variation", variation_id)
        conn.commit()
        row = conn.execute("SELECT * FROM project_variations WHERE id = ?", (variation_id,)).fetchone()
        self.respond(200 if action.endswith("update") else 201, {"success": True, "data": variation_payload(row)})

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

    def delete_user(self, conn, uid):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        if user["id"] == uid:
            self.respond(400, {"success": False, "error": "不能删除当前登录账号"})
            return
        row = conn.execute("SELECT * FROM system_users WHERE id = ?", (uid,)).fetchone()
        if not row:
            self.not_found()
            return
        if row["role"] == "admin" and row["is_active"]:
            active_admin_count = conn.execute(
                "SELECT COUNT(*) AS c FROM system_users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()["c"]
            if active_admin_count <= 1:
                self.respond(400, {"success": False, "error": "至少需要保留一个启用状态的管理员账号"})
                return
        conn.execute("DELETE FROM system_users WHERE id = ?", (uid,))
        self.write_operation_log(conn, "user.delete", user, "system_user", uid, detail={"username": row["username"]})
        conn.commit()
        self.respond(200, {"success": True, "data": None})

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

    def system_sidebar_nav_order(self, conn):
        if not self.require_user(conn):
            return
        allowed = ["/", "/bidding", "/project-management", "/audit", "/materials", "/finance"]
        row = conn.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'sidebar_nav_order'").fetchone()
        try:
            value = json.loads(row["setting_value"] or "{}") if row else {}
            submitted = value.get("order") if isinstance(value, dict) else []
        except (TypeError, ValueError):
            submitted = []
        next_order = [item for item in submitted if item in allowed]
        next_order.extend([item for item in allowed if item not in next_order])
        self.respond(200, {"success": True, "data": {"order": next_order}})

    def set_system_setting(self, conn, key, data):
        user = self.require_role(conn, {"admin"})
        if not user:
            return
        ts = now_iso()
        value = data.get("value")
        if key == "upload_settings":
            value = {"maxFileSizeMb": clamp_upload_size_mb((value or {}).get("maxFileSizeMb"))}
        if key == "sidebar_nav_order":
            allowed = ["/", "/bidding", "/project-management", "/audit", "/materials", "/finance"]
            submitted = value.get("order") if isinstance(value, dict) else []
            next_order = [item for item in submitted if item in allowed]
            next_order.extend([item for item in allowed if item not in next_order])
            value = {"order": next_order}
        conn.execute(
            """
            INSERT INTO system_settings
            (setting_key, setting_value, setting_group, description, updated_by, created_at, updated_at)
            VALUES (?, ?, 'system', '', ?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
              setting_value = excluded.setting_value, updated_by = excluded.updated_by, updated_at = excluded.updated_at
            """,
            (key, json.dumps(value, ensure_ascii=False), user["username"], ts, ts),
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
        value["brandColor"] = normalize_hex_color(value.get("brandColor")) or "#165DFF"
        if (
            value.get("themeKey") == "arco-theme-0000"
            and value.get("brandColor") == "#4787F0"
            and not value.get("themePackage")
        ):
            value["brandColor"] = "#165DFF"
        if not value.get("themePackage"):
            value["themePackage"] = ""
        if value.get("sidebarLogoVariant") not in {"color", "white", "black"}:
            value["sidebarLogoVariant"] = "color"
        value["workspaceBackgroundImage"] = value.get("workspaceBackgroundImage") or ""
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
        brand_color = normalize_hex_color(brand_color) or "#165DFF"
        theme_package = str(data.get("themePackage") or "").strip()
        if theme_package and not re.match(r"^@(arco-design/theme|arco-themes/vue)-[a-z0-9-]+$", theme_package, re.IGNORECASE):
            self.respond(400, {"success": False, "error": "样式名称格式不正确，请从主题商店复制完整名称后再试。"})
            return
        sidebar_logo_variant = str(data.get("sidebarLogoVariant") or "color").strip()
        if sidebar_logo_variant not in {"color", "white", "black"}:
            self.respond(400, {"success": False, "error": "侧边栏 LOGO 色彩选择不正确，请重新选择后保存。"})
            return
        try:
            workspace_background_image = normalize_workspace_background_image(data.get("workspaceBackgroundImage"))
        except ValueError as exc:
            self.respond(400, {"success": False, "error": str(exc)})
            return
        value = {
            "themeKey": theme_key,
            "darkMode": bool(data.get("darkMode")),
            "compactMode": bool(data.get("compactMode")),
            "applyScope": data.get("applyScope") or "global",
            "brandColor": brand_color,
            "themePackage": theme_package,
            "sidebarLogoVariant": sidebar_logo_variant,
            "workspaceBackgroundImage": workspace_background_image,
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
        self.update_theme_current(conn, {"themeKey": "arco-theme-0000", "darkMode": False, "compactMode": False, "applyScope": "global", "brandColor": "#165DFF", "themePackage": "", "sidebarLogoVariant": "color", "workspaceBackgroundImage": ""})

    def theme_payload(self, row):
        if not row:
            return None
        preview_colors = json.loads(row["preview_colors"] or "[]")
        if row["theme_key"] in {"arco-theme-0000", "arco-default"} and preview_colors[:1] == ["#4787F0"]:
            preview_colors = ["#165DFF", *preview_colors[1:]]
        return {
            "id": row["id"],
            "themeKey": row["theme_key"],
            "themeName": row["theme_name"],
            "packageName": row["package_name"],
            "previewColors": preview_colors,
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

    def mounted_document_api(self, conn, user):
        actor = {
            "id": user["id"],
            "name": user["display_name"] or user["username"],
            "role": user["role"],
        }
        return DocumentApi(
            conn=conn,
            handler=self,
            actor=actor,
            allowed_project_ids=self.document_project_scope_provider(conn, actor),
            storage_root=upload_root(),
            max_upload_size=self.document_max_upload_size(),
            read_json=read_json,
            filename_decoder=multipart_filename,
            project_code_generator=generate_project_code,
            recognition_adapter_key=build_recognition_adapter().adapter_key,
        )

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)
            with connect() as conn:
                if DocumentApi.is_route("GET", path):
                    user = self.require_user(conn)
                    if user:
                        self.mounted_document_api(conn, user).dispatch("GET", path)
                    return
                elif path == "/api/health":
                    recognition_health = recognition_health_payload(
                        conn,
                        recognition_configured=recognition_configured(),
                        worker_alive=bool(
                            RECOGNITION_WORKER and RECOGNITION_WORKER.is_alive
                        ),
                    )
                    self.respond(
                        200,
                        {
                            "success": True,
                            "data": {
                                "status": "ok",
                                "time": now_iso(),
                                **recognition_health,
                            },
                        },
                    )
                elif path.startswith("/api/audit/") and not self.require_user(conn):
                    return
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
                elif path == "/api/system/sidebar-nav-order":
                    self.system_sidebar_nav_order(conn)
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
                elif path == "/api/projects/meta":
                    self.project_meta(conn)
                elif path == "/api/projects/summary":
                    self.project_summary(conn)
                elif path == "/api/work-items":
                    self.work_items(conn, params)
                elif path == "/api/projects":
                    self.list_project_records(conn, params)
                elif path == "/api/project-evidence":
                    self.project_evidence_library(conn, params)
                elif path == "/api/project-files":
                    self.list_project_files(conn, params)
                elif path == "/api/project-settlements":
                    self.list_project_settlements(conn, params)
                elif path == "/api/settlement/dashboard/boss":
                    self.settlement_boss_dashboard(conn)
                elif path == "/api/settlement/workbench/finance":
                    self.settlement_finance_workbench(conn)
                elif path == "/api/settlement/projects":
                    self.list_settlement_finance_projects(conn)
                elif path == "/api/settlement/invoices":
                    self.settlement_invoice_records(conn)
                elif path == "/api/settlement/payment-records":
                    self.settlement_payment_records(conn)
                elif path == "/api/settlement/retentions":
                    self.settlement_retention_records(conn)
                elif path == "/api/project-variations":
                    self.list_project_variations(conn, params)
                elif re.match(r"^/api/project-settlements/([^/]+)$", path):
                    self.get_project_settlement(conn, re.match(r"^/api/project-settlements/([^/]+)$", path).group(1))
                elif re.match(r"^/api/project-variations/([^/]+)$", path):
                    self.get_project_variation(conn, re.match(r"^/api/project-variations/([^/]+)$", path).group(1))
                elif re.match(r"^/api/projects/([^/]+)/files$", path):
                    params["projectId"] = [re.match(r"^/api/projects/([^/]+)/files$", path).group(1)]
                    self.list_project_files(conn, params)
                elif re.match(r"^/api/project-files/([^/]+)/preview$", path):
                    self.preview_project_file(conn, re.match(r"^/api/project-files/([^/]+)/preview$", path).group(1))
                elif re.match(r"^/api/project-files/([^/]+)/download$", path):
                    self.download_project_file(conn, re.match(r"^/api/project-files/([^/]+)/download$", path).group(1))
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
                elif re.match(r"^/api/projects/([^/]+)/lifecycle$", path):
                    self.project_lifecycle_snapshot(conn, re.match(r"^/api/projects/([^/]+)/lifecycle$", path).group(1))
                else:
                    project_match = re.match(r"^/api/projects/([^/]+)$", path)
                    if project_match:
                        self.get_project_record(conn, project_match.group(1))
                        return
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
                if DocumentApi.is_route("POST", path):
                    user = self.require_user(conn)
                    if user:
                        self.mounted_document_api(conn, user).dispatch("POST", path)
                    return
                project_file_upload_match = re.match(r"^/api/projects/([^/]+)/files$", path)
                if project_file_upload_match:
                    self.upload_project_file(conn, project_file_upload_match.group(1))
                    return
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
                elif path == "/api/projects":
                    self.create_project_record(conn, data)
                elif path == "/api/settlement/projects":
                    self.create_settlement_finance_project(conn, data)
                elif path == "/api/projects/dictionary-options":
                    self.create_project_dictionary_option(conn, data)
                elif re.match(r"^/api/projects/([^/]+)/lifecycle/validate$", path):
                    self.validate_project_lifecycle(conn, re.match(r"^/api/projects/([^/]+)/lifecycle/validate$", path).group(1), data)
                elif re.match(r"^/api/projects/([^/]+)/lifecycle/transitions$", path):
                    self.transition_project_lifecycle(conn, re.match(r"^/api/projects/([^/]+)/lifecycle/transitions$", path).group(1), data)
                elif re.match(r"^/api/projects/([^/]+)/start-audit$", path):
                    self.start_project_audit(conn, re.match(r"^/api/projects/([^/]+)/start-audit$", path).group(1), data)
                elif re.match(r"^/api/projects/([^/]+)/settlements$", path):
                    data["projectId"] = re.match(r"^/api/projects/([^/]+)/settlements$", path).group(1)
                    self.upsert_project_settlement(conn, data)
                elif re.match(r"^/api/projects/([^/]+)/variations$", path):
                    data["projectId"] = re.match(r"^/api/projects/([^/]+)/variations$", path).group(1)
                    self.upsert_project_variation(conn, data)
                elif path == "/api/audit/projects":
                    self.respond(400, {
                        "success": False,
                        "error": "请先在项目管理中建立项目主档案，再从项目详情发起审计，避免重复建档。",
                    })
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
                project_match = re.match(r"^/api/projects/([^/]+)$", path)
                if project_match:
                    self.update_project_record(conn, project_match.group(1), data)
                elif re.match(r"^/api/project-document-categories/([^/]+)$", path):
                    self.update_project_document_category(conn, re.match(r"^/api/project-document-categories/([^/]+)$", path).group(1), data)
                elif re.match(r"^/api/project-files/([^/]+)$", path):
                    self.rename_project_file(conn, re.match(r"^/api/project-files/([^/]+)$", path).group(1), data)
                elif re.match(r"^/api/project-settlements/([^/]+)$", path):
                    self.upsert_project_settlement(conn, data, re.match(r"^/api/project-settlements/([^/]+)$", path).group(1))
                elif re.match(r"^/api/project-variations/([^/]+)$", path):
                    self.upsert_project_variation(conn, data, re.match(r"^/api/project-variations/([^/]+)$", path).group(1))
                elif match:
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
                if re.match(r"^/api/projects/([^/]+)$", path):
                    self.delete_project_record(conn, re.match(r"^/api/projects/([^/]+)$", path).group(1))
                elif re.match(r"^/api/admin/users/([^/]+)$", path):
                    self.delete_user(conn, re.match(r"^/api/admin/users/([^/]+)$", path).group(1))
                elif re.match(r"^/api/project-files/([^/]+)$", path):
                    self.delete_project_file(conn, re.match(r"^/api/project-files/([^/]+)$", path).group(1))
                elif path.startswith("/api/audit/admin/field-configs/"):
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
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM audit_projects WHERE id = ?", (pid,)).fetchone()
        if not row:
            self.not_found()
            return
        stage = data.get("stage") or data.get("stageCode")
        if not stage:
            self.respond(400, {"success": False, "error": "stageCode 不能为空"})
            return
        stage_codes = [code for code, _title, _color in STAGES]
        current_stage = row["current_stage"] or "submitted"
        if stage == current_stage:
            self.respond(200, {"success": True, "data": project_payload(conn, row)})
            return
        expected_stage = None
        if current_stage in stage_codes:
            current_index = stage_codes.index(current_stage)
            if current_index + 1 < len(stage_codes):
                expected_stage = stage_codes[current_index + 1]
        if stage not in stage_codes or stage != expected_stage:
            self.respond(422, {
                "success": False,
                "error": "审计阶段只能按既定顺序逐步推进",
                "code": "audit_stage_transition_required",
                "currentStage": current_stage,
                "expectedStage": expected_stage,
            })
            return
        project_id = (row["project_id"] or "").strip()
        project = conn.execute(
            "SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
            (project_id,),
        ).fetchone() if project_id else None
        audit_to_project_stage = {
            "submitted": "pending_submission",
            "first_audit": "first_audit",
            "second_audit": "second_audit",
            "conclusion": "conclusion",
            "archived": "archived",
        }
        current_project_stage = audit_to_project_stage.get(current_stage)
        target_project_stage = audit_to_project_stage.get(stage)
        if not project or project["project_status"] != current_project_stage:
            self.respond(409, {
                "success": False,
                "error": "审计阶段与项目生命周期不一致，请刷新项目状态后重试",
                "code": "audit_project_lifecycle_conflict",
            })
            return
        blockers = self.lifecycle_transition_blockers(conn, project, target_project_stage, from_audit_progress=True)
        if blockers:
            self.respond(422, {
                "success": False,
                "error": "项目暂不满足审计阶段推进条件",
                "code": "audit_stage_blocked",
                "blockers": blockers,
            })
            return
        ts = now_iso()
        stage_name = dict((c, t) for c, t, _ in STAGES).get(stage, stage)
        conn.execute("UPDATE audit_project_stages SET finished_at = ?, status = 'done' WHERE project_id = ? AND status = 'active'", (ts, pid))
        conn.execute("UPDATE audit_projects SET current_stage = ?, is_archived = ?, updated_at = ? WHERE id = ?", (stage, 1 if stage == "archived" else 0, ts, pid))
        new_lifecycle_version = int(project["lifecycle_version"] or 0) + 1
        actor_name = (user["display_name"] or user["username"] or "").strip() if user else ""
        conn.execute(
            """
            UPDATE project_records
            SET project_status = ?, audit_stage = ?, lifecycle_version = ?, updated_at = ?, updated_by = ?
            WHERE id = ?
            """,
            (target_project_stage, stage, new_lifecycle_version, ts, user["username"] if user else "", project_id),
        )
        conn.execute(
            """
            INSERT INTO project_lifecycle_events
            (id, project_id, from_stage, to_stage, transition_type, reason,
             idempotency_key, lifecycle_version, actor_id, actor_name, payload_json, created_at)
            VALUES (?, ?, ?, ?, 'forward', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id(), project_id, current_project_stage, target_project_stage,
                data.get("note", f"审计流转至{stage}"),
                f"audit-progress:{pid}:{stage}:{new_lifecycle_version}",
                new_lifecycle_version,
                user["id"] if user else "",
                actor_name,
                json.dumps({"source": "audit_progress", "auditProjectId": pid}, ensure_ascii=False),
                ts,
            ),
        )
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
             table_width, sort_order, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
             entity_type = excluded.entity_type, field_key = excluded.field_key, field_label = excluded.field_label,
             field_type = excluded.field_type, option_group = excluded.option_group, bind_field = excluded.bind_field,
             required = excluded.required, visible_in_card = excluded.visible_in_card, visible_in_table = excluded.visible_in_table,
             visible_in_detail = excluded.visible_in_detail, visible_in_form = excluded.visible_in_form,
             visible_in_gantt = excluded.visible_in_gantt, table_width = excluded.table_width, sort_order = excluded.sort_order,
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
                int(data.get("tableWidth") or 140),
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
    global RECOGNITION_WORKER
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("AUDIT_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AUDIT_API_PORT", "3008")))
    args = parser.parse_args()
    bootstrap()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    RECOGNITION_WORKER = RecognitionWorker(
        connection_factory=connect,
        adapter_resolver=lambda _adapter_key: build_recognition_adapter(),
        storage_root=upload_root(),
    )
    RECOGNITION_WORKER.start()
    print(f"Audit Kanban API listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        RECOGNITION_WORKER.stop()
        server.server_close()


if __name__ == "__main__":
    main()
