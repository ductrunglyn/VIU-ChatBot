"""Tinh chỉnh câu hỏi và đáp án bằng Qwen3-14B, có cổng kiểm chứng dữ kiện.

VÌ SAO CẦN TỆP NÀY
Bộ sinh Q/A dựng câu từ khuôn cố định nên số liệu chính xác nhưng câu chữ rập
khuôn, và độ dài dồn cục. Đo trên 1000 câu của qa_nang_cao.csv:
    câu hỏi   : 68,6% dài trên 20 từ, ngắn nhất cũng 9 từ  -> không ai hỏi vậy
    đáp án    : 21,5% dưới 60 từ, 51,8% ở 150-220 từ, lõm hẳn khoảng 100-150
Hai cục đó là dấu vết của khuôn: hoặc một câu cụt, hoặc một danh sách dài.

VÌ SAO KHÔNG ĐỂ MÔ HÌNH TỰ VIẾT ĐÁP ÁN
Đáp án chứa số tín chỉ, mã học phần, tên môn. Mô hình viết lại từ đầu sẽ sai vài
con số mà không ai soát nổi trong 1000 câu, rồi ta huấn luyện chính mô hình trên
số sai đó — đúng vòng lặp đã sinh ra lỗi "150 tín chỉ" và 230 đáp án dán nhầm
đoạn hành chính. Nên phân vai: mô hình lo DIỄN ĐẠT, dữ kiện luôn do code cấp.

CÁCH CHO ĐÁP ÁN DÀI RA MÀ KHÔNG BỊA
Đáp án cụt cần dài thêm, nhưng "viết dài hơn" là lời mời bịa. Vì vậy mỗi câu
được cấp kèm KHỐI DỮ KIỆN do curriculum_index tra từ dữ liệu đã bóc. Mô hình chỉ
được lấy thêm thông tin từ khối đó. Cổng kiểm tra vì thế nới theo đúng khối này:
    - mọi số trong bản mới phải nằm trong (đáp án gốc  ∪  khối dữ kiện)
    - mọi số của đáp án gốc phải còn nguyên trong bản mới
Thiếu số là mất học phần, thừa số là bịa; chặn cả hai chiều.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/refine_qa_llm.py --limit 20 --dry-run
    python src/Phase4-Finetuning/refine_qa_llm.py
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sys
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import curriculum_index

MODEL = "Qwen/Qwen3-14B"
COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes", "origin"]

# --------------------------------------------------------------- đích độ dài
# Chia thành dải để phân bố trải đều thay vì dồn hai cục. Số đo hiện tại nằm ở
# đầu tệp; đích là mỗi dải chiếm khoảng một phần bằng nhau.
Q_BANDS = [(6, 10), (11, 15), (16, 21), (22, 30)]
A_BANDS = [(55, 90), (90, 125), (125, 160), (160, 200), (200, 250)]

SYSTEM = (
    "Bạn là cố vấn học tập của Trường Đại học Công nghiệp Việt - Hung, biên tập "
    "lại một cặp câu hỏi - câu trả lời để dùng làm dữ liệu huấn luyện.\n\n"
    "QUY TẮC TUYỆT ĐỐI:\n"
    "1. Mọi dữ kiện phải lấy từ ĐÁP ÁN GỐC hoặc khối DỮ KIỆN TRA CỨU được cấp. "
    "Không thêm bất kỳ thông tin nào từ hiểu biết của bạn, kể cả khi bạn tin là "
    "đúng ngoài đời.\n"
    "2. Không đổi, không thêm, không bớt con số: số tín chỉ, số học kỳ, mã học "
    "phần, số Điều, tên học phần, tên ngành.\n"
    "3. Giữ nguyên trọng tâm câu hỏi. Nếu câu hỏi hỏi về học kỳ 6 ngành KT Nhiệt "
    "thì bản viết lại vẫn phải hỏi đúng học kỳ 6 ngành KT Nhiệt.\n"
    "4. Câu hỏi viết như sinh viên hỏi thật: tự nhiên, có thể cụt, có thể thân "
    "mật. Đừng viết như đề thi.\n"
    "5. Câu trả lời xưng 'em' với sinh viên, câu đầu trả lời thẳng vào trọng tâm, "
    "sau đó mới tới chi tiết. Không mở đầu bằng khuôn 'Theo kế hoạch đào tạo...' "
    "nếu đáp án gốc đã mở như vậy — hãy đổi cách vào đề.\n"
    "6. Nếu phải liệt kê nhiều học phần, hãy nhóm lại cho dễ đọc thay vì đổ một "
    "chuỗi dấu chấm phẩy dài.\n\n"
    "Trả về ĐÚNG một khối JSON, không kèm lời dẫn:\n"
    '{"question": "...", "answer": "..."}'
)

USER = (
    "CÂU HỎI GỐC ({q_len} từ):\n{question}\n\n"
    "ĐÁP ÁN GỐC ({a_len} từ):\n{answer}\n"
    "{facts}\n"
    "YÊU CẦU ĐỘ DÀI: câu hỏi khoảng {q_lo}-{q_hi} từ, câu trả lời khoảng "
    "{a_lo}-{a_hi} từ.\n"
    "Viết lại cặp này, giữ nguyên 100% dữ kiện."
)


# ------------------------------------------------------- cổng kiểm tra dữ kiện
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def _facts(text: str) -> list[str]:
    """Mọi chuỗi số trong văn bản, giữ cả số lần lặp."""
    return sorted(_NUM_RE.findall(text or ""))


def verify(orig_q: str, orig_a: str, new_q: str, new_a: str,
           extra: str = "") -> tuple[bool, str]:
    """Bản viết lại có giữ đúng dữ kiện không.

    Kiểm tra hai chiều vì hỏng theo cả hai hướng đều nguy hiểm: thừa số là mô
    hình bịa, thiếu số là nó bỏ mất học phần hay điều kiện.
    """
    if not new_q or not new_q.strip() or not new_a or not new_a.strip():
        return False, "bản viết lại rỗng"

    a, b = _facts(orig_a), _facts(new_a)
    allowed = set(a) | set(_facts(extra))
    thua = sorted({x for x in b if x not in allowed})
    if thua:
        return False, f"đáp án có số không có trong dữ liệu: {thua}"
    thieu = [x for x in a if a.count(x) > b.count(x)]
    if thieu:
        return False, f"đáp án làm mất số: {sorted(set(thieu))}"

    # Câu hỏi không được đổi trọng tâm: mọi số trong câu hỏi mới phải có sẵn ở
    # câu hỏi cũ (hỏi "học kỳ 6" mà viết lại thành "học kỳ 8" là hỏng dữ liệu).
    qa, qb = _facts(orig_q), _facts(new_q)
    if sorted(set(qb)) != sorted(set(qa)):
        return False, f"câu hỏi đổi số: gốc {sorted(set(qa))} -> mới {sorted(set(qb))}"
    return True, ""


# ------------------------------------------------------------ chọn dải độ dài
def assign_bands(rows: list[dict]) -> list[tuple]:
    """Gán dải độ dài cho từng câu sao cho phân bố cuối cùng trải đều.

    Không gán ngẫu nhiên: đáp án liệt kê 11 học phần thì không thể nén còn 60 từ
    mà không mất học phần — ép vào dải ngắn chỉ làm cổng kiểm tra loại hết. Nên
    lấy độ dài gốc làm SÀN rồi chia đều trong các dải còn khả thi.
    """
    out = []
    for i, r in enumerate(rows):
        a_len = len(r["answer"].split())
        # Sàn tính theo MẬT ĐỘ DỮ KIỆN chứ không theo tỉ lệ co: đáp án liệt kê 11
        # học phần có 11 con số phải giữ, mỗi mục cần chừng 6 từ để nêu tên và số
        # tín chỉ. Lấy tỉ lệ (kiểu "được co còn 55%") thì một đáp án 155 từ vẫn bị
        # xếp vào dải 55-90, mô hình buộc phải bỏ bớt học phần và cổng loại sạch.
        n_facts = len(set(_NUM_RE.findall(r["answer"])))
        floor = max(40, 25 + 6 * n_facts, int(a_len * 0.7))
        feasible = [b for b in A_BANDS if b[1] >= floor]
        a_band = feasible[i % len(feasible)] if feasible else A_BANDS[-1]
        q_band = Q_BANDS[i % len(Q_BANDS)]
        out.append((q_band, a_band))
    return out


# ------------------------------------------------------------------ gọi model
def load_model(dtype_4bit: bool = True):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(MODEL, padding_side="left")
    kw = {"dtype": torch.bfloat16, "device_map": "auto"}
    if dtype_4bit:
        kw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(MODEL, **kw)
    model.eval()
    return tok, model


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse(text: str) -> tuple[str, str]:
    """Bóc {"question","answer"} khỏi đầu ra. Trả ("","") nếu không đọc được."""
    m = _JSON_RE.search(text or "")
    if not m:
        return "", ""
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return "", ""
    return str(d.get("question", "")).strip(), str(d.get("answer", "")).strip()


def run_batch(tok, model, prompts: list[str], max_new: int) -> list[str]:
    import torch

    texts = [tok.apply_chat_template(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": p}],
        tokenize=False, add_generation_prompt=True,
        # Qwen3 mặc định bật khối suy nghĩ dài; ở đây chỉ cần biên tập câu chữ nên
        # tắt đi, vừa nhanh vừa khỏi lẫn phần suy nghĩ vào JSON đầu ra.
        enable_thinking=False) for p in prompts]
    enc = tok(texts, return_tensors="pt", padding=True).to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=max_new, do_sample=True,
                             temperature=0.8, top_p=0.9,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
    return [tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=True)
            for o in out]


# ---------------------------------------------------------------------- chạy
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="data/qa/qa_nang_cao.csv")
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--max-new", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = pathlib.Path(args.src)
    if not src.is_absolute():
        src = config.ROOT / src
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    if args.limit:
        rows = rows[:args.limit]
    bands = assign_bands(rows)
    print(f"{src.name}: tinh chỉnh {len(rows)} câu bằng {MODEL}")

    tok, model = load_model()
    print("Đã nạp mô hình. Bắt đầu.\n")

    ok, rejected, samples = 0, [], []
    t0 = time.time()
    for start in range(0, len(rows), args.batch):
        chunk = rows[start:start + args.batch]
        chunk_bands = bands[start:start + args.batch]
        prompts, extras = [], []
        for r, (qb, ab) in zip(chunk, chunk_bands):
            extra = curriculum_index.facts_for(r["question"]) or ""
            extras.append(extra)
            prompts.append(USER.format(
                question=r["question"], answer=r["answer"],
                q_len=len(r["question"].split()), a_len=len(r["answer"].split()),
                facts=("\nDỮ KIỆN TRA CỨU (chỉ được lấy thêm thông tin từ đây):\n"
                       + extra + "\n") if extra else "",
                q_lo=qb[0], q_hi=qb[1], a_lo=ab[0], a_hi=ab[1]))

        for r, raw, extra in zip(chunk, run_batch(tok, model, prompts, args.max_new), extras):
            nq, na = _parse(raw)
            good, why = verify(r["question"], r["answer"], nq, na, extra)
            if not good:
                rejected.append((r["id"], r["question"][:55], why))
                continue                       # giữ nguyên cặp gốc
            if len(samples) < 3:
                samples.append((r["question"], r["answer"], nq, na))
            r["question"], r["answer"] = nq, na
            ok += 1

        done = min(start + args.batch, len(rows))
        rate = done / max(time.time() - t0, 1e-9)
        print(f"  {done}/{len(rows)}  nhận {ok}  loại {len(rejected)}  "
              f"({rate:.2f} câu/s, còn ~{(len(rows) - done) / max(rate, 1e-9) / 60:.0f} phút)")

    print(f"\n✅ Nhận {ok}/{len(rows)}   ❌ Loại {len(rejected)} (giữ nguyên bản gốc)")
    for rid, q, why in rejected[:10]:
        print(f"   [{rid}] {q} -> {why}")
    for q0, a0, q1, a1 in samples:
        print(f"\n--- HỎI gốc: {q0}\n    HỎI mới: {q1}")
        print(f"    ĐÁP gốc ({len(a0.split())} từ): {a0[:200]}")
        print(f"    ĐÁP mới ({len(a1.split())} từ): {a1[:200]}")

    if args.dry_run:
        print("\n[thử] không ghi tệp.")
        return

    out = pathlib.Path(args.out) if args.out else src.with_name(src.stem + "_tinh.csv")
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL,
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\n✅ Đã ghi -> {out}")


if __name__ == "__main__":
    main()
