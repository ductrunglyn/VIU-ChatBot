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
CONG=7860          # phải khớp UI_PORT trong src/common/config.py

# Gradio mặc định ghi tệp tạm vào /tmp/gradio. Trên máy nhiều người dùng, thư mục
# đó do người CHẠY TRƯỚC tạo và mang quyền của họ -> ta không tạo được thư mục con
# và web chết bằng "PermissionError: /tmp/gradio/<hash>". Lỗi này xuất hiện SAU khi
# log đã in "Sẵn sàng", nên script tưởng chạy thành công trong khi cổng 7860 chưa
# hề mở. Trỏ sang thư mục tạm của chính dự án để khỏi tranh chấp.
export GRADIO_TEMP_DIR="${GRADIO_TEMP_DIR:-$GOC/.gradio_tmp}"
mkdir -p "$GRADIO_TEMP_DIR"

# Card DÙNG CHUNG với việc khác trên máy. Đã gặp: một job train khác chiếm
# 18,5 GB, web còn 13,5 GB và chết OOM ngay lúc nạp model. Bật cấp phát bộ nhớ
# co giãn để bớt phân mảnh — đo được đỉnh tụt từ 13,9 GB xuống 13,05 GB, vừa đủ.
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

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
  echo "✅ Web đang chạy rồi: http://$(hostname -I | awk '{print $1}'):${CONG}"
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

# Adapter chỉ dùng được khi khớp base model. Đọc thẳng adapter_config.json thay vì
# chỉ xem thư mục có tồn tại — bản cũ train trên Qwen2.5-3B từng khiến script báo
# "có adapter" trong khi rag.py phải bỏ qua vì không nạp được vào 14B.
# Nay adapter đã khớp base nhưng USE_FINETUNED=False vì đo được nó kém hơn model gốc,
# nên phải xem cả cờ đó mới báo đúng cái đang thực sự chạy.
ADAPTER_CFG="$GOC/models/qlora-viu/adapter_config.json"
if [[ -f "$ADAPTER_CFG" ]]; then
  BASE=$(grep -o '"base_model_name_or_path"[^,]*' "$ADAPTER_CFG" | cut -d'"' -f4)
  DUNG=$(grep -E "^USE_FINETUNED" "$GOC/src/common/config.py" | tail -1 | grep -c True)
  if [[ "$BASE" == "Qwen/Qwen3-14B" && "$DUNG" == "1" ]]; then
    echo "  ✓ Adapter fine-tune: ĐANG DÙNG (khớp base)"
  elif [[ "$BASE" == "Qwen/Qwen3-14B" ]]; then
    # Adapter khớp base nhưng bị tắt có chủ đích: đo được nó KÉM HƠN model gốc.
    echo "  ✓ Chạy MODEL GỐC (USE_FINETUNED=False — adapter có nhưng đã tắt, xem CLAUDE.md)"
  else
    echo "  ⚠ Adapter qlora-viu train trên '$BASE', không khớp Qwen3-14B -> chạy MODEL GỐC"
  fi
else
  echo "  ⚠ Chưa có models/qlora-viu — chạy model GỐC"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  TRONG=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
  echo "  ✓ GPU trống: ${TRONG} MiB"
  # Đo thực tế: Qwen3-14B NF4 + BGE-M3 + reranker đỉnh 13,9 GB. Lấy 15000 làm mức
  # cảnh báo để còn dư cho ngữ cảnh dài.
  (( TRONG < 15000 )) && echo "     ⚠ dưới 15000 MiB, dễ tràn với 14B. Xem ai đang chiếm: nvidia-smi"
else
  echo "  ⚠ Không có nvidia-smi — chạy bằng CPU, mỗi câu trả lời sẽ mất vài PHÚT"
fi

echo
echo "== Khởi động (nạp model mất ~1 phút) =="
cd "$GOC"
screen -dmS "$PHIEN" bash -c "$PY src/Phase5-UI/app.py 2>&1 | tee '$NHAT_KY'"

# Căn cứ "đã lên" phải là CỔNG ĐANG MỞ, không phải dòng log "Sẵn sàng": app.py in
# dòng đó TRƯỚC khi gọi launch(), nên khi launch() ném lỗi (đã gặp: PermissionError
# ở /tmp/gradio) script vẫn báo thành công còn cổng 7860 chưa hề mở — đúng cảnh
# "web báo chạy mà không vào được".
dang_mo() { ss -tln 2>/dev/null | grep -q ":${CONG} "; }

for _ in $(seq 60); do
  sleep 2
  dang_mo && break
  grep -qiE "Traceback|OutOfMemory|Error" "$NHAT_KY" 2>/dev/null && {
    echo "❌ Lỗi khi khởi động:"; tail -15 "$NHAT_KY"; exit 1; }
done

if dang_mo; then
  echo "✅ Web đã lên: http://$(hostname -I | awk '{print $1}'):${CONG}"
  echo "   Nhật ký : bash scripts/chay-web.sh --xem"
  echo "   Dừng    : bash scripts/chay-web.sh --dung"
else
  echo "⚠ Quá 2 phút chưa thấy báo sẵn sàng. Xem nhật ký:"; tail -15 "$NHAT_KY"
fi
