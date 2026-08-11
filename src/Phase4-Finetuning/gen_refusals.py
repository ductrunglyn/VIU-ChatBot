"""Sinh mẫu huấn luyện dạy mô hình TỪ CHỐI khi kho tri thức không có câu trả lời.

Vì sao cần: toàn bộ 1834 mẫu hiện có đều dạy "hỏi là phải trả lời". Không mẫu nào
dạy "tài liệu không có thông tin này". Hậu quả đo được khi dùng thật — hỏi khung
chương trình ngành Công nghệ thông tin, mô hình bịa ra "tổng số tín chỉ là 150"
và "Nhà trường đào tạo 02 ngành chính: Công nghệ thông tin và Công nghệ thông
tin", trong khi kho tri thức KHÔNG có bất kỳ tài liệu chương trình đào tạo nào.

Bộ lọc `retriever.has_relevant` không chặn được các câu này: chúng vẫn truy xuất
ra điều khoản nói CHUNG về chương trình đào tạo (Điều 2 Quy chế), điểm xếp hạng
cao, chỉ là không chứa con số cụ thể được hỏi. Đây là trường hợp "đúng chủ đề
nhưng thiếu dữ kiện" — chỉ dạy được bằng ví dụ.

Mẫu sinh ra có ngữ cảnh THẬT (truy xuất y như lúc chạy) nhưng đáp án là lời từ
chối nêu rõ thiếu tài liệu gì và hỏi ai, chứ không phải câu từ chối chung chung.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/gen_refusals.py            # -> data/qa/qa_tu_choi.csv
"""
from __future__ import annotations
import csv
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes", "origin"]

# Mỗi nhóm: (thiếu tài liệu gì, hỏi đơn vị nào, danh sách câu hỏi thật của sinh viên)
GROUPS = [
    (
        "khung chương trình đào tạo của từng ngành",
        "Phòng Quản lý đào tạo hoặc khoa chủ quản ngành",
        [
            "Khung chương trình ngành Công nghệ thông tin gồm bao nhiêu tín chỉ?",
            "Ngành Công nghệ thông tin học bao nhiêu tín chỉ thì ra trường?",
            "Chương trình đào tạo ngành Kế toán có tổng bao nhiêu tín chỉ?",
            "Các môn học của ngành Công nghệ thông tin học kỳ 2 năm 2 là gì?",
            "Học kỳ 1 năm nhất ngành Điện tử viễn thông học những môn nào?",
            "Cho em xem danh sách học phần bắt buộc của ngành Khoa học máy tính",
            "Môn Mạng máy tính có mấy tín chỉ?",
            "Học phần Trí tuệ nhân tạo là bắt buộc hay tự chọn?",
            "Ngành Công nghệ thông tin có mấy chuyên ngành?",
            "Trường đang đào tạo bao nhiêu ngành đại học?",
            "Môn nào là môn tiên quyết của học phần Cơ sở dữ liệu?",
            "Kế hoạch học tập chuẩn toàn khóa của ngành Marketing như thế nào?",
        ],
    ),
    (
        "biểu mức thu học phí cụ thể theo từng ngành, từng khóa",
        "Phòng Tài chính - Kế toán",
        [
            "Học phí ngành Công nghệ thông tin một kỳ là bao nhiêu tiền?",
            "Một tín chỉ có giá bao nhiêu?",
            "Học phí năm học này tăng bao nhiêu phần trăm?",
            "Học lại một môn thì phải đóng bao nhiêu tiền?",
            "Tiền học phí ngành Kế toán khác ngành Công nghệ thông tin không?",
            "Em thuộc diện miễn giảm thì được giảm bao nhiêu phần trăm học phí?",
        ],
    ),
    (
        "quy định về tuyển sinh, phương thức xét tuyển và điểm chuẩn",
        "Phòng Tuyển sinh và Truyền thông",
        [
            "Điểm chuẩn ngành Công nghệ thông tin năm ngoái là bao nhiêu?",
            "Trường xét tuyển bằng những phương thức nào?",
            "Em thi khối A01 có xét tuyển được ngành Công nghệ thông tin không?",
            "Chỉ tiêu tuyển sinh năm nay của trường là bao nhiêu?",
            "Hồ sơ xét tuyển học bạ cần những giấy tờ gì?",
            "Thời gian nộp hồ sơ xét tuyển đến khi nào?",
        ],
    ),
    (
        "quy định về công tác sinh viên như ký túc xá, học bổng, chế độ chính sách",
        "Phòng Công tác sinh viên",
        [
            "Trường có ký túc xá cho sinh viên không?",
            "Giá phòng ký túc xá một tháng là bao nhiêu?",
            "Điều kiện để được nhận học bổng khuyến khích học tập là gì?",
            "Học bổng của trường có mấy mức?",
            "Sinh viên có được vay vốn ngân hàng chính sách không?",
            "Em là con thương binh thì được hưởng chế độ gì?",
            "Trường có bảo hiểm y tế cho sinh viên không?",
            "Sinh viên vi phạm nội quy ký túc xá bị xử lý thế nào?",
        ],
    ),
    (
        "lịch học, lịch thi và thời khóa biểu từng học kỳ",
        "Phòng Quản lý đào tạo hoặc xem thông báo trên hệ thống",
        [
            "Lịch thi cuối kỳ này của em vào ngày nào?",
            "Khi nào trường công bố thời khóa biểu học kỳ tới?",
            "Học kỳ hè năm nay bắt đầu từ ngày mấy?",
            "Lịch nghỉ Tết của sinh viên là khi nào?",
            "Bao giờ có điểm thi học phần?",
        ],
    ),
    (
        "thông tin về việc làm, thực tập và hợp tác doanh nghiệp",
        "khoa chủ quản ngành hoặc Trung tâm Hỗ trợ sinh viên và Quan hệ doanh nghiệp",
        [
            "Sinh viên tốt nghiệp ngành Công nghệ thông tin làm được những việc gì?",
            "Trường liên kết thực tập với những công ty nào?",
            "Tỷ lệ sinh viên có việc làm sau tốt nghiệp là bao nhiêu?",
            "Mức lương khởi điểm của sinh viên ra trường khoảng bao nhiêu?",
            "Trường có hỗ trợ giới thiệu việc làm không?",
        ],
    ),
]


