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


def format_source(meta: dict) -> str:
    """Chuỗi trích dẫn nguồn gọn: 'tên file | Điều X | tiêu đề'."""
    parts = [meta.get("source"), meta.get("dieu"), meta.get("heading")]
    return " | ".join(p for p in parts if p)
