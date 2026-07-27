from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


HASH_CHUNK_SIZE = 1024 * 1024


class InvalidSyncCursor(ValueError):
    pass


def project_record_ref(project_id):
    return f"project:{project_id}"


def audit_project_ref(audit_project_id):
    return f"audit:{audit_project_id}"


def effective_project_ref(canonical_project_id, audit_project_id):
    return (
        project_record_ref(canonical_project_id)
        if canonical_project_id
        else audit_project_ref(audit_project_id)
    )


def source_revision(source_type, row):
    if source_type == "project_file":
        return (
            f"{row['id']}:{row['version_no']}:{row['file_size']}:"
            f"{row['uploaded_at']}"
        )
    return (
        f"{row['id']}:{row['file_size']}:"
        f"{row['created_at'] or row['uploaded_at']}"
    )


def encode_cursor(item):
    payload = json.dumps(
        [item["uploadedAt"], item["sourceType"], item["sourceId"]],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(cursor):
    if not cursor:
        return None
    try:
        encoded = cursor.encode("ascii")
        encoded += b"=" * (-len(encoded) % 4)
        payload = base64.b64decode(encoded, altchars=b"-_", validate=True)
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeEncodeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidSyncCursor("Invalid desktop sync cursor") from exc
    if (
        not isinstance(value, list)
        or len(value) != 3
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise InvalidSyncCursor("Invalid desktop sync cursor")
    return tuple(value)


def list_sync_project_roots(conn, policy):
    roots = {}
    for item in _eligible_source_rows(conn, policy):
        project_ref = item["projectRef"]
        root = roots.setdefault(
            project_ref,
            {
                "projectRef": project_ref,
                "canonicalProjectId": item["canonicalProjectId"],
                "auditProjectId": item["auditProjectId"],
                "projectCode": item["projectCode"],
                "projectName": item["projectName"],
                "fileCount": 0,
            },
        )
        if not root["auditProjectId"] and item["auditProjectId"]:
            root["auditProjectId"] = item["auditProjectId"]
        root["fileCount"] += 1
    return sorted(
        roots.values(),
        key=lambda item: (item["projectName"], item["projectRef"]),
    )


def list_sync_manifest(
    conn,
    policy,
    project_refs,
    cursor,
    limit,
    path_resolver,
):
    cursor_key = decode_cursor(cursor)
    requested_refs = {
        str(project_ref).strip()
        for project_ref in project_refs or []
        if str(project_ref).strip()
    }
    page_limit = _clamp_limit(limit)
    rows = [
        item
        for item in _eligible_source_rows(conn, policy)
        if item["projectRef"] in requested_refs
    ]
    rows.sort(
        key=lambda item: (
            item["uploadedAt"],
            item["sourceType"],
            item["sourceId"],
        )
    )
    if cursor_key:
        rows = [
            item
            for item in rows
            if (
                item["uploadedAt"],
                item["sourceType"],
                item["sourceId"],
            )
            > cursor_key
        ]

    selected = rows[: page_limit + 1]
    has_more = len(selected) > page_limit
    selected = selected[:page_limit]
    items = [_manifest_item(conn, item, path_resolver) for item in selected]
    next_cursor = encode_cursor(items[-1]) if has_more and items else ""
    return {"items": items, "nextCursor": next_cursor}


def _eligible_source_rows(conn, policy):
    rows = [*_project_file_rows(conn), *_audit_attachment_rows(conn)]
    return [item for item in rows if _policy_allows_source(policy, item)]


def _project_file_rows(conn):
    rows = conn.execute(
        """
        SELECT
          f.*,
          p.project_code AS canonical_project_code,
          p.project_name AS canonical_project_name
        FROM project_files f
        JOIN project_records p ON p.id = f.project_id
        WHERE COALESCE(f.is_deleted, 0) = 0
          AND COALESCE(f.is_current, 0) = 1
          AND COALESCE(p.is_deleted, 0) = 0
        """
    ).fetchall()
    return [
        {
            "projectRef": project_record_ref(row["project_id"]),
            "canonicalProjectId": row["project_id"],
            "auditProjectId": None,
            "projectCode": row["canonical_project_code"] or "",
            "projectName": row["canonical_project_name"] or "",
            "sourceType": "project_file",
            "sourceId": row["id"],
            "sourceRevision": source_revision("project_file", row),
            "displayName": row["display_name"] or row["original_name"],
            "originalName": row["original_name"],
            "categoryKey": row["category_key"],
            "fileExt": _normalized_extension(
                row["file_ext"],
                row["original_name"],
            ),
            "mimeType": row["mime_type"] or "",
            "fileSize": int(row["file_size"] or 0),
            "relativePath": row["relative_path"],
            "uploadedAt": row["uploaded_at"] or "",
        }
        for row in rows
    ]


def _audit_attachment_rows(conn):
    rows = conn.execute(
        """
        SELECT
          a.*,
          audit.project_id AS canonical_project_id,
          audit.project_code AS audit_project_code,
          audit.project_name AS audit_project_name,
          canonical.project_code AS canonical_project_code,
          canonical.project_name AS canonical_project_name
        FROM audit_project_attachments a
        JOIN audit_projects audit ON audit.id = a.project_id
        LEFT JOIN project_records canonical
          ON canonical.id = NULLIF(audit.project_id, '')
         AND COALESCE(canonical.is_deleted, 0) = 0
        WHERE COALESCE(a.is_deleted, 0) = 0
          AND COALESCE(audit.status, 'active') != 'deleted'
        """
    ).fetchall()
    result = []
    for row in rows:
        canonical_project_id = row["canonical_project_id"] or None
        original_name = row["original_name"] or row["file_name"]
        result.append(
            {
                "projectRef": effective_project_ref(
                    canonical_project_id,
                    row["project_id"],
                ),
                "canonicalProjectId": canonical_project_id,
                "auditProjectId": row["project_id"],
                "projectCode": (
                    row["canonical_project_code"]
                    if canonical_project_id
                    else row["audit_project_code"]
                )
                or "",
                "projectName": (
                    row["canonical_project_name"]
                    if canonical_project_id
                    else row["audit_project_name"]
                )
                or "",
                "sourceType": "audit_attachment",
                "sourceId": row["id"],
                "sourceRevision": source_revision("audit_attachment", row),
                "displayName": original_name,
                "originalName": original_name,
                "categoryKey": "audit_attachment",
                "fileExt": _normalized_extension(row["file_ext"], original_name),
                "mimeType": row["mime_type"] or "",
                "fileSize": int(row["file_size"] or 0),
                "relativePath": row["relative_path"],
                "uploadedAt": row["created_at"] or row["uploaded_at"] or "",
            }
        )
    return result


def _policy_allows_source(policy, item):
    if (
        policy.get("projectSelectionMode") == "admin_assigned"
        and item["projectRef"] not in set(policy.get("allowedProjectRefs") or [])
    ):
        return False
    allowed_categories = set(policy.get("allowedCategoryKeys") or [])
    if allowed_categories and item["categoryKey"] not in allowed_categories:
        return False
    allowed_extensions = {
        str(value).lower()
        for value in policy.get("allowedExtensions") or []
    }
    if allowed_extensions and item["fileExt"] not in allowed_extensions:
        return False
    try:
        maximum_size = int(policy.get("maxFileSizeBytes") or 0)
    except (TypeError, ValueError):
        maximum_size = 0
    return not maximum_size or item["fileSize"] <= maximum_size


def _manifest_item(conn, item, path_resolver):
    availability = "missing"
    sha256 = ""
    download_path = None
    try:
        path = Path(path_resolver(item["relativePath"]))
        if path.is_file():
            availability = "available"
            sha256 = _cached_sha256(conn, item, path)
            download_path = (
                f"/api/project-files/{item['sourceId']}/download"
                if item["sourceType"] == "project_file"
                else f"/api/audit/attachments/{item['sourceId']}/download"
            )
    except (OSError, TypeError, ValueError):
        pass
    return {
        key: value
        for key, value in item.items()
        if key != "relativePath"
    } | {
        "availability": availability,
        "sha256": sha256,
        "downloadPath": download_path,
    }


def _cached_sha256(conn, item, path):
    cached = conn.execute(
        """
        SELECT sha256
        FROM desktop_sync_hash_cache
        WHERE source_type = ? AND source_id = ? AND revision_key = ?
        """,
        (
            item["sourceType"],
            item["sourceId"],
            item["sourceRevision"],
        ),
    ).fetchone()
    if cached:
        return cached["sha256"]

    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(HASH_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    value = digest.hexdigest()
    conn.execute(
        """
        INSERT INTO desktop_sync_hash_cache
        (source_type, source_id, revision_key, sha256, file_size, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_type, source_id, revision_key)
        DO UPDATE SET
          sha256 = excluded.sha256,
          file_size = excluded.file_size,
          updated_at = excluded.updated_at
        """,
        (
            item["sourceType"],
            item["sourceId"],
            item["sourceRevision"],
            value,
            item["fileSize"],
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        ),
    )
    return value


def _normalized_extension(file_ext, filename):
    value = str(file_ext or Path(filename or "").suffix).lower()
    if value and not value.startswith("."):
        value = f".{value}"
    return value


def _clamp_limit(limit):
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = 200
    return max(1, min(200, value))
