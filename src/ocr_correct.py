"""Sửa lỗi OCR tiếng Việt phổ biến (hậu xử lý sau OCR).

Triết lý: CHỈ sửa những dạng CHẮC CHẮN sai (không phải từ tiếng Việt hợp lệ),
để đạt độ chính xác cao, tránh tạo lỗi mới. Không đụng vào các từ mơ hồ vốn
đúng (dạy, dẫn, dân, dịch, dõi, dành, dấu...).

Hai tầng:
  1) Luật ký tự (regex) cho họ vần "ươ" và lỗi "I hoa -> l".
  2) Từ điển từ/cụm sai chắc chắn (WORD_MAP), có bảo toàn hoa/thường.

An toàn với văn bản đã đúng: các dạng lỗi này không xuất hiện trong text chuẩn,
nên có thể áp dụng cho cả file text số hóa lẫn file OCR mà không hỏng dữ liệu.
"""
from __future__ import annotations
import re

# --- Tầng 1a: sửa họ vần "ươ" bị OCR làm hỏng (giữ nguyên thanh điệu) ---
# u + {ơ,ờ,ớ,ở,ỡ,ợ}  ->  ư + (giữ nguyên)   vd: truờng->trường, chuơng->chương
_U_BEFORE_OHOOK = re.compile(r"(?<!q)u([ơờớởỡợ])", re.IGNORECASE)
# ư + {o,ò,ó,ỏ,õ,ọ}  ->  ư + {ơ,ờ,ớ,ở,ỡ,ợ}   vd: tưong->tương, lưọng->lượng
_O_TO_OHOOK = {"o": "ơ", "ò": "ờ", "ó": "ớ", "ỏ": "ở", "õ": "ỡ", "ọ": "ợ",
               "O": "Ơ", "Ò": "Ờ", "Ó": "Ớ", "Ỏ": "Ở", "Õ": "Ỡ", "Ọ": "Ợ"}
_UHOOK_BEFORE_O = re.compile(r"ư([oòóỏõọ])", re.IGNORECASE)

# --- Tầng 1b: "I" (i hoa) đứng trước nguyên âm thường là chữ "l" bị OCR nhầm ---
_VN_VOWELS = "aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ"
_I_AS_L = re.compile(r"I(?=[" + _VN_VOWELS + r"])")

# --- Tầng 2: từ/cụm sai CHẮC CHẮN (không phải từ tiếng Việt hợp lệ) ---
WORD_MAP = {
    # thiếu dấu / sai thanh
    "hoc": "học", "tao": "tạo", "trinh": "trình", "vién": "viên",
    "cúa": "của", "cùa": "của", "chuong": "chương", "quy dinh": "quy định",
    "tín chi": "tín chỉ",
    # d -> đ (chỉ những chuỗi không phải từ hợp lệ)
    "dào": "đào", "dịnh": "định", "dinh": "định", "dăng": "đăng",
    "dến": "đến", "dánh": "đánh", "dảm": "đảm", "dể": "để", "diều": "điều",
    "dại": "đại", "dơn": "đơn", "dồng": "đồng", "dủ": "đủ", "dạt": "đạt",
    "dúng": "đúng", "dịa": "địa", "dó": "đó", "diểm": "điểm", "diểu": "điều",
    "dạo": "đạo",  # trong "đào tạo"/"chỉ đạo" (dạo này -> hiếm trong văn bản chính quy)
}


def _match_case(src: str, repl: str) -> str:
    """Bảo toàn hoa/thường: nếu từ gốc viết hoa chữ đầu thì kết quả cũng hoa."""
    if src[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def _apply_word_map(text: str) -> str:
    for wrong, right in WORD_MAP.items():
        pat = re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE)
        text = pat.sub(lambda m: _match_case(m.group(0), right), text)
    return text


def correct_text(text: str) -> str:
    # Tầng 1a
    text = _U_BEFORE_OHOOK.sub(lambda m: "ư" + m.group(1), text)
    text = _UHOOK_BEFORE_O.sub(lambda m: "ư" + _O_TO_OHOOK[m.group(1)], text)
    # Tầng 1b
    text = _I_AS_L.sub("l", text)
    # Tầng 2
    text = _apply_word_map(text)
    return text


if __name__ == "__main__":
    # Chạy trực tiếp: sửa lỗi tại chỗ cho toàn bộ file trong data/interim/
    import glob
    import config

    files = sorted(config.DATA_INTERIM.glob("*.md"))
    total = 0
    for f in files:
        before = f.read_text(encoding="utf-8")
        after = correct_text(before)
        if after != before:
            f.write_text(after, encoding="utf-8")
            # đếm số ký tự thay đổi (xấp xỉ số lỗi sửa)
            diff = sum(1 for a, b in zip(before, after) if a != b)
            total += diff
            print(f"  ✓ {f.name}: ~{diff} vị trí sửa")
    print(f"\nĐã sửa OCR tại chỗ cho {len(files)} file (~{total} vị trí).")
    print("Chạy tiếp: python src/pipeline.py --from-interim --stats  để cập nhật chunks.jsonl")
