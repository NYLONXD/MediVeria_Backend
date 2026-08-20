"""
Synchronous OCR / DICOM conversion helpers.

Hackathon scope: NO AI summarization here. This module only turns an
uploaded file into (a) readable text or (b) a viewable preview image,
so the pipeline actually produces something the frontend can show —
instead of a "queued" processing_job that never runs.

Requires the `tesseract-ocr` binary installed on the host machine
(pytesseract is just a Python wrapper around it, pip alone is not enough):
  Ubuntu/Debian: sudo apt-get install -y tesseract-ocr
  macOS:         brew install tesseract
  Windows:       https://github.com/UB-Mannheim/tesseract/wiki
"""

import io
from typing import Optional

import fitz  # PyMuPDF
import numpy as np
import pytesseract
from PIL import Image


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Try direct text extraction first (fast, works for digital/typed PDFs).
    Falls back to OCR-ing each rendered page for scanned PDFs."""
    text_chunks: list[str] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        for page in doc:
            page_text = page.get_text().strip()
            if page_text:
                text_chunks.append(page_text)
                continue
            # No embedded text layer -> it's a scanned page, OCR it
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            text_chunks.append(pytesseract.image_to_string(img))
    finally:
        doc.close()
    return "\n\n".join(t for t in text_chunks if t).strip()


def extract_text_from_image(file_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return pytesseract.image_to_string(img).strip()


def dicom_to_preview_png(file_bytes: bytes) -> Optional[bytes]:
    """Convert a DICOM file to a single viewable PNG preview.

    For multi-frame series (e.g. a CT stack), this returns only the
    middle frame. A full slice-by-slice viewer is future work — this
    just gives the patient/doctor something real to look at tonight.
    """
    import pydicom

    ds = pydicom.dcmread(io.BytesIO(file_bytes))
    if not hasattr(ds, "pixel_array"):
        return None

    pixels = ds.pixel_array
    if pixels.ndim == 3:  # multi-frame: (frames, rows, cols)
        pixels = pixels[pixels.shape[0] // 2]

    pixels = pixels.astype(np.float32)
    p_min, p_max = float(pixels.min()), float(pixels.max())
    if p_max > p_min:
        pixels = (pixels - p_min) / (p_max - p_min) * 255.0
    else:
        pixels = np.zeros_like(pixels)
    pixels = pixels.astype(np.uint8)

    img = Image.fromarray(pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def dicom_metadata(file_bytes: bytes) -> dict:
    """Lightweight header read (no pixel data) for display + audit."""
    import pydicom

    ds = pydicom.dcmread(io.BytesIO(file_bytes), stop_before_pixels=True)
    return {
        "modality": getattr(ds, "Modality", None),
        "study_description": getattr(ds, "StudyDescription", None),
        "body_part": getattr(ds, "BodyPartExamined", None),
        "rows": getattr(ds, "Rows", None),
        "columns": getattr(ds, "Columns", None),
        "number_of_frames": int(getattr(ds, "NumberOfFrames", 1)),
    }