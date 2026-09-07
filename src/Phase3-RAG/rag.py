"""Giai đoạn 3: RAG — truy xuất tài liệu + LLM sinh câu trả lời.

Luồng: câu hỏi -> mở rộng truy vấn -> lấy ứng viên (BGE-M3 + BM25, hợp nhất RRF)
       -> rerank cross-encoder -> ghép trọn Điều vào ngữ cảnh
       -> LLM (Qwen3-14B, 4-bit) đọc tài liệu và trả lời + trích nguồn.

Cách dùng:
    conda activate test
    python src/Phase3-RAG/rag.py "Em bị CPA 1.5 có bị đuổi học không?"
    python src/Phase3-RAG/rag.py            # chế độ hỏi-đáp liên tục (gõ 'thoat' để dừng)
"""
from __future__ import annotations
import argparse
import re
import sys as _sys, pathlib as _pathlib

_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import retriever
import curriculum_index

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
    "4. Khi sinh viên KỂ HOÀN CẢNH của mình rồi hỏi nên làm gì (ví dụ: 'em còn nợ "
    "3 môn và GPA 1.9, làm sao ra trường đúng hạn'), BẮT BUỘC phải tư vấn chứ không "
    "được chỉ trích quy định rồi thôi. Trả lời theo trình tự: (a) đối chiếu tình "
    "trạng của em với mốc quy định trong tài liệu — đang an toàn, bị cảnh báo, hay "
    "sắp bị buộc thôi học; (b) nêu các LỰA CHỌN mà quy chế cho phép, kèm điều kiện "
    "của từng lựa chọn: học lại học phần chưa đạt, học cải thiện điểm, đăng ký thêm "
    "tín chỉ trong giới hạn cho phép, học kỳ phụ, học trực tuyến...; (c) nêu các "
    "bước em cần làm, đánh số rõ ràng. Nếu tài liệu thiếu MỘT phần dữ kiện thì vẫn "
    "phải tư vấn bằng phần đã có, chỉ nói rõ phần nào cần hỏi thêm — TUYỆT ĐỐI "
    "không lấy cớ thiếu một chi tiết để từ chối cả câu hỏi.\n"
    "5. Khi dẫn căn cứ, phải gọi ĐÚNG TÊN VĂN BẢN kèm số Điều — ví dụ: 'theo Quy "
    "định về chuẩn đầu ra ngoại ngữ và tin học (Điều 3)'. TUYỆT ĐỐI KHÔNG viết "
    "'theo Tài liệu [1]', 'Tài liệu 2' hay bất kỳ cách đánh số nào; người đọc "
    "không biết các số đó là gì. Mỗi khối tài liệu mở đầu bằng dòng '### <số "
    "Điều>, <tên văn bản>' — đó là cặp ĐI LIỀN NHAU, hãy chép đúng cả cặp. TUYỆT "
    "ĐỐI KHÔNG lấy số Điều của khối này ghép với tên văn bản của khối khác. Tên "
    "văn bản CHỈ được lấy từ dòng '###', KHÔNG được lấy từ chữ nằm trong phần "
    "nội dung: nội dung một văn bản thường nhắc tên văn bản khác (ví dụ Điều 3 "
    "của Quy định về học phí có câu 'theo quy chế đào tạo'), nhắc không có nghĩa "
    "đoạn đó thuộc về văn bản được nhắc.\n\n"
    "6. Nếu TÀI LIỆU có khối 'DỮ KIỆN TRA CỨU TỪ KẾ HOẠCH ĐÀO TẠO' thì đó là số "
    "liệu đã tra sẵn, CHÍNH XÁC — hãy dùng đúng con số/danh sách trong đó, không "
    "tự cộng lại và không lấy số ở chỗ khác. Nếu khối này ghi rõ kho dữ liệu KHÔNG "
    "có ngành nào đó, phải nói thẳng là chưa có dữ liệu ngành đó, TUYỆT ĐỐI không "
    "tự nghĩ ra số tín chỉ hay danh sách môn học.\n\n"
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


def _adapter_base() -> str | None:
    """Base model mà LoRA adapter trong ADAPTER_DIR được huấn luyện trên đó."""
    import json
    cfg = config.ADAPTER_DIR / "adapter_config.json"
    if not cfg.exists():
        return None
    try:
        return json.loads(cfg.read_text(encoding="utf-8")).get("base_model_name_or_path")
    except (ValueError, OSError):
        return None


