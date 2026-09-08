#!/usr/bin/env bash
# Chuyển dự án ChatBot sang một server khác trong cùng mạng LAN.
#
# Dùng rsync chứ không phải scp: rsync chỉ gửi phần KHÁC NHAU nên chạy lại lần
# hai gần như tức thì, và đứt mạng giữa chừng thì chạy lại là tiếp tục chỗ dở.
#
# Cách dùng:
#     bash scripts/chuyen-sang-server.sh                # chỉ mã + dữ liệu (~205MB)
#     bash scripts/chuyen-sang-server.sh --model-web    # thêm 35GB mô hình ĐỂ CHẠY WEB
#     bash scripts/chuyen-sang-server.sh --model-all    # thêm cả kho HF (~70GB)
#     bash scripts/chuyen-sang-server.sh --thu          # chỉ xem sẽ gửi gì, không gửi
#
# Chạy web CẦN 3 mô hình (~35GB): Qwen3-14B soạn câu trả lời, bge-m3 để nhúng,
# bge-reranker-v2-m3 để xếp hạng lại.
#
# CẢNH BÁO: script này giả định máy đích ĐÃ CÓ conda + đã cài requirements.txt.
# Muốn máy đích không phải cài gì hết thì dùng scripts/dong-goi.sh — nó gói kèm
# cả môi trường Python nên bên kia chỉ việc chạy `bash chay.sh`.
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
    # Đúng 3 mô hình mà rag.py nạp lúc phục vụ. Kho HF còn ~35GB mô hình của các
    # dự án khác (whisper, phobert, wav2vec2...) — không liên quan, đừng gửi.
    MLOAI=(--include 'hub/' --include 'hub/models--Qwen--Qwen3-14B/***'
           --include 'hub/models--BAAI--bge-m3/***'
           --include 'hub/models--BAAI--bge-reranker-v2-m3/***'
           --exclude '*')
    echo; echo "==> Gửi 3 mô hình để CHẠY WEB (~35GB)"
  else
    echo; echo "==> Gửi toàn bộ kho mô hình (~70GB, kèm cả mô hình dự án khác)"
  fi
  rsync -az --info=progress2 --partial $KHO "${MLOAI[@]}" \
        "$HOME/.cache/huggingface/" "$DICH:~/.cache/huggingface/"
fi

# Bộ nhớ Claude Code được đánh khóa THEO ĐƯỜNG DẪN dự án, mà bên đích tên người
# dùng khác nên khóa cũng khác. Phải chuyển vào đúng thư mục tương ứng, nếu không
# phiên Claude Code mới bên đó sẽ không thấy gì.
NGUOI="${DICH%@*}"
KHOA="-home-${NGUOI}-${THU_MUC}"
BO_NHO="$HOME/.claude/projects/-home-hoangductrung-hdtrungoi/memory"
if [[ -d "$BO_NHO" && -z "$KHO" ]]; then
  echo
  echo "==> Gửi bộ nhớ Claude Code -> ~/.claude/projects/$KHOA/memory"
  ssh "$DICH" "mkdir -p ~/.claude/projects/$KHOA/memory"
  rsync -az "$BO_NHO/" "$DICH:~/.claude/projects/$KHOA/memory/"
fi

echo
echo "✅ Xong. Trên server đích:"
echo "     conda create -n ChatBot python=3.10 -y && conda activate ChatBot"
echo "     cd ~/$THU_MUC/ChatBot && pip install -r requirements.txt"

echo "     bash scripts/chay-web.sh               # tự dò env, kiểm tra, mở cổng 7860"
echo
echo "  (chỉ khi cần train lại: python src/Phase4-Finetuning/build_dataset.py)"
