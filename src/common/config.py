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
    # Kế hoạch đào tạo khoá 50 — tên tệp là chuỗi không dấu do hệ thống xuất ra,
    # phải quy đổi sang tên ngành/chuyên ngành đúng để trích dẫn cho sinh viên hiểu.
    "k50-cnkt-o-to-chuyen-nganh-cn-o-to-20260702075009-e":
        "Kế hoạch đào tạo K50 ngành Công nghệ kỹ thuật ô tô, chuyên ngành Công nghệ ô tô",
    "k50-cnkt-o-to-chuyen-nganh-cn-o-to-dien-20260702075009-e":
        "Kế hoạch đào tạo K50 ngành Công nghệ kỹ thuật ô tô, chuyên ngành Công nghệ ô tô điện",
    "k50-kto-to-chuyen-nganh-o-to-20260702075009-e":
        "Kế hoạch đào tạo K50 ngành Kỹ thuật ô tô, chuyên ngành Ô tô",
    "k50-kto-to-chuyen-nganh-xe-cd-mct-20260702075009-e":
        "Kế hoạch đào tạo K50 ngành Kỹ thuật ô tô, chuyên ngành Xe chuyên dụng và máy công trình",
    "ke-hoach-k50-cnkt-nhiet-20260702075009-e":
        "Kế hoạch đào tạo K50 ngành Kỹ thuật nhiệt",
    "ke-hoach-k50-kt-moi-truong-20260702075009-e":
        "Kế hoạch đào tạo K50 ngành Kỹ thuật môi trường",
}

# ---- Giai đoạn 2: Embedding & Vector Database ----
EMBED_MODEL = "BAAI/bge-m3"          # đa ngôn ngữ, tiếng Việt tốt, chạy GPU
VECTOR_DB_DIR = ROOT / "data" / "vectordb"   # ChromaDB lưu bền ở đây
COLLECTION_NAME = "viu_docs"
EMBED_BATCH = 32

# ---- Giai đoạn 3: RAG & LLM ----
# Qwen3-14B chạy 4-bit NF4. Đo trên RTX 5090 (32,6 GB): trọng số 9,97 GB, đỉnh
# 10,18 GB, sinh 46 token/giây — còn dư ~22 GB cho ngữ cảnh dài của RAG mới.
# Bản bf16 cần ~29 GB riêng trọng số nên không dùng được cùng embedder+reranker.
# Máy yếu VRAM đổi về "Qwen/Qwen2.5-3B-Instruct" và đặt LLM_LOAD_4BIT = False.
LLM_MODEL = "Qwen/Qwen3-14B"
LLM_LOAD_4BIT = True       # lượng tử hoá NF4 khi nạp (bitsandbytes)
# Qwen3 mặc định bật chế độ "suy nghĩ": sinh một khối <think>...</think> dài trước
# câu trả lời. Với chatbot trích dẫn quy chế thì khối này chỉ làm chậm và rối
# giao diện — tài liệu đã nằm sẵn trong ngữ cảnh, không cần mô hình tự suy luận.
LLM_ENABLE_THINKING = False

RAG_TOP_K = 6              # số chunk CUỐI đưa vào ngữ cảnh (sau rerank)
# Reranker: lấy nhiều ứng viên bằng dense rồi chấm lại bằng cross-encoder để
# xếp hạng chính xác hơn (BGE-M3 dense cho điểm khá phẳng, khó phân biệt).
RERANK_ENABLED = True
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
# Kho hiện chỉ có 183 đoạn, mà cross-encoder chấm 183 cặp chỉ mất ~0,2 giây trên
# 5090 — nên lấy dư ứng viên tới mức gần như quét cả kho. Truy xuất xấp xỉ không
# còn bỏ sót đoạn nào, việc phân biệt đúng/sai giao hết cho reranker.
RETRIEVE_CANDIDATES = 80   # số ứng viên dense trước khi rerank

