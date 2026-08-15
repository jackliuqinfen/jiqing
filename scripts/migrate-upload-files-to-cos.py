#!/usr/bin/env python3
"""Upload existing application files to COS without deleting local copies."""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.file_storage import build_file_storage


def rows(conn):
    queries = (
        ("document_versions", "relative_path, mime_type, file_size, sha256", ""),
        ("document_pages", "relative_path, 'image/png' AS mime_type, 0 AS file_size, '' AS sha256", ""),
        ("project_files", "relative_path, mime_type, file_size, '' AS sha256", "WHERE COALESCE(is_deleted, 0) = 0"),
        ("audit_project_attachments", "relative_path, mime_type, file_size, '' AS sha256", "WHERE COALESCE(is_deleted, 0) = 0"),
    )
    seen = set()
    for table, fields, suffix in queries:
        for row in conn.execute(f"SELECT {fields} FROM {table} {suffix}"):
            relative_path = str(row["relative_path"] or "").replace("\\", "/")
            if relative_path and relative_path not in seen:
                seen.add(relative_path)
                yield row


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="perform uploads; default is preview only")
    parser.add_argument("--db", default=os.environ.get("AUDIT_DB_PATH", str(PROJECT_ROOT / "server" / "audit-kanban.sqlite3")))
    parser.add_argument("--upload-root", default=os.environ.get("UPLOAD_ROOT", str(PROJECT_ROOT / "server" / "uploads")))
    args = parser.parse_args()

    if (os.environ.get("STORAGE_BACKEND") or "").strip().lower() != "cos":
        raise SystemExit("请先设置 STORAGE_BACKEND=cos，并配置 COS_BUCKET/COS_REGION/COS_SECRET_ID/COS_SECRET_KEY。")

    storage = build_file_storage(args.upload_root)
    root = Path(args.upload_root).resolve()
    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row
        total = uploaded = missing = skipped = 0
        for row in rows(conn):
            total += 1
            relative_path = row["relative_path"].replace("\\", "/")
            source = (root / relative_path).resolve()
            if not source.is_file():
                print(f"MISSING {relative_path}")
                missing += 1
                continue
            local_sha = sha256(source)
            expected_sha = str(row["sha256"] or "")
            if expected_sha and expected_sha != local_sha:
                print(f"HASH_MISMATCH {relative_path} expected={expected_sha} actual={local_sha}")
                continue
            if storage.exists(relative_path):
                print(f"EXISTS {relative_path} size={source.stat().st_size}")
                skipped += 1
                continue
            print(f"UPLOAD {relative_path} size={source.stat().st_size}")
            if args.apply:
                with source.open("rb") as stream:
                    storage.save_stream(
                        relative_path,
                        stream,
                        content_type=row["mime_type"] or mimetypes.guess_type(source.name)[0] or "application/octet-stream",
                    )
                uploaded += 1
        mode = "APPLY" if args.apply else "DRY_RUN"
        print(f"MIGRATION_{mode} total={total} uploaded={uploaded} missing={missing} skipped={skipped}")


if __name__ == "__main__":
    main()
