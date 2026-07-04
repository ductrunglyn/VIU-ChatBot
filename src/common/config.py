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
# 3B suy luận con số/quy định tốt hơn hẳn 1.5B (~6GB VRAM, vẫn dư trên 4080 16GB).
# Máy yếu VRAM có thể đổi về "Qwen/Qwen2.5-1.5B-Instruct".
LLM_MODEL = "Qwen/Qwen2.5-3B-Instruct"
RAG_TOP_K = 5              # số chunk CUỐI đưa vào ngữ cảnh (sau rerank)
# Reranker: lấy nhiều ứng viên bằng dense rồi chấm lại bằng cross-encoder để
# xếp hạng chính xác hơn (BGE-M3 dense cho điểm khá phẳng, khó phân biệt).
RERANK_ENABLED = True
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
RETRIEVE_CANDIDATES = 20   # số ứng viên dense trước khi rerank
LLM_MAX_NEW_TOKENS = 512   # độ dài tối đa câu trả lời
LLM_TEMPERATURE = 0.1      # rất thấp = bám tài liệu, ổn định, tránh rò tiếng Trung/Anh
RAG_MIN_SCORE = 0.35       # điểm tương đồng tối thiểu để coi là có thông tin liên quan

# ---- Giai đoạn 4: Fine-tuning QLoRA ----
FINETUNE_BASE = LLM_MODEL                       # base để fine-tune
ADAPTER_DIR = ROOT / "models" / "qlora-viu"     # nơi lưu LoRA adapter (gitignore)
USE_FINETUNED = True        # rag.py tự nạp adapter nếu ADAPTER_DIR tồn tại
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
FT_EPOCHS = 8               # dataset còn nhỏ -> nhiều epoch; GIẢM khi có nhiều dữ liệu
FT_LR = 2e-4
FT_BATCH = 2
FT_GRAD_ACCUM = 4
FT_MAX_LEN = 1024

