import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.document_storage import DocumentStorage, UnsafeDocumentPathError


class BrokenStream(io.BytesIO):
    def read(self, size=-1):
        if self.tell() > 0:
            raise OSError("interrupted")
        return super().read(4 if size < 0 else min(size, 4))


class DocumentStorageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.authorized = {}
        self.storage = DocumentStorage(
            self.root,
            resolve_version_path=lambda version_id: self.authorized.get(version_id),
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_original_is_atomic_hashed_and_read_by_authorized_version(self):
        first = self.storage.save_original(
            document_id="doc-1",
            version_no=1,
            original_name="合同 扫描件.pdf",
            source=io.BytesIO(b"same-content"),
        )
        second = self.storage.save_original(
            document_id="doc-2",
            version_no=1,
            original_name="contract.pdf",
            source=io.BytesIO(b"same-content"),
        )
        self.authorized["version-1"] = first.relative_path

        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.size, len(b"same-content"))
        self.assertFalse(Path(first.relative_path).is_absolute())
        with self.storage.open_original("version-1") as source:
            self.assertEqual(source.read(), b"same-content")
        with self.assertRaises(PermissionError):
            self.storage.open_original("unknown-version")

    def test_path_traversal_is_rejected(self):
        for filename in ("../secret.pdf", "..\\secret.pdf", "/tmp/secret.pdf"):
            with self.subTest(filename=filename):
                with self.assertRaises(UnsafeDocumentPathError):
                    self.storage.save_original(
                        document_id="doc-1",
                        version_no=1,
                        original_name=filename,
                        source=io.BytesIO(b"content"),
                    )

    def test_interrupted_write_leaves_no_final_or_partial_file(self):
        with self.assertRaises(OSError):
            self.storage.save_original(
                document_id="doc-1",
                version_no=1,
                original_name="contract.pdf",
                source=BrokenStream(b"longer-content"),
            )

        files = [path for path in self.root.rglob("*") if path.is_file()]
        self.assertEqual(files, [])

    def test_existing_immutable_version_is_never_overwritten_or_deleted(self):
        saved = self.storage.save_original(
            document_id="doc-1",
            version_no=1,
            original_name="contract.pdf",
            source=io.BytesIO(b"original"),
        )

        with self.assertRaises(FileExistsError):
            self.storage.save_original(
                document_id="doc-1",
                version_no=1,
                original_name="contract.pdf",
                source=io.BytesIO(b"replacement"),
            )

        self.authorized["version-1"] = saved.relative_path
        with self.storage.open_original("version-1") as source:
            self.assertEqual(source.read(), b"original")

    def test_successful_write_fsyncs_the_final_parent_directory(self):
        with patch("server.document_storage._fsync_directory") as fsync_directory:
            saved = self.storage.save_original(
                document_id="doc-1",
                version_no=1,
                original_name="contract.pdf",
                source=io.BytesIO(b"content"),
            )

        fsync_directory.assert_called_once_with(
            self.root / Path(saved.relative_path).parent
        )

    def test_failure_after_publish_removes_final_and_partial_files(self):
        with patch(
            "server.document_storage._fsync_directory",
            side_effect=OSError("directory sync failed"),
        ):
            with self.assertRaises(OSError):
                self.storage.save_original(
                    document_id="doc-1",
                    version_no=1,
                    original_name="contract.pdf",
                    source=io.BytesIO(b"content"),
                )

        files = [path for path in self.root.rglob("*") if path.is_file()]
        self.assertEqual(files, [])

    def test_page_path_is_stable_and_zero_padded(self):
        saved = self.storage.save_page(
            document_id="doc-1",
            version_no=2,
            page_number=7,
            content=b"png-data",
        )
        self.assertEqual(
            saved.relative_path,
            "documents/doc-1/v2/pages/page-0007.png",
        )


if __name__ == "__main__":
    unittest.main()
