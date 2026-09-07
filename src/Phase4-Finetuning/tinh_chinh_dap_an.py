"""Viết lại các đáp án DÁN NGUYÊN VĂN thành đáp án có bố cục tư vấn.

VÌ SAO
Bản fine-tune Qwen3-14B kém hơn model gốc vì học đúng thói quen có trong dữ liệu:
1067/3502 đáp án (30%) mở đầu bằng "Theo <văn bản>, quy định như sau:" rồi dán
nguyên văn trung bình 347 từ (nhóm còn lại chỉ 80 từ). Mô hình học lối đó nên khi
chạy thật nó đọc lể tài liệu, dài gấp 2-3 lần và bị cắt cụt giữa câu.

VÌ SAO KHÔNG RÚT GỌN
Đã đo: bảo mô hình "viết lại cho gọn theo lối tư vấn" thì 3/5 mẫu MẤT dữ kiện thật
(một mẫu rơi cả '1,5', '2020', '40', '8') và chỉ giữ 32-67% từ ghép nội dung. Đó
đúng là cách sự cố restyle_qa.py từng làm mất 69.513 từ. Nên ở đây KHÔNG tóm tắt:
chỉ ĐƯA KẾT LUẬN LÊN ĐẦU và sắp lại phần còn lại thành gạch đầu dòng, giữ đủ ý.

CỔNG KIỂM CHỨNG
Dùng lại nguyên các tầng của refine_qa_llm.verify (tín chỉ, mốc ngữ cảnh, mẫu từ
chối, nội dung không phải số), chỉ thay đúng một chỗ: cách so SỐ.

    Đo thực tế trên 8 mẫu: cổng gốc loại 7/8, toàn bộ vì "làm mất số" 1, 2, 3, 23.
    Soi lại ngữ cảnh thì đó là hai loại khác hẳn nhau:
        "1. Chuẩn chương trình đào tạo quy định..."  -> SỐ THỨ TỰ KHOẢN
        "Theo Luật Giáo dục đại học (Điều 23)"       -> SỐ ĐIỀU, dữ kiện thật
    Chuyển khoản thành gạch đầu dòng thì số thứ tự biến mất — đúng và mong muốn.
    Mất số Điều thì hỏng trích dẫn. Vì vậy một con số chỉ được phép biến mất khi
    MỌI lần xuất hiện của nó trong bản gốc đều là số thứ tự khoản.

Cách dùng:
    python src/Phase4-Finetuning/tinh_chinh_dap_an.py --thu 20   # thử 20 mẫu, không ghi
    python src/Phase4-Finetuning/tinh_chinh_dap_an.py            # chạy thật, có sao lưu
"""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Phase3-RAG"))
import refine_qa_llm as R

QA_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "qa"
# Chỉ ba tệp này chứa đáp án dán nguyên văn (đo được: 782 / 58 / 227 dòng).
TEP = ["qa_viu_full.csv", "qa_cau_hoi_thuong_gap.csv", "qa_tu_dong_tu_tai_lieu.csv"]

DAN_RE = re.compile(r"^\s*Theo\b.{0,120}?(quy định như sau|như sau)\s*:", re.I | re.S)

# Ứng viên số thứ tự khoản: "3." hoặc "3)" theo sau là khoảng trắng. KHÔNG tính khi
# đứng sau Điều/khoản/điểm/mục/Chương — "(Điều 23)" khớp hình dạng nhưng là dữ kiện.
_ENUM_CAND_RE = re.compile(
    r"(?<!\d)(?<!Điều )(?<!điều )(?<!khoản )(?<!Khoản )(?<!điểm )(?<!Điểm )"
    r"(?<!mục )(?<!Mục )(?<!chương )(?<!Chương )(\d{1,2})\s*[.)]\s")


