"""Dùng một LLM MẠNH viết lại ĐÁP ÁN cho tự nhiên, nhưng KHÔNG cho nó đổi dữ kiện.

Vấn đề: đáp án do bộ sinh dựng ra chính xác tuyệt đối (số liệu tính bằng code)
nhưng lặp văn phong, vì mọi câu cùng chủ đề dùng chung một khuôn chữ.

Cám dỗ: để mô hình tự viết cả đáp án. Không làm vậy. Đáp án ở đây chứa số tín
chỉ, mã học phần, tên môn — mô hình viết lại từ đầu sẽ sai vài con số mà không ai
soát nổi trong 1000 câu, rồi ta huấn luyện chính mô hình trên số sai đó. Đúng cái
vòng lặp đã sinh ra lỗi "150 tín chỉ" và "230 đáp án dán nhầm đoạn hành chính".

Cách làm ở đây: mô hình chỉ được DIỄN ĐẠT LẠI đáp án gốc. Sau đó bản viết lại
phải qua CỔNG KIỂM TRA DỮ KIỆN — mọi con số và mã học phần trong bản mới phải có
trong bản gốc, và mọi con số của bản gốc phải còn nguyên trong bản mới. Sai một
chữ số là loại, giữ nguyên đáp án gốc. Cổng này mới là phần quan trọng của tệp:
không có nó thì bất kỳ mô hình nào viết lại cũng có thể âm thầm làm hỏng số liệu.

Yêu cầu: đặt biến môi trường ANTHROPIC_API_KEY (hoặc chạy `ant auth login`), và
    pip install anthropic

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/llm_rewrite_answers.py --dry-run --limit 20
    python src/Phase4-Finetuning/llm_rewrite_answers.py --in data/qa/qa_nang_cao.csv
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import re
import sys
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config

COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes", "origin"]
MODEL = "claude-opus-5"
BATCH_POLL_SECONDS = 30

SYSTEM = (
    "Bạn là biên tập viên của Trường Đại học Công nghiệp Việt - Hung, viết lại lời "
    "tư vấn học vụ cho tự nhiên và dễ đọc hơn.\n\n"
    "QUY TẮC TUYỆT ĐỐI:\n"
    "1. Bạn CHỈ được diễn đạt lại. Mọi dữ kiện phải lấy nguyên từ đáp án gốc.\n"
    "2. KHÔNG được thêm, bớt hay sửa bất kỳ con số nào: số tín chỉ, số học kỳ, số "
    "học phần, mã học phần, số Điều, tên văn bản, tên học phần, tên ngành.\n"
    "3. KHÔNG được bổ sung thông tin không có trong đáp án gốc, kể cả khi bạn biết "
    "thông tin đó đúng ngoài đời.\n"
    "4. KHÔNG được bỏ bớt dữ kiện. Đáp án gốc liệt kê 6 học phần thì bản mới phải "
    "đủ 6 học phần.\n"
    "5. Viết bằng tiếng Việt, giọng cố vấn học tập thân thiện, gọi sinh viên là "
    "'em'. Câu đầu trả lời thẳng vào câu hỏi.\n"
    "6. Mỗi lần viết hãy chọn cách mở đầu và cách sắp xếp khác nhau, đừng dùng lại "
    "một khuôn câu.\n\n"
    "Chỉ trả về đáp án đã viết lại, không thêm lời dẫn, không thêm nhãn."
)

USER_TEMPLATE = (
    "CÂU HỎI CỦA SINH VIÊN:\n{question}\n\n"
    "ĐÁP ÁN GỐC (nguồn dữ kiện duy nhất):\n{answer}\n\n"
    "Viết lại đáp án trên cho tự nhiên hơn, giữ nguyên 100% dữ kiện."
)


# ------------------------------------------------------- cổng kiểm tra dữ kiện
# Số (kể cả dạng "2(1.6,0.4,4)"), mã học phần, số Điều — tất cả đều phải khớp.
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def _facts(text: str) -> list[str]:
    """Rút mọi chuỗi số trong văn bản, giữ cả số lần lặp."""
    return sorted(_NUM_RE.findall(text or ""))


def verify(original: str, rewritten: str) -> tuple[bool, str]:
    """Bản viết lại có giữ đúng dữ kiện không.

    Kiểm tra hai chiều, vì hỏng theo cả hai hướng đều nguy hiểm:
      - thừa số  -> mô hình bịa thêm dữ kiện
      - thiếu số -> mô hình bỏ mất học phần / điều kiện
    """
    if not rewritten or not rewritten.strip():
        return False, "bản viết lại rỗng"

    a, b = _facts(original), _facts(rewritten)
    if a != b:
        extra = [x for x in b if b.count(x) > a.count(x)]
        missing = [x for x in a if a.count(x) > b.count(x)]
        parts = []
        if extra:
            parts.append(f"thêm số không có trong bản gốc: {sorted(set(extra))}")
        if missing:
            parts.append(f"làm mất số: {sorted(set(missing))}")
        return False, "; ".join(parts)

    # Không cho rút gọn quá tay: mất một nửa độ dài thường là mất nội dung.
    if len(rewritten.split()) < 0.5 * len(original.split()):
        return False, "ngắn hơn bản gốc quá nhiều, nhiều khả năng mất nội dung"
    return True, ""


# ------------------------------------------------------------------ gọi model
def _client():
    try:
        import anthropic
    except ImportError:
        print("❌ Chưa cài SDK. Chạy: pip install anthropic")
        sys.exit(1)
    # Client rỗng tự lấy ANTHROPIC_API_KEY, hoặc hồ sơ đăng nhập của `ant auth login`.
    return anthropic.Anthropic()


def rewrite_batch(client, rows: list[dict]) -> dict[str, str]:
    """Gửi cả lô qua Batches API (rẻ hơn 50%), trả về {id: đáp án mới}."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    requests = [
        Request(
            custom_id=f"qa-{r['id']}",
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=2000,
                system=SYSTEM,
                messages=[{"role": "user", "content": USER_TEMPLATE.format(
                    question=r["question"], answer=r["answer"])}],
            ),
        )
        for r in rows
    ]

    batch = client.messages.batches.create(requests=requests)
    print(f"   Đã gửi lô {batch.id} ({len(requests)} câu). Đang chờ xử lý...")

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        print(f"   ... {batch.request_counts.processing} câu đang xử lý")
        time.sleep(BATCH_POLL_SECONDS)

    out = {}
    for result in client.messages.batches.results(batch.id):
        if result.result.type != "succeeded":
            continue
        text = next((b.text for b in result.result.message.content
                     if b.type == "text"), "")
        out[result.custom_id.removeprefix("qa-")] = text.strip()
    return out


