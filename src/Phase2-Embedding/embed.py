"""Giai đoạn 2: Nhúng (embedding) các chunk bằng BGE-M3 và lưu vào ChromaDB.

Cách dùng:
    conda activate test
    python src/embed.py            # nhúng toàn bộ chunks.jsonl vào vector DB
    python src/embed.py --reset    # xóa DB cũ rồi nhúng lại từ đầu

Vector DB lưu bền ở data/vectordb/ (dùng lại cho Giai đoạn 3 - RAG).
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys as _sys, pathlib as _pathlib

_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / "common"))
import config


def load_chunks():
    if not config.CHUNKS_FILE.exists():
        raise SystemExit(f"Chưa có {config.CHUNKS_FILE}. Chạy pipeline Giai đoạn 1 trước.")
    rows = [json.loads(l) for l in config.CHUNKS_FILE.open(encoding="utf-8")]
    # đảm bảo id duy nhất (phòng trùng)
    seen = {}
    for r in rows:
        cid = r["chunk_id"]
        if cid in seen:
            seen[cid] += 1
            r["chunk_id"] = f"{cid}#{seen[cid]}"
        else:
            seen[cid] = 0
    return rows


def _meta(r: dict) -> dict:
    """Chroma không nhận None -> đổi thành chuỗi rỗng."""
    return {k: (r.get(k) or "") for k in ("source", "chuong", "dieu", "heading")} \
        | {"word_count": int(r.get("word_count", 0))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="Xóa DB cũ rồi nhúng lại")
    args = ap.parse_args()

    import chromadb
    from sentence_transformers import SentenceTransformer

    if args.reset and config.VECTOR_DB_DIR.exists():
        shutil.rmtree(config.VECTOR_DB_DIR)
        print("Đã xóa vector DB cũ.")

    rows = load_chunks()
    print(f"Nạp {len(rows)} chunk. Đang tải model {config.EMBED_MODEL} ...")
    model = SentenceTransformer(config.EMBED_MODEL, device="cuda")
    print(f"  Thiết bị: {model.device}")

    texts = [r["text"] for r in rows]
    embs = model.encode(
        texts, batch_size=config.EMBED_BATCH, normalize_embeddings=True,
        show_progress_bar=True, convert_to_numpy=True,
    )

    client = chromadb.PersistentClient(path=str(config.VECTOR_DB_DIR))
    # xóa collection cũ để nhúng lại sạch (idempotent)
    try:
        client.delete_collection(config.COLLECTION_NAME)
    except Exception:
        pass
    col = client.create_collection(
        config.COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    col.add(
        ids=[r["chunk_id"] for r in rows],
        documents=texts,
        embeddings=embs.tolist(),
        metadatas=[_meta(r) for r in rows],
    )
    print(f"\n✅ Đã nhúng {col.count()} chunk vào ChromaDB -> {config.VECTOR_DB_DIR}")
    print("   Kiểm thử truy xuất: python src/search.py \"câu hỏi của bạn\"")


if __name__ == "__main__":
    main()