def build_answer(missing: str, office: str) -> str:
    """Lời từ chối CỤ THỂ: thiếu tài liệu gì, và hỏi ai để có thông tin đúng."""
    return (
        f"Nội dung này chưa có trong các văn bản quy định mà cô/thầy đang tra cứu được, "
        f"em ạ. Kho tài liệu hiện có gồm quy chế đào tạo, quy định đào tạo trực tuyến, "
        f"chuẩn đầu ra ngoại ngữ - tin học, quy định học phí, hướng dẫn hệ thống LMS và "
        f"Luật Giáo dục đại học — chưa bao gồm {missing}, nên cô/thầy không dám nêu con "
        f"số hay danh sách cụ thể để tránh cho em thông tin sai. "
        f"Em liên hệ {office} để được cung cấp thông tin chính xác và mới nhất nhé."
    )


def main():
    qa_dir = config.DATA_PROCESSED.parent / "qa"
    out = qa_dir / "qa_tu_choi.csv"

    rows, i = [], 0
    for missing, office, questions in GROUPS:
        for q in questions:
            i += 1
            rows.append({
                "id": str(i),
                "category": "Ngoài phạm vi kho tri thức",
                "question": q,
                "answer": build_answer(missing, office),
                "source_refs": "",
                "notes": f"Mẫu từ chối — thiếu {missing}",
                "origin": "gen_refusals.py",
            })

    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    print(f"✅ {len(rows)} mẫu từ chối -> {out}")
    for missing, _, qs in GROUPS:
        print(f"   {len(qs):3d}  {missing}")
    print("\nChạy tiếp: python src/Phase4-Finetuning/build_dataset.py")


if __name__ == "__main__":
    main()
