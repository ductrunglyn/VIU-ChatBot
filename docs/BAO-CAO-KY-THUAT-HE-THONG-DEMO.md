# BÁO CÁO KỸ THUẬT HỆ THỐNG DEMO
## Chatbot hỗ trợ cố vấn học tập cho sinh viên Trường Đại học Công nghiệp Việt – Hung

*Tài liệu được xây dựng trên cơ sở phân tích trực tiếp mã nguồn, tệp cấu hình, dữ liệu và lịch sử phát triển của repository `VIU-ChatBot` tại thời điểm khảo sát.*

---

### QUY ƯỚC TRÌNH BÀY

Nhằm bảo đảm tính chính xác khoa học, toàn bộ nội dung báo cáo được phân loại theo bốn mức trạng thái. Người đọc cần lưu ý các nhãn này khi trích dẫn số liệu:

| Nhãn | Ý nghĩa |
|---|---|
| **[TK]** | Đã triển khai và thuộc luồng vận hành hiện tại của bản demo |
| **[CTC]** | Có trong mã nguồn nhưng **không** thuộc luồng vận hành hiện tại (do dữ liệu đầu vào đã thay đổi) |
| **[CXĐ]** | Chưa xác định được từ mã nguồn, cấu hình hoặc dữ liệu hiện có |
| **[ĐH]** | Định hướng phát triển, chưa được hiện thực hóa |

Mọi số liệu định lượng trong báo cáo đều được trích xuất trực tiếp từ hệ thống tại thời điểm khảo sát. Những nội dung không kiểm chứng được đã được ghi nhận tại **Chương 15**.

---

## CHƯƠNG 1. GIỚI THIỆU VÀ MỤC TIÊU HỆ THỐNG

### 1.1. Bối cảnh và sự cần thiết

Công tác cố vấn học tập tại các cơ sở giáo dục đại học hiện nay đối mặt với hai khó khăn có tính hệ thống. Thứ nhất, khối lượng văn bản quy phạm nội bộ (quy chế đào tạo, quy định học phí, quy định đào tạo trực tuyến, hướng dẫn sử dụng hệ thống quản lý học tập) có dung lượng lớn, cấu trúc pháp lý phức tạp theo mô hình Chương – Điều – Khoản, khiến sinh viên khó tra cứu chính xác điều khoản áp dụng cho trường hợp cụ thể của mình. Thứ hai, đội ngũ cố vấn học tập phải xử lý lặp đi lặp lại một khối lượng lớn câu hỏi có nội dung tương tự, làm giảm quỹ thời gian dành cho các tình huống tư vấn thực sự phức tạp.

### 1.2. Mục tiêu của hệ thống

Hệ thống demo được xây dựng nhằm các mục tiêu sau:

**Mục tiêu tổng quát:** Xây dựng một trợ lý hỏi–đáp tự động có khả năng trả lời các câu hỏi của sinh viên về quy chế, quy định đào tạo của Nhà trường, trên cơ sở **bám sát văn bản chính thức** thay vì dựa vào tri thức tổng quát của mô hình ngôn ngữ.

**Các mục tiêu cụ thể:**

1. Xây dựng quy trình tự động chuyển đổi văn bản quy phạm của Nhà trường thành cơ sở tri thức có cấu trúc, phục vụ truy xuất ngữ nghĩa.
2. Xây dựng cơ chế truy xuất thông tin hai tầng bảo đảm lựa chọn đúng điều khoản liên quan đến câu hỏi.
3. Tích hợp mô hình ngôn ngữ lớn theo kiến trúc Sinh có tăng cường truy xuất (Retrieval-Augmented Generation – RAG), trong đó mô hình chỉ được phép trả lời dựa trên tài liệu đã truy xuất.
4. Bảo đảm mỗi câu trả lời đều kèm trích dẫn nguồn ở mức điều khoản, cho phép người dùng kiểm chứng.
5. Triển khai toàn bộ hệ thống trên hạ tầng tính toán cục bộ của đơn vị, không phụ thuộc dịch vụ trí tuệ nhân tạo thương mại bên ngoài.

### 1.3. Vai trò của hệ thống trong đề tài

Hệ thống đóng vai trò là **sản phẩm minh chứng khả thi (proof-of-concept)** cho hướng ứng dụng mô hình ngôn ngữ lớn kết hợp truy xuất tri thức vào công tác hỗ trợ đào tạo. Mức độ hoàn thiện hiện tại là **bản demo có đầy đủ luồng xử lý từ đầu đến cuối**, đã vận hành được trên giao diện web, chưa phải sản phẩm triển khai diện rộng.

---

## CHƯƠNG 2. PHẠM VI VÀ ĐỐI TƯỢNG SỬ DỤNG

### 2.1. Đối tượng sử dụng

| Đối tượng | Hình thức sử dụng | Trạng thái |
|---|---|---|
| Sinh viên | Truy cập giao diện web, đặt câu hỏi bằng ngôn ngữ tự nhiên tiếng Việt | **[TK]** |
| Cố vấn học tập, cán bộ phòng đào tạo | Tra cứu nhanh điều khoản; đối chiếu câu trả lời với văn bản gốc | **[TK]** |
| Quản trị hệ thống | Cập nhật kho tài liệu, vận hành lại quy trình xử lý dữ liệu, huấn luyện lại mô hình | **[TK]** |

Hệ thống **chưa có** cơ chế xác thực người dùng, phân quyền hay quản lý tài khoản **[CXĐ – không tồn tại trong mã nguồn]**. Mọi người dùng truy cập được địa chỉ mạng của máy chủ đều sử dụng được với quyền như nhau.

### 2.2. Phạm vi tri thức

Phạm vi trả lời của hệ thống bị giới hạn nghiêm ngặt bởi tập tài liệu đã nạp. Tại thời điểm khảo sát, cơ sở tri thức được xây dựng từ **05 văn bản** sau:

| STT | Tên tài liệu | Số đoạn tri thức |
|---|---|---|
| 1 | Luật Giáo dục đại học | 50 |
| 2 | Quy chế đào tạo (số 220) | 37 |
| 3 | Tài liệu hướng dẫn sử dụng hệ thống LMS | 29 |
| 4 | Quy định đào tạo trực tuyến | 21 |
| 5 | Quy định về học phí và các khoản thu khác | 7 |
| | **Tổng cộng** | **144** |

**Ghi chú quan trọng:** Thư mục dữ liệu nguồn chứa 06 tệp, tuy nhiên tệp *"3. Quy định về chuẩn đầu ra ngoại ngữ và tin học"* có định dạng `.doc` (Word 97–2003) **không nằm trong danh sách định dạng được hỗ trợ** (`SUPPORTED_EXTS` trong `config.py` chỉ gồm `.pdf`, `.docx`, `.xlsx`, `.xls`, `.txt`, `.md`). Tệp này đã bị bỏ qua âm thầm trong quá trình xử lý, do đó **các câu hỏi về chuẩn đầu ra ngoại ngữ, tin học hiện không có cơ sở tri thức để trả lời**. Đây là một hạn chế cần khắc phục trước khi trình diễn (xem Mục 14.1).

### 2.3. Giới hạn phạm vi

Hệ thống **không** thực hiện các chức năng sau: tra cứu điểm cá nhân của sinh viên, đăng ký học phần, kết nối tới hệ thống quản lý đào tạo của Nhà trường, xử lý thủ tục hành chính, hay bất kỳ thao tác ghi dữ liệu nào. Hệ thống thuần túy là công cụ **hỏi – đáp tra cứu tri thức**.

---

## CHƯƠNG 3. KIẾN TRÚC TỔNG THỂ

### 3.1. Mô hình kiến trúc

Hệ thống được tổ chức theo kiến trúc **năm phân hệ tuần tự**, phản ánh trực tiếp cấu trúc thư mục mã nguồn. Hai phân hệ đầu vận hành **ngoại tuyến** (offline, chỉ chạy khi cập nhật tài liệu), ba phân hệ sau vận hành **trực tuyến** (online, phục vụ truy vấn của người dùng).

