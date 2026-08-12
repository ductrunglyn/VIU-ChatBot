#!/usr/bin/env bash
# Điều khiển mẻ tinh chỉnh Q/A bằng Qwen3-14B: chạy, xem, dừng an toàn, chạy tiếp.
#
#     bash scripts/tinh-chinh.sh            # chạy (tự chạy tiếp nếu có mẻ dở)
#     bash scripts/tinh-chinh.sh --xem      # tiến độ hiện tại
#     bash scripts/tinh-chinh.sh --dung     # dừng, GIỮ nguyên phần đã làm
#     bash scripts/tinh-chinh.sh --lam-lai  # xoá tiến độ, chạy lại từ đầu
#
# Mẻ đầy đủ mất khoảng 6 tiếng trên card dùng chung. Dừng rồi chạy tiếp được, nên
# muốn nhường GPU cho web hay huấn luyện thì cứ --dung, xong bật lại bình thường.
set -uo pipefail

GOC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PHIEN="TinhChinh"
NHAT_KY="$GOC/tinh-chinh.log"
TEP=(qa_tu_choi qa_ke_hoach_dao_tao qa_nang_cao qa_viu_full)

# Dùng lại bộ dò env của chay-web.sh thay vì đóng cứng tên: máy này 'test',
# server kia 'ChatBot'.
PY="${PY:-$(ENV="${ENV:-}" bash "$GOC/scripts/chay-web.sh" --python 2>/dev/null)}"
[[ -n "$PY" && -x "$PY" ]] || {
  echo "❌ Không dò được Python có đủ gói. Chỉ định thẳng:"
  echo "     PY=/đường/dẫn/bin/python bash scripts/tinh-chinh.sh"; exit 1; }

