"""Tra cứu CHÍNH XÁC trên dữ liệu kế hoạch đào tạo đã bóc thành bản ghi.

Đây là nửa "có cấu trúc" của hệ truy xuất. Nửa kia là tìm theo ngữ nghĩa trên văn
bản quy chế (retriever.py). Hai nửa giải hai loại câu hỏi khác nhau:

    "Sinh viên bị cảnh báo học tập khi nào?"   -> tìm ngữ nghĩa, câu trả lời nằm
                                                  gọn trong một đoạn văn.
    "Ngành Kỹ thuật ô tô tổng bao nhiêu tín chỉ?" -> KHÔNG đoạn nào chứa sẵn con
                                                  số này; phải cộng 8 học kỳ.

Mô hình 3B không cộng được và sẽ bịa (đo thực tế: trả lời "150 tín chỉ" khi kho
tri thức chưa hề có kế hoạch đào tạo nào). Nên ở đây ta TỰ TRA rồi đưa kết quả
vào ngữ cảnh dưới nhãn "DỮ KIỆN TRA CỨU", mô hình chỉ còn việc diễn đạt lại.

Hệ quả phụ nhưng quan trọng: hai câu hỏi khác nhau (tổng tín chỉ / môn học kỳ 4 /
môn tiên quyết) sinh ra ba khối dữ kiện khác hẳn nhau, nên câu trả lời không thể
giống nhau như trước.
"""
from __future__ import annotations
import json
import re
import unicodedata
from functools import lru_cache
from typing import Optional

import config

COURSES_FILE = config.DATA_PROCESSED / "curriculum.jsonl"
PROGRAMS_FILE = config.DATA_PROCESSED / "curriculum_programs.json"