def _so_thu_tu(text: str) -> set[str]:
    """Các con số mà MỌI lần xuất hiện trong text đều là SỐ THỨ TỰ KHOẢN.

    Không thể nhận diện bằng ký tự đứng trước: đo thực tế có "Phương thức tổ chức
    đào tạo 1. Đào tạo theo niên chế" — số thứ tự nằm ngay sau chữ của tiêu đề, nên
    quy tắc "phải sau dấu câu" loại oan hàng loạt. Mà nới ra cho phép đứng sau chữ
    thì "không vượt quá 16." lại bị coi là số thứ tự và cho phép đánh rơi số 16.

    Dấu hiệu chắc chắn hơn là DÃY LIÊN TIẾP: số thứ tự khoản luôn chạy 1, 2, 3...
    theo đúng thứ tự xuất hiện. Một con số chỉ được coi là số thứ tự khi nó nối
    đúng vào dãy đang chạy.
    """
    la_stt: dict[str, int] = {}
    mong_doi = 1
    for m in _ENUM_CAND_RE.finditer(text or ""):
        v = int(m.group(1))
        if v == mong_doi:
            la_stt[m.group(1)] = la_stt.get(m.group(1), 0) + 1
            mong_doi += 1
        elif v == 1:                      # dãy mới bắt đầu (sang mục khác)
            la_stt["1"] = la_stt.get("1", 0) + 1
            mong_doi = 2
    tat_ca: dict[str, int] = {}
    for m in R._NUM_RE.finditer(text or ""):
        tat_ca[m.group(0)] = tat_ca.get(m.group(0), 0) + 1
    # Chỉ tha khi SỐ LẦN làm số thứ tự phủ hết mọi lần xuất hiện của con số đó.
    return {s for s, n in tat_ca.items() if la_stt.get(s, 0) >= n}


def kiem_tra(q: str, goc: str, moi: str) -> tuple[bool, str]:
    """Như refine_qa_llm.verify nhưng bỏ qua số thứ tự khoản, và cho gọn bớt đôi chút."""
    if not moi or not moi.strip():
        return False, "bản viết lại rỗng"

    a, b = set(R._facts(goc)), set(R._facts(moi))
    thua = sorted(set(R._NUM_RE.findall(moi)) - (a | set(R._facts(goc))))
    if thua:
        return False, f"thêm số không có trong bản gốc: {thua}"
    # Chỉ tha cho số thứ tự khoản; số Điều, mốc điểm, tín chỉ... vẫn bắt buộc giữ.
    thieu = sorted((a - b) - _so_thu_tu(goc))
    if thieu:
        return False, f"làm mất số: {thieu}"

    if R._credits(goc) != R._credits(moi):
        return False, f"tín chỉ học phần lệch: {R._credits(goc)} -> {R._credits(moi)}"
    mat = R._missing_anchors(goc, moi)
    if mat:
        return False, f"bỏ mất ngữ cảnh: {mat}"
    if R._is_refusal(goc) and not R._is_refusal(moi):
        return False, "mẫu từ chối bị viết thành câu khẳng định"
    # Sắp lại bố cục thì độ dài xê dịch ít; tụt sâu là dấu hiệu đã tóm tắt.
    if len(moi.split()) < 0.75 * len(goc.split()):
        return False, f"ngắn hơn bản gốc quá nhiều ({len(goc.split())} -> {len(moi.split())})"
    thieu_y = R._missing_content(goc, moi)
    if thieu_y:
        return False, f"bỏ mất ý: {thieu_y[:6]}"
    return True, ""


