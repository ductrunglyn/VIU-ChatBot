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

# Chat template có tag {% generation %} để đánh dấu token trả lời của trợ lý
# -> cho phép chỉ tính loss trên phần trả lời (assistant_only_loss).
#
# Khối <think></think> RỖNG là bắt buộc, không phải trang trí: lúc chạy thật
# rag.py gọi apply_chat_template(enable_thinking=False), và template của Qwen3
# sinh ra prefix '<|im_start|>assistant\n<think>\n\n</think>\n\n'. Huấn luyện mà
# thiếu khối này thì mô hình học sinh chữ ngay sau '<|im_start|>assistant\n',
# còn lúc suy luận lại bị đặt vào một vị trí khác hẳn -> lệch train/inference,
# đúng loại lỗi làm fine-tune mất tác dụng mà không báo lỗi gì.
_ASSISTANT_PREFIX = "<|im_start|>assistant\n<think>\n\n</think>\n\n"

_GEN_TEMPLATE = (
    "{%- for message in messages %}"
    "{%- if message.role == 'assistant' %}"
    # đưa cả <|im_end|> vào vùng {% generation %} để model HỌC được cách dừng
    "{{- '" + _ASSISTANT_PREFIX + "' }}{% generation %}{{ message.content + '<|im_end|>' }}{% endgeneration %}{{ '\n' }}"
    "{%- else %}"
    "{{- '<|im_start|>' + message.role + '\n' + message.content + '<|im_end|>\n' }}"
    "{%- endif %}"
    "{%- endfor %}"
    "{%- if add_generation_prompt %}{{- '" + _ASSISTANT_PREFIX + "' }}{%- endif %}"
)


def _callback_ghi_loss(duong_dan):
    """Ghi mỗi mốc log của Trainer thành một dòng JSON.

    Với `report_to="none"`, TRL 1.x KHÔNG in loss ra màn hình — đã kiểm chứng:
    chạy tới bước 36 mà trong nhật ký không có lấy một chữ "loss". Lượt train này
    dài ~7 giờ, không nhìn được loss thì tới cuối mới biết nó có học hay không (hay
    đã NaN từ bước 10). Ghi ra tệp để theo dõi được trong lúc chạy.
    """
    import json
    from transformers import TrainerCallback

    class GhiLoss(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kw):
            if not logs:
                return
            ban_ghi = {"step": state.global_step, **logs}
            with open(duong_dan, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")
            if "loss" in logs:
                print(f"[bước {state.global_step}] loss={logs['loss']:.4f} "
                      f"lr={logs.get('learning_rate', 0):.2e} "
                      f"epoch={logs.get('epoch', 0):.2f}", flush=True)

    return GhiLoss()


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

    # TRL 1.x đã bỏ `warmup_ratio`, chỉ còn `warmup_steps`. Tự quy đổi 5% thay vì
    # đóng cứng một con số, để đổi dữ liệu hay số epoch thì warmup vẫn đúng tỉ lệ.
    import math
    steps_moi_epoch = math.ceil(len(ds) / (config.FT_BATCH * config.FT_GRAD_ACCUM))
    tong_buoc = steps_moi_epoch * config.FT_EPOCHS
    warmup = max(1, round(tong_buoc * 0.05))
    print(f"  {steps_moi_epoch} bước/epoch × {config.FT_EPOCHS} epoch = {tong_buoc} bước "
          f"(warmup {warmup})")

    # Checkpoint để riêng, KHÔNG lẫn vào thư mục adapter cuối cùng (rag.py đọc
    # thẳng ADAPTER_DIR nên trộn checkpoint vào đó là tự chuốc rắc rối).
    run_dir = config.ADAPTER_DIR.parent / (config.ADAPTER_DIR.name + "-runs")

    args = SFTConfig(
        output_dir=str(run_dir),
        per_device_train_batch_size=config.FT_BATCH,
        gradient_accumulation_steps=config.FT_GRAD_ACCUM,
        num_train_epochs=config.FT_EPOCHS,
        learning_rate=config.FT_LR,
        warmup_steps=warmup, lr_scheduler_type="cosine",
        # Lưu sau mỗi epoch: lượt chạy dài ~7 giờ, mất điện hay OOM ở giờ thứ 6 mà
        # save_strategy="no" thì mất trắng toàn bộ. Giữ 3 bản để còn so epoch 2 với
        # epoch 3 — CLAUDE.md ghi số epoch từng là nút thắt chất lượng.
        logging_steps=5, save_strategy="epoch", save_total_limit=3,
        bf16=True, max_length=config.FT_MAX_LEN, packing=False,
        assistant_only_loss=True, report_to="none",
        # Mẫu dài (trung vị ~4400 token): đánh đổi ~30% thời gian để không tràn GPU.
        gradient_checkpointing=True,
        # Bản checkpointing "reentrant" hay làm đứt đường lan gradient khi model bị
        # đóng băng 4-bit rồi bọc LoRA (lỗi kinh điển "element 0 of tensors does
        # not require grad"). Bản non-reentrant không có vấn đề đó.
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )

    loss_file = config.ADAPTER_DIR.parent / "train_loss.jsonl"
    loss_file.unlink(missing_ok=True)
    trainer = SFTTrainer(
        model=model, args=args, train_dataset=ds,
        peft_config=peft_config, processing_class=tok,
        callbacks=[_callback_ghi_loss(loss_file)],
    )
    print(f"  Theo dõi loss: tail -f {loss_file}")
    trainer.train()

    config.ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(config.ADAPTER_DIR))
    tok.save_pretrained(str(config.ADAPTER_DIR))
    print(f"\n✅ Đã lưu LoRA adapter -> {config.ADAPTER_DIR}")
    print("   Kiểm thử: python src/Phase3-RAG/rag.py \"...\"  (rag tự nạp adapter)")


if __name__ == "__main__":
    main()