# Truy xuất lai: kết hợp tìm theo TỪ KHÓA (BM25) với tìm theo NGỮ NGHĨA (vector).
# Cần thiết vì câu hỏi thường chứa thuật ngữ chính xác (VSTEP, MOS, ICDL, tên học
# phần...) mà vector ngữ nghĩa dễ bỏ sót.
HYBRID_ENABLED = True
BM25_CANDIDATES = 40       # số ứng viên lấy theo từ khóa
# Lô 8 thay vì 32: card dùng chung, đã có lúc chỉ còn 13,5 GB trống vì job khác.
# Kho chỉ 183 đoạn nên chênh lệch tốc độ không đáng kể, đổi lại chạy được khi chật.
RERANK_BATCH = 8
RERANK_FP16 = True         # nạp mô hình xếp hạng ở nửa độ chính xác (giảm ~50% VRAM)

# Mở rộng truy vấn: sinh viên hỏi bằng khẩu ngữ ("đuổi học", "trượt môn") trong
# khi văn bản viết bằng thuật ngữ pháp quy ("buộc thôi học", "học phần không
# đạt"). Ghép thêm biến thể thuật ngữ vào câu truy xuất để BM25 bắt đúng từ và
# dense bắt đúng vùng ngữ nghĩa. Bảng từ ở QUERY_SYNONYMS bên dưới.
QUERY_EXPANSION = True

# Mở rộng đoạn trúng thành TRỌN VẸN một Điều trước khi đưa vào ngữ cảnh.
# Điều dài bị cắt thành nhiều phần (18/104 Điều, cá biệt Điều 7 có 6 phần) nên
# đoạn trúng thường chỉ là một mẩu — mô hình đọc được khoản a, b mà mất khoản c,
# rồi trả lời thiếu. Ghép lại theo (tên văn bản, số Điều), khử câu trùng do
# chồng lấp (đo được 4-5 câu trùng liền đầu mỗi phần).
PARENT_EXPAND = True
# Trần độ dài ngữ cảnh (số từ). Ghép full Điều làm ngữ cảnh phình to; 14B đọc
# được nhiều hơn 3B nhưng vẫn cần chặn để không tràn và không loãng trọng tâm.
CONTEXT_MAX_WORDS = 3500

# Ngưỡng chặn chống suy diễn — nay chỉ còn là SÀN AN TOÀN, không phải cổng chính.
#
# Lịch sử: ban đầu chặn bằng ngưỡng similarity vì mô hình 3B hay bịa khi ngữ cảnh
# lạc đề. Nhưng đo lại trên bộ 22 câu hợp lệ + 8 câu ngoài phạm vi (chạy
# src/Phase3-RAG/calib_retrieval.py) thì HAI VÙNG ĐIỂM ĐÃ CHỒNG LÊN NHAU:
#     dense : câu hợp lệ thấp nhất 0,496 | câu ngoài phạm vi cao nhất 0,493
#     rerank: câu hợp lệ thấp nhất 0,0071 | câu ngoài phạm vi cao nhất 0,0129
# Không còn ngưỡng nào tách được hai lớp. Để 0,55 thì chặn oan 3/22 câu hợp lệ,
# trong đó có đúng loại câu quan trọng nhất của hệ cố vấn:
#     "Em còn nợ 3 môn và GPA 1.9, nên làm gì để ra trường đúng hạn?"
# Sinh viên hỏi thật lại nhận "chưa tìm thấy quy định" — hỏng đúng mục đích hệ thống.
#
# Đo tiếp: bỏ cổng chặn rồi đưa thẳng 8 câu ngoài phạm vi cho Qwen3-14B đọc ngữ
# cảnh lạc đề. Kết quả 8/8 mô hình TỰ từ chối đúng, không bịa câu nào ("Tài liệu
# không cung cấp thông tin về giá vé máy bay..."). Mô hình 14B đọc hiểu ngữ cảnh
# tốt hơn hẳn một con số cosine, nên giao việc phán đoán cho nó.
#
# Hai ngưỡng dưới đây nay chỉ để bắt trường hợp thảm hoạ (kho rỗng, truy vấn rác):
# thấp hơn hẳn cả vùng câu ngoài phạm vi đã đo (cao nhất 0,493 / 0,0129).
RERANK_MIN_SCORE = 0.001
DENSE_MIN_SCORE = 0.30