# ---------------------------------------------------------------------- chạy
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="data/qa/qa_nang_cao.csv")
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=0, help="chỉ xử lý N câu đầu")
    ap.add_argument("--dry-run", action="store_true", help="in thử, không ghi tệp")
    args = ap.parse_args()

    src = pathlib.Path(args.src)
    if not src.is_absolute():
        src = config.ROOT / src
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    if args.limit:
        rows = rows[:args.limit]
    print(f"{src.name}: {len(rows)} câu cần viết lại bằng {MODEL}")

    client = _client()
    rewritten = rewrite_batch(client, rows)

    ok, rejected, samples = 0, [], []
    for r in rows:
        new = rewritten.get(r["id"])
        if not new:
            continue
        good, why = verify(r["answer"], new)
        if not good:
            rejected.append((r["id"], r["question"][:60], why))
            continue                      # giữ nguyên đáp án gốc
        if len(samples) < 3:
            samples.append((r["question"], r["answer"], new))
        r["answer"] = new
        ok += 1

    print(f"\n✅ Nhận {ok}/{len(rows)} bản viết lại")
    print(f"❌ Loại {len(rejected)} bản do sai dữ kiện (giữ nguyên đáp án gốc)")
    for rid, q, why in rejected[:8]:
        print(f"   [{rid}] {q} -> {why}")
    for q, old, new in samples:
        print(f"\n--- {q[:70]}")
        print(f"  GỐC : {old[:220]}")
        print(f"  MỚI : {new[:220]}")

    if args.dry_run:
        print("\n[thử] không ghi tệp.")
        return

    out = pathlib.Path(args.out) if args.out else src.with_name(src.stem + "_llm.csv")
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL,
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\n✅ Đã ghi -> {out}")


if __name__ == "__main__":
    main()
