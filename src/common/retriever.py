"""Truy xuất chunk liên quan từ ChromaDB — dùng chung cho Phase2 (search) và Phase3 (RAG).

Quy trình để tăng độ chính xác:
  0) Mở rộng truy vấn: ghép thêm thuật ngữ pháp quy tương ứng với khẩu ngữ của
     sinh viên ("đuổi học" -> "buộc thôi học"). CHỈ dùng cho BM25 — xem retrieve().
  1) Lấy ứng viên từ HAI nguồn: dense (BGE-M3) và từ khóa (BM25), lấy dư tới mức
     gần như quét cả kho (kho chỉ 183 đoạn).
  2) Hợp nhất bằng RRF (Reciprocal Rank Fusion) — gộp theo THỨ HẠNG nên không
     phải chuẩn hóa hai thang điểm vốn không cùng đơn vị.
  3) Rerank (cross-encoder BGE-reranker): chấm lại từng cặp (câu hỏi, đoạn) và
     xếp hạng lại -> lấy top-k. Bước này phân biệt tốt hơn hẳn dense đơn thuần.
  4) (rag.py) Mở rộng đoạn trúng thành TRỌN VẸN một Điều trước khi đưa vào ngữ cảnh.

Các model nạp 1 lần (singleton).
"""
from __future__ import annotations

import config

_model = None
_col = None
_reranker = None
_bm25 = None
_bm25_docs = None      # [(text, meta)] song song với chỉ mục BM25
_corpus = None         # [{"id","text","meta"}] toàn kho, nạp 1 lần
_dieu_index = None     # (source, dieu) -> [phần đã sắp theo p1,p2,... ]


def _load():
    global _model, _col
    if _model is None:
        import chromadb
        import torch
        from sentence_transformers import SentenceTransformer
        kw = ({"model_kwargs": {"dtype": torch.float16}}
              if getattr(config, "RERANK_FP16", False) else {})
        _model = SentenceTransformer(config.EMBED_MODEL, device="cuda", **kw)
        client = chromadb.PersistentClient(path=str(config.VECTOR_DB_DIR))
        _col = client.get_collection(config.COLLECTION_NAME)
    return _model, _col


def _tokenize(text: str):
    """Tách từ đơn giản cho BM25: hạ chữ thường, tách theo ký tự không phải chữ/số."""
    import re
    import unicodedata
    text = unicodedata.normalize("NFC", text.lower())
    return [t for t in re.split(r"[^0-9a-zà-ỹ]+", text) if t]


def _load_corpus():
    """Nạp TOÀN BỘ đoạn (id, text, meta) một lần — dùng chung cho BM25 và ghép Điều.

    Trước đây BM25 tự gọi col.get() riêng và không lấy id, nên không biết một đoạn
    là phần thứ mấy của Điều. Gom về một chỗ để cả hai việc dùng chung một bản.
    """
    global _corpus
    if _corpus is None:
        _, col = _load()
        data = col.get(include=["documents", "metadatas"])
        _corpus = [{"id": i, "text": d, "meta": m}
                   for i, d, m in zip(data["ids"], data["documents"], data["metadatas"])]
    return _corpus


def _part_no(chunk_id: str) -> int:
    """Số thứ tự phần trong một Điều: '...::Điều 7::p3' -> 3. Không có hậu tố -> 0."""
    import re as _r
    m = _r.search(r"::p(\d+)$", chunk_id or "")
    return int(m.group(1)) if m else 0


def _load_dieu_index():
    """Gom các phần của cùng một Điều lại, sắp đúng thứ tự p1, p2, p3...

    Điều dài bị cắt nhỏ lúc chunk nên đoạn trúng thường chỉ là một mẩu. Có chỉ mục
    này thì rag.py ghép lại được trọn Điều để mô hình đọc đủ các khoản.
    """
    global _dieu_index
    if _dieu_index is None:
        idx = {}
        for e in _load_corpus():
            meta = e["meta"] or {}
            key = (meta.get("source") or "", meta.get("dieu") or "")
            if not key[1]:
                continue          # đoạn không thuộc Điều nào (bảng kế hoạch đào tạo)
            idx.setdefault(key, []).append(e)
        for v in idx.values():
            v.sort(key=lambda e: _part_no(e["id"]))
        _dieu_index = idx
    return _dieu_index


def _load_bm25():
    """Dựng chỉ mục BM25 trên toàn bộ đoạn trong cơ sở dữ liệu (chạy 1 lần)."""
    global _bm25, _bm25_docs
    if _bm25 is None:
        from rank_bm25 import BM25Okapi
        corpus = _load_corpus()
        _bm25_docs = [(e["text"], e["meta"]) for e in corpus]
        _bm25 = BM25Okapi([_tokenize(t) for t, _ in _bm25_docs])
    return _bm25, _bm25_docs


