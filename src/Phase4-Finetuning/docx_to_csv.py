"""Chuyển file .docx câu hỏi tư vấn -> CSV theo mẫu qa.

Định dạng .docx mong đợi (mỗi câu 1 khối, phân tách bởi dòng trống):
    Câu N
    Chủ đề: <chủ đề>
    Câu hỏi:
    <nội dung câu hỏi ...>
    Đáp án:
    <nội dung đáp án ...>
    Tài liệu tham chiếu:
    <nguồn 1>
    <nguồn 2 ...>

Cách dùng:
    conda activate test
    # tự tìm mọi .docx trong data/qa/:
    python src/Phase4-FinetuningData/docx_to_csv.py
    # hoặc chỉ định file:
    python src/Phase4-FinetuningData/docx_to_csv.py "data/qa/Câu hỏi tổng hợp.docx"

Kết quả: mỗi <tên>.docx -> data/qa/<tên>.csv (cột: id,category,question,answer,source_refs,notes)
"""
from __future__ import annotations
import csv
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes"]

_CAU_RE = re.compile(r"^\s*Câu\s+\d+\s*$", re.IGNORECASE)
_LABELS = [
    ("category", re.compile(r"^\s*Chủ\s*đề\s*:\s*(.*)$", re.IGNORECASE)),
    ("question", re.compile(r"^\s*Câu\s*hỏi\s*:\s*(.*)$", re.IGNORECASE)),
    ("answer",   re.compile(r"^\s*Đáp\s*án\s*:\s*(.*)$", re.IGNORECASE)),
    ("source",   re.compile(r"^\s*Tài\s*liệu\s*tham\s*khảo\s*:\s*(.*)$|"
                            r"^\s*Tài\s*liệu\s*tham\s*chiếu\s*:\s*(.*)$", re.IGNORECASE)),
]


def parse_paragraphs(paras):
    """Trả về danh sách dict {category, question, answer, source}."""
    items, cur, field = [], None, None

    def flush():
        if cur and cur["question"] and cur["answer"]:
            items.append(cur.copy())

    for raw in paras:
        line = raw.strip()
        if not line or set(line) <= {"_", "-", "—", "•"}:  # bỏ dòng trống / gạch ngang
            continue
        if _CAU_RE.match(line):
            flush()
            cur = {"category": "", "question": "", "answer": "", "source": ""}
            field = None
            continue
        if cur is None:
            continue

        matched = False
        for key, rx in _LABELS:
            m = rx.match(line)
            if m:
                val = next((g for g in m.groups() if g), "").strip()
                if key == "category":
                    cur["category"] = val
                    field = None
                else:
                    field = key
                    if val:
                        cur[key] = val
                matched = True
                break
        if matched:
            continue

        # dòng nội dung nối tiếp field đang mở
        if field:
            sep = " | " if (field == "source" and cur[field]) else (" " if cur[field] else "")
            cur[field] = cur[field] + sep + line
    flush()
    return items


def convert(docx_path: pathlib.Path) -> pathlib.Path:
    from docx import Document

    doc = Document(docx_path)
    # Mỗi câu có thể nằm trọn trong 1 đoạn văn với xuống dòng mềm (\n) -> tách thêm
    # theo \n để mỗi nhãn (Câu N / Chủ đề / Câu hỏi / Đáp án / Tài liệu) là 1 dòng.
    lines = []
    for p in doc.paragraphs:
        lines.extend(p.text.split("\n"))
    items = parse_paragraphs(lines)

    out = docx_path.with_suffix(".csv")
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for i, it in enumerate(items, start=1):
            w.writerow({
                "id": i,
                "category": it["category"],
                "question": it["question"].strip(),
                "answer": it["answer"].strip(),
                "source_refs": it["source"].strip(),
                "notes": "",
            })
    print(f"  ✓ {docx_path.name} -> {out.name}: {len(items)} câu hỏi")
    return out


def main():
    qa_dir = config.DATA_PROCESSED.parent / "qa"
    if len(sys.argv) > 1:
        files = [pathlib.Path(a) for a in sys.argv[1:]]
    else:
        files = sorted(qa_dir.glob("*.docx"))
    if not files:
        print(f"⚠️  Không tìm thấy .docx nào trong {qa_dir}")
        return
    for f in files:
        convert(f)
    print("\nXong. Chạy tiếp: python src/Phase4-Finetuning/build_dataset.py")


if __name__ == "__main__":
    main()
