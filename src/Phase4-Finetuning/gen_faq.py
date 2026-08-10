"""Sinh bộ câu hỏi THƯỜNG GẶP của sinh viên kèm đáp án chi tiết có căn cứ.

Danh sách câu hỏi dưới đây được soạn theo cách sinh viên thường hỏi trên thực tế
(cả cách hỏi trang trọng lẫn cách hỏi thân mật), bám vào những chủ đề có thật
trong kho tri thức: học vụ, đăng ký học phần, điểm và xử lý kết quả học tập,
tốt nghiệp, chuẩn đầu ra ngoại ngữ - tin học, học phí, đào tạo trực tuyến - LMS.

Đáp án KHÔNG viết tay và cũng không do mô hình bịa: hệ thống truy xuất đúng điều
khoản liên quan trong kho tri thức rồi dựng đáp án từ nội dung văn bản thật. Câu
hỏi nào không tìm được căn cứ sẽ bị loại bỏ để dữ liệu luôn trung thực.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/gen_faq.py     # -> data/qa/qa_cau_hoi_thuong_gap.csv
"""
from __future__ import annotations
import csv
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import retriever

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes"]
EXCERPT_WORDS = 300
ADVICE = ("Em nên đối chiếu trực tiếp điều khoản nêu trên để nắm đầy đủ chi tiết; "
          "nếu còn vướng mắc, em liên hệ Phòng Quản lý đào tạo hoặc cố vấn học tập "
          "của lớp để được hướng dẫn cụ thể.")

# (nhóm chủ đề, danh sách câu hỏi theo cách sinh viên thường hỏi)
FAQ = [
    ("Xử lý kết quả học tập", [
        "Sinh viên bị cảnh báo học tập trong những trường hợp nào?",
        "Em bị cảnh báo học tập thì phải làm gì để không bị buộc thôi học?",
        "Bị cảnh báo học tập bao nhiêu lần thì bị buộc thôi học?",
        "Những trường hợp nào sinh viên bị buộc thôi học?",
        "Điểm trung bình tích lũy thấp thì bị xử lý như thế nào?",
        "Sinh viên được học tiếp lên năm sau khi nào?",
        "Kết quả học tập của sinh viên được xử lý theo quy định nào?",
    ]),
    ("Đăng ký học phần và kế hoạch học tập", [
        "Sinh viên đăng ký học phần như thế nào?",
        "Một học kỳ em được đăng ký tối đa bao nhiêu tín chỉ?",
        "Em muốn rút bớt học phần đã đăng ký thì làm thế nào?",
        "Học lại học phần chưa đạt thì đăng ký ra sao?",
        "Em muốn học cải thiện điểm thì có được không?",
        "Kế hoạch giảng dạy và học tập được xây dựng như thế nào?",
        "Học phần tiên quyết là gì và ảnh hưởng thế nào đến việc đăng ký?",
    ]),
    ("Đánh giá và tính điểm", [
        "Kết quả học tập của sinh viên được đánh giá như thế nào?",
        "Điểm học phần được tính từ những thành phần nào?",
        "Bao nhiêu điểm thì được coi là đạt học phần?",
        "Cách tính điểm trung bình tích lũy như thế nào?",
        "Thang điểm chữ và thang điểm 4 được quy đổi ra sao?",
        "Em bị điểm F thì phải làm gì?",
    ]),
    ("Tốt nghiệp", [
        "Điều kiện để được xét công nhận tốt nghiệp là gì?",
        "Em cần đáp ứng những gì để được cấp bằng tốt nghiệp?",
        "Thời gian đào tạo tối đa của sinh viên là bao lâu?",
        "Nếu quá thời gian đào tạo tối đa mà chưa tốt nghiệp thì sao?",
        "Hạng tốt nghiệp được xếp như thế nào?",
    ]),
    ("Chuẩn đầu ra ngoại ngữ và tin học", [
        "Chuẩn đầu ra ngoại ngữ của trường yêu cầu đạt trình độ nào?",
        "Các chứng chỉ tiếng Anh nào được nhà trường công nhận?",
        "Em có chứng chỉ VSTEP thì có được công nhận chuẩn đầu ra không?",
        "Chứng chỉ ngoại ngữ phải còn thời hạn bao lâu?",
        "Em có chứng chỉ ngoại ngữ rồi thì có phải học tiếng Anh nữa không?",
        "Chuẩn đầu ra tin học yêu cầu những gì?",
        "Những chứng chỉ tin học nào được nhà trường công nhận?",
        "Chương trình dạy học ngoại ngữ gồm bao nhiêu tín chỉ?",
        "Sinh viên được miễn học ngoại ngữ trong trường hợp nào?",
        "Nếu chưa đạt chuẩn đầu ra ngoại ngữ thì có được xét tốt nghiệp không?",
    ]),
    ("Học phí và nghĩa vụ tài chính", [
        "Học phí được quy định như thế nào?",
        "Học phí học lại và học cải thiện điểm được tính ra sao?",
        "Em nộp học phí muộn thì bị xử lý thế nào?",
        "Sinh viên không hoàn thành nghĩa vụ tài chính thì hậu quả là gì?",
        "Thi lại có phải nộp lệ phí không?",
        "Nghĩa vụ nộp học phí của sinh viên được quy định ra sao?",
    ]),
    ("Đào tạo trực tuyến và hệ thống LMS", [
        "Đào tạo trực tuyến của trường được tổ chức như thế nào?",
        "Hệ thống phần mềm phục vụ đào tạo trực tuyến gồm những gì?",
        "Học liệu đào tạo trực tuyến được quy định thế nào?",
        "Kết quả học tập trực tuyến được đánh giá ra sao?",
        "Sinh viên có trách nhiệm gì khi tham gia học trực tuyến?",
        "Hệ thống LMS dùng để làm gì?",
        "Em đăng nhập vào hệ thống LMS như thế nào?",
        "Nộp bài tập trên hệ thống LMS ra sao?",
    ]),
    ("Tổ chức đào tạo", [
        "Chương trình đào tạo của trường được quy định như thế nào?",
        "Trường tổ chức đào tạo theo những hình thức nào?",
        "Đào tạo theo tín chỉ và theo niên chế khác nhau thế nào?",
        "Liên kết đào tạo được quy định ra sao?",
        "Sinh viên nghỉ học tạm thời cần điều kiện gì?",
        "Em muốn bảo lưu kết quả học tập thì thủ tục thế nào?",
    ]),
    ("Quyền và nghĩa vụ của người học", [
        "Sinh viên có những quyền gì theo quy định của pháp luật?",
        "Nghĩa vụ của sinh viên được quy định như thế nào?",
        "Người học được hưởng những chính sách hỗ trợ nào?",
    ]),
]


