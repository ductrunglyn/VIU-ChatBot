# Chatbot Cố vấn Học tập — ĐH Công nghiệp Việt - Hung (VIU)

Trợ lý AI (kiến trúc **RAG**) trả lời câu hỏi về quy chế, chương trình đào tạo,
tuyển sinh và tư vấn lộ trình học tập cho sinh viên.

## 📖 Tài liệu

- [Hướng dẫn sử dụng web](docs/HUONG-DAN-SU-DUNG-WEB.md) — giao diện, cách dùng, xử lý sự cố

## Môi trường

Tên môi trường conda **khác nhau giữa các máy** (máy thầy Trung là `test`, server
`192.168.88.31` là `ChatBot`). Cài thư viện (chỉ cần 1 lần, đổi tên env cho đúng máy):
```bash
conda activate <tên_env>
pip install -r requirements.txt
pip install sentence-transformers chromadb    # cho Giai đoạn 2
```
Kiểm GPU: `nvidia-smi`.

---

## Chạy web (bước dùng lại thường xuyên nhất)

Web chạy nền trong `screen` để đóng terminal/mất SSH không bị ngắt. Có **2 screen
độc lập**: một chạy chính web, một chạy tunnel để có link truy cập từ Internet —
chỉ tạo tunnel khi cần chia sẻ ra ngoài mạng nội bộ trường.

### 1) Screen chạy web

```bash
bash scripts/chay-web.sh        # tự tạo/kiểm tra screen tên "ChatBot", tự dò env, tự kiểm tra điều kiện
```
Script tự dò env nào có đủ `gradio` + `torch` nên thường không cần sửa gì. Muốn
chỉ định thẳng: `ENV=ChatBot bash scripts/chay-web.sh` hoặc `PY=/đường/dẫn/python bash scripts/chay-web.sh`.

Script sẽ tự tạo screen (không cần `screen -S ChatBot` tay trước), kiểm tra vector
DB, adapter fine-tune, dung lượng GPU trống, rồi báo:
```
✅ Web đã lên: http://<IP-máy-chủ>:7860
```
Các lệnh khác:
```bash
bash scripts/chay-web.sh --xem    # xem nhật ký đang chạy (Ctrl+C để thoát, KHÔNG dừng web)
bash scripts/chay-web.sh --dung   # dừng web
screen -r ChatBot                 # vào thẳng bên trong screen (Ctrl+A rồi D để thoát ra mà không dừng)
```
Mở trình duyệt: `http://localhost:7860` (trên chính máy chủ) hoặc `http://<IP-máy-chủ>:7860` (máy khác cùng mạng LAN, xem IP bằng `hostname -I`).

### 2) Screen chạy tunnel (link công khai ra Internet)

Dùng khi cần truy cập từ ngoài mạng nội bộ trường (demo từ xa, chia sẻ cho người
không cùng LAN). Dùng Cloudflare Quick Tunnel — **không cần tài khoản**, mỗi lần
chạy sinh một địa chỉ ngẫu nhiên mới (dạng `https://<3-từ-ngẫu-nhiên>.trycloudflare.com`).

**Web phải đang chạy trước** (bước 1), vì tunnel chỉ chuyển tiếp tới cổng 7860.

```bash
screen -dmS CFTunnel bash -c \
  "cloudflared tunnel --url http://127.0.0.1:7860 2>&1 | tee ~/hdtrungoi/ChatBot/tunnel.log"
```
Lấy địa chỉ công khai vừa được cấp:
```bash
grep -o 'https://[a-z-]*\.trycloudflare\.com' ~/hdtrungoi/ChatBot/tunnel.log | head -1
```
Các lệnh khác:
```bash
screen -r CFTunnel                # vào thẳng bên trong screen xem trực tiếp
screen -S CFTunnel -X quit        # dừng tunnel (địa chỉ công khai sẽ chết theo)
```
> **Lưu ý:** địa chỉ tunnel **đổi mới mỗi lần chạy lại** — không lưu cố định được
> với Quick Tunnel. Nếu cần địa chỉ ổn định lâu dài, phải đăng ký tài khoản
> Cloudflare và cấu hình named tunnel (chưa thiết lập ở dự án này).
> **Cân nhắc trước khi bật:** tunnel để lộ chatbot (và qua đó là nội dung văn bản
> đã nạp) ra Internet công khai, ai có link đều truy cập được.

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
conda activate ChatBot
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
conda activate ChatBot
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
conda activate ChatBot
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

> **Cách chạy (kể cả link công khai qua tunnel): xem mục [Chạy web](#chạy-web-bước-dùng-lại-thường-xuyên-nhất) ở đầu tài liệu này.**

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
> Cần link công khai tạm thời (demo qua Internet): dùng tunnel, xem mục
> [Chạy web](#chạy-web-bước-dùng-lại-thường-xuyên-nhất) ở đầu tài liệu — không dùng
> `share=True` của Gradio (dự án không dùng cách này).

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
