# Hướng dẫn sử dụng web Cố vấn học tập AI — ĐHCN Việt - Hung

Tài liệu này mô tả giao diện web của chatbot cố vấn học tập: cách khởi động, các
thành phần trên màn hình, cách dùng, và những giới hạn cần biết trước khi đưa cho
sinh viên.

Mọi mô tả dưới đây bám đúng mã nguồn hiện tại
([app.py](../src/Phase5-UI/app.py), [theme.py](../src/Phase5-UI/theme.py)) và
cấu hình trong [config.py](../src/common/config.py).

---

## 1. Web này là gì

Một trang chat cho sinh viên hỏi về học vụ. Điểm khác với chatbot thông thường:
mô hình **không trả lời bằng trí nhớ**. Mỗi câu hỏi đều đi qua ba bước:

1. **Truy xuất** — tìm trong kho văn bản của trường những đoạn liên quan nhất
2. **Xếp hạng lại** — chấm điểm từng đoạn theo mức liên quan với chính câu hỏi đó
3. **Trả lời** — mô hình đọc các đoạn được chọn rồi soạn câu trả lời, kèm nguồn

Vì vậy dưới mỗi câu trả lời luôn có mục **📚 Nguồn tham khảo** ghi rõ tên văn bản
và số Điều. Sinh viên đối chiếu được ngay.

Kho tri thức hiện gồm 6 văn bản quy phạm và 6 bản kế hoạch đào tạo K50:

| Nhóm | Nội dung |
|---|---|
| Quy chế | Quy chế đào tạo trình độ đại học |
| | Quy định về đào tạo trực tuyến |
| | Quy định về chuẩn đầu ra ngoại ngữ và tin học |
| | Quy định về học phí và các khoản thu khác |
| | Tài liệu hướng dẫn sử dụng hệ thống LMS |
| | Luật Giáo dục đại học |
| Kế hoạch đào tạo K50 | Công nghệ kỹ thuật ô tô — chuyên ngành Công nghệ ô tô |
| | Công nghệ kỹ thuật ô tô — chuyên ngành Công nghệ ô tô điện |
| | Kỹ thuật ô tô — chuyên ngành Ô tô |
| | Kỹ thuật ô tô — chuyên ngành Xe chuyên dụng và máy công trình |
| | Kỹ thuật nhiệt |
| | Kỹ thuật môi trường |

Ngoài phạm vi này, hệ thống được huấn luyện để **nói thẳng là chưa có dữ liệu**
chứ không đoán bừa.

---

## 2. Khởi động

Chạy trong `screen` để web sống tiếp sau khi đóng terminal:

```bash
cd ~/hdtrungoi/ChatBot
bash scripts/chay-web.sh
```

Script tự kiểm tra rồi chạy web trong `screen`. Nó **tự dò môi trường conda** nào
có đủ `gradio` + `torch`, vì tên env khác nhau giữa các máy (`test` ở máy này,
`ChatBot` ở server 192.168.88.31). Muốn chỉ định thẳng:

```bash
ENV=ChatBot bash scripts/chay-web.sh
```

Dừng web: `bash scripts/chay-web.sh --dung` · Xem nhật ký: `--xem`

Làm tay cũng được:

```bash
screen -r ChatBot          # vào lại phiên đã có
conda activate ChatBot     # hoặc tên env của máy đó
cd ~/hdtrungoi/ChatBot
python src/Phase5-UI/app.py
```

Thoát khỏi screen mà vẫn để web chạy: nhấn `Ctrl+A` rồi `D`.

Khởi động mất khoảng **một phút** vì phải nạp ba mô hình (nhúng, xếp hạng lại,
mô hình ngôn ngữ) và chạy một câu làm nóng. Chờ tới khi thấy:

```
✅ Sẵn sàng. Khởi động giao diện web...
```

### Mở trang

| Vị trí | Địa chỉ |
|---|---|
| Ngay trên máy chủ | `http://localhost:7860` |
| Máy khác cùng mạng LAN | `http://<IP-máy-chủ>:7860` |

Xem IP máy chủ bằng `hostname -I`. Cổng đặt ở `UI_PORT` trong `config.py`.

> **Lưu ý về GPU:** web và việc huấn luyện **không chạy cùng lúc được** — cả hai
> đều cần bộ nhớ GPU. Muốn train thì tắt web trước.

---

## 3. Các phần trên màn hình

