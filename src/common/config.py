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
SUPPORTED_EXTS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".md"}

# ---- Tên hiển thị chuẩn của tài liệu ----
# Tên tệp gốc thường có số thứ tự, viết tắt, chữ "sửa"... Bảng này quy đổi sang
# tên văn bản đầy đủ để trích dẫn trong câu trả lời cho đúng và dễ hiểu.
# Khóa: phần tên tệp không có đuôi. Tệp không có trong bảng sẽ được làm sạch tự động.
DOC_TITLES = {
    "1.quy chế đào tạo  220": "Quy chế đào tạo trình độ đại học",
    "2.Quy định đào tạo trực tuyến": "Quy định về đào tạo trực tuyến",
    "3.Quy định về CĐR ngoại ngữ và tin học sửa":
        "Quy định về chuẩn đầu ra ngoại ngữ và tin học",
    "4.Quy định về học phí, các khoản thu khác":
        "Quy định về học phí và các khoản thu khác",
    "5.Tai lieu huong dan LMS (ký)":
        "Tài liệu hướng dẫn sử dụng hệ thống LMS",
    "6.Luật giáo dục đại học": "Luật Giáo dục đại học",
}

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

# Truy xuất lai: kết hợp tìm theo TỪ KHÓA (BM25) với tìm theo NGỮ NGHĨA (vector).
# Cần thiết vì câu hỏi thường chứa thuật ngữ chính xác (VSTEP, MOS, ICDL, tên học
# phần...) mà vector ngữ nghĩa dễ bỏ sót.
HYBRID_ENABLED = True
BM25_CANDIDATES = 10       # số ứng viên lấy theo từ khóa
RERANK_BATCH = 8           # chia lô nhỏ khi xếp hạng lại để tiết kiệm bộ nhớ GPU
RERANK_FP16 = True         # nạp mô hình xếp hạng ở nửa độ chính xác (giảm ~50% VRAM)

# Ngưỡng chặn chống suy diễn: nếu đoạn tốt nhất sau rerank có điểm dưới ngưỡng
# này, coi như KHÔNG có tài liệu liên quan và trả lời "chưa tìm thấy quy định".
# Giá trị hiệu chỉnh từ đo thực tế trên kho tri thức hiện tại:
#   câu TRONG phạm vi  : điểm thấp nhất đo được 0,264
#   câu NGOÀI phạm vi  : điểm cao nhất  đo được 0,025
# Chọn 0,10 nằm giữa hai vùng, thiên về không chặn nhầm câu hỏi hợp lệ.
RERANK_MIN_SCORE = 0.10
# Mô hình xếp hạng chấm điểm rất thấp với câu hỏi diễn đạt dài/khẩu ngữ, dù đoạn
# tài liệu thực sự trả lời được. Vì vậy chấp nhận câu hỏi khi MỘT trong hai tín
# hiệu đủ mạnh: điểm xếp hạng, hoặc độ tương đồng ngữ nghĩa.
# Đo thực tế: câu hợp lệ bị xếp hạng chấm thấp vẫn đạt tương đồng 0,566;
# câu ngoài phạm vi cao nhất chỉ 0,508.
DENSE_MIN_SCORE = 0.55

# ---- Giai đoạn 5: Giao diện web (Gradio) ----
UI_PORT = 7860
UI_HISTORY_TURNS = 3       # số lượt hội thoại trước đưa vào ngữ cảnh (cho câu hỏi nối tiếp)
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
# Số vòng huấn luyện: đặt theo kích thước dữ liệu. Với ~1800 mẫu, 3 vòng là đủ;
# để 8 vòng như khi dữ liệu còn ít (73 mẫu) sẽ khiến mô hình học vẹt.
FT_EPOCHS = 3
FT_LR = 2e-4
# Mẫu huấn luyện nay kèm cả khối TÀI LIỆU (giống hệt lúc chạy thật) nên dài hơn
# hẳn: đo thực tế trung vị 2194 token, p90 2644. Để 1024 như trước sẽ cắt cụt
# 99,9% số mẫu — cắt từ cuối, tức mất đúng phần đáp án cần học.
# Bù lại độ dài tăng, giảm batch xuống 1 và tăng tích lũy để giữ nguyên batch
# hiệu dụng (1x8 = 2x4) mà vẫn vừa bộ nhớ GPU.
FT_BATCH = 1
FT_GRAD_ACCUM = 8
FT_MAX_LEN = 3072