HD = ("Bạn là cố vấn học tập của Trường Đại học Công nghiệp Việt - Hung. Hãy SẮP XẾP "
      "LẠI đáp án dưới đây cho sinh viên dễ đọc. ĐÂY KHÔNG PHẢI việc tóm tắt.\n\n"
      "Bố cục bắt buộc:\n"
      "(1) Câu ĐẦU TIÊN do em tự viết: trả lời thẳng vào câu hỏi, nêu kết luận rõ ràng, "
      "kèm căn cứ dạng 'theo <tên văn bản> (Điều N)'.\n"
      "(2) Sau đó trình bày LẠI ĐẦY ĐỦ nội dung đáp án gốc thành các gạch đầu dòng '-', "
      "mỗi ý một dòng, giữ nguyên mọi chi tiết.\n\n"
      "QUY TẮC TUYỆT ĐỐI:\n"
      "- GIỮ TẤT CẢ: mọi con số, mốc điểm, số tín chỉ, số Điều, tên văn bản, tên học "
      "phần, mọi điều kiện. KHÔNG bỏ bất kỳ ý nào.\n"
      "- KHÔNG thêm con số hay thông tin không có trong đáp án gốc.\n"
      "- Được phép bỏ cụm đưa đẩy 'quy định như sau' và đổi số thứ tự khoản (1. 2. 3.) "
      "thành gạch đầu dòng.\n"
      "- Bản mới phải DÀI TƯƠNG ĐƯƠNG bản gốc.\n"
      "- Chỉ dùng tiếng Việt, xưng hô gọi sinh viên là 'em'.\n\n"
      'Trả về ĐÚNG một JSON: {"answer": "..."}\n\n')


def _lam(tok, model, q: str, a: str, loi: str = "") -> str:
    nhac = (f"\nLẦN TRƯỚC BỊ LOẠI VÌ: {loi}. Hãy sửa đúng chỗ đó.\n" if loi else "")
    p = HD + nhac + f"CÂU HỎI: {q}\n\nĐÁP ÁN GỐC:\n{a}\n\nJSON:"
    out = R.run_batch(tok, model, [p], max_new=1400)[0]
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return ""
    try:
        return str(json.loads(m.group(0)).get("answer", "")).strip()
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu", type=int, default=0, help="chỉ chạy thử N mẫu, không ghi tệp")
    args = ap.parse_args()

    import pandas as pd
    tok, model = R.load_model()

    tong = {"qua": 0, "giu_goc": 0, "xet": 0}
    for ten in TEP:
        p = QA_DIR / ten
        if not p.exists():
            print(f"⚠ không thấy {ten}"); continue
        df = pd.read_csv(p, dtype=str).fillna("")
        idx = [i for i in df.index if DAN_RE.search(str(df.at[i, "answer"]))]
        if args.thu:
            idx = idx[:args.thu]
        print(f"\n=== {ten}: {len(idx)} đáp án cần sắp lại ===")
        t0 = time.time()
        for n, i in enumerate(idx, 1):
            q, a = str(df.at[i, "question"]).strip(), str(df.at[i, "answer"]).strip()
            moi, ly_do = "", ""
            for lan in range(2):            # thử tối đa 2 lần, lần 2 có báo lỗi cũ
                moi = _lam(tok, model, q, a, ly_do)
                ok, ly_do = kiem_tra(q, a, moi)
                if ok:
                    break
            tong["xet"] += 1
            if ok:
                tong["qua"] += 1
                if not args.thu:
                    df.at[i, "answer"] = moi
            else:
                tong["giu_goc"] += 1        # không đạt -> GIỮ NGUYÊN bản gốc
            if n % 25 == 0 or n == len(idx):
                toc = (time.time() - t0) / n
                print(f"   {n}/{len(idx)} | qua {tong['qua']} giữ gốc {tong['giu_goc']} "
                      f"| {toc:.1f}s/mẫu | còn ~{(len(idx)-n)*toc/60:.0f} phút")
            if args.thu:
                print(f"   [{n}] {'✅' if ok else '❌ ' + ly_do[:80]}  "
                      f"{len(a.split())}->{len(moi.split()) if moi else 0} từ")
        if not args.thu:
            sao_luu = p.with_suffix(".truoc-tinhchinh.csv")
            if not sao_luu.exists():
                pd.read_csv(p, dtype=str).fillna("").to_csv(sao_luu, index=False)
            df.to_csv(p, index=False)
            print(f"   đã ghi {p.name} (sao lưu: {sao_luu.name})")

    print(f"\n=== TỔNG: xét {tong['xet']} | viết lại được {tong['qua']} "
          f"| giữ nguyên bản gốc {tong['giu_goc']} ===")


if __name__ == "__main__":
    main()