```
┌──────────────────── GIAI ĐOẠN NGOẠI TUYẾN (chạy khi cập nhật tài liệu) ───────────────────┐
│                                                                                           │
│  [Văn bản gốc]        Phân hệ 1                Phân hệ 2                                  │
│  data/raw/*.docx  →   Tiền xử lý dữ liệu   →   Vector hóa & lưu trữ                       │
│                       (trích xuất, làm sạch,    (BGE-M3 → ChromaDB)                       │
│                        phân đoạn theo Điều)                                               │
│                              ↓                        ↓                                   │
│                    data/interim/*.md         data/vectordb/                               │
│                    data/processed/chunks.jsonl                                            │
└───────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────── GIAI ĐOẠN TRỰC TUYẾN (phục vụ người dùng) ────────────────────────────┐
│                                                                                           │
│   Người dùng                Phân hệ 5              Phân hệ 3                              │
│   (trình duyệt)   ⇄    Giao diện web Gradio  ⇄   Lõi RAG (rag.py)                         │
│                        (app.py, cổng 7860)         │                                      │
│                                                    ├→ retriever.py → ChromaDB             │
│                                                    │                → BGE-reranker        │
│                                                    └→ Qwen2.5-3B + LoRA adapter           │
│                                                            ↑                              │
│                                                     Phân hệ 4: Tinh chỉnh QLoRA           │
│                                                     (tạo adapter, chạy ngoại tuyến)       │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2. Đặc điểm kiến trúc

**Kiến trúc đơn tiến trình, không phân tách dịch vụ.** Toàn bộ phân hệ trực tuyến (giao diện, lõi RAG, mô hình nhúng, mô hình xếp hạng lại, mô hình ngôn ngữ) chạy trong **cùng một tiến trình Python**. Giao diện gọi trực tiếp hàm Python của lõi RAG (`app.py` nhập khẩu mô-đun `rag`), không thông qua giao thức mạng nội bộ. Hệ thống **không** sử dụng kiến trúc vi dịch vụ, **không** có máy chủ mô hình riêng biệt, **không** có tầng API trung gian tự xây dựng.

**Hệ quả kỹ thuật:** thiết kế này giảm độ trễ truyền thông và đơn giản hóa triển khai, phù hợp với quy mô demo; nhưng đồng thời giới hạn khả năng mở rộng theo chiều ngang (xem Mục 14.4).

**Cấu hình tập trung.** Toàn bộ tham số vận hành của cả năm phân hệ được khai báo tại một tệp duy nhất `src/common/config.py`. Đây là điểm thiết kế cho phép thay đổi mô hình, ngưỡng truy xuất hay tham số huấn luyện mà không phải sửa mã nguồn nghiệp vụ.

---

## CHƯƠNG 4. KIẾN TRÚC KỸ THUẬT CHI TIẾT

### 4.1. Tổ chức mã nguồn

Mã nguồn được tổ chức theo phân hệ chức năng, mỗi thư mục tương ứng một giai đoạn trong quy trình:

```
ChatBot/
├── src/
│   ├── common/                      # Thành phần dùng chung
│   │   ├── config.py                # Cấu hình tập trung toàn hệ thống
│   │   └── retriever.py             # Truy xuất hai tầng (dense + rerank)
│   ├── Phase1-DataPreprocessing/    # Phân hệ 1: Tiền xử lý dữ liệu
│   │   ├── extract.py               # Trích xuất văn bản và bảng
│   │   ├── ocr.py                   # Nhận dạng ký tự quang học  [CTC]
│   │   ├── table_ocr.py             # Nhận dạng bảng trên ảnh    [CTC]
│   │   ├── ocr_correct.py           # Hiệu chỉnh lỗi nhận dạng tiếng Việt
│   │   ├── clean.py                 # Chuẩn hóa và làm sạch văn bản
│   │   ├── chunk.py                 # Phân đoạn theo cấu trúc pháp lý
│   │   └── pipeline.py              # Điều phối toàn bộ Phân hệ 1
│   ├── Phase2-Embedding/            # Phân hệ 2: Vector hóa
│   │   ├── embed.py                 # Sinh vector và ghi vào ChromaDB
│   │   └── search.py                # Công cụ kiểm thử truy xuất
│   ├── Phase3-RAG/                  # Phân hệ 3: Lõi RAG
│   │   ├── rag.py                   # Xây dựng ngữ cảnh, sinh câu trả lời
│   │   └── test_rag.py              # Kiểm thử theo lô câu hỏi
│   ├── Phase4-Finetuning/           # Phân hệ 4: Tinh chỉnh mô hình
│   │   ├── docx_to_csv.py           # Chuyển bộ câu hỏi Word sang CSV
│   │   ├── build_dataset.py         # Tạo tập huấn luyện định dạng hội thoại
│   │   └── train_qlora.py           # Huấn luyện QLoRA
│   └── Phase5-UI/
│       └── app.py                   # Giao diện web Gradio
├── data/
│   ├── raw/                         # Văn bản gốc
│   ├── interim/                     # Văn bản đã làm sạch (kiểm tra thủ công)
│   ├── processed/chunks.jsonl       # Cơ sở tri thức dạng đoạn
│   ├── qa/                          # Bộ câu hỏi – đáp án phục vụ tinh chỉnh
│   └── vectordb/                    # Cơ sở dữ liệu vector ChromaDB
└── models/qlora-viu/                # Bộ trọng số LoRA sau tinh chỉnh
```

### 4.2. Phân hệ 1 – Tiền xử lý dữ liệu

Phân hệ này chuyển văn bản hành chính thành các đoạn tri thức có gắn siêu dữ liệu pháp lý. Quy trình gồm bốn bước tuần tự do `pipeline.py` điều phối:

**Bước 1 – Trích xuất (`extract.py`).** Hàm `extract_file()` định tuyến theo phần mở rộng tệp. Với định dạng `.docx` (nguồn dữ liệu hiện tại), hàm `extract_docx()` sử dụng thư viện `python-docx` để đọc lần lượt toàn bộ đoạn văn, sau đó đọc các bảng và chuyển mỗi bảng thành cú pháp bảng Markdown nhằm bảo toàn quan hệ hàng – cột. **[TK]**

Mô-đun còn hiện thực hai nhánh xử lý tài liệu quét ảnh: nhận dạng ký tự bằng EasyOCR trên GPU (`ocr.py`) và nhận dạng cấu trúc bảng bằng `img2table` (`table_ocr.py`). Các nhánh này chỉ kích hoạt với tệp PDF có trang không chứa lớp văn bản số. **[CTC – tập dữ liệu hiện tại không còn tệp PDF quét ảnh]**

**Bước 2 – Làm sạch (`clean.py`).** Hàm `clean_text()` thực hiện tuần tự: chuẩn hóa Unicode về dạng NFC (thao tác bắt buộc với tiếng Việt để hợp nhất ký tự tổ hợp và ký tự dựng sẵn); loại bỏ các dòng tiêu đề, chân trang lặp lại trên nhiều trang theo ngưỡng tần suất; loại bỏ dòng chỉ chứa số trang; nối từ bị ngắt bởi dấu gạch nối cuối dòng; chuẩn hóa khoảng trắng; và cuối cùng gọi `ocr_correct.correct_text()`.

**Bước 3 – Hiệu chỉnh lỗi tiếng Việt (`ocr_correct.py`).** Mô-đun áp dụng hai tầng quy tắc: tầng quy tắc ký tự xử lý họ vần "ươ" bị sai và ký tự "I" hoa bị nhận nhầm thành "l"; tầng từ điển xử lý các chuỗi chắc chắn sai (ví dụ `dào` → `đào`, `dịnh` → `định`). Nguyên tắc thiết kế được ghi rõ trong mã nguồn là **chỉ hiệu chỉnh những dạng chắc chắn sai**, không can thiệp vào từ có thể hợp lệ, nhằm tránh tạo ra lỗi mới.

**Bước 4 – Phân đoạn (`chunk.py`).** Đây là thành phần mang tính đặc thù nghiệp vụ cao nhất của phân hệ. Thay vì cắt văn bản theo số lượng từ cố định như cách làm phổ thông, mô-đun áp dụng chiến lược lai:

- Biểu thức chính quy `_DIEU_RE` nhận diện mốc "Điều N" tại bất kỳ vị trí nào trong văn bản, nhưng đặt hai điều kiện ràng buộc: phải có dấu chấm hoặc hai chấm ngay sau số, và ký tự kế tiếp phải là chữ hoa tiếng Việt. Ràng buộc này loại bỏ các tham chiếu chéo dạng "theo Điều 5 của Quy chế này".
- Hàm `_find_dieu_boundaries()` bổ sung tầng lọc thứ hai: chỉ giữ các mốc có số hiệu **tăng dần đơn điệu**, loại tiếp các tham chiếu lùi số.
- Điều nào vượt ngưỡng `CHUNK_MAX_WORDS` được cắt tiếp theo ranh giới câu, có phần chồng lấp `CHUNK_OVERLAP_WORDS` từ giữa hai đoạn liền kề để tránh mất ngữ cảnh tại điểm cắt.
- Tài liệu không có cấu trúc "Điều" được xử lý bằng nhánh `_chunk_generic()` cắt theo tiêu đề Markdown hoặc theo số từ.
- Các đoạn quá ngắn được gộp vào đoạn liền trước bởi `merge_tiny_chunks()`.

Mỗi đoạn kết quả mang siêu dữ liệu: `chunk_id`, `source`, `text`, `word_count`, `chuong`, `dieu`, `heading`. **Siêu dữ liệu `dieu` và `chuong` chính là cơ sở để hệ thống trích dẫn nguồn ở mức điều khoản** — đây là mắt xích nối trực tiếp giữa khâu xử lý dữ liệu và độ tin cậy của câu trả lời cuối cùng.

**Tham số phân đoạn thực tế** (`config.py`): mục tiêu 400 từ/đoạn; ngưỡng tối đa 550 từ; ngưỡng gộp tối thiểu 40 từ; chồng lấp 50 từ.

### 4.3. Phân hệ 2 – Vector hóa và lưu trữ

**Mô hình nhúng.** Hệ thống sử dụng **BAAI/bge-m3** nạp qua thư viện `sentence-transformers`, thực thi trên GPU. Đây là mô hình nhúng đa ngôn ngữ hỗ trợ tiếng Việt. Vector được chuẩn hóa (`normalize_embeddings=True`), kích thước lô xử lý 32.

**Cơ sở dữ liệu vector.** Hệ thống dùng **ChromaDB** ở chế độ lưu trữ bền vững cục bộ (`PersistentClient`), lưu tại `data/vectordb/`. Bộ sưu tập tên `viu_docs` được tạo với tham số `hnsw:space = cosine`, tức sử dụng chỉ mục HNSW với độ đo tương đồng cosine.

Mỗi bản ghi gồm: định danh `chunk_id`, nội dung văn bản gốc của đoạn, vector nhúng, và siêu dữ liệu. Do ChromaDB không chấp nhận giá trị rỗng kiểu `None`, mã nguồn quy đổi các trường siêu dữ liệu rỗng thành chuỗi rỗng.

**Trạng thái thực tế:** bộ sưu tập `viu_docs` hiện chứa **144 vector**, khớp chính xác với 144 đoạn trong `chunks.jsonl`; dung lượng lưu trữ 3,6 MB. Thao tác nạp lại (`--reset`) xóa và tạo lại toàn bộ bộ sưu tập, bảo đảm tính nhất quán giữa cơ sở tri thức và chỉ mục vector.

### 4.4. Phân hệ 3 – Lõi RAG

Đây là trung tâm xử lý của hệ thống, gồm hai mô-đun phối hợp:

**`common/retriever.py` – Truy xuất hai tầng.** Hàm `retrieve()` thực hiện:
1. *Tầng truy hồi thô:* mã hóa câu hỏi thành vector bằng cùng mô hình BGE-M3, truy vấn ChromaDB lấy **20 ứng viên** (`RETRIEVE_CANDIDATES`).
2. *Tầng xếp hạng lại:* nạp mô hình **BAAI/bge-reranker-v2-m3** dưới dạng `CrossEncoder`, chấm điểm từng cặp (câu hỏi, đoạn văn) và sắp xếp lại theo điểm giảm dần.
3. Trả về **5 đoạn** tốt nhất (`RAG_TOP_K`).

Điểm khác biệt kỹ thuật giữa hai tầng: tầng một mã hóa câu hỏi và tài liệu **độc lập** rồi so sánh vector, cho tốc độ cao nhưng khả năng phân biệt hạn chế; tầng hai đưa **đồng thời** câu hỏi và tài liệu qua mạng nơ-ron, cho phép mô hình phân tích quan hệ trực tiếp giữa hai văn bản, độ chính xác cao hơn nhưng chi phí tính toán lớn hơn nên chỉ áp dụng cho 20 ứng viên đã lọc.

Hàm `format_source()` sinh chuỗi trích dẫn theo mẫu `"Điều X, <tên tài liệu>"`, trong đó tên tài liệu được làm sạch khỏi mã số hiệu và ngày tháng trong tên tệp.

**`Phase3-RAG/rag.py` – Xây dựng ngữ cảnh và sinh câu trả lời.**

- `_build_context()` ghép năm đoạn đã truy xuất thành khối văn bản đánh số `[1]`…`[5]`, mỗi khối kèm nhãn nguồn; đồng thời sinh danh sách trích dẫn trả về giao diện.
- `_build_messages()` lắp ráp chuỗi hội thoại: thông điệp hệ thống → các cặp hỏi–đáp trước đó → thông điệp người dùng chứa khối `TÀI LIỆU` và `CÂU HỎI`.
- `_load_llm()` nạp mô hình ngôn ngữ ở độ chính xác `bfloat16` lên GPU; nếu thư mục adapter tồn tại và cờ `USE_FINETUNED` bật, mô-đun bọc mô hình bằng `PeftModel` để áp bộ trọng số LoRA đã tinh chỉnh.
- `answer_stream()` sinh câu trả lời theo cơ chế **luồng (streaming)**: sử dụng `TextIteratorStreamer` và chạy hàm sinh trên một luồng riêng, trả về văn bản tích lũy dần qua cơ chế `yield`.

**Tham số sinh văn bản:** số token tối đa 512; `temperature = 0,1`; `top_p = 0,9`; lấy mẫu có bật (`do_sample=True`). Giá trị nhiệt độ rất thấp được lựa chọn nhằm ưu tiên tính ổn định và bám sát tài liệu.

### 4.5. Phân hệ 4 – Tinh chỉnh mô hình

**Quy trình chuẩn bị dữ liệu.** `docx_to_csv.py` phân tích tệp Word chứa bộ câu hỏi theo cấu trúc nhãn ("Câu N", "Chủ đề:", "Câu hỏi:", "Đáp án:", "Tài liệu tham chiếu:"), hỗ trợ cả trường hợp toàn bộ một câu nằm trong một đoạn văn với ký tự xuống dòng mềm. `build_dataset.py` gộp các tệp CSV, loại trùng theo nội dung câu hỏi đã chuẩn hóa, và xuất tệp `train.jsonl` theo định dạng hội thoại ba vai (`system`, `user`, `assistant`).

**Cấu hình huấn luyện (`train_qlora.py`).** Hệ thống áp dụng phương pháp **QLoRA**:
- Mô hình nền được lượng tử hóa 4 bit, kiểu `nf4`, có lượng tử hóa kép, kiểu tính toán `bfloat16`.
- Bộ điều hợp LoRA: hạng `r = 16`, hệ số `alpha = 32`, tỉ lệ bỏ học 0,05, áp lên bảy ma trận chiếu (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`).
- Tham số tối ưu: 8 vòng lặp, tốc độ học 2·10⁻⁴, kích thước lô 2, tích lũy gradient 4 bước, độ dài chuỗi tối đa 1024, bộ lập lịch cosine.
- Mô-đun thay thế khuôn mẫu hội thoại bằng phiên bản có thẻ `{% generation %}` bao quanh nội dung câu trả lời (bao gồm cả token kết thúc lượt), cho phép bật `assistant_only_loss=True` — tức **hàm mất mát chỉ tính trên phần câu trả lời của trợ lý**, không tính trên phần câu hỏi và tài liệu.

