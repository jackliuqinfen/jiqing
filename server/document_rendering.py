"""Scan-first PDF and image page rendering for OCR input."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageFilter, ImageOps, ImageStat


@dataclass(frozen=True)
class PageRenderResult:
    page_number: int
    output_path: Path
    width_px: int
    height_px: int
    dpi: int
    rotation_degrees: int
    quality_score: float
    manual_review_required: bool


def render_document_pages(source_path, output_dir, *, dpi=300, quality_threshold=0.35):
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if source_path.suffix.lower() == ".pdf":
        images = _render_pdf(source_path, dpi)
    else:
        images = [_normalize_image(Image.open(source_path))]

    results = []
    for index, image in enumerate(images, start=1):
        image = _normalize_image(image)
        output_path = output_dir / f"page-{index:04d}.png"
        image.save(output_path, format="PNG", dpi=(dpi, dpi), optimize=True)
        quality_score = _quality_score(image, dpi)
        results.append(
            PageRenderResult(
                page_number=index,
                output_path=output_path,
                width_px=image.width,
                height_px=image.height,
                dpi=int(dpi),
                rotation_degrees=0,
                quality_score=quality_score,
                manual_review_required=quality_score < quality_threshold,
            )
        )
        image.close()
    return results


def _render_pdf(source_path, dpi):
    document = pdfium.PdfDocument(str(source_path))
    try:
        scale = float(dpi) / 72.0
        for page_index in range(len(document)):
            page = document[page_index]
            try:
                bitmap = page.render(scale=scale, rotation=0)
                try:
                    image = bitmap.to_pil().convert("RGB").copy()
                finally:
                    bitmap.close()
            finally:
                page.close()
            yield image
    finally:
        document.close()


def _normalize_image(image):
    normalized = ImageOps.exif_transpose(image)
    if normalized.mode not in {"RGB", "L"}:
        normalized = normalized.convert("RGB")
    elif normalized.mode == "L":
        normalized = normalized.convert("RGB")
    return normalized


def _quality_score(image, dpi):
    grayscale = image.convert("L")
    width_target = 8.27 * dpi
    height_target = 11.69 * dpi
    resolution = min(image.width / width_target, image.height / height_target, 1.0)
    contrast = min((ImageStat.Stat(grayscale).stddev[0] or 0.0) / 64.0, 1.0)
    if grayscale.width > 4 and grayscale.height > 4:
        grayscale = grayscale.crop((2, 2, grayscale.width - 2, grayscale.height - 2))
    edge_image = grayscale.filter(ImageFilter.FIND_EDGES)
    sharpness = min((ImageStat.Stat(edge_image).mean[0] or 0.0) / 32.0, 1.0)
    score = 0.25 * resolution + 0.45 * contrast + 0.3 * sharpness
    return round(max(0.0, min(score, 1.0)), 4)
