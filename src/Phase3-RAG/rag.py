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
    "2. Phải nêu ĐẦY ĐỦ và CHÍNH XÁC các chi tiết cụ thể có trong tài liệu: tên gọi, "
    "con số, mốc điểm, bậc, thời hạn, điều kiện kèm theo. Nếu tài liệu liệt kê nhiều "
    "mục (a, b, c...) thì phải liệt kê ĐỦ các mục, không tóm tắt chung chung. "
    "TUYỆT ĐỐI không trả lời kiểu 'theo danh mục được công nhận' mà phải nêu rõ danh "
    "mục đó gồm những gì theo đúng tài liệu.\n"
    "3. Nếu câu hỏi nêu con số cụ thể của sinh viên (CPA, điểm, số tín chỉ, số lần "
    "cảnh báo...), hãy SO SÁNH con số đó với đúng mốc quy định trong tài liệu rồi mới "
    "kết luận. Phân biệt rõ các mức xử lý khác nhau — ví dụ 'cảnh báo học tập' KHÁC "
    "'buộc thôi học'; đừng nhầm lẫn mốc điểm của mức này sang mức kia.\n"
    "4. Nêu bước hành động cụ thể cho sinh viên nếu phù hợp.\n"
    "5. Khi dẫn căn cứ, phải gọi ĐÚNG TÊN VĂN BẢN kèm số Điều — ví dụ: 'theo Quy "
    "định về chuẩn đầu ra ngoại ngữ và tin học (Điều 3)'. TUYỆT ĐỐI KHÔNG viết "
    "'theo Tài liệu [1]', 'Tài liệu 2' hay bất kỳ cách đánh số nào; người đọc "
    "không biết các số đó là gì.\n\n"
    "Ràng buộc:\n"
    "- Chỉ dùng thông tin trong TÀI LIỆU; TUYỆT ĐỐI không bịa.\n"
    "- CHỈ dùng những đoạn thực sự trả lời đúng câu hỏi. Các đoạn nói về chủ đề "
    "KHÁC thì bỏ qua, KHÔNG trộn vào câu trả lời. Ví dụ: hỏi về ngoại ngữ/tiếng "
    "Anh thì không đưa nội dung về tin học (MOS, ICDL, IC3, năng lực số) vào, và "
    "ngược lại.\n"
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


def _gen_kwargs(tok):
    """Tham số sinh văn bản.

    Với chatbot trích dẫn quy chế, lấy mẫu ngẫu nhiên là hại chứ không lợi: cùng
    một câu hỏi có thể ra hai câu trả lời khác nhau, và ở nhiệt độ thấp mô hình
    vẫn thỉnh thoảng chọn token lệch rồi bịa tiếp cả đoạn quy định không có thật.
    Đặt LLM_TEMPERATURE = 0 để chuyển sang giải mã tất định (greedy).
    """
    kw = {"max_new_tokens": config.LLM_MAX_NEW_TOKENS,
          "pad_token_id": tok.eos_token_id}
    if config.LLM_TEMPERATURE and config.LLM_TEMPERATURE > 0:
        kw.update(do_sample=True, temperature=config.LLM_TEMPERATURE, top_p=0.9)
    else:
        kw.update(do_sample=False)
    return kw


def _select_for_context(hits):
    """Chỉ giữ những đoạn có điểm xếp hạng đủ gần đoạn đầu bảng.

    Truy xuất lấy dư đoạn để không bỏ sót, nhưng đưa hết vào ngữ cảnh thì đoạn
    lạc đề (thường là "Phạm vi điều chỉnh", dài mấy trăm từ) lấn át đoạn trả lời
    đúng và mô hình quay sang bịa. Ngưỡng đặt theo CONTEXT_MIN_RATIO.
    """
    scores = [h.get("rerank_score") for h in hits]
    if not hits or any(s is None for s in scores):
        return hits                      # không có điểm xếp hạng -> giữ nguyên
    top = scores[0]
    if not top or top <= 0:
        return hits
    ratio = getattr(config, "CONTEXT_MIN_RATIO", 0.25)
    kept = [h for h, s in zip(hits, scores) if s >= top * ratio]
    return kept or [hits[0]]             # luôn giữ ít nhất đoạn tốt nhất


