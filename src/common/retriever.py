"""Truy xuất chunk liên quan từ ChromaDB — dùng chung cho Phase2 (search) và Phase3 (RAG).

Nạp model embedding + collection 1 lần (singleton).
"""
from __future__ import annotations

import config

_model = None
_col = None


def _load():
    global _model, _col
    if _model is None:
        import chromadb
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(config.EMBED_MODEL, device="cuda")
        client = chromadb.PersistentClient(path=str(config.VECTOR_DB_DIR))
        _col = client.get_collection(config.COLLECTION_NAME)
    return _model, _col


def retrieve(query: str, k: int = 5):
    """Trả về danh sách {score, text, meta} — score càng cao càng liên quan (cosine)."""
    model, col = _load()
    q_emb = model.encode([query], normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=q_emb, n_results=k,
                    include=["documents", "metadatas", "distances"])
    out = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"score": 1 - dist, "text": doc, "meta": meta})
    return out


def format_source(meta: dict) -> str:
    """Chuỗi trích dẫn nguồn gọn: 'tên file | Điều X | tiêu đề'."""
    parts = [meta.get("source"), meta.get("dieu"), meta.get("heading")]
    return " | ".join(p for p in parts if p)
