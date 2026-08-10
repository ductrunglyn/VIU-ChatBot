"""Giai đoạn 4: Fine-tune QLoRA cho LLM cố vấn học tập.

Dạy Qwen2.5-3B "văn phong & tư duy tư vấn" từ bộ Q/A ở data/qa/train.jsonl
(4-bit NF4 + LoRA, chỉ tính loss trên phần trả lời của trợ lý).

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/build_dataset.py   # đảm bảo train.jsonl mới nhất
    python src/Phase4-Finetuning/train_qlora.py     # -> LoRA adapter ở models/qlora-viu/

Sau khi train xong, rag.py tự nạp adapter (config.USE_FINETUNED=True).
"""
from __future__ import annotations
import sys as _sys, pathlib as _pathlib

_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / "common"))
import config

# Chat template Qwen2.5 có tag {% generation %} để đánh dấu token trả lời của trợ lý
# -> cho phép chỉ tính loss trên phần trả lời (assistant_only_loss).
_GEN_TEMPLATE = (
    "{%- for message in messages %}"
    "{%- if message.role == 'assistant' %}"
    # đưa cả <|im_end|> vào vùng {% generation %} để model HỌC được cách dừng
    "{{- '<|im_start|>assistant\n' }}{% generation %}{{ message.content + '<|im_end|>' }}{% endgeneration %}{{ '\n' }}"
    "{%- else %}"
    "{{- '<|im_start|>' + message.role + '\n' + message.content + '<|im_end|>\n' }}"
    "{%- endif %}"
    "{%- endfor %}"
    "{%- if add_generation_prompt %}{{- '<|im_start|>assistant\n' }}{%- endif %}"
)


def main():
    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig
    from trl import SFTTrainer, SFTConfig

    train_file = config.DATA_PROCESSED.parent / "qa" / "train.jsonl"
    if not train_file.exists():
        raise SystemExit("Chưa có data/qa/train.jsonl. Chạy build_dataset.py trước.")

    ds = load_dataset("json", data_files=str(train_file), split="train")
    print(f"Nạp {len(ds)} cặp Q/A từ {train_file.name}")
    if len(ds) < 200:
        print("  ⚠️  Dataset còn ít — kết quả fine-tune chỉ mang tính minh họa/định hình "
              "văn phong. Nên đạt 500–1000 cặp để cải thiện rõ rệt.")

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    tok = AutoTokenizer.from_pretrained(config.FINETUNE_BASE)
    tok.chat_template = _GEN_TEMPLATE
    model = AutoModelForCausalLM.from_pretrained(
        config.FINETUNE_BASE, quantization_config=bnb,
        dtype=torch.bfloat16, device_map={"": 0},
    )
    model.config.use_cache = False

    peft_config = LoraConfig(
        r=config.LORA_R, lora_alpha=config.LORA_ALPHA, lora_dropout=config.LORA_DROPOUT,
        bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )

    args = SFTConfig(
        output_dir=str(config.ADAPTER_DIR),
        per_device_train_batch_size=config.FT_BATCH,
        gradient_accumulation_steps=config.FT_GRAD_ACCUM,
        num_train_epochs=config.FT_EPOCHS,
        learning_rate=config.FT_LR,
        warmup_ratio=0.05, lr_scheduler_type="cosine",
        logging_steps=5, save_strategy="no",
        bf16=True, max_length=config.FT_MAX_LEN, packing=False,
        assistant_only_loss=True, report_to="none",
        # Mẫu dài ~3000 token: đánh đổi ~30% thời gian để không tràn bộ nhớ GPU.
        gradient_checkpointing=True,
    )

    trainer = SFTTrainer(
        model=model, args=args, train_dataset=ds,
        peft_config=peft_config, processing_class=tok,
    )
    trainer.train()

    config.ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(config.ADAPTER_DIR))
    tok.save_pretrained(str(config.ADAPTER_DIR))
    print(f"\n✅ Đã lưu LoRA adapter -> {config.ADAPTER_DIR}")
    print("   Kiểm thử: python src/Phase3-RAG/rag.py \"...\"  (rag tự nạp adapter)")


if __name__ == "__main__":
    main()