def _load_llm():
    global _llm, _tok
    if _llm is None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        print(f"[LLM] Đang tải {MODEL_NAME} ...")
        _tok = AutoTokenizer.from_pretrained(MODEL_NAME)
        kw = {}
        if getattr(config, "LLM_LOAD_4BIT", False):
            # NF4 + double quant: 14B từ ~29 GB (bf16) xuống 9,97 GB đo thực tế,
            # vẫn dư chỗ cho BGE-M3 + reranker + ngữ cảnh dài trên card 32 GB.
            from transformers import BitsAndBytesConfig
            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True)
            kw["device_map"] = "cuda:0"
        else:
            kw["dtype"] = torch.bfloat16
        _llm = AutoModelForCausalLM.from_pretrained(MODEL_NAME, **kw)
        if not getattr(config, "LLM_LOAD_4BIT", False):
            _llm = _llm.to("cuda")
        # Nạp LoRA adapter đã fine-tune — CHỈ khi nó được train trên đúng base này.
        # Adapter train trên 3B mà nạp vào 14B thì kích thước tầng không khớp; kiểm
        # bằng chính adapter_config.json thay vì so với config.LLM_MODEL, vì
        # LLM_MODEL đổi thì phép so cũ vẫn "khớp" và nạp nhầm.
        if config.USE_FINETUNED and config.ADAPTER_DIR.exists():
            base = _adapter_base()
            if base and base != MODEL_NAME:
                print(f"[LLM] ⚠ Bỏ qua adapter {config.ADAPTER_DIR.name}: nó train trên "
                      f"{base}, không khớp {MODEL_NAME}. Đang chạy MODEL GỐC.")
            else:
                from peft import PeftModel
                _llm = PeftModel.from_pretrained(_llm, str(config.ADAPTER_DIR))
                print(f"[LLM] Đã nạp LoRA adapter cố vấn: {config.ADAPTER_DIR.name}")
        _llm.eval()
        print(f"[LLM] Sẵn sàng trên {next(_llm.parameters()).device}.")
    return _llm, _tok


def _chat_text(tok, messages):
    """Dựng prompt theo chat template, tắt chế độ suy nghĩ của Qwen3 nếu có.

    Qwen3 mặc định chèn khối <think>...</think> và sinh hàng trăm token suy luận
    trước câu trả lời. Tài liệu đã nằm sẵn trong ngữ cảnh nên khối đó chỉ làm chậm
    và lọt vào giao diện. Model không phải Qwen3 sẽ không nhận tham số này -> bỏ qua.
    """
    kw = {"tokenize": False, "add_generation_prompt": True}
    if not getattr(config, "LLM_ENABLE_THINKING", True):
        try:
            return tok.apply_chat_template(messages, enable_thinking=False, **kw)
        except TypeError:
            pass       # template không nhận tham số này (model không phải Qwen3)
    return tok.apply_chat_template(messages, **kw)


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think(text: str) -> str:
    """Bỏ khối suy nghĩ nếu mô hình vẫn sinh ra (phòng khi template không tắt được)."""
    return _THINK_RE.sub("", text).lstrip()


# Các cách mô hình nói "tài liệu không có nội dung này". Gom lại từ đầu ra thực tế
# của Qwen3-14B trên 8 câu ngoài phạm vi, nó không dùng một khuôn cố định nào.
_TU_CHOI_RE = re.compile(
    r"tài liệu (không|chưa) (cung cấp|có|đề cập|nêu|nhắc)|"
    r"(không|chưa) tìm thấy|(không|chưa) có (thông tin|nội dung|quy định)|"
    r"(không|chưa) được đề cập|ngoài phạm vi", re.IGNORECASE)


def _la_tu_choi(reply: str, by_dieu: dict) -> bool:
    """Câu trả lời có phải LỜI TỪ CHỐI thuần không (để còn ẩn danh sách nguồn).

    Không thể chỉ dò cụm từ chối: câu "GPA 1.9 có tốt nghiệp được không" trả lời
    rất hữu ích, có dẫn Điều 8, mà vẫn chứa "tài liệu không nêu rõ mốc GPA cụ thể".
    Ẩn nguồn của câu đó là sai. Vì vậy chỉ coi là từ chối thuần khi vừa có cụm từ
    chối VỪA không dẫn tên văn bản nào trong ngữ cảnh.
    """
    if not _TU_CHOI_RE.search(reply or ""):
        return False
    docs = {d for v in by_dieu.values() for d in v}
    return not any(d and d in reply for d in docs)


_HEADER_RE = re.compile(r"^### (Điều\s*(\d+)),\s*(.+)$", re.MULTILINE)


def _ctx_dieu_map(context: str) -> dict:
    """Từ khối ngữ cảnh, lập bảng: số Điều -> tập tên văn bản THỰC SỰ chứa Điều đó."""
    by_dieu = {}
    for _, num, doc in _HEADER_RE.findall(context):
        by_dieu.setdefault(num, set()).add(doc.strip())
    return by_dieu