**Trạng thái bộ trọng số hiện tại.** Bộ điều hợp lưu tại `models/qlora-viu/` có dung lượng khoảng 57 MB, khai báo mô hình nền `Qwen/Qwen2.5-3B-Instruct` với các tham số LoRA đúng như cấu hình. Tuy nhiên, đối chiếu mốc thời gian cho thấy: **bộ trọng số này được sinh ra trước thời điểm bộ dữ liệu huấn luyện hiện tại được tạo lập**. Do đó bộ điều hợp đang được hệ thống nạp **không phải** kết quả huấn luyện trên tập 1.549 mẫu hiện có, mà là kết quả của một lần huấn luyện trước đó trên tập dữ liệu nhỏ hơn. Tại thời điểm khảo sát, một tiến trình huấn luyện lại đang được thực thi. **Số liệu chính xác về tập dữ liệu tương ứng với bộ trọng số cuối cùng cần được xác nhận lại sau khi tiến trình này kết thúc.**

### 4.6. Phân hệ 5 – Giao diện web

Giao diện xây dựng bằng **Gradio**, sử dụng thành phần dựng sẵn `ChatInterface`. Các đặc điểm triển khai:

- Hàm `chat_fn()` là hàm sinh (generator), chuyển tiếp từng phần văn bản từ `rag.answer_stream()` ra giao diện, tạo hiệu ứng hiển thị dần.
- Sau khi hoàn tất, hàm nối thêm khối **"Nguồn tham khảo"** liệt kê các điều khoản đã sử dụng.
- `_history_to_pairs()` chuyển lịch sử hội thoại của Gradio thành danh sách cặp hỏi–đáp, đồng thời **cắt bỏ khối trích dẫn** khỏi các câu trả lời cũ để không làm loãng ngữ cảnh, và giới hạn số lượt đưa vào ngữ cảnh.
- `_as_text()` ép kiểu nội dung tin nhắn về chuỗi ký tự — xử lý trường hợp Gradio trả về nội dung dạng danh sách ở các lượt sau.
- Tham số `concurrency_limit=1` buộc các yêu cầu được xử lý **tuần tự**, phù hợp với hạ tầng một GPU.
- Máy chủ lắng nghe trên `0.0.0.0`, cổng 7860, chế độ chia sẻ công khai **tắt** (`share=False`), tức chỉ truy cập được trong mạng nội bộ.
- Khi khởi động, hệ thống nạp sẵn toàn bộ mô hình và thực hiện một truy vấn làm nóng, nhằm loại bỏ độ trễ khởi tạo ở câu hỏi đầu tiên của người dùng.

---

## CHƯƠNG 5. CÁC CÔNG NGHỆ VÀ THÀNH PHẦN LÕI

### 5.1. Bảng công nghệ và vai trò

| Công nghệ / Thư viện | Phiên bản | Vai trò trong hệ thống |
|---|---|---|
| Python | 3.10.0 | Ngôn ngữ triển khai toàn hệ thống |
| PyTorch | 2.12.1+cu130 | Nền tảng tính toán tensor, thực thi mô hình trên GPU |
| Transformers | 5.13.0 | Nạp và thực thi mô hình ngôn ngữ; khuôn mẫu hội thoại; sinh văn bản theo luồng |
| sentence-transformers | 5.6.0 | Nạp mô hình nhúng BGE-M3 và mô hình xếp hạng lại CrossEncoder |
| ChromaDB | 1.5.9 | Cơ sở dữ liệu vector lưu trữ bền vững, chỉ mục HNSW độ đo cosine |
| PEFT | 0.19.1 | Áp dụng bộ điều hợp LoRA lên mô hình nền |
| TRL | 1.7.1 | Bộ huấn luyện tinh chỉnh có giám sát (SFTTrainer) |
| bitsandbytes | 0.49.2 | Lượng tử hóa 4 bit phục vụ QLoRA |
| Datasets | 5.0.0 | Nạp tập dữ liệu huấn luyện |
| Gradio | 6.19.0 | Giao diện web hỏi–đáp |
| python-docx | 1.2.0 | Trích xuất văn bản và bảng từ tệp Word |
| pdfplumber | 0.11.10 | Trích xuất văn bản và bảng từ PDF **[CTC]** |
| EasyOCR | 1.7.2 | Nhận dạng ký tự quang học tiếng Việt **[CTC]** |
| img2table | (chưa xác định) | Nhận dạng cấu trúc bảng trên trang quét **[CTC]** |

### 5.2. Bảng mô hình trí tuệ nhân tạo

| Mô hình | Vai trò | Vị trí thực thi |
|---|---|---|
| `BAAI/bge-m3` | Sinh vector ngữ nghĩa cho đoạn tài liệu và câu hỏi | GPU, cục bộ |
| `BAAI/bge-reranker-v2-m3` | Xếp hạng lại độ liên quan của cặp (câu hỏi, đoạn) | GPU, cục bộ |
| `Qwen/Qwen2.5-3B-Instruct` | Sinh câu trả lời ngôn ngữ tự nhiên | GPU, cục bộ |
| `qlora-viu` (bộ điều hợp LoRA) | Hiệu chỉnh văn phong và cách trả lời theo nghiệp vụ cố vấn | Áp lên mô hình nền |

**Toàn bộ mô hình vận hành cục bộ.** Hệ thống không gọi tới bất kỳ dịch vụ trí tuệ nhân tạo thương mại nào. Điều này có ý nghĩa trực tiếp về bảo mật dữ liệu nội bộ và chi phí vận hành (xem Mục 12.3).

### 5.3. Cơ sở lựa chọn mô hình ngôn ngữ

