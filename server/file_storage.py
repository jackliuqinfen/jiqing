"""Local and Tencent COS backed file storage.

The application stores object keys in existing database columns named
``relative_path``.  Keeping that value stable lets us migrate old local files
without changing business records.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


class StorageConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    sha256: str
    size: int


def _safe_relative_path(value):
    relative = Path(str(value or "").replace("\\", "/"))
    if (
        not str(value).strip()
        or relative.is_absolute()
        or ".." in relative.parts
        or any("\x00" in part for part in relative.parts)
    ):
        raise ValueError("非法文件存储路径")
    return relative.as_posix()


class LocalFileStorage:
    backend_name = "local"

    def __init__(self, root):
        self.root = Path(root).resolve()

    def save_stream(self, relative_path, source, *, content_type=""):
        relative = _safe_relative_path(relative_path)
        target = self._resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"文件已存在: {relative}")
        partial = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
        digest = hashlib.sha256()
        size = 0
        published = False
        try:
            with partial.open("xb") as output:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.link(partial, target)
            published = True
            partial.unlink()
            return StoredFile(relative, digest.hexdigest(), size)
        except Exception:
            partial.unlink(missing_ok=True)
            if published:
                target.unlink(missing_ok=True)
            raise

    def save_bytes(self, relative_path, content, *, content_type=""):
        return self.save_stream(relative_path, _BytesReader(content), content_type=content_type)

    def exists(self, relative_path):
        return self._resolve(relative_path).is_file()

    def presigned_download_url(self, relative_path, *, expires=300):
        return None

    def size(self, relative_path):
        return self._resolve(relative_path).stat().st_size

    def delete(self, relative_path):
        self._resolve(relative_path).unlink(missing_ok=True)

    def move(self, source_path, destination_path):
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

    def resolve(self, relative_path):
        return self._resolve(relative_path)

    @contextlib.contextmanager
    def open_stream(self, relative_path, *, start=0, end=None):
        path = self._resolve(relative_path)
        with path.open("rb") as source:
            source.seek(max(int(start), 0))
            remaining = None if end is None else max(int(end) - int(start) + 1, 0)
            yield _LimitedReader(source, remaining)

    @contextlib.contextmanager
    def materialize(self, relative_path):
        yield self._resolve(relative_path)

    def read_bytes(self, relative_path):
        return self._resolve(relative_path).read_bytes()

    def _resolve(self, relative_path):
        relative = Path(_safe_relative_path(relative_path))
        resolved = (self.root / relative).resolve()
        if os.path.commonpath((str(self.root), str(resolved))) != str(self.root):
            raise ValueError("文件路径越界")
        return resolved


class TencentCosFileStorage:
    backend_name = "cos"

    def __init__(self, root, *, secret_id, secret_key, region, bucket, prefix=""):
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError as exc:
            raise StorageConfigurationError(
                "COS 存储已启用，但运行环境缺少 cos-python-sdk-v5。"
            ) from exc
        if not all((secret_id, secret_key, region, bucket)):
            raise StorageConfigurationError(
                "COS 存储配置不完整，请设置 COS_SECRET_ID、COS_SECRET_KEY、COS_REGION 和 COS_BUCKET。"
            )
        self.root = Path(root).resolve()
        self.prefix = str(prefix or "").strip("/")
        self.bucket = str(bucket).strip()
        config = CosConfig(Region=str(region).strip(), SecretId=secret_id, SecretKey=secret_key)
        self.client = CosS3Client(config)

    def save_stream(self, relative_path, source, *, content_type=""):
        relative = _safe_relative_path(relative_path)
        key = self._key(relative)
        if self.exists(relative):
            raise FileExistsError(f"COS 对象已存在: {relative}")
        with tempfile.TemporaryFile(mode="w+b") as buffered:
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                buffered.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            buffered.seek(0)
            kwargs = {"Bucket": self.bucket, "Key": key, "Body": buffered}
            if content_type:
                kwargs["ContentType"] = content_type
            self.client.put_object(**kwargs)
        return StoredFile(relative, digest.hexdigest(), size)

    def save_bytes(self, relative_path, content, *, content_type=""):
        return self.save_stream(relative_path, _BytesReader(content), content_type=content_type)

    def exists(self, relative_path):
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(relative_path))
            return True
        except Exception as exc:
            if _is_cos_not_found(exc):
                return False
            raise

    def presigned_download_url(self, relative_path, *, expires=300):
        return self.client.get_presigned_download_url(
            Bucket=self.bucket,
            Key=self._key(relative_path),
            Expired=max(60, min(int(expires), 900)),
        )

    def size(self, relative_path):
        response = self.client.head_object(Bucket=self.bucket, Key=self._key(relative_path))
        return int(response.get("ContentLength") or 0)

    def delete(self, relative_path):
        self.client.delete_object(Bucket=self.bucket, Key=self._key(relative_path))

    def move(self, source_path, destination_path):
        if not self.exists(source_path) and self.exists(destination_path):
            return
        if self.exists(destination_path):
            raise FileExistsError(str(destination_path))
        with self.open_stream(source_path) as source:
            self.save_stream(destination_path, source)
        self.delete(source_path)

    def resolve(self, relative_path):
        """Return a safe local staging path for compatibility checks only."""
        relative = Path(_safe_relative_path(relative_path))
        resolved = (self.root / relative).resolve()
        if os.path.commonpath((str(self.root), str(resolved))) != str(self.root):
            raise ValueError("文件路径越界")
        return resolved

    @contextlib.contextmanager
    def open_stream(self, relative_path, *, start=0, end=None):
        kwargs = {"Bucket": self.bucket, "Key": self._key(relative_path)}
        if end is not None:
            kwargs["Range"] = f"bytes={int(start)}-{int(end)}"
        elif int(start or 0):
            kwargs["Range"] = f"bytes={int(start)}-"
        response = self.client.get_object(**kwargs)
        body = response["Body"]
        stream = body.get_raw_stream() if hasattr(body, "get_raw_stream") else body
        try:
            yield stream
        finally:
            close = getattr(body, "close", None) or getattr(stream, "close", None)
            if close:
                close()

    @contextlib.contextmanager
    def materialize(self, relative_path):
        target = self.resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with self.open_stream(relative_path) as source, temporary.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            yield temporary
        finally:
            temporary.unlink(missing_ok=True)

    def read_bytes(self, relative_path):
        with self.open_stream(relative_path) as source:
            return source.read()

    def _key(self, relative_path):
        relative = _safe_relative_path(relative_path)
        parts = relative.split("/")
        if parts and parts[0] == "project-records" and len(parts) >= 3:
            relative = "/".join(("projects", parts[1], "项目资料", *parts[2:]))
        elif parts and parts[0] == "audit-projects" and len(parts) >= 3:
            relative = "/".join(("projects", parts[1], "审计附件", *parts[2:]))
        elif parts and parts[0] == "contract-records" and len(parts) >= 3:
            relative = "/".join(("projects", parts[1], "合同文档", *parts[2:]))
        elif parts and parts[0] == "documents":
            relative = "/".join(("projects", "待关联项目", "合同文档", *parts[1:]))
        return f"{self.prefix}/{relative}" if self.prefix else relative


def build_file_storage(root):
    backend = (os.environ.get("STORAGE_BACKEND") or "local").strip().lower()
    if backend in {"", "local", "filesystem"}:
        return LocalFileStorage(root)
    if backend != "cos":
        raise StorageConfigurationError(f"不支持的文件存储后端: {backend}")
    return TencentCosFileStorage(
        root,
        secret_id=os.environ.get("COS_SECRET_ID", ""),
        secret_key=os.environ.get("COS_SECRET_KEY", ""),
        region=os.environ.get("COS_REGION", "ap-shanghai"),
        bucket=os.environ.get("COS_BUCKET", ""),
        prefix=os.environ.get("COS_PREFIX", "prod"),
    )


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


def _is_cos_not_found(exc):
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    code = str(getattr(exc, "error_code", "") or getattr(exc, "code", ""))
    message = str(exc)
    return str(status) == "404" or code in {
        "NoSuchKey",
        "NoSuchObject",
        "NoSuchBucket",
        "NoSuchResource",
    } or any(marker in message for marker in ("NoSuchKey", "NoSuchObject", "NoSuchBucket", "NoSuchResource"))
