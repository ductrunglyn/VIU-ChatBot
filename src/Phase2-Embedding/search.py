"""Kiểm thử truy xuất (retrieval) trên vector DB — xem trước 'bộ não' của RAG.

Cách dùng:
    conda activate test
    python src/search.py "Em bị CPA 1.5 có bị đuổi học không?"
    python src/search.py "điều kiện tốt nghiệp" --k 5
"""
from __future__ import annotations
import argparse
import sys as _sys, pathlib as _pathlib

_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / "common"))
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


def search(query: str, k: int = 5):
    model, col = _load()
    q_emb = model.encode([query], normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=q_emb, n_results=k,
                    include=["documents", "metadatas", "distances"])
    out = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"score": 1 - dist, "text": doc, "meta": meta})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="Câu hỏi cần tìm")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    hits = search(args.query, args.k)
    print(f"\n🔎 '{args.query}'  — {len(hits)} kết quả gần nhất:\n")
    for i, h in enumerate(hits, 1):
        m = h["meta"]
        loc = " | ".join(x for x in (m.get("source"), m.get("dieu"), m.get("heading")) if x)
        print(f"[{i}] (điểm {h['score']:.3f})  {loc}")
        snippet = h["text"].replace("\n", " ")
        print(f"    {snippet[:260]}...\n")


if __name__ == "__main__":
    main()