Lịch sử phát triển ghi nhận hệ thống ban đầu sử dụng `Qwen2.5-1.5B-Instruct`, sau đó chuyển sang bản 3 tỉ tham số. Chú thích trong tệp cấu hình ghi rõ căn cứ: mô hình 3 tỉ tham số cho kết quả suy luận trên các mốc số quy định tốt hơn, với mức tiêu thụ bộ nhớ đồ họa vẫn nằm trong giới hạn phần cứng hiện có. Mã nguồn giữ lại khả năng chuyển đổi mô hình qua tham số dòng lệnh `--model` mà không cần sửa mã.

---

## CHƯƠNG 6. QUY TRÌNH XỬ LÝ MỘT CÂU HỎI (LUỒNG ĐẦU–CUỐI)

Mục này mô tả chi tiết đường đi của một câu hỏi, chỉ rõ thành phần thực hiện từng bước.

### 6.1. Sơ đồ tuần tự

| Bước | Hành động | Thành phần thực hiện |
|---|---|---|
| 1 | Sinh viên nhập câu hỏi tiếng Việt và gửi | Trình duyệt → `ChatInterface` |
| 2 | Tiếp nhận yêu cầu, trích lịch sử hội thoại | `app.py :: chat_fn()` |
| 3 | Chuẩn hóa lịch sử: ép kiểu chuỗi, cắt bỏ khối trích dẫn cũ, giới hạn số lượt | `app.py :: _history_to_pairs()` |
| 4 | Mã hóa câu hỏi thành vector chuẩn hóa | `retriever.py` + BGE-M3 |
| 5 | Truy vấn 20 đoạn ứng viên gần nhất theo cosine | ChromaDB (`viu_docs`) |
| 6 | Chấm điểm lại 20 cặp (câu hỏi, đoạn), sắp xếp giảm dần | BGE-reranker-v2-m3 |
| 7 | Chọn 5 đoạn tốt nhất | `retriever.py :: retrieve()` |
| 8 | Ghép khối `TÀI LIỆU` đánh số, sinh danh sách trích dẫn | `rag.py :: _build_context()` |
| 9 | Lắp ráp chuỗi hội thoại: hệ thống → lịch sử → tài liệu + câu hỏi | `rag.py :: _build_messages()` |
| 10 | Áp khuôn mẫu hội thoại, mã hóa token, chuyển lên GPU | Tokenizer của Transformers |
| 11 | Sinh câu trả lời theo luồng trên luồng xử lý riêng | Qwen2.5-3B + LoRA, `TextIteratorStreamer` |
| 12 | Trả về từng phần văn bản tích lũy | `rag.py :: answer_stream()` |
| 13 | Hiển thị dần trên giao diện | `app.py :: chat_fn()` → trình duyệt |
| 14 | Nối khối "Nguồn tham khảo" sau khi sinh xong | `app.py :: chat_fn()` |

### 6.2. Cấu trúc lời nhắc gửi tới mô hình ngôn ngữ

Lời nhắc thực tế có cấu trúc ba tầng:

```
[Vai trò hệ thống]
  Bạn là trợ lý cố vấn học tập của Trường ĐHCN Việt - Hung.
  Hãy trả lời DỰA HOÀN TOÀN trên phần TÀI LIỆU bên dưới.
  Cách trả lời:
    1. Trả lời TRỰC TIẾP câu hỏi ngay ở câu đầu tiên.
    2. Nếu câu hỏi nêu con số cụ thể (CPA, điểm, tín chỉ, số lần cảnh báo...),
       hãy SO SÁNH con số đó với đúng mốc quy định rồi mới kết luận.
       Phân biệt rõ 'cảnh báo học tập' KHÁC 'buộc thôi học'.
    3. Giải thích ngắn gọn căn cứ và nêu bước hành động cụ thể.
    4. Ghi nguồn [1], [2]... cho thông tin đã dùng.
  Ràng buộc:
    - Chỉ dùng thông tin trong TÀI LIỆU; TUYỆT ĐỐI không bịa.
    - Nếu tài liệu không đủ thông tin, nói rõ là chưa tìm thấy trong quy định
      và khuyên sinh viên liên hệ phòng đào tạo / cố vấn học tập.
    - CHỈ trả lời bằng TIẾNG VIỆT.

[Lịch sử hội thoại]   (tối đa 3 lượt gần nhất)
  Người dùng: ...
  Trợ lý: ...

[Lượt hiện tại]
  TÀI LIỆU:
  [1] (Nguồn: Điều 11, quy chế đào tạo 220)
  <nội dung đoạn 1>

  [2] (Nguồn: Điều 12, quy chế đào tạo 220)
  <nội dung đoạn 2>
  ... (tới đoạn [5])

  CÂU HỎI: <câu hỏi của sinh viên>
```

Cấu trúc này thể hiện ba nguyên tắc thiết kế có thể kiểm chứng trong mã nguồn: (i) tri thức được **cấp phát tại thời điểm truy vấn** chứ không dựa vào trí nhớ tham số của mô hình; (ii) mỗi đoạn tri thức được **gắn nhãn nguồn ngay trong lời nhắc**, tạo điều kiện để mô hình trích dẫn; (iii) các ràng buộc hành vi được phát biểu tường minh.

---

## CHƯƠNG 7. CÁC CHỨC NĂNG CHÍNH

### 7.1. Bảng chức năng

| Chức năng | Cơ chế thực hiện | Giá trị đối với sinh viên | Trạng thái |
|---|---|---|---|
| Hỏi–đáp quy chế bằng ngôn ngữ tự nhiên | RAG: truy xuất hai tầng + sinh câu trả lời | Không cần biết điều khoản nằm ở đâu, hỏi bằng lời thường ngày | **[TK]** |
| Trích dẫn nguồn ở mức điều khoản | Siêu dữ liệu `dieu` gắn từ khâu phân đoạn, hiển thị qua `format_source()` | Kiểm chứng được câu trả lời, tra ngược văn bản gốc | **[TK]** |
| Hội thoại nhiều lượt | Ghép tối đa 3 lượt gần nhất vào ngữ cảnh | Hỏi nối tiếp mà không phải lặp lại bối cảnh | **[TK]** |
| Hiển thị câu trả lời theo luồng | `TextIteratorStreamer` trên luồng riêng | Giảm cảm giác chờ đợi | **[TK]** |
| Từ chối câu hỏi ngoài phạm vi | Ràng buộc trong lời nhắc hệ thống | Tránh nhận thông tin sai lệch | **[TK]** |
| Câu hỏi gợi ý sẵn | Danh sách `EXAMPLES` trong giao diện | Định hướng cách đặt câu hỏi hiệu quả | **[TK]** |
| Tra cứu nội dung bảng biểu | Bảng được chuyển thành Markdown khi trích xuất | Tra cứu được thông tin dạng bảng | **[TK]** một phần |
| Cập nhật kho tri thức | Chạy lại `pipeline.py` và `embed.py` | Tri thức theo kịp văn bản mới ban hành | **[TK]** (dành cho quản trị) |
| Kiểm thử theo lô câu hỏi | `test_rag.py`, cờ `--base` so sánh mô hình gốc | Công cụ đánh giá chất lượng | **[TK]** (dành cho quản trị) |

### 7.2. Phân tích một số chức năng trọng tâm

**Trích dẫn nguồn ở mức điều khoản.** Đây là chức năng có giá trị nghiệp vụ cao nhất trong bối cảnh tư vấn quy chế, vì nó biến câu trả lời của hệ thống từ "thông tin tham khảo không rõ căn cứ" thành "thông tin có thể đối chiếu". Về mặt kỹ thuật, chức năng này **không** đạt được nhờ mô hình ngôn ngữ mà nhờ chuỗi thiết kế xuyên suốt ba phân hệ: khâu phân đoạn nhận diện và lưu số hiệu điều khoản; khâu vector hóa bảo toàn siêu dữ liệu này trong cơ sở dữ liệu; khâu sinh câu trả lời hiển thị lại chúng. Đây là lý do việc phân đoạn theo cấu trúc pháp lý (thay vì theo số từ) là lựa chọn thiết kế có chủ đích.

**Từ chối câu hỏi ngoài phạm vi.** Cơ chế hiện tại **thuần túy dựa trên chỉ dẫn trong lời nhắc**, không có tầng kiểm tra bằng mã. Hệ thống có khai báo tham số ngưỡng điểm tương đồng `RAG_MIN_SCORE = 0.35` trong tệp cấu hình, tuy nhiên **kiểm tra toàn bộ mã nguồn xác nhận tham số này hiện không được sử dụng ở bất kỳ đâu** — đây là cấu hình tồn dư từ phiên bản trước khi bổ sung tầng xếp hạng lại. Hệ quả: hệ thống luôn đưa 5 đoạn tốt nhất vào ngữ cảnh kể cả khi độ liên quan thấp, và việc từ chối trả lời hoàn toàn phụ thuộc vào mức độ tuân thủ chỉ dẫn của mô hình ngôn ngữ. Đây là một hạn chế về độ tin cậy cần được ghi nhận trung thực (xem Mục 14.2).

---

## CHƯƠNG 8. CƠ CHẾ AI/LLM VÀ TRUY XUẤT TRI THỨC

### 8.1. Các kỹ thuật đã áp dụng

| Kỹ thuật | Hiện diện | Chi tiết triển khai |
|---|---|---|
| Sinh có tăng cường truy xuất (RAG) | **Có [TK]** | Toàn bộ luồng `rag.py` |
| Nhúng ngữ nghĩa (embedding) | **Có [TK]** | BGE-M3, vector chuẩn hóa |
| Cơ sở dữ liệu vector | **Có [TK]** | ChromaDB, HNSW, cosine |
| Xếp hạng lại (reranking) | **Có [TK]** | CrossEncoder BGE-reranker-v2-m3, 20 → 5 |
| Kỹ thuật lời nhắc có ràng buộc | **Có [TK]** | Lời nhắc hệ thống bốn quy tắc + ba ràng buộc |
| Tinh chỉnh hiệu quả tham số (QLoRA) | **Có [TK]** | 4 bit nf4 + LoRA hạng 16 |
| Sinh theo luồng (streaming) | **Có [TK]** | `TextIteratorStreamer` |
| Quản lý ngữ cảnh hội thoại | **Có [TK]** | Giới hạn số lượt |
| Gọi công cụ (tool calling) | **Không** | Không tồn tại trong mã nguồn |
| Kiến trúc tác tử (agent) | **Không** | Không tồn tại |
| Tìm kiếm lai (hybrid: từ khóa + ngữ nghĩa) | **Không** | Chỉ truy xuất theo vector |
| Viết lại truy vấn (query rewriting) | **Không** | Câu hỏi được dùng nguyên trạng |
| Kiểm chứng câu trả lời tự động | **Không** | Không có tầng hậu kiểm |

