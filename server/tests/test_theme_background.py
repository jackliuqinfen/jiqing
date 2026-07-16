import base64
import unittest

from server import audit_api


class WorkspaceBackgroundValidationTests(unittest.TestCase):
    def data_url(self, mime_type, content):
        payload = base64.b64encode(content).decode("ascii")
        return f"data:{mime_type};base64,{payload}"

    def test_accepts_supported_image_signatures(self):
        samples = [
            ("image/png", b"\x89PNG\r\n\x1a\ncontent"),
            ("image/jpeg", b"\xff\xd8\xffcontent"),
            ("image/webp", b"RIFF\x08\x00\x00\x00WEBPcontent"),
        ]

        for mime_type, content in samples:
            with self.subTest(mime_type=mime_type):
                value = self.data_url(mime_type, content)
                self.assertEqual(audit_api.normalize_workspace_background_image(value), value)

    def test_empty_value_restores_bundled_default(self):
        self.assertEqual(audit_api.normalize_workspace_background_image(""), "")

    def test_rejects_unsupported_or_forged_images(self):
        with self.assertRaisesRegex(ValueError, "PNG、JPG 或 WebP"):
            audit_api.normalize_workspace_background_image(self.data_url("image/gif", b"GIF89a"))

        with self.assertRaisesRegex(ValueError, "文件内容"):
            audit_api.normalize_workspace_background_image(self.data_url("image/png", b"not-a-png"))

    def test_rejects_images_larger_than_two_megabytes(self):
        oversized = self.data_url("image/png", b"\x89PNG\r\n\x1a\n" + b"x" * (2 * 1024 * 1024))
        with self.assertRaisesRegex(ValueError, "2 MB"):
            audit_api.normalize_workspace_background_image(oversized)


if __name__ == "__main__":
    unittest.main()
