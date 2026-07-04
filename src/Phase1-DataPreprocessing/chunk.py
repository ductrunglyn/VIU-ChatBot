"""Bước 4: Chunking theo cấu trúc văn bản quy chế Việt Nam.

Chiến lược hybrid:
  1) Nếu tài liệu có cấu trúc "Điều N" (quy chế) -> cắt theo từng Điều,
     kèm ngữ cảnh Chương/Mục ở tiêu đề (metadata).
  2) Điều nào dài quá CHUNK_MAX_WORDS -> cắt nhỏ tiếp theo Khoản (1. 2. 3.)
     hoặc theo đoạn văn, có overlap.
  3) Tài liệu không có "Điều" (khung chương trình, đề án tuyển sinh) ->
     cắt theo tiêu đề Markdown / đoạn văn với mục tiêu số từ.

Mỗi chunk kèm metadata: nguồn file, chương, điều, tiêu đề -> giúp RAG trích dẫn.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / "common"))
import config

# Bảng chữ hoa tiếng Việt (để nhận tiêu đề bắt đầu ngay sau "Điều N.")
_VN_UPPER = ("A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊ"
             "ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ")

# Nhận "Điều N" ở BẤT KỲ đâu (vì OCR gộp đoạn -> tiêu đề nằm giữa dòng),
# nhưng yêu cầu có dấu . hoặc : và ngay sau là CHỮ HOA tiêu đề -> loại tham chiếu
# chéo kiểu "theo Điều 5 của Quy chế" (sau số không có dấu chấm + chữ hoa).
_DIEU_RE = re.compile(r"Điều\s+(\d+)([a-z]?)\s*[.:]\s*(?=[" + _VN_UPPER + r"])")
_CHUONG_RE = re.compile(r"CHƯƠNG\s+([IVXLCDM\d]+)\b\s*[.:]?\s*", re.IGNORECASE)
_KHOAN_RE = re.compile(r"(?m)^\s*(\d{1,2})\.\s+")


def _find_dieu_boundaries(text: str):
    """Lọc các match 'Điều N' thành chuỗi TĂNG DẦN (loại tham chiếu chéo lùi số)."""
    kept, last = [], (0, "")
    for m in _DIEU_RE.finditer(text):
        key = (int(m.group(1)), m.group(2) or "")
        if key > last:
            kept.append(m)
            last = key
    return kept


def _wc(text: str) -> int:
    return len(text.split())


@dataclass
class Chunk:
    chunk_id: str
    source: str
    text: str
    word_count: int
    chuong: Optional[str] = None
    dieu: Optional[str] = None
    heading: Optional[str] = None


def _split_by_words(text: str, target: int, max_w: int, overlap: int) -> List[str]:
    """Cắt 1 đoạn dài theo ranh giới câu, gom tới ~target từ, chồng lấp overlap từ."""
    # Ưu tiên cắt theo khoản, nếu không có thì theo câu.
    sentences = re.split(r"(?<=[\.\?!;])\s+|\n", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    chunks, cur, cur_wc = [], [], 0
    for sent in sentences:
        sw = _wc(sent)
        if cur_wc + sw > max_w and cur:
            chunks.append(" ".join(cur))
            # tạo overlap: giữ lại vài câu cuối
            keep, kw = [], 0
            for s in reversed(cur):
                if kw >= overlap:
                    break
                keep.insert(0, s)
                kw += _wc(s)
            cur, cur_wc = keep[:], kw
        cur.append(sent)
        cur_wc += sw
        if cur_wc >= target:
            chunks.append(" ".join(cur))
            keep, kw = [], 0
            for s in reversed(cur):
                if kw >= overlap:
                    break
                keep.insert(0, s)
                kw += _wc(s)
            cur, cur_wc = keep[:], kw
    if cur:
        chunks.append(" ".join(cur))
    # loại trùng do overlap tạo ra chunk giống hệt
    seen, uniq = set(), []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def _current_chuong(text: str, pos: int, chuong_matches) -> Optional[str]:
    """Tìm 'Chương' gần nhất phía trên vị trí pos."""
    label = None
    for m in chuong_matches:
        if m.start() <= pos:
            label = "CHƯƠNG " + m.group(1).upper()
        else:
            break
    return label


def chunk_document(text: str, source: str) -> List[Chunk]:
    chuong_matches = list(_CHUONG_RE.finditer(text))
    dieu_matches = _find_dieu_boundaries(text)

    if dieu_matches:
        return _chunk_by_dieu(text, source, dieu_matches, chuong_matches)
    return _chunk_generic(text, source)


def _chunk_by_dieu(text, source, dieu_matches, chuong_matches) -> List[Chunk]:
    chunks: List[Chunk] = []
    for idx, m in enumerate(dieu_matches):
        start = m.start()
        end = dieu_matches[idx + 1].start() if idx + 1 < len(dieu_matches) else len(text)
        block = text[start:end].strip()
        dieu_label = f"Điều {m.group(1)}{m.group(2) or ''}"
        # Tiêu đề Điều = phần chữ ngay sau "Điều N." tới trước khoản đầu ("1."),
        # giới hạn 20 từ (OCR gộp cả Điều lên 1 dòng -> tránh 'nuốt' nội dung).
        after = text[m.end():m.end() + 300]
        dieu_title = re.split(r"\s+\d{1,2}[.\)]\s", " " + after)[0].strip()
        dieu_title = " ".join(dieu_title.split()[:20])
        chuong = _current_chuong(text, start, chuong_matches)

        if _wc(block) <= config.CHUNK_MAX_WORDS:
            pieces = [block]
        else:
            pieces = _split_by_words(block, config.CHUNK_TARGET_WORDS,
                                     config.CHUNK_MAX_WORDS, config.CHUNK_OVERLAP_WORDS)
        for j, piece in enumerate(pieces):
            cid = f"{source}::{dieu_label}" + (f"::p{j+1}" if len(pieces) > 1 else "")
            chunks.append(Chunk(
                chunk_id=cid, source=source, text=piece, word_count=_wc(piece),
                chuong=chuong, dieu=dieu_label,
                heading=dieu_title or None,
            ))
    return chunks


def _chunk_generic(text, source) -> List[Chunk]:
    """Cho tài liệu không theo cấu trúc Điều: cắt theo heading Markdown / số từ."""
    # Tách theo heading markdown (##) nếu có, giữ heading làm ngữ cảnh.
    blocks = re.split(r"(?m)^(#+\s+.*)$", text)
    segments, heading = [], None
    if len(blocks) == 1:
        segments = [(None, text)]
    else:
        # blocks xen kẽ: [trước-heading, heading, nội-dung, heading, nội-dung...]
        buf = blocks[0]
        if buf.strip():
            segments.append((None, buf))
        i = 1
        while i < len(blocks):
            heading = blocks[i].lstrip("# ").strip()
            content = blocks[i + 1] if i + 1 < len(blocks) else ""
            segments.append((heading, content))
            i += 2

    chunks: List[Chunk] = []
    counter = 0
    for heading, content in segments:
        content = content.strip()
        if not content:
            continue
        pieces = ([content] if _wc(content) <= config.CHUNK_MAX_WORDS
                  else _split_by_words(content, config.CHUNK_TARGET_WORDS,
                                       config.CHUNK_MAX_WORDS, config.CHUNK_OVERLAP_WORDS))
        for piece in pieces:
            counter += 1
            body = (f"{heading}\n{piece}" if heading else piece)
            chunks.append(Chunk(
                chunk_id=f"{source}::c{counter}", source=source,
                text=body, word_count=_wc(body), heading=heading,
            ))
    return chunks


def merge_tiny_chunks(chunks: List[Chunk]) -> List[Chunk]:
    """Gộp chunk quá ngắn (< CHUNK_MIN_WORDS) vào chunk trước cùng nguồn."""
    out: List[Chunk] = []
    for c in chunks:
        if out and c.word_count < config.CHUNK_MIN_WORDS and out[-1].source == c.source:
            prev = out[-1]
            prev.text = prev.text + "\n" + c.text
            prev.word_count = _wc(prev.text)
        else:
            out.append(c)
    return out


def to_dict(c: Chunk) -> dict:
    return asdict(c)
