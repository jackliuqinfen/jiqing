"""Authenticated HTTP boundary for document recognition and human review."""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from server import document_repository
from server.document_domain import DocumentType, allowed_document_types
from server.document_repository import (
    DocumentNotFoundError,
    RecognitionIdempotencyConflictError,
    ReviewImmutableError,
    add_document_pages,
    create_document_upload,
)
from server.document_rendering import render_document_pages
from server.document_review_service import (
    ReviewBlockedError,
    ReviewDecisionValidationError,
    ReviewProjectScopeError,
    ReviewVersionConflictError,
    confirm_review,
    review_detail,
    save_decisions,
)
from server.document_storage import DocumentStorage, UnsafeDocumentPathError
from server.recognition.schemas import schema_for_document_type, schema_for_version
from server.recognition_service import enqueue_recognition, recognition_job_snapshot


WRITE_ROLES = frozenset({"admin", "editor"})
MAX_MULTIPART_OVERHEAD = 64 * 1024
MAX_MULTIPART_FIELD_SIZE = 64 * 1024
MAX_JSON_BODY_SIZE = 2 * 1024 * 1024


class DocumentApiError(RuntimeError):
    def __init__(self, status, code, message, **details):
        super().__init__(message)
        self.status = int(status)
        self.code = str(code)
        self.message = str(message)
        self.details = details


class UploadTooLargeError(DocumentApiError):
    def __init__(self):
        super().__init__(413, "upload_too_large", "文件超过当前上传大小限制。")


class InvalidMultipartError(DocumentApiError):
    def __init__(self, message="上传内容不是有效的单文件 multipart 表单。"):
        super().__init__(422, "invalid_multipart_upload", message)


@dataclass(frozen=True)
class ParsedUpload:
    fields: dict[str, str]
    filename: str
    stored: object