Bảng trên được lập nhằm phân định rõ ràng những gì hệ thống **thực sự có** với những kỹ thuật thường được nhắc tới trong các hệ thống hỏi–đáp hiện đại nhưng **không** hiện diện trong sản phẩm này.

### 8.2. Vai trò của mô hình ngôn ngữ trong kiến trúc

Cần nhấn mạnh một đặc điểm kiến trúc quan trọng: trong hệ thống này, mô hình ngôn ngữ **không đóng vai trò nguồn tri thức**, mà đóng vai trò **bộ đọc hiểu và diễn đạt**. Tri thức chuyên ngành (nội dung quy chế) nằm hoàn toàn trong cơ sở dữ liệu vector; mô hình có nhiệm vụ đọc năm đoạn được cấp, tổng hợp và diễn đạt lại thành câu trả lời tiếng Việt phù hợp với câu hỏi.

Phân định vai trò này có ba hệ quả thực tiễn: (i) khi văn bản của Nhà trường thay đổi, chỉ cần chạy lại quy trình xử lý dữ liệu, **không cần huấn luyện lại mô hình**; (ii) sai sót về nội dung quy chế chủ yếu bắt nguồn từ khâu truy xuất chứ không phải từ mô hình; (iii) có thể thay thế mô hình ngôn ngữ bằng mô hình khác mà không ảnh hưởng tới cơ sở tri thức.

### 8.3. Về vai trò của khâu tinh chỉnh

Phân tích mã nguồn cho thấy một khác biệt có ý nghĩa giữa dữ liệu huấn luyện và dữ liệu suy luận, cần được ghi nhận chính xác:

- Trong tập huấn luyện (`build_dataset.py`), mỗi mẫu gồm: lời nhắc hệ thống **ngắn gọn** (không có khối `TÀI LIỆU`), câu hỏi của sinh viên, và đáp án mẫu.
- Trong suy luận (`rag.py`), lời nhắc hệ thống **dài hơn nhiều** và thông điệp người dùng **có chứa khối `TÀI LIỆU`** gồm năm đoạn trích.

Như vậy, quá trình tinh chỉnh dạy cho mô hình **văn phong, giọng điệu và cách thức trả lời của một cố vấn học tập**, nhưng **không** dạy mô hình kỹ năng "đọc tài liệu được cấp rồi trả lời", vì định dạng dữ liệu huấn luyện không chứa tình huống đó. Kỹ năng bám tài liệu trong hệ thống hiện tại đến từ **năng lực sẵn có của mô hình nền cộng với ràng buộc trong lời nhắc**, không phải từ khâu tinh chỉnh.

Đây là một nhận định kỹ thuật quan trọng: nó cho biết chính xác khâu tinh chỉnh đóng góp gì và không đóng góp gì, đồng thời chỉ ra hướng cải thiện cụ thể (xem Mục 14.6).

### 8.4. Thống kê bộ dữ liệu tinh chỉnh

Tại thời điểm khảo sát, bộ dữ liệu câu hỏi – đáp án gồm **1.679 câu** trong tệp CSV, sau khi loại trùng còn **1.549 mẫu** trong tệp huấn luyện, phân bố theo bốn nhóm chủ đề:

| Nhóm chủ đề | Số câu | Tỉ lệ |
|---|---|---|
| Quản lý học tập và tiến độ đào tạo | 729 | 43,4% |
| Đánh giá kết quả học tập | 420 | 25,0% |
| Công nhận tín chỉ và chuyển đổi học tập | 330 | 19,7% |
| Tốt nghiệp, quyền và nghĩa vụ sinh viên | 200 | 11,9% |
| **Tổng** | **1.679** | **100%** |

Bộ dữ liệu này do đội ngũ chuyên môn của Nhà trường biên soạn, là **đóng góp dữ liệu có giá trị riêng của đề tài**, độc lập với phần mã nguồn.

---

## CHƯƠNG 9. QUẢN LÝ NGỮ CẢNH VÀ CƠ CHẾ BẢO ĐẢM ĐỘ TIN CẬY

### 9.1. Quản lý ngữ cảnh hội thoại

Hệ thống áp dụng chiến lược **cửa sổ trượt** đơn giản: chỉ ba lượt hỏi–đáp gần nhất được đưa vào ngữ cảnh. Ba đặc điểm bổ sung:

1. **Loại bỏ khối trích dẫn khỏi lịch sử.** Câu trả lời cũ được cắt bỏ phần "Nguồn tham khảo" trước khi đưa vào ngữ cảnh, tránh chiếm dụng cửa sổ ngữ cảnh bằng thông tin không cần thiết cho suy luận.
2. **Truy xuất độc lập theo từng lượt.** Mỗi câu hỏi mới đều kích hoạt một lượt truy xuất mới trên toàn bộ cơ sở tri thức. Hệ thống **không** viết lại câu hỏi dựa trên lịch sử trước khi truy xuất — đây là một hạn chế: với câu hỏi rút gọn phụ thuộc ngữ cảnh (ví dụ "thế còn trường hợp kia thì sao?"), khâu truy xuất có thể không đủ thông tin để tìm đúng điều khoản, dù mô hình ngôn ngữ vẫn nhận được lịch sử.
3. **Không lưu trữ hội thoại.** Kiểm tra mã nguồn xác nhận hệ thống **không ghi nhật ký hội thoại, không có cơ sở dữ liệu người dùng**. Lịch sử chỉ tồn tại trong phiên làm việc của trình duyệt.

### 9.2. Các cơ chế bảo đảm độ tin cậy đang hiện diện

| Cơ chế | Mức độ triển khai | Đánh giá |
|---|---|---|
| Neo tri thức (knowledge grounding) | **Đầy đủ** — mọi câu trả lời đều dựa trên 5 đoạn được cấp | Cơ chế chính chống bịa đặt |
| Trích dẫn nguồn | **Đầy đủ** — hiển thị điều khoản và tên tài liệu | Cho phép người dùng tự kiểm chứng |
| Ràng buộc bằng lời nhắc | **Đầy đủ** — cấm bịa, yêu cầu thừa nhận khi thiếu thông tin | Phụ thuộc mức tuân thủ của mô hình |
| Xếp hạng lại | **Đầy đủ** — nâng chất lượng đoạn đưa vào ngữ cảnh | Giảm sai sót do truy xuất nhầm |
| Nhiệt độ sinh thấp (0,1) | **Đầy đủ** | Tăng tính ổn định, giảm sáng tạo tùy tiện |
| Khuyến cáo trên giao diện | **Đầy đủ** — nêu rõ thông tin mang tính tham khảo | Cảnh báo người dùng |
| Ngưỡng chặn theo điểm liên quan | **Khai báo nhưng không hoạt động** | Xem Mục 7.2 |
| Hậu kiểm câu trả lời tự động | **Không có** | — |
| Cơ chế dự phòng khi truy xuất thất bại | **Không có tầng mã riêng** | Chỉ dựa vào lời nhắc |

### 9.3. Đánh giá thực trạng kiểm soát ảo giác

Cần phát biểu khách quan: hệ thống **giảm đáng kể** nguy cơ bịa đặt nhờ kiến trúc RAG và cơ chế trích dẫn, nhưng **không loại trừ hoàn toàn**. Cụ thể, các rủi ro còn tồn tại gồm:

- Khi cơ sở tri thức không chứa thông tin (ví dụ nhóm câu hỏi về chuẩn đầu ra ngoại ngữ do tệp `.doc` chưa được xử lý), hệ thống vẫn nhận được 5 đoạn ít liên quan nhất và có thể suy diễn từ đó.
- Với câu hỏi yêu cầu so sánh mốc số, mô hình 3 tỉ tham số có thể đưa ra kết luận đúng nhưng kèm lập luận không chính xác. Lời nhắc hệ thống đã bổ sung quy tắc riêng cho tình huống này, song đây là biện pháp giảm thiểu chứ không phải bảo đảm.
- Không có cơ chế nào đối chiếu tự động giữa câu trả lời sinh ra và nội dung đoạn trích.

Do đó, khuyến cáo hiển thị trên giao diện — đề nghị người dùng xác nhận lại với phòng đào tạo trong các trường hợp quan trọng — là **thành phần bắt buộc của thiết kế**, không phải yếu tố hình thức.

---

## CHƯƠNG 10. KỊCH BẢN DEMO VÀ KẾT QUẢ

### 10.1. Nguyên tắc xây dựng kịch bản

Các kịch bản dưới đây được thiết kế bám sát **tập tài liệu hiện có** (05 văn bản nêu tại Mục 2.2), nhằm bảo đảm hệ thống thực sự có cơ sở tri thức để trả lời. Mỗi kịch bản nhằm chứng minh một năng lực kỹ thuật cụ thể.

### 10.2. Bảng kịch bản demo đề xuất

