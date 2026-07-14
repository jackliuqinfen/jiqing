import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from server.document_rendering import render_document_pages


class DocumentRenderingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_two_page_scanned_pdf_renders_in_order_at_300_dpi(self):
        pdf_path = self.root / "scanned.pdf"
        first = Image.new("RGB", (600, 800), "white")
        second = Image.new("RGB", (600, 800), "white")
        ImageDraw.Draw(first).text((40, 40), "CONTRACT PAGE 1", fill="black")
        ImageDraw.Draw(second).text((40, 40), "CONTRACT PAGE 2", fill="black")
        first.save(pdf_path, "PDF", save_all=True, append_images=[second], resolution=150)

        results = render_document_pages(pdf_path, self.root / "pages", dpi=300)

        self.assertEqual([result.page_number for result in results], [1, 2])
        self.assertTrue(all(result.dpi == 300 for result in results))
        self.assertTrue(all(result.width_px > 0 and result.height_px > 0 for result in results))
        self.assertTrue(all(result.rotation_degrees == 0 for result in results))
        self.assertTrue(all(result.output_path.exists() for result in results))
        self.assertTrue(all(0 <= result.quality_score <= 1 for result in results))

    def test_blank_scan_is_preserved_and_flagged_low_quality(self):
        source_path = self.root / "blank.png"
        Image.new("RGB", (2481, 3507), "white").save(source_path)

        results = render_document_pages(source_path, self.root / "blank-pages", dpi=300)

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].output_path.exists())
        self.assertLess(results[0].quality_score, 0.35)
        self.assertTrue(results[0].manual_review_required)


if __name__ == "__main__":
    unittest.main()