class DocumentApi:
    _GET_ROUTES = (
        re.compile(r"^/api/documents/([^/]+)$"),
        re.compile(r"^/api/document-versions/([^/]+)/pages/([1-9][0-9]*)/image$"),
        re.compile(r"^/api/document-recognition-jobs/([^/]+)$"),
        re.compile(r"^/api/document-reviews/([^/]+)$"),
    )
    _POST_ROUTES = (
        re.compile(r"^/api/documents/uploads$"),
        re.compile(r"^/api/document-recognition-jobs$"),
        re.compile(r"^/api/document-recognition-jobs/([^/]+)/retry$"),
        re.compile(r"^/api/document-reviews/([^/]+)/decisions$"),
        re.compile(r"^/api/document-reviews/([^/]+)/confirm$"),
    )

    def __init__(
        self,
        *,
        conn,
        handler,
        actor,
        allowed_project_ids,
        storage_root,
        max_upload_size,
        read_json,
        filename_decoder,
        project_code_generator,
        recognition_adapter_key,
        read_repository=None,
    ):
        self.conn = conn
        self.handler = handler
        self.actor = {
            "id": str(actor.get("id") or ""),
            "name": str(actor.get("name") or ""),
            "role": str(actor.get("role") or ""),
        }
        self.allowed_project_ids = (
            None
            if allowed_project_ids is None
            else {str(item) for item in allowed_project_ids if item}
        )
        self.max_upload_size = int(max_upload_size)
        self.read_json = read_json
        self.filename_decoder = filename_decoder
        self.project_code_generator = project_code_generator
        self.recognition_adapter_key = str(recognition_adapter_key or "manual").strip() or "manual"
        self.read_repository = read_repository or _DocumentReadRepository(conn)
        self.storage = DocumentStorage(storage_root, resolve_version_path=lambda _version_id: None)

    @classmethod
    def is_route(cls, method, path):
        routes = cls._GET_ROUTES if method == "GET" else cls._POST_ROUTES if method == "POST" else ()
        return any(route.fullmatch(path) for route in routes)

    def dispatch(self, method, path):
        try:
            if method == "GET":
                return self._dispatch_get(path)
            if method == "POST":
                return self._dispatch_post(path)
            return False
        except DocumentApiError as exc:
            self._error(exc.status, exc.code, exc.message, **exc.details)
        except ReviewVersionConflictError as exc:
            self._error(
                409,
                "review_version_conflict",
                "复核内容已被更新，请刷新后重试。",
                expectedReviewVersion=exc.expected_version,
                currentReviewVersion=exc.current_version,
            )
        except ReviewBlockedError as exc:
            self._error(422, "review_confirmation_blocked", "当前复核仍有阻断项。", blockers=exc.blockers)
        except ReviewDecisionValidationError as exc:
            self._error(422, exc.code, str(exc), field=exc.field)
        except ReviewProjectScopeError:
            self._error(403, "project_scope_forbidden", "当前用户无权访问该项目。")
        except RecognitionIdempotencyConflictError:
            self._error(409, "recognition_idempotency_conflict", "识别幂等键已用于其他请求。")
        except ReviewImmutableError:
            self._error(409, "review_immutable", "已确认的复核记录不能修改。")
        except DocumentNotFoundError:
            self._error(404, "document_resource_not_found", "未找到相关文档记录。")
        except (UnsafeDocumentPathError, json.JSONDecodeError) as exc:
            self._error(422, "invalid_request", str(exc) or "请求内容无效。")
        except (TypeError, ValueError) as exc:
            self._error(422, "invalid_request", str(exc) or "请求内容无效。")
        except sqlite3.IntegrityError:
            self._error(409, "document_write_conflict", "数据已被其他操作更新，请刷新后重试。")
        except (sqlite3.OperationalError, TimeoutError, OSError):
            self._error(503, "document_service_temporarily_unavailable", "文档服务暂时不可用，请稍后重试。")
        return True

    def _dispatch_get(self, path):
        match = self._GET_ROUTES[0].fullmatch(path)
        if match:
            self._get_document(match.group(1))
            return True
        match = self._GET_ROUTES[1].fullmatch(path)
        if match:
            self._get_page_image(match.group(1), int(match.group(2)))
            return True
        match = self._GET_ROUTES[2].fullmatch(path)
        if match:
            self._get_recognition_job(match.group(1))
            return True
        match = self._GET_ROUTES[3].fullmatch(path)
        if match:
            self._get_review(match.group(1))
            return True
        return False

    def _dispatch_post(self, path):
        if self._POST_ROUTES[0].fullmatch(path):
            self._require_writer()
            self._upload_document()
            return True
        if self._POST_ROUTES[1].fullmatch(path):
            self._require_writer()
            self._create_recognition_job()
            return True
        match = self._POST_ROUTES[2].fullmatch(path)
        if match:
            self._require_writer()
            self._retry_recognition_job(match.group(1))
            return True
        match = self._POST_ROUTES[3].fullmatch(path)
        if match:
            self._require_writer()
            self._save_review_decisions(match.group(1))
            return True
        match = self._POST_ROUTES[4].fullmatch(path)
        if match:
            self._require_confirmer()
            self._confirm_review(match.group(1))
            return True
        return False

    def _require_writer(self):
        if self.actor["role"] not in WRITE_ROLES:
            raise DocumentApiError(403, "document_write_forbidden", "当前角色只有文档只读权限。")

    def _require_confirmer(self):
        if self.actor["role"] not in WRITE_ROLES:
            raise DocumentApiError(403, "document_confirm_forbidden", "当前角色无权确认生成正式业务事实。")

    def _read_json_body(self):
        try:
            content_length = int(self.handler.headers.get("Content-Length") or "0")
        except ValueError as exc:
            raise DocumentApiError(422, "invalid_content_length", "Content-Length 无效。") from exc
        if content_length < 0:
            raise DocumentApiError(422, "invalid_content_length", "Content-Length 无效。")
        if content_length > MAX_JSON_BODY_SIZE:
            raise DocumentApiError(413, "json_body_too_large", "请求数据过大，请减少单次提交内容。")
        return self.read_json(self.handler)

    def _upload_document(self):
        parser = _StreamingMultipartParser(
            self.handler,
            storage=self.storage,
            max_file_size=self.max_upload_size,
            filename_decoder=self.filename_decoder,
        )
        parsed = parser.parse()
        stored = parsed.stored
        keep_stored = False
        try:
            document_type = _required_text(parsed.fields, "documentType")
            lifecycle_stage = _required_text(parsed.fields, "lifecycleStage")
            if document_type not in {item.value for item in DocumentType}:
                raise DocumentApiError(422, "unsupported_document_type", "当前阶段不支持该文档类型。")
            if document_type != DocumentType.CONSTRUCTION_CONTRACT.value:
                raise DocumentApiError(
                    422,
                    "phase_one_contract_only",
                    "一期仅开放施工合同识别，其他阶段凭证将在后续版本开放。",
                )
            if document_type not in allowed_document_types(lifecycle_stage):
                raise DocumentApiError(422, "document_stage_mismatch", "文档类型与生命周期阶段不匹配。")

            project_id = _optional_text(parsed.fields, "projectId")
            candidate_project_id = _optional_text(parsed.fields, "candidateProjectId")
            document_id = _optional_text(parsed.fields, "documentId")
            self._require_project_access(project_id)
            self._require_project_access(candidate_project_id)
            self._require_existing_project(project_id)
            self._require_existing_project(candidate_project_id)
            if document_type == DocumentType.CONSTRUCTION_CONTRACT.value and (
                project_id or candidate_project_id
            ):
                raise DocumentApiError(
                    422,
                    "contract_project_association_forbidden",
                    "施工合同创建项目时不能预先关联已有项目。",
                )

            existing_document = None
            if document_id:
                existing_document = self.read_repository.document(document_id)
                if not existing_document:
                    raise DocumentApiError(404, "document_not_found", "未找到要追加版本的文档。")
                self._require_resource_access(existing_document)
                if existing_document["document_type"] != document_type:
                    raise DocumentApiError(422, "document_type_immutable", "新版本不能改变文档类型。")
                if existing_document["lifecycle_stage"] != lifecycle_stage:
                    raise DocumentApiError(422, "document_stage_immutable", "新版本不能改变生命周期阶段。")

            mime_type = _detect_mime_type(self.storage._resolve(stored.relative_path))
            if not mime_type:
                raise DocumentApiError(
                    422,
                    "unsupported_document_signature",
                    "仅支持签名有效的 PDF、PNG、JPEG、TIFF 或 WebP 文件。",
                )
            self.conn.execute("BEGIN IMMEDIATE")
            result = create_document_upload(
                self.conn,
                document_type=document_type,
                lifecycle_stage=lifecycle_stage,
                project_id=project_id,
                candidate_project_id=candidate_project_id,
                original_name=parsed.filename,
                mime_type=mime_type,
                file_size=stored.size,
                sha256=stored.sha256,
                relative_path=stored.relative_path,
                uploaded_by=self.actor["id"],
                document_id=document_id,
            )
            self.conn.commit()
            keep_stored = not bool(result["replayed"])
            if not keep_stored:
                self.storage.discard(stored.relative_path)
            self._success(200 if result["replayed"] else 201, _map_upload_result(result))
        except Exception:
            self.conn.rollback()
            if not keep_stored:
                self.storage.discard(stored.relative_path)
            raise

    def _get_document(self, document_id):
        row = self.read_repository.document(document_id)
        if not row:
            raise DocumentApiError(404, "document_not_found", "未找到文档。")
        self._require_resource_access(row)
        pages = self.read_repository.pages(row["version_id"])
        self._success(200, _map_document(row, pages))

    def _get_page_image(self, version_id, page_number):
        row = self.read_repository.page(version_id, page_number)
        if not row:
            raise DocumentApiError(404, "document_page_not_found", "未找到文档页。")
        self._require_resource_access(row)
        path = self.storage._resolve(row["relative_path"])
        if not path.is_file():
            raise DocumentApiError(404, "document_page_file_not_found", "文档页文件不存在。")
        self._respond_file_range(path, "image/png")

    def _create_recognition_job(self):
        data = self._read_json_body()
        version_id = _required_text(data, "documentVersionId")
        source = self.read_repository.version(version_id)
        if not source:
            raise DocumentApiError(404, "document_version_not_found", "未找到文档版本。")
        self._require_resource_access(source)
        if source["document_type"] != DocumentType.CONSTRUCTION_CONTRACT.value:
            raise DocumentApiError(
                422,
                "phase_one_contract_only",
                "一期仅开放施工合同识别，其他阶段凭证将在后续版本开放。",
            )
        adapter_key = self.recognition_adapter_key
        schema_version = str(data.get("schemaVersion") or schema_for_document_type(source["document_type"]).version).strip()
        idempotency_key = _required_text(data, "idempotencyKey")
        schema = schema_for_version(schema_version)
        if schema.document_type != source["document_type"]:
            raise DocumentApiError(422, "recognition_schema_mismatch", "识别模式与文档类型不匹配。")
        self._ensure_rendered_pages(source)
        existing = self.read_repository.job_by_idempotency_key(idempotency_key)
        job = enqueue_recognition(
            self.conn,
            document_version_id=version_id,
            adapter_key=adapter_key,
            schema_version=schema_version,
            idempotency_key=idempotency_key,
        )
        self.conn.commit()
        self._success(200 if existing else 201, _map_job(recognition_job_snapshot(self.conn, job["id"])))

    def _ensure_rendered_pages(self, source):
        version_id = source["id"]
        if self.read_repository.pages(version_id):
            return
        stored_paths = []
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            if self.read_repository.pages(version_id):
                self.conn.commit()
                return
            self.storage.root.mkdir(parents=True, exist_ok=True)
            source_path = self.storage._resolve(source["relative_path"])
            with tempfile.TemporaryDirectory(
                prefix=".document-render-",
                dir=self.storage.root,
            ) as output_dir:
                rendered = render_document_pages(source_path, output_dir, dpi=300)
                if not rendered:
                    raise DocumentApiError(
                        422,
                        "document_render_empty",
                        "文件未生成可识别页面，请检查文件后重试。",
                    )
                page_rows = []
                for page in rendered:
                    stored = self.storage.save_page(
                        document_id=source["document_id"],
                        version_no=source["version_no"],
                        page_number=page.page_number,
                        content=page.output_path.read_bytes(),
                    )
                    stored_paths.append(stored.relative_path)
                    page_rows.append({
                        "page_number": page.page_number,
                        "relative_path": stored.relative_path,
                        "width_px": page.width_px,
                        "height_px": page.height_px,
                        "dpi": page.dpi,
                        "rotation_degrees": page.rotation_degrees,
                        "quality_score": page.quality_score,
                        "preprocessing_version": "scan-first-300dpi-v1",
                    })
                add_document_pages(
                    self.conn,
                    document_version_id=version_id,
                    pages=page_rows,
                )
            self.conn.commit()
        except DocumentApiError:
            self.conn.rollback()
            for relative_path in stored_paths:
                self.storage.discard(relative_path)
            raise
        except Exception as exc:
            self.conn.rollback()
            for relative_path in stored_paths:
                self.storage.discard(relative_path)
            raise DocumentApiError(
                422,
                "document_render_failed",
                "文件无法生成识别页面，请确认文件未损坏后重试。",
            ) from exc

    def _get_recognition_job(self, job_id):
        source = self.read_repository.job_source(job_id)
        if not source:
            raise DocumentApiError(404, "recognition_job_not_found", "未找到识别任务。")
        self._require_resource_access(source)
        self._success(200, _map_job(recognition_job_snapshot(self.conn, job_id)))

    def _retry_recognition_job(self, job_id):
        source = self.read_repository.job_source(job_id)
        if not source:
            raise DocumentApiError(404, "recognition_job_not_found", "未找到识别任务。")
        self._require_resource_access(source)
        if source["status"] not in {"failed", "manual_required"}:
            raise DocumentApiError(422, "recognition_retry_not_allowed", "当前识别状态不能重试。")
        data = self._read_json_body()
        idempotency_key = _required_text(data, "idempotencyKey")
        existing = self.read_repository.job_by_idempotency_key(idempotency_key)
        job = enqueue_recognition(
            self.conn,
            document_version_id=source["document_version_id"],
            adapter_key=source["adapter_key"],
            schema_version=source["schema_version"],
            idempotency_key=idempotency_key,
            max_attempts=source["max_attempts"],
        )
        self.conn.commit()
        self._success(200 if existing else 201, _map_job(recognition_job_snapshot(self.conn, job["id"])))

    def _get_review(self, review_id):
        source = self._review_source(review_id)
        detail = review_detail(self.conn, review_id)
        pages = self.read_repository.pages(source["document_version_id"])
        self._success(200, _map_review(detail, pages, can_write=self.actor["role"] in WRITE_ROLES))

    def _save_review_decisions(self, review_id):
        self._review_source(review_id)
        data = self._read_json_body()
        result = save_decisions(
            self.conn,
            review_id=review_id,
            expected_review_version=_required_int(data, "expectedReviewVersion"),
            decisions=data.get("decisions") or [],
            actor=self.actor,
            bulk=bool(data.get("bulk")),
        )
        pages = self.read_repository.pages(self.read_repository.review_source(review_id)["document_version_id"])
        self._success(200, _map_review(result, pages, can_write=True))

    def _confirm_review(self, review_id):
        source = self._review_source(review_id)
        if source["document_type"] != DocumentType.CONSTRUCTION_CONTRACT.value:
            raise DocumentApiError(
                422,
                "phase_one_contract_only",
                "一期仅开放施工合同识别，其他阶段凭证将在后续版本开放。",
            )
        data = self._read_json_body()
        project_id = str(data.get("projectId") or source.get("project_id") or "").strip() or None
        self._require_project_access(project_id)
        self._require_existing_project(project_id)
        result = confirm_review(
            self.conn,
            review_id=review_id,
            expected_review_version=_required_int(data, "expectedReviewVersion"),
            idempotency_key=_required_text(data, "idempotencyKey"),
            actor=self.actor,
            allowed_project_ids=self._service_project_scope(project_id),
            form_template_version=_required_text(data, "formTemplateVersion"),
            project_id=project_id,
            project_code_generator=self.project_code_generator,
        )
        self._success(200 if result.get("replayed") else 201, _map_confirmation(result))

    def _review_source(self, review_id):
        source = self.read_repository.review_source(review_id)
        if not source:
            raise DocumentApiError(404, "document_review_not_found", "未找到复核记录。")
        self._require_resource_access(source)
        return source

    def _require_resource_access(self, resource):
        scoped_project_ids = []
        for key in (
            "project_id",
            "document_project_id",
            "candidate_project_id",
            "document_candidate_project_id",
        ):
            project_id = resource.get(key)
            if project_id:
                scoped_project_ids.append(str(project_id))
                self._require_project_access(project_id)
        if not scoped_project_ids and self.actor["role"] != "admin":
            creator_id = str(
                resource.get("created_by")
                or resource.get("document_created_by")
                or resource.get("uploaded_by")
                or ""
            )
            if not creator_id or creator_id != self.actor["id"]:
                raise DocumentApiError(403, "unbound_document_forbidden", "当前用户无权访问该未关联文档。")

    def _require_project_access(self, project_id):
        if project_id and self.allowed_project_ids is not None and str(project_id) not in self.allowed_project_ids:
            raise DocumentApiError(403, "project_scope_forbidden", "当前用户无权访问该项目。")

    def _require_existing_project(self, project_id):
        if project_id and not self.read_repository.project_exists(project_id):
            raise DocumentApiError(422, "project_not_found", "关联项目不存在。")

    def _service_project_scope(self, target_project_id):
        if self.allowed_project_ids is not None:
            return self.allowed_project_ids
        return {target_project_id} if target_project_id else set()

    def _respond_file_range(self, path, content_type):
        size = path.stat().st_size
        range_header = str(self.handler.headers.get("Range") or "").strip()
        start, end, status = 0, max(size - 1, 0), 200
        if range_header:
            parsed = _parse_range(range_header, size)
            if parsed is None:
                self.handler.send_response(416)
                self.handler.send_header("Content-Range", f"bytes */{size}")
                self.handler.send_header("Accept-Ranges", "bytes")
                self.handler.send_header("Content-Length", "0")
                self.handler.send_header("Connection", "close")
                self.handler.end_headers()
                self.handler.close_connection = True
                return
            start, end = parsed
            status = 206
        length = end - start + 1 if size else 0
        self.handler.send_response(status)
        self.handler.send_header("Content-Type", content_type)
        self.handler.send_header("Content-Length", str(length))
        self.handler.send_header("Accept-Ranges", "bytes")
        self.handler.send_header("X-Content-Type-Options", "nosniff")
        if status == 206:
            self.handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.handler.send_header("Connection", "close")
        self.handler.end_headers()
        with path.open("rb") as source:
            source.seek(start)
            remaining = length
            while remaining:
                chunk = source.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                self.handler.wfile.write(chunk)
                remaining -= len(chunk)
        self.handler.close_connection = True

    def _success(self, status, data):
        self.handler.respond(status, {"success": True, "data": data})

    def _error(self, status, code, message, **details):
        self.handler.respond(
            status,
            {"success": False, "code": code, "error": message, **details},
        )


