"""Kho cách diễn đạt cho bộ sinh Q/A: nhiều cách hỏi và nhiều cách mở câu trả lời.

Vì sao cần tệp này:

Bộ sinh Q/A dựng câu từ khuôn cố định nên 48 câu hỏi về học kỳ đều mở đầu y hệt
("Học kỳ 4 ngành X có mấy học phần bắt buộc?"), và 48 đáp án cũng mở đầu y hệt
("Học kỳ 4 (học kỳ 2 năm thứ 2) ngành X có ..."). Huấn luyện trên dữ liệu như vậy
dạy mô hình đúng MỘT cách nói, nên khi dùng thật, hai câu hỏi khác nhau về trọng
tâm vẫn cho ra câu trả lời na ná nhau — đúng lỗi người dùng phản ánh.

Vì sao KHÔNG để mô hình ngôn ngữ sinh luôn cả đáp án:

Đáp án ở đây chứa số liệu (tổng tín chỉ, danh sách học phần, mã học phần). Để mô
hình tự viết là mở đường cho nó bịa số — đúng lỗi đã phải sửa cả một vòng huấn
luyện. Nên phân vai rõ: phần DIỄN ĐẠT lấy từ kho câu chữ ở tệp này, phần DỮ KIỆN
luôn tính bằng code từ bản ghi đã bóc.

Cách chọn: theo băm nội dung (không phải ngẫu nhiên thuần), nên chạy lại nhiều lần
vẫn ra cùng kết quả — dữ liệu huấn luyện tái lập được.
"""
from __future__ import annotations
import hashlib

