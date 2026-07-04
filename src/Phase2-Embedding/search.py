"""Kiểm thử truy xuất (retrieval) trên vector DB — xem trước 'bộ não' của RAG.

Cách dùng:
    conda activate test
    python src/Phase2-Embedding/search.py "Em bị CPA 1.5 có bị đuổi học không?"
    python src/Phase2-Embedding/search.py "điều kiện tốt nghiệp" --k 5
"""
from __future__ import annotations
import argparse
import sys as _sys, pathlib as _pathlib

_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / "common"))
import retriever


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="Câu hỏi cần tìm")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    hits = retriever.retrieve(args.query, args.k)
    print(f"\n🔎 '{args.query}'  — {len(hits)} kết quả tốt nhất:\n")
    for i, h in enumerate(hits, 1):
        rr = f"rerank {h['rerank_score']:.3f} | " if h.get("rerank_score") is not None else ""
        print(f"[{i}] ({rr}dense {h['score']:.3f})  {retriever.format_source(h['meta'])}")
        snippet = h["text"].replace("\n", " ")
        print(f"    {snippet[:260]}...\n")


if __name__ == "__main__":
    main()