class _DocumentReadRepository:
    """Read-only adapter kept behind the API boundary; write behavior stays in services."""

    def __init__(self, conn):
        self.conn = conn

    def document(self, document_id):
        return document_repository._fetch_one(
            self.conn,
            """
            SELECT d.*, dv.id AS version_id, dv.version_no, dv.original_name,
                   dv.mime_type, dv.file_size, dv.uploaded_by, dv.uploaded_at
            FROM documents d
            JOIN document_versions dv ON dv.id = d.current_version_id
            WHERE d.id = ?
            """,
            (document_id,),
        )

    def version(self, version_id):
        return document_repository._fetch_one(
            self.conn,
            """
            SELECT dv.*, d.document_type, d.lifecycle_stage, d.project_id,
                   d.candidate_project_id, d.status AS document_status
            FROM document_versions dv
            JOIN documents d ON d.id = dv.document_id
            WHERE dv.id = ?
            """,
            (version_id,),
        )

    def pages(self, version_id):
        return document_repository._fetch_all(
            self.conn,
            "SELECT * FROM document_pages WHERE document_version_id = ? ORDER BY page_number",
            (version_id,),
        )

    def page(self, version_id, page_number):
        return document_repository._fetch_one(
            self.conn,
            """
            SELECT dp.*, d.project_id, d.candidate_project_id,
                   d.created_by AS document_created_by
            FROM document_pages dp
            JOIN document_versions dv ON dv.id = dp.document_version_id
            JOIN documents d ON d.id = dv.document_id
            WHERE dp.document_version_id = ? AND dp.page_number = ?
            """,
            (version_id, int(page_number)),
        )

    def job_source(self, job_id):
        return document_repository._fetch_one(
            self.conn,
            """
            SELECT rj.*, d.project_id, d.candidate_project_id,
                   d.created_by AS document_created_by
            FROM recognition_jobs rj
            JOIN document_versions dv ON dv.id = rj.document_version_id
            JOIN documents d ON d.id = dv.document_id
            WHERE rj.id = ?
            """,
            (job_id,),
        )

    def job_by_idempotency_key(self, idempotency_key):
        return document_repository._fetch_one(
            self.conn,
            "SELECT * FROM recognition_jobs WHERE idempotency_key = ?",
            (idempotency_key,),
        )

    def review_source(self, review_id):
        return document_repository._fetch_one(
            self.conn,
            """
            SELECT dr.*, d.document_type,
                   d.project_id AS document_project_id,
                   d.candidate_project_id AS document_candidate_project_id,
                   d.created_by AS document_created_by
            FROM document_reviews dr
            JOIN documents d ON d.id = dr.document_id
            WHERE dr.id = ?
            """,
            (review_id,),
        )

    def project_exists(self, project_id):
        return bool(
            document_repository._fetch_one(
                self.conn, "SELECT id FROM project_records WHERE id = ?", (project_id,)
            )
        )


