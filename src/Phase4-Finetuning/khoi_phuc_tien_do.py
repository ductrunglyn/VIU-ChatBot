"""Dựng lại tệp tiến độ cho một mẻ tinh chỉnh đã chạy bằng bản code CŨ.

VÌ SAO CẦN
`refine_qa_llm.py --tiep` dựa vào tệp `<ra>.tien_do.json` để biết câu nào đã xử
lý. Mẻ nào khởi động trước khi tính năng đó có mặt thì không có tệp ấy, dừng lại
là mất sạch phần đã chạy. Tệp này dựng lại tiến độ từ chính tệp kết quả dở.

DỰNG LẠI BẰNG CÁCH NÀO
Bộ tinh chỉnh duyệt các câu theo THỨ TỰ ĐỘ DÀI (`len(question) + len(answer)` của
bản gốc), không theo thứ tự tệp. Thứ tự đó tất định nên tính lại được y hệt.

Câu nào đã xử lý mà được nhận thì nội dung khác bản gốc. Lấy câu-đã-đổi nằm xa
nhất trong thứ tự duyệt, ta biết bộ tinh chỉnh chắc chắn đã đi tới đó.

ƯỚC LƯỢNG NÀY CỐ Ý DÈ DẶT. Câu bị cổng kiểm chứng loại thì giữ nguyên bản gốc,
nhìn không khác gì câu chưa chạy. Nên vài câu cuối cùng — nếu chúng đều bị loại —
sẽ bị đánh dấu là chưa xong và chạy lại. Chạy lại thì chỉ tốn thêm ít phút, còn
đánh dấu nhầm là xong thì mất hẳn câu đó. Chọn phía an toàn.

Cách dùng:
    python src/Phase4-Finetuning/khoi_phuc_tien_do.py --in data/qa/qa_viu_full.csv
    python src/Phase4-Finetuning/khoi_phuc_tien_do.py --in ... --ghi
"""
from __future__ import annotations
import argparse
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True, help="tệp Q/A gốc")
    ap.add_argument("--out", default="", help="tệp kết quả (mặc định <gốc>_tinh.csv)")
    ap.add_argument("--ghi", action="store_true", help="ghi thật, không có thì chỉ xem")
    args = ap.parse_args()

    src = pathlib.Path(args.src)
    if not src.is_absolute():
        src = config.ROOT / src
    out = pathlib.Path(args.out) if args.out else src.with_name(src.stem + "_tinh.csv")
    if not out.is_absolute():
        out = config.ROOT / out

    goc = list(csv.DictReader(src.open(encoding="utf-8")))
    if not out.exists():
        sys.exit(f"❌ Chưa có tệp kết quả {out} — không có gì để khôi phục.")
    moi = list(csv.DictReader(out.open(encoding="utf-8")))

    if len(goc) != len(moi) or any(a["id"] != b["id"] for a, b in zip(goc, moi)):
        sys.exit("❌ Tệp kết quả không khớp tệp gốc (lệch số câu hoặc id). "
                 "Phải chạy lại từ đầu.")

    order = sorted(range(len(goc)),
                   key=lambda i: len(goc[i]["question"]) + len(goc[i]["answer"]))

    doi = {i for i in range(len(goc))
           if goc[i]["question"] != moi[i]["question"]
           or goc[i]["answer"] != moi[i]["answer"]}
    if not doi:
        sys.exit("❌ Không câu nào khác bản gốc — chưa có tiến độ nào để ghi.")

    vi_tri = {idx: pos for pos, idx in enumerate(order)}
    xa_nhat = max(vi_tri[i] for i in doi)
    k = xa_nhat + 1
    ids = [goc[order[p]]["id"] for p in range(k)]

    print(f"Tệp gốc     : {src.name}  ({len(goc)} câu)")
    print(f"Tệp kết quả : {out.name}")
    print(f"Câu đã đổi  : {len(doi)}")
    print(f"=> Đã xử lý ít nhất {k}/{len(goc)} câu "
          f"({len(doi)} nhận, {k - len(doi)} bị loại giữ nguyên gốc)")
    print(f"   Còn lại  : {len(goc) - k} câu")

    tien_do = out.with_name(out.name + ".tien_do.json")
    if not args.ghi:
        print(f"\n[xem thử] chưa ghi. Thêm --ghi để ghi ra {tien_do.name}")
        return
    tien_do.write_text(json.dumps(sorted(ids), ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ Đã ghi {tien_do}")
    print(f"   Chạy tiếp: python src/Phase4-Finetuning/refine_qa_llm.py "
          f"--in {args.src} --batch 2 --tiep")


if __name__ == "__main__":
    main()
