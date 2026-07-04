# Chatbot Cố vấn Học tập — ĐH Công nghiệp Việt - Hung (VIU)

Trợ lý AI (kiến trúc **RAG**) trả lời câu hỏi về quy chế, chương trình đào tạo,
tuyển sinh và tư vấn lộ trình học tập cho sinh viên.

## Môi trường

Dự án chạy trong conda env **`test`**. Nên chạy trong `screen` để không bị ngắt:
```bash
screen -r ChatBot                 # vào lại phiên screen của dự án
conda activate test               # kích hoạt môi trường
cd ~/hdtrungoi/ChatBot
nvidia-smi                        # kiểm tra GPU (RTX 4080 SUPER) còn trống không
```
Cài thư viện (chỉ cần 1 lần):
```bash
conda activate test
pip install -r requirements.txt
pip install sentence-transformers chromadb    # cho Giai đoạn 2
```

---

## Giai đoạn 1 — Xử lý dữ liệu  ✅

Biến tài liệu gốc (PDF/Word/Excel) → chunk văn bản sạch, có cấu trúc.

```
data/raw/  ─►  extract  ─►  clean + sửa OCR  ─►  chunk  ─►  data/processed/chunks.jsonl
(file gốc)    (text+bảng    (chuẩn hóa NFC,      (cắt theo
              +OCR scan)    bỏ header, fix OCR)   "Điều")
                                  │
                                  ▼
                           data/interim/*.md   (bản sạch để soát tay)
```

### ⭐ Khi có DỮ LIỆU MỚI (đây là quy trình bạn sẽ dùng lại thường xuyên)
```bash
conda activate test
cd ~/hdtrungoi/ChatBot

# 1) Chép file mới (.pdf/.docx/.xlsx) vào thư mục:
#    data/raw/

# 2) Chạy lại pipeline (tự OCR file scan, làm sạch, sửa lỗi OCR, cắt chunk):
python src/pipeline.py --stats

# 3) Nhúng lại vào vector DB để chatbot dùng dữ liệu mới (Giai đoạn 2):
python src/embed.py --reset
```
> `pipeline.py` xử lý LẠI toàn bộ `data/raw/` mỗi lần chạy (ghi đè `chunks.jsonl`).
> Nếu file cũ nhiều mà chỉ thêm vài file, vẫn nên chạy lại cả cụm cho nhất quán.

### Các lệnh phụ trợ
```bash
# Chỉ sửa lại lỗi OCR trên bản .md rồi cắt chunk lại (KHÔNG OCR lại — chạy tức thì):
python src/ocr_correct.py
python src/pipeline.py --from-interim --stats

# Chỉ cắt chunk lại từ data/interim (khi sửa tham số chunk trong config.py):
python src/pipeline.py --from-interim --stats
```

### Đầu ra
- `data/interim/*.md` — văn bản đã làm sạch + sửa OCR (**nên mở đọc để soát**).
- `data/processed/chunks.jsonl` — mỗi dòng 1 chunk:
  `chunk_id, source, text, word_count, chuong, dieu, heading`.

### Lưu ý dữ liệu
- Phần lớn PDF của trường là **scan ảnh** → pipeline tự OCR (EasyOCR, GPU).
  OCR ~90% chính xác; bước sửa lỗi (`src/ocr_correct.py`) đã xử lý các lỗi phổ biến
  (ươ, d↔đ, I→l...). Với tài liệu quan trọng nên soát lại `data/interim/`.
- Muốn tư vấn **lộ trình học** cần bổ sung **khung chương trình đào tạo** các ngành
  (bảng: mã HP, tín chỉ, học kỳ, môn tiên quyết) — chép vào `data/raw/` và chạy lại.

---

## Bộ dữ liệu Q/A cho fine-tuning (Giai đoạn 4)
Thầy cô soạn Q/A bằng Excel/CSV theo mẫu, đặt vào `data/qa/`, rồi:
```bash
conda activate test
python src/build_dataset.py        # -> data/qa/train.jsonl (định dạng chat, chuẩn QLoRA)
```
Chi tiết cấu trúc cột và cách soạn: xem **`data/qa/README.md`**.

---

## Giai đoạn 2 — Embedding & Vector Database  ✅
Nhúng chunk bằng **BGE-M3** (đa ngôn ngữ, chạy GPU) → lưu **ChromaDB** ở `data/vectordb/`.
```bash
conda activate test
python src/embed.py --reset                    # nhúng toàn bộ chunk vào vector DB
python src/search.py "Em bị CPA 1.5 có bị đuổi học không?"   # kiểm thử truy xuất
```

---

## Cấu trúc mã nguồn
| File | Chức năng |
|------|-----------|
| `src/config.py`       | Đường dẫn, tham số chunking & embedding |
| `src/extract.py`      | Trích text + bảng (Markdown); tự OCR trang scan |
| `src/ocr.py`          | OCR tiếng Việt bằng EasyOCR (GPU) |
| `src/ocr_correct.py`  | Sửa lỗi OCR tiếng Việt phổ biến |
| `src/clean.py`        | Chuẩn hóa Unicode NFC, bỏ header/footer, gọi sửa OCR |
| `src/chunk.py`        | Cắt chunk theo cấu trúc Chương/Điều/Khoản |
| `src/pipeline.py`     | Chạy Giai đoạn 1, xuất `chunks.jsonl` |
| `src/build_dataset.py`| Gộp Q/A (CSV/XLSX) → `train.jsonl` |
| `src/embed.py`        | Nhúng chunk → ChromaDB (Giai đoạn 2) |
| `src/search.py`       | Kiểm thử truy xuất từ vector DB |

## Lộ trình
1. Xử lý dữ liệu ✅ · 2. Embedding + Vector DB ✅ · 3. Lắp RAG (retrieval + LLM) ·
4. Fine-tuning tư vấn (QLoRA) · 5. Giao diện (Streamlit/Gradio) · 6. Kiểm thử & deploy