class _StreamingMultipartParser:
    def __init__(self, handler, *, storage, max_file_size, filename_decoder):
        self.handler = handler
        self.storage = storage
        self.max_file_size = int(max_file_size)
        self.filename_decoder = filename_decoder

    def parse(self):
        content_type = str(self.handler.headers.get("Content-Type") or "")
        match = re.search(r"boundary=(\"[^\"]+\"|[^;]+)", content_type, re.IGNORECASE)
        if "multipart/form-data" not in content_type.lower() or not match:
            raise InvalidMultipartError("请使用 multipart/form-data 上传单个文件。")
        boundary = match.group(1).strip().strip('"').encode("utf-8")
        if not boundary or len(boundary) > 200:
            raise InvalidMultipartError()
        try:
            content_length = int(self.handler.headers.get("Content-Length") or "0")
        except ValueError as exc:
            raise InvalidMultipartError("Content-Length 无效。") from exc
        if content_length <= 0:
            raise InvalidMultipartError("上传内容为空。")
        if content_length > self.max_file_size + MAX_MULTIPART_OVERHEAD:
            raise UploadTooLargeError()

        source = _LimitedInput(self.handler.rfile, content_length)
        if source.readline(4096).rstrip(b"\r\n") != b"--" + boundary:
            raise InvalidMultipartError()

        fields = {}
        stored = None
        filename = ""
        final_boundary = False
        try:
            while not final_boundary:
                headers = _read_part_headers(source)
                disposition = headers.get("content-disposition", "")
                name_match = re.search(r'name="([^"]+)"', disposition)
                if not name_match:
                    raise InvalidMultipartError("multipart 字段缺少名称。")
                field_name = name_match.group(1)
                part = _MultipartPartReader(source, boundary)
                part_filename = self.filename_decoder(disposition)
                if part_filename:
                    if field_name != "file" or stored is not None:
                        raise InvalidMultipartError("一次只能上传一个名为 file 的文件。")
                    part.max_size = self.max_file_size
                    stored = self.storage.save_original(
                        document_id=f"incoming-{uuid.uuid4().hex}",
                        version_no=1,
                        original_name=part_filename,
                        source=part,
                    )
                    filename = part_filename
                else:
                    part.max_size = MAX_MULTIPART_FIELD_SIZE
                    try:
                        fields[field_name] = _read_all(part).decode("utf-8").strip()
                    except UploadTooLargeError as exc:
                        raise InvalidMultipartError("multipart 文本字段过大。") from exc
                    except UnicodeDecodeError as exc:
                        raise InvalidMultipartError("multipart 文本字段编码无效。") from exc
                final_boundary = part.final_boundary
            if stored is None:
                raise InvalidMultipartError("未找到上传文件。")
            return ParsedUpload(fields=fields, filename=filename, stored=stored)
        except Exception:
            if stored is not None:
                self.storage.discard(stored.relative_path)
            raise


