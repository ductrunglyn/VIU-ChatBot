#!/usr/bin/env bash
# Khởi động web chatbot trong screen, kiểm tra sẵn các điều kiện dễ hỏng.
#
#     bash scripts/chay-web.sh          # khởi động (hoặc báo nếu đã chạy)
#     bash scripts/chay-web.sh --dung   # dừng
#     bash scripts/chay-web.sh --xem    # xem nhật ký đang chạy
set -uo pipefail

GOC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PHIEN="ChatBot"
NHAT_KY="$GOC/web.log"
PY="${PY:-$HOME/miniconda3/envs/test/bin/python}"

case "${1:-}" in
  --dung)
    screen -S "$PHIEN" -X quit 2>/dev/null
    pkill -f "src/Phase5-UI/app.py" 2>/dev/null
    sleep 2
    pgrep -f "src/Phase5-UI/app.py" >/dev/null && echo "⚠ vẫn còn chạy" || echo "✅ đã dừng web"
    exit 0 ;;
  --xem)
    tail -f "$NHAT_KY"; exit 0 ;;
esac

if pgrep -f "src/Phase5-UI/app.py" > /dev/null; then
  echo "✅ Web đang chạy rồi: http://$(hostname -I | awk '{print $1}'):7860"
  echo "   Xem nhật ký: bash scripts/chay-web.sh --xem"
  exit 0
fi

echo "== Kiểm tra trước khi chạy =="

[[ -x "$PY" ]] || { echo "❌ Không thấy Python của env 'test' ở $PY"
                    echo "   Tạo bằng: conda create -n test python=3.10 -y"; exit 1; }
echo "  ✓ Python: $PY"

# Vectordb thiếu thì RAG không truy xuất được gì, mà lỗi lại chỉ lộ ra lúc hỏi
# câu đầu tiên — kiểm trước để khỏi tưởng web chạy tốt.
if [[ ! -d "$GOC/data/vectordb" ]] || [[ -z "$(ls -A "$GOC/data/vectordb" 2>/dev/null)" ]]; then
  echo "❌ Thiếu data/vectordb. Dựng lại bằng:"
  echo "     $PY src/Phase2-Embedding/embed.py"
  exit 1
fi
echo "  ✓ Kho vector: $(du -sh "$GOC/data/vectordb" | cut -f1)"

if [[ -d "$GOC/models/qlora-viu" ]]; then
  echo "  ✓ Adapter fine-tune: có"
else
  echo "  ⚠ Chưa có models/qlora-viu — web vẫn chạy nhưng dùng model GỐC, chất lượng kém hơn hẳn"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  TRONG=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
  echo "  ✓ GPU trống: ${TRONG} MiB"
  # Cần ~7,5GB: Qwen2.5-3B 4-bit + BGE-M3 + reranker + bộ nhớ đệm.
  (( TRONG < 8000 )) && echo "     ⚠ dưới 8000 MiB, dễ tràn. Xem ai đang chiếm: nvidia-smi"
else
  echo "  ⚠ Không có nvidia-smi — chạy bằng CPU, mỗi câu trả lời sẽ mất vài PHÚT"
fi

echo
echo "== Khởi động (nạp model mất ~1 phút) =="
cd "$GOC"
screen -dmS "$PHIEN" bash -c "$PY src/Phase5-UI/app.py 2>&1 | tee '$NHAT_KY'"

for _ in $(seq 60); do
  sleep 2
  grep -q "Sẵn sàng" "$NHAT_KY" 2>/dev/null && break
  grep -qiE "Traceback|OutOfMemory|Error" "$NHAT_KY" 2>/dev/null && {
    echo "❌ Lỗi khi khởi động:"; tail -15 "$NHAT_KY"; exit 1; }
done

if grep -q "Sẵn sàng" "$NHAT_KY" 2>/dev/null; then
  echo "✅ Web đã lên: http://$(hostname -I | awk '{print $1}'):7860"
  echo "   Nhật ký : bash scripts/chay-web.sh --xem"
  echo "   Dừng    : bash scripts/chay-web.sh --dung"
else
  echo "⚠ Quá 2 phút chưa thấy báo sẵn sàng. Xem nhật ký:"; tail -15 "$NHAT_KY"
fi
