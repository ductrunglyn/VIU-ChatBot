"""Sinh bộ Q/A cho kế hoạch đào tạo, theo 4 MỨC ĐỘ khó dần.

    Mức 1 - Dễ        : tra một dữ kiện đơn ("ngành X tổng bao nhiêu tín chỉ?").
    Mức 2 - Trung bình: lọc/liệt kê ("học kỳ 4 ngành X học những môn nào?").
    Mức 3 - Khó       : tổng hợp, so sánh, đếm ("ngành nào nặng tín chỉ nhất?").
    Mức 4 - Liên văn bản: phải ghép kế hoạch đào tạo VỚI quy chế/quy định khác
                          ("học ngành X thì ngoài tín chỉ còn cần chuẩn ngoại ngữ gì?").

Mọi đáp án đều dựng từ dữ liệu thật: con số lấy từ bản ghi đã bóc (curriculum.jsonl)
và trích dẫn quy định lấy nguyên văn từ kho tri thức. Không có câu nào do mô hình
tự nghĩ ra, nên dùng làm dữ liệu huấn luyện thì không dạy mô hình bịa.

Mức 4 quan trọng nhất: đây là loại câu hỏi sinh viên thực sự hỏi ("em ngành ô tô,
ra trường cần gì?") và cũng là loại mà truy xuất một tài liệu đơn lẻ luôn trả lời
thiếu.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/gen_qa_curriculum.py     # -> data/qa/qa_ke_hoach_dao_tao.csv
"""
from __future__ import annotations
import csv
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import curriculum_index as CI
import retriever

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes", "origin"]
OUT = config.DATA_PROCESSED.parent / "qa" / "qa_ke_hoach_dao_tao.csv"

# Số học kỳ của một năm học, dùng để đổi "học kỳ 2 năm 2" <-> "học kỳ 4"
KY_MOI_NAM = 2


def _label(p):
    return CI.program_label(p)


def _nam_ky(hoc_ky: int) -> str:
    nam = (hoc_ky - 1) // KY_MOI_NAM + 1
    ky = (hoc_ky - 1) % KY_MOI_NAM + 1
    return f"học kỳ {ky} năm thứ {nam}"


def _courses_of(courses, p, hoc_ky=None):
    rows = [c for c in courses if c["source"] == p["source"]]
    return [c for c in rows if hoc_ky is None or c["hoc_ky"] == hoc_ky]


def _list_courses(rows) -> str:
    return "; ".join(f"{c['ten_hp']} ({c['tin_chi']:g} tín chỉ, mã {c['ma_hp']})"
                     for c in rows)


def _tong_str(p) -> str:
    if p.get("co_hai_he"):
        return (f"{p['tong_tin_chi']:g} tín chỉ đối với hệ cử nhân và "
                f"{p['tong_tin_chi_ky_su']:g} tín chỉ đối với hệ kỹ sư")
    return f"{p['tong_tin_chi']:g} tín chỉ"


# --------------------------------------------------------------- mức 1: dễ
def level1(courses, programs):
    out = []
    for p in programs:
        lbl = _label(p)
        out.append((
            f"Ngành {lbl} tổng cộng bao nhiêu tín chỉ?",
            f"Chương trình {lbl} khoá {p['khoa_hoc']} có tổng khối lượng {_tong_str(p)}, "
            f"chia thành {p['so_hoc_ky']} học kỳ. Đây là số tín chỉ em cần tích lũy đủ "
            f"để được xét tốt nghiệp."))
        out.append((
            f"Ngành {lbl} học trong mấy học kỳ?",
            f"Chương trình {lbl} khoá {p['khoa_hoc']} được thiết kế {p['so_hoc_ky']} học kỳ, "
            f"tương ứng {p['so_hoc_ky'] // KY_MOI_NAM} năm học, do khoa {p['khoa']} quản lý, "
            f"loại hình {p['loai_hinh'].lower()}."))
        for h in p["hoc_ky"]:
            out.append((
                f"Học kỳ {h['hoc_ky']} ngành {lbl} có bao nhiêu tín chỉ?",
                f"Học kỳ {h['hoc_ky']} ({_nam_ky(h['hoc_ky'])}) của ngành {lbl} có "
                f"{h['tong']:g} tín chỉ"
                + (f", trong đó {h['bat_buoc']:g} tín chỉ bắt buộc" if "bat_buoc" in h else "")
                + (f" và {h['tu_chon']:g} tín chỉ tự chọn" if h.get("tu_chon") else "")
                + "."))
    return out