```
┌────────────────────┬──────────────────────────────────────────────┐
│  ĐHCN Việt - Hung  │   [logo + tên trường]                        │
│  Trợ lý học vụ     │   Cố vấn học tập AI                          │
│                    │   Quy chế · chuẩn đầu ra · học phí · lộ trình│
│  ＋ Đoạn chat mới  │                                              │
│                    │  ┌────────────────────────────────────────┐  │
│  Lịch sử trò chuyện│  │                                        │  │
│  ┌──────────────┐  │  │        khung hội thoại                 │  │
│  │ Cảnh báo học…│🗑│  │        (cao 62% màn hình, kéo được)    │  │
│  ├──────────────┤  │  │                                        │  │
│  │ Chuẩn đầu ra…│🗑│  └────────────────────────────────────────┘  │
│  ├──────────────┤  │                                              │
│  │ Đoạn chat mới│🗑│  [ Nhập câu hỏi của em…        ]  [ Gửi ]    │
│  └──────────────┘  │                                              │
│                    │  [gợi ý 1][gợi ý 2][gợi ý 3][gợi ý 4][gợi ý5]│
│                    │  Thông tin mang tính tham khảo…              │
└────────────────────┴──────────────────────────────────────────────┘
```

### 3.1 Thanh bên trái — lịch sử trò chuyện

- **Nhận diện trường** ở trên cùng: logo VIU, dòng "ĐHCN Việt - Hung / Trợ lý học vụ"
- **＋ Đoạn chat mới** — mở một đoạn trắng. Nếu đoạn hiện tại chưa hỏi gì thì nút
  này dùng lại đoạn đó, không tạo thêm đoạn rỗng
- **Danh sách đoạn chat** — mỗi dòng là một đoạn. Đoạn đang mở được tô nền xanh.
  Tên đoạn **tự đặt theo câu hỏi đầu tiên** (cắt còn 38 ký tự)
- **🗑** — xóa đoạn đó. Xóa hết thì hệ thống tự tạo lại một đoạn trắng

### 3.2 Đầu trang

Logo đầy đủ của trường kèm tiêu đề **"Cố vấn học tập AI"** và dòng mô tả phạm vi:
*Giải đáp quy chế đào tạo · chuẩn đầu ra · học phí · lộ trình học tập*.

Màu nhận diện lấy theo trường: xanh `#0082BC`, xanh đậm `#00629A`, cam `#EA902F`.
Giao diện tự đổi theo chế độ sáng/tối của trình duyệt.

### 3.3 Khung hội thoại

- Khi chưa hỏi gì, hiện lời chào giới thiệu phạm vi trả lời
- Ảnh đại diện của trợ lý là logo trường
- Câu trả lời **hiện dần từng đoạn** thay vì chờ xong mới hiện
- Kéo được mép dưới để đổi chiều cao khung

### 3.4 Ô nhập và nút gửi

- Gõ rồi nhấn **Enter** để gửi, hoặc bấm nút **Gửi**
- Ô nhập tự giãn tối đa 6 dòng cho câu hỏi dài
- Con trỏ tự đặt vào ô này khi mở trang

### 3.5 Câu hỏi gợi ý

Năm nút bấm là năm câu hỏi mẫu, bấm vào là điền sẵn vào ô nhập (chưa gửi ngay,
sinh viên sửa lại được):

1. Sinh viên bị cảnh báo học tập trong những trường hợp nào?
2. Điều kiện để được xét tốt nghiệp là gì?
3. Trường công nhận những chứng chỉ ngoại ngữ nào?
4. Em còn nợ 3 môn và CPA 1.9, nên làm gì để ra trường đúng hạn?
5. Nộp học phí muộn thì bị xử lý thế nào?

### 3.6 Chân trang

Dòng nhắc thường trực: *Thông tin mang tính tham khảo — trường hợp quan trọng em
hãy xác nhận lại với Phòng Quản lý đào tạo hoặc cố vấn học tập của lớp.*

---

## 4. Cách dùng

### Hỏi một câu

Gõ câu hỏi rồi Enter. Câu trả lời hiện dần, xong thì phần **📚 Nguồn tham khảo**
xuất hiện ở cuối.

### Hỏi nối tiếp

Hỏi tiếp mà không cần nhắc lại chủ đề:

> **Hỏi:** Chuẩn đầu ra ngoại ngữ yêu cầu trình độ nào?
> **Hỏi tiếp:** *Thế còn tin học thì sao?*

Hệ thống giữ **3 lượt hội thoại gần nhất** (`UI_HISTORY_TURNS`) làm ngữ cảnh, và
với câu hỏi ngắn hoặc có từ chỉ định ("đó", "này", "thế còn"…) nó tự ghép câu hỏi
trước vào để tìm đúng tài liệu.

### Quản lý nhiều đoạn chat

Mỗi chủ đề nên một đoạn riêng — hỏi học phí và hỏi khung chương trình mà chung
một đoạn thì ngữ cảnh dễ lẫn. Bấm **＋ Đoạn chat mới** khi đổi chủ đề.

### Hỏi thế nào cho đúng trọng tâm

