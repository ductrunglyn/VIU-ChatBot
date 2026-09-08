#!/usr/bin/env bash
# Đóng gói TOÀN BỘ hệ thống thành một thư mục tự chạy được trên máy khác.
#
# Gói ra gồm 4 phần, máy đích KHÔNG cần cài gì thêm:
#   moi-truong.tar.gz  môi trường Python đã cài sẵn (torch, gradio, transformers...)
#   hf/                3 mô hình AI (Qwen3-14B, bge-m3, bge-reranker-v2-m3)
#   ChatBot/           mã nguồn + dữ liệu + kho vector + adapter
#   bin/cloudflared    để mở link public
#
#     bash scripts/dong-goi.sh --thu              # chỉ tính dung lượng, KHÔNG chép
#     bash scripts/dong-goi.sh                    # đóng gói vào ~/goi-chatbot
#     bash scripts/dong-goi.sh --dich /mnt/usb/goi
#     bash scripts/dong-goi.sh --gon              # bỏ file trọng số trùng lặp (-2,2GB)
#     bash scripts/dong-goi.sh --nen              # nén cả gói thành 1 tệp .tar
#
# Máy đích chỉ cần: Linux x86_64 + driver NVIDIA đủ mới + GPU trống ~15GB.
set -uo pipefail

GOC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DICH="$HOME/goi-chatbot"
THU=0; GON=0; NEN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --thu)  THU=1 ;;
    --gon)  GON=1 ;;
    --nen)  NEN=1 ;;
    --dich) DICH="${2:?thiếu đường dẫn sau --dich}"; shift ;;
    *) echo "Tham số lạ: $1"; exit 1 ;;
  esac
  shift
done

# ── Tìm môi trường conda đang dùng ────────────────────────────────────────────
# Không đóng cứng tên env: máy thầy Trung là 'test', server là 'ChatBot'.
tim_env() {
  [[ -n "${ENV_GOC:-}" ]] && { echo "$ENV_GOC"; return; }
  local conda="${CONDA_EXE:-}"
  [[ -x "$conda" ]] || conda="$(command -v conda 2>/dev/null || true)"
  [[ -x "$conda" ]] || conda="$HOME/miniconda3/bin/conda"
  [[ -x "$conda" ]] || { echo ""; return; }
  "$conda" env list 2>/dev/null | awk '!/^#/ && NF {print $NF}' | grep '^/' \
    | while read -r d; do
        [[ -x "$d/bin/python" ]] && "$d/bin/python" -c "import gradio, torch" 2>/dev/null \
          && { echo "$d"; break; }
      done
}

ENV_DIR="$(tim_env)"
[[ -n "$ENV_DIR" ]] || {
  echo "❌ Không tìm thấy môi trường nào có đủ gradio + torch."
  echo "   Chỉ định thẳng: ENV_GOC=/đường/dẫn/envs/ChatBot bash scripts/dong-goi.sh"
  exit 1; }

# ── Đọc tên 3 mô hình THẲNG TỪ config.py ──────────────────────────────────────
# Không chép cứng tên model vào đây: đổi LLM_MODEL trong config mà quên sửa script
# thì gói ra sẽ thiếu đúng cái model đang dùng, và chỉ vỡ lở khi đã sang máy khác.
doc_model() {
  "$ENV_DIR/bin/python" - "$GOC" <<'PY'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / "src" / "common"))
import config
for m in (config.LLM_MODEL, config.EMBED_MODEL, config.RERANK_MODEL):
    print("models--" + m.replace("/", "--"))
