"""Cấu hình chung dùng cho MỌI giai đoạn (đặt ở src/common/)."""
from pathlib import Path

# ---- Đường dẫn ----
# File ở src/common/config.py -> parents[2] = thư mục gốc dự án (ChatBot/)
ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"          # nơi bạn thả file gốc: .pdf .docx .xlsx
DATA_INTERIM = ROOT / "data" / "interim"  # văn bản đã chuyển đổi + làm sạch (.md)
DATA_PROCESSED = ROOT / "data" / "processed"  # các chunk cuối cùng (.jsonl)

CHUNKS_FILE = DATA_PROCESSED / "chunks.jsonl"

# ---- Tham số Chunking ----
# Mục tiêu số từ mỗi chunk. Quy chế được cắt theo "Điều"; điều nào dài hơn
# ngưỡng này sẽ được cắt nhỏ tiếp theo khoản / đoạn văn.
CHUNK_TARGET_WORDS = 400
CHUNK_MAX_WORDS = 550       # vượt ngưỡng này thì buộc phải cắt
CHUNK_MIN_WORDS = 40        # chunk quá ngắn sẽ được gộp với chunk trước
CHUNK_OVERLAP_WORDS = 50    # số từ chồng lấp giữa 2 chunk liền kề

# ---- Định dạng file được hỗ trợ ----
SUPPORTED_EXTS = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md"}

# ---- Giai đoạn 2: Embedding & Vector Database ----
EMBED_MODEL = "BAAI/bge-m3"          # đa ngôn ngữ, tiếng Việt tốt, chạy GPU
VECTOR_DB_DIR = ROOT / "data" / "vectordb"   # ChromaDB lưu bền ở đây
COLLECTION_NAME = "viu_docs"
EMBED_BATCH = 32

# ---- Giai đoạn 3: RAG & LLM ----
LLM_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"   # nhỏ nhẹ (~3GB VRAM), tiếng Việt tốt
RAG_TOP_K = 5              # số chunk truy xuất để đưa vào ngữ cảnh
LLM_MAX_NEW_TOKENS = 512   # độ dài tối đa câu trả lời
LLM_TEMPERATURE = 0.3      # thấp = bám tài liệu, ít bịa
RAG_MIN_SCORE = 0.35       # điểm tương đồng tối thiểu để coi là có thông tin liên quan