# ------------------------------------------------------ mức 2: trung bình
def level2(courses, programs):
    out = []
    for p in programs:
        lbl = _label(p)
        for h in p["hoc_ky"]:
            rows = _courses_of(courses, p, h["hoc_ky"])
            if not rows:
                continue
            out.append((
                f"Học kỳ {h['hoc_ky']} ngành {lbl} học những môn gì?",
                f"Học kỳ {h['hoc_ky']} ({_nam_ky(h['hoc_ky'])}) ngành {lbl} gồm {len(rows)} "
                f"học phần với tổng {h['tong']:g} tín chỉ: {_list_courses(rows)}."))
            out.append((
                f"Các môn học của ngành {lbl} {_nam_ky(h['hoc_ky'])} là gì?",
                f"{_nam_ky(h['hoc_ky']).capitalize()} tương ứng học kỳ {h['hoc_ky']} của "
                f"chương trình {lbl}, gồm: {_list_courses(rows)}. Tổng {h['tong']:g} tín chỉ."))

            bb = [c for c in rows if c["nhom"] == "Bắt buộc"]
            tc = [c for c in rows if c["nhom"] == "Tự chọn"]
            if tc:
                out.append((
                    f"Học kỳ {h['hoc_ky']} ngành {lbl} có môn tự chọn nào?",
                    f"Học kỳ {h['hoc_ky']} ngành {lbl} yêu cầu {h.get('tu_chon', 0):g} tín chỉ "
                    f"tự chọn, em chọn trong các học phần sau: {_list_courses(tc)}. "
                    f"Ngoài ra có {len(bb)} học phần bắt buộc phải học."))
    # tra theo tên học phần
    seen = set()
    for c in courses:
        key = c["ten_hp"].lower()
        if key in seen:
            continue
        seen.add(key)
        same = [x for x in courses if x["ten_hp"].lower() == key]
        progs = "; ".join(f"{_label(_prog_of(programs, x))} (học kỳ {x['hoc_ky']})"
                          for x in same)
        out.append((
            f"Học phần {c['ten_hp']} có mấy tín chỉ và học ở kỳ nào?",
            f"Học phần {c['ten_hp']} (mã {c['ma_hp']}) có {c['tin_chi']:g} tín chỉ, "
            f"phân bổ {c['tin_chi_raw']}, thuộc nhóm {c['nhom'].lower()}"
            + (f", hình thức đánh giá: {c['ktdg']}" if c.get("ktdg") else "")
            + f". Học phần này nằm trong chương trình: {progs}."))
    return out


def _prog_of(programs, course):
    return next(p for p in programs if p["source"] == course["source"])


