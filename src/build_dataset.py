"""Gộp các file Q/A (CSV/XLSX) trong data/qa/ -> data/qa/train.jsonl (chat format).

Dùng cho Giai đoạn 4 (fine-tuning QLoRA). Có kiểm tra hợp lệ cơ bản:
- thiếu cột bắt buộc, câu hỏi/câu trả lời rỗng, id trùng.
"""
from __future__ import annotations
import json
import sys

import config

SYSTEM_PROMPT = (
    "Bạn là trợ lý cố vấn học tập của Trường Đại học Công nghiệp Việt - Hung. "
    "Nhiệm vụ của bạn là trả lời chính xác theo quy chế, quy định của trường và "
    "tư vấn lộ trình học tập cho sinh viên bằng giọng thân thiện, có bước hành động "
    "cụ thể. Nếu không chắc chắn, hãy khuyên sinh viên liên hệ cố vấn học tập/phòng đào tạo."
)

REQUIRED = ["id", "category", "question", "answer"]


def _load_rows():
    """Đọc mọi file .csv/.xlsx trong data/qa/ (bỏ qua train.jsonl và template rỗng)."""
    import pandas as pd

    qa_dir = config.DATA_PROCESSED.parent / "qa"
    rows = []
    files = list(qa_dir.glob("*.csv")) + list(qa_dir.glob("*.xlsx"))
    if not files:
        print(f"⚠️  Không tìm thấy file .csv/.xlsx nào trong {qa_dir}")
        sys.exit(0)
    for f in files:
        df = pd.read_csv(f, dtype=str) if f.suffix == ".csv" else pd.read_excel(f, dtype=str)
        df = df.fillna("")
        missing = [c for c in REQUIRED if c not in df.columns]
        if missing:
            print(f"❌ {f.name} thiếu cột bắt buộc: {missing} -> bỏ qua")
            continue
        for _, r in df.iterrows():
            rows.append({c: str(r.get(c, "")).strip() for c in df.columns})
        print(f"  ✓ {f.name}: {len(df)} dòng")
    return rows


def main():
    rows = _load_rows()
    seen_ids, kept, skipped = set(), [], 0
    for r in rows:
        if not r["question"] or not r["answer"]:
            skipped += 1
            continue
        if r["id"] in seen_ids:
            print(f"  ⚠️  id trùng: {r['id']} -> bỏ qua")
            skipped += 1
            continue
        seen_ids.add(r["id"])
        kept.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": r["question"]},
                {"role": "assistant", "content": r["answer"]},
            ]
        })

    out = config.DATA_PROCESSED.parent / "qa" / "train.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for ex in kept:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"\n✅ {len(kept)} cặp Q/A hợp lệ -> {out}  (bỏ qua {skipped})")
    if len(kept) < 500:
        print(f"   ℹ️  Khuyến nghị đạt 500–1000 cặp trước khi fine-tuning (hiện {len(kept)}).")


if __name__ == "__main__":
    main()
