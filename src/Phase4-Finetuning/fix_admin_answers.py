"""Sửa các đáp án Q/A bị dán nhầm phần thủ tục hành chính của văn bản.

Bối cảnh: các bộ sinh dữ liệu (gen_qa_from_docs, gen_faq, enrich_qa) dựng đáp án
bằng cách trích nguyên văn đoạn quy định lấy từ kho tri thức. Lúc đó bộ cắt còn
gộp Quyết định ban hành chung với Quy định đính kèm, nên một số đáp án bị dán
phần "Nơi nhận / HIỆU TRƯỞNG / chịu trách nhiệm thi hành quyết định này" — thứ
không trả lời được câu hỏi nào.

Hậu quả nặng hơn ta tưởng: khi fine-tune, mô hình học thuộc đúng đoạn đó và ĐỌC
LẠI nó ngay cả khi kho tri thức đã sạch, vì phần thủ tục nằm ở ĐÁP ÁN (tức là
đích cần học), không phải chỉ ở ngữ cảnh.

Cách sửa: với mỗi đáp án hỏng, truy xuất lại trên kho tri thức ĐÃ SẠCH, chọn Điều
thật sự liên quan rồi dựng lại phần căn cứ; kết luận do thầy cô/bộ sinh viết
trước đó được giữ nguyên. Câu nào không tìm được căn cứ mới thì bỏ hẳn khỏi bộ
dữ liệu — thà thiếu còn hơn dạy mô hình nói sai.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/fix_admin_answers.py --dry-run   # xem trước
    python src/Phase4-Finetuning/fix_admin_answers.py             # ghi đè (có sao lưu)
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
import retriever

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes", "origin"]
EXCERPT_WORDS = 260

# Dấu hiệu CHẮC CHẮN của khối thủ tục ban hành. Cố ý không dùng "chịu trách nhiệm"
# trơ trọi vì "chịu trách nhiệm biên soạn" là nội dung thật, cần giữ.
ADMIN_RE = re.compile(
    r"Nơi nhận\s*:|HIỆU TRƯỞNG|chịu trách nhiệm thi hành (quyết định|văn bản) này|"
    r"Ban hành kèm theo quyết định này|Lưu\s*:?\s*VT",
    re.IGNORECASE)

# Dạng đáp án do enrich_qa/gen_* dựng: "Theo <nguồn>, quy định (cụ thể) như sau:
# <trích dẫn> Như vậy, <kết luận>"
SHAPE_RE = re.compile(
    r"^Theo\s+(?P<label>.{5,140}?),\s*quy định(?:\s+cụ thể)?\s+như sau:\s*"
    r"(?P<excerpt>.*?)(?:\s*Như vậy,\s*(?P<concl>.*))?$",
    re.DOTALL)


def _tidy(text: str) -> str:
    t = re.sub(r"^Điều\s+\d+[a-z]?\s*[.:]\s*", "", text.strip())
    return re.sub(r"\s+", " ", t).strip()


def _tokens(s: str) -> set:
    return {w for w in re.split(r"[^0-9a-zà-ỹ]+", (s or "").lower()) if len(w) > 2}


def _pick_basis(hits, question: str, hint: str):
    """Chọn đoạn làm căn cứ: ưu tiên đoạn khớp nội dung câu hỏi và kết luận cũ."""
    want = _tokens(hint) | _tokens(question)
    best, best_score = None, -1.0
    for h in hits:
        overlap = len(want & _tokens(h["text"])) / (len(want) or 1)
        score = overlap + 0.3 * (h.get("rerank_score") or 0)
        if score > best_score:
            best, best_score = h, score
    return best


def rebuild(question: str, answer: str):
    """Dựng lại đáp án từ kho tri thức sạch. Trả (đáp án mới, nguồn) hoặc (None, None)."""
    m = SHAPE_RE.match(answer.strip())
    conclusion = (m.group("concl") or "").strip() if m else ""
    # Kết luận cũ có thể cũng dính phần thủ tục -> không dùng làm gợi ý nữa.
    if ADMIN_RE.search(conclusion):
        conclusion = ""

    hits = retriever.retrieve(question, config.RAG_TOP_K)
    if not retriever.has_relevant(hits):
        return None, None
    # Bỏ hẳn mọi đoạn thủ tục còn sót trong kho tri thức.
    hits = [h for h in hits if not ADMIN_RE.search(h["text"])]
    if not hits:
        return None, None

    top = _pick_basis(hits, question, conclusion)
    meta = top["meta"]
    doc = retriever._clean_doc_name(meta.get("source", ""))
    dieu = meta.get("dieu")
    label = f"{doc} ({dieu})" if dieu else doc

    excerpt = _tidy(top["text"])
    words = excerpt.split()
    if len(words) > EXCERPT_WORDS:
        excerpt = " ".join(words[:EXCERPT_WORDS]).rstrip(" ,;.") + "..."

    new = f"Theo {label}, quy định như sau: {excerpt}"
    if conclusion:
        new += f" Như vậy, {conclusion[0].lower() + conclusion[1:]}"
    return re.sub(r"\s{2,}", " ", new).strip(), " | ".join(retriever.group_sources(hits))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="", help="tệp Q/A (mặc định data/qa/qa_viu_full.csv)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    qa_dir = config.DATA_PROCESSED.parent / "qa"
    path = pathlib.Path(args.file) if args.file else qa_dir / "qa_viu_full.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))

    bad = [r for r in rows if ADMIN_RE.search(r.get("answer", ""))]
    print(f"{path.name}: {len(rows)} câu, {len(bad)} câu dính văn bản thủ tục hành chính")
    if not bad:
        print("✅ Không có gì phải sửa.")
        return

    fixed, dropped = 0, []
    for r in bad:
        new_ans, refs = rebuild(r["question"], r["answer"])
        if not new_ans or ADMIN_RE.search(new_ans):
            dropped.append(r)
            continue
        r["answer"] = new_ans
        if refs:
            r["source_refs"] = refs
        fixed += 1

    kept = [r for r in rows if r not in dropped]
    for i, r in enumerate(kept, 1):
        r["id"] = str(i)

    print(f"   Dựng lại được : {fixed}")
    print(f"   Phải bỏ hẳn   : {len(dropped)} (không còn căn cứ sạch trong kho tri thức)")
    for r in dropped[:5]:
        print(f"      · {r['question'][:70]}")

    if args.dry_run:
        print("\n[thử] không ghi tệp.")
        return

    shutil.copy2(path, path.with_suffix(".admin.bak.csv"))
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL,
                           extrasaction="ignore")
        w.writeheader()
        for r in kept:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    print(f"\n✅ Đã ghi {len(kept)} câu -> {path}  (bản cũ: {path.stem}.admin.bak.csv)")
    print("Chạy tiếp: python src/Phase4-Finetuning/build_dataset.py")


if __name__ == "__main__":
    main()
