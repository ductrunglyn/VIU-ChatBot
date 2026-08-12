#!/usr/bin/env bash
# Chuyển dự án ChatBot sang một server khác trong cùng mạng LAN.
#
# Dùng rsync chứ không phải scp: rsync chỉ gửi phần KHÁC NHAU nên chạy lại lần
# hai gần như tức thì, và đứt mạng giữa chừng thì chạy lại là tiếp tục chỗ dở.
#
# Cách dùng:
#     bash scripts/chuyen-sang-server.sh                # chỉ mã + dữ liệu (249MB)
#     bash scripts/chuyen-sang-server.sh --model-web    # thêm 13GB mô hình ĐỂ CHẠY WEB
#     bash scripts/chuyen-sang-server.sh --model-all    # thêm cả 41GB (kèm Qwen3-14B)
#     bash scripts/chuyen-sang-server.sh --thu          # chỉ xem sẽ gửi gì, không gửi
#
# Chạy web CHỈ CẦN 3 mô hình (13GB): Qwen2.5-3B-Instruct làm nền, bge-m3 để nhúng,
# bge-reranker-v2-m3 để xếp hạng lại. Qwen3-14B nặng 28GB nhưng chỉ dùng lúc tinh
# chỉnh dữ liệu, KHÔNG dính gì tới việc phục vụ — đừng chép nếu chỉ để chạy web.
set -euo pipefail

DICH="${DICH:-hoangtrung@192.168.88.31}"
THU_MUC="${THU_MUC:-hdtrungoi}"
GOC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODEL=""
KHO=""
for a in "$@"; do
  case "$a" in
    --model-web) MODEL="web" ;;
    --model-all) MODEL="all" ;;
    --thu)       KHO="--dry-run" ;;
    *) echo "Tham số lạ: $a"; exit 1 ;;
  esac
done

# Những thứ KHÔNG gửi. Lý do từng dòng:
#   __pycache__  - Python tự sinh lại, gửi đi chỉ tổ lệch phiên bản
#   *.bak.csv    - bản sao lưu trung gian, tái tạo được từ bộ sinh
#   train.jsonl  - 21MB, dựng lại bằng build_dataset.py trong 2 phút
#   *_tinh.csv   - ĐANG được ghi dở nếu bộ tinh chỉnh còn chạy
#
# CÓ gửi data/vectordb dù dựng lại được: chỉ 4,3MB, mà dựng lại phải nạp bge-m3
# và cần GPU. Gửi kèm thì server đích chạy web được ngay, khỏi thêm một bước.
LOAI=(
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude '.git/'
  --exclude 'data/qa/*.bak.csv'
  --exclude 'data/qa/train.jsonl'
  --exclude 'models/qlora-viu.ep2/'
  --exclude 'models/qlora-viu.v3/'
)

if pgrep -f refine_qa_llm > /dev/null; then
  echo "⚠️  Bộ tinh chỉnh đang chạy — BỎ QUA các tệp *_tinh.csv đang ghi dở."
  echo "    Chạy lại script này sau khi nó xong để đồng bộ nốt."
  LOAI+=(--exclude 'data/qa/*_tinh.csv')
fi

echo "Nguồn : $GOC"
echo "Đích  : $DICH:~/$THU_MUC/ChatBot"
echo

ssh -o BatchMode=yes -o ConnectTimeout=8 "$DICH" "mkdir -p ~/$THU_MUC" 2>/dev/null || {
  echo "❌ Chưa đăng nhập được bằng khoá. Chạy MỘT LẦN lệnh sau rồi thử lại:"
  echo "     ssh-copy-id $DICH"
  exit 1
}

echo "==> Gửi mã nguồn và dữ liệu"
rsync -az --info=progress2 --partial $KHO "${LOAI[@]}" \
      "$GOC/" "$DICH:~/$THU_MUC/ChatBot/"

if [[ -n "$MODEL" ]]; then
  MLOAI=()
  if [[ "$MODEL" == "web" ]]; then
    # Chỉ 3 mô hình cần để phục vụ. Bỏ Qwen3-14B (28GB) vì nó chỉ dùng lúc tinh
    # chỉnh dữ liệu — chép sang server chạy web là phí băng thông lẫn ổ đĩa.
    MLOAI=(--include 'hub/' --include 'hub/models--Qwen--Qwen2.5-3B-Instruct/***'
           --include 'hub/models--BAAI--bge-m3/***'
           --include 'hub/models--BAAI--bge-reranker-v2-m3/***'
           --exclude '*')
    echo; echo "==> Gửi 3 mô hình để CHẠY WEB (~13GB)"
  else
    echo; echo "==> Gửi toàn bộ kho mô hình (~41GB, kèm Qwen3-14B để tinh chỉnh)"
  fi
  rsync -az --info=progress2 --partial $KHO "${MLOAI[@]}" \
        "$HOME/.cache/huggingface/" "$DICH:~/.cache/huggingface/"
fi

echo
echo "✅ Xong. Trên server đích:"
echo "     conda create -n test python=3.10 -y && conda activate test"
echo "     cd ~/$THU_MUC/ChatBot && pip install -r requirements.txt"
echo "     screen -S ChatBot"
echo "     python src/Phase5-UI/app.py            # mở http://<IP-server>:7860"
echo
echo "  (chỉ khi cần train lại: python src/Phase4-Finetuning/build_dataset.py)"
