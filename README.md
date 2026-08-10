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
python src/Phase1-DataPreprocessing/pipeline.py --stats

# 3) Nhúng lại vào vector DB để chatbot dùng dữ liệu mới (Giai đoạn 2):
python src/Phase2-Embedding/embed.py --reset
```
> `pipeline.py` xử lý LẠI toàn bộ `data/raw/` mỗi lần chạy (ghi đè `chunks.jsonl`).
> Nếu file cũ nhiều mà chỉ thêm vài file, vẫn nên chạy lại cả cụm cho nhất quán.

### Các lệnh phụ trợ
```bash
# Chỉ sửa lại lỗi OCR trên bản .md rồi cắt chunk lại (KHÔNG OCR lại — chạy tức thì):
python src/Phase1-DataPreprocessing/ocr_correct.py
python src/Phase1-DataPreprocessing/pipeline.py --from-interim --stats

# Chỉ cắt chunk lại từ data/interim (khi sửa tham số chunk trong config.py):
python src/Phase1-DataPreprocessing/pipeline.py --from-interim --stats
```

### Đầu ra
- `data/interim/*.md` — văn bản đã làm sạch + sửa OCR (**nên mở đọc để soát**).
- `data/processed/chunks.jsonl` — mỗi dòng 1 chunk:
  `chunk_id, source, text, word_count, chuong, dieu, heading`.

### Lưu ý dữ liệu
- Phần lớn PDF của trường là **scan ảnh** → pipeline tự OCR (EasyOCR, GPU).
  OCR ~90% chính xác; bước sửa lỗi (`ocr_correct.py`) xử lý các lỗi phổ biến
  (ươ, d↔đ, I→l...). Với tài liệu quan trọng nên soát lại `data/interim/`.
- **OCR BẢNG** (`table_ocr.py`, dùng img2table): trang scan có bảng (khung chương
  trình: mã HP · tín chỉ · môn tiên quyết; bảng quy đổi điểm...) được trích riêng
  giữ nguyên hàng/cột → chuyển thành bảng Markdown, thay vì bị OCR làm vỡ cấu trúc.
- Khung chương trình đào tạo các ngành (`khdt *`) đã có trong `data/raw/`; thêm
  ngành mới chỉ cần chép PDF vào đó và chạy lại pipeline.

---

## Giai đoạn 2 — Embedding & Vector Database (+ Rerank)  ✅
Nhúng chunk bằng **BGE-M3** (đa ngôn ngữ, chạy GPU) → lưu **ChromaDB** ở `data/vectordb/`.
Truy xuất 2 bước: dense lấy 20 ứng viên → **rerank** bằng cross-encoder
`BGE-reranker-v2-m3` để xếp hạng chính xác hơn → lấy top-5.
```bash
conda activate test
python src/Phase2-Embedding/embed.py --reset                 # nhúng toàn bộ chunk
python src/Phase2-Embedding/search.py "Em bị CPA 1.5 có bị đuổi học không?"  # test truy xuất
```
> Bật/tắt rerank và số ứng viên: `RERANK_ENABLED`, `RETRIEVE_CANDIDATES` trong `common/config.py`.
> Logic truy xuất dùng chung ở `common/retriever.py` (cả Giai đoạn 2 và 3).

---

## Giai đoạn 3 — RAG (truy xuất + LLM sinh câu trả lời)  ✅
Ghép truy xuất tài liệu với **LLM Qwen2.5-3B-Instruct** (~6GB VRAM, chạy GPU).
LLM chỉ trả lời dựa trên tài liệu tìm được và trích dẫn nguồn.
```bash
conda activate test
# Hỏi 1 câu:
python src/Phase3-RAG/rag.py "Em bị CPA 1.5 ở năm hai có bị buộc thôi học không?"
# Chế độ hỏi-đáp liên tục:
python src/Phase3-RAG/rag.py
# Thử model khác (vd bản nhẹ 1.5B cho máy yếu VRAM):
python src/Phase3-RAG/rag.py "..." --model Qwen/Qwen2.5-1.5B-Instruct
```
> Lần chạy đầu tự tải model (~6GB) về `~/.cache/huggingface`.
> Đã so sánh: **3B suy luận con số/quy định chính xác hơn hẳn 1.5B** (vd đối chiếu
> CPA 1.5 với mốc 1.4). Muốn đổi mặc định: sửa `LLM_MODEL` trong `common/config.py`.
> Chất lượng sẽ còn cải thiện sau **Giai đoạn 4 (fine-tuning)** với bộ Q/A của trường.

---

## Giai đoạn 4 — Fine-tuning QLoRA  ✅
Dạy LLM "văn phong & tư duy tư vấn" từ bộ Q/A của trường (4-bit NF4 + LoRA).

**Bước 1 — Chuẩn bị Q/A** (đặt file vào `data/qa/`):
- **Cách 1 — Word (.docx):** soạn theo mẫu "Câu N / Chủ đề / Câu hỏi / Đáp án /
  Tài liệu tham chiếu" (xem `data/qa/README.md`), rồi chuyển sang CSV:
  ```bash
  python src/Phase4-Finetuning/docx_to_csv.py    # mỗi .docx -> 1 .csv cùng tên
  ```
- **Cách 2 — Excel/CSV:** điền trực tiếp theo `data/qa/qa_pairs_template.csv`.

**Bước 1b — Sinh và nâng chất lượng dữ liệu tự động** (dựa trên kho tri thức):
```bash
# Sinh Q/A bám nội dung từng Điều của mọi văn bản (đáp án chi tiết, có trích dẫn)
python src/Phase4-Finetuning/gen_qa_from_docs.py

# Sinh bộ câu hỏi sinh viên thường gặp, đáp án dựng từ văn bản thật
python src/Phase4-Finetuning/gen_faq.py

# Viết lại các đáp án quá ngắn thành đáp án chi tiết có căn cứ văn bản
# (ghi đè tệp .csv, tự sao lưu bản gốc thành <tên>.bak.csv)
python src/Phase4-Finetuning/enrich_qa.py            # thêm --dry-run để xem trước
```
> Ba công cụ này chỉ dùng nội dung có thật trong `data/processed/chunks.jsonl`.
> Câu hỏi không tìm được căn cứ sẽ bị loại thay vì để mô hình bịa đáp án.

**Bước 2 — Gộp mọi tệp Q/A thành MỘT tệp duy nhất:**
```bash
python src/Phase4-Finetuning/merge_qa.py        # -> data/qa/qa_viu_full.csv
```
Tệp gộp đánh id liên tục, bỏ câu trùng (giữ bản có đáp án dài hơn), thêm cột
`origin` để truy vết tệp nguồn. Đây là tệp DUY NHẤT cần rà soát/chỉnh sửa về sau.

> ⚠️ Sau khi đã sửa tay trong `qa_viu_full.csv`, **đừng chạy lại `merge_qa.py`** trừ
> khi vừa bổ sung tệp Q/A mới: lệnh gộp đọc lại các tệp nguồn cũ và khi trùng câu
> hỏi thì giữ bản có đáp án DÀI hơn, nên phần bạn rút gọn có thể bị ghi đè ngược.
> Muốn thêm dữ liệu mới an toàn: xóa/di chuyển các tệp nguồn cũ trước khi gộp lại.

**Bước 3 — Dựng tập huấn luyện** (mặc định **kèm khối TÀI LIỆU** giống lúc chạy thật):
```bash
python src/Phase4-Finetuning/build_dataset.py   # -> data/qa/train.jsonl
```
> **Vì sao phải kèm tài liệu:** lúc chạy thật, `rag.py` đưa cho mô hình khối
> `TÀI LIỆU:` (các Điều truy xuất được) rồi mới tới `CÂU HỎI:`. Nếu huấn luyện chỉ
> bằng *câu hỏi → đáp án*, mô hình học trả lời bằng trí nhớ theo một khuôn cố định
> và khi chạy thật nó **bỏ qua tài liệu vừa truy xuất**, cho ra câu trả lời chung
> chung dù tài liệu có đủ chi tiết. Dựng mẫu đúng như lúc suy luận thì mô hình mới
> học đúng kỹ năng cần dùng: *đọc tài liệu được cấp → liệt kê đầy đủ → dẫn đúng tên văn bản*.
>
> Tùy chọn: `--k 3` (số Điều kèm mỗi mẫu), `--no-rag` (quay lại kiểu cũ).

**Bước 4 — Huấn luyện QLoRA** (adapter lưu ở `models/qlora-viu/`):
```bash
python src/Phase4-Finetuning/train_qlora.py
```
Sau khi train xong, `rag.py` **tự động nạp adapter** (bật/tắt bằng `USE_FINETUNED`
trong `common/config.py`). Tham số LoRA/epoch cũng ở `config.py`.

> Chi tiết cấu trúc cột: xem **`data/qa/README.md`**.

---

## Giai đoạn 5 — Giao diện web (chatbot)  ✅
Website chat (Gradio) cho sinh viên/thầy cô dùng thật. Nạp model 1 lần, phục vụ
nhiều người; câu trả lời hiện dần (streaming) và kèm nguồn trích dẫn.
```bash
conda activate test
cd ~/hdtrungoi/ChatBot
python src/Phase5-UI/app.py       # nên chạy trong `screen -r ChatBot` để giữ chạy nền
```
Mở trình duyệt:
- Trên chính máy chủ: **http://localhost:7860**
- Máy khác cùng mạng LAN: **http://\<IP-máy-chủ\>:7860** (xem IP bằng `hostname -I`)

**Giao diện có gì:**
- Nhận diện thương hiệu Nhà trường: logo và màu chuẩn (xanh `#0082BC`, cam `#EA902F`),
  ảnh nằm ở `assets/`, khai báo tập trung trong `Phase5-UI/theme.py`.
- **Thanh bên lịch sử trò chuyện:** tạo đoạn chat mới, mở lại đoạn cũ, xóa đoạn.
  Tên đoạn tự đặt theo câu hỏi đầu tiên.
- Câu hỏi gợi ý bấm là điền sẵn, câu trả lời hiện dần kèm khối *Nguồn tham khảo*.

> **Lịch sử chat lưu ở đâu?** Trong trình duyệt của chính sinh viên (`gr.BrowserState`
> → localStorage), **không** lưu trên máy chủ. Nhờ vậy không cần cơ sở dữ liệu, và
> không có chuyện người này đọc được đoạn chat của người kia. Đổi lại, xóa dữ liệu
> trình duyệt hoặc đổi máy là mất lịch sử — đúng như mong đợi với dữ liệu học vụ cá nhân.

> Dùng model đã fine-tune (nếu có adapter). Đổi cổng: `UI_PORT` trong `common/config.py`.
> Số lượt hội thoại đưa vào ngữ cảnh: `UI_HISTORY_TURNS`.
> Cần link công khai tạm thời (demo qua Internet): sửa `share=False` -> `share=True`
> trong `app.py` — **cân nhắc** vì sẽ lộ chatbot + dữ liệu ra ngoài.

---

## Cấu trúc mã nguồn (tách theo giai đoạn)
```
src/
  common/                    config.py · retriever.py — dùng chung mọi giai đoạn
  Phase1-DataPreprocessing/  extract · ocr · table_ocr · ocr_correct · clean · chunk · pipeline
  Phase2-Embedding/          embed · search
  Phase3-RAG/                rag · test_rag
  Phase4-Finetuning/         docx_to_csv · merge_qa · build_dataset · train_qlora
  Phase5-UI/                 app (giao diện web Gradio) · theme (logo, màu, CSS)
assets/                      viu_logo.png · viu_lockup.png — logo Trường ĐHCN Việt - Hung
```
| File | Chức năng |
|------|-----------|
| `common/config.py`             | Đường dẫn, tham số chunking / embedding / LLM (dùng chung) |
| `common/retriever.py`          | Truy xuất chunk từ ChromaDB (Phase2 & Phase3 dùng chung) |
| `Phase1.../extract.py`         | Trích text + bảng (Markdown); tự OCR trang scan |
| `Phase1.../ocr.py`             | OCR tiếng Việt bằng EasyOCR (GPU) |
| `Phase1.../table_ocr.py`       | OCR BẢNG (img2table) giữ cấu trúc hàng/cột cho trang scan |
| `Phase1.../ocr_correct.py`     | Sửa lỗi OCR tiếng Việt phổ biến |
| `Phase1.../clean.py`           | Chuẩn hóa Unicode NFC, bỏ header/footer, gọi sửa OCR |
| `Phase1.../chunk.py`           | Cắt chunk theo cấu trúc Chương/Điều/Khoản |
| `Phase1.../pipeline.py`        | Chạy Giai đoạn 1, xuất `chunks.jsonl` |
| `Phase2.../embed.py`           | Nhúng chunk → ChromaDB (Giai đoạn 2) |
| `Phase2.../search.py`          | Kiểm thử truy xuất từ vector DB |
| `Phase3.../rag.py`             | RAG: truy xuất + LLM sinh câu trả lời (Giai đoạn 3) |
| `Phase3.../test_rag.py`        | Test RAG theo lô câu hỏi (đánh giá chatbot) |
| `Phase4.../docx_to_csv.py`     | Chuyển .docx câu hỏi → .csv |
| `Phase4.../gen_qa_from_docs.py`| Sinh Q/A bám nội dung từng Điều trong kho tri thức |
| `Phase4.../gen_faq.py`         | Sinh bộ câu hỏi sinh viên thường gặp kèm đáp án có căn cứ |
| `Phase4.../enrich_qa.py`       | Viết lại đáp án ngắn thành đáp án chi tiết có trích dẫn |
| `Phase4.../merge_qa.py`        | Gộp mọi tệp Q/A rời → một tệp `qa_viu_full.csv` |
| `Phase4.../build_dataset.py`   | Dựng `train.jsonl` kèm khối TÀI LIỆU (khớp lúc chạy thật) |
| `Phase4.../train_qlora.py`     | Fine-tune QLoRA → LoRA adapter (Giai đoạn 4) |
| `Phase5.../app.py`             | Giao diện web chatbot + lịch sử đoạn chat (Giai đoạn 5) |
| `Phase5.../theme.py`           | Logo, màu thương hiệu và CSS của giao diện |

> Giai đoạn 6 (triển khai) sẽ thêm `Phase6-Deploy/`.

## Lộ trình
1. Xử lý dữ liệu ✅ · 2. Embedding + Vector DB ✅ · 3. Lắp RAG (retrieval + LLM) ✅ ·
4. Fine-tuning tư vấn (QLoRA) ✅ · 5. Giao diện web (Gradio) ✅ · 6. Kiểm thử & triển khai
