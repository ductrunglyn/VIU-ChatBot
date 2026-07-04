"""Giai đoạn 3: RAG — truy xuất tài liệu + LLM sinh câu trả lời.

Luồng: câu hỏi -> retrieve top-k chunk (BGE-M3 + ChromaDB) -> ghép Prompt
       -> LLM (Qwen2.5-1.5B-Instruct) đọc tài liệu và trả lời + trích nguồn.

Cách dùng:
    conda activate test
    python src/Phase3-RAG/rag.py "Em bị CPA 1.5 có bị đuổi học không?"
    python src/Phase3-RAG/rag.py            # chế độ hỏi-đáp liên tục (gõ 'thoat' để dừng)
"""
from __future__ import annotations
import argparse
import sys as _sys, pathlib as _pathlib

_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import retriever

SYSTEM_PROMPT = (
    "Bạn là trợ lý cố vấn học tập của Trường Đại học Công nghiệp Việt - Hung. "
    "Hãy trả lời câu hỏi của sinh viên DỰA HOÀN TOÀN trên phần TÀI LIỆU bên dưới.\n\n"
    "Cách trả lời:\n"
    "1. Trả lời TRỰC TIẾP câu hỏi ngay ở câu đầu tiên.\n"
    "2. Nếu câu hỏi nêu con số cụ thể của sinh viên (CPA, điểm, số tín chỉ, số lần "
    "cảnh báo...), hãy SO SÁNH con số đó với đúng mốc quy định trong tài liệu rồi mới "
    "kết luận. Phân biệt rõ các mức xử lý khác nhau — ví dụ 'cảnh báo học tập' KHÁC "
    "'buộc thôi học'; đừng nhầm lẫn mốc điểm của mức này sang mức kia.\n"
    "3. Giải thích ngắn gọn căn cứ và nêu bước hành động cụ thể cho sinh viên nếu phù hợp.\n"
    "4. Ghi nguồn [1], [2]... cho thông tin đã dùng.\n\n"
    "Ràng buộc:\n"
    "- Chỉ dùng thông tin trong TÀI LIỆU; TUYỆT ĐỐI không bịa.\n"
    "- Nếu tài liệu không đủ thông tin, nói rõ là chưa tìm thấy trong quy định và khuyên "
    "sinh viên liên hệ phòng đào tạo / cố vấn học tập.\n"
    "- CHỈ trả lời bằng TIẾNG VIỆT, tuyệt đối KHÔNG chèn tiếng Trung hay tiếng Anh. "
    "Giọng thân thiện, gọi sinh viên là 'em'."
)

_llm = None
_tok = None
MODEL_NAME = config.LLM_MODEL   # có thể override qua CLI --model


def _load_llm():
    global _llm, _tok
    if _llm is None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        print(f"[LLM] Đang tải {MODEL_NAME} ...")
        _tok = AutoTokenizer.from_pretrained(MODEL_NAME)
        _llm = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME, dtype=torch.bfloat16).to("cuda")
        # Nạp LoRA adapter đã fine-tune (nếu có và đang dùng đúng base model)
        if (config.USE_FINETUNED and config.ADAPTER_DIR.exists()
                and MODEL_NAME == config.LLM_MODEL):
            from peft import PeftModel
            _llm = PeftModel.from_pretrained(_llm, str(config.ADAPTER_DIR))
            print(f"[LLM] Đã nạp LoRA adapter cố vấn: {config.ADAPTER_DIR.name}")
        _llm.eval()
        print(f"[LLM] Sẵn sàng trên {next(_llm.parameters()).device}.")
    return _llm, _tok


def _build_context(hits):
    """Ghép các chunk thành khối TÀI LIỆU đánh số + danh sách nguồn."""
    blocks, sources = [], []
    for i, h in enumerate(hits, 1):
        src = retriever.format_source(h["meta"])
        blocks.append(f"[{i}] (Nguồn: {src})\n{h['text']}")
        sources.append(f"[{i}] {src}")
    return "\n\n".join(blocks), sources


def answer(query: str, k: int = None, verbose: bool = True):
    k = k or config.RAG_TOP_K
    hits = retriever.retrieve(query, k)   # đã rerank, lấy top-k tốt nhất
    context, sources = _build_context(hits)
    user_msg = f"TÀI LIỆU:\n{context}\n\nCÂU HỎI: {query}"

    llm, tok = _load_llm()
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}]
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok([text], return_tensors="pt").to(llm.device)
    gen = llm.generate(
        **inputs, max_new_tokens=config.LLM_MAX_NEW_TOKENS,
        do_sample=True, temperature=config.LLM_TEMPERATURE, top_p=0.9,
        pad_token_id=tok.eos_token_id,
    )
    reply = tok.decode(gen[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

    if verbose:
        print("\n" + "=" * 70)
        print("💬 TRẢ LỜI:\n")
        print(reply)
        print("\n📚 NGUỒN THAM KHẢO:")
        for s in sources:
            print("   " + s)
        print("=" * 70 + "\n")
    return reply, sources


def main():
    global MODEL_NAME
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", help="Câu hỏi (bỏ trống để vào chế độ hỏi-đáp liên tục)")
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--model", default=None,
                    help="Ghi đè LLM, vd: Qwen/Qwen2.5-3B-Instruct")
    ap.add_argument("--base", action="store_true",
                    help="Dùng model gốc, KHÔNG nạp LoRA adapter (để so sánh)")
    args = ap.parse_args()
    if args.model:
        MODEL_NAME = args.model
    if args.base:
        config.USE_FINETUNED = False

    if args.query:
        answer(args.query, args.k)
        return

    print("=== Cố vấn học tập VIU (RAG) — gõ 'thoat' để dừng ===")
    _load_llm()  # nạp sẵn để lần hỏi đầu không chờ lâu
    while True:
        try:
            q = input("\n🧑 Sinh viên: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"thoat", "thoát", "exit", "quit"}:
            break
        if q:
            answer(q, args.k)


if __name__ == "__main__":
    main()