def _fix_citations(reply: str, by_dieu: dict) -> str:
    """Sửa trích dẫn ghép nhầm số Điều của văn bản này với tên văn bản khác.

    Siết prompt KHÔNG chữa được lỗi này (đo thực tế: sau khi thêm ràng buộc, câu
    "Em trượt môn thì phải làm sao?" vẫn ghi "Điều 3 của Quy chế đào tạo trình độ
    đại học" trong khi Điều 3 đó thuộc Quy định về học phí). Nguyên nhân: thân
    Điều 3 có câu "theo quy chế đào tạo", mô hình nhặt tên văn bản từ nội dung.
    Giải mã tất định nên nó lặp lại y hệt mỗi lần.

    Vậy nên đối chiếu bằng code: cặp (số Điều, tên văn bản) nào không có trong ngữ
    cảnh thì thay tên văn bản bằng tên đúng — chỉ thay khi trong ngữ cảnh số Điều
    đó thuộc về DUY NHẤT một văn bản, còn nhập nhằng thì để nguyên, không đoán.
    """
    docs = {d for s in by_dieu.values() for d in s}
    if not docs:
        return reply
    # Tên dài đặt trước để không khớp trúng phần đầu của một tên dài hơn.
    alt = "|".join(re.escape(d) for d in sorted(docs, key=len, reverse=True))

    def _right_name(num, named):
        owners = by_dieu.get(num)
        if not owners or named in owners or len(owners) != 1:
            return None                 # đúng rồi / không có căn cứ / nhập nhằng
        return next(iter(owners))

    # Dạng 1: "... Điều 3 của <tên văn bản>"   (dấu chấm chặn không cho vắt câu)
    def _f1(m):
        fix = _right_name(m.group(1), m.group(3))
        return f"Điều {m.group(1)}{m.group(2)}{fix}" if fix else m.group(0)

    reply = re.sub(rf"Điều\s*(\d+)([^.]{{0,25}}?)({alt})", _f1, reply)

    # Dạng 2: "... <tên văn bản> (Điều 3)"
    def _f2(m):
        fix = _right_name(m.group(3), m.group(1))
        return f"{fix}{m.group(2)}Điều {m.group(3)}" if fix else m.group(0)

    return re.sub(rf"({alt})([^.]{{0,15}}?)Điều\s*(\d+)", _f2, reply)


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


_ANAPHORA_RE = re.compile(
    r"\b(đó|này|kia|vậy|nêu trên|ở trên|nói trên|như trên|còn|thế còn)\b", re.IGNORECASE)


def _retrieval_query(query: str, history=None) -> str:
    """Câu hỏi truy xuất, có ghép ngữ cảnh cho câu hỏi NỐI TIẾP.

    Sinh viên hay hỏi tiếp kiểu "danh mục được công nhận là gồm những chứng chỉ
    gì" — câu này thiếu chủ đề nên truy xuất trượt hoàn toàn và chatbot trả lời
    "chưa tìm thấy", dù câu hỏi trước đó đã nói rõ là về chứng chỉ ngoại ngữ.
    Khi câu hỏi ngắn hoặc có từ thay thế ("đó", "này", "vậy"), ghép thêm câu hỏi
    liền trước để truy xuất bắt đúng chủ đề.
    """
    if not history:
        return query
    if len(query.split()) <= 12 or _ANAPHORA_RE.search(query):
        prev_q = (history[-1][0] or "").strip()
        if prev_q:
            return f"{prev_q} {query}"
    return query


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