| # | Kịch bản | Câu hỏi minh họa | Năng lực được chứng minh |
|---|---|---|---|
| 1 | Tra cứu điều khoản trực tiếp | "Sinh viên bị cảnh báo học tập trong những trường hợp nào?" | Truy xuất đúng điều khoản; trích dẫn nguồn chính xác |
| 2 | Tra cứu điều kiện tổng hợp | "Điều kiện để được công nhận tốt nghiệp là gì?" | Tổng hợp thông tin từ nhiều khoản trong một điều |
| 3 | Tra cứu quy định chuyên đề | "Quy định về đào tạo trực tuyến của trường như thế nào?" | Phân biệt đúng tài liệu nguồn giữa 5 văn bản |
| 4 | Tra cứu nghiệp vụ hỗ trợ | "Hệ thống LMS dùng để làm gì?" | Truy xuất từ tài liệu hướng dẫn, không nhầm sang quy chế |
| 5 | Hội thoại nhiều lượt | Lượt 1: "Thời gian đào tạo tối đa là bao lâu?" → Lượt 2: "Thế còn trường hợp học liên thông?" | Duy trì ngữ cảnh giữa các lượt |
| 6 | Tư vấn theo tình huống cá nhân | "Em bị điểm trung bình tích lũy thấp thì bị xử lý thế nào?" | So sánh mốc số; đưa bước hành động |
| 7 | **Câu hỏi ngoài phạm vi** | "Trường có ký túc xá cho sinh viên không?" | **Thừa nhận không có thông tin thay vì bịa** — kịch bản quan trọng nhất về độ tin cậy |
| 8 | So sánh có/không tinh chỉnh | Chạy `test_rag.py` và `test_rag.py --base` trên cùng bộ câu hỏi | Minh chứng đóng góp của khâu tinh chỉnh |

**Khuyến nghị trình diễn:** nên đưa kịch bản 7 vào phần demo trước hội đồng. Việc hệ thống **từ chối trả lời** một câu hỏi ngoài phạm vi là minh chứng thuyết phục hơn nhiều so với việc trả lời đúng một câu hỏi dễ, vì nó thể hiện cơ chế kiểm soát rủi ro của kiến trúc.

### 10.3. Trạng thái kiểm thử hiện tại

Cần trình bày trung thực về mức độ đã kiểm chứng:

**Đã thực hiện:**
- Kiểm thử định tính trong quá trình phát triển, xác nhận toàn bộ luồng đầu–cuối hoạt động: từ giao diện web → truy xuất → sinh câu trả lời → hiển thị kèm trích dẫn.
- Xác nhận cơ chế truy xuất hai tầng cải thiện thứ hạng tài liệu so với chỉ dùng truy hồi vector.
- Xác nhận cơ chế hội thoại nhiều lượt hoạt động sau khi khắc phục lỗi ép kiểu dữ liệu lịch sử.
- Công cụ kiểm thử theo lô (`test_rag.py`) đã được xây dựng, kèm bộ câu hỏi mẫu bảy câu phủ các nhóm: quy chế, khung chương trình, tư vấn tình huống và câu hỏi ngoài phạm vi.

**Chưa thực hiện [CXĐ]:**
- **Chưa có đánh giá định lượng chính thức**: hệ thống không có bộ dữ liệu kiểm thử chuẩn có đáp án đối chiếu, không có chỉ số đo độ chính xác truy xuất hay độ chính xác câu trả lời, không có biên bản kiểm thử.
- **Chưa đo được thời gian phản hồi và mức tiêu thụ bộ nhớ đồ họa trên cấu hình hiện tại.** Phép đo đã được chuẩn bị nhưng không thực hiện được tại thời điểm khảo sát do tài nguyên GPU đang được sử dụng bởi tiến trình huấn luyện và bởi tiến trình của người dùng khác trên cùng máy chủ.
- **Chưa có kiểm thử với người dùng thực** (sinh viên, cố vấn học tập).
- Các kết quả quan sát trong quá trình phát triển được ghi nhận trên **tập tài liệu phiên bản trước** (gồm các tệp PDF quét ảnh), không áp dụng cho cơ sở tri thức hiện tại gồm 05 văn bản Word.

**Khuyến nghị trước khi bảo vệ:** chạy `python src/Phase3-RAG/test_rag.py` với bộ câu hỏi theo Mục 10.2 sau khi tiến trình huấn luyện kết thúc, ghi lại toàn văn kết quả và thời gian phản hồi để bổ sung vào báo cáo dưới dạng số liệu đã kiểm chứng.

---

## CHƯƠNG 11. ĐÁNH GIÁ HỆ THỐNG

### 11.1. Số liệu hệ thống đã kiểm chứng

| Hạng mục | Giá trị | Nguồn kiểm chứng |
|---|---|---|
| Số văn bản trong kho tri thức | 05 (trên 06 tệp có mặt) | Đối chiếu `data/raw/` với `SUPPORTED_EXTS` |
| Số đoạn tri thức | 144 | Đếm bản ghi `chunks.jsonl` |
| Số vector trong cơ sở dữ liệu | 144 | Truy vấn ChromaDB |
| Đoạn có siêu dữ liệu điều khoản | 115/144 (79,9%) | Thống kê `chunks.jsonl` |
| Đoạn có siêu dữ liệu chương | 105/144 (72,9%) | Thống kê `chunks.jsonl` |
| Độ dài đoạn (số từ) | Nhỏ nhất 51 – Trung bình 316 – Lớn nhất 545 | Thống kê `chunks.jsonl` |
| Dung lượng cơ sở dữ liệu vector | 3,6 MB | Đo dung lượng thư mục |
| Số mẫu huấn luyện | 1.549 (từ 1.679 câu) | Đếm dòng `train.jsonl` |
| Dung lượng bộ điều hợp LoRA | ~57 MB | Đo dung lượng tệp |
| Số phiên bản mã nguồn được ghi nhận | 12 | Lịch sử `git log` |

Tỉ lệ 79,9% đoạn mang siêu dữ liệu điều khoản là chỉ số có ý nghĩa: nó cho biết phần lớn cơ sở tri thức đã được neo vào cấu trúc pháp lý, tức phần lớn câu trả lời có khả năng trích dẫn chính xác tới điều khoản. Phần còn lại (20,1%) thuộc các đoạn không theo cấu trúc Điều — chủ yếu là tài liệu hướng dẫn LMS.

### 11.2. Cấu hình phần cứng và môi trường triển khai

| Thành phần | Thông số |
|---|---|
| Bộ xử lý đồ họa | NVIDIA GeForce RTX 4080 SUPER, 16 GB bộ nhớ, phiên bản trình điều khiển 595.80 |
| Bộ xử lý trung tâm | Intel Core i7-14700KF, 28 luồng |
| Bộ nhớ hệ thống | 31 GB |
| Hệ điều hành | Linux, nhân 6.8.0-124 |
| Môi trường Python | Conda, Python 3.10.0 |
| Nền tảng tính toán | PyTorch 2.12.1, CUDA 13.0 |
| Phương thức triển khai | Tiến trình đơn, cổng 7860, phạm vi mạng nội bộ |

**Lưu ý về môi trường:** máy chủ hiện là **tài nguyên dùng chung**, tại thời điểm khảo sát ghi nhận tiến trình của người dùng khác đang chiếm dụng bộ nhớ đồ họa. Đây là yếu tố cần tính đến khi lập kế hoạch trình diễn, vì hệ thống cần khoảng bộ nhớ đồ họa liên tục cho ba mô hình chạy đồng thời.

### 11.3. Đánh giá mức độ hoàn thiện theo phân hệ

| Phân hệ | Mức độ hoàn thiện | Ghi chú |
|---|---|---|
| 1. Tiền xử lý dữ liệu | Cao | Hoạt động ổn định với `.docx`; nhánh xử lý ảnh quét chưa dùng đến ở cấu hình hiện tại; chưa hỗ trợ `.doc` |
| 2. Vector hóa và lưu trữ | Cao | Vận hành đúng, dữ liệu nhất quán |
| 3. Lõi RAG | Cao | Đầy đủ truy xuất hai tầng, sinh theo luồng, trích dẫn |
| 4. Tinh chỉnh mô hình | Trung bình | Quy trình hoàn chỉnh; bộ trọng số đang dùng chưa tương ứng bộ dữ liệu mới nhất; định dạng dữ liệu huấn luyện chưa phản ánh tình huống RAG |
| 5. Giao diện web | Trung bình – Khá | Đầy đủ chức năng hỏi–đáp; thiếu xác thực, nhật ký, quản trị |

---

## CHƯƠNG 12. ĐIỂM MẠNH VÀ ĐÓNG GÓP KỸ THUẬT

Mục này trình bày các điểm mạnh **có cơ sở trong mã nguồn**, tránh quy các năng lực thông thường của mô hình ngôn ngữ thành đóng góp riêng của đề tài.

### 12.1. Phân đoạn văn bản theo cấu trúc pháp lý

Đây là đóng góp kỹ thuật đặc thù nhất của hệ thống. Các giải pháp phổ thông thường cắt văn bản theo số lượng ký tự cố định, làm đứt gãy điều khoản và mất khả năng trích dẫn. Hệ thống này xây dựng cơ chế nhận diện mốc "Điều N" với hai tầng ràng buộc — điều kiện hình thái (dấu câu và chữ hoa theo sau) và điều kiện thứ tự (số hiệu tăng dần đơn điệu) — nhằm phân biệt **tiêu đề điều khoản thật** với **tham chiếu chéo** trong nội dung. Cơ chế này được thiết kế riêng cho đặc thù văn bản quy phạm tiếng Việt và là nền tảng cho toàn bộ khả năng trích dẫn của hệ thống.

### 12.2. Chuỗi truy xuất hai tầng

Việc bổ sung tầng xếp hạng lại bằng mô hình cross-encoder là quyết định kỹ thuật có căn cứ, xuất phát từ quan sát thực nghiệm trong quá trình phát triển: điểm tương đồng của truy hồi vector trên tập tài liệu hành chính tiếng Việt có xu hướng tập trung trong dải hẹp, làm giảm khả năng phân biệt tài liệu đúng với tài liệu chỉ có từ vựng tương tự. Kiến trúc 20 ứng viên → 5 kết quả là sự cân bằng giữa độ chính xác và chi phí tính toán.

### 12.3. Vận hành hoàn toàn cục bộ

Toàn bộ ba mô hình chạy trên hạ tầng của đơn vị. Điều này có hai ý nghĩa cụ thể: **văn bản nội bộ của Nhà trường không rời khỏi hệ thống**, và chi phí vận hành không phụ thuộc số lượng truy vấn. Với đặc thù dữ liệu là văn bản quản lý nội bộ, đây là yêu cầu có tính nguyên tắc chứ không đơn thuần là lựa chọn kỹ thuật.

