"""Làm giàu bộ Q/A: biến đáp án ngắn thành đáp án chi tiết, có căn cứ văn bản.

Vấn đề: bộ Q/A soạn tay có nhiều đáp án rất ngắn ("18 tín chỉ.", "06 học phần.").
Dùng làm dữ liệu huấn luyện, chúng dạy mô hình thói quen trả lời cụt.

Cách xử lý: với mỗi câu hỏi, truy xuất đúng Điều liên quan trong kho tri thức rồi
dựng lại đáp án theo bố cục:
    (1) Căn cứ: trích nội dung quy định thật, kèm TÊN VĂN BẢN + số Điều
    (2) Kết luận: giữ nguyên đáp án gốc do thầy cô soạn (phần này đã đúng)
    (3) Hướng dẫn: nhắc sinh viên đối chiếu văn bản / liên hệ đơn vị phụ trách

Nhờ vậy đáp án dài và đầy đủ hơn nhưng KHÔNG do mô hình bịa ra — mọi chi tiết bổ
sung đều lấy nguyên văn từ văn bản của Nhà trường.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/enrich_qa.py                  # xử lý mọi .csv trong data/qa
    python src/Phase4-Finetuning/enrich_qa.py "data/qa/A.csv"  # chỉ một tệp
    python src/Phase4-Finetuning/enrich_qa.py --dry-run        # chỉ xem thử, không ghi
Tệp gốc luôn được sao lưu thành <tên>.bak.csv trước khi ghi đè.
"""
from __future__ import annotations
import csv
import re
import shutil
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import retriever

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes"]

MIN_WORDS = 60          # đáp án ngắn hơn ngưỡng này thì cần làm giàu
EXCERPT_WORDS = 260     # độ dài tối đa phần trích quy định
ADVICE = ("Em nên đối chiếu trực tiếp điều khoản nêu trên để nắm đầy đủ chi tiết; "
          "nếu còn vướng mắc, em liên hệ Phòng Quản lý đào tạo hoặc cố vấn học tập "
          "của lớp để được hướng dẫn cụ thể.")


def _tidy(text: str) -> str:
    t = re.sub(r"^Điều\s+\d+[a-z]?\s*[.:]\s*", "", text.strip())
    return re.sub(r"\s+", " ", t).strip()


def _strip_lead(ans: str) -> str:
    """Bỏ mở đầu kiểu 'Theo Quy chế ...,' để không lặp với phần căn cứ phía trên."""
    a = ans.strip()
    a = re.sub(r"^(Theo|Căn cứ)\s+[^,]{5,120},\s*", "", a, flags=re.IGNORECASE)
    return a[0].upper() + a[1:] if a else a


# Các điều mang tính thủ tục/hành chính, hiếm khi là căn cứ nội dung cho câu hỏi
_BOILERPLATE = re.compile(
    r"phạm vi điều chỉnh|đối tượng áp dụng|tổ chức thực hiện|hiệu lực thi hành|"
    r"trách nhiệm thi hành|chế độ báo cáo|giải thích từ ngữ|ban hành kèm",
    re.IGNORECASE)


def _tokens(s: str) -> set:
    return {w for w in re.split(r"[^0-9a-zà-ỹ]+", (s or "").lower()) if len(w) > 2}


def _pick_basis(hits, question: str, answer: str):
    """Chọn đoạn làm căn cứ: ưu tiên đoạn khớp nội dung ĐÁP ÁN GỐC.

    Đáp án gốc do thầy cô soạn nên đã đúng trọng tâm; đoạn tài liệu trùng nhiều từ
    với đáp án đó thường chính là điều khoản cần dẫn — chính xác hơn là lấy đoạn
    xếp hạng cao nhất, vốn có thể là điều khoản thủ tục.
    """
    want = _tokens(answer) | _tokens(question)
    best, best_score = None, -1.0
    for h in hits:
        toks = _tokens(h["text"])
        overlap = len(want & toks) / (len(want) or 1)
        score = overlap + 0.3 * (h.get("rerank_score") or 0)
        heading = (h["meta"].get("heading") or "") + " " + h["text"][:120]
        if _BOILERPLATE.search(heading):
            score -= 0.35          # hạ ưu tiên điều khoản thủ tục
        if score > best_score:
            best, best_score = h, score
    return best or hits[0]


def enrich_answer(question: str, answer: str):
    """Trả về (đáp án mới, chuỗi nguồn). Trả về (None, None) nếu không đủ căn cứ."""
    hits = retriever.retrieve(question, config.RAG_TOP_K)
    if not retriever.has_relevant(hits):
        return None, None

    top = _pick_basis(hits, question, answer)
    meta = top["meta"]
    doc = retriever._clean_doc_name(meta.get("source", ""))
    dieu = meta.get("dieu")
    label = f"{doc} ({dieu})" if dieu else doc

    excerpt = _tidy(top["text"])
    words = excerpt.split()
    if len(words) > EXCERPT_WORDS:
        excerpt = " ".join(words[:EXCERPT_WORDS]).rstrip(" ,;.") + "..."

    conclusion = _strip_lead(answer)
    new = (f"Theo {label}, quy định như sau: {excerpt} "
           f"Như vậy, {conclusion[0].lower() + conclusion[1:] if conclusion else ''} "
           f"{ADVICE}")
    return re.sub(r"\s{2,}", " ", new).strip(), " | ".join(retriever.group_sources(hits))


def process_file(path: pathlib.Path, dry_run: bool = False):
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        return 0, 0
    n_short = sum(1 for r in rows if len(r.get("answer", "").split()) < MIN_WORDS)
    print(f"\n→ {path.name}: {len(rows)} câu, {n_short} câu có đáp án ngắn (<{MIN_WORDS} từ)")

    changed = 0
    for i, r in enumerate(rows, 1):
        ans = r.get("answer", "")
        if len(ans.split()) >= MIN_WORDS:
            continue
        new_ans, refs = enrich_answer(r.get("question", ""), ans)
        if not new_ans:
            continue
        r["answer"] = new_ans
        if refs:
            r["source_refs"] = refs
        changed += 1
        if i % 200 == 0:
            print(f"   ... đã xử lý {i}/{len(rows)} câu")

    if dry_run:
        print(f"   [thử] sẽ làm giàu {changed} câu (không ghi tệp)")
        return len(rows), changed

    shutil.copy2(path, path.with_suffix(".bak.csv"))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL,
                           extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    print(f"   ✅ Đã làm giàu {changed} câu (bản gốc lưu ở {path.stem}.bak.csv)")
    return len(rows), changed


def main():
    args = [a for a in sys.argv[1:]]
    dry = "--dry-run" in args
    if dry:
        args.remove("--dry-run")

    qa_dir = config.DATA_PROCESSED.parent / "qa"
    if args:
        files = [pathlib.Path(a) for a in args]
    else:
        files = sorted(p for p in qa_dir.glob("*.csv")
                       if not p.name.endswith(".bak.csv"))
    total, changed = 0, 0
    for f in files:
        t, c = process_file(f, dry)
        total += t
        changed += c
    print(f"\nTổng: {changed}/{total} câu được làm giàu đáp án.")
    if not dry:
        print("Chạy tiếp: python src/Phase4-Finetuning/build_dataset.py")


if __name__ == "__main__":
    main()
