"""Sinh bộ câu hỏi – đáp án CHI TIẾT bám sát nội dung văn bản của Nhà trường.

Khác với bộ Q/A soạn tay (đáp án thường ngắn), bộ này lấy nội dung THẬT của từng
Điều trong kho tri thức làm đáp án, nên:
  - Chính xác: mọi chi tiết đều có trong văn bản gốc, không do mô hình bịa ra.
  - Chi tiết: giữ đủ các khoản, mốc số, điều kiện kèm theo.
  - Bao quát: quét toàn bộ các Điều của tất cả tài liệu trong kho tri thức.
  - Trích dẫn đúng: đáp án luôn dẫn TÊN VĂN BẢN kèm số Điều.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/gen_qa_from_docs.py
    # -> data/qa/qa_tu_dong_tu_tai_lieu.csv
    python src/Phase4-Finetuning/build_dataset.py     # gộp vào train.jsonl
"""
from __future__ import annotations
import csv
import json
import re
import sys
import pathlib
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import retriever  # dùng _clean_doc_name để lấy tên văn bản chuẩn

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes"]

# Gán nhóm chủ đề theo tên tài liệu, cho khớp cách phân loại của bộ Q/A soạn tay.
CATEGORY_BY_DOC = {
    "Quy chế đào tạo trình độ đại học": "Quản lý học tập và tiến độ đào tạo",
    "Quy định về đào tạo trực tuyến": "Đào tạo trực tuyến và hệ thống LMS",
    "Quy định về chuẩn đầu ra ngoại ngữ và tin học": "Chuẩn đầu ra ngoại ngữ và tin học",
    "Quy định về học phí và các khoản thu khác": "Học phí và nghĩa vụ tài chính",
    "Tài liệu hướng dẫn sử dụng hệ thống LMS": "Đào tạo trực tuyến và hệ thống LMS",
    "Luật Giáo dục đại học": "Quy định pháp luật về giáo dục đại học",
}

# Mẫu câu hỏi: sinh nhiều cách hỏi cho cùng một Điều để bộ dữ liệu đa dạng hơn.
QUESTION_TEMPLATES = [
    "{topic} được quy định như thế nào?",
    "Theo {doc}, {topic_low} được quy định ra sao?",
    "Em muốn hỏi về {topic_low}, nhà trường quy định thế nào ạ?",
]


# Dấu hiệu tiêu đề bị dính nội dung điều khoản (không dùng để đặt câu hỏi được)
_NOT_TITLE = re.compile(
    r"quyết định này|kể từ ngày|ban hành kèm|chịu trách nhiệm thi hành|"
    r"có hiệu lực|trong luật này|quy chế này|theo quy định tại|các ông|các bà",
    re.IGNORECASE)


_VN_LOWER = "a-zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
_VN_UPPER_C = ("A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊ"
               "ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ")
# Ranh giới "từ thường + Từ Hoa": thường là chỗ tiêu đề kết thúc và nội dung bắt đầu
_TITLE_CUT = re.compile(r"(?<=[" + _VN_LOWER + r"])\s+(?=[" + _VN_UPPER_C + r"])")


def _norm_topic(heading: str) -> str:
    """Rút gọn tiêu đề Điều thành 'chủ đề' đặt câu hỏi. Trả về '' nếu không dùng được."""
    t = re.sub(r"\s+", " ", (heading or "").strip())
    # cắt trước khoản đầu tiên nếu tiêu đề bị dính nội dung
    t = re.split(r"\s+\d{1,2}\s*[.)]\s+", " " + t)[0].strip()
    # cắt tại chỗ nội dung điều khoản bắt đầu (chữ hoa mở câu mới)
    first = _TITLE_CUT.split(t)[0].strip()
    if len(first.split()) >= 3:
        t = first
    t = t.rstrip(" ,.;:")

    # Tiêu đề thật thường ngắn gọn; nếu quá dài hoặc mang dấu hiệu nội dung
    # điều khoản thì không dùng để sinh câu hỏi.
    if not t or len(t.split()) > 12 or _NOT_TITLE.search(t):
        return ""
    if re.search(r"\d{2,}", t):          # chứa số hiệu/ngày tháng -> không phải tiêu đề
        return ""
    return t


