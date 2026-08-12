"""Tinh chỉnh câu hỏi và đáp án bằng Qwen3-14B, có cổng kiểm chứng dữ kiện.

VÌ SAO CẦN TỆP NÀY
Bộ sinh Q/A dựng câu từ khuôn cố định nên số liệu chính xác nhưng câu chữ rập
khuôn, và độ dài dồn cục. Đo trên 1000 câu của qa_nang_cao.csv:
    câu hỏi   : 68,6% dài trên 20 từ, ngắn nhất cũng 9 từ  -> không ai hỏi vậy
    đáp án    : 21,5% dưới 60 từ, 51,8% ở 150-220 từ, lõm hẳn khoảng 100-150
Hai cục đó là dấu vết của khuôn: hoặc một câu cụt, hoặc một danh sách dài.

VÌ SAO KHÔNG ĐỂ MÔ HÌNH TỰ VIẾT ĐÁP ÁN
Đáp án chứa số tín chỉ, mã học phần, tên môn. Mô hình viết lại từ đầu sẽ sai vài
con số mà không ai soát nổi trong 1000 câu, rồi ta huấn luyện chính mô hình trên
số sai đó — đúng vòng lặp đã sinh ra lỗi "150 tín chỉ" và 230 đáp án dán nhầm
đoạn hành chính. Nên phân vai: mô hình lo DIỄN ĐẠT, dữ kiện luôn do code cấp.

CÁCH CHO ĐÁP ÁN DÀI RA MÀ KHÔNG BỊA
Đáp án cụt cần dài thêm, nhưng "viết dài hơn" là lời mời bịa. Vì vậy mỗi câu
được cấp kèm KHỐI DỮ KIỆN do curriculum_index tra từ dữ liệu đã bóc. Mô hình chỉ
được lấy thêm thông tin từ khối đó. Cổng kiểm tra vì thế nới theo đúng khối này:
    - mọi số trong bản mới phải nằm trong (đáp án gốc  ∪  khối dữ kiện)
    - mọi số của đáp án gốc phải còn nguyên trong bản mới
Thiếu số là mất học phần, thừa số là bịa; chặn cả hai chiều.

Cách dùng:
    conda activate test
    python src/Phase4-Finetuning/refine_qa_llm.py --limit 20 --dry-run
    python src/Phase4-Finetuning/refine_qa_llm.py
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sys
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import curriculum_index

MODEL = "Qwen/Qwen3-14B"
COLUMNS = ["id", "category", "question", "answer", "source_refs", "notes", "origin"]

# --------------------------------------------------------------- đích độ dài
# Chia thành dải để phân bố trải đều thay vì dồn hai cục. Số đo hiện tại nằm ở
# đầu tệp; đích là mỗi dải chiếm khoảng một phần bằng nhau.
Q_BANDS = [(6, 10), (11, 15), (16, 21), (22, 30)]
A_BANDS = [(55, 90), (90, 125), (125, 160), (160, 200), (200, 250)]

SYSTEM = (
    "Bạn là cố vấn học tập của Trường Đại học Công nghiệp Việt - Hung, biên tập "
    "lại một cặp câu hỏi - câu trả lời để dùng làm dữ liệu huấn luyện.\n\n"
    "QUY TẮC TUYỆT ĐỐI:\n"
    "1. Mọi dữ kiện phải lấy từ ĐÁP ÁN GỐC hoặc khối DỮ KIỆN TRA CỨU được cấp. "
    "Không thêm bất kỳ thông tin nào từ hiểu biết của bạn, kể cả khi bạn tin là "
    "đúng ngoài đời.\n"
    "2. Không đổi, không thêm, không bớt con số: số tín chỉ, số học kỳ, mã học "
    "phần, số Điều, tên học phần, tên ngành.\n"
    "3. Giữ nguyên trọng tâm câu hỏi. Nếu câu hỏi hỏi về học kỳ 6 ngành KT Nhiệt "
    "thì bản viết lại vẫn phải hỏi đúng học kỳ 6 ngành KT Nhiệt.\n"
    "4. Câu hỏi viết như sinh viên hỏi thật: tự nhiên, có thể cụt, có thể thân "
    "mật. Đừng viết như đề thi.\n"
    "5. Câu trả lời xưng 'em' với sinh viên, câu đầu trả lời thẳng vào trọng tâm, "
    "sau đó mới tới chi tiết. Không mở đầu bằng khuôn 'Theo kế hoạch đào tạo...' "
    "nếu đáp án gốc đã mở như vậy — hãy đổi cách vào đề.\n"
    "6. Nếu phải liệt kê nhiều học phần, hãy nhóm lại cho dễ đọc thay vì đổ một "
    "chuỗi dấu chấm phẩy dài.\n"
    "7. Câu trả lời phải nêu rõ HỌC KỲ và TÊN NGÀNH đang nói tới. Đừng rút gọn "
    "thành 'Em học 6 học phần' vì người đọc mất ngữ cảnh.\n"
    "8. Viết mọi con số bằng CHỮ SỐ (1, 2, 3), không viết bằng chữ (một, hai, "
    "nhất).\n"
    "9. Tín chỉ của mỗi học phần LUÔN viết trong ngoặc ngay sau tên môn, đúng "
    "dạng: Vật lý đại cương (2 tín chỉ). Không viết 'Vật lý đại cương với 2 tín "
    "chỉ'.\n"
    "10. Liệt kê ĐÚNG những học phần có trong đáp án gốc — không thêm môn nào từ "
    "khối dữ kiện, kể cả khi môn đó cùng học kỳ. Khối dữ kiện chỉ dùng để bổ sung "
    "thông tin nền (tổng tín chỉ học kỳ, tên định hướng), không dùng để nối dài "
    "danh sách môn.\n\n"
    "Trả về ĐÚNG một khối JSON, không kèm lời dẫn:\n"
    '{"question": "...", "answer": "..."}'
)

USER = (
    "CÂU HỎI GỐC ({q_len} từ):\n{question}\n\n"
    "ĐÁP ÁN GỐC ({a_len} từ):\n{answer}\n"
    "{facts}\n"
    "YÊU CẦU ĐỘ DÀI: câu hỏi khoảng {q_lo}-{q_hi} từ, câu trả lời khoảng "
    "{a_lo}-{a_hi} từ.\n"
    "Viết lại cặp này, giữ nguyên 100% dữ kiện."
)


# ------------------------------------------------------- cổng kiểm tra dữ kiện
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
# Tín chỉ CỦA TỪNG HỌC PHẦN, nhận ra nhờ cặp ngoặc: "Vật lý đại cương (2 tín chỉ)".
# Đây là dữ kiện đếm được — mất một cái là rơi một môn, thừa một cái là chèn môn
# không được hỏi. Phải so theo SỐ LẦN XUẤT HIỆN.
#
# Cố ý KHÔNG bắt tín chỉ viết ngoài ngoặc ("cộng lại 15 tín chỉ", "tổng 20 tín
# chỉ"): đó là số tổng, và mô hình được phép thêm tổng đã có trong khối dữ kiện.
# Bản trước gộp cả hai nên vừa loại oan câu thêm đúng tổng học kỳ, vừa phải nới
# lỏng tới mức bỏ lọt câu bị bơm thêm 8 học phần không ai hỏi.
_ITEM_CREDIT_RE = re.compile(r"\(\s*(\d+(?:[.,]\d+)*)\s*tín\s*chỉ", re.IGNORECASE)
# "năm thứ 1" và "năm thứ nhất" là một. Không quy đổi thì bản viết lại tự nhiên
# hơn lại bị loại oan — đã đo: đây là lý do loại của 2/3 ca trong lần chạy thử.
_ORDINALS = {"nhất": "1", "hai": "2", "ba": "3", "tư": "4", "bốn": "4",
             "năm": "5", "sáu": "6", "bảy": "7", "tám": "8"}
_ORDINAL_RE = re.compile(r"\bthứ\s+(" + "|".join(_ORDINALS) + r")\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return _ORDINAL_RE.sub(lambda m: "thứ " + _ORDINALS[m.group(1).lower()], text or "")


def _facts(text: str) -> list[str]:
    """Mọi chuỗi số trong văn bản, giữ cả số lần lặp."""
    return sorted(_NUM_RE.findall(_norm(text)))


def _credits(text: str) -> list[str]:
    return sorted(_ITEM_CREDIT_RE.findall(_norm(text)))


_SEM_MENTION_RE = re.compile(r"(?:học\s*)?kỳ\s*(\d{1,2})", re.IGNORECASE)
# Nhận ra lời từ chối. Bản đầu chỉ liệt kê vài cụm cố định ("chưa có", "không
# quy định") nên loại oan 17/42 câu: mô hình diễn đạt lại thành "chưa ĐƯỢC quy
# định", "không NẰM trong kho tài liệu" là trượt hết. Nay bắt theo cấu trúc —
# một từ phủ định, cách vài chữ, rồi tới một động từ chỉ sự hiện diện.
_REFUSAL_RE = re.compile(
    r"(?:không|chưa|chẳng)\s+(?:\S+\s+){0,3}"
    r"(?:có|nêu|ghi|nhắc|đề\s*cập|quy\s*định|tìm\s*thấy|nằm|thuộc|tra|xuất\s*hiện|"
    r"cung\s*cấp|đưa\s*ra|nói)"
    r"|ngoài\s+phạm\s+vi|vượt\s+quá\s+phạm\s+vi|không\s+thuộc\s+phạm\s+vi",
    re.IGNORECASE)
# Lời từ chối phải nằm ở CÂU ĐẦU TIÊN. Tìm khắp văn bản, hay cả nới rộng ra 40
# từ đầu, đều bỏ lọt: câu "Trường đào tạo 12 ngành... và KHÔNG CÓ ngành nào tạm
# dừng tuyển sinh" là một khẳng định trọn vẹn nhưng vẫn dính mẫu phủ định.
_FIRST_SENT_RE = re.compile(r"^[^.!?]{0,400}(?:[.!?]|$)")


# Cụm khung sườn của mọi lời tư vấn học vụ. Chúng có mặt ở gần như mọi đáp án nên
# mất chúng không phải mất ý — đối chiếu chỉ làm loãng phép đo.
_KHUNG = {
    "sinh vien", "nha truong", "quy che", "quy dinh", "hoc tap", "em ay",
    "co van", "co van hoc tap", "phong quan ly", "quan ly dao tao", "truong hop",
    "tai lieu", "van ban", "noi dung", "thong tin", "hien tai", "hien nay",
}
_GIU_TOI_THIEU = 0.75


def _missing_content(orig_a: str, new_a: str) -> list[str]:
    """Cụm từ mang nghĩa có trong bản gốc mà bản viết lại đánh rơi.

    Đơn vị so sánh là TỪ GHÉP do bộ tách từ tiếng Việt nhận ra, không phải cặp hai
    chữ liền nhau. Đã thử cách cặp-hai-chữ và số đo bác bỏ thẳng: bản diễn đạt lại
    trung thành chỉ đạt 66,7% trong khi bản BỎ MẤT hẳn một vế lại đạt 72,2% — thước
    đo xếp hạng ngược, vì cặp hai chữ cắt ngang ranh giới từ ("chưa bao" lấy từ
    "chưa bao giờ", "cấp thông" lấy từ "cung cấp thông tin"). Nó đã loại oan 34/42
    mẫu từ chối.

    Tách từ đúng cách thì thứ tự đảo lại: 85,7% / 71,4% / 57,1%, và các cụm bị mất
    ở bản hỏng đúng là phần nội dung bị bỏ (thời gian, tối đa, đào tạo, chương
    trình). Đây là chỗ bộ tách từ tiếng Việt thực sự có ích — so sánh nội dung —
    chứ không phải để tách token đưa vào mô hình.
    """
    try:
        from pyvi import ViTokenizer
    except ImportError:
        return []                       # thiếu gói thì bỏ qua, không chặn nhầm

    def ghep(s: str) -> set:
        seg = ViTokenizer.tokenize(s or "")
        out = {curriculum_index._fold(w.replace("_", " "))
               for w in seg.split() if "_" in w}
        return {g for g in out if g and g not in _KHUNG}

    goc = ghep(orig_a)
    if not goc:
        return []
    mat = sorted(goc - ghep(new_a))
    if len(goc) - len(mat) >= _GIU_TOI_THIEU * len(goc):
        return []
    return mat


def _is_refusal(text: str) -> bool:
    """Đáp án có mở đầu bằng lời từ chối không."""
    m = _FIRST_SENT_RE.match(" ".join((text or "").split()))
    return bool(m and _REFUSAL_RE.search(m.group(0)))


def _missing_anchors(orig_a: str, new_a: str) -> list[str]:
    """Ngữ cảnh bắt buộc giữ lại: học kỳ nào, ngành nào.

    Cổng số học không bắt được kiểu hỏng này. Đo thực tế: đáp án "Kỳ 2 ngành KT
    Nhiệt bố trí 6 học phần, cộng lại 18 tín chỉ: ..." bị viết lại thành "Em học
    6 học phần, tổng 18 tín chỉ: ..." — mọi con số còn nguyên nên cổng cho qua,
    nhưng người đọc không còn biết đang nói về học kỳ nào của ngành nào.
    """
    fold_new = curriculum_index._fold(new_a)
    missing = []

    sems = {m.group(1) for m in _SEM_MENTION_RE.finditer(_norm(orig_a))}
    for s in sorted(sems):
        if not re.search(rf"\bky\s*{s}\b", fold_new):
            missing.append(f"học kỳ {s}")

    try:
        _, programs = curriculum_index.load()
    except Exception:
        programs = []
    for p in programs:
        lbl = curriculum_index.program_label(p)
        if curriculum_index._fold(lbl) in curriculum_index._fold(orig_a):
            if curriculum_index._fold(lbl) not in fold_new:
                missing.append(lbl)
    return missing


def verify(orig_q: str, orig_a: str, new_q: str, new_a: str,
           extra: str = "") -> tuple[bool, str]:
    """Bản viết lại có giữ đúng dữ kiện không.

    Hai mức chặt khác nhau, vì hai loại số hỏng theo hai kiểu:

    - SỐ TÍN CHỈ so theo số lần xuất hiện. Đáp án liệt kê sáu môn "(3 tín chỉ)"
      mà bản mới chỉ còn năm là rơi mất một học phần, dù chữ số 3 vẫn còn.
    - CÁC SỐ CÒN LẠI chỉ so có/không. Đáp án gốc viết "Học kỳ 1 (học kỳ 1 năm thứ
      1)" lặp ba lần chữ số 1; bản viết lại bỏ phần trong ngoặc cho gọn là ĐÚNG,
      không phải mất dữ kiện. So theo số lần ở đây chỉ loại oan bản tốt.

    Chiều ngược lại — số lạ xuất hiện — luôn chặn, vì đó là mô hình bịa.
    """
    if not new_q or not new_q.strip() or not new_a or not new_a.strip():
        return False, "bản viết lại rỗng"

    # Hai chiều dùng hai bản văn khác nhau, cố ý:
    #   - chiều THIẾU đọc bản đã quy đổi "thứ nhất" -> "thứ 1", để bản viết lại tự
    #     nhiên hơn không bị coi là đánh rơi chữ số;
    #   - chiều THỪA đọc bản NGUYÊN VĂN, vì chính phép quy đổi đó tự sinh ra con số:
    #     câu "Thứ nhất là khi điểm dưới 1,2..." bị quy thành "Thứ 1" rồi báo là
    #     bịa thêm số 1. Đã loại oan một bản viết lại hoàn toàn đúng vì lỗi này.
    a = _facts(orig_a)
    b_norm = _facts(new_a)
    b_raw = sorted(_NUM_RE.findall(new_a or ""))
    allowed = set(a) | set(_facts(extra))
    thua = sorted({x for x in b_raw if x not in allowed})
    if thua:
        return False, f"đáp án có số không có trong dữ liệu: {thua}"

    thieu = sorted(set(a) - set(b_norm))
    if thieu:
        return False, f"đáp án làm mất số: {thieu}"

    ca, cb = _credits(orig_a), _credits(new_a)
    if ca != cb:
        kieu = "chèn thêm học phần không được hỏi" if len(cb) > len(ca) else "rơi học phần"
        return False, f"tín chỉ từng học phần không khớp ({kieu}): gốc {ca} -> mới {cb}"

    mat = _missing_anchors(orig_a, new_a)
    if mat:
        return False, f"đáp án bỏ mất ngữ cảnh: {mat}"

    # Mẫu TỪ CHỐI là chỗ bịa đặt nguy hiểm nhất: nếu mô hình biến "kho dữ liệu
    # không có ngành đó" thành một câu trả lời nghe hợp lý, mọi cổng phía trên
    # đều không thấy gì — đáp án mới có thể chẳng chứa con số nào. Bắt buộc giữ
    # lại lời phủ định.
    if _is_refusal(orig_a) and not _is_refusal(new_a):
        return False, "mẫu từ chối bị viết thành câu trả lời khẳng định"

    # Nội dung KHÔNG PHẢI SỐ cũng có thể rơi mất mà mọi tầng trên đều không thấy:
    # "sinh viên bị buộc thôi học nếu vượt quá thời gian đào tạo tối đa" chẳng có
    # con số nào. Đo bằng tỉ lệ giữ lại các từ nội dung dài (bỏ hư từ), và chặn
    # cả việc rút ngắn — đáp án viết lại là để dễ đọc, không phải để tóm tắt.
    if len(new_a.split()) < 0.9 * len(orig_a.split()):
        return False, (f"đáp án ngắn hơn bản gốc quá nhiều "
                       f"({len(orig_a.split())} -> {len(new_a.split())} từ)")
    thieu_y = _missing_content(orig_a, new_a)
    if thieu_y:
        return False, f"đáp án bỏ mất ý: {thieu_y[:6]}"

    # Câu hỏi được phép BỎ BỚT chữ thừa nhưng không được thêm số mới: "học kỳ 2
    # năm thứ 1" rút thành "học kỳ 2" vẫn hỏi đúng chỗ đó, còn "học kỳ 6" thành
    # "học kỳ 8" là hỏng dữ liệu. Riêng số học kỳ thì phải giữ, mất nó là câu hỏi
    # hết xác định và không còn khớp với đáp án.
    qa, qb = set(_facts(orig_q)), set(_NUM_RE.findall(new_q or ""))
    if qb - qa:
        return False, f"câu hỏi thêm số lạ: {sorted(qb - qa)}"
    sem_q = {m.group(1) for m in _SEM_MENTION_RE.finditer(_norm(orig_q))}
    mat_q = sem_q - {m.group(1) for m in _SEM_MENTION_RE.finditer(_norm(new_q))}
    if mat_q:
        return False, f"câu hỏi bỏ mất học kỳ: {sorted(mat_q)}"
    return True, ""


# ------------------------------------------------------------ chọn dải độ dài
def assign_bands(rows: list[dict]) -> list[tuple]:
    """Gán dải độ dài cho từng câu sao cho phân bố cuối cùng trải đều.

    Không gán ngẫu nhiên: đáp án liệt kê 11 học phần thì không thể nén còn 60 từ
    mà không mất học phần — ép vào dải ngắn chỉ làm cổng kiểm tra loại hết. Nên
    lấy độ dài gốc làm SÀN rồi chia đều trong các dải còn khả thi.
    """
    out = []
    for i, r in enumerate(rows):
        a_len = len(r["answer"].split())
        # KHÔNG cho nén ngắn lại. Đáp án được viết lại cho dễ đọc, không phải để
        # tóm tắt: mọi ý trong bản gốc đều là điều khoản quy chế hoặc học phần mà
        # sinh viên cần biết. Đã có bài học — bản trước dùng cách cắt đuôi cho gọn
        # và mất 69.513 từ trên 782 đáp án, trong đó một câu về Điều 11 Luật Giáo
        # dục đại học bị cắt từ 479 xuống 72 từ, mất luôn phần liệt kê chính.
        # Sàn vì vậy đặt ở NGUYÊN độ dài gốc; dải đích chỉ được phép bằng hoặc dài
        # hơn, phần dài thêm lấy từ khối dữ kiện đã tra cứu.
        n_facts = len(set(_NUM_RE.findall(r["answer"])))
        floor = max(40, 25 + 6 * n_facts, a_len)
        feasible = [b for b in A_BANDS if b[1] >= floor]
        a_band = feasible[i % len(feasible)] if feasible else (floor, int(floor * 1.25))
        q_band = Q_BANDS[i % len(Q_BANDS)]
        out.append((q_band, a_band))
    return out


# ------------------------------------------------------------------ gọi model
def load_model(dtype_4bit: bool = True):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(MODEL, padding_side="left")
    kw = {"dtype": torch.bfloat16, "device_map": "auto"}
    if dtype_4bit:
        kw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(MODEL, **kw)
    model.eval()
    return tok, model


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse(text: str) -> tuple[str, str]:
    """Bóc {"question","answer"} khỏi đầu ra. Trả ("","") nếu không đọc được."""
    m = _JSON_RE.search(text or "")
    if not m:
        return "", ""
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return "", ""
    return str(d.get("question", "")).strip(), str(d.get("answer", "")).strip()


def _generate(tok, model, prompts: list[str], max_new: int) -> list[str]:
    import torch

    texts = [tok.apply_chat_template(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": p}],
        tokenize=False, add_generation_prompt=True,
        # Qwen3 mặc định bật khối suy nghĩ dài; ở đây chỉ cần biên tập câu chữ nên
        # tắt đi, vừa nhanh vừa khỏi lẫn phần suy nghĩ vào JSON đầu ra.
        enable_thinking=False) for p in prompts]
    enc = tok(texts, return_tensors="pt", padding=True).to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=max_new, do_sample=True,
                             temperature=0.8, top_p=0.9,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
    return [tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=True)
            for o in out]


def run_batch(tok, model, prompts: list[str], max_new: int) -> list[str]:
    """Sinh cả lô, tự chia đôi lô nếu hết bộ nhớ GPU.

    Máy này dùng chung card với tiến trình của người khác: lúc bắt đầu chạy còn
    11,6GB nhưng phần trống đó co giãn ngoài tầm kiểm soát. Một lần tràn bộ nhớ
    mà không bắt lại sẽ giết cả mẻ 1000 câu sau nhiều giờ chạy, nên chia nhỏ rồi
    thử lại; xuống tới lô 1 câu mà vẫn tràn thì mới bỏ qua câu đó.
    """
    import torch

    try:
        return _generate(tok, model, prompts, max_new)
    except torch.OutOfMemoryError:
        torch.cuda.empty_cache()
        if len(prompts) == 1:
            print("   ⚠️  hết bộ nhớ GPU ngay cả với 1 câu -> bỏ qua câu này")
            return [""]
        mid = len(prompts) // 2
        print(f"   ⚠️  hết bộ nhớ GPU, chia lô {len(prompts)} -> {mid}+{len(prompts) - mid}")
        return (run_batch(tok, model, prompts[:mid], max_new)
                + run_batch(tok, model, prompts[mid:], max_new))


# ---------------------------------------------------------------------- chạy
def out_path(args, src: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(args.out) if args.out else src.with_name(src.stem + "_tinh.csv")


def _prompt(r: dict, qb: tuple, ab: tuple, extra: str, loi: str = "") -> str:
    """Lời nhắc cho một câu. `loi` khác rỗng nghĩa là đang làm lại lượt 2."""
    sua = (f"\nBẢN VIẾT LẠI TRƯỚC ĐÓ BỊ LOẠI VÌ: {loi}.\n"
           f"Hãy làm lại và tránh đúng lỗi đó. Cách chắc nhất là GIỮ NGUYÊN danh "
           f"sách học phần của đáp án gốc — cả tên môn lẫn số tín chỉ trong ngoặc, "
           f"không thêm không bớt môn nào — và chỉ đổi cách viết những câu dẫn "
           f"xung quanh.\n") if loi else ""
    # Đáp án gốc không liệt kê học phần nào thì phải nói thẳng ra. Đo trên 341 câu
    # kế hoạch đào tạo: đây là lý do loại đông nhất — hỏi "học kỳ 1 có bao nhiêu
    # tín chỉ", đáp án gốc chỉ nêu con số, mà mô hình thấy khối dữ kiện có sẵn
    # danh sách môn là chép cả vào. Số liệu không sai, nhưng khi ấy mọi câu hỏi về
    # học kỳ N đều cho ra cùng một danh sách — đúng lỗi "câu trả lời giống y nhau".
    khong_liet_ke = ("\nĐáp án gốc KHÔNG liệt kê học phần nào. Bản viết lại cũng "
                     "TUYỆT ĐỐI không được liệt kê tên học phần, dù khối dữ kiện "
                     "có sẵn. Câu hỏi này chỉ hỏi con số.\n"
                     if not _ITEM_CREDIT_RE.search(r["answer"]) else "")
    return USER.format(
        question=r["question"], answer=r["answer"],
        q_len=len(r["question"].split()), a_len=len(r["answer"].split()),
        facts=("\nDỮ KIỆN TRA CỨU (chỉ được lấy thêm thông tin từ đây):\n"
               + extra + "\n") if extra else "",
        q_lo=qb[0], q_hi=qb[1], a_lo=ab[0], a_hi=ab[1]) + khong_liet_ke + sua


def _write(rows: list[dict], out: pathlib.Path) -> None:
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL,
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="data/qa/qa_nang_cao.csv")
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--max-new", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show-rejects", action="store_true", help="in đầy đủ bản bị loại")
    args = ap.parse_args()

    src = pathlib.Path(args.src)
    if not src.is_absolute():
        src = config.ROOT / src
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    if args.limit:
        rows = rows[:args.limit]
    bands = assign_bands(rows)
    print(f"{src.name}: tinh chỉnh {len(rows)} câu bằng {MODEL}")

    tok, model = load_model()
    print("Đã nạp mô hình. Bắt đầu.\n")

    # Xử lý theo THỨ TỰ ĐỘ DÀI chứ không theo thứ tự tệp. Sinh theo lô phải đệm
    # mọi câu cho bằng câu dài nhất trong lô, nên ghép một câu 40 từ với một câu
    # 260 từ là phí gần hết phần đệm. Gom câu dài gần nhau vào cùng lô rút ngắn
    # đáng kể tổng thời gian; kết quả vẫn ghi về đúng vị trí cũ nên tệp ra không
    # đổi thứ tự.
    order = sorted(range(len(rows)),
                   key=lambda i: len(rows[i]["question"]) + len(rows[i]["answer"]))

    ok, ok_retry, rejected, samples = 0, 0, [], []
    t0 = time.time()
    for start in range(0, len(order), args.batch):
        idxs = order[start:start + args.batch]
        chunk = [rows[i] for i in idxs]
        chunk_bands = [bands[i] for i in idxs]
        prompts, extras = [], []
        for r, (qb, ab) in zip(chunk, chunk_bands):
            extra = curriculum_index.facts_for(r["question"]) or ""
            extras.append(extra)
            prompts.append(_prompt(r, qb, ab, extra))

        outs = run_batch(tok, model, prompts, args.max_new)

        # Lượt 2 cho những câu vừa trượt, kèm ĐÚNG lý do bị loại. Phần lớn ca
        # trượt là đáp án liệt kê dài — mô hình cắt bớt hoặc bơm thêm học phần —
        # và chỉ cần chỉ tên lỗi là nó sửa được. Câu trượt lượt 2 thì giữ nguyên
        # bản gốc, nên lượt này chỉ có thể làm dữ liệu tốt lên.
        retry_idx, retry_prompts = [], []
        results = []
        for i, (r, raw, extra) in enumerate(zip(chunk, outs, extras)):
            nq, na = _parse(raw)
            good, why = verify(r["question"], r["answer"], nq, na, extra)
            results.append((nq, na, good, why))
            if not good:
                qb, ab = chunk_bands[i]
                retry_idx.append(i)
                retry_prompts.append(_prompt(r, qb, ab, extra, loi=why))

        if retry_prompts:
            for i, raw in zip(retry_idx, run_batch(tok, model, retry_prompts, args.max_new)):
                r, extra = chunk[i], extras[i]
                nq, na = _parse(raw)
                good, why = verify(r["question"], r["answer"], nq, na, extra)
                if good:
                    ok_retry += 1
                results[i] = (nq, na, good, why)

        for r, (nq, na, good, why) in zip(chunk, results):
            if not good:
                rejected.append((r["id"], r["question"][:55], why))
                if args.show_rejects:
                    print(f"\n  ✗ [{r['id']}] {why}\n    GỐC: {r['answer'][:400]}"
                          f"\n    MỚI: {na[:400]}\n")
                continue                       # giữ nguyên cặp gốc
            if len(samples) < 3:
                samples.append((r["question"], r["answer"], nq, na))
            r["question"], r["answer"] = nq, na
            ok += 1

        done = min(start + args.batch, len(rows))
        rate = done / max(time.time() - t0, 1e-9)
        print(f"  {done}/{len(rows)}  nhận {ok}  loại {len(rejected)}  "
              f"({rate:.2f} câu/s, còn ~{(len(rows) - done) / max(rate, 1e-9) / 60:.0f} phút)",
              flush=True)
        # Ghi lại sau mỗi 20 lô: cả mẻ chạy ~3 tiếng trên card dùng chung với
        # người khác, mất giữa chừng mà không có bản dở là mất trắng công sức.
        if not args.dry_run and (start // max(args.batch, 1)) % 20 == 19:
            _write(rows, out_path(args, src))

    print(f"\n✅ Nhận {ok}/{len(rows)} (trong đó {ok_retry} câu phải làm lại lượt 2)"
          f"   ❌ Loại {len(rejected)} (giữ nguyên bản gốc)")
    for rid, q, why in rejected[:10]:
        print(f"   [{rid}] {q} -> {why}")
    for q0, a0, q1, a1 in samples:
        print(f"\n--- HỎI gốc: {q0}\n    HỎI mới: {q1}")
        print(f"    ĐÁP gốc ({len(a0.split())} từ): {a0[:200]}")
        print(f"    ĐÁP mới ({len(a1.split())} từ): {a1[:200]}")

    if args.dry_run:
        print("\n[thử] không ghi tệp.")
        return

    out = out_path(args, src)
    _write(rows, out)
    print(f"\n✅ Đã ghi -> {out}")


if __name__ == "__main__":
    main()
