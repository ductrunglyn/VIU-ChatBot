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
        # Loại mọi BẢN SAO LƯU. Chỉ chặn ".bak.csv" là chưa đủ: bản sao lưu của
        # tinh_chinh_dap_an.py tên ".truoc-tinhchinh.csv" đã lọt vào và nâng số câu
        # từ 3502 lên 5621 — tập huấn luyện khi đó chứa CẢ đáp án cũ chưa tinh chỉnh
        # lẫn bản mới, đúng thứ vừa bỏ công sửa. Chặn theo danh sách hậu tố.
        HAU_TO_SAO_LUU = (".bak.csv", ".truoc-tinhchinh.csv", ".backup.csv", ".old.csv")
        extra = sorted(p for p in qa_dir.glob("qa_*.csv")
                       if p.name not in (MERGED_NAME,)
                       and not p.name.endswith(HAU_TO_SAO_LUU)
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
    # Mặc định bám theo RAG_TOP_K để mẫu huấn luyện có ĐÚNG số đoạn tài liệu như
    # lúc chạy thật. Đóng cứng 3 như trước là tự tạo lệch: rag.py đưa 6 đoạn vào
    # ngữ cảnh còn mô hình chỉ từng học đọc 3 đoạn.
    ap.add_argument("--k", type=int, default=config.RAG_TOP_K,
                    help=f"số đoạn tài liệu truy xuất kèm mỗi mẫu (mặc định RAG_TOP_K={config.RAG_TOP_K})")
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
    seen_q, kept, skipped, no_ctx, too_long, bot_ctx = set(), [], 0, 0, 0, 0
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
        else:
            hits = []

        def _dung(hs):
            if not with_rag:
                return r["question"]
            # Truyền CẢ CÂU HỎI, y như rag.py lúc chạy thật. Bản trước gọi thiếu
            # đối số này nên mẫu huấn luyện không có khối "DỮ KIỆN TRA CỨU TỪ KẾ
            # HOẠCH ĐÀO TẠO", trong khi lúc chạy thật khối đó luôn được ghép vào.
            # Mô hình vì thế chưa từng học cách đọc khối dữ kiện đã tra sẵn — đúng
            # thứ dùng để trả lời chính xác số tín chỉ và danh sách học phần.
            context, _ = rag._build_context(hs, r["question"])
            # Mẫu TỪ CHỐI cố ý giữ lại đúng trường hợp khó: tài liệu truy xuất ra
            # đúng chủ đề nhưng KHÔNG chứa con số/danh sách được hỏi. Bỏ chúng đi
            # thì mô hình không bao giờ học được cách nói "tài liệu không có".
            return f"TÀI LIỆU:\n{context}\n\nCÂU HỎI: {r['question']}"

        def _mau(hs):
            return {"messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _dung(hs)},
                {"role": "assistant", "content": answer},
            ]}

        # Mẫu dài quá max_length sẽ bị cắt từ CUỐI, tức cắt mất chính đáp án cần
        # học. Bản trước loại thẳng mẫu đó — nhưng như vậy là mất hẳn một câu hỏi
        # khỏi tập huấn luyện. Nay bỏ bớt ĐOẠN TÀI LIỆU kém liên quan nhất (đã xếp
        # hạng nên đoạn cuối là đoạn yếu nhất) cho tới khi vừa, giữ nguyên đáp án.
        # Chỉ loại khi còn đúng một đoạn mà vẫn dài quá.
        sample = _mau(hits)
        if _tok is not None:
            def _dem(s):
                return len(_tok(_tok.apply_chat_template(s["messages"],
                                                         tokenize=False))["input_ids"])
            dung = list(hits)
            while _dem(sample) > args.max_tokens and len(dung) > 1:
                dung = dung[:-1]
                sample = _mau(dung)
                bot_ctx += 1
            if _dem(sample) > args.max_tokens:
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
    if bot_ctx:
        print(f"   ℹ️  {bot_ctx} lần bớt bớt đoạn tài liệu để mẫu vừa ngưỡng mà KHÔNG cắt đáp án")
    if len(kept) < 500:
        print(f"   ℹ️  Khuyến nghị đạt 500–1000 cặp trước khi fine-tuning (hiện {len(kept)}).")


if __name__ == "__main__":
    main()