PY
}
mapfile -t MODELS < <(doc_model)
[[ ${#MODELS[@]} -eq 3 ]] || { echo "❌ Không đọc được tên mô hình từ config.py"; exit 1; }

HF_GOC="${HF_HOME:-$HOME/.cache/huggingface}"

echo "=============================================="
echo " ĐÓNG GÓI CHATBOT VIU"
echo "=============================================="
echo "Môi trường : $ENV_DIR"
echo "Kho mô hình: $HF_GOC/hub"
echo "Gói ra     : $DICH"
echo

# ── Kiểm tra đủ mô hình chưa ──────────────────────────────────────────────────
TONG_MODEL=0
echo "Mô hình cần mang theo:"
for m in "${MODELS[@]}"; do
  d="$HF_GOC/hub/$m"
  if [[ -d "$d" ]]; then
    kb=$(du -sk "$d" | cut -f1); TONG_MODEL=$((TONG_MODEL + kb))
    printf "  ✓ %-42s %6s\n" "$m" "$(du -sh "$d" | cut -f1)"
  else
    printf "  ✗ %-42s THIẾU\n" "$m"
    echo; echo "❌ Chưa có mô hình này trong cache. Chạy web một lần để nó tự tải về."
    exit 1
  fi
done

ENV_KB=$(du -sk "$ENV_DIR" | cut -f1)
DA_KB=$(du -sk --exclude=.git --exclude=__pycache__ --exclude=.gradio_tmp "$GOC" | cut -f1)
TONG_KB=$((TONG_MODEL + ENV_KB + DA_KB))

echo
printf "  môi trường Python  %8s\n" "$(du -sh "$ENV_DIR" | cut -f1)"
printf "  mã nguồn + dữ liệu %8s\n" "$((DA_KB / 1024))M"
printf "  ─────────────────────────\n"
printf "  TỔNG (chưa nén)    %8s\n" "$((TONG_KB / 1024 / 1024))G"
echo

TRONG_KB=$(df -Pk "$(dirname "$DICH")" | tail -1 | awk '{print $4}')
echo "Chỗ trống tại đích: $((TRONG_KB / 1024 / 1024))G"
if (( TRONG_KB < TONG_KB + 2097152 )); then
  echo "❌ Không đủ chỗ. Cần ít nhất $(( (TONG_KB + 2097152) / 1024 / 1024 ))G."
  exit 1
fi

if (( THU )); then
  echo
  echo "(chế độ --thu: dừng ở đây, chưa chép gì)"
  exit 0
fi

echo
mkdir -p "$DICH"/{hf/hub,bin}

# ── 1. Môi trường Python ──────────────────────────────────────────────────────
# conda-pack thay vì tar thẳng: nó viết lại các đường dẫn tuyệt đối bị nhúng
# trong shebang và file cấu hình, nên env bung ra ở thư mục nào cũng chạy.
echo "==> [1/4] Đóng gói môi trường Python (lâu nhất, ~5-15 phút)"
if [[ -f "$DICH/moi-truong.tar.gz" ]]; then
  echo "    (đã có, bỏ qua — xoá tệp đó nếu muốn đóng lại)"
else
  "$ENV_DIR/bin/python" -c "import conda_pack" 2>/dev/null || {
    echo "    cài conda-pack..."
    "$ENV_DIR/bin/pip" install -q conda-pack || { echo "❌ Không cài được conda-pack"; exit 1; }
  }
  "$ENV_DIR/bin/python" -m conda_pack --prefix "$ENV_DIR" \
      --output "$DICH/moi-truong.tar.gz" \
      --ignore-missing-files --ignore-editable-packages --force \
    || { echo "❌ conda-pack thất bại"; exit 1; }
fi

# ── 2. Mô hình ────────────────────────────────────────────────────────────────
echo "==> [2/4] Chép mô hình (~$((TONG_MODEL / 1024 / 1024))G, chạy lại được nếu đứt)"
for m in "${MODELS[@]}"; do
  echo "    $m"
  rsync -a --partial --info=progress2 "$HF_GOC/hub/$m" "$DICH/hf/hub/" \
    || { echo "❌ Chép mô hình thất bại"; exit 1; }
done

# Kho HF giữ trọng số ở blobs/ và trỏ symlink từ snapshots/. Một số model có CẢ
# .bin lẫn .safetensors cùng nội dung; transformers chỉ đọc .safetensors nên
# bản .bin là thừa. Phải xoá cả symlink LẪN blob thật, xoá mỗi symlink không
# giảm được byte nào.
if (( GON )); then
  echo "==> Bỏ trọng số trùng lặp"
  while IFS= read -r bin_link; do
    thu_muc="$(dirname "$bin_link")"
    [[ -e "$thu_muc/model.safetensors" ]] || continue
    blob="$(readlink -f "$bin_link" 2>/dev/null)"
    rm -f "$bin_link"
    [[ -n "$blob" && "$blob" == *"/blobs/"* ]] && rm -f "$blob"
    echo "    bỏ ${thu_muc##*/hub/}/pytorch_model.bin"
  done < <(find "$DICH/hf/hub" -name 'pytorch_model.bin')
fi

# ── 3. Mã nguồn + dữ liệu ─────────────────────────────────────────────────────
echo "==> [3/4] Chép mã nguồn, dữ liệu, kho vector"
rsync -a --partial \
      --exclude '.git/' --exclude '__pycache__/' --exclude '*.pyc' \
      --exclude '.gradio_tmp/' --exclude '*.log' \
      --exclude 'data/qa/sao-luu/' \
      "$GOC/" "$DICH/ChatBot/" \
  || { echo "❌ Chép mã nguồn thất bại"; exit 1; }

# ── 4. cloudflared ────────────────────────────────────────────────────────────
echo "==> [4/4] Chép cloudflared"
CF="$(command -v cloudflared || echo "$HOME/bin/cloudflared")"
if [[ -x "$CF" ]]; then
  cp -f "$CF" "$DICH/bin/cloudflared"; chmod +x "$DICH/bin/cloudflared"
else
  echo "    ⚠ Không thấy cloudflared — máy đích sẽ không mở được link public."
  echo "      Tải sau bằng: curl -L -o bin/cloudflared \\"
  echo "        https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
fi

# ── Script chạy trên máy đích ─────────────────────────────────────────────────
# Heredoc trích dẫn ('CHAY') để KHÔNG có biến nào bị thay giá trị lúc đóng gói —
# mọi thứ trong đây phải được tính lúc chạy trên máy đích.
cat > "$DICH/chay.sh" <<'CHAY'
#!/usr/bin/env bash
# Chạy Chatbot VIU trên máy này. Không cần cài gì thêm.
#
#     bash chay.sh          # bật web + tunnel, in ra link public
#     bash chay.sh --dung   # tắt cả hai
#     bash chay.sh --xem    # xem nhật ký web
set -uo pipefail

GOI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MT="$GOI/moi-truong"
DA="$GOI/ChatBot"
CONG=7860

case "${1:-}" in
  --dung)
    screen -S CFTunnel -X quit 2>/dev/null
    bash "$DA/scripts/chay-web.sh" --dung
    exit 0 ;;
  --xem) tail -f "$DA/web.log"; exit 0 ;;
esac

# ── Lần đầu: bung môi trường ──────────────────────────────────────────────────
if [[ ! -x "$MT/bin/python" ]]; then
  echo "==> Lần chạy đầu: bung môi trường Python (~2-5 phút, chỉ một lần)"
  mkdir -p "$MT"
  tar -xzf "$GOI/moi-truong.tar.gz" -C "$MT" || { echo "❌ Bung thất bại"; exit 1; }
  # Sửa lại đường dẫn tuyệt đối bị nhúng lúc đóng gói ở máy nguồn.
  "$MT/bin/conda-unpack" 2>/dev/null || true
  echo "    xong"
fi

# ── Kiểm tra máy đích có chạy nổi không ───────────────────────────────────────
echo "== Kiểm tra máy này =="
command -v nvidia-smi >/dev/null 2>&1 || {
  echo "❌ Không có nvidia-smi. Máy này chưa cài driver NVIDIA — không chạy được."
  exit 1; }

DRV=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)
if [[ -z "$DRV" ]]; then
  echo "❌ nvidia-smi không nói chuyện được với driver. Kiểm tra lại driver/GPU."
  exit 1
