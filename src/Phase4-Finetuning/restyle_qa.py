"""Viết lại các đáp án DÁN NGUYÊN VĂN thành đáp án tổng hợp, đúng trọng tâm.

Vấn đề quan sát được khi dùng thật: hỏi "sinh viên bị cảnh báo học tập trong
trường hợp nào" thì chatbot đọc nguyên cả Điều 11 — gồm cả phần buộc thôi học và
phần quy trình thủ tục không ai hỏi — rồi bị cắt cụt giữa chừng vì quá dài.

Truy ngược vào dữ liệu huấn luyện: 1052 đáp án do thầy cô soạn có văn phong tổng
hợp rất tốt ("Theo <văn bản>, <trả lời gọn>"), nhưng 782 đáp án do các script
gen_qa_from_docs/enrich_qa sinh ra lại có dạng "Theo X, quy định như sau: <dán
nguyên văn 260 từ>". Chính 782 mẫu này dạy mô hình thói quen đọc lể.

Cách sửa, hoàn toàn TRÍCH XUẤT chứ không sinh chữ mới (nên không có nguy cơ bịa):
- Dạng có kết luận: đưa kết luận lên TRƯỚC, phần trích lùi xuống làm căn cứ.
- Mọi dạng: cắt bớt phần trích theo ranh giới KHOẢN, giữ từ đầu xuống.
Cố ý KHÔNG chọn khoản theo mức trùng từ với câu hỏi — đã thử và cho kết quả sai
nguy hiểm (xem ghi chú trong _pick_blocks).

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/restyle_qa.py --dry-run
    python src/Phase4-Finetuning/restyle_qa.py
"""
from __future__ import annotations
import argparse
import csv
import re
import shutil
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes", "origin"]

TARGET_WORDS = 170      # độ dài mong muốn của phần trích trong đáp án

# "Theo <nguồn>, quy định (cụ thể) như sau: <trích dẫn> [Như vậy, <kết luận>]"
SHAPE_RE = re.compile(
    r"^Theo\s+(?P<label>.{5,140}?),\s*quy định(?:\s+cụ thể)?\s+như sau:\s*"
    r"(?P<body>.*)$", re.DOTALL)
CONCL_RE = re.compile(r"\s*Như vậy,\s*(?P<concl>.+)$", re.DOTALL)

# Ranh giới KHOẢN: số thứ tự "1." "2." ở đầu ý. Cắt theo khoản chứ không theo câu,
# vì một khoản thường kèm danh sách a) b) c) — cắt lẻ ra thì đáp án mất mục, đọc
# thành vô nghĩa ("...d) Bằng tốt nghiệp... đ) Giấy chứng nhận..." mà không có a, b, c).
_KHOAN_SPLIT_RE = re.compile(r"(?=(?<![0-9])\b\d{1,2}\.\s+[A-ZÀ-Ỹa-zà-ỹ])")


def _blocks(text: str) -> tuple[str, list[str]]:
    """Tách đoạn trích thành (câu dẫn, danh sách khoản).

    Câu dẫn là phần trước khoản đầu tiên — thường là tên Điều, nêu chủ đề.
    """
    text = re.sub(r"\s+", " ", text).strip()
    parts = [p.strip() for p in _KHOAN_SPLIT_RE.split(text) if p.strip()]
    if len(parts) <= 1:
        return "", [text]
    if re.match(r"^\d{1,2}\.\s", parts[0]):
        return "", parts
    return parts[0], parts[1:]


def _pick_blocks(blocks: list[str], budget: int) -> list[str]:
    """Giữ các KHOẢN đầu tiên trong phạm vi độ dài cho phép, CẮT PHẦN ĐUÔI.

    Đã thử chọn khoản theo mức trùng từ với câu hỏi và kết quả sai nguy hiểm: hỏi
    "cảnh báo học tập trong trường hợp nào" thì nó chọn khoản 2 (buộc thôi học)
    vì khoản đó nhắc cụm "cảnh báo học tập" nhiều lần hơn. Đáp án sai còn tệ hơn
    đáp án dài, nên bỏ hẳn hướng chọn lọc.

    Cắt đuôi thì an toàn: văn bản quy phạm viết từ chính tới phụ, khoản đầu là
    quy định cốt lõi còn khoản cuối thường là thủ tục, nên phần giữ lại vẫn đúng,
    chỉ có thể thiếu chứ không sai. Luôn giữ trọn khoản đầu tiên và giữ nguyên vẹn
    mọi mục a, b, c bên trong khoản đã chọn.
    """
    kept, used = [], 0
    for b in blocks:
        n = len(b.split())
        if kept and used + n > budget:
            break
        kept.append(b)
        used += n
    return kept or [blocks[0]]


def restyle(question: str, answer: str):
    """Trả về đáp án đã viết lại, hoặc None nếu đáp án vốn đã đúng văn phong."""
    m = SHAPE_RE.match(answer.strip())
    if not m:
        return None                       # đáp án thầy cô soạn -> giữ nguyên

    label = m.group("label").strip()
    body = m.group("body").strip()

    cm = CONCL_RE.search(body)
    conclusion = ""
    if cm:
        conclusion = cm.group("concl").strip()
        body = body[:cm.start()].strip()

    intro, blocks = _blocks(body)
    if not blocks:
        return None
    picked = _pick_blocks(blocks, TARGET_WORDS)
    quote = " ".join(([intro] if intro else []) + picked).strip()

    if conclusion:
        # Kết luận đã trả lời thẳng câu hỏi -> đưa lên TRƯỚC, trích dẫn làm căn cứ.
        lead = conclusion[0].upper() + conclusion[1:]
        new = f"{lead} Căn cứ {label}: {quote}"
    else:
        new = f"Theo {label}, {quote}"

    new = re.sub(r"\s{2,}", " ", new).strip()
    return new if new.rstrip().endswith((".", ";", ":")) else new + "."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    qa_dir = config.DATA_PROCESSED.parent / "qa"
    path = pathlib.Path(args.file) if args.file else qa_dir / "qa_viu_full.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))

    before = [len(r["answer"].split()) for r in rows]
    changed, samples = 0, []
    for r in rows:
        new = restyle(r["question"], r["answer"])
        if not new:
            continue
        if len(samples) < 3:
            samples.append((r["question"], r["answer"], new))
        r["answer"] = new
        changed += 1

    after = [len(r["answer"].split()) for r in rows]
    print(f"{path.name}: viết lại {changed}/{len(rows)} đáp án dán nguyên văn")
    print(f"   Độ dài trung bình: {sum(before)//len(before)} -> {sum(after)//len(after)} từ")
    print(f"   Dài nhất         : {max(before)} -> {max(after)} từ")
    for q, old, new in samples:
        print(f"\n--- {q[:70]}")
        print(f"  TRƯỚC ({len(old.split())} từ): {old[:170]}...")
        print(f"  SAU   ({len(new.split())} từ): {new[:300]}")

    if args.dry_run:
        print("\n[thử] không ghi tệp.")
        return

    shutil.copy2(path, path.with_suffix(".style.bak.csv"))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL,
                           extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    print(f"\n✅ Đã ghi -> {path}  (bản cũ: {path.stem}.style.bak.csv)")


if __name__ == "__main__":
    main()