### 12.4. Quy trình xử lý dữ liệu tự động và tái lập được

Toàn bộ chặng từ văn bản gốc đến cơ sở dữ liệu vector được tự động hóa qua hai lệnh. Việc lưu bản trung gian dạng Markdown cho phép cán bộ chuyên môn kiểm tra chất lượng trích xuất bằng mắt trước khi đưa vào chỉ mục — một điểm thiết kế phục vụ kiểm soát chất lượng dữ liệu. Cờ `--from-interim` cho phép thử nghiệm lại tham số phân đoạn mà không phải chạy lại khâu trích xuất tốn thời gian.

### 12.5. Cấu hình tập trung và khả năng thay thế thành phần

Việc tập trung tham số tại một tệp duy nhất cho phép thay đổi mô hình ngôn ngữ, mô hình nhúng, mô hình xếp hạng lại, số lượng đoạn truy xuất và tham số huấn luyện mà không sửa mã nghiệp vụ. Mã nguồn còn cung cấp tham số dòng lệnh cho phép so sánh trực tiếp mô hình gốc với mô hình đã tinh chỉnh — công cụ cần thiết để đánh giá khách quan đóng góp của khâu tinh chỉnh.

### 12.6. Bộ dữ liệu câu hỏi – đáp án chuyên ngành

Bộ 1.679 câu hỏi – đáp án do đội ngũ chuyên môn biên soạn, phân loại theo bốn nhóm nghiệp vụ, là tài sản dữ liệu có giá trị độc lập với phần mềm. Bộ dữ liệu này có thể tái sử dụng cho việc huấn luyện các mô hình khác, xây dựng bộ đánh giá chuẩn, hoặc làm cơ sở tri thức bổ sung.

---

## CHƯƠNG 13. KHẢ NĂNG TRIỂN KHAI THỰC TẾ

### 13.1. Mức độ sẵn sàng hiện tại

Hệ thống ở trạng thái **sẵn sàng cho trình diễn và thử nghiệm nội bộ quy mô nhỏ**. Cơ sở đánh giá: toàn bộ luồng chức năng đã thông suốt; giao diện web vận hành được; quy trình cập nhật tri thức đã tự động hóa; hạ tầng phần cứng hiện có đáp ứng được yêu cầu.

Hệ thống **chưa sẵn sàng** cho triển khai diện rộng, do các thiếu hụt về vận hành nêu tại Mục 13.2 và 14.

### 13.2. Các điều kiện cần bổ sung để triển khai

| Hạng mục | Trạng thái hiện tại | Yêu cầu bổ sung |
|---|---|---|
| Khả năng phục vụ đồng thời | Xử lý tuần tự, một yêu cầu tại một thời điểm | Cần đánh giá tải thực tế; cân nhắc hàng đợi hoặc bộ suy luận tối ưu |
| Tự khởi động lại khi sự cố | Không có | Cần cấu hình dịch vụ hệ thống hoặc trình quản lý tiến trình |
| Nhật ký vận hành | Không có | Cần ghi nhật ký truy vấn phục vụ phân tích và cải tiến |
| Bảo mật truy cập | Không có xác thực | Cần bổ sung nếu mở rộng ngoài mạng nội bộ |
| Giám sát tài nguyên | Không có | Cần theo dõi bộ nhớ đồ họa, đặc biệt trên máy chủ dùng chung |
| Sao lưu cơ sở tri thức | Không có quy trình | Cần định kỳ sao lưu `data/` và bộ trọng số |

### 13.3. Khả năng tích hợp với hệ thống khác

Kiến trúc hiện tại tạo điều kiện cho ba hướng tích hợp, song **cả ba đều chưa được hiện thực hóa [ĐH]**:

- **Giao diện lập trình ứng dụng:** Gradio tự động phơi bày điểm cuối gọi hàm; đã xác nhận có thể gọi từ chương trình khách. Đây là cơ sở kỹ thuật để nhúng chatbot vào cổng thông tin sinh viên hoặc ứng dụng di động.
- **Mở rộng kho tri thức:** quy trình xử lý dữ liệu nhận nhiều định dạng, cho phép bổ sung khung chương trình đào tạo, đề án tuyển sinh, sổ tay sinh viên mà không thay đổi kiến trúc.
- **Thay thế mô hình:** thiết kế cấu hình tập trung cho phép nâng cấp lên mô hình ngôn ngữ lớn hơn khi có điều kiện phần cứng.

---

## CHƯƠNG 14. HẠN CHẾ VÀ ĐỊNH HƯỚNG PHÁT TRIỂN

### 14.1. Hạn chế về dữ liệu

**Hạn chế nghiêm trọng nhất hiện nay là quy mô cơ sở tri thức.** Với 144 đoạn từ 05 văn bản, phạm vi trả lời còn hẹp so với mục tiêu đề ra ban đầu (bao gồm cả chương trình đào tạo và tuyển sinh). Cụ thể:

- Tệp *"Quy định về chuẩn đầu ra ngoại ngữ và tin học"* định dạng `.doc` **không được xử lý** do không nằm trong danh sách định dạng hỗ trợ, và **quá trình bỏ qua này diễn ra âm thầm, không phát sinh cảnh báo**. Đây vừa là lỗ hổng tri thức vừa là khiếm khuyết thiết kế cần khắc phục.
- Kho tri thức hiện **không chứa khung chương trình đào tạo các ngành**, do đó các câu hỏi về số tín chỉ học phần, môn tiên quyết, lộ trình học cụ thể **không có cơ sở để trả lời**. Cần lưu ý điểm này khi lựa chọn câu hỏi trình diễn.
- Thư mục trung gian còn tồn đọng các tệp từ tập tài liệu phiên bản trước, không ảnh hưởng tới cơ sở tri thức hiện tại (do quy trình chạy từ dữ liệu gốc) nhưng gây nhầm lẫn khi rà soát và tiềm ẩn rủi ro nếu chạy nhầm chế độ `--from-interim`.

*Định hướng:* bổ sung hỗ trợ định dạng `.doc`; thêm cảnh báo tường minh với tệp bị bỏ qua; bổ sung khung chương trình đào tạo; dọn thư mục trung gian.

### 14.2. Hạn chế về kiểm soát độ tin cậy

Như phân tích tại Mục 7.2 và 9.3: tham số ngưỡng liên quan được khai báo nhưng không hoạt động; hệ thống luôn đưa năm đoạn vào ngữ cảnh bất kể mức độ liên quan; việc từ chối câu hỏi ngoài phạm vi hoàn toàn dựa vào mức tuân thủ chỉ dẫn của mô hình; không có tầng hậu kiểm.

*Định hướng:* hiện thực hóa ngưỡng chặn dựa trên điểm của mô hình xếp hạng lại, trả về thông báo chuẩn khi không đoạn nào vượt ngưỡng; nghiên cứu bổ sung bước đối chiếu câu trả lời với đoạn trích.

### 14.3. Hạn chế về mô hình ngôn ngữ

Mô hình 3 tỉ tham số là lựa chọn phù hợp với ràng buộc phần cứng, nhưng có giới hạn năng lực suy luận, đặc biệt với các câu hỏi đòi hỏi so sánh ngưỡng số và suy luận nhiều bước. Quan sát trong quá trình phát triển ghi nhận hiện tượng mô hình đưa ra kết luận đúng nhưng kèm lập luận không chính xác.

*Định hướng:* khi có điều kiện phần cứng, đánh giá mô hình quy mô lớn hơn; hoặc bổ sung dữ liệu tinh chỉnh chuyên biệt cho nhóm câu hỏi so sánh ngưỡng.

### 14.4. Hạn chế về hiệu năng và khả năng mở rộng

Kiến trúc đơn tiến trình, xử lý tuần tự, một GPU. Chưa có số liệu đo về thời gian phản hồi và khả năng chịu tải. Máy chủ là tài nguyên dùng chung nên bộ nhớ đồ họa khả dụng không ổn định.

*Định hướng:* đo thời gian phản hồi và mức chiếm dụng bộ nhớ; đánh giá các bộ suy luận tối ưu nếu cần phục vụ nhiều người dùng đồng thời.

### 14.5. Hạn chế về bảo mật và vận hành

Không có xác thực người dùng, không giới hạn tần suất truy vấn, không ghi nhật ký, không tự khởi động lại. Hệ thống hiện chỉ an toàn trong phạm vi mạng nội bộ có kiểm soát.

*Định hướng:* bổ sung xác thực; ghi nhật ký truy vấn (có cân nhắc yếu tố bảo vệ dữ liệu cá nhân); cấu hình dịch vụ tự khởi động.

### 14.6. Hạn chế về khâu tinh chỉnh

Hai vấn đề đã xác định: (i) bộ trọng số đang được nạp không tương ứng với bộ dữ liệu huấn luyện mới nhất; (ii) định dạng dữ liệu huấn luyện không chứa khối tài liệu truy xuất, nên không dạy được mô hình kỹ năng trả lời dựa trên tài liệu được cấp.

*Định hướng:* hoàn tất huấn luyện lại trên bộ dữ liệu đầy đủ và xác nhận lại; nghiên cứu bổ sung dữ liệu huấn luyện có mô phỏng đúng định dạng RAG (câu hỏi kèm đoạn trích, đáp án có trích dẫn), nhằm dạy mô hình cả kỹ năng bám tài liệu chứ không chỉ văn phong.

### 14.7. Hạn chế về đánh giá

Chưa có bộ dữ liệu kiểm thử chuẩn, chưa có chỉ số định lượng, chưa kiểm thử với người dùng thực.

*Định hướng:* trích một phần bộ 1.679 câu hỏi làm tập kiểm thử độc lập (không dùng để huấn luyện); xây dựng chỉ số đánh giá cho hai khâu riêng biệt — độ chính xác truy xuất và độ chính xác câu trả lời; tổ chức thử nghiệm với nhóm sinh viên và cố vấn học tập.

---

