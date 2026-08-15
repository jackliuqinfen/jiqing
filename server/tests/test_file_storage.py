import unittest

from server.file_storage import TencentCosFileStorage


class _HeadObjectClient:
    def head_object(self, **kwargs):
        return {
            "Content-length": "2582841",
            "Content-type": "application/pdf",
        }


class TencentCosFileStorageTests(unittest.TestCase):
    def test_size_reads_tencent_cos_hyphenated_content_length(self):
        storage = object.__new__(TencentCosFileStorage)
        storage.client = _HeadObjectClient()
        storage.bucket = "bucket"
        storage._key = lambda relative_path: relative_path

        self.assertEqual(storage.size("documents/contract.pdf"), 2582841)


if __name__ == "__main__":
    unittest.main()