# --------------------------------------------------------------- mức 3: khó
def level3(courses, programs):
    out = []
    # so sánh khối lượng giữa các ngành
    rank = sorted(programs, key=lambda p: -p["tong_tin_chi"])
    bang = "; ".join(f"{_label(p)}: {p['tong_tin_chi']:g} tín chỉ" for p in rank)
    out.append((
        "Ngành nào của trường có khối lượng tín chỉ lớn nhất?",
        f"Trong các chương trình khoá 50 hiện có, {_label(rank[0])} có khối lượng lớn nhất "
        f"với {rank[0]['tong_tin_chi']:g} tín chỉ, còn {_label(rank[-1])} thấp nhất với "
        f"{rank[-1]['tong_tin_chi']:g} tín chỉ. Cụ thể từng ngành: {bang}."))

    for p in programs:
        lbl = _label(p)
        rows = _courses_of(courses, p)
        bb = [c for c in rows if c["nhom"] == "Bắt buộc"]
        heavy = max(p["hoc_ky"], key=lambda h: h["tong"])
        light = min(p["hoc_ky"], key=lambda h: h["tong"])
        out.append((
            f"Ngành {lbl} có bao nhiêu học phần và học kỳ nào nặng nhất?",
            f"Chương trình {lbl} liệt kê {len(rows)} học phần, trong đó {len(bb)} học phần "
            f"bắt buộc. Học kỳ nặng nhất là học kỳ {heavy['hoc_ky']} với {heavy['tong']:g} "
            f"tín chỉ, nhẹ nhất là học kỳ {light['hoc_ky']} với {light['tong']:g} tín chỉ. "
            f"Tổng toàn khoá {_tong_str(p)}. Em nên cân đối khối lượng đăng ký ở các kỳ nặng."))

        by_ktdg = {}
        for c in rows:
            if c.get("ktdg"):
                by_ktdg.setdefault(c["ktdg"], []).append(c["ten_hp"])
        if by_ktdg:
            desc = "; ".join(f"{k}: {len(v)} học phần" for k, v in sorted(by_ktdg.items()))
            out.append((
                f"Ngành {lbl} đánh giá kết quả học phần bằng những hình thức nào?",
                f"Chương trình {lbl} sử dụng các hình thức đánh giá sau — {desc}. "
                f"Hình thức đánh giá của từng học phần được ghi rõ trong kế hoạch đào tạo "
                f"khoá {p['khoa_hoc']}."))

    # môn chung giữa các ngành
    by_name = {}
    for c in courses:
        by_name.setdefault(c["ten_hp"], set()).add(c["source"])
    chung = sorted([n for n, s in by_name.items() if len(s) >= len(programs)])
    if chung:
        out.append((
            "Những học phần nào tất cả các ngành đều phải học?",
            f"Có {len(chung)} học phần xuất hiện trong toàn bộ {len(programs)} chương trình "
            f"khoá 50 hiện có: {', '.join(chung)}. Đây là khối kiến thức chung, em học ngành "
            f"nào cũng phải tích lũy."))
    return out


# ------------------------------------------------- mức 4: liên kết văn bản
# Mỗi mục: (chủ đề truy xuất, cách đặt câu hỏi, cách dựng câu trả lời)
CROSS_TOPICS = [
    ("chuẩn đầu ra ngoại ngữ sinh viên phải đạt bậc mấy",
     "Em học ngành {lbl}, ngoài việc tích lũy đủ tín chỉ thì còn phải đạt chuẩn ngoại ngữ nào?",
     "Về khối lượng, chương trình {lbl} yêu cầu {tong}. Nhưng tích lũy đủ tín chỉ mới là "
     "một điều kiện. {quote} Nói cách khác, em cần song song hai việc: hoàn thành "
     "{tong} theo kế hoạch đào tạo khoá {khoa_hoc}, và có minh chứng đạt chuẩn ngoại ngữ "
     "theo quy định trên trước khi xét tốt nghiệp."),

    ("chuẩn đầu ra tin học năng lực số",
     "Ngành {lbl} có yêu cầu chuẩn tin học không?",
     "Có. Kế hoạch đào tạo {lbl} khoá {khoa_hoc} quy định khối lượng {tong}, còn yêu cầu "
     "tin học nằm ở văn bản riêng. {quote} Vậy ngoài các học phần trong kế hoạch đào tạo, "
     "em phải đạt thêm chuẩn đầu ra tin học mới đủ điều kiện xét tốt nghiệp."),

    ("cảnh báo học tập điểm trung bình tích lũy",
     "Em học ngành {lbl}, nếu học kỳ nặng mà kết quả kém thì có bị cảnh báo học tập không?",
     "Kế hoạch đào tạo {lbl} có học kỳ nặng nhất là học kỳ {heavy_ky} với {heavy_tc} tín chỉ, "
     "nên đây là kỳ dễ đuối nhất. Việc cảnh báo học tập không tính theo ngành mà theo quy "
     "chế chung. {quote} Em nên theo dõi điểm trung bình tích lũy sau mỗi kỳ, đặc biệt ở "
     "học kỳ {heavy_ky}, và giảm số tín chỉ đăng ký nếu thấy quá tải."),

    ("nghĩa vụ nộp học phí thời hạn nộp",
     "Học kỳ {heavy_ky} ngành {lbl} có {heavy_tc} tín chỉ, em cần lưu ý gì về học phí?",
     "Theo kế hoạch đào tạo {lbl}, học kỳ {heavy_ky} có {heavy_tc} tín chỉ — là học kỳ nặng "
     "nhất toàn khoá nên học phí kỳ này cũng cao nhất. {quote} Em chủ động chuẩn bị tài "
     "chính sớm cho kỳ này, hoặc làm đơn xin gia hạn nếu khó khăn."),

    ("đào tạo trực tuyến công nhận tín chỉ hệ thống LMS",
     "Các học phần trong kế hoạch đào tạo ngành {lbl} có thể học trực tuyến không?",
     "Kế hoạch đào tạo {lbl} khoá {khoa_hoc} gồm {tong} và không tự quy định hình thức dạy "
     "học; việc tổ chức trực tuyến theo văn bản riêng. {quote} Em xem thông báo từng học kỳ "
     "để biết học phần nào của ngành mình được tổ chức trực tuyến."),
]