def _fold(s: str) -> str:
    """Bỏ dấu + thường hóa để so khớp tên ngành người dùng gõ tự do."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s.replace("đ", "d")).strip()


# Tên ngành trong kế hoạch đào tạo được nhà trường viết TẮT ("KT Nhiệt",
# "Công nghệ KT ô tô") còn sinh viên gõ đầy đủ ("Kỹ thuật nhiệt"). Không khai
# triển thì "ngành Kỹ thuật nhiệt tổng bao nhiêu tín chỉ" không khớp ngành nào,
# rơi xuống nhánh học phần cùng tên và trả về 3 tín chỉ của MÔN thay vì 150 tín
# chỉ của NGÀNH — đo được mô hình nhận dữ kiện sai rồi bịa ra "132 tín chỉ".
_ABBREV = ((r"\bcnkt\b", "cong nghe ky thuat"),
           (r"\bkt\b", "ky thuat"),
           (r"\bcn\b", "cong nghe"))


def _fold_name(s: str) -> str:
    """Như _fold nhưng khai triển các chữ viết tắt hay gặp ở tên ngành."""
    out = _fold(s)
    for pat, full in _ABBREV:
        out = re.sub(pat, full, out)
    return re.sub(r"\s{2,}", " ", out).strip()


@lru_cache(maxsize=1)
def load():
    courses, programs = [], []
    if COURSES_FILE.exists():
        courses = [json.loads(l) for l in COURSES_FILE.open(encoding="utf-8")]
    if PROGRAMS_FILE.exists():
        programs = json.loads(PROGRAMS_FILE.read_text(encoding="utf-8"))
    return courses, programs


def program_label(p: dict) -> str:
    cn = p.get("chuyen_nganh")
    return f"{p['nganh']} — chuyên ngành {cn}" if cn else p["nganh"]


# ------------------------------------------------------------------ nhận diện
# Mọi mẫu dưới đây so khớp trên văn bản ĐÃ BỎ DẤU (_fold). Viết lớp ký tự có dấu
# kiểu [ií] rất dễ sót: "tín chỉ" có chữ "ỉ" không nằm trong lớp đó nên câu hỏi
# "ngành X tổng bao nhiêu tín chỉ" từng không được nhận diện.

# Dấu hiệu CHẮC CHẮN là hỏi kế hoạch đào tạo
_STRONG_INTENT = re.compile(
    r"khung chuong trinh|chuong trinh (dao tao|hoc)|ke hoach dao tao|"
    r"tien quyet|hoc ky\s*\d|nam thu\s*\d|nam \d")

# Dấu hiệu YẾU: nói tới tín chỉ / môn học. Riêng chúng chưa đủ, vì quy chế và quy
# định chuẩn đầu ra cũng nhắc tín chỉ ("chương trình ngoại ngữ 18 tín chỉ").
# Chỉ tính là hỏi kế hoạch đào tạo khi kèm dấu hiệu về NGÀNH/KHOÁ.
_WEAK_INTENT = re.compile(r"tin chi|mon hoc|hoc phan|hoc nhung gi")
_PROGRAM_HINT = re.compile(r"\bnganh\b|chuyen nganh|khoa\s*\d|\bk\d{2}\b")

_SEM_RE = re.compile(r"hoc ky\s*(\d{1,2})")
_YEAR_RE = re.compile(r"nam (?:thu\s*)?(\d)")

# Một cái tên có thể vừa là NGÀNH vừa là HỌC PHẦN ("Kỹ thuật nhiệt" là cả hai).
# Từ chỉ loại trong câu hỏi quyết định hỏi cái nào — thiếu bước này thì
# "ngành Kỹ thuật nhiệt bao nhiêu tín chỉ" (150) và "môn Kỹ thuật nhiệt bao nhiêu
# tín chỉ" (3) nhận cùng một khối dữ kiện.
_ASK_PROGRAM = re.compile(r"\bnganh\b|chuyen nganh|chuong trinh|toan khoa|ca khoa|"
                          r"ra truong|tot nghiep")
_ASK_COURSE = re.compile(r"\bmon\b|\bmon hoc\b|hoc phan")


def is_curriculum_question(q: str) -> bool:
    fq = _fold(q)
    if _STRONG_INTENT.search(fq):
        return True
    if _WEAK_INTENT.search(fq):
        # có nhắc ngành/khoá, gọi thẳng tên một chương trình, hoặc gọi tên một học
        # phần có thật ("môn Kỹ thuật nhiệt mấy tín chỉ?")
        return (bool(_PROGRAM_HINT.search(fq)) or bool(match_programs(q))
                or bool(match_courses(q)))
    return False


def resolve_semester(q: str) -> Optional[int]:
    """Đổi cách nói của sinh viên thành số học kỳ tuyệt đối 1..8.

    "học kỳ 2 năm 2" nghĩa là học kỳ thứ 4 của khoá — nói cách khác (năm-1)*2+kỳ.
    Nếu chỉ nói "học kỳ 5" thì đó đã là số tuyệt đối.
    """
    fq = _fold(q)
    sem = _SEM_RE.search(fq)
    year = _YEAR_RE.search(fq)
    if sem and year:
        k, n = int(sem.group(1)), int(year.group(1))
        return (n - 1) * 2 + k if k in (1, 2) else k
    if sem:
        return int(sem.group(1))
    return None


def match_programs(q: str) -> list[dict]:
    """Tìm chương trình mà câu hỏi đang nhắc tới, khớp theo tên ngành/chuyên ngành."""
    _, programs = load()
    fq = _fold_name(q)
    hits = []          # [(độ dài tên khớp, chương trình)]
    for p in programs:
        best = 0
        for field in (p.get("chuyen_nganh"), p.get("nganh")):
            if not field:
                continue
            key = _fold_name(field)
            # tên ngắn như "ô tô" dễ khớp bừa -> yêu cầu khớp trọn cụm
            if key and key in fq:
                best = max(best, len(key))
        if best:
            hits.append((best, p))
    if not hits:
        return []
    # Tên ngành lồng nhau: "ky thuat o to" là con của "cong nghe ky thuat o to".
    # Hỏi "ngành Công nghệ kỹ thuật ô tô" mà không ưu tiên tên DÀI nhất thì cả hai
    # ngành cùng khớp, dữ kiện trả về gấp đôi và mô hình lẫn tổng tín chỉ hai ngành.
    longest = max(n for n, _ in hits)
    return [p for n, p in hits if n == longest]


def match_courses(q: str) -> list[dict]:
    """Tìm học phần được nhắc tên trong câu hỏi (gộp các ngành cùng dạy môn đó)."""
    courses, _ = load()
    fq = _fold(q)
    best: dict[str, list[dict]] = {}
    for c in courses:
        key = _fold(c["ten_hp"])
        # bỏ tên quá ngắn (dễ khớp bừa) và tên không xuất hiện trong câu hỏi
        if len(key) < 8 or key not in fq:
            continue
        best.setdefault(key, []).append(c)
    if not best:
        return []
    # chọn tên khớp DÀI nhất: "kỹ thuật nhiệt" ưu tiên hơn "hóa học"
    longest = max(best, key=len)
    return best[longest]


# ------------------------------------------------------------------ dữ kiện
def _fmt_courses(rows: list[dict]) -> str:
    out = []
    for r in rows:
        bits = [f"{r['ten_hp']} (mã {r['ma_hp']}, {r['tin_chi']:g} tín chỉ, {r['nhom'].lower()}"]
        if r.get("ktdg"):
            bits.append(f", đánh giá: {r['ktdg']}")
        if r.get("hptq"):
            bits.append(f", học phần tiên quyết: {r['hptq']}")
        out.append("- " + "".join(bits) + ")")
    return "\n".join(out)


def _ky_of(p: dict, sem: int) -> dict:
    return next((h for h in p.get("hoc_ky", []) if h["hoc_ky"] == sem), {})


def _exclusive_note(rows: list[dict], ky: dict) -> str:
    """Cảnh báo các nhánh LOẠI TRỪ NHAU trong một học kỳ.

    Nếu chỉ đưa danh sách học phần, mô hình sẽ cộng hết và ra số lớn hơn tổng
    thật: học kỳ 6 ngành KT Nhiệt liệt kê 11 học phần cộng 35 tín chỉ, nhưng sinh
    viên chỉ học 20 vì hai định hướng chuyên ngành là chọn MỘT, còn nhóm tự chọn
    chỉ lấy 6 trong 9. Phải nói thẳng điều đó ra trong dữ kiện.
    """
    notes = []
    tracks = sorted({r["dinh_huong"] for r in rows if r.get("dinh_huong")})
    if len(tracks) > 1:
        notes.append(f"Học kỳ này có {len(tracks)} định hướng chuyên ngành LOẠI TRỪ "
                     f"NHAU ({'; '.join(tracks)}) — sinh viên chỉ học MỘT định hướng, "
                     f"không cộng gộp cả hai.")
    if any(r.get("he") for r in rows):
        hes = sorted({r["he"] for r in rows if r.get("he")})
        notes.append(f"Một số học phần chỉ dành cho hệ {', '.join(hes)}.")
    if ky.get("tu_chon"):
        listed = sum(r["tin_chi"] for r in rows if r.get("nhom") == "Tự chọn")
        if listed > ky["tu_chon"]:
            notes.append(f"Nhóm tự chọn liệt kê {listed:g} tín chỉ nhưng chỉ cần tích "
                         f"lũy {ky['tu_chon']:g} tín chỉ.")
    if ky.get("tong"):
        notes.append(f"Vì vậy tổng tín chỉ THỰC PHẢI HỌC của học kỳ này là "
                     f"{ky['tong']:g}, KHÔNG phải tổng cộng của mọi học phần liệt kê.")
    return ("\n" + " ".join(notes)) if notes else ""


def facts_for(question: str) -> str:
    """Khối DỮ KIỆN TRA CỨU cho câu hỏi, hoặc chuỗi rỗng nếu không liên quan."""
    if not is_curriculum_question(question):
        return ""
    courses, programs = load()
    if not programs:
        return ""

    progs = match_programs(question) or []
    sem = resolve_semester(question)
    parts: list[str] = []

    named = match_courses(question)
    # Trùng tên giữa ngành và học phần -> để từ chỉ loại trong câu hỏi phân xử.
    if named and progs:
        fq = _fold(question)
        if _ASK_PROGRAM.search(fq):
            named = []
        elif _ASK_COURSE.search(fq):
            progs = []

    # Hỏi thẳng về một học phần: trả đúng học phần đó ở mọi ngành có dạy.
    if named and not progs:
        lines = [f"- {program_label(c)}: học kỳ {c['hoc_ky']}, {c['tin_chi']:g} tín chỉ "
                 f"({c['tin_chi_raw']}), {c['nhom'].lower()}, mã {c['ma_hp']}"
                 + (f", đánh giá: {c['ktdg']}" if c.get("ktdg") else "")
                 + (f", tiên quyết: {c['hptq']}" if c.get("hptq") else "")
                 for c in named]
        return (f"Học phần \"{named[0]['ten_hp']}\" có trong các chương trình sau:\n"
                + "\n".join(lines))

    if not progs:
        # Không nêu rõ ngành -> liệt kê các ngành đang có dữ liệu để mô hình biết
        # phạm vi, tránh nó tự nghĩ ra ngành không tồn tại.
        lines = [f"- {program_label(p)}: {p['tong_tin_chi']:g} tín chỉ toàn khoá"
                 + (f" (hệ kỹ sư {p['tong_tin_chi_ky_su']:g} tín chỉ)" if p.get("co_hai_he") else "")
                 + f", {p['so_hoc_ky']} học kỳ, khoá {p.get('khoa_hoc') or '?'}"
                 for p in programs]
        parts.append("Các ngành hiện CÓ kế hoạch đào tạo trong kho dữ liệu:\n"
                     + "\n".join(lines))
        parts.append("Ngoài các ngành trên, kho dữ liệu KHÔNG có kế hoạch đào tạo "
                     "của ngành nào khác.")
        return "\n\n".join(parts)

    for p in progs:
        head = [f"Chương trình: {program_label(p)} (khoá {p.get('khoa_hoc') or '?'}, "
                f"khoa {p.get('khoa') or '?'}, {p.get('loai_hinh') or ''})".rstrip(", ")]
        head.append(f"Tổng khối lượng toàn khoá: {p['tong_tin_chi']:g} tín chỉ"
                    + (f" đối với hệ cử nhân, {p['tong_tin_chi_ky_su']:g} tín chỉ "
                       f"đối với hệ kỹ sư" if p.get("co_hai_he") else "")
                    + f", chia thành {p['so_hoc_ky']} học kỳ.")
        head.append("Tín chỉ từng học kỳ: "
                    + "; ".join(f"học kỳ {h['hoc_ky']}: {h['tong']:g}" for h in p["hoc_ky"]) + ".")
        parts.append("\n".join(head))

        rows = [c for c in courses if c["source"] == p["source"]]
        if sem is not None:
            sem_rows = [c for c in rows if c["hoc_ky"] == sem]
            if sem_rows:
                parts.append(f"Danh sách học phần học kỳ {sem} của {program_label(p)}:\n"
                             + _fmt_courses(sem_rows)
                             + _exclusive_note(sem_rows, _ky_of(p, sem)))
            else:
                parts.append(f"Chương trình này không có dữ liệu học phần cho học kỳ {sem}.")
    return "\n\n".join(parts)
