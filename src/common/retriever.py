"""Truy xuất chunk liên quan từ ChromaDB — dùng chung cho Phase2 (search) và Phase3 (RAG).

Quy trình 2 bước để tăng độ chính xác:
  1) Dense retrieval (BGE-M3): lấy nhiều ứng viên (RETRIEVE_CANDIDATES).
  2) Rerank (cross-encoder BGE-reranker): chấm lại từng cặp (câu hỏi, đoạn) và
     xếp hạng lại -> lấy top-k. Bước này phân biệt tốt hơn hẳn dense đơn thuần.

Các model nạp 1 lần (singleton).
"""
from __future__ import annotations

import config

_model = None
_col = None
_reranker = None
_bm25 = None
_bm25_docs = None      # [(text, meta)] song song với chỉ mục BM25


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


def _load_bm25():
    """Dựng chỉ mục BM25 trên toàn bộ đoạn trong cơ sở dữ liệu (chạy 1 lần)."""
    global _bm25, _bm25_docs
    if _bm25 is None:
        from rank_bm25 import BM25Okapi
        _, col = _load()
        data = col.get(include=["documents", "metadatas"])
        _bm25_docs = list(zip(data["documents"], data["metadatas"]))
        _bm25 = BM25Okapi([_tokenize(d) for d, _ in _bm25_docs])
    return _bm25, _bm25_docs


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


def retrieve(query: str, k: int = 5, candidates: int = None):
    """Truy xuất đoạn liên quan theo ba tầng.

    1) Lấy ứng viên từ HAI nguồn: tìm ngữ nghĩa (vector) và tìm từ khóa (BM25).
    2) Hợp nhất, loại trùng.
    3) Xếp hạng lại bằng cross-encoder, trả về top-k.

    Mỗi phần tử: {score (cosine), bm25, rerank_score, text, meta}.
    """
    model, col = _load()
    n = candidates or (config.RETRIEVE_CANDIDATES if config.RERANK_ENABLED else k)

    # --- Nguồn 1: tìm theo ngữ nghĩa ---
    q_emb = model.encode([query], normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=q_emb, n_results=n,
                    include=["documents", "metadatas", "distances"])
    merged = {}
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        merged[doc] = {"score": 1 - dist, "bm25": None, "rerank_score": None,
                       "text": doc, "meta": meta}

    # --- Nguồn 2: tìm theo từ khóa (bắt đúng thuật ngữ: VSTEP, MOS, ICDL...) ---
    if config.HYBRID_ENABLED:
        bm25, docs = _load_bm25()
        scores = bm25.get_scores(_tokenize(query))
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i],
                         reverse=True)[:config.BM25_CANDIDATES]
        for i in top_idx:
            if scores[i] <= 0:
                continue
            doc, meta = docs[i]
            if doc in merged:
                merged[doc]["bm25"] = float(scores[i])
            else:
                merged[doc] = {"score": None, "bm25": float(scores[i]),
                               "rerank_score": None, "text": doc, "meta": meta}

    hits = list(merged.values())

    # --- Xếp hạng lại toàn bộ ứng viên đã hợp nhất ---
    if config.RERANK_ENABLED and hits:
        reranker = _load_reranker()
        scores = reranker.predict([(query, h["text"]) for h in hits],
                                  batch_size=getattr(config, "RERANK_BATCH", 8),
                                  show_progress_bar=False)
        for h, s in zip(hits, scores):
            h["rerank_score"] = float(s)
        hits.sort(key=lambda h: h["rerank_score"], reverse=True)

    return hits[:k]


def has_relevant(hits) -> bool:
    """Có đoạn nào đủ liên quan không? Dùng để chặn suy diễn khi kho tri thức thiếu."""
    if not hits:
        return False
    top = hits[0].get("rerank_score")
    if top is None:                      # không bật rerank -> dựa vào cosine
        return (hits[0].get("score") or 0) >= config.RAG_MIN_SCORE
    return top >= config.RERANK_MIN_SCORE


import re as _re


def _clean_doc_name(fname: str) -> str:
    """Biến tên file thành tên tài liệu dễ đọc (bỏ đuôi, mã số, ngày tháng)."""
    n = _re.sub(r"\.(pdf|docx?|xlsx?|txt|md)$", "", fname or "", flags=_re.I)
    n = _re.sub(r"^\[[^\]]*\]", "", n)                 # bỏ '[26-08-2022 ...]' đầu
    n = _re.sub(r"qd-so-[\d-]+", "", n, flags=_re.I)   # bỏ mã 'qd-so-250-0001'
    n = _re.sub(r"[-_]?\d{4,}[-_\d]*", " ", n)          # bỏ chuỗi số dài (mã/ngày)
    n = _re.sub(r"[_]+", " ", n)
    n = _re.sub(r"\s{2,}", " ", n).strip(" -_.·")
    return n or (fname or "").strip()


def format_source(meta: dict) -> str:
    """Trích dẫn gọn: 'Điều X, <tên tài liệu>' (KHÔNG kèm tên file)."""
    doc = _clean_doc_name(meta.get("source", ""))
    dieu = meta.get("dieu")
    return f"{dieu}, {doc}" if dieu else doc
