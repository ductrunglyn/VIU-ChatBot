"""Sinh bộ Q/A NÂNG CAO, tập trung vào câu khó và câu phải đọc nhiều văn bản.

Tỉ lệ mặc định theo yêu cầu: 20% trung bình, 30% khó, 50% liên kết nhiều văn bản.
Ghi ra tệp RIÊNG để đánh giá mô hình xong mới quyết định ghép vào bộ đang dùng.

Điểm khác gen_qa_curriculum.py: bộ này KHÔNG dùng GPU. Trích dẫn quy định được
lấy trực tiếp từ data/processed/chunks.jsonl theo (tên văn bản, số Điều) đã biết
trước, thay vì truy xuất bằng mô hình nhúng. Nhờ vậy chạy nền được song song với
tiến trình huấn luyện mà không tranh chấp bộ nhớ GPU.

Ba mức:
  - Trung bình : lọc/đếm trong một chương trình ("năm thứ 2 ngành X mấy tín chỉ?").
  - Khó        : tổng hợp, so sánh giữa các ngành, phân bố hình thức đánh giá.
  - Liên văn bản: bắt buộc ghép số liệu kế hoạch đào tạo VỚI điều khoản quy chế /
                  chuẩn đầu ra / học phí / đào tạo trực tuyến / Luật GDĐH.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/gen_qa_advanced.py                 # 1000 câu
    python src/Phase4-Finetuning/gen_qa_advanced.py --target 500
"""
from __future__ import annotations
import argparse
import csv
import itertools
import json
import random
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config
import curriculum_index as CI
import phrasing as PH

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes", "origin"]
OUT = config.DATA_PROCESSED.parent / "qa" / "qa_nang_cao.csv"
KY_MOI_NAM = 2
QUOTE_WORDS = 95            # độ dài tối đa phần trích quy định trong đáp án

CAT = {
    "tb": "Nâng cao - mức trung bình",
    "kho": "Nâng cao - mức khó",
    "lien": "Nâng cao - liên kết nhiều văn bản",
}


# ------------------------------------------------------------- trích quy định
def _load_chunks():
    rows = [json.loads(l) for l in config.CHUNKS_FILE.open(encoding="utf-8")]
    return rows


class Quotes:
    """Tra nguyên văn một Điều trong kho tri thức, không cần GPU."""

    def __init__(self):
        self.rows = _load_chunks()

    def get(self, source_hint: str, dieu: str):
        for r in self.rows:
            if source_hint in r["source"] and r.get("dieu") == dieu:
                text = re.sub(r"\s+", " ", r["text"]).strip()
                text = re.sub(r"^Điều\s+\d+[a-z]?\s*[.:]\s*", "", text)
                words = text.split()
                if len(words) > QUOTE_WORDS:
                    text = " ".join(words[:QUOTE_WORDS]).rstrip(" ,;.") + "..."
                doc = _doc_title(r["source"])
                return f"Theo {doc} ({dieu}): {text}", f"{dieu} — {doc}"
        return None, None


def _doc_title(source: str) -> str:
    stem = pathlib.Path(source).stem
    return config.DOC_TITLES.get(stem, stem)


# ------------------------------------------------------------------ tiện ích
def _label(p):
    return CI.program_label(p)


def _nam_ky(k: int) -> str:
    return f"học kỳ {(k - 1) % KY_MOI_NAM + 1} năm thứ {(k - 1) // KY_MOI_NAM + 1}"


def _tong_str(p) -> str:
    if p.get("co_hai_he"):
        return (f"{p['tong_tin_chi']:g} tín chỉ (hệ cử nhân) / "
                f"{p['tong_tin_chi_ky_su']:g} tín chỉ (hệ kỹ sư)")
    return f"{p['tong_tin_chi']:g} tín chỉ"


def _rows_of(courses, p, ky=None):
    rs = [c for c in courses if c["source"] == p["source"]]
    return [c for c in rs if ky is None or c["hoc_ky"] == ky]


def _names(rows) -> str:
    return ", ".join(c["ten_hp"] for c in rows)


def _detail(rows) -> str:
    return "; ".join(f"{c['ten_hp']} ({c['tin_chi']:g} tín chỉ)" for c in rows)


def _ky_of(p, k):
    return next((h for h in p["hoc_ky"] if h["hoc_ky"] == k), None)


