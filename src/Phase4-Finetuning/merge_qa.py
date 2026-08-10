"""Gộp tất cả tệp Q/A rời trong data/qa/ thành MỘT tệp tổng hợp duy nhất.

Lý do: bộ Q/A hiện nằm rải ở nhiều tệp (soạn tay, sinh tự động từ tài liệu, câu
hỏi thường gặp). Mỗi tệp đánh số id riêng nên id bị trùng giữa các tệp, khó tra
cứu và khó bàn giao. Tệp gộp có id liên tục, không trùng câu hỏi.

Quy tắc gộp:
- Nhận diện trùng theo NỘI DUNG câu hỏi đã chuẩn hóa (bỏ dấu câu, gộp khoảng trắng).
- Khi trùng, GIỮ bản có đáp án dài hơn (đáp án dài thường là bản đã làm giàu căn cứ).
- Bỏ dòng thiếu câu hỏi hoặc thiếu đáp án.
- Thêm cột `origin` ghi tệp nguồn để sau này còn truy vết được.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/merge_qa.py
    python src/Phase4-Finetuning/merge_qa.py --out data/qa/qa_viu_full.csv
"""
from __future__ import annotations
import argparse
import csv
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes", "origin"]
DEFAULT_OUT = "qa_viu_full.csv"


def _norm(q: str) -> str:
    """Chuẩn hóa câu hỏi để so trùng: thường hóa, bỏ dấu câu, gộp khoảng trắng."""
    q = re.sub(r"[^\w\s]", " ", (q or "").lower())
    return " ".join(q.split())


def _read(path: pathlib.Path) -> list[dict]:
    import pandas as pd

    df = pd.read_excel(path, dtype=str) if path.suffix in (".xlsx", ".xls") \
        else pd.read_csv(path, dtype=str)
    df = df.fillna("")
    missing = [c for c in ("question", "answer") if c not in df.columns]
    if missing:
        print(f"  ⚠️  {path.name}: thiếu cột {missing} -> bỏ qua")
        return []
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "category": str(r.get("category", "")).strip(),
            "question": str(r.get("question", "")).strip(),
            "answer": str(r.get("answer", "")).strip(),
            "source_refs": str(r.get("source_refs", "")).strip(),
            "notes": str(r.get("notes", "")).strip(),
            "origin": path.name,
        })
    return rows


def collect(qa_dir: pathlib.Path, out_name: str) -> list[pathlib.Path]:
    """Liệt kê tệp nguồn: bỏ bản sao lưu *.bak.csv và bỏ chính tệp đầu ra."""
    files = sorted(list(qa_dir.glob("*.csv")) + list(qa_dir.glob("*.xlsx")))
    return [p for p in files
            if not p.name.endswith(".bak.csv") and p.name != out_name]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="đường dẫn tệp gộp (mặc định data/qa/qa_viu_full.csv)")
    args = ap.parse_args()

    qa_dir = config.DATA_PROCESSED.parent / "qa"
    out = pathlib.Path(args.out) if args.out else qa_dir / DEFAULT_OUT

    files = collect(qa_dir, out.name)
    if not files:
        print(f"❌ Không tìm thấy tệp Q/A nào trong {qa_dir}")
        sys.exit(1)

    print(f"Đọc {len(files)} tệp nguồn:")
    rows = []
    for f in files:
        got = _read(f)
        rows.extend(got)
        print(f"  ✓ {f.name}: {len(got)} dòng")

    # Gộp, chống trùng: giữ bản có đáp án DÀI hơn.
    best: dict[str, dict] = {}
    empty = dup = 0
    for r in rows:
        if not r["question"] or not r["answer"]:
            empty += 1
            continue
        key = _norm(r["question"])
        old = best.get(key)
        if old is None:
            best[key] = r
        else:
            dup += 1
            if len(r["answer"].split()) > len(old["answer"].split()):
                best[key] = r

    # Sắp xếp theo chủ đề rồi theo câu hỏi để tệp dễ đọc, dễ rà soát thủ công.
    merged = sorted(best.values(), key=lambda r: (r["category"], r["question"]))
    for i, r in enumerate(merged, 1):
        r["id"] = str(i)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL,
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(merged)

    words = [len(r["answer"].split()) for r in merged]
    cats: dict[str, int] = {}
    for r in merged:
        cats[r["category"]] = cats.get(r["category"], 0) + 1

    print(f"\n✅ Đã gộp -> {out}")
    print(f"   {len(merged)} câu hỏi (bỏ {dup} câu trùng, {empty} dòng rỗng)")
    print(f"   Đáp án: trung bình {sum(words)//len(words)} từ, "
          f"ngắn nhất {min(words)}, dài nhất {max(words)}")
    print(f"   {len(cats)} chủ đề:")
    for k, v in sorted(cats.items(), key=lambda kv: -kv[1]):
        print(f"     {v:5d}  {k or '(chưa phân loại)'}")


if __name__ == "__main__":
    main()
