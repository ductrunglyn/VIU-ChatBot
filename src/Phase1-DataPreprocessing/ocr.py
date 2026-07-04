"""OCR cho PDF scan ảnh bằng EasyOCR (chạy GPU), render trang qua PyMuPDF.

Reader được nạp 1 lần (singleton) vì khởi tạo model khá tốn thời gian.
"""
from __future__ import annotations
from pathlib import Path

_READER = None
_DPI = 300  # độ phân giải render trang -> ảnh; 300 hợp lý cho OCR tiếng Việt


def get_reader():
    """Nạp EasyOCR reader tiếng Việt + Anh, ưu tiên GPU."""
    global _READER
    if _READER is None:
        import easyocr
        try:
            _READER = easyocr.Reader(["vi", "en"], gpu=True)
            print("    [OCR] EasyOCR sẵn sàng (GPU).")
        except Exception as e:  # noqa: BLE001 - fallback CPU nếu GPU lỗi
            print(f"    [OCR] Không dùng được GPU ({e}); chuyển sang CPU (chậm hơn).")
            _READER = easyocr.Reader(["vi", "en"], gpu=False)
    return _READER


def _page_to_image(page):
    """Render 1 trang PDF (fitz.Page) thành numpy array RGB."""
    import numpy as np
    import fitz  # PyMuPDF

    zoom = _DPI / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:  # RGBA -> RGB
        img = img[:, :, :3]
    return img


def ocr_page(page) -> str:
    """OCR 1 trang, trả về text (đã gộp thành đoạn)."""
    reader = get_reader()
    img = _page_to_image(page)
    lines = reader.readtext(img, detail=0, paragraph=True)
    return "\n".join(lines).strip()


def ocr_pdf_page_by_index(pdf_path: Path, page_index: int) -> str:
    """Tiện ích: OCR đúng 1 trang theo chỉ số (0-based)."""
    import fitz
    with fitz.open(pdf_path) as doc:
        return ocr_page(doc[page_index])