fi
# torch trong gói build cho CUDA 12.8 -> driver phải từ 525 trở lên.
if (( ${DRV%%.*} < 525 )); then
  echo "❌ Driver $DRV quá cũ. Gói này cần CUDA 12.8, tức driver >= 525."
  exit 1
fi
echo "  ✓ Driver NVIDIA: $DRV"

TRONG=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
echo "  ✓ GPU trống: ${TRONG} MiB"
(( TRONG < 15000 )) && {
  echo "     ⚠ dưới 15000 MiB — Qwen3-14B cần ~14GB, dễ tràn."
  echo "       Xem ai đang chiếm: nvidia-smi"; }

GLIBC=$(ldd --version | head -1 | grep -oE '[0-9]+\.[0-9]+$')
echo "  ✓ glibc: $GLIBC (gói đóng trên 2.39)"

# ── Trỏ mọi thứ vào trong gói, không đụng thư mục nhà của máy đích ────────────
export HF_HOME="$GOI/hf"          # transformers tìm mô hình ở đây
export HF_HUB_OFFLINE=1           # cấm gọi mạng: mô hình đã có sẵn trong gói
export TRANSFORMERS_OFFLINE=1
export GRADIO_TEMP_DIR="$DA/.gradio_tmp"
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export PATH="$GOI/bin:$PATH"

echo
PY="$MT/bin/python" bash "$DA/scripts/chay-web.sh" || exit 1