tien_do() {
  for f in "${TEP[@]}"; do
    local ra="$GOC/data/qa/${f}_tinh.csv" td="$GOC/data/qa/${f}_tinh.csv.tien_do.json"
    if [[ ! -f "$ra" ]]; then
      printf "  %-24s chưa chạy\n" "$f"; continue
    fi
    local tong xong
    # Đếm bằng csv chứ không phải `wc -l`: đáp án có xuống dòng ngay trong ô nên
    # đếm dòng ra gấp mấy lần số câu thật.
    tong=$("$PY" -c "import csv,sys;print(sum(1 for _ in csv.DictReader(open(sys.argv[1],encoding='utf-8'))))" \
           "$GOC/data/qa/$f.csv")
    if [[ -f "$td" ]]; then
      xong=$("$PY" -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" "$td")
      [[ "$xong" == "$tong" ]] && printf "  %-24s %s/%s câu  ✅ xong\n" "$f" "$xong" "$tong" \
                               || printf "  %-24s %s/%s câu\n" "$f" "$xong" "$tong"
    else
      printf "  %-24s có kết quả, chưa rõ mốc (chạy --dung sẽ dựng lại)\n" "$f"
    fi
  done
}

case "${1:-}" in
  --xem)
    echo "== Tiến độ tinh chỉnh =="; tien_do
    if pgrep -f refine_qa_llm > /dev/null; then
      echo; echo "Đang chạy (PID $(pgrep -f refine_qa_llm | head -1)). Nhật ký:"
      tail -5 "$NHAT_KY" 2>/dev/null
    else
      echo; echo "Không có tiến trình nào đang chạy."
    fi
    exit 0 ;;

  --dung)
    PID=$(pgrep -f refine_qa_llm | head -1)
    [[ -z "$PID" ]] && { echo "Không có tiến trình nào đang chạy."; exit 0; }
    echo "Gửi lệnh dừng tới PID $PID..."
    screen -S "$PHIEN" -X quit 2>/dev/null
    kill "$PID" 2>/dev/null
    # Bản mới bắt SIGTERM và ghi tiến độ trước khi thoát; chờ nó làm xong nốt lô.
    for _ in $(seq 60); do sleep 2; pgrep -f refine_qa_llm >/dev/null || break; done
    pkill -9 -f refine_qa_llm 2>/dev/null
    sleep 2
    echo
    # Mẻ khởi động bằng bản code cũ không tự ghi tiến độ -> dựng lại từ tệp kết quả.
    for f in "${TEP[@]}"; do
      ra="$GOC/data/qa/${f}_tinh.csv"
      [[ -f "$ra" && ! -f "$ra.tien_do.json" ]] && {
        echo "Dựng lại tiến độ cho $f:"
        "$PY" "$GOC/src/Phase4-Finetuning/khoi_phuc_tien_do.py" \
              --in "data/qa/$f.csv" --ghi 2>&1 | sed 's|^|  |'; }
    done
    echo; echo "✅ Đã dừng. Tiến độ hiện tại:"; tien_do
    echo; echo "   Chạy tiếp: bash scripts/tinh-chinh.sh"
    exit 0 ;;

  --lam-lai)
    pgrep -f refine_qa_llm >/dev/null && {
      echo "❌ Đang có tiến trình chạy. Dừng trước: bash scripts/tinh-chinh.sh --dung"
      exit 1; }
    rm -f "$GOC"/data/qa/*_tinh.csv.tien_do.json
    echo "✅ Đã xoá mốc tiến độ. Lần chạy tới sẽ làm lại từ đầu."
    echo "   (tệp *_tinh.csv vẫn còn — sẽ bị ghi đè)"
    exit 0 ;;

  "") ;;
  *) echo "Tham số lạ: $1"; exit 1 ;;
esac

pgrep -f refine_qa_llm > /dev/null && {
  echo "✅ Đang chạy rồi (PID $(pgrep -f refine_qa_llm | head -1))."
  echo "   Xem tiến độ: bash scripts/tinh-chinh.sh --xem"; exit 0; }

if command -v nvidia-smi >/dev/null 2>&1; then
  TRONG=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
  echo "GPU trống: ${TRONG} MiB"
  # Qwen3-14B 4-bit: trọng số 9,39 GB + đệm sinh theo lô.
  (( TRONG < 11000 )) && {
    echo "❌ Cần ít nhất 11000 MiB cho Qwen3-14B 4-bit. Xem ai đang chiếm: nvidia-smi"
    echo "   (web đang chạy thì tắt: bash scripts/chay-web.sh --dung)"; exit 1; }
fi

echo "== Tiến độ trước khi chạy =="; tien_do; echo

cat > "$GOC/.tinh-chinh-mot-mach.sh" <<EOF
cd "$GOC"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
for f in ${TEP[@]}; do
  echo "########## \$f  \$(date +%H:%M) ##########"
  "$PY" src/Phase4-Finetuning/refine_qa_llm.py --in data/qa/\$f.csv --batch 2 --tiep 2>&1 \\
    | grep -vE "Loading weights|FutureWarning|torch\._check|^Warning|Fetching"
done
echo "########## XONG TOÀN BỘ \$(date +%H:%M) ##########"
EOF

# stdbuf: grep trong ống dẫn đệm theo khối 4KB nên nhật ký tụt lại hàng chục dòng
# so với thực tế — đã đo, tệp kết quả đi trước nhật ký 64 câu. Tắt đệm cho khớp.
screen -dmS "$PHIEN" bash -c \
  "stdbuf -oL -eL bash '$GOC/.tinh-chinh-mot-mach.sh' 2>&1 | tee '$NHAT_KY'"

sleep 3
pgrep -f "tinh-chinh-mot-mach" >/dev/null && {
  echo "✅ Đã khởi động trong screen '$PHIEN' (nạp mô hình mất ~2 phút)"
  echo "   Xem tiến độ : bash scripts/tinh-chinh.sh --xem"
  echo "   Xem nhật ký : tail -f $NHAT_KY"
  echo "   Dừng an toàn: bash scripts/tinh-chinh.sh --dung"
} || echo "⚠ Không thấy tiến trình. Xem: cat $NHAT_KY"
