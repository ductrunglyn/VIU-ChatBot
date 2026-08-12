# Chatbot Cố vấn học tập — ĐHCN Việt - Hung (VIU)

Trợ lý RAG trả lời câu hỏi học vụ cho sinh viên, dựa **hoàn toàn** trên văn bản
chính thức của trường. Chủ dự án: thầy Hoàng Đức Trung. **Trao đổi bằng tiếng Việt.**

## Chạy dự án

```bash
conda activate test            # môi trường bắt buộc
screen -S ChatBot              # chạy nền để không đứt khi đóng terminal
python src/Phase5-UI/app.py    # web ở cổng 7860
```

Hoặc gọn hơn: `bash scripts/chay-web.sh`

Kiểm GPU bằng `nvidia-smi`. **Người dùng không có quyền sudo.**

## Kiến trúc

Câu hỏi → BGE-M3 (dense) + BM25 → gộp → BGE-reranker-v2-m3 xếp hạng lại → lọc
ngữ cảnh → Qwen2.5-3B-Instruct đã fine-tune QLoRA soạn câu trả lời kèm nguồn.

Song song có **tầng tra cứu có cấu trúc** (`src/common/curriculum_index.py`):
số tín chỉ và danh sách học phần được **code tra thẳng** từ dữ liệu đã bóc rồi
chèn vào ngữ cảnh dưới nhãn `DỮ KIỆN TRA CỨU TỪ KẾ HOẠCH ĐÀO TẠO`. Mô hình 3B
không cộng số đáng tin — đã đo nó bịa "150 tín chỉ".

| Giai đoạn | Thư mục |
|---|---|
| 1. Bóc & chia đoạn | `src/Phase1-DataPreprocessing/` |
| 2. Nhúng vector | `src/Phase2-Embedding/` |
| 3. RAG | `src/Phase3-RAG/` |
| 4. Fine-tune | `src/Phase4-Finetuning/` |
| 5. Giao diện web | `src/Phase5-UI/` |

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

Card **dùng chung với người khác** — thường bị chiếm ~4 GB ngoài tầm kiểm soát.
Đo được: tổng 15,57 GB, còn ~11,5 GB.

- Chạy web: Qwen2.5-3B + BGE-M3 + reranker ≈ 7,5 GB ✅
- Fine-tune 3B: ≈ 5,3 GB ✅
- Fine-tune Qwen3-14B: trọng số đã 9,39 GB, đỉnh cần thêm 2,90 GB → **tràn**.
  Chỉ chạy được khi card trống hẳn.

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