def _build_context(hits):
    """Ghép các chunk thành khối TÀI LIỆU + danh sách nguồn đã gộp theo văn bản.

    Mỗi đoạn được gắn nhãn bằng TÊN VĂN BẢN và số Điều (không dùng số thứ tự [1],
    [2]) để mô hình trích dẫn theo tên văn bản, ví dụ "theo Quy định về chuẩn đầu
    ra ngoại ngữ và tin học (Điều 3)".
    """
    # Trích nguồn phải khớp đúng những đoạn ĐÃ đưa vào ngữ cảnh. Liệt kê cả đoạn
    # đã bị lọc bỏ thì sinh viên mở ra sẽ không thấy nội dung được nhắc tới.
    used = _select_for_context(hits)
    blocks = []
    for h in used:
        meta = h["meta"]
        doc = retriever._clean_doc_name(meta.get("source", ""))
        dieu = meta.get("dieu")
        label = f"{doc} — {dieu}" if dieu else doc
        blocks.append(f"### {label}\n{h['text']}")
    return "\n\n".join(blocks), retriever.group_sources(used)


def answer(query: str, k: int = None, verbose: bool = True):
    k = k or config.RAG_TOP_K
    hits = retriever.retrieve(query, k)   # đã hợp nhất 2 nguồn + rerank
    if not retriever.has_relevant(hits):
        if verbose:
            print("\n" + "=" * 70)
            print("💬 TRẢ LỜI:\n")
            print(NO_ANSWER)
            print("=" * 70 + "\n")
        return NO_ANSWER, []

    context, sources = _build_context(hits)
    user_msg = f"TÀI LIỆU:\n{context}\n\nCÂU HỎI: {query}"

    llm, tok = _load_llm()
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}]
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok([text], return_tensors="pt").to(llm.device)
    gen = llm.generate(**inputs, **_gen_kwargs(tok))
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


NO_ANSWER = (
    "Em ơi, cô/thầy chưa tìm thấy nội dung này trong các văn bản quy định hiện có "
    "của Nhà trường. Em vui lòng liên hệ Phòng Quản lý đào tạo hoặc cố vấn học tập "
    "của lớp để được giải đáp chính xác nhé."
)


def _build_messages(query: str, history=None):
    """Ghép system + lịch sử hội thoại + tài liệu truy xuất cho câu hỏi hiện tại.

    Trả về (messages, sources, relevant). relevant=False nghĩa là không có đoạn nào
    đủ liên quan -> phía gọi nên trả lời NO_ANSWER thay vì để mô hình suy diễn.
    """
    hits = retriever.retrieve(query, config.RAG_TOP_K)
    relevant = retriever.has_relevant(hits)
    context, sources = _build_context(hits)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for u, a in (history or []):
        messages.append({"role": "user", "content": u})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": f"TÀI LIỆU:\n{context}\n\nCÂU HỎI: {query}"})
    return messages, sources, relevant


def answer_stream(query: str, history=None):
    """Generator cho giao diện chat: yield (văn bản đang sinh dần, danh sách nguồn).

    history: danh sách các cặp (câu hỏi, câu trả lời) trước đó.
    """
    import threading
    from transformers import TextIteratorStreamer

    llm, tok = _load_llm()
    messages, sources, relevant = _build_messages(query, history)
    if not relevant:
        # Không có đoạn nào đủ liên quan -> không để mô hình suy diễn từ tài liệu lạc đề
        yield NO_ANSWER, []
        return
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok([text], return_tensors="pt").to(llm.device)
    streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True)
    kwargs = dict(**inputs, **_gen_kwargs(tok), streamer=streamer)
    threading.Thread(target=llm.generate, kwargs=kwargs).start()
    acc = ""
    for piece in streamer:
        acc += piece
        yield acc, sources


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