## CHƯƠNG 15. THÔNG TIN CẦN BỔ SUNG

Các nội dung sau **không xác định được** từ mã nguồn, cấu hình và dữ liệu hiện có; đề nghị bổ sung trước khi hoàn thiện báo cáo chính thức:

1. **Số liệu hiệu năng:** thời gian phản hồi trung bình, thời gian khởi động hệ thống, mức chiếm dụng bộ nhớ đồ họa khi vận hành. *(Đo được bằng cách chạy hệ thống khi GPU rảnh.)*
2. **Kết quả huấn luyện của bộ trọng số cuối cùng:** tập dữ liệu tương ứng, số vòng lặp, giá trị hàm mất mát, thời gian huấn luyện.
3. **Kết quả kiểm thử trên cơ sở tri thức hiện tại:** toàn văn câu trả lời cho bộ câu hỏi tại Mục 10.2, kèm đánh giá đúng/sai của cán bộ chuyên môn.
4. **Thông tin đề tài:** tên đầy đủ, mã số, đơn vị chủ trì, chủ nhiệm đề tài, thời gian thực hiện.
5. **Kế hoạch dữ liệu:** danh mục đầy đủ văn bản dự kiến đưa vào kho tri thức và lộ trình bổ sung.
6. **Phiên bản thư viện `img2table`** (không truy vấn được tại thời điểm khảo sát).
7. **Kế hoạch triển khai:** địa chỉ máy chủ dự kiến, phạm vi người dùng, thời điểm mở thử nghiệm.

---

## CHƯƠNG 16. ĐỀ XUẤT HÌNH VẼ VÀ BẢNG BIỂU

### 16.1. Danh mục hình đề xuất

**Hình 1 – Kiến trúc tổng thể hệ thống.**
Bố cục hai khối ngang. Khối trên "Giai đoạn ngoại tuyến": ba hộp nối tiếp *Văn bản gốc (.docx)* → *Phân hệ tiền xử lý* → *Phân hệ vector hóa*, mũi tên đi xuống hai trụ dữ liệu *chunks.jsonl* và *ChromaDB*. Khối dưới "Giai đoạn trực tuyến": *Người dùng/Trình duyệt* ⇄ *Giao diện Gradio* ⇄ *Lõi RAG*, từ Lõi RAG có hai mũi tên tới *ChromaDB + Reranker* và tới *Qwen2.5-3B + LoRA*. Đường nét đứt từ *Phân hệ tinh chỉnh* tới khối mô hình, chú thích "chạy ngoại tuyến". Dùng màu phân biệt hai khối.

**Hình 2 – Luồng xử lý một câu hỏi (sơ đồ tuần tự).**
Năm cột dọc: *Sinh viên*, *Giao diện (app.py)*, *Bộ truy xuất (retriever.py)*, *Cơ sở dữ liệu vector + Reranker*, *Mô hình ngôn ngữ*. Các mũi tên ngang đánh số 1–14 theo bảng Mục 6.1. Nên ghi rõ trên mũi tên: "20 ứng viên", "5 đoạn", "streaming".

**Hình 3 – Quy trình tiền xử lý dữ liệu.**
Chuỗi năm hộp: *Trích xuất* → *Làm sạch (NFC, bỏ đầu/chân trang)* → *Hiệu chỉnh lỗi tiếng Việt* → *Phân đoạn theo Chương/Điều/Khoản* → *chunks.jsonl*. Bên dưới hộp phân đoạn, vẽ hộp phụ minh họa siêu dữ liệu: `chunk_id`, `source`, `chuong`, `dieu`, `heading`, `word_count`. Nhánh phụ nét đứt cho OCR (ghi chú "áp dụng với tài liệu quét ảnh").

**Hình 4 – Cơ chế truy xuất hai tầng.**
Sơ đồ hình phễu: *Câu hỏi* → *Mã hóa BGE-M3* → *ChromaDB: 144 đoạn* → *20 ứng viên* → *BGE-reranker chấm điểm từng cặp* → *5 đoạn tốt nhất*. Ghi chú so sánh: tầng 1 mã hóa độc lập (nhanh, phân biệt kém) / tầng 2 mã hóa đồng thời (chậm, chính xác).

**Hình 5 – Cấu trúc lời nhắc gửi mô hình.**
Hộp chữ nhật chia ba tầng chồng nhau: *Vai trò hệ thống + ràng buộc*, *Lịch sử hội thoại (tối đa 3 lượt)*, *Khối TÀI LIỆU [1]–[5] + CÂU HỎI*. Chú thích bên cạnh mỗi tầng nêu vai trò.

**Hình 6 – Sơ đồ triển khai.**
Một hộp lớn "Máy chủ GPU (RTX 4080 SUPER 16GB)" chứa các hộp con: *Tiến trình Python* (bên trong: Gradio cổng 7860, Lõi RAG, ba mô hình), *ChromaDB (tệp cục bộ)*, *Thư mục dữ liệu*. Bên ngoài: các máy trạm trong mạng nội bộ nối tới cổng 7860.

**Hình 7 – Ảnh chụp giao diện.** Ba ảnh: (a) màn hình chính với câu hỏi gợi ý; (b) câu trả lời kèm khối "Nguồn tham khảo"; (c) hội thoại nhiều lượt thể hiện câu hỏi nối tiếp.

**Hình 8 – Sơ đồ mô-đun mã nguồn.** Sơ đồ khối theo cấu trúc thư mục tại Mục 4.1, với mũi tên phụ thuộc: mọi phân hệ → `common/config.py`; `Phase5` → `Phase3` → `common/retriever.py`.

### 16.2. Danh mục bảng đề xuất

| Bảng | Nội dung | Nguồn trong báo cáo |
|---|---|---|
| Bảng 1 | Danh mục tài liệu trong cơ sở tri thức | Mục 2.2 |
| Bảng 2 | Công nghệ, thư viện và vai trò | Mục 5.1 |
| Bảng 3 | Các mô hình AI và vai trò | Mục 5.2 |
| Bảng 4 | Các bước xử lý câu hỏi và thành phần thực hiện | Mục 6.1 |
| Bảng 5 | Chức năng hệ thống và giá trị sử dụng | Mục 7.1 |
| Bảng 6 | Kỹ thuật AI: có / không áp dụng | Mục 8.1 |
| Bảng 7 | Phân bố bộ dữ liệu câu hỏi theo chủ đề | Mục 8.4 |
| Bảng 8 | Cơ chế bảo đảm độ tin cậy | Mục 9.2 |
| Bảng 9 | Kịch bản demo và năng lực chứng minh | Mục 10.2 |
| Bảng 10 | Số liệu hệ thống đã kiểm chứng | Mục 11.1 |
| Bảng 11 | Cấu hình phần cứng và môi trường | Mục 11.2 |
| Bảng 12 | Hạn chế và định hướng khắc phục | Chương 14 |

---

## CHƯƠNG 17. KẾT LUẬN

Hệ thống chatbot hỗ trợ cố vấn học tập đã được xây dựng hoàn chỉnh theo kiến trúc năm phân hệ, vận hành thông suốt từ khâu xử lý văn bản quy phạm của Nhà trường đến khâu trả lời câu hỏi của sinh viên qua giao diện web. Hệ thống áp dụng kiến trúc Sinh có tăng cường truy xuất với cơ chế truy xuất hai tầng, toàn bộ mô hình trí tuệ nhân tạo vận hành trên hạ tầng cục bộ của đơn vị.

**Về mặt kỹ thuật**, đóng góp nổi bật của hệ thống nằm ở cơ chế phân đoạn văn bản theo cấu trúc pháp lý Chương – Điều – Khoản với hai tầng ràng buộc nhận diện, tạo nền tảng cho khả năng trích dẫn nguồn ở mức điều khoản — yếu tố quyết định tính kiểm chứng được của câu trả lời trong lĩnh vực tư vấn quy chế. Cùng với đó là chuỗi truy xuất hai tầng, quy trình xử lý dữ liệu tự động và tái lập được, và thiết kế cấu hình tập trung cho phép thay thế linh hoạt các thành phần mô hình.

**Về mặt dữ liệu**, đề tài đã xây dựng được bộ 1.679 câu hỏi – đáp án chuyên ngành phân loại theo bốn nhóm nghiệp vụ, là tài sản có giá trị sử dụng lâu dài, độc lập với phiên bản phần mềm.

**Về mức độ hoàn thiện**, hệ thống đạt trạng thái sẵn sàng cho trình diễn và thử nghiệm nội bộ quy mô nhỏ. Báo cáo đã trình bày trung thực các hạn chế còn tồn tại, trong đó đáng lưu ý nhất là: quy mô cơ sở tri thức còn hẹp (144 đoạn từ 05 văn bản, chưa bao gồm khung chương trình đào tạo và một tệp bị bỏ qua do định dạng); cơ chế kiểm soát câu hỏi ngoài phạm vi hiện chỉ dựa vào ràng buộc lời nhắc mà chưa có tầng kiểm tra bằng mã; và hệ thống chưa có bộ đánh giá định lượng chính thức cũng như số liệu hiệu năng đã đo.

Các hạn chế nêu trên đều đã được xác định nguyên nhân cụ thể trong mã nguồn và có hướng khắc phục rõ ràng, không phải là khiếm khuyết mang tính kiến trúc. Điều này cho thấy hệ thống có nền tảng kỹ thuật phù hợp để tiếp tục hoàn thiện thành sản phẩm triển khai thực tế, với các bước ưu tiên là: mở rộng cơ sở tri thức, hiện thực hóa cơ chế ngưỡng chặn, hoàn tất và xác nhận khâu tinh chỉnh, và xây dựng bộ đánh giá định lượng phục vụ đo lường khách quan chất lượng hệ thống.

---

*Báo cáo được lập trên cơ sở phân tích trực tiếp mã nguồn và dữ liệu hệ thống. Các số liệu định lượng đều trích xuất từ hệ thống tại thời điểm khảo sát và có thể kiểm chứng lại bằng các lệnh tương ứng. Những nội dung chưa xác định được đã liệt kê tại Chương 15.*