def _bat_buoc_cau(h, rs, k, lbl) -> str:
    """Câu trả lời cho "học kỳ K có mấy học phần bắt buộc".

    Không lấy con số ở dòng nhãn "Bắt buộc" của tài liệu làm tổng cho danh sách
    liệt kê: 10/48 học kỳ có nhãn KHÔNG khớp danh sách môn (tài liệu gộp khối kỹ
    sư hoặc một định hướng vào nhãn đó, có tệp còn tự cộng lệch 1). Bản sinh cũ
    ghép hai nguồn nên ra "11 học phần bắt buộc, tương ứng 14 tín chỉ" trong khi
    danh sách kèm theo cộng đúng 35 — sai hiển nhiên khi sinh viên tự cộng lại.
    Nên: con số đi kèm danh sách LUÔN cộng từ chính danh sách đó, còn nhãn của
    tài liệu chỉ nêu riêng khi khác, kèm giải thích vì sao khác.
    """
    core = [c for c in rs if c["nhom"] == "Bắt buộc" and not c["he"]]
    tong_core = sum(c["tin_chi"] for c in core)
    parts = [f"Học kỳ {k} ({_nam_ky(k)}) ngành {lbl} có {len(core)} học phần "
             f"bắt buộc, cộng lại {tong_core:g} tín chỉ: {_detail(core)}."]

    # Định hướng chuyên ngành: các nhánh LOẠI TRỪ NHAU, sinh viên chỉ theo một.
    dh = {}
    for c in rs:
        if c["nhom"] == "Định hướng chuyên ngành" and c["dinh_huong"]:
            dh.setdefault(c["dinh_huong"], []).append(c)
    if dh:
        ten = "; ".join(f"{t} ({sum(x['tin_chi'] for x in cs):g} tín chỉ, "
                        f"{len(cs)} học phần)" for t, cs in dh.items())
        parts.append(f"Ngoài ra kỳ này có {len(dh)} định hướng chuyên ngành để chọn "
                     f"MỘT: {ten}.")

    ks = [c for c in rs if c["he"] == "Kỹ sư"]
    if ks:
        parts.append(f"Riêng hệ kỹ sư học thêm {len(ks)} học phần "
                     f"({sum(c['tin_chi'] for c in ks):g} tín chỉ).")

    if h.get("bat_buoc_khong_khop") and h.get("bat_buoc") is not None:
        parts.append(f"Lưu ý: kế hoạch đào tạo ghi ở dòng \"Bắt buộc\" là "
                     f"{h['bat_buoc']:g} tín chỉ — con số này đã gộp cả phần định "
                     f"hướng hoặc phần dành riêng cho hệ kỹ sư, nên em căn theo "
                     f"tổng {h['tong']:g} tín chỉ của cả học kỳ.")
    return " ".join(parts)


# --------------------------------------------------------------- mức trung bình
def gen_medium(courses, programs):
    out = []
    for p in programs:
        lbl, rows = _label(p), _rows_of(courses, p)
        nam_max = max(h["hoc_ky"] for h in p["hoc_ky"]) // KY_MOI_NAM

        for nam in range(1, nam_max + 1):
            kys = [k for k in ((nam - 1) * KY_MOI_NAM + 1, nam * KY_MOI_NAM)]
            hs = [_ky_of(p, k) for k in kys]
            hs = [h for h in hs if h]
            if not hs:
                continue
            tong = sum(h["tong"] for h in hs)
            chi_tiet = " + ".join(f"học kỳ {h['hoc_ky']}: {h['tong']:g}" for h in hs)
            key = f"{p['source']}|nam{nam}"
            out.append((
                PH.question("tin_chi_nam", key, nam=nam, lbl=lbl),
                f"Năm thứ {nam} của chương trình {lbl} khoá {p['khoa_hoc']} gồm {chi_tiet}, "
                f"tổng cộng {tong:g} tín chỉ. Toàn khoá là {_tong_str(p)}. "
                + PH.closing(key)))

        for h in p["hoc_ky"]:
            k = h["hoc_ky"]
            rs = _rows_of(courses, p, k)
            if not rs:
                continue
            key = f"{p['source']}|bb{k}"
            out.append((
                PH.question("mon_bat_buoc_ky", key, hk=k, lbl=lbl, nam_ky=_nam_ky(k)),
                _bat_buoc_cau(h, rs, k, lbl) + " " + PH.closing(key)))

            forms = {}
            for c in rs:
                if c.get("ktdg"):
                    forms.setdefault(c["ktdg"], []).append(c)
            for form, cs in forms.items():
                key = f"{p['source']}|kt{k}{form}"
                out.append((
                    PH.question("ktdg_ky", key, hk=k, lbl=lbl, form=form.lower()),
                    f"Ở học kỳ {k} ngành {lbl}, có {len(cs)} học phần đánh giá bằng "
                    f"{form.lower()}: {_detail(cs)}."))

            key = f"{p['source']}|tc{k}"
            out.append((
                PH.question("tin_chi_ky", key, hk=k, lbl=lbl, nam_ky=_nam_ky(k)),
                PH.opening("tin_chi_ky", key, hk=k, lbl=lbl, nam_ky=_nam_ky(k),
                           hk_tc=f"{h['tong']:g}")
                + (f", trong đó {h['bat_buoc']:g} tín chỉ bắt buộc" if "bat_buoc" in h else "")
                + (f" và {h['tu_chon']:g} tín chỉ tự chọn" if h.get("tu_chon") else "")
                + f". Toàn khoá ngành này là {_tong_str(p)}. " + PH.closing(key)))

            key = f"{p['source']}|mk{k}"
            out.append((
                PH.question("mon_ky", key, hk=k, lbl=lbl, nam_ky=_nam_ky(k)),
                PH.opening("mon_ky", key, hk=k, lbl=lbl, nam_ky=_nam_ky(k),
                           n=len(rs), hk_tc=f"{h['tong']:g}")
                + f": {_detail(rs)}."))

            tuchon = [c for c in rs if c["nhom"] == "Tự chọn"]
            if tuchon:
                key = f"{p['source']}|tuchon{k}"
                out.append((
                    PH.question("mon_tu_chon_ky", key, hk=k, lbl=lbl),
                    f"Học kỳ {k} ngành {lbl} yêu cầu {h.get('tu_chon', 0):g} tín chỉ tự chọn. "
                    f"Em chọn trong {len(tuchon)} học phần sau: {_detail(tuchon)}. "
                    f"Chỉ cần đủ số tín chỉ yêu cầu, không phải học hết."))
    return out