def expand_query(query: str) -> str:
    """Ghép thêm thuật ngữ pháp quy tương ứng với khẩu ngữ trong câu hỏi.

    Sinh viên viết "em bị đuổi học không", văn bản viết "buộc thôi học" — BM25
    không có từ nào chung, dense thì mờ. Chỉ THÊM từ, không thay thế, nên câu hỏi
    vốn đã dùng đúng thuật ngữ không bị ảnh hưởng.
    """
    if not getattr(config, "QUERY_EXPANSION", False):
        return query
    low = query.lower()
    extra = []
    for slang, formal in getattr(config, "QUERY_SYNONYMS", {}).items():
        if slang in low:
            for w in formal.split():
                if w.lower() not in low and w not in extra:
                    extra.append(w)
    return f"{query} {' '.join(extra)}" if extra else query


def full_dieu_text(meta: dict) -> str | None:
    """Ghép trọn vẹn một Điều từ các phần của nó, khử câu trùng do chồng lấp.

    Lúc chunk có chồng lấp CHUNK_OVERLAP_WORDS nên phần sau lặp lại vài câu cuối
    của phần trước (đo được 4-5 câu trùng liền đầu mỗi phần). Nối thẳng sẽ ra văn
    bản lặp, vừa tốn token vừa dễ làm mô hình tưởng quy định được nhắc hai lần.
    Khử theo CÂU: giữ thứ tự xuất hiện, bỏ câu đã gặp.
    """
    import re as _r
    key = ((meta or {}).get("source") or "", (meta or {}).get("dieu") or "")
    parts = _load_dieu_index().get(key)
    if not parts or len(parts) == 1:
        return None                      # Điều không bị cắt -> không cần ghép
    seen, out = set(), []
    for e in parts:
        for s in _r.split(r"(?<=[.;:])\s+", e["text"]):
            s = s.strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return " ".join(out)


def _load_reranker():
    global _reranker
    if _reranker is None:
        import torch
        from sentence_transformers import CrossEncoder
        kw = {}
        if getattr(config, "RERANK_FP16", False):
            # Nửa độ chính xác: giảm khoảng một nửa bộ nhớ GPU, độ chính xác
            # xếp hạng gần như không đổi.
            kw["model_kwargs"] = {"dtype": torch.float16}
        _reranker = CrossEncoder(config.RERANK_MODEL, device="cuda", **kw)
    return _reranker


RRF_K = 60      # hằng số làm trơn của RRF; 60 là giá trị chuẩn trong bài gốc


def retrieve(query: str, k: int = 5, candidates: int = None):
    """Truy xuất đoạn liên quan theo bốn tầng.

    0) Mở rộng truy vấn (khẩu ngữ -> thuật ngữ pháp quy).
    1) Lấy ứng viên từ HAI nguồn: tìm ngữ nghĩa (vector) và tìm từ khóa (BM25).
    2) Hợp nhất bằng RRF: điểm = tổng 1/(RRF_K + thứ hạng) trên từng nguồn.
       Gộp theo thứ hạng nên không phải chuẩn hóa cosine với điểm BM25 (hai thang
       khác đơn vị, cách cũ chỉ gộp bằng phép hợp tập nên mất tín hiệu thứ hạng).
    3) Xếp hạng lại bằng cross-encoder, trả về top-k.

    Mỗi phần tử: {score (cosine), bm25, rrf, rerank_score, text, meta}.
    Điểm dense/BM25 vẫn giữ nguyên nghĩa cũ để has_relevant() dùng lại được ngưỡng.
    """
    model, col = _load()
    n = candidates or (config.RETRIEVE_CANDIDATES if config.RERANK_ENABLED else k)
    # Câu mở rộng CHỈ dành cho BM25. Dùng nó cho cả dense là sai và đã gây lỗi
    # thật: câu "Em còn nợ 3 môn và GPA 1.9, nên làm gì để ra trường đúng hạn?"
    # đạt 0,559 với câu gốc (qua ngưỡng 0,55) nhưng chỉ còn 0,538 với câu đã ghép
    # thêm từ khoá -> bị chặn oan, sinh viên nhận câu "chưa tìm thấy quy định".
    # Lý do: embedding là trung bình ngữ nghĩa của CẢ câu, nhồi thêm từ khoá rời
    # rạc thì kéo vector ra khỏi vùng câu hỏi gốc. BM25 thì ngược lại: càng nhiều
    # từ khoá đúng càng khớp.
    q_bm25 = expand_query(query)

    merged = {}     # id -> hit

    def _slot(cid, text, meta):
        if cid not in merged:
            merged[cid] = {"score": None, "bm25": None, "rrf": 0.0,
                           "rerank_score": None, "text": text, "meta": meta}
        return merged[cid]

    # --- Nguồn 1: tìm theo ngữ nghĩa ---
    q_emb = model.encode([query], normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=q_emb, n_results=n,
                    include=["documents", "metadatas", "distances"])
    for rank, (cid, doc, meta, dist) in enumerate(zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])):
        h = _slot(cid, doc, meta)
        h["score"] = 1 - dist
        h["rrf"] += 1.0 / (RRF_K + rank + 1)

    # --- Nguồn 2: tìm theo từ khóa (bắt đúng thuật ngữ: VSTEP, MOS, ICDL...) ---
    if config.HYBRID_ENABLED:
        bm25, _docs = _load_bm25()
        corpus = _load_corpus()
        scores = bm25.get_scores(_tokenize(q_bm25))
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i],
                         reverse=True)[:config.BM25_CANDIDATES]
        for rank, i in enumerate(top_idx):
            if scores[i] <= 0:
                continue
            e = corpus[i]
            h = _slot(e["id"], e["text"], e["meta"])
            h["bm25"] = float(scores[i])
            h["rrf"] += 1.0 / (RRF_K + rank + 1)

    hits = sorted(merged.values(), key=lambda h: h["rrf"], reverse=True)

    # --- Xếp hạng lại toàn bộ ứng viên đã hợp nhất ---
    if config.RERANK_ENABLED and hits:
        reranker = _load_reranker()
        # Chấm bằng câu hỏi GỐC: từ ghép thêm ở bước mở rộng chỉ để tìm cho ra
        # ứng viên, đưa vào cross-encoder sẽ làm nhiễu ngữ nghĩa câu hỏi.
        scores = reranker.predict([(query, h["text"]) for h in hits],
                                  batch_size=getattr(config, "RERANK_BATCH", 8),
                                  show_progress_bar=False)
        for h, s in zip(hits, scores):
            h["rerank_score"] = float(s)
        hits.sort(key=lambda h: h["rerank_score"], reverse=True)

    return hits[:k]


