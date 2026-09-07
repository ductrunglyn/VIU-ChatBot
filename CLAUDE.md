# Chatbot Cố vấn học tập — ĐHCN Việt - Hung (VIU)

Trợ lý RAG trả lời câu hỏi học vụ cho sinh viên, dựa **hoàn toàn** trên văn bản
chính thức của trường. Chủ dự án: thầy Hoàng Đức Trung. **Trao đổi bằng tiếng Việt.**

## Chạy dự án

```bash
bash scripts/chay-web.sh       # tự dò env, tự kiểm tra, chạy trong screen
```

Tên môi trường conda **khác nhau giữa các máy** (máy của thầy Trung là `test`,
server 192.168.88.31 là `ChatBot`). Script tự dò env nào có đủ `gradio` + `torch`
nên không cần sửa gì. Muốn chỉ định thẳng: `ENV=ChatBot bash scripts/chay-web.sh`.

Làm tay thì: `conda activate <env> && python src/Phase5-UI/app.py`

Kiểm GPU bằng `nvidia-smi`. **Người dùng không có quyền sudo.**

## Kiến trúc

Câu hỏi → mở rộng truy vấn (khẩu ngữ → thuật ngữ pháp quy) → BGE-M3 (dense) +
BM25 → hợp nhất bằng RRF → BGE-reranker-v2-m3 xếp hạng lại → lọc ngữ cảnh →
**ghép trọn Điều** → Qwen3-14B (4-bit NF4) soạn câu trả lời kèm nguồn → **đối
chiếu trích dẫn bằng code**.

Bốn điểm của tầng truy xuất, tất cả đều để chữa một lỗi đã đo được:

- **Mở rộng truy vấn** (`retriever.expand_query`, bảng ở `config.QUERY_SYNONYMS`):
  sinh viên viết "đuổi học", văn bản viết "buộc thôi học" — không có từ nào chung
  cho BM25 bám vào. Chỉ THÊM từ, không thay thế.
- **RRF** thay cho phép hợp tập cũ: gộp theo THỨ HẠNG nên không phải chuẩn hóa
  cosine với điểm BM25 vốn khác đơn vị.
- **Ghép trọn Điều** (`retriever.full_dieu_text`): 18/104 Điều bị cắt nhiều phần
  (Điều 7 có 6 phần), đoạn trúng thường chỉ là một mẩu nên trả lời thiếu khoản.
  Khử câu trùng do chồng lấp (đo được 4-5 câu trùng liền đầu mỗi phần).
- **Rerank gần như cả kho**: kho chỉ 183 đoạn, cross-encoder chấm hết chỉ tốn
  ~0,2 giây, nên lấy dư ứng viên tới 80 + 40. Truy xuất xấp xỉ hết bỏ sót.

**Câu mở rộng CHỈ dùng cho BM25, KHÔNG dùng cho dense.** Đây là lỗi đã gây hậu quả
thật: nhồi từ khoá vào câu rồi đem đi encode thì kéo vector ra khỏi vùng ngữ nghĩa
của câu hỏi gốc. Câu "Em còn nợ 3 môn và GPA 1.9, nên làm gì để ra trường đúng
hạn?" tụt từ 0,559 xuống 0,538, rơi dưới ngưỡng và sinh viên nhận "chưa tìm thấy
quy định" — hỏng đúng mục đích của một hệ cố vấn.

### Chặn câu ngoài phạm vi: HAI TẦNG

Trước đây chặn bằng ngưỡng similarity. Nay **không còn dùng cách đó làm cổng chính**
vì đo được hai vùng điểm đã chồng lên nhau, không ngưỡng nào tách được:

| | câu hợp lệ thấp nhất | câu ngoài phạm vi cao nhất |
|---|---|---|
| dense | 0,496 | 0,493 |
| rerank | 0,0071 | 0,0129 |

- **Tầng 1** — ngưỡng chỉ còn là SÀN AN TOÀN (`DENSE_MIN_SCORE = 0.30`,
  `RERANK_MIN_SCORE = 0.001`), bắt trường hợp thảm hoạ. Câu ngoài phạm vi đi qua
  tầng này là ĐÚNG THIẾT KẾ. Yêu cầu duy nhất: không chặn nhầm câu hợp lệ nào.
- **Tầng 2** — chính Qwen3-14B đọc ngữ cảnh rồi tự từ chối. Đo thực tế **8/8 câu
  ngoài phạm vi bị từ chối đúng, không bịa câu nào**. Mô hình 14B phán đoán "ngữ
  cảnh này có trả lời được câu hỏi không" tốt hơn hẳn một con số cosine.