# Lọc đoạn trước khi ghép vào ngữ cảnh: bỏ đoạn có điểm THẤP HƠN HẲN đoạn đầu bảng.
# RAG_TOP_K đặt cao để không bỏ sót (recall), nhưng nhồi cả 5 đoạn vào ngữ cảnh thì
# đoạn lạc đề lấn át đoạn đúng. Đo thực tế: hỏi "chương trình ngoại ngữ bao nhiêu
# tín chỉ", đoạn đúng (Điều 4) chỉ 110 từ trong khi hai đoạn "Phạm vi điều chỉnh"
# lạc đề chiếm 849/1307 từ — mô hình bỏ qua đoạn đúng và bịa ra nội dung.
# Tỉ lệ điểm so với hạng 1 trên bộ câu kiểm thử: đoạn thật sự liên quan luôn từ
# 0,26 trở lên; đoạn nhiễu tụt xuống 0,19 trở xuống. Chọn 0,25 nằm giữa hai vùng.
CONTEXT_MIN_RATIO = 0.25

# Bảng khẩu ngữ -> thuật ngữ pháp quy, dùng cho QUERY_EXPANSION.
# Chỉ ghép THÊM vào câu truy xuất (không thay thế) nên không làm hỏng câu hỏi đã
# dùng đúng thuật ngữ. Khóa viết thường, không dấu câu; so khớp trên bản đã hạ
# chữ thường của câu hỏi.
QUERY_SYNONYMS = {
    "đuổi học": "buộc thôi học",
    "bị đuổi": "buộc thôi học",
    "thôi học": "buộc thôi học cảnh báo học tập",
    "trượt môn": "học phần không đạt học lại",
    "rớt môn": "học phần không đạt học lại",
    "học lại": "học lại học phần không đạt",
    "thi lại": "học phần không đạt đánh giá lại",
    "cải thiện điểm": "học cải thiện điểm học phần",
    "bằng giỏi": "xếp loại tốt nghiệp hạng giỏi",
    "bằng khá": "xếp loại tốt nghiệp hạng khá",
    "loại xuất sắc": "xếp loại tốt nghiệp hạng xuất sắc",
    "ra trường": "tốt nghiệp công nhận tốt nghiệp",
    "tốt nghiệp sớm": "tốt nghiệp thời gian đào tạo rút ngắn",
    "học phí": "học phí khoản thu miễn giảm",
    "nợ môn": "học phần chưa đạt tích lũy",
    "bảo lưu": "nghỉ học tạm thời bảo lưu kết quả",
    "nghỉ học": "nghỉ học tạm thời thôi học",
    "chuyển ngành": "chuyển ngành chuyển chương trình đào tạo",
    "chuyển trường": "chuyển trường tiếp nhận sinh viên",
    "tiếng anh": "ngoại ngữ chuẩn đầu ra VSTEP",
    "chứng chỉ tiếng anh": "chứng chỉ ngoại ngữ VSTEP chuẩn đầu ra",
    "tin học": "chuẩn đầu ra tin học MOS ICDL IC3 năng lực số",
    "gpa": "điểm trung bình tích lũy CPA GPA",
    "cpa": "điểm trung bình tích lũy CPA",
    "học bổng": "học bổng khuyến khích học tập",
    "cảnh cáo": "cảnh báo học tập",
    "học online": "đào tạo trực tuyến",
    "học trực tuyến": "đào tạo trực tuyến LMS",
    "bao nhiêu tín": "số tín chỉ khối lượng học tập",
    "mấy tín": "số tín chỉ khối lượng học tập",
}

# ---- Giai đoạn 5: Giao diện web (Gradio) ----
UI_PORT = 7860
UI_HISTORY_TURNS = 3       # số lượt hội thoại trước đưa vào ngữ cảnh (cho câu hỏi nối tiếp)
# Độ dài tối đa câu trả lời. 512 từng cắt cụt giữa chừng ("...việc thống báo hình
# thức áp dụng đối với sinh viên như") khi mô hình trích dài. Nới lên để câu trả
# lời luôn kết thúc trọn vẹn; muốn ngắn gọn thì sửa ở dữ liệu huấn luyện chứ
# không phải chặn cứng ở đây.
LLM_MAX_NEW_TOKENS = 900
# 0 = giải mã tất định (greedy): cùng câu hỏi luôn ra cùng câu trả lời, và mô hình
# không còn cơ hội chọn token lệch rồi bịa tiếp đoạn quy định không có thật. Với
# chatbot trích dẫn quy chế thì tính nhất quán quan trọng hơn sự đa dạng câu chữ.
LLM_TEMPERATURE = 0
RAG_MIN_SCORE = 0.35       # điểm tương đồng tối thiểu để coi là có thông tin liên quan