def has_relevant(hits) -> bool:
    """Có đoạn nào đủ liên quan không? Dùng để chặn suy diễn khi kho tri thức thiếu.

    Xét HAI tín hiệu và chấp nhận nếu một trong hai đủ mạnh: điểm xếp hạng lại
    (chính xác nhưng chấm rất thấp với câu hỏi khẩu ngữ dài) và độ tương đồng ngữ
    nghĩa (ổn định hơn khi câu hỏi diễn đạt khác văn bản).
    """
    if not hits:
        return False
    top_rr = hits[0].get("rerank_score")
    top_dense = max((h.get("score") or 0) for h in hits)

    if top_rr is None:                   # không bật rerank -> chỉ dựa vào tương đồng
        return top_dense >= config.RAG_MIN_SCORE
    return (top_rr >= config.RERANK_MIN_SCORE
            or top_dense >= getattr(config, "DENSE_MIN_SCORE", 1.1))


import re as _re


def _clean_doc_name(fname: str) -> str:
    """Tên tài liệu để trích dẫn. Ưu tiên bảng DOC_TITLES, nếu không có thì làm sạch."""
    stem = _re.sub(r"\.(pdf|docx?|xlsx?|txt|md)$", "", fname or "", flags=_re.I)
    titles = getattr(config, "DOC_TITLES", {})
    if stem in titles:
        return titles[stem]

    n = _re.sub(r"^\[[^\]]*\]", "", stem)              # bỏ '[26-08-2022 ...]' đầu
    n = _re.sub(r"^\s*\d+\s*[.)-]\s*", "", n)          # bỏ số thứ tự đầu tên tệp
    n = _re.sub(r"qd-so-[\d-]+", "", n, flags=_re.I)   # bỏ mã 'qd-so-250-0001'
    n = _re.sub(r"[-_]?\d{4,}[-_\d]*", " ", n)          # bỏ chuỗi số dài (mã/ngày)
    n = _re.sub(r"[_]+", " ", n)
    n = _re.sub(r"\s{2,}", " ", n).strip(" -_.·")
    return n or stem.strip()


def _dieu_num(dieu: str):
    m = _re.search(r"\d+", dieu or "")
    return int(m.group()) if m else 10**6


def format_source(meta: dict) -> str:
    """Trích dẫn một đoạn: 'Điều X, <tên tài liệu>'."""
    doc = _clean_doc_name(meta.get("source", ""))
    dieu = meta.get("dieu")
    return f"{dieu}, {doc}" if dieu else doc


def group_sources(hits) -> list:
    """Gộp trích dẫn theo tài liệu để hiển thị ngắn gọn.

    Ví dụ 5 đoạn thuộc cùng một văn bản -> 'Điều 3, 5, 6 — Quy định về chuẩn đầu ra
    ngoại ngữ và tin học' thay vì liệt kê 5 dòng lặp tên tài liệu.
    """
    order, by_doc = [], {}
    for h in hits:
        meta = h.get("meta", {})
        doc = _clean_doc_name(meta.get("source", ""))
        if doc not in by_doc:
            by_doc[doc] = []
            order.append(doc)
        d = meta.get("dieu")
        if d and d not in by_doc[doc]:
            by_doc[doc].append(d)

    out = []
    for doc in order:
        dieus = sorted(by_doc[doc], key=_dieu_num)
        if dieus:
            nums = ", ".join(_re.sub(r"^Điều\s*", "", d) for d in dieus)
            out.append(f"Điều {nums} — {doc}")
        else:
            out.append(doc)
    return out