class _LimitedInput:
    def __init__(self, source, remaining):
        self.source = source
        self.remaining = int(remaining)
        self.pushback = bytearray()

    def unread(self, content):
        if content:
            self.pushback = bytearray(content) + self.pushback

    def read(self, size=-1):
        if size == 0:
            return b""
        target = self.remaining if size < 0 else min(int(size), self.remaining + len(self.pushback))
        result = bytearray()
        if self.pushback and target:
            take = min(target, len(self.pushback))
            result.extend(self.pushback[:take])
            del self.pushback[:take]
            target -= take
        if target and self.remaining:
            take = min(target, self.remaining)
            chunk = self.source.read(take)
            self.remaining -= len(chunk)
            result.extend(chunk)
        return bytes(result)

    def readline(self, limit=65536):
        result = bytearray()
        while len(result) < limit:
            byte = self.read(1)
            if not byte:
                break
            result.extend(byte)
            if byte == b"\n":
                break
        return bytes(result)


class _MultipartPartReader:
    def __init__(self, source, boundary):
        self.source = source
        self.marker = b"\r\n--" + boundary
        self.buffer = bytearray()
        self.ready = bytearray()
        self.finished = False
        self.final_boundary = False
        self.max_size = None
        self.returned = 0

    def read(self, size=-1):
        if size == 0:
            return b""
        target = 1024 * 1024 if size < 0 else int(size)
        while not self.ready and not self.finished:
            self._fill()
        if not self.ready:
            return b""
        take = min(target, len(self.ready))
        chunk = bytes(self.ready[:take])
        del self.ready[:take]
        if self.max_size is not None and self.returned + len(chunk) > self.max_size:
            raise UploadTooLargeError()
        self.returned += len(chunk)
        return chunk

    def _fill(self):
        chunk = self.source.read(64 * 1024)
        if chunk:
            self.buffer.extend(chunk)
        marker_index = self.buffer.find(self.marker)
        if marker_index >= 0:
            required = marker_index + len(self.marker) + 2
            while len(self.buffer) < required:
                more = self.source.read(required - len(self.buffer))
                if not more:
                    raise InvalidMultipartError("multipart 边界不完整。")
                self.buffer.extend(more)
            suffix_start = marker_index + len(self.marker)
            suffix = bytes(self.buffer[suffix_start:suffix_start + 2])
            if suffix not in {b"--", b"\r\n"}:
                raise InvalidMultipartError("multipart 边界无效。")
            self.ready.extend(self.buffer[:marker_index])
            consumed = suffix_start + 2
            self.final_boundary = suffix == b"--"
            if self.final_boundary and self.buffer[consumed:consumed + 2] == b"\r\n":
                consumed += 2
            self.source.unread(self.buffer[consumed:])
            self.buffer.clear()
            self.finished = True
            return
        if not chunk:
            raise InvalidMultipartError("multipart 缺少结束边界。")
        keep = len(self.marker) + 4
        if len(self.buffer) > keep:
            flush = len(self.buffer) - keep
            self.ready.extend(self.buffer[:flush])
            del self.buffer[:flush]