def _tidy(text: str) -> str:
    """Làm gọn nội dung Điều để dùng làm đáp án."""
    t = re.sub(r"^Điều\s+\d+[a-z]?\s*[.:]\s*", "", text.strip())
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def load_dieu_texts():
    """Gom các đoạn cùng một Điều thành nội dung đầy đủ của Điều đó."""
    if not config.CHUNKS_FILE.exists():
        raise SystemExit("Chưa có chunks.jsonl. Chạy pipeline Giai đoạn 1 trước.")
    rows = [json.loads(l) for l in config.CHUNKS_FILE.open(encoding="utf-8")]
    grouped = defaultdict(lambda: {"parts": [], "heading": "", "chuong": ""})
    for r in rows:
        if not r.get("dieu"):
            continue
        key = (r["source"], r["dieu"])
        g = grouped[key]
        g["parts"].append(r["text"])
        if r.get("heading") and not g["heading"]:
            g["heading"] = r["heading"]
        if r.get("chuong") and not g["chuong"]:
            g["chuong"] = r["chuong"]
    return grouped


def build_answer(doc: str, dieu: str, body: str) -> str:
    """Đáp án chi tiết: dẫn tên văn bản + số Điều, giữ nguyên nội dung quy định."""
    body = _tidy(body)
    # giới hạn độ dài để mẫu huấn luyện không quá tải, vẫn đủ chi tiết
    words = body.split()
    if len(words) > 420:
        body = " ".join(words[:420]).rstrip(" ,;.") + "..."
    return (f"Theo {doc} ({dieu}), quy định cụ thể như sau: {body} "
            f"Em nên đối chiếu trực tiếp {dieu} của {doc} để nắm đầy đủ chi tiết; "
            f"nếu còn vướng mắc, em liên hệ Phòng Quản lý đào tạo hoặc cố vấn học tập "
            f"của lớp để được hướng dẫn cụ thể.")


def main():
    grouped = load_dieu_texts()
    out_rows, idx = [], 0
    seen_q = set()

    for (source, dieu), g in grouped.items():
        doc = retriever._clean_doc_name(source)
        body = " ".join(g["parts"])
        if len(body.split()) < 40:
            continue                       # Điều quá ngắn, ít giá trị hỏi đáp
        category = CATEGORY_BY_DOC.get(doc, "Quy định chung")
        answer = build_answer(doc, dieu, body)

        topic = _norm_topic(g["heading"])
        if topic and len(topic) >= 6:
            templates = QUESTION_TEMPLATES
        else:
            # Tiêu đề không dùng được -> hỏi theo số Điều để vẫn bao quát văn bản
            templates = ["{dieu} của {doc} quy định về nội dung gì?"]

        for tpl in templates:
            q = tpl.format(doc=doc, dieu=dieu, topic=topic,
                           topic_low=(topic[0].lower() + topic[1:]) if topic else topic)
            key = " ".join(q.lower().split())
            if key in seen_q:
                continue
            seen_q.add(key)
            idx += 1
            out_rows.append({
                "id": idx, "category": category, "question": q, "answer": answer,
                "source_refs": f"{dieu}, {doc}",
                "notes": "Sinh tự động từ nội dung văn bản trong kho tri thức",
            })

    out = config.DATA_PROCESSED.parent / "qa" / "qa_tu_dong_tu_tai_lieu.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(out_rows)

    n_dieu = len({(s, d) for (s, d) in grouped})
    print(f"✅ Sinh {len(out_rows)} cặp Q/A từ {n_dieu} Điều -> {out.name}")
    by_cat = defaultdict(int)
    for r in out_rows:
        by_cat[r["category"]] += 1
    for c, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"   {n:4}  {c}")
    print("\nChạy tiếp: python src/Phase4-Finetuning/build_dataset.py")


if __name__ == "__main__":
    main()