# ---------------------------------------------------------------------- mức khó
def gen_hard(courses, programs):
    out = []
    for p in programs:
        lbl, rows = _label(p), _rows_of(courses, p)
        bb = [c for c in rows if c["nhom"] == "Bắt buộc"]
        tc = [c for c in rows if c["nhom"] == "Tự chọn"]
        dh = [c for c in rows if c["nhom"] == "Định hướng chuyên ngành"]
        tc_req = sum(h.get("tu_chon", 0) for h in p["hoc_ky"])

        out.append((
            f"Ngành {lbl} có bao nhiêu tín chỉ tự chọn trên tổng số?",
            f"Chương trình {lbl} yêu cầu {tc_req:g} tín chỉ tự chọn trên tổng "
            f"{_tong_str(p)}. Nhà trường liệt kê {len(tc)} học phần tự chọn để em chọn, "
            f"chỉ cần tích lũy đủ {tc_req:g} tín chỉ chứ không phải học hết. Phần còn lại "
            f"là {len(bb)} học phần bắt buộc"
            + (f", cùng {len(dh)} học phần thuộc các định hướng chuyên ngành mà em "
               f"chỉ theo một" if dh else "") + "."))

        nam_max = max(h["hoc_ky"] for h in p["hoc_ky"]) // KY_MOI_NAM
        for nam in range(1, nam_max + 1):
            hs = [h for h in p["hoc_ky"] if (h["hoc_ky"] - 1) // KY_MOI_NAM + 1 <= nam]
            luy_ke = sum(h["tong"] for h in hs)
            con_lai = p["tong_tin_chi"] - luy_ke
            cong_don = ", ".join("kỳ {}: {:g}".format(h["hoc_ky"], h["tong"]) for h in hs)
            key = f"{p['source']}|lk{nam}"
            out.append((
                PH.question("luy_ke_nam", key, nam=nam, lbl=lbl),
                f"Hết năm thứ {nam}, sinh viên ngành {lbl} tích lũy được {luy_ke:g} tín chỉ "
                f"(cộng dồn {cong_don}). Còn lại {con_lai:g} tín chỉ nữa mới đủ "
                f"{p['tong_tin_chi']:g} tín chỉ toàn khoá."))

        cnt = {}
        for c in rows:
            cnt[c["tin_chi"]] = cnt.get(c["tin_chi"], 0) + 1
        phan_bo = ", ".join(f"{n} học phần {tc_:g} tín chỉ"
                            for tc_, n in sorted(cnt.items()))
        nhieu_nhat = max(p["hoc_ky"], key=lambda h: len(_rows_of(courses, p, h["hoc_ky"])))
        out.append((
            f"Học phần của ngành {lbl} phân bố theo số tín chỉ như thế nào?",
            f"Chương trình {lbl} có {len(rows)} học phần, phân bố: {phan_bo}. "
            f"Học kỳ có nhiều học phần nhất là học kỳ {nhieu_nhat['hoc_ky']} với "
            f"{len(_rows_of(courses, p, nhieu_nhat['hoc_ky']))} học phần."))

        # học phần nặng nhất / có tiên quyết
        nang = max(rows, key=lambda c: c["tin_chi"])
        nang_all = [c for c in rows if c["tin_chi"] == nang["tin_chi"]]
        out.append((
            f"Học phần nào của ngành {lbl} có nhiều tín chỉ nhất?",
            f"Trong chương trình {lbl}, học phần nhiều tín chỉ nhất là {nang['tin_chi']:g} "
            f"tín chỉ, gồm {len(nang_all)} học phần: {_detail(nang_all)}. Đây là các học phần "
            f"chiếm trọng số lớn khi tính điểm trung bình, em nên ưu tiên đầu tư."))

        tq = [c for c in rows if c.get("hptq")]
        out.append((
            f"Ngành {lbl} có học phần nào yêu cầu học phần tiên quyết không?",
            (f"Chương trình {lbl} có {len(tq)} học phần ghi học phần tiên quyết: "
             + "; ".join(f"{c['ten_hp']} (tiên quyết: {c['hptq']})" for c in tq) + "."
             if tq else
             f"Trong kế hoạch đào tạo {lbl} khoá {p['khoa_hoc']}, cột học phần tiên quyết "
             f"không ghi ràng buộc nào, nghĩa là các học phần không bị chặn đăng ký theo "
             f"môn học trước. Tuy nhiên em vẫn nên học đúng thứ tự kế hoạch để theo kịp "
             f"kiến thức nền.")))

        # năm học nặng nhất
        by_year = {}
        for h in p["hoc_ky"]:
            y = (h["hoc_ky"] - 1) // KY_MOI_NAM + 1
            by_year[y] = by_year.get(y, 0) + h["tong"]
        y_max = max(by_year, key=by_year.get)
        y_desc = ", ".join(f"năm {y}: {t:g} tín chỉ" for y, t in sorted(by_year.items()))
        out.append((
            f"Năm học nào của ngành {lbl} nặng nhất?",
            f"Phân bổ khối lượng theo năm của ngành {lbl}: {y_desc}. Năm thứ {y_max} nặng "
            f"nhất với {by_year[y_max]:g} tín chỉ. Em nên hạn chế đăng ký thêm học phần "
            f"ngoài kế hoạch trong năm này."))

        # so sánh một học kỳ với mặt bằng chung
        tb_ky = sum(h["tong"] for h in p["hoc_ky"]) / len(p["hoc_ky"])
        for h in p["hoc_ky"]:
            k = h["hoc_ky"]
            chenh = h["tong"] - tb_ky
            nhan_xet = ("nặng hơn mức trung bình" if chenh > 1 else
                        "nhẹ hơn mức trung bình" if chenh < -1 else
                        "xấp xỉ mức trung bình")
            key = f"{p['source']}|nn{k}"
            out.append((
                PH.question("ky_nang_nhe", key, hk=k, lbl=lbl),
                f"Học kỳ {k} ({_nam_ky(k)}) ngành {lbl} có {h['tong']:g} tín chỉ, trong khi "
                f"trung bình mỗi kỳ của chương trình là {tb_ky:.1f} tín chỉ — tức {nhan_xet} "
                f"({chenh:+.1f} tín chỉ). Toàn khoá gồm {_tong_str(p)} trải trên "
                f"{p['so_hoc_ky']} học kỳ."))

        # phân bố theo hình thức đánh giá, kèm danh sách
        forms = {}
        for c in rows:
            if c.get("ktdg"):
                forms.setdefault(c["ktdg"], []).append(c)
        for form, cs in forms.items():
            out.append((
                f"Ngành {lbl} có bao nhiêu học phần đánh giá bằng {form.lower()}?",
                f"Chương trình {lbl} có {len(cs)}/{len(rows)} học phần đánh giá bằng "
                f"{form.lower()}, tổng {sum(c['tin_chi'] for c in cs):g} tín chỉ: "
                f"{_names(cs)}."))

    # so sánh từng cặp ngành theo học kỳ
    for a, b in itertools.combinations(programs, 2):
        la, lb = _label(a), _label(b)
        for k in range(1, min(a["so_hoc_ky"], b["so_hoc_ky"]) + 1):
            ra = {c["ten_hp"] for c in _rows_of(courses, a, k)}
            rb = {c["ten_hp"] for c in _rows_of(courses, b, k)}
            if not ra or not rb:
                continue
            ha, hb = _ky_of(a, k), _ky_of(b, k)
            key = f"{a['source']}|{b['source']}|k{k}"
            out.append((
                PH.question("khac_ky", key, hk=k, la=la, lb=lb),
                f"Học kỳ {k} ({_nam_ky(k)}): ngành {la} có {ha['tong']:g} tín chỉ, ngành "
                f"{lb} có {hb['tong']:g} tín chỉ. Hai ngành cùng học {len(ra & rb)} học phần"
                + (f" ({', '.join(sorted(ra & rb)[:5])})" if ra & rb else "")
                + (f". Riêng {la} học thêm: {', '.join(sorted(ra - rb)[:5])}" if ra - rb else "")
                + (f". Riêng {lb} học thêm: {', '.join(sorted(rb - ra)[:5])}" if rb - ra else "")
                + "."))

    # so sánh tổng thể từng cặp ngành
    for a, b in itertools.combinations(programs, 2):
        la, lb = _label(a), _label(b)
        ra = {c["ten_hp"] for c in _rows_of(courses, a)}
        rb = {c["ten_hp"] for c in _rows_of(courses, b)}
        chung, rieng_a, rieng_b = ra & rb, ra - rb, rb - ra
        key = f"{a['source']}|{b['source']}|ss"
        out.append((
            PH.question("so_sanh_nganh", key, la=la, lb=lb),
            f"Hai chương trình có {len(chung)} học phần trùng nhau. Riêng {la} có "
            f"{len(rieng_a)} học phần mà {lb} không có"
            + (f", ví dụ: {', '.join(sorted(rieng_a)[:6])}" if rieng_a else "")
            + f". Ngược lại {lb} có {len(rieng_b)} học phần riêng"
            + (f", ví dụ: {', '.join(sorted(rieng_b)[:6])}" if rieng_b else "")
            + f". Về khối lượng, {la} là {a['tong_tin_chi']:g} tín chỉ còn {lb} là "
            f"{b['tong_tin_chi']:g} tín chỉ."))
        out.append((
            PH.question("nang_hon", f"{a['source']}|{b['source']}|nh", la=la, lb=lb),
            f"Xét khối lượng tín chỉ, {la} có {a['tong_tin_chi']:g} tín chỉ và {lb} có "
            f"{b['tong_tin_chi']:g} tín chỉ"
            + (" — hai ngành bằng nhau về tổng khối lượng."
               if a["tong_tin_chi"] == b["tong_tin_chi"] else
               f" — {(la if a['tong_tin_chi'] > b['tong_tin_chi'] else lb)} nặng hơn "
               f"{abs(a['tong_tin_chi'] - b['tong_tin_chi']):g} tín chỉ.")
            + f" Số học phần lần lượt là {len(_rows_of(courses, a))} và "
            f"{len(_rows_of(courses, b))}. Em nên chọn theo định hướng nghề nghiệp "
            f"chứ không chỉ theo khối lượng."))
    return out


# ----------------------------------------------------- mức liên kết văn bản
# (khoá tra trích dẫn, mẫu câu hỏi, mẫu đáp án)
CROSS = [
    (("3.Quy định về CĐR", "Điều 3"),
     "Em học ngành {lbl}, muốn tốt nghiệp thì ngoài {tong} còn cần chuẩn ngoại ngữ gì?",
     "Về khối lượng học tập, kế hoạch đào tạo {lbl} khoá {kh} yêu cầu {tong}. Nhưng đủ "
     "tín chỉ mới là một điều kiện. {quote} Vậy em cần song song: hoàn thành các học phần "
     "trong kế hoạch đào tạo, và có minh chứng đạt chuẩn ngoại ngữ trước khi xét tốt nghiệp."),

    (("3.Quy định về CĐR", "Điều 6"),
     "Ngành {lbl} có phải đạt chuẩn tin học không?",
     "Có. Kế hoạch đào tạo {lbl} quy định khối lượng {tong}, còn chuẩn tin học nằm ở văn "
     "bản riêng. {quote} Đây là điều kiện độc lập với số tín chỉ trong kế hoạch đào tạo."),

    (("3.Quy định về CĐR", "Điều 4"),
     "18 tín chỉ ngoại ngữ có nằm trong {tong} của ngành {lbl} không?",
     "Kế hoạch đào tạo {lbl} khoá {kh} có tổng {tong}, gồm các học phần chuyên môn theo "
     "từng học kỳ. Chương trình ngoại ngữ được quy định ở văn bản khác. {quote} Em đối "
     "chiếu bảng học phần từng kỳ của ngành mình: nếu không thấy các học phần ngoại ngữ "
     "trong đó thì phần này học theo lộ trình riêng của Trung tâm Ngoại ngữ - Tin học, "
     "và em nên hỏi Phòng Quản lý đào tạo cách tính vào khối lượng tốt nghiệp."),

    (("3.Quy định về CĐR", "Điều 5"),
     "Em có chứng chỉ ngoại ngữ rồi, học ngành {lbl} có được miễn học ngoại ngữ không?",
     "Kế hoạch đào tạo {lbl} không tự quy định việc miễn; điều này theo quy định chuẩn đầu "
     "ra. {quote} Em mang chứng chỉ còn hiệu lực nộp ngay khi nhập học để được xét miễn, "
     "phần thời gian tiết kiệm được dành cho {tong} chuyên môn của ngành."),

    (("1.quy chế đào tạo", "Điều 11"),
     "Em học ngành {lbl}, học kỳ {hk} có {hk_tc} tín chỉ, nếu kết quả kém thì bị xử lý sao?",
     "Học kỳ {hk} của ngành {lbl} có {hk_tc} tín chỉ nên đây là kỳ khá nặng. Việc xử lý kết "
     "quả học tập không theo ngành mà theo quy chế chung. {quote} Em theo dõi điểm trung "
     "bình tích lũy sau mỗi kỳ; nếu thấy đuối thì giảm số tín chỉ đăng ký kỳ sau."),

    (("1.quy chế đào tạo", "Điều 7"),
     "Học kỳ {hk} ngành {lbl} có {hk_tc} tín chỉ, em đăng ký học phần thế nào?",
     "Theo kế hoạch đào tạo {lbl}, học kỳ {hk} ({nam_ky}) có {hk_tc} tín chỉ. Việc đăng ký "
     "thực hiện theo quy chế đào tạo. {quote} Em bám kế hoạch chuẩn của ngành để không bị "
     "lệch tiến độ so với {tong} toàn khoá."),

    (("1.quy chế đào tạo", "Điều 2"),
     "Ngành {lbl} học mấy năm và tối đa được kéo dài bao lâu?",
     "Kế hoạch đào tạo {lbl} khoá {kh} thiết kế {so_ky} học kỳ, tức {so_nam} năm, tổng "
     "{tong}. Thời gian tối đa được phép kéo dài theo quy chế. {quote} Em cần hoàn thành "
     "trong giới hạn đó, nếu không sẽ thuộc diện bị buộc thôi học."),

    (("1.quy chế đào tạo", "Điều 9"),
     "Học phần ngành {lbl} được chấm điểm như thế nào?",
     "Kế hoạch đào tạo {lbl} ghi rõ hình thức đánh giá của từng học phần (trắc nghiệm, tự "
     "luận, thực hành, báo cáo, bảo vệ). Cách tính điểm thì theo quy chế. {quote} Em xem "
     "cột hình thức đánh giá trong kế hoạch đào tạo của ngành để biết từng môn thi kiểu gì."),

    (("1.quy chế đào tạo", "Điều 13"),
     "Em chuyển từ ngành khác sang ngành {lbl} thì các môn đã học có được công nhận không?",
     "Chương trình {lbl} gồm {tong} với {so_hp} học phần. Việc công nhận môn đã học theo "
     "quy chế đào tạo. {quote} Em nộp bảng điểm cũ cho Phòng Quản lý đào tạo để đối chiếu "
     "với danh mục học phần của ngành {lbl}."),

    (("1.quy chế đào tạo", "Điều 10"),
     "Ngành {lbl} tính điểm trung bình học kỳ và năm học ra sao?",
     "Mỗi học kỳ của ngành {lbl} có khối lượng khác nhau (nặng nhất là học kỳ {hk} với "
     "{hk_tc} tín chỉ), nên số tín chỉ dùng làm trọng số cũng khác nhau. {quote} Vì vậy "
     "điểm ở các kỳ nặng ảnh hưởng nhiều hơn tới điểm trung bình tích lũy của em."),

    (("4.Quy định về học ph", "Điều 4"),
     "Học kỳ {hk} ngành {lbl} có {hk_tc} tín chỉ, em phải nộp học phí thế nào?",
     "Theo kế hoạch đào tạo {lbl}, học kỳ {hk} có {hk_tc} tín chỉ — học phí kỳ này tính "
     "theo số tín chỉ đăng ký nên cũng cao tương ứng. {quote} Em chuẩn bị tài chính sớm cho "
     "các kỳ nặng tín chỉ."),

    (("4.Quy định về học ph", "Điều 5"),
     "Em học ngành {lbl} mà chưa nộp học phí kỳ {hk} thì bị ảnh hưởng gì?",
     "Học kỳ {hk} của ngành {lbl} có {hk_tc} tín chỉ, nghĩa là khá nhiều học phần sẽ bị ảnh "
     "hưởng nếu em nợ học phí. {quote} Em nên làm đơn xin gia hạn trước hạn thay vì để quá "
     "hạn rồi bị khoá quyền dự thi."),

    (("4.Quy định về học ph", "Điều 3"),
     "Em trượt một môn ở học kỳ {hk} ngành {lbl} thì học lại tốn thêm bao nhiêu?",
     "Học kỳ {hk} ngành {lbl} có {hk_tc} tín chỉ; nếu trượt, em phải học lại đúng số tín chỉ "
     "của học phần đó. {quote} Em xem số tín chỉ của học phần trong kế hoạch đào tạo rồi "
     "nhân với đơn giá học lại để ước tính."),

    (("2.Quy định đào tạo t", "Điều 15"),
     "Học phần của ngành {lbl} học trực tuyến có được công nhận tín chỉ không?",
     "Kế hoạch đào tạo {lbl} quy định {tong} nhưng không quy định hình thức dạy học; việc "
     "công nhận tín chỉ trực tuyến theo văn bản riêng. {quote} Em xem thông báo từng học kỳ "
     "để biết học phần nào của ngành mình được tổ chức trực tuyến."),

    (("2.Quy định đào tạo t", "Điều 11"),
     "Ngành {lbl} có được học trực tuyến toàn bộ không?",
     "Chương trình {lbl} gồm {so_hp} học phần, trong đó nhiều học phần thực hành, đồ án nên "
     "khó tổ chức hoàn toàn trực tuyến. Quy định cụ thể như sau. {quote} Em đối chiếu hình "
     "thức đánh giá từng học phần trong kế hoạch đào tạo để hình dung."),

    (("1.quy chế đào tạo", "Điều 6"),
     "Kế hoạch học tập học kỳ {hk} ngành {lbl} được xây dựng thế nào?",
     "Học kỳ {hk} ({nam_ky}) của ngành {lbl} có {hk_tc} tín chỉ theo kế hoạch đào tạo khoá "
     "{kh}. Cách Nhà trường lập và công bố kế hoạch giảng dạy - học tập được quy chế quy "
     "định. {quote} Em bám kế hoạch chuẩn này để không lệch tiến độ."),

    (("1.quy chế đào tạo", "Điều 8"),
     "Học kỳ {hk} ngành {lbl} tổ chức giảng dạy ra sao?",
     "Theo kế hoạch đào tạo {lbl}, học kỳ {hk} có {hk_tc} tín chỉ. Việc tổ chức giảng dạy "
     "và học tập theo quy chế chung. {quote} Em theo dõi thời khoá biểu từng kỳ do Phòng "
     "Quản lý đào tạo công bố."),

    (("1.quy chế đào tạo", "Điều 20"),
     "Em gian lận thi ở học kỳ {hk} ngành {lbl} thì bị xử lý thế nào?",
     "Học kỳ {hk} ngành {lbl} có {hk_tc} tín chỉ, nếu bị xử lý vi phạm thì toàn bộ kết quả "
     "kỳ này có thể bị ảnh hưởng. Quy chế quy định rõ. {quote} Em tuyệt đối không vi phạm "
     "quy chế thi, vì hậu quả nặng hơn nhiều so với việc trượt một học phần."),

    (("1.quy chế đào tạo", "Điều 12"),
     "Ngành {lbl} xử lý kết quả học tập theo tín chỉ hay niên chế?",
     "Kế hoạch đào tạo {lbl} khoá {kh} được xây dựng theo tín chỉ, tổng {tong} chia thành "
     "{so_ky} học kỳ. Quy chế có quy định riêng cho hình thức niên chế. {quote} Em học theo "
     "tín chỉ thì áp dụng điều khoản xử lý kết quả theo tín chỉ."),

    (("3.Quy định về CĐR", "Điều 7"),
     "Ngành {lbl} học tin học bao nhiêu tín chỉ?",
     "Kế hoạch đào tạo {lbl} khoá {kh} có tổng {tong} gồm các học phần chuyên môn. Chương "
     "trình tin học được quy định ở văn bản riêng. {quote} Em đối chiếu bảng học phần của "
     "ngành mình để xem học phần tin học nằm ở kỳ nào."),

    (("3.Quy định về CĐR", "Điều 8"),
     "Em học ngành {lbl}, có chứng chỉ MOS thì được miễn tin học không?",
     "Kế hoạch đào tạo {lbl} không quy định việc miễn học phần; việc này theo quy định "
     "chuẩn đầu ra. {quote} Em nộp chứng chỉ ngay khi nhập học để được xét, thời gian tiết "
     "kiệm dành cho {tong} chuyên môn."),

    (("2.Quy định đào tạo t", "Điều 6"),
     "Học liệu trực tuyến cho học phần ngành {lbl} phải đạt yêu cầu gì?",
     "Chương trình {lbl} có {so_hp} học phần; học phần nào tổ chức trực tuyến thì học liệu "
     "phải theo chuẩn riêng. {quote} Nếu học liệu môn nào chưa đạt, em phản ánh qua kênh "
     "tiếp nhận ý kiến của Nhà trường."),

    (("4.Quy định về học ph", "Điều 2"),
     "Học phí ngành {lbl} tính theo tín chỉ hay theo kỳ?",
     "Kế hoạch đào tạo {lbl} chia {tong} thành {so_ky} học kỳ với khối lượng khác nhau "
     "từng kỳ, nên số tiền mỗi kỳ cũng khác nhau. {quote} Em xem số tín chỉ của kỳ mình "
     "đăng ký trong kế hoạch đào tạo để ước tính học phí."),

    (("2.Quy định đào tạo t", "Điều 18"),
     "Học kỳ {hk} ngành {lbl} nếu học trực tuyến đồng bộ thì em cần chuẩn bị gì?",
     "Học kỳ {hk} ({nam_ky}) ngành {lbl} có {hk_tc} tín chỉ. Khi học phần được tổ chức trực "
     "tuyến đồng bộ, Nhà trường quy định như sau. {quote} Em bảo đảm thiết bị và đường "
     "truyền ổn định để không bị tính vắng mặt."),

    (("1.quy chế đào tạo", "Điều 22"),
     "Em xem kết quả học tập học kỳ {hk} ngành {lbl} ở đâu?",
     "Học kỳ {hk} ngành {lbl} có {hk_tc} tín chỉ, điểm của từng học phần trong kỳ này được "
     "Nhà trường lưu trữ và công bố theo quy chế. {quote} Em đăng nhập hệ thống của Trường "
     "để tra cứu, nếu thấy sai sót thì phản ánh sớm với Phòng Quản lý đào tạo."),

    (("6.Luật giáo dục đại", "Điều 8"),
     "Học xong {tong} của ngành {lbl} thì em được cấp bằng gì?",
     "Kế hoạch đào tạo {lbl} khoá {kh} yêu cầu {tong} trong {so_ky} học kỳ. Về văn bằng, "
     "Luật Giáo dục đại học quy định. {quote} Em lưu ý chương trình của ngành có thể có hai "
     "mức tốt nghiệp khác nhau về khối lượng, nên hỏi rõ khoa để chọn đúng lộ trình."),
]


def gen_cross(courses, programs, quotes: Quotes):
    out, missing = [], []
    for (hint, dieu), q_tpl, a_tpl in CROSS:
        quote, ref = quotes.get(hint, dieu)
        if not quote:
            missing.append(f"{hint} {dieu}")
            continue
        for p in programs:
            rows = _rows_of(courses, p)
            heavy = max(p["hoc_ky"], key=lambda h: h["tong"])
            # Chỉ trải theo học kỳ khi CÂU HỎI có {hk}. Nếu {hk} chỉ nằm ở đáp án
            # thì 8 học kỳ sinh ra 8 câu hỏi y hệt nhau, bị lọc trùng gần hết.
            kys = ([h["hoc_ky"] for h in p["hoc_ky"]]
                   if "{hk}" in q_tpl else [heavy["hoc_ky"]])
            for k in kys:
                h = _ky_of(p, k)
                if not h:
                    continue
                f = {
                    "lbl": _label(p), "tong": _tong_str(p), "kh": p["khoa_hoc"],
                    "so_ky": p["so_hoc_ky"], "so_nam": p["so_hoc_ky"] // KY_MOI_NAM,
                    "so_hp": len(rows), "hk": k, "hk_tc": f"{h['tong']:g}",
                    "nam_ky": _nam_ky(k), "quote": quote,
                }
                out.append((q_tpl.format(**f), a_tpl.format(**f), ref))
    if missing:
        print(f"   ⚠️  không tra được trích dẫn cho: {', '.join(missing)}")
    return out


# ---------------------------------------------------------------------- chạy
def _take(pairs, n, seed):
    """Lấy n mẫu, xáo trộn có kiểm soát để không thiên về một ngành."""
    pairs = list(pairs)
    random.Random(seed).shuffle(pairs)
    return pairs[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1000)
    ap.add_argument("--out", default="")
    ap.add_argument("--seed", type=int, default=20260811)
    args = ap.parse_args()

    courses, programs = CI.load()
    if not programs:
        print("❌ Chưa có dữ liệu kế hoạch đào tạo. Chạy trước curriculum.py")
        sys.exit(1)
    quotes = Quotes()

    want = {"tb": round(args.target * 0.20),
            "kho": round(args.target * 0.30),
            "lien": round(args.target * 0.50)}

    pools = {
        "tb": gen_medium(courses, programs),
        "kho": gen_hard(courses, programs),
        "lien": gen_cross(courses, programs, quotes),
    }

    rows, i, seen = [], 0, set()
    for key in ("tb", "kho", "lien"):
        picked, n = _take(pools[key], want[key], args.seed), 0
        for item in picked:
            q, a = item[0], item[1]
            ref = item[2] if len(item) > 2 else ""
            k = " ".join(q.lower().split())
            if k in seen:
                continue
            seen.add(k)
            i += 1
            n += 1
            rows.append({"id": str(i), "category": CAT[key], "question": q, "answer": a,
                         "source_refs": ref, "notes": "",
                         "origin": "gen_qa_advanced.py"})
        print(f"  {n:5d}/{want[key]:<5d} {CAT[key]}   (kho mẫu có {len(pools[key])})")

    out = pathlib.Path(args.out) if args.out else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    words = [len(r["answer"].split()) for r in rows]
    print(f"\n✅ {len(rows)} cặp Q/A -> {out}")
    print(f"   Đáp án: trung bình {sum(words)//len(words)} từ, "
          f"ngắn nhất {min(words)}, dài nhất {max(words)}")


if __name__ == "__main__":
    main()