# ---- Giai đoạn 4: Fine-tuning QLoRA ----
FINETUNE_BASE = LLM_MODEL                       # base để fine-tune
ADAPTER_DIR = ROOT / "models" / "qlora-viu"     # nơi lưu LoRA adapter (gitignore)
# Adapter models/qlora-viu nay ĐÃ train trên đúng Qwen3-14B (1197 bước, 3 epoch,
# loss cuối 0,070). Nhưng đo lại bằng src/Phase4-Finetuning/so_sanh_adapter.py thì
# nó KÉM HƠN model gốc: học thuộc lối chép nguyên văn tài liệu ("Theo <văn bản>
# (Điều N), quy định như sau: ..."), trả lời dài gấp 2-3 lần, bị cắt cụt giữa câu,
# và có ca trả lời lạc hẳn đề (hỏi CPA 1.5 năm hai có bị thôi học không -> đáp về
# học phí). Chi tiết ở CLAUDE.md, mục "Kết quả fine-tune Qwen3-14B".
# Vì vậy TẮT. Adapter vẫn giữ nguyên trên đĩa; muốn bật lại chỉ cần đổi thành True.
# rag.py vẫn kiểm adapter_config.json và bỏ qua adapter nếu base không khớp.
USE_FINETUNED = False       # đang chạy MODEL GỐC Qwen3-14B
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
# Số vòng huấn luyện. Đã thử nghiệm trên chính bộ dữ liệu này (~1800 mẫu có kèm
# tài liệu), kết quả đo được:
#   3 vòng + dữ liệu CHƯA sạch: bám tài liệu tốt, nhưng đọc lại nguyên văn đoạn
#       thủ tục hành chính vì đoạn đó nằm sẵn trong 230 đáp án huấn luyện.
#   2 vòng + dữ liệu đã sạch  : hết đoạn thủ tục, nhưng CHƯA học được kỹ năng đọc
#       tài liệu — hỏi "chương trình ngoại ngữ bao nhiêu tín chỉ" thì bỏ qua Điều 4
#       xếp hạng 1 (điểm 0,9995) và bịa ra nội dung của một "Điều 3" không có
#       trong ngữ cảnh. Giải mã tất định cũng không cứu được.
# Vậy nút thắt là số vòng, không phải mức học thuộc: quay lại 3 vòng trên dữ liệu
# đã làm sạch.
FT_EPOCHS = 3
FT_LR = 2e-4
# Mẫu huấn luyện nay kèm cả khối TÀI LIỆU (giống hệt lúc chạy thật) nên dài hơn
# hẳn: đo thực tế trung vị 2194 token, p90 2644. Để 1024 như trước sẽ cắt cụt
# 99,9% số mẫu — cắt từ cuối, tức mất đúng phần đáp án cần học.
# Bù lại độ dài tăng, giảm batch xuống 1 và tăng tích lũy để giữ nguyên batch
# hiệu dụng (1x8 = 2x4) mà vẫn vừa bộ nhớ GPU.
FT_BATCH = 1
FT_GRAD_ACCUM = 8
# Ngữ cảnh dài hẳn ra sau khi bật ghép trọn Điều và nâng RAG_TOP_K lên 6. Đo trên
# 120 câu lấy ngẫu nhiên từ qa_viu_full.csv, dựng mẫu ĐÚNG như lúc chạy thật:
#   trung vị 4447 token | p90 5494 | p95 5737 | dài nhất 9189
#   tỉ lệ mẫu vừa nguyên vẹn: 3072 -> 20%, 4096 -> 34%, 5120 -> 70%, 6144 -> 97%
# Giữ 3072 như trước thì 80% số mẫu bị bớt đoạn tài liệu, tức huấn luyện trên ngữ
# cảnh ngắn hơn hẳn lúc chạy thật — đúng loại lệch làm fine-tune phản tác dụng.
FT_MAX_LEN = 6144

