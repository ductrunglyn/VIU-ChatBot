"""Dựng tập huấn luyện data/qa/train.jsonl từ bộ Q/A trong data/qa/.

QUAN TRỌNG — vì sao phải kèm TÀI LIỆU vào mẫu huấn luyện:
Khi chạy thật, rag.py đưa cho mô hình một khối "TÀI LIỆU:" gồm các đoạn quy định
truy xuất được, rồi mới tới "CÂU HỎI:". Nếu huấn luyện chỉ bằng (câu hỏi -> đáp
án) mà KHÔNG có khối tài liệu, mô hình học cách trả lời bằng trí nhớ theo một
khuôn câu cố định, và khi chạy thật nó đọc lướt phần tài liệu rồi vẫn đọc lại
khuôn đã thuộc -> câu trả lời chung chung, bỏ sót chi tiết dù tài liệu có đủ.

Vì vậy mỗi mẫu huấn luyện được dựng ĐÚNG như lúc suy luận:
    system  = SYSTEM_PROMPT của rag.py (y hệt, không đổi một chữ)
    user    = "TÀI LIỆU:\\n<các đoạn truy xuất>\\n\\nCÂU HỎI: <câu hỏi>"
    assistant = đáp án do thầy cô soạn/làm giàu
Nhờ vậy mô hình học đúng kỹ năng cần dùng: ĐỌC tài liệu được cấp rồi liệt kê đầy
đủ chi tiết và dẫn đúng tên văn bản.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/build_dataset.py            # kèm tài liệu (khuyến nghị)
    python src/Phase4-Finetuning/build_dataset.py --no-rag   # kiểu cũ, chỉ hỏi-đáp
    python src/Phase4-Finetuning/build_dataset.py --k 3      # số đoạn tài liệu mỗi mẫu
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Phase3-RAG"))
import config

REQUIRED = ["id", "category", "question", "answer"]
MERGED_NAME = "qa_viu_full.csv"
REFUSAL_NAME = "qa_tu_choi.csv"          # mẫu dạy mô hình nói "tài liệu không có"
REFUSAL_CATEGORY = "Ngoài phạm vi kho tri thức"

# Đáp án cũ đều kết thúc bằng ĐÚNG MỘT câu khuyên, lặp ở 30% số mẫu. Mô hình học
# thuộc câu đó và đọc lại như phản xạ, cắt ngắn phần nội dung phía trước. Ta bỏ
# câu cố định và thay bằng vài biến thể luân phiên để nó không thành khuôn cứng.
_STOCK_ADVICE = re.compile(
    r"\s*Em nên đối chiếu trực tiếp điều khoản nêu trên để nắm đầy đủ chi tiết;\s*"
    r"nếu còn vướng mắc,\s*em liên hệ Phòng Quản lý đào tạo hoặc cố vấn học tập\s*"
    r"(của lớp\s*)?để được hướng dẫn cụ thể\.?\s*$")

_ADVICE_VARIANTS = [
    "",   # phần lớn mẫu KHÔNG có câu khuyên -> mô hình hết coi nó là bắt buộc
    "",
    "",
    "Nếu trường hợp của em có tình tiết riêng, em mang bảng điểm tới gặp cố vấn "
    "học tập để được tính cụ thể nhé.",
    "Em liên hệ Phòng Quản lý đào tạo nếu cần xác nhận cho trường hợp cụ thể của mình.",
]


def _vary_advice(ans: str, idx: int) -> str:
    """Bỏ câu khuyên rập khuôn ở cuối đáp án, thỉnh thoảng thay bằng biến thể."""
    trimmed = _STOCK_ADVICE.sub("", ans).strip()
    if trimmed == ans.strip():
        return ans.strip()                      # đáp án không dùng khuôn -> giữ nguyên
    tail = _ADVICE_VARIANTS[idx % len(_ADVICE_VARIANTS)]
    return (trimmed + " " + tail).strip() if tail else trimmed


def _load_rows():
    """Đọc bộ Q/A. Ưu tiên tệp gộp qa_viu_full.csv nếu đã chạy merge_qa.py."""
    import pandas as pd

    qa_dir = config.DATA_PROCESSED.parent / "qa"
    merged = qa_dir / MERGED_NAME
    if merged.exists():
        # Tệp gộp (đã rà soát tay) + các tệp SINH TỰ ĐỘNG kèm theo: mẫu từ chối,
        # Q/A kế hoạch đào tạo... Cố ý không gộp chúng vào qa_viu_full.csv để mỗi
        # lần sinh lại không ghi đè phần thầy cô đã chỉnh tay.
        extra = sorted(p for p in qa_dir.glob("qa_*.csv")
                       if p.name not in (MERGED_NAME,) and not p.name.endswith(".bak.csv")
                       and p.name != "qa_pairs_template.csv")
        files = [merged] + extra
    else:
        # Bỏ qua tệp sao lưu (*.bak.csv) do enrich_qa.py tạo: chúng chứa đáp án
        # NGẮN trước khi làm giàu, nạp vào sẽ kéo chất lượng dữ liệu xuống.
        files = [p for p in list(qa_dir.glob("*.csv")) + list(qa_dir.glob("*.xlsx"))
                 if not p.name.endswith(".bak.csv")]
    if not files:
        print(f"⚠️  Không tìm thấy file .csv/.xlsx nào trong {qa_dir}")
        sys.exit(0)

    rows = []
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-rag", action="store_true",
                    help="dựng kiểu cũ: chỉ câu hỏi -> đáp án, không kèm tài liệu")
    ap.add_argument("--k", type=int, default=3,
                    help="số đoạn tài liệu truy xuất kèm mỗi mẫu (mặc định 3)")
    ap.add_argument("--max-tokens", type=int, default=config.FT_MAX_LEN,
                    help="bỏ mẫu dài hơn ngưỡng này (mặc định lấy theo FT_MAX_LEN)")
    args = ap.parse_args()
    with_rag = not args.no_rag

    rows = _load_rows()

    if with_rag:
        import rag                      # dùng lại y hệt prompt + cách ghép tài liệu
        import retriever
        system_prompt = rag.SYSTEM_PROMPT
        print(f"\nTruy xuất tài liệu cho {len(rows)} câu hỏi (k={args.k}) ...")
    else:
        import rag
        system_prompt = rag.SYSTEM_PROMPT

    _tok = None
    if args.max_tokens > 0:
        from transformers import AutoTokenizer
        _tok = AutoTokenizer.from_pretrained(config.FINETUNE_BASE)

    # Chống trùng theo NỘI DUNG câu hỏi (id chỉ là số thứ tự cục bộ trong mỗi file).
    seen_q, kept, skipped, no_ctx, too_long = set(), [], 0, 0, 0
    for i, r in enumerate(rows):
        if not r["question"] or not r["answer"]:
            skipped += 1
            continue
        key = " ".join(r["question"].lower().split())
        if key in seen_q:
            skipped += 1
            continue
        seen_q.add(key)

        answer = _vary_advice(r["answer"], i)

        is_refusal = r.get("category") == REFUSAL_CATEGORY

        if with_rag:
            hits = retriever.retrieve(r["question"], args.k)
            if not retriever.has_relevant(hits) and not is_refusal:
                # Không có căn cứ trong kho tri thức: nếu vẫn huấn luyện, ta dạy
                # mô hình bịa ra nội dung không có trong tài liệu. Bỏ mẫu này.
                no_ctx += 1
                continue
            context, _ = rag._build_context(hits)
            # Mẫu TỪ CHỐI cố ý giữ lại đúng trường hợp khó: tài liệu truy xuất ra
            # đúng chủ đề nhưng KHÔNG chứa con số/danh sách được hỏi. Bỏ chúng đi
            # thì mô hình không bao giờ học được cách nói "tài liệu không có".
            user_msg = f"TÀI LIỆU:\n{context}\n\nCÂU HỎI: {r['question']}"
        else:
            user_msg = r["question"]

        sample = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": answer},
            ]
        }
        # Bộ huấn luyện cắt cụt từ CUỐI khi mẫu dài quá max_length, tức là cắt mất
        # chính phần đáp án cần học. Nên loại luôn ở đây thay vì để bị cắt.
        if _tok is not None:
            n_tok = len(_tok(_tok.apply_chat_template(sample["messages"],
                                                      tokenize=False))["input_ids"])
            if n_tok > args.max_tokens:
                too_long += 1
                continue

        kept.append(sample)
        if with_rag and (i + 1) % 300 == 0:
            print(f"   ... {i + 1}/{len(rows)} câu")

    out = config.DATA_PROCESSED.parent / "qa" / "train.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for ex in kept:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")

    mode = "CÓ kèm tài liệu (khớp lúc chạy thật)" if with_rag else "KHÔNG kèm tài liệu"
    print(f"\n✅ {len(kept)} mẫu [{mode}] -> {out}")
    print(f"   Bỏ qua: {skipped} dòng rỗng/trùng"
          + (f", {no_ctx} câu không tìm được căn cứ trong kho tri thức" if with_rag else "")
          + (f", {too_long} mẫu dài quá {args.max_tokens} token" if too_long else ""))
    if len(kept) < 500:
        print(f"   ℹ️  Khuyến nghị đạt 500–1000 cặp trước khi fine-tuning (hiện {len(kept)}).")


if __name__ == "__main__":
    main()
