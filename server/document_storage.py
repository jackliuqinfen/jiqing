"""Protected, atomic filesystem storage for lifecycle documents."""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path


class UnsafeDocumentPathError(ValueError):
    pass


@dataclass(frozen=True)
class StoredDocument:
    relative_path: str
    sha256: str
    size: int


class DocumentStorage:
    def __init__(self, root, *, resolve_version_path):
        self.root = Path(root).resolve()
        self.resolve_version_path = resolve_version_path

    def save_original(
        self, *, document_id, version_no, original_name, source
    ) -> StoredDocument:
        safe_document_id = _safe_segment(document_id)
        safe_name = _safe_filename(original_name)
        relative_path = (
            Path("documents")
            / safe_document_id
            / f"v{int(version_no)}"
            / "original"
            / safe_name
        )
        return self._atomic_stream_write(relative_path, source)

    def save_page(
        self, *, document_id, version_no, page_number, content
    ) -> StoredDocument:
        safe_document_id = _safe_segment(document_id)
        relative_path = (
            Path("documents")
            / safe_document_id
            / f"v{int(version_no)}"
            / "pages"
            / f"page-{int(page_number):04d}.png"
        )
        return self._atomic_stream_write(relative_path, _BytesReader(content))

    def open_original(self, document_version_id):
        relative_path = self.resolve_version_path(document_version_id)
        if not relative_path:
            raise PermissionError("document version is not authorized")
        return self._resolve(relative_path).open("rb")

    def discard(self, relative_path):
        """Remove an uncommitted upload after validation failure or idempotent replay."""
        path = self._resolve(relative_path)
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent != self.root and parent.name not in {"documents", "uploads"}:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def _atomic_stream_write(self, relative_path, source):
        final_path = self._resolve(relative_path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists():
            raise FileExistsError(f"immutable document path already exists: {relative_path}")
        partial_path = final_path.with_name(f".{final_path.name}.{uuid.uuid4().hex}.part")
        digest = hashlib.sha256()
        size = 0
        published = False
        try:
            with partial_path.open("xb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                target.flush()
                os.fsync(target.fileno())
            os.link(partial_path, final_path)
            published = True
            partial_path.unlink()
            _fsync_directory(final_path.parent)
        except Exception:
            partial_path.unlink(missing_ok=True)
            if published:
                final_path.unlink(missing_ok=True)
            raise
        return StoredDocument(
            relative_path=relative_path.as_posix(),
            sha256=digest.hexdigest(),
            size=size,
        )

    def _resolve(self, relative_path):
        relative = Path(str(relative_path).replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts:
            raise UnsafeDocumentPathError("document path escapes storage root")
        resolved = (self.root / relative).resolve()
        if os.path.commonpath((str(self.root), str(resolved))) != str(self.root):
            raise UnsafeDocumentPathError("document path escapes storage root")
        return resolved


class _BytesReader:
    def __init__(self, content):
        self.content = memoryview(content)
        self.offset = 0

    def read(self, size=-1):
        if self.offset >= len(self.content):
            return b""
        end = len(self.content) if size < 0 else min(self.offset + size, len(self.content))
        chunk = self.content[self.offset:end].tobytes()
        self.offset = end
        return chunk


def _safe_segment(value):
    text = str(value or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise UnsafeDocumentPathError("invalid document identifier")
    return text


def _fsync_directory(path):
    if os.name != "posix":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_filename(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not text or text in {".", ".."} or "/" in text or "\\" in text:
        raise UnsafeDocumentPathError("invalid document filename")
    safe = re.sub(r"[^\w.()（）\- ]+", "_", text, flags=re.UNICODE).strip(" .")
    if not safe:
        raise UnsafeDocumentPathError("invalid document filename")
    return safe[:180]