# ---------------------------------------------------------------- cách hỏi
# Mỗi khoá là một "ý định hỏi". Trường thay thế dùng {} theo tên.
QUESTION = {
    "tong_tin_chi": [
        "Ngành {lbl} tổng cộng bao nhiêu tín chỉ?",
        "Học ngành {lbl} phải tích lũy bao nhiêu tín chỉ mới ra trường?",
        "Cho em hỏi chương trình {lbl} có tất cả bao nhiêu tín chỉ ạ?",
        "Em định đăng ký ngành {lbl}, khối lượng học tập của ngành này là bao nhiêu?",
        "Toàn khoá ngành {lbl} nặng bao nhiêu tín chỉ vậy ạ?",
        "Số tín chỉ cần tích lũy của ngành {lbl} là bao nhiêu?",
        "Ngành {lbl} yêu cầu bao nhiêu tín chỉ để được xét tốt nghiệp?",
        "Em muốn biết khối lượng toàn khoá của chương trình {lbl}.",
    ],
    "so_ky": [
        "Ngành {lbl} học trong mấy học kỳ?",
        "Chương trình {lbl} kéo dài bao lâu ạ?",
        "Học ngành {lbl} mất mấy năm?",
        "Em hỏi thời lượng đào tạo của ngành {lbl} với ạ.",
        "Ngành {lbl} thiết kế bao nhiêu kỳ học?",
    ],
    "tin_chi_ky": [
        "Học kỳ {hk} ngành {lbl} có bao nhiêu tín chỉ?",
        "Kỳ {hk} của ngành {lbl} nặng bao nhiêu tín chỉ ạ?",
        "Cho em hỏi {nam_ky} ngành {lbl} phải học mấy tín chỉ?",
        "Em ngành {lbl}, kỳ {hk} tới đăng ký khoảng bao nhiêu tín chỉ là đủ?",
        "Khối lượng học kỳ {hk} của chương trình {lbl} là bao nhiêu?",
    ],
    "mon_ky": [
        "Học kỳ {hk} ngành {lbl} học những môn gì?",
        "Kỳ {hk} ngành {lbl} có các học phần nào ạ?",
        "Cho em xin danh sách môn học kỳ {hk} của ngành {lbl}.",
        "Em ngành {lbl}, {nam_ky} sẽ học những gì?",
        "Các môn của {nam_ky} ngành {lbl} là gì vậy ạ?",
        "Học phần nào nằm trong học kỳ {hk} của chương trình {lbl}?",
    ],
    "mon_bat_buoc_ky": [
        "Học kỳ {hk} ngành {lbl} có mấy học phần bắt buộc?",
        "Kỳ {hk} ngành {lbl} bắt buộc phải học những môn nào?",
        "Em ngành {lbl}, kỳ {hk} có môn nào không được bỏ ạ?",
        "Số học phần bắt buộc của học kỳ {hk} ngành {lbl} là bao nhiêu?",
        "Cho em hỏi những môn bắt buộc {nam_ky} ngành {lbl}.",
    ],
    "mon_tu_chon_ky": [
        "Học kỳ {hk} ngành {lbl} có môn tự chọn nào?",
        "Kỳ {hk} ngành {lbl} em được chọn những môn gì?",
        "Phần tự chọn của học kỳ {hk} ngành {lbl} gồm những học phần nào ạ?",
        "Em ngành {lbl} muốn biết kỳ {hk} phải chọn bao nhiêu tín chỉ tự chọn.",
    ],
    "ktdg_ky": [
        "Học kỳ {hk} ngành {lbl} có môn nào đánh giá bằng {form}?",
        "Kỳ {hk} ngành {lbl} môn nào thi {form} ạ?",
        "Em ngành {lbl}, kỳ {hk} những môn nào hình thức {form}?",
        "Cho em hỏi học phần thi {form} ở học kỳ {hk} ngành {lbl}.",
    ],
    "tin_chi_nam": [
        "Năm thứ {nam} ngành {lbl} học bao nhiêu tín chỉ?",
        "Cả năm {nam} ngành {lbl} nặng bao nhiêu tín chỉ ạ?",
        "Em ngành {lbl}, năm {nam} phải tích lũy bao nhiêu tín chỉ?",
        "Khối lượng năm thứ {nam} của chương trình {lbl} là bao nhiêu?",
    ],
    "luy_ke_nam": [
        "Học hết năm thứ {nam} ngành {lbl} thì tích lũy được bao nhiêu tín chỉ?",
        "Đến cuối năm {nam}, sinh viên ngành {lbl} đã có bao nhiêu tín chỉ?",
        "Em ngành {lbl} học xong năm {nam} rồi, còn thiếu bao nhiêu tín chỉ nữa?",
        "Sau {nam} năm học ngành {lbl} thì đã đi được bao nhiêu phần chương trình?",
    ],
    "hoc_phan_info": [
        "Học phần {ten} có mấy tín chỉ và học ở kỳ nào?",
        "Môn {ten} nặng mấy tín chỉ vậy ạ?",
        "Cho em hỏi môn {ten} học kỳ mấy và thi hình thức gì?",
        "Em muốn biết thông tin học phần {ten}.",
        "Môn {ten} thuộc nhóm bắt buộc hay tự chọn ạ?",
    ],
    "so_sanh_nganh": [
        "Ngành {la} và ngành {lb} khác nhau như thế nào về chương trình học?",
        "Em đang phân vân giữa {la} và {lb}, hai ngành học khác gì nhau ạ?",
        "So sánh giúp em chương trình đào tạo của {la} với {lb}.",
        "Chọn {la} hay {lb} thì học khác nhau ra sao?",
    ],
    "nang_hon": [
        "Học ngành {la} hay {lb} thì nặng hơn?",
        "Giữa {la} và {lb}, ngành nào nhiều tín chỉ hơn ạ?",
        "Em sợ học nặng, {la} với {lb} ngành nào nhẹ hơn?",
    ],
    "khac_ky": [
        "Học kỳ {hk} ngành {la} và ngành {lb} khác nhau môn gì?",
        "Kỳ {hk} của {la} so với {lb} thì học khác nhau thế nào ạ?",
        "Em muốn so sánh môn học kỳ {hk} giữa {la} và {lb}.",
    ],
    "ky_nang_nhe": [
        "Học kỳ {hk} ngành {lbl} nặng hay nhẹ so với các kỳ khác?",
        "Kỳ {hk} ngành {lbl} có phải kỳ nặng không ạ?",
        "Em ngành {lbl} lo kỳ {hk} quá tải, kỳ này so với mặt bằng thế nào?",
    ],
}

