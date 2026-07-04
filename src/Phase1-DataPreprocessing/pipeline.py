"""Chạy toàn bộ Giai đoạn 1:  raw -> interim (markdown sạch) -> processed (chunks.jsonl).

Cách dùng:
    python src/Phase1-DataPreprocessing/pipeline.py          # xử lý data/raw
    python src/Phase1-DataPreprocessing/pipeline.py --stats  # kèm thống kê chunk
"""
from __future__ import annotations
import argparse
import json
import sys
import pathlib
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import extract
import clean
import chunk as chunker


def process_one(path: Path) -> list:
    print(f"  → {path.name}")
    raw = extract.extract_file(path)
    cleaned = clean.clean_text(raw)

    # Lưu bản markdown sạch để bạn kiểm tra bằng mắt (rất nên xem qua!)
    interim_path = config.DATA_INTERIM / (path.stem + ".md")
    interim_path.write_text(cleaned, encoding="utf-8")

    chunks = chunker.chunk_document(cleaned, source=path.name)
    chunks = chunker.merge_tiny_chunks(chunks)
    return chunks


def rechunk_from_interim() -> list:
    """Re-chunk từ các file .md đã làm sạch (bỏ qua extract + OCR, chạy tức thì)."""
    mds = sorted(config.DATA_INTERIM.glob("*.md"))
    all_chunks = []
    for md in mds:
        cleaned = md.read_text(encoding="utf-8")
        source = md.stem + ".pdf"  # tên nguồn gần đúng để hiển thị
        chunks = chunker.merge_tiny_chunks(chunker.chunk_document(cleaned, source=source))
        all_chunks.extend(chunks)
        print(f"  → {md.name}: {len(chunks)} chunk")
    return all_chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true", help="In thống kê sau khi chạy")
    ap.add_argument("--from-interim", action="store_true",
                    help="Chỉ re-chunk từ data/interim (không extract/OCR lại)")
    args = ap.parse_args()

    if args.from_interim:
        print("Re-chunk từ data/interim (bỏ qua OCR)...\n")
        all_chunks = rechunk_from_interim()
    else:
        files = sorted(p for p in config.DATA_RAW.iterdir()
                       if p.is_file() and p.suffix.lower() in config.SUPPORTED_EXTS)
        if not files:
            print(f"⚠️  Chưa có file nào trong {config.DATA_RAW}")
            print("    Hãy thả các file .pdf / .docx / .xlsx vào đó rồi chạy lại.")
            sys.exit(0)

        print(f"Tìm thấy {len(files)} file trong data/raw. Bắt đầu xử lý...\n")
        all_chunks = []
        for f in files:
            try:
                all_chunks.extend(process_one(f))
            except Exception as e:  # noqa: BLE001
                print(f"    ❌ Lỗi khi xử lý {f.name}: {e}")

    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    with config.CHUNKS_FILE.open("w", encoding="utf-8") as fh:
        for c in all_chunks:
            fh.write(json.dumps(chunker.to_dict(c), ensure_ascii=False) + "\n")

    print(f"\n✅ Xong. {len(all_chunks)} chunk -> {config.CHUNKS_FILE}")
    print(f"   Bản markdown sạch để kiểm tra: {config.DATA_INTERIM}/")

    if args.stats and all_chunks:
        wcs = [c.word_count for c in all_chunks]
        print("\n--- Thống kê chunk ---")
        print(f"  Số chunk      : {len(wcs)}")
        print(f"  Số từ / chunk : min={min(wcs)}  tb={sum(wcs)//len(wcs)}  max={max(wcs)}")
        n_dieu = sum(1 for c in all_chunks if c.dieu)
        print(f"  Chunk gắn 'Điều': {n_dieu}")


if __name__ == "__main__":
    main()
