"""Bước 3: Làm sạch dữ liệu tiếng Việt.

- Chuẩn hóa Unicode NFC (gộp dấu tổ hợp -> ký tự dựng sẵn).
- Xóa đầu trang / chân trang lặp lại (page number, tên trường in mỗi trang).
- Nối lại từ bị gạch nối cuối dòng, gom khoảng trắng / dòng trống thừa.
"""
from __future__ import annotations
import re
import unicodedata
from collections import Counter
from typing import List

from extract import PAGE_MARKER

_PAGE_RE = re.compile(r"<<<PAGE \d+>>>")


def normalize_unicode(text: str) -> str:
    """NFC + thay các loại khoảng trắng / gạch nối lạ về dạng chuẩn."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ").replace("\t", " ")
    text = text.replace("–", "-").replace("—", "-")  # en/em dash
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    return text


def _split_pages(text: str) -> List[str]:
    """Tách văn bản thành danh sách trang dựa trên dấu mốc PAGE."""
    parts = _PAGE_RE.split(text)
    return [p for p in parts if p is not None]


def remove_repeated_headers_footers(text: str, min_repeat_ratio: float = 0.5) -> str:
    """Dòng ngắn xuất hiện ở >= min_repeat_ratio số trang được coi là header/footer.

    Chỉ áp dụng khi có nhiều trang; giữ nguyên nếu tài liệu chỉ 1-2 trang.
    """
    pages = _split_pages(text)
    if len(pages) < 4:
        return _PAGE_RE.sub("\n", text)

    # Đếm tần suất các dòng "ngắn" (nghi là header/footer), bỏ qua dòng dài.
    counter: Counter = Counter()
    for pg in pages:
        seen = set()
        for line in pg.splitlines():
            s = line.strip()
            if s and len(s) <= 80 and s not in seen:
                counter[s] += 1
                seen.add(s)

    threshold = max(2, int(len(pages) * min_repeat_ratio))
    boilerplate = {line for line, c in counter.items() if c >= threshold}

    cleaned_pages = []
    for pg in pages:
        kept = [ln for ln in pg.splitlines()
                if ln.strip() not in boilerplate]
        cleaned_pages.append("\n".join(kept))
    return "\n".join(cleaned_pages)


def _strip_page_numbers(text: str) -> str:
    """Xóa các dòng chỉ chứa số trang (vd: '12', 'Trang 12', '- 12 -')."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if re.fullmatch(r"(trang\s*)?[-–\s]*\d{1,4}[-–\s]*", s, flags=re.IGNORECASE):
            continue
        out.append(line)
    return "\n".join(out)


def dehyphenate(text: str) -> str:
    """Nối từ bị ngắt bằng dấu '-' cuối dòng (hiếm ở tiếng Việt nhưng có ở PDF)."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def collapse_whitespace(text: str) -> str:
    text = re.sub(r"[  ]{2,}", " ", text)      # nhiều space -> 1
    text = re.sub(r" *\n *", "\n", text)             # bỏ space quanh xuống dòng
    text = re.sub(r"\n{3,}", "\n\n", text)           # tối đa 1 dòng trống
    return text.strip()


def clean_text(text: str) -> str:
    import ocr_correct  # sửa lỗi OCR tiếng Việt phổ biến

    text = normalize_unicode(text)
    text = remove_repeated_headers_footers(text)
    text = _strip_page_numbers(text)
    text = dehyphenate(text)
    text = collapse_whitespace(text)
    text = ocr_correct.correct_text(text)
    return text