def _build_context(hits, question: str = ""):
    """Ghép các chunk thành khối TÀI LIỆU + danh sách nguồn đã gộp theo văn bản.

    Mỗi đoạn được gắn nhãn bằng TÊN VĂN BẢN và số Điều (không dùng số thứ tự [1],
    [2]) để mô hình trích dẫn theo tên văn bản, ví dụ "theo Quy định về chuẩn đầu
    ra ngoại ngữ và tin học (Điều 3)".
    """
    # Trích nguồn phải khớp đúng những đoạn ĐÃ đưa vào ngữ cảnh. Liệt kê cả đoạn
    # đã bị lọc bỏ thì sinh viên mở ra sẽ không thấy nội dung được nhắc tới.
    used = _select_for_context(hits)
    blocks = []
    # Câu hỏi về kế hoạch đào tạo được TRA CỨU trực tiếp trên dữ liệu bảng đã bóc,
    # vì con số như "tổng tín chỉ toàn khoá" không nằm sẵn ở đoạn văn nào — phải
    # cộng nhiều học kỳ, mà mô hình tự cộng thì bịa.
    facts = curriculum_index.facts_for(question) if question else ""
    if facts:
        blocks.append("### DỮ KIỆN TRA CỨU TỪ KẾ HOẠCH ĐÀO TẠO (chính xác, ưu tiên dùng)\n"
                      + facts)

    expand = getattr(config, "PARENT_EXPAND", False)
    budget = getattr(config, "CONTEXT_MAX_WORDS", 3500)
    spent = sum(len(b.split()) for b in blocks)
    seen_dieu = set()       # (văn bản, Điều) đã ghép trọn -> không lặp lại
    kept = []
    for h in used:
        meta = h["meta"]
        doc = retriever._clean_doc_name(meta.get("source", ""))
        dieu = meta.get("dieu")
        key = (meta.get("source", ""), dieu or "")
        if dieu and key in seen_dieu:
            continue        # đoạn này là mẩu khác của Điều đã ghép trọn ở trên
        text = h["text"]
        if expand and dieu:
            # Đoạn trúng thường chỉ là một mẩu của Điều. Ghép trọn để mô hình đọc
            # đủ các khoản — thiếu khoản là trả lời thiếu điều kiện.
            full = retriever.full_dieu_text(meta)
            # Chỉ nhận bản đầy đủ nếu còn đủ ngân sách; hết thì dùng mẩu gốc.
            if full and spent + len(full.split()) <= budget:
                text = full
            seen_dieu.add(key)
        n = len(text.split())
        if kept and spent + n > budget:
            break           # luôn giữ ít nhất đoạn hạng 1 dù nó dài quá trần
        spent += n
        # Nhãn viết ĐÚNG dạng trích dẫn mong muốn, số Điều đứng LIỀN tên văn bản.
        # Dạng cũ "<tên văn bản> — Điều 3" tách đôi hai thứ, đo được mô hình ghép
        # nhầm: lấy "Điều 3" của Quy định học phí gán cho Quy chế đào tạo. Đặt sẵn
        # chuỗi trích dẫn hoàn chỉnh thì mô hình chỉ việc chép lại.
        label = f"{dieu}, {doc}" if dieu else doc
        blocks.append(f"### {label}\n{text}")
        kept.append(h)
    return "\n\n".join(blocks), retriever.group_sources(kept or used[:1])


def _is_relevant(query: str, hits) -> bool:
    """Có căn cứ để trả lời không.

    Ngoài tín hiệu truy xuất trên văn bản, còn tính cả trường hợp tra được dữ kiện
    trong kế hoạch đào tạo — câu "ngành X tổng bao nhiêu tín chỉ" thường không
    khớp đoạn văn nào nên nếu chỉ nhìn truy xuất sẽ bị từ chối oan.
    """
    return retriever.has_relevant(hits) or bool(curriculum_index.facts_for(query))


def answer(query: str, k: int = None, verbose: bool = True):
    k = k or config.RAG_TOP_K
    hits = retriever.retrieve(query, k)   # đã hợp nhất 2 nguồn + rerank
    if not _is_relevant(query, hits):
        if verbose:
            print("\n" + "=" * 70)
            print("💬 TRẢ LỜI:\n")
            print(NO_ANSWER)
            print("=" * 70 + "\n")
        return NO_ANSWER, []

    context, sources = _build_context(hits, query)
    user_msg = f"TÀI LIỆU:\n{context}\n\nCÂU HỎI: {query}"

    llm, tok = _load_llm()
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}]
    text = _chat_text(tok, messages)
    inputs = tok([text], return_tensors="pt").to(llm.device)
    gen = llm.generate(**inputs, **_gen_kwargs(tok))
    reply = _strip_think(
        tok.decode(gen[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip())
    by_dieu = _ctx_dieu_map(context)
    reply = _fix_citations(reply, by_dieu)
    if _la_tu_choi(reply, by_dieu):
        sources = []      # đừng trích nguồn cho một lời từ chối

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
    hits = retriever.retrieve(_retrieval_query(query, history), config.RAG_TOP_K)
    relevant = _is_relevant(query, hits)
    context, sources = _build_context(hits, query)
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
    text = _chat_text(tok, messages)
    inputs = tok([text], return_tensors="pt").to(llm.device)
    streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True)
    kwargs = dict(**inputs, **_gen_kwargs(tok), streamer=streamer)
    threading.Thread(target=llm.generate, kwargs=kwargs).start()
    # Bảng đối chiếu trích dẫn dựng từ đúng khối tài liệu mô hình đang đọc.
    by_dieu = _ctx_dieu_map(messages[-1]["content"])
    acc = ""
    for piece in streamer:
        acc += piece
        # Khối <think> (nếu có) phải bị chặn NGAY khi đang chảy chữ, không thể đợi
        # sinh xong mới cắt — nếu không sinh viên nhìn thấy phần suy luận thô.
        if "<think>" in acc and "</think>" not in acc:
            continue
        # Sửa trích dẫn ngay trong lúc chảy chữ: mẫu chỉ khớp khi tên văn bản đã
        # ra đủ, nên phần đang gõ dở không bị đụng vào.
        da_sua = _fix_citations(_strip_think(acc), by_dieu)
        yield da_sua, ([] if _la_tu_choi(da_sua, by_dieu) else sources)


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
