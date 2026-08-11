"""Bóc kế hoạch đào tạo (.docx) thành DỮ LIỆU CÓ CẤU TRÚC để tra cứu chính xác.

Vì sao cần bước này thay vì chỉ nhúng vector như các văn bản khác:

Kho tri thức có hai loại dữ liệu khác hẳn nhau về bản chất.
  - Quy chế, quy định: văn xuôi. Hỏi "cảnh báo học tập khi nào" thì câu trả lời
    nằm gọn trong một đoạn -> tìm theo ngữ nghĩa (vector) là đúng công cụ.
  - Kế hoạch đào tạo: BẢNG. Hỏi "ngành này tổng bao nhiêu tín chỉ" thì câu trả
    lời KHÔNG nằm ở đoạn nào cả — phải CỘNG 8 học kỳ lại. Vector không cộng được,
    và mô hình ngôn ngữ 3B tự cộng thì sẽ bịa (đã đo: nó trả lời "150 tín chỉ"
    trong khi không có tài liệu nào nói vậy).

Nên tài liệu dạng bảng được bóc thành bản ghi có cấu trúc, mỗi học phần một dòng,
rồi truy vấn bằng phép lọc/cộng chính xác. Kết quả tra cứu được chèn vào ngữ cảnh
như DỮ KIỆN ĐÃ TRA CỨU để mô hình chỉ việc diễn đạt, không phải tự suy ra con số.

Chạy:
    conda activate test
    python src/Phase1-DataPreprocessing/curriculum.py          # -> data/processed/curriculum.jsonl
"""
from __future__ import annotations
import json
import re
import sys
import pathlib
from typing import Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config

OUT_FILE = config.DATA_PROCESSED / "curriculum.jsonl"
PROGRAMS_FILE = config.DATA_PROCESSED / "curriculum_programs.json"

# Nhận diện tệp kế hoạch đào tạo trong data/raw
CURRICULUM_HINT = re.compile(r"(k\d{2}|ke-hoach|khung.?ch[uư]?[oơ]ng.?tr[iì]nh)", re.IGNORECASE)

# "2(1.6,0.4,4)" -> 2 tín chỉ. Số đầu tiên là tổng tín chỉ, trong ngoặc là phân bổ
# lý thuyết/thực hành/tự học.
_CREDIT_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)")
_SEMESTER_RE = re.compile(r"H[oọ]c\s*k[yỳ]\s*(\d{1,2})", re.IGNORECASE)
_HEADER_CELLS = {"tt", "mã hp", "ma hp", "tên học phần", "ten hoc phan", "số tín chỉ",
                 "so tin chi", "hptq", "ktđg", "ktdg"}
_GROUP_ROWS = {"bắt buộc": "Bắt buộc", "tự chọn": "Tự chọn"}

# Bảng kế hoạch có các NHÁNH LOẠI TRỪ NHAU mà bản bóc đầu tiên làm phẳng hết,
# nên cộng dồn ra số sai. Ví dụ học kỳ 6 ngành KT Nhiệt:
#     | Bắt buộc                               | 14 |   <- phải tích lũy 14
#     |   Tiếng anh kỹ thuật                   |  2 |
#     | 2.1 Chuyên ngành Nhiệt - Năng lượng CT | 12 |   ┐ sinh viên chỉ theo
#     |   (3 học phần, cộng 12)                      │ MỘT trong hai
#     | 2.2 Chuyên ngành Năng lượng Tái tạo    | 12 |   ┘ định hướng
#     |   (4 học phần, cộng 12)
#     | Dành cho hệ đào tạo kỹ sư              |  6 |   <- chỉ hệ kỹ sư học
#     |   Tự chọn                              |  6 |   <- chọn 6 trong 9
#     | Tổng                                   | 20 |
# Cộng phẳng ra 35; đúng phải là 2 + 12 (một định hướng) = 14 bắt buộc, cộng 6 tự
# chọn = 20. Vì vậy mỗi học phần cần mang thêm: thuộc ĐỊNH HƯỚNG nào và thuộc HỆ
# nào, còn số tín chỉ của nhóm thì luôn đọc từ dòng nhãn chứ không cộng dòng con.
_TRACK_RE = re.compile(r"^\s*\d+\.\d+\s*$")            # ô đầu "2.1", "2.2"
# Học phần tự chọn cũng được đánh số "7.1", "7.2" y như dòng định hướng, nên chỉ
# dựa vào ô đầu là nhận nhầm 40 học phần thành dòng phân nhóm (đã đo). Phân biệt
# bằng ô kế: dòng học phần luôn có MÃ HỌC PHẦN 4-6 chữ số ở đó, dòng định hướng
# thì ghi tên định hướng bằng chữ.
_CODE_RE = re.compile(r"^\s*0?\d{4,6}\s*$")
_TRACK_NAME_RE = re.compile(r"^\s*chuyên ngành\b", re.IGNORECASE)
_HE_RE = re.compile(r"dành cho hệ đào tạo\s*(cử nhân|kỹ sư)", re.IGNORECASE)
_HE_LABEL = {"cử nhân": "Cử nhân", "kỹ sư": "Kỹ sư"}