def _read_part_headers(source):
    headers = {}
    total = 0
    while True:
        line = source.readline(8192)
        total += len(line)
        if total > 32 * 1024 or not line:
            raise InvalidMultipartError("multipart 头部无效。")
        if line in {b"\r\n", b"\n"}:
            return headers
        try:
            name, value = line.decode("iso-8859-1").rstrip("\r\n").split(":", 1)
        except ValueError as exc:
            raise InvalidMultipartError("multipart 头部无效。") from exc
        headers[name.strip().lower()] = value.strip()


def _read_all(source):
    chunks = []
    while True:
        chunk = source.read(64 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _detect_mime_type(path):
    with Path(path).open("rb") as source:
        signature = source.read(16)
    if signature.startswith(b"%PDF-"):
        return "application/pdf"
    if signature.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if signature.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if signature.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")):
        return "image/tiff"
    if len(signature) >= 12 and signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _parse_range(value, size):
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if not match or size <= 0:
        return None
    start_text, end_text = match.groups()
    if not start_text and not end_text:
        return None
    if not start_text:
        suffix = int(end_text)
        if suffix <= 0:
            return None
        start = max(size - suffix, 0)
        return start, size - 1
    start = int(start_text)
    if start >= size:
        return None
    end = size - 1 if not end_text else min(int(end_text), size - 1)
    if end < start:
        return None
    return start, end


def _required_text(data, key):
    value = str((data or {}).get(key) or "").strip()
    if not value:
        raise DocumentApiError(422, "required_field_missing", f"{key} 不能为空。", field=key)
    return value


def _optional_text(data, key):
    return str((data or {}).get(key) or "").strip() or None


def _required_int(data, key):
    if key not in (data or {}):
        raise DocumentApiError(422, "required_field_missing", f"{key} 不能为空。", field=key)
    try:
        return int(data[key])
    except (TypeError, ValueError) as exc:
        raise DocumentApiError(422, "invalid_integer", f"{key} 必须是整数。", field=key) from exc


def _map_upload_result(result):
    return {
        "replayed": bool(result["replayed"]),
        "crossProjectDuplicateCount": int(result.get("cross_project_duplicate_count") or 0),
        "document": _map_document_row(result["document"]),
        "version": _map_version_row(result["version"]),
    }


def _map_document(row, pages):
    return {
        **_map_document_row(row),
        "currentVersion": {
            "id": row["version_id"],
            "number": int(row["version_no"]),
            "name": row["original_name"],
            "mimeType": row["mime_type"],
            "fileSize": int(row["file_size"]),
            "uploadedBy": row["uploaded_by"],
            "uploadedAt": row["uploaded_at"],
        },
        "pages": [_map_page(page) for page in pages],
    }


def _map_document_row(row):
    return {
        "id": row["id"],
        "type": row["document_type"],
        "lifecycleStage": row["lifecycle_stage"],
        "projectId": row.get("project_id"),
        "candidateProjectId": row.get("candidate_project_id"),
        "status": row["status"],
        "createdBy": row["created_by"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _map_version_row(row):
    return {
        "id": row["id"],
        "documentId": row["document_id"],
        "number": int(row["version_no"]),
        "name": row["original_name"],
        "mimeType": row["mime_type"],
        "fileSize": int(row["file_size"]),
        "uploadedBy": row["uploaded_by"],
        "uploadedAt": row["uploaded_at"],
    }


def _map_page(row):
    return {
        "id": row["id"],
        "pageNumber": int(row["page_number"]),
        "width": int(row["width_px"]),
        "height": int(row["height_px"]),
        "dpi": int(row["dpi"]),
        "rotationDegrees": int(row["rotation_degrees"]),
        "qualityScore": row.get("quality_score"),
        "imageUrl": f"/api/document-versions/{row['document_version_id']}/pages/{row['page_number']}/image",
    }


def _map_job(row):
    if not row:
        return None
    error = None
    if row.get("error_code") or row.get("error_message"):
        error = {"code": row.get("error_code") or "", "message": row.get("error_message") or ""}
    return {
        "id": row["id"],
        "documentVersionId": row["document_version_id"],
        "status": row["status"],
        "adapterKey": row["adapter_key"],
        "schemaVersion": row["schema_version"],
        "attempts": int(row["attempts"]),
        "maxAttempts": int(row["max_attempts"]),
        "blockCount": int(row.get("block_count") or 0),
        "fieldCount": int(row.get("field_count") or 0),
        "reviewId": row.get("review_id") or "",
        "reviewStatus": row.get("review_status") or "",
        "error": error,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "finishedAt": row.get("finished_at") or "",
    }


def _map_review(detail, pages, *, can_write):
    sections = {}
    for field in detail.get("fields") or []:
        section_key = str(field.get("semanticKey") or "other").split(".", 1)[0]
        sections.setdefault(section_key, []).append(field)
    candidate_id = detail.get("candidateProjectId")
    commands = list(detail.get("allowedCommands") or []) if can_write else []
    return {
        "id": detail["id"],
        "status": detail["status"],
        "reviewVersion": int(detail["reviewVersion"]),
        "projectId": detail.get("projectId"),
        "projectCandidates": ([{"projectId": candidate_id, "recommended": True}] if candidate_id else []),
        "reviewer": detail.get("reviewer") or {"id": "", "name": ""},
        "document": detail["document"],
        "pages": [_map_page(page) for page in pages],
        "sections": [
            {"key": key, "fields": fields}
            for key, fields in sorted(sections.items())
        ],
        "blockers": detail.get("blockers") or [],
        "warnings": detail.get("warnings") or [],
        "allowedCommands": commands,
    }


def _map_confirmation(result):
    snapshot = result.get("snapshot") or {}
    fact = result.get("contract") or result.get("acceptance") or result.get("determination") or {}
    fact_type = "contract" if result.get("contract") else "acceptance" if result.get("acceptance") else "determination" if result.get("determination") else ""
    return {
        "status": result.get("status") or "created",
        "replayed": bool(result.get("replayed")),
        "projectId": result.get("projectId"),
        "snapshotId": snapshot.get("id"),
        "fact": {"type": fact_type, "id": fact.get("id")} if fact else None,
    }