def _quote_for(topic: str, max_words: int = 110):
    """Lấy nguyên văn đoạn quy định liên quan, kèm tên văn bản và số Điều."""
    hits = retriever.retrieve(topic, 3)
    if not hits or not retriever.has_relevant(hits):
        return None, None
    top = hits[0]
    doc = retriever._clean_doc_name(top["meta"].get("source", ""))
    dieu = top["meta"].get("dieu")
    label = f"{doc} ({dieu})" if dieu else doc
    text = re.sub(r"\s+", " ", top["text"]).strip()
    text = re.sub(r"^Điều\s+\d+[a-z]?\s*[.:]\s*", "", text)
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip(" ,;.") + "..."
    return f"Theo {label}: {text}", " | ".join(retriever.group_sources(hits))


def level4(courses, programs):
    out = []
    for topic, q_tpl, a_tpl in CROSS_TOPICS:
        quote, refs = _quote_for(topic)
        if not quote:
            print(f"   ⚠️  bỏ chủ đề liên văn bản (không có căn cứ): {topic[:40]}")
            continue
        for p in programs:
            heavy = max(p["hoc_ky"], key=lambda h: h["tong"])
            fields = {
                "lbl": _label(p), "tong": _tong_str(p), "khoa_hoc": p["khoa_hoc"],
                "heavy_ky": heavy["hoc_ky"], "heavy_tc": f"{heavy['tong']:g}",
                "quote": quote,
            }
            out.append((q_tpl.format(**fields), a_tpl.format(**fields), refs))
    return out


def main():
    courses, programs = CI.load()
    if not programs:
        print("❌ Chưa có dữ liệu kế hoạch đào tạo. Chạy trước:")
        print("   python src/Phase1-DataPreprocessing/curriculum.py")
        sys.exit(1)

    groups = [
        ("Kế hoạch đào tạo - mức 1 (dễ)", level1(courses, programs)),
        ("Kế hoạch đào tạo - mức 2 (trung bình)", level2(courses, programs)),
        ("Kế hoạch đào tạo - mức 3 (khó)", level3(courses, programs)),
        ("Kế hoạch đào tạo - mức 4 (liên kết nhiều văn bản)", level4(courses, programs)),
    ]

    rows, i, seen = [], 0, set()
    for cat, pairs in groups:
        n = 0
        for item in pairs:
            q, a = item[0], item[1]
            refs = item[2] if len(item) > 2 else ""
            key = " ".join(q.lower().split())
            if key in seen:
                continue
            seen.add(key)
            i += 1
            n += 1
            rows.append({"id": str(i), "category": cat, "question": q, "answer": a,
                         "source_refs": refs, "notes": "",
                         "origin": "gen_qa_curriculum.py"})
        print(f"  {n:5d}  {cat}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)
    words = [len(r["answer"].split()) for r in rows]
    print(f"\n✅ {len(rows)} cặp Q/A -> {OUT}")
    print(f"   Đáp án: trung bình {sum(words)//len(words)} từ, dài nhất {max(words)}")


if __name__ == "__main__":
    main()