- `rag._la_tu_choi()` ẩn danh sách nguồn khi câu trả lời là từ chối thuần, để
  giao diện không trích "Điều 5 — Quy chế đào tạo" cho câu hỏi nấu phở. Chỉ ẩn khi
  vừa có cụm từ chối VỪA không dẫn tên văn bản nào — vì có câu vừa hữu ích vừa
  chứa "tài liệu không nêu rõ...".

Đo bằng `python src/Phase3-RAG/calib_retrieval.py` (tầng 1, nhanh) hoặc thêm
`--llm` (đo cả tầng 2). Kết quả hiện tại: **tầng 1 chặn nhầm 0/22, tầng 2 từ chối
đúng 8/8**, độ trễ truy xuất trung vị 328ms. Chạy lại MỖI KHI đổi cách truy xuất.

Bộ đo có nhóm riêng `TU_VAN` — câu sinh viên kể hoàn cảnh kèm con số cụ thể. Bộ đo
đầu tiên thiếu hẳn nhóm này nên đã bỏ lọt lỗi trên; đừng bỏ nhóm đó đi.

Song song có **tầng tra cứu có cấu trúc** (`src/common/curriculum_index.py`):
số tín chỉ và danh sách học phần được **code tra thẳng** từ dữ liệu đã bóc rồi
chèn vào ngữ cảnh dưới nhãn `DỮ KIỆN TRA CỨU TỪ KẾ HOẠCH ĐÀO TẠO`. Mô hình tự cộng
là bịa: 3B từng bịa "150 tín chỉ", 14B bịa "132 tín chỉ" cho ngành Kỹ thuật nhiệt
(thật là 150) khi khối dữ kiện tra sai.

| Giai đoạn | Thư mục |
|---|---|
| 1. Bóc & chia đoạn | `src/Phase1-DataPreprocessing/` |
| 2. Nhúng vector | `src/Phase2-Embedding/` |
| 3. RAG | `src/Phase3-RAG/` |
| 4. Fine-tune | `src/Phase4-Finetuning/` |
| 5. Giao diện web | `src/Phase5-UI/` |

## Kết quả fine-tune Qwen3-14B — ĐÃ TẮT

Đã train lại QLoRA trên đúng base Qwen3-14B: 3189 mẫu, 3 epoch, 1197 bước, 7h17m,
loss cuối 0,070, token accuracy 98,8%. **Loss đẹp nhưng mô hình KÉM HƠN bản gốc**,
nên `USE_FINETUNED = False`. Adapter vẫn giữ ở `models/qlora-viu`.

Đo bằng `python src/Phase4-Finetuning/so_sanh_adapter.py` (nạp một lần rồi bật/tắt
adapter để so trên cùng ngữ cảnh), 7 câu:

- **Chép nguyên văn tài liệu.** Bản fine-tune trả lời theo đúng khuôn "Theo <văn
  bản> (Điều N), quy định như sau: <đọc lại nguyên đoạn>", dài gấp 2-3 lần bản gốc
  (470 vs 136 từ; 451 vs 180 từ) và **bị cắt cụt giữa câu** vì chạm
  `LLM_MAX_NEW_TOKENS`. Hỏi "thời gian đào tạo tối đa" thì nó đọc cả Điều 2 về cấu
  trúc chương trình mà không hề trả lời câu hỏi.
- **Có ca trả lời lạc hẳn đề.** "Em bị CPA 1.5 ở năm hai thì có bị buộc thôi học
  không?" -> bản fine-tune đáp về **học phí** và khuyên liên hệ Phòng Tài chính -
  Kế toán. Bản gốc so đúng mốc 1,4 và trả lời chính xác.
- Chỉ 1/7 câu bản fine-tune nhỉnh hơn (diễn đạt số tín chỉ mượt hơn), 2/7 hoà
  (câu từ chối), 4/7 kém hơn rõ.

**Nguyên nhân:** đáp án trong `data/qa/*.csv` phần lớn là trích nguyên văn văn bản,
nên 3 epoch với loss 0,07 dạy mô hình học thuộc đúng lối chép đó. Muốn fine-tune có
ích thì phải sửa DỮ LIỆU trước (viết lại đáp án theo lối tư vấn, ngắn gọn, có kết
luận ở câu đầu) chứ không phải chỉnh siêu tham số. Checkpoint từng epoch còn ở
`models/qlora-viu-runs/` nếu muốn thử epoch 1 (ít học thuộc hơn).

**Bài học ghi lại:** loss giảm KHÔNG đủ để kết luận fine-tune tốt. Luôn chạy
`so_sanh_adapter.py` đối chiếu với model gốc trước khi bật `USE_FINETUNED`.


## Nguyên tắc bắt buộc

**Không bao giờ để mô hình tự sinh dữ kiện.** Mọi con số, mã học phần, tên môn
phải do code tra từ dữ liệu đã bóc. Khi dùng LLM viết lại câu chữ
(`refine_qa_llm.py`), bản viết lại phải qua **cổng kiểm chứng 5 tầng** trong
cùng tệp đó — sai một chữ số là loại, giữ nguyên bản gốc.