def _num(s: str) -> Optional[float]:
    m = _CREDIT_RE.match((s or "").replace(",", "."))
    return float(m.group(1)) if m else None


def _classify_group(cells: list[str]) -> Optional[tuple]:
    """Nhận diện dòng PHÂN NHÓM. Trả về (loại, tên, số tín chỉ) hoặc None.

    Nhãn nhóm không nằm cố định ở ô đầu: có bảng ghi ['Tự chọn', '2', ''], bảng
    khác lại ghi ['', 'Tự chọn', '6', ''] (ô đầu để trống). Đọc cứng ô đầu là lý
    do 46 dòng "Tự chọn" bị bỏ sót, khiến học phần tự chọn bị gán nhầm "Bắt buộc".
    Nên tìm nhãn ở ô đầu, không thấy thì tìm ở ô thứ hai; số tín chỉ luôn nằm ở ô
    ngay sau ô chứa nhãn.
    """
    for i in (0, 1):
        if i >= len(cells):
            break
        label = cells[i].strip()
        if not label:
            continue
        low = label.lower()
        credit = _num(cells[i + 1]) if i + 1 < len(cells) else None

        if low in _GROUP_ROWS:
            return ("nhom", _GROUP_ROWS[low], credit)
        if _HE_RE.search(low):
            return ("he", _HE_LABEL[_HE_RE.search(low).group(1).lower()], credit)
        # Định hướng chuyên ngành: ô đầu là số mục "2.1", tên nằm ở ô kế tiếp.
        if (i == 0 and _TRACK_RE.match(label) and len(cells) > 1
                and cells[1].strip() and not _CODE_RE.match(cells[1])):
            return ("dinh_huong", cells[1].strip(), _num(cells[2]) if len(cells) > 2 else None)
        if i == 1 and _TRACK_NAME_RE.match(label):
            return ("dinh_huong", label, credit)
        break            # ô đầu có chữ nhưng không khớp -> không phải dòng nhóm
    return None


def _collapse(cells: list[str]) -> list[str]:
    """Gộp các ô TRÙNG LIỀN KỀ do ô bảng bị merge ngang.

    python-docx trả về ô gộp bằng cách lặp lại nội dung ra từng cột, mà số cột bị
    lặp lại khác nhau giữa các bảng: có bảng cột "Số tín chỉ" gộp đôi nên dòng học
    phần thành 7 ô, dòng "Bắt buộc" lại gộp 4 ô đầu. Nếu đọc cứng theo chỉ số cột
    thì lúc đúng lúc sai — đã làm tổng tín chỉ thiếu hẳn 3 học kỳ.

    Sau khi gộp, mọi bảng về cùng một dạng:
        dòng học phần : [TT, Mã HP, Tên học phần, Số tín chỉ, HPTQ, KTĐG]
        dòng nhóm/tổng: [nhãn, số tín chỉ, ...]
    """
    out: list[str] = []
    for c in cells:
        if not out or c != out[-1]:
            out.append(c)
    return out


def _is_header(cells: list[str]) -> bool:
    return sum(1 for c in cells if c.strip().lower() in _HEADER_CELLS) >= 3


def _meta_from_tables(doc) -> dict:
    """Đọc Ngành / Chuyên ngành / Khoa / Loại hình từ các bảng đầu tài liệu."""
    meta = {}
    keys = {"ngành:": "nganh", "chuyên ngành:": "chuyen_nganh",
            "khoa:": "khoa", "loại hình đào tạo:": "loai_hinh"}
    for tbl in doc.tables[:4]:
        for row in tbl.rows:
            for cell in row.cells:
                txt = " ".join(cell.text.split())
                low = txt.lower()
                for k, field in keys.items():
                    if low.startswith(k) and field not in meta:
                        meta[field] = txt[len(k):].strip()
    return meta


