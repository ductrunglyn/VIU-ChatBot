# Bộ dữ liệu Q/A cho fine-tuning (Giai đoạn 4)

Thư mục này chứa các cặp **Câu hỏi – Câu trả lời** do thầy cô/cố vấn soạn để
dạy chatbot "văn phong tư vấn" và tư duy logic (khác với RAG chỉ cung cấp kiến thức).

## Bạn cần chuẩn bị gì?

Soạn Q/A trong file bảng cho **dễ** (Excel hoặc CSV), theo đúng các cột sau:

| Cột | Bắt buộc | Ý nghĩa |
|-----|:---:|---------|
| `id` | ✔ | Số thứ tự (duy nhất) |
| `category` | ✔ | Nhóm chủ đề, vd: `canh_bao_hoc_vu`, `tot_nghiep`, `tuyen_sinh`, `lo_trinh_go_diem`, `chon_chuyen_nganh` |
| `question` | ✔ | Câu hỏi của sinh viên (viết tự nhiên như thật) |
| `answer` | ✔ | Câu trả lời mẫu, đúng quy chế, giọng tư vấn thân thiện |
| `source_refs` | | Trích dẫn nguồn (tên tài liệu + Điều), giúp kiểm tra tính đúng |
| `notes` | | Ghi chú nội bộ (không đưa vào huấn luyện) |

- Xem `qa_pairs_template.csv` làm mẫu (đã có 3 ví dụ).
- **Cách làm khuyến nghị**: mở template bằng Excel → điền thêm dòng → lưu lại
  dưới dạng `.csv` (UTF-8) hoặc `.xlsx`, đặt vào chính thư mục `data/qa/`.
- Mục tiêu: **500–1000 cặp**, tập trung nhiều vào các ca **tư vấn phức tạp**
  (lộ trình gỡ điểm, chọn môn song hành, định hướng chuyên ngành) chứ không chỉ
  câu hỏi tra cứu đơn giản.

## Nguyên tắc viết câu trả lời tốt
1. **Đúng quy chế** — đối chiếu tài liệu gốc, ghi `source_refs`.
2. **Có bước hành động cụ thể** — sinh viên đọc xong biết phải làm gì.
3. **Giọng cố vấn** — thân thiện, gọi "em", tránh máy móc.
4. **Không bịa số liệu** — nếu không chắc mốc điểm/điều khoản, để trống và hỏi lại thầy cô.

## Sau khi soạn xong
Chạy script để gộp tất cả file bảng trong thư mục này thành dataset huấn luyện chuẩn:
```bash
conda activate test
python src/build_dataset.py
```
Kết quả: `data/qa/train.jsonl` — định dạng **chat messages** (dùng được cho
LLaMA-Factory / Unsloth / axolotl khi QLoRA ở Giai đoạn 4). Mỗi dòng:
```json
{"messages": [
  {"role": "system", "content": "Bạn là trợ lý cố vấn học tập của Trường ĐHCN Việt - Hung..."},
  {"role": "user", "content": "<question>"},
  {"role": "assistant", "content": "<answer>"}
]}
```
