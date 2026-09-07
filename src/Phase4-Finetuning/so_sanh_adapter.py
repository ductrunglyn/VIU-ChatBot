"""So sánh model GỐC với model đã fine-tune trên cùng bộ câu hỏi và cùng ngữ cảnh.

Fine-tune chỉ đáng giữ nếu nó thật sự tốt hơn model gốc. Nạp cả hai trong MỘT lần
chạy, hỏi cùng câu, in cạnh nhau để soát bằng mắt — kèm vài chỉ số đếm được:

  - độ dài đáp án (bản gốc hay lan man, bản fine-tune nên gọn mà vẫn đủ ý)
  - có trích dẫn tên văn bản không (mục tiêu chính của fine-tune)
  - có lọt chữ Hán / khối <think> không

    python src/Phase4-Finetuning/so_sanh_adapter.py
    python src/Phase4-Finetuning/so_sanh_adapter.py cauhoi.txt   # mỗi dòng 1 câu
"""
from __future__ import annotations
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Phase3-RAG"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import rag
import retriever

QUESTIONS = [
    "Sinh viên bị cảnh báo học tập trong những trường hợp nào?",
    "Em bị CPA 1.5 ở năm hai thì có bị buộc thôi học không?",
    "Chuẩn đầu ra tin học gồm những chứng chỉ nào?",
    "Em trượt môn thì phải làm sao?",
    "Ngành Kỹ thuật nhiệt tổng bao nhiêu tín chỉ?",
    "Thời gian đào tạo tối đa của sinh viên là bao lâu?",
    "Trường có bán trú cho sinh viên không?",
]

_HAN = re.compile(r"[一-鿿]")


def _sinh(llm, tok, question, history=None):
    """Sinh câu trả lời cho sẵn model — dùng lại đúng đường ghép prompt của rag.py."""
    messages, sources, relevant = rag._build_messages(question, history)
    if not relevant:
        return rag.NO_ANSWER, sources
    text = rag._chat_text(tok, messages)
    inputs = tok([text], return_tensors="pt").to(llm.device)
    gen = llm.generate(**inputs, **rag._gen_kwargs(tok))
    out = tok.decode(gen[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    out = rag._fix_citations(rag._strip_think(out),
                             rag._ctx_dieu_map(messages[-1]["content"]))
    return out, sources


def _do(reply, sources):
    """Vài chỉ số đếm được, không thay cho việc đọc bằng mắt."""
    doc_names = {s.split("—")[-1].strip() for s in sources}
    return {
        "từ": len(reply.split()),
        "dẫn nguồn": any(d and d in reply for d in doc_names),
        "lọt chữ Hán": bool(_HAN.search(reply)),
        "lọt <think>": "<think>" in reply,
    }


def main():
    import torch

    if len(sys.argv) > 1 and pathlib.Path(sys.argv[1]).exists():
        qs = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    else:
        qs = QUESTIONS

    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    name = config.LLM_MODEL
    tok = AutoTokenizer.from_pretrained(name)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    print(f"Nạp {name} (4-bit) ...")
    base = AutoModelForCausalLM.from_pretrained(name, quantization_config=bnb,
                                                device_map="cuda:0").eval()
    # PeftModel bọc quanh CHÍNH model gốc; disable_adapter() cho phép tắt/bật
    # adapter mà không phải nạp 10 GB trọng số hai lần.
    tuned = PeftModel.from_pretrained(base, str(config.ADAPTER_DIR)).eval()
    print("Đã nạp adapter:", config.ADAPTER_DIR)

    # rag dùng singleton _llm/_tok; gán thẳng để _build_messages không nạp lại model.
    rag._llm, rag._tok = tuned, tok

    for i, q in enumerate(qs, 1):
        print("\n" + "#" * 78)
        print(f"[{i}/{len(qs)}] {q}")
        with tuned.disable_adapter():
            g, src = _sinh(tuned, tok, q)
        f, _ = _sinh(tuned, tok, q)
        for nhan, r in (("GỐC", g), ("FINE-TUNE", f)):
            print("\n--- " + nhan + " " + "-" * (72 - len(nhan)))
            print(r)
            print("   " + " | ".join(f"{k}: {v}" for k, v in _do(r, src).items()))


if __name__ == "__main__":
    main()
