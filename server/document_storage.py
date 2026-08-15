"""Protected, atomic filesystem storage for lifecycle documents."""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
import uuid
from contextlib import contextmanager
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
    def __init__(self, root, *, resolve_version_path, file_storage=None):
        self.root = Path(root).resolve()
        self.resolve_version_path = resolve_version_path
        self.file_storage = file_storage

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
        if self.file_storage is not None:
            stored = self.file_storage.save_stream(relative_path, source)
            return StoredDocument(stored.relative_path, stored.sha256, stored.size)
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
        if self.file_storage is not None:
            stored = self.file_storage.save_bytes(relative_path, content, content_type="image/png")
            return StoredDocument(stored.relative_path, stored.sha256, stored.size)
        return self._atomic_stream_write(relative_path, _BytesReader(content))

    def open_original(self, document_version_id):
        relative_path = self.resolve_version_path(document_version_id)
        if not relative_path:
            raise PermissionError("document version is not authorized")
        return self._resolve(relative_path).open("rb")

    def discard(self, relative_path):
        """Remove an uncommitted upload after validation failure or idempotent replay."""
        if self.file_storage is not None:
            self.file_storage.delete(relative_path)
            return
        path = self._resolve(relative_path)
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent != self.root and parent.name not in {"documents", "uploads"}:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def move(self, source_path, destination_path):
        if self.file_storage is not None:
            self.file_storage.move(source_path, destination_path)
            return
        source = self._resolve(source_path)
        destination = self._resolve(destination_path)
        if not source.exists() and destination.exists():
            return
        if not source.is_file():
            raise FileNotFoundError(str(source_path))
        if destination.exists():
            raise FileExistsError(str(destination_path))
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)

    def exists(self, relative_path):
        if self.file_storage is not None:
            return self.file_storage.exists(relative_path)
        return self._resolve(relative_path).is_file()

    def size(self, relative_path):
        if self.file_storage is not None:
            return self.file_storage.size(relative_path)
        return self._resolve(relative_path).stat().st_size

    @contextmanager
    def open_stream(self, relative_path, *, start=0, end=None):
        if self.file_storage is not None:
            with self.file_storage.open_stream(relative_path, start=start, end=end) as source:
                yield source
            return
        with self._resolve(relative_path).open("rb") as source:
            source.seek(max(int(start), 0))
            remaining = None if end is None else max(int(end) - int(start) + 1, 0)
            yield _LimitedReader(source, remaining)

    @contextmanager
    def materialize(self, relative_path):
        if self.file_storage is not None:
            with self.file_storage.materialize(relative_path) as path:
                yield path
            return
        yield self._resolve(relative_path)

    def read_bytes(self, relative_path):
        if self.file_storage is not None:
            return self.file_storage.read_bytes(relative_path)
        return self._resolve(relative_path).read_bytes()

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


class _LimitedReader:
    def __init__(self, source, remaining):
        self.source = source
        self.remaining = remaining

    def read(self, size=-1):
        if self.remaining is not None:
            if self.remaining <= 0:
                return b""
            size = self.remaining if size < 0 else min(size, self.remaining)
        chunk = self.source.read(size)
        if self.remaining is not None:
            self.remaining -= len(chunk)
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