def _tidy(text: str) -> str:
    t = re.sub(r"^Điều\s+\d+[a-z]?\s*[.:]\s*", "", text.strip())
    return re.sub(r"\s+", " ", t).strip()


def build_answer(hits) -> str:
    """Dựng đáp án chi tiết từ 1–2 đoạn liên quan nhất, giữ nguyên nội dung văn bản."""
    parts = []
    used = set()
    for h in hits[:2]:
        meta = h["meta"]
        doc = retriever._clean_doc_name(meta.get("source", ""))
        dieu = meta.get("dieu")
        label = f"{doc} ({dieu})" if dieu else doc
        if label in used:
            continue
        used.add(label)
        parts.append((label, _tidy(h["text"])))

    if not parts:
        return ""
    label0, body0 = parts[0]
    words = body0.split()
    if len(words) > EXCERPT_WORDS:
        body0 = " ".join(words[:EXCERPT_WORDS]).rstrip(" ,;.") + "..."
    out = f"Theo {label0}, quy định như sau: {body0}"

    if len(parts) > 1:
        label1, body1 = parts[1]
        extra = " ".join(body1.split()[:120]).rstrip(" ,;.")
        out += f" Bên cạnh đó, {label1} cũng quy định: {extra}..."
    return f"{out} {ADVICE}"


def main():
    rows, idx, skipped = [], 0, []
    for category, questions in FAQ:
        for q in questions:
            hits = retriever.retrieve(q, config.RAG_TOP_K)
            if not retriever.has_relevant(hits):
                skipped.append(q)          # không có căn cứ -> loại, giữ dữ liệu trung thực
                continue
            ans = build_answer(hits)
            if not ans:
                skipped.append(q)
                continue
            idx += 1
            rows.append({
                "id": idx, "category": category, "question": q, "answer": ans,
                "source_refs": " | ".join(retriever.group_sources(hits)),
                "notes": "Câu hỏi thường gặp; đáp án dựng từ văn bản trong kho tri thức",
            })

    out = config.DATA_PROCESSED.parent / "qa" / "qa_cau_hoi_thuong_gap.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    print(f"✅ Sinh {len(rows)} câu hỏi thường gặp -> {out.name}")
    if skipped:
        print(f"⚠️  Bỏ {len(skipped)} câu do kho tri thức chưa có căn cứ:")
        for q in skipped:
            print(f"     ✗ {q}")


if __name__ == "__main__":
    main()