# ------------------------------------------------------- cách mở câu trả lời
# Dùng để phần đầu đáp án không lặp một khuôn duy nhất.
ANSWER_OPEN = {
    "tong_tin_chi": [
        "Chương trình {lbl} khoá {kh} có tổng khối lượng {tong}",
        "Ngành {lbl} yêu cầu tích lũy {tong}",
        "Theo kế hoạch đào tạo khoá {kh}, ngành {lbl} gồm {tong}",
        "Để tốt nghiệp ngành {lbl}, em cần {tong}",
        "Khối lượng toàn khoá của {lbl} là {tong}",
    ],
    "tin_chi_ky": [
        "Học kỳ {hk} ({nam_ky}) của ngành {lbl} có {hk_tc} tín chỉ",
        "Ở ngành {lbl}, kỳ {hk} nặng {hk_tc} tín chỉ",
        "Theo kế hoạch đào tạo {lbl}, học kỳ {hk} gồm {hk_tc} tín chỉ",
        "Kỳ {hk} ({nam_ky}) ngành {lbl} được thiết kế {hk_tc} tín chỉ",
    ],
    "mon_ky": [
        "Học kỳ {hk} ({nam_ky}) ngành {lbl} gồm {n} học phần với tổng {hk_tc} tín chỉ",
        "Ở kỳ {hk}, sinh viên ngành {lbl} học {n} học phần ({hk_tc} tín chỉ)",
        "Theo kế hoạch đào tạo {lbl}, {nam_ky} có {n} học phần, tổng {hk_tc} tín chỉ",
        "Kỳ {hk} ngành {lbl} bố trí {n} học phần, cộng lại {hk_tc} tín chỉ",
    ],
    "chung": [
        "Theo kế hoạch đào tạo {lbl} khoá {kh}",
        "Căn cứ kế hoạch đào tạo ngành {lbl}",
        "Tra trong chương trình {lbl} khoá {kh}",
        "Với chương trình {lbl}",
    ],
}

# Câu chốt, thêm vào cuối một phần đáp án cho tự nhiên hơn (không phải câu nào cũng có)
CLOSING = [
    "",
    "",
    "",
    "Em đối chiếu thêm kế hoạch đào tạo của khoá mình cho chắc nhé.",
    "Nếu cần bản kế hoạch đào tạo đầy đủ, em xin ở Phòng Quản lý đào tạo.",
    "Em nên bám kế hoạch chuẩn này để không lệch tiến độ tốt nghiệp.",
]


def _idx(key: str, n: int) -> int:
    """Chọn theo băm nội dung: cùng câu hỏi luôn ra cùng cách diễn đạt."""
    h = hashlib.md5(key.encode("utf-8")).digest()
    return h[0] % n if n else 0


def pick(bank: dict, intent: str, key: str, **fields) -> str:
    """Lấy một cách diễn đạt của `intent`, thay các trường trong {}."""
    variants = bank.get(intent)
    if not variants:
        raise KeyError(f"Chưa có cách diễn đạt cho ý định '{intent}'")
    return variants[_idx(intent + "|" + key, len(variants))].format(**fields)


def question(intent: str, key: str, **fields) -> str:
    return pick(QUESTION, intent, key, **fields)


def opening(intent: str, key: str, **fields) -> str:
    return pick(ANSWER_OPEN, intent, key, **fields)


def closing(key: str) -> str:
    return CLOSING[_idx("closing|" + key, len(CLOSING))]


def variety_report(bank: dict) -> str:
    total = sum(len(v) for v in bank.values())
    return f"{len(bank)} ý định hỏi, {total} cách diễn đạt"