| Nên | Không nên |
|---|---|
| Nêu rõ ngành và học kỳ: *"Học kỳ 6 ngành Kỹ thuật nhiệt học môn gì?"* | *"Kỳ này học gì?"* |
| Hỏi một việc mỗi câu | Gộp nhiều câu hỏi vào một lượt |
| Nêu tình huống cụ thể: *"Em nợ 3 môn, CPA 1.9…"* | Hỏi chung chung rồi mong đoán ý |

---

## 5. Lịch sử chat được lưu ở đâu

**Trong trình duyệt của chính sinh viên**, không phải trên máy chủ
(`gr.BrowserState`, khóa lưu `viu_chat_history_v1`).

Hệ quả cần biết:

- Máy chủ **không lưu** nội dung hỏi đáp của bất kỳ ai → không cần cơ sở dữ liệu,
  và người này không thể thấy đoạn chat của người kia
- Đổi trình duyệt hoặc đổi máy thì **không thấy lịch sử cũ**
- Xóa dữ liệu duyệt web / dùng chế độ ẩn danh sẽ **mất lịch sử**
- Máy dùng chung: sinh viên sau **thấy được** lịch sử của sinh viên trước nếu
  cùng trình duyệt và không xóa. Nên nhắc sinh viên tự xóa bằng nút 🗑

---

## 6. Giới hạn cần biết

**Trả lời tuần tự.** Chỉ một GPU nên mỗi lúc chỉ xử lý một câu
(`concurrency_limit=1`). Nhiều người hỏi cùng lúc thì phải xếp hàng — hiện chưa
có báo hiệu chờ trên giao diện.

**Chỉ biết những gì có trong 12 văn bản đã nạp.** Hỏi ngoài phạm vi (tuyển sinh,
ký túc xá, lịch thi cụ thể, học bổng…) sẽ nhận câu trả lời "chưa có trong tài
liệu" — đó là hành vi cố ý, không phải lỗi.

**Kế hoạch đào tạo mới có 6 ngành khoá K50.** Ngành khác hoặc khoá khác thì hệ
thống nói rõ là chưa có dữ liệu.

**Không phải văn bản pháp lý.** Câu trả lời dẫn đúng nguồn nhưng vẫn do mô hình
soạn. Việc quan trọng phải đối chiếu văn bản gốc và hỏi Phòng Quản lý đào tạo.

**Độ dài câu trả lời tối đa** khoảng 900 token (`LLM_MAX_NEW_TOKENS`). Câu hỏi
đòi liệt kê rất dài có thể bị dừng giữa chừng — khi đó hỏi tách nhỏ ra.

---

## 7. Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Mở trang không lên | Web chưa chạy | `screen -r ChatBot` xem tiến trình còn sống không |
| Máy khác không vào được | Tường lửa chặn cổng 7860, hoặc khác mạng | Kiểm tra bằng `curl http://localhost:7860` ngay trên máy chủ trước |
| Khởi động báo hết bộ nhớ GPU | Đang có tiến trình khác chiếm GPU | `nvidia-smi` xem ai giữ; tắt bớt rồi chạy lại |
| Trả lời rất chậm | Nhiều người hỏi cùng lúc, đang xếp hàng | Chờ; hoặc kiểm tra GPU có bị tiến trình khác chiếm không |
| Mất hết lịch sử chat | Đã xóa dữ liệu duyệt web, hoặc đổi trình duyệt | Không khôi phục được — lịch sử chỉ nằm ở máy sinh viên |
| Không hiện logo | Thiếu tệp trong thư mục `assets/` | Kiểm tra có `viu_logo.png` và `viu_lockup.png` không |
| Trả lời cụt giữa câu | Chạm trần độ dài | Hỏi tách nhỏ, hoặc tăng `LLM_MAX_NEW_TOKENS` |

---

## 8. Các tham số chỉnh được

Trong [src/common/config.py](../src/common/config.py):

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `UI_PORT` | 7860 | Cổng web |
| `UI_HISTORY_TURNS` | 3 | Số lượt hội thoại trước đưa vào ngữ cảnh |
| `RAG_TOP_K` | 5 | Số đoạn tài liệu lấy ra sau khi xếp hạng lại |
| `RERANK_ENABLED` | True | Bật/tắt bước xếp hạng lại |
| `LLM_MAX_NEW_TOKENS` | 900 | Độ dài tối đa một câu trả lời |
| `LLM_TEMPERATURE` | 0 | 0 = luôn trả lời giống nhau cho cùng câu hỏi |

> `LLM_TEMPERATURE = 0` là chủ ý: tư vấn quy chế cần **nhất quán**. Cùng một câu
> hỏi phải cho cùng một câu trả lời, không được lúc thế này lúc thế khác.

Sau khi sửa `config.py` phải **khởi động lại web** thì thay đổi mới có hiệu lực.