# ── Tunnel ────────────────────────────────────────────────────────────────────
echo
echo "== Mở link public =="
command -v cloudflared >/dev/null 2>&1 || {
  echo "⚠ Không có cloudflared trong gói — chỉ dùng được trong mạng nội bộ."
  exit 0; }

screen -S CFTunnel -X quit 2>/dev/null
rm -f "$DA/tunnel.log"
screen -dmS CFTunnel bash -c \
  "cloudflared tunnel --url http://127.0.0.1:$CONG 2>&1 | tee '$DA/tunnel.log'"

URL=""
for _ in $(seq 20); do
  sleep 2
  URL=$(grep -o 'https://[a-z-]*\.trycloudflare\.com' "$DA/tunnel.log" 2>/dev/null | head -1)
  [[ -n "$URL" ]] && break
done

echo
if [[ -n "$URL" ]]; then
  echo "╔══════════════════════════════════════════════════════════╗"
  echo "  Link public : $URL"
  echo "  Mạng nội bộ : http://$(hostname -I | awk '{print $1}'):$CONG"
  echo "╚══════════════════════════════════════════════════════════╝"
  echo "  Link public ĐỔI MỚI mỗi lần chạy lại. Tắt: bash chay.sh --dung"
else
  echo "⚠ Chưa lấy được link sau 40 giây. Xem: cat $DA/tunnel.log"
  echo "  Web vẫn chạy trong mạng nội bộ: http://$(hostname -I | awk '{print $1}'):$CONG"
fi
CHAY
chmod +x "$DICH/chay.sh"

# ── Hướng dẫn kèm gói ─────────────────────────────────────────────────────────
cat > "$DICH/DOC-TRUOC.md" <<'DOC'
# Chatbot cố vấn học tập VIU — gói chạy sẵn

Chép cả thư mục này sang máy mới rồi chạy **một lệnh duy nhất**:

```bash
bash chay.sh
```

Lần đầu mất thêm 2–5 phút để bung môi trường. Xong nó in ra link public.

```bash
bash chay.sh --dung    # tắt web + tunnel
bash chay.sh --xem     # xem nhật ký
```

## Máy đích cần gì

| | |
|---|---|
| Hệ điều hành | Linux x86_64 (Ubuntu 22.04 trở lên) |
| Driver NVIDIA | từ 525 trở lên (`nvidia-smi` phải chạy được) |
| GPU | trống ~15GB |
| Đĩa | ~50GB |
| Internet | **không cần** cho web; chỉ cần nếu muốn link public |
| Quyền root | **không cần** |
| Cài đặt | **không cần** — không conda, không pip, không tải model |

## Trong gói có gì

| Phần | Nội dung |
|---|---|
| `moi-truong.tar.gz` | Python + torch + gradio + transformers, cài sẵn |
| `hf/` | 3 mô hình AI: Qwen3-14B, bge-m3, bge-reranker-v2-m3 |
| `ChatBot/` | mã nguồn, dữ liệu, kho vector đã nhúng |
| `bin/cloudflared` | mở link public |

Gói tự chứa hoàn toàn: mô hình đọc từ `hf/` trong gói, không đụng và không
làm bẩn thư mục nhà của máy đích.

## Hỏng thì xem đâu

| Hiện tượng | Nguyên nhân thường gặp |
|---|---|
| `Driver ... quá cũ` | máy đích cần driver >= 525 |
| `nvidia-smi không nói chuyện được` | driver lỗi/chưa nạp, cần người có root |
| Web lên nhưng trả lời sai/thiếu | thiếu `ChatBot/data/vectordb` — chép lại cho đủ |
| Không có link public | thiếu `bin/cloudflared`, hoặc máy chặn ra Internet |
DOC

echo
echo "=============================================="
echo " ✅ ĐÓNG GÓI XONG"
echo "=============================================="
du -sh "$DICH"
echo
echo "Gói ở: $DICH"
echo
if (( NEN )); then
  echo "==> Nén thành một tệp (lâu, mô hình gần như không nén được)"
  tar -cf "$DICH.tar" -C "$(dirname "$DICH")" "$(basename "$DICH")" \
    && echo "  $DICH.tar  ($(du -sh "$DICH.tar" | cut -f1))"
fi
echo "Chuyển sang máy khác:"
echo "  rsync -a --partial --info=progress2 '$DICH/' user@may-dich:~/goi-chatbot/"
echo
echo "Rồi trên máy đích chỉ cần:"
echo "  cd ~/goi-chatbot && bash chay.sh"
