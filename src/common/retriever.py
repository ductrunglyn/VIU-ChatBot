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


def _load():
    global _model, _col
    if _model is None:
        import chromadb
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(config.EMBED_MODEL, device="cuda")
        client = chromadb.PersistentClient(path=str(config.VECTOR_DB_DIR))
        _col = client.get_collection(config.COLLECTION_NAME)
    return _model, _col


def _load_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(config.RERANK_MODEL, device="cuda")
    return _reranker


def retrieve(query: str, k: int = 5, candidates: int = None):
    """Trả về top-k {score, rerank_score, text, meta}. score = độ tương đồng dense (cosine)."""
    model, col = _load()
    n = candidates or (config.RETRIEVE_CANDIDATES if config.RERANK_ENABLED else k)
    q_emb = model.encode([query], normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=q_emb, n_results=n,
                    include=["documents", "metadatas", "distances"])
    hits = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append({"score": 1 - dist, "rerank_score": None, "text": doc, "meta": meta})

    if config.RERANK_ENABLED and hits:
        reranker = _load_reranker()
        scores = reranker.predict([(query, h["text"]) for h in hits])
        for h, s in zip(hits, scores):
            h["rerank_score"] = float(s)
        hits.sort(key=lambda h: h["rerank_score"], reverse=True)

    return hits[:k]


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
