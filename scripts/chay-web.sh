#!/usr/bin/env bash
# Khởi động web chatbot trong screen, kiểm tra sẵn các điều kiện dễ hỏng.
#
#     bash scripts/chay-web.sh          # khởi động (hoặc báo nếu đã chạy)
#     bash scripts/chay-web.sh --dung   # dừng
#     bash scripts/chay-web.sh --xem    # xem nhật ký đang chạy
#
# Tên môi trường conda KHÁC NHAU giữa các máy (máy này 'test', máy khác 'ChatBot'),
# nên script tự dò thay vì đóng cứng. Muốn chỉ định thẳng:
#     ENV=tên_env bash scripts/chay-web.sh
#     PY=/đường/dẫn/python bash scripts/chay-web.sh
set -uo pipefail

GOC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PHIEN="ChatBot"
NHAT_KY="$GOC/web.log"

du_goi() { [[ -x "$1" ]] && "$1" -c "import gradio, torch" 2>/dev/null; }

# Liệt kê mọi env conda. HỎI THẲNG CONDA thay vì đoán vị trí cài: bản trước dò
# cứng 4 thư mục ($HOME/miniconda3, anaconda3, miniforge3, /opt/conda) nên máy
# nào cài chỗ khác là trượt, kể cả khi đã chỉ đúng tên env.
liet_ke_env() {
  local conda="${CONDA_EXE:-}"
  [[ -x "$conda" ]] || conda="$(command -v conda 2>/dev/null || true)"
  if [[ -z "$conda" ]]; then
    for g in "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniforge3" \
             "$HOME/mambaforge" "$HOME/conda" "/opt/conda" "/usr/local/conda"; do
      [[ -x "$g/bin/conda" ]] && { conda="$g/bin/conda"; break; }
    done
  fi
  # `conda env list` in ra: "tên   *   /đường/dẫn" (dấu * là env đang bật)
  [[ -x "$conda" ]] && "$conda" env list 2>/dev/null \
    | awk '!/^#/ && NF {print $NF}' | grep '^/' || true
  # Dự phòng khi không gọi được conda: quét thư mục envs
  for g in "$HOME"/miniconda3 "$HOME"/anaconda3 "$HOME"/miniforge3 \
           "$HOME"/mambaforge "/opt/conda"; do
    [[ -d "$g/envs" ]] && find "$g/envs" -maxdepth 1 -mindepth 1 -type d 2>/dev/null
  done
  # Luôn trả 0. Thư mục cuối không tồn tại thì vòng lặp trả mã lỗi, mà script bật
  # `pipefail` nên cả ống dẫn thành lỗi -> nhánh "||" phía sau bắn nhầm, in ra
  # "không dò được env nào" ngay bên dưới danh sách env vừa liệt kê.
  return 0
}

tim_python() {
  # 1. Người dùng chỉ định thẳng đường dẫn python
  [[ -n "${PY:-}" ]] && { echo "$PY"; return; }

  local envs; envs="$(liet_ke_env | sort -u)"

  # 2. Chỉ định tên env -> tìm env có tên khớp
  if [[ -n "${ENV:-}" ]]; then
    while read -r d; do
      [[ "$(basename "$d")" == "$ENV" && -x "$d/bin/python" ]] && {
        echo "$d/bin/python"; return; }
    done <<< "$envs"
    echo ""; return
  fi

  # Từ đây trở xuống phải THỰC SỰ import được gradio + torch mới nhận. Không kiểm
  # thì vớ ngay env base: đã đo, base được chọn trước cả env đúng vì CONDA_PREFIX
  # trỏ vào đấy, rồi web chết lúc nạp model chứ không báo ở bước kiểm tra này.

  # 3. Đang ở trong env sẵn rồi
  du_goi "${CONDA_PREFIX:-}/bin/python" && { echo "$CONDA_PREFIX/bin/python"; return; }

  # 4. Ưu tiên các tên hay dùng
  for ten in ChatBot chatbot test viu; do
    while read -r d; do
      [[ "$(basename "$d")" == "$ten" ]] && du_goi "$d/bin/python" && {
        echo "$d/bin/python"; return; }
    done <<< "$envs"
  done

  # 5. Bí quá thì quét hết
  while read -r d; do
    du_goi "$d/bin/python" && { echo "$d/bin/python"; return; }
  done <<< "$envs"

  echo ""
}

PY="$(tim_python)"

case "${1:-}" in
  --python)
    # Chỉ in đường dẫn Python dò được rồi thoát. Để script khác (tinh-chinh.sh)
    # dùng lại đúng bộ dò này thay vì chép logic sang chỗ thứ hai.
    [[ -n "$PY" ]] && { echo "$PY"; exit 0; } || exit 1 ;;
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

[[ -n "$PY" && -x "$PY" ]] || {
  if [[ -n "${ENV:-}" ]]; then
    echo "❌ Không tìm thấy env tên '$ENV'."
  else
    echo "❌ Không env nào có đủ gradio + torch."
  fi
  echo "   Các env tìm thấy trên máy này:"
  liet_ke_env | sort -u | sed 's|^|     |' || echo "     (không dò được env nào)"
  echo
  echo "   Cách xử lý:"
  echo "     ENV=<tên> bash scripts/chay-web.sh       # chỉ định tên env"
  echo "     PY=/đường/dẫn/bin/python bash scripts/chay-web.sh   # chỉ định thẳng"
  exit 1; }

# Env chỉ định bằng ENV chưa chắc đã cài gói — kiểm và nói rõ thiếu gì, thay vì
# để web chết lúc nạp model.
du_goi "$PY" || {
  echo "❌ Env này thiếu gói: $PY"
  "$PY" -c "import gradio" 2>&1 | tail -1 | sed 's|^|     |'
  echo "   Cài bằng: $PY -m pip install -r requirements.txt"
  exit 1; }
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