**Không cắt bớt thông tin trong đáp án.** Đã có bài học: `restyle_qa.py` từng
cắt đuôi 782 đáp án và mất 69.513 từ; một câu về Điều 11 Luật GDĐH bị cắt từ
479 xuống 72 từ. Đã khôi phục. Dải độ dài nay đặt sàn ở nguyên độ dài gốc.

**Mẫu huấn luyện phải khớp lúc chạy thật.** `build_dataset.py` dựng mẫu đúng
định dạng `rag.py` dùng, kể cả khối `TÀI LIỆU:` và khối dữ kiện tra cứu. Huấn
luyện thiếu khối này thì mô hình học trả lời bằng trí nhớ, đọc lướt tài liệu.

**Đẩy GitHub sau mỗi thay đổi code.** Repo `ductrunglyn/VIU-ChatBot` là **công
khai** — chỉ đẩy mã và tài liệu. Tuyệt đối không đẩy: `data/`, PDF, văn bản
OCR, vectordb, bộ Q/A thật, trọng số mô hình.

**Báo cáo phải trung thực.** Không tự tạo số liệu hay thông số chưa kiểm chứng.
Chỗ nào chưa xác định được thì nói thẳng là chưa xác định được.

## Ràng buộc phần cứng

Server 192.168.88.31: **RTX 5090, 32,6 GB VRAM** (đo 08/2026, lúc đo chỉ có tiến
trình của dự án này chiếm card).

- Chạy web: Qwen3-14B 4-bit + BGE-M3 + reranker ≈ **13,9 GB đỉnh** ✅
- Trọng số 14B: 9,97 GB ở NF4. Bản bf16 cần ~29 GB → không dùng chung với
  embedder + reranker được, phải để `LLM_LOAD_4BIT = True`.
- Tốc độ đo được: 46 token/giây, thời gian trả lời trung vị **3,0 giây**.

**Đĩa ĐÃ ĐẦY: còn 7,2 GB/1,9 TB (100%)** (đo 18/08/2026). Cache HuggingFace chiếm
57 GB (riêng Qwen3-14B 28 GB); cả dự án ChatBot chỉ 1,5 GB. Phần lớn dung lượng
là của NGƯỜI DÙNG KHÁC — ổ `/` dùng chung cả máy. KHÔNG tải thêm model cho tới khi
dọn được chỗ; hiện chỉ đủ chạy vì mọi model cần thiết đã nằm sẵn trong cache.

Driver NVIDIA 570.133.07 chỉ hỗ trợ tới CUDA 12.8 → phải dùng **torch cu128**
(`torch==2.11.0+cu128`). Bản cu130 nạp lên là lỗi "NVIDIA driver is too old".

**Web và training không chạy cùng lúc được.** Muốn train thì tắt web trước.

## Chỗ dễ sai đã gặp

- **Kế hoạch đào tạo có nhánh loại trừ nhau**: hai định hướng chuyên ngành chỉ
  chọn MỘT, nhóm tự chọn lấy 6 trong 9, khối "dành cho hệ kỹ sư" riêng. Cộng
  phẳng ra 35 tín chỉ trong khi thật là 20. Xem `curriculum.py`.
- **10/48 học kỳ có số liệu tự vênh trong tài liệu gốc của trường** — nhãn "Bắt
  buộc" lúc gộp khối kỹ sư, lúc gộp định hướng, một chỗ cộng lệch 1. Ghi cả hai
  con số, không chọn bừa.
- **python-docx trả đoạn văn và bảng ở hai danh sách riêng** — phải duyệt
  `doc.element.body` mới giữ đúng thứ tự. Xem `_iter_docx_blocks`.
- **Ô bảng bị merge**: python-docx lặp lại nội dung ra từng cột, số cột lặp khác
  nhau giữa các bảng. Xem `_collapse`.
- **Regex tiếng Việt phải khử dấu trước rồi mới khớp** — lớp `[ií]` không chứa
  "ỉ" nên "tín chỉ" từng không khớp bao giờ.
- **Tách từ (pyvi/underthesea) KHÔNG giảm token cho LLM** — đo được tăng 35%, vì
  dấu gạch dưới là chuỗi lạ với bộ tách BPE của Qwen. Nhưng nó rất hữu ích để
  **đối chiếu nội dung** hai bản văn (xem `_missing_content`).

## Tài liệu

- [README.md](README.md) — tổng quan, quy trình 5 giai đoạn
- [docs/HUONG-DAN-SU-DUNG-WEB.md](docs/HUONG-DAN-SU-DUNG-WEB.md) — giao diện, cách dùng, xử lý sự cố
- `git log` — mỗi commit ghi rõ số đo và lý do quyết định
