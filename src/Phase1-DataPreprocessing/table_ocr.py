"""OCR BẢNG cho PDF scan bằng img2table + EasyOCR -> Markdown.

EasyOCR thường (ocr.py) đọc text nhưng làm VỠ cấu trúc bảng. img2table phát hiện
ô/đường kẻ bảng rồi OCR từng ô -> giữ được hàng/cột (mã HP, tín chỉ, môn tiên quyết
trong khung chương trình; bảng quy đổi điểm...).

Dùng cho các trang scan trong extract.py.
"""
from __future__ import annotations
from pathlib import Path

from extract import _table_to_markdown

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        from img2table.ocr import EasyOCR
        _ocr = EasyOCR(lang=["vi", "en"])
    return _ocr


def extract_tables_markdown(pdf_path: Path) -> dict:
    """Trả về {chỉ số trang (0-based): markdown các bảng của trang đó}."""
    from img2table.document import PDF

    doc = PDF(str(pdf_path))
    tables = doc.extract_tables(
        ocr=_get_ocr(), borderless_tables=True,
        implicit_rows=True, min_confidence=50,
    )
    out = {}
    for page, tbls in tables.items():
        mds = []
        for t in tbls:
            rows = t.df.fillna("").astype(str).values.tolist()
            md = _table_to_markdown(rows)
            if md:
                mds.append(md)
        if mds:
            out[page] = "\n\n".join(mds)
    return out