def parse_file(path: pathlib.Path) -> list[dict]:
    """Bóc một tệp kế hoạch đào tạo -> danh sách bản ghi học phần."""
    import docx
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from extract import _iter_docx_blocks
    from docx.table import Table

    doc = docx.Document(str(path))
    meta = _meta_from_tables(doc)
    khoa_hoc = None
    m = re.search(r"KHO[AÁ]\s*(\d+)", "\n".join(p.text for p in doc.paragraphs), re.IGNORECASE)
    if m:
        khoa_hoc = f"K{m.group(1)}"

    records, hoc_ky, group = [], None, "Bắt buộc"
    dinh_huong, he = "", ""
    totals: dict[int, dict] = {}
    for block in _iter_docx_blocks(doc):
        if not isinstance(block, Table):
            sm = _SEMESTER_RE.search(block.text or "")
            if sm:
                hoc_ky = int(sm.group(1))
                group, dinh_huong, he = "Bắt buộc", "", ""
            continue
        if hoc_ky is None:
            continue                     # bảng tiêu đề/thông tin chung, chưa vào học kỳ
        for row in block.rows:
            cells = _collapse([" ".join(c.text.split()) for c in row.cells])
            if _is_header(cells):
                continue
            first = cells[0].strip().lower()
            # Hai tệp đặt nhãn "Học kỳ N:" NGAY TRONG bảng chứ không ở đoạn văn.
            if _SEMESTER_RE.match(first):
                hoc_ky = int(_SEMESTER_RE.match(first).group(1))
                group, dinh_huong, he = "Bắt buộc", "", ""
                continue

            kind = _classify_group(cells)
            if kind:
                what, name, n = kind
                slot = totals.setdefault(hoc_ky, {})
                if what == "nhom":
                    # Sang nhóm mới thì thoát khỏi định hướng đang đọc dở, nhưng
                    # GIỮ nguyên hệ: bảng ghi "Dành cho hệ kỹ sư" rồi mới tới
                    # "Tự chọn", tức nhóm tự chọn đó nằm trong phần của hệ kỹ sư.
                    group, dinh_huong = name, ""
                    # Dòng nhãn ghi luôn SỐ TÍN CHỈ PHẢI TÍCH LŨY của nhóm. Với
                    # nhóm tự chọn, số này nhỏ hơn tổng các môn được liệt kê (chọn
                    # 6 trong 9), nên phải lấy ở đây thay vì cộng các dòng con.
                    if n is not None:
                        slot["bat_buoc" if name == "Bắt buộc" else "tu_chon"] = n
                elif what == "he":
                    he, dinh_huong = name, ""
                    if n is not None:
                        slot.setdefault("he", {})[name] = n
                else:                                   # định hướng chuyên ngành
                    dinh_huong, group = name, "Định hướng chuyên ngành"
                    if n is not None:
                        slot.setdefault("dinh_huong", []).append(
                            {"ten": name, "tin_chi": n})
                continue
            if first.startswith(("tổng", "tong")):
                # Học kỳ cuối tách hai hệ, dòng tổng ghi "Tổng: Cử nhân/Kỹ sư | 12/18".
                raw = cells[1] if len(cells) > 1 else ""
                dual = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)", raw)
                slot = totals.setdefault(hoc_ky, {})
                if dual:
                    slot["tong_cu_nhan"] = float(dual.group(1).replace(",", "."))
                    slot["tong_ky_su"] = float(dual.group(2).replace(",", "."))
                    slot["tong"] = slot["tong_cu_nhan"]
                else:
                    n = _num(raw)
                    if n is not None:
                        slot["tong"] = n
                continue
            if len(cells) < 4 or not cells[1].strip():
                continue                  # dòng trống hoặc thiếu mã học phần
            tin_chi = _num(cells[3])
            if tin_chi is None:
                continue
            records.append({
                "source": path.name,
                "khoa_hoc": khoa_hoc,
                "nganh": meta.get("nganh", ""),
                "chuyen_nganh": meta.get("chuyen_nganh", ""),
                "khoa": meta.get("khoa", ""),
                "loai_hinh": meta.get("loai_hinh", ""),
                "hoc_ky": hoc_ky,
                "nhom": group,
                "dinh_huong": dinh_huong,     # rỗng nếu môn không thuộc định hướng nào
                "he": he,                     # rỗng = cả hai hệ; "Kỹ sư"/"Cử nhân"
                "ma_hp": cells[1].strip(),
                "ten_hp": cells[2].strip(),
                "tin_chi": tin_chi,
                "tin_chi_raw": cells[3].strip(),
                "hptq": cells[4].strip() if len(cells) > 4 else "",
                "ktdg": cells[5].strip() if len(cells) > 5 else "",
            })

    # Có bảng thiếu hẳn dòng "Tổng" (soạn thiếu trong tệp gốc). Suy ra từ hai nhóm
    # thay vì bỏ qua cả học kỳ — bỏ qua thì tổng tín chỉ toàn khoá bị hụt.
    for k, v in totals.items():
        if "tong" not in v:
            v["tong"] = v.get("bat_buoc", 0) + v.get("tu_chon", 0)
            v["tong_suy_ra"] = True

    # Nhãn "Bắt buộc" KHÔNG cùng nghĩa giữa các tệp: có tệp ghi 15 = 9 môn lõi + 6
    # của khối kỹ sư, tệp khác ghi 14 = 2 môn lõi + 12 của một định hướng, lại có
    # tệp tự cộng lệch (ghi 19 trong khi 5 môn liệt kê cộng đúng 18). Không có
    # cách suy ra thống nhất, nên ghi CẢ HAI con số và đánh dấu chỗ vênh; bộ sinh
    # Q/A phải tránh khẳng định "học kỳ X có N tín chỉ bắt buộc" ở những kỳ này.
    for k, v in totals.items():
        liet_ke = sum(r["tin_chi"] for r in records
                      if r["hoc_ky"] == k and r["nhom"] == "Bắt buộc" and not r["he"])
        v["bat_buoc_liet_ke"] = liet_ke
        if v.get("bat_buoc") is not None and abs(liet_ke - v["bat_buoc"]) > 0.01:
            v["bat_buoc_khong_khop"] = True

    program = {
        "source": path.name,
        "khoa_hoc": khoa_hoc,
        "nganh": meta.get("nganh", ""),
        "chuyen_nganh": meta.get("chuyen_nganh", ""),
        "khoa": meta.get("khoa", ""),
        "loai_hinh": meta.get("loai_hinh", ""),
        "so_hoc_ky": len(totals),
        # Chương trình có học kỳ tách hai hệ nên tổng tín chỉ có hai con số khác
        # nhau; nêu gộp một số duy nhất là sai với một trong hai hệ.
        "tong_tin_chi": sum(v.get("tong", 0) for v in totals.values()),
        "tong_tin_chi_ky_su": sum(v.get("tong_ky_su", v.get("tong", 0))
                                  for v in totals.values()),
        "co_hai_he": any("tong_ky_su" in v for v in totals.values()),
        "hoc_ky": [{"hoc_ky": k, **v} for k, v in sorted(totals.items())],
        "so_hoc_phan": len(records),
    }
    return records, program


def find_files() -> list[pathlib.Path]:
    return sorted(p for p in config.DATA_RAW.iterdir()
                  if p.suffix.lower() == ".docx" and CURRICULUM_HINT.search(p.stem))


def main():
    files = find_files()
    if not files:
        print(f"⚠️  Không thấy tệp kế hoạch đào tạo nào trong {config.DATA_RAW}")
        return

    all_recs, programs = [], []
    for f in files:
        recs, prog = parse_file(f)
        all_recs.extend(recs)
        programs.append(prog)
        name = f"{prog['nganh']} / {prog['chuyen_nganh'] or '(không chuyên ngành)'}"
        print(f"  ✓ {len(recs):3d} học phần | {prog['so_hoc_ky']} kỳ | "
              f"{prog['tong_tin_chi']:g} tín chỉ | {name}")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as fh:
        for r in all_recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    PROGRAMS_FILE.write_text(
        json.dumps(programs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {len(all_recs)} bản ghi học phần -> {OUT_FILE}")
    print(f"✅ {len(programs)} chương trình (tổng tín chỉ theo kỳ) -> {PROGRAMS_FILE}")


if __name__ == "__main__":
    main()
