"""Đo tầng TRUY XUẤT (không nạp LLM) — hiệu chỉnh ngưỡng chặn và đo độ trễ.

Việc chặn câu ngoài phạm vi nay chia làm HAI TẦNG:

  Tầng 1 (tệp này) — ngưỡng RERANK_MIN_SCORE / DENSE_MIN_SCORE, chỉ còn là SÀN
  AN TOÀN bắt trường hợp thảm hoạ. Đo được hai vùng điểm đã chồng nhau (câu hợp lệ
  thấp nhất 0,496 vs câu ngoài phạm vi cao nhất 0,493) nên không ngưỡng nào tách
  được. Ở tầng này, câu ngoài phạm vi ĐI QUA là ĐÚNG THIẾT KẾ, không phải lỗi.
  Điều PHẢI đạt ở tầng 1 là: không chặn nhầm câu hợp lệ nào.

  Tầng 2 — chính LLM đọc ngữ cảnh rồi tự từ chối. Chạy `--llm` để đo tầng này.

    python src/Phase3-RAG/calib_retrieval.py          # chỉ tầng 1, nhanh, không nạp LLM
    python src/Phase3-RAG/calib_retrieval.py --llm    # đo cả tầng 2 (nạp LLM ~1 phút)
"""
from __future__ import annotations
import sys
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import retriever

# Câu TRONG phạm vi: kho tài liệu phải trả lời được.
IN_SCOPE = [
    "Sinh viên bị cảnh báo học tập trong những trường hợp nào?",
    "Điều kiện để được xét tốt nghiệp là gì?",
    "Em bị CPA 1.5 ở năm hai thì có bị buộc thôi học không?",
    "Thời gian đào tạo tối đa của sinh viên là bao lâu?",
    "Chuẩn đầu ra ngoại ngữ của trường yêu cầu chứng chỉ gì?",
    "Chuẩn đầu ra tin học gồm những chứng chỉ nào?",
    "Học phí được thu theo hình thức nào?",
    "Sinh viên được nghỉ học tạm thời trong trường hợp nào?",
    "Cách tính điểm trung bình học kỳ như thế nào?",
    "Đào tạo trực tuyến được tổ chức ra sao?",
    "Em muốn học cải thiện điểm thì có được không?",
    "Sinh viên bị đuổi học khi nào?",
    "Xếp loại tốt nghiệp bằng giỏi cần điều kiện gì?",
    "Em trượt môn thì phải làm sao?",
    "Thủ tục chuyển ngành học thế nào?",
]

# Câu TƯ VẤN TÌNH HUỐNG: sinh viên kể hoàn cảnh của mình kèm CON SỐ cụ thể rồi hỏi
# nên làm gì. Đây là loại câu quan trọng nhất của một hệ cố vấn học tập, nhưng bộ đo
# đầu tiên KHÔNG có câu nào loại này — nên đã bỏ lọt lỗi: câu mở rộng dùng nhầm cho
# dense làm điểm tụt từ 0,559 xuống 0,538 và sinh viên bị trả lời "chưa tìm thấy".
# Giữ nhóm này tách riêng để luôn soi được đúng lớp câu dễ hỏng đó.
TU_VAN = [
    "Em còn nợ 3 môn và GPA 1.9, nên làm gì để ra trường đúng hạn?",
    "Em bị điểm F môn Toán cao cấp, giờ phải làm sao?",
    "Em đang bị cảnh báo học tập lần 2, em nên làm gì?",
    "Em thi trượt tiếng Anh đầu ra thì có được xét tốt nghiệp không?",
    "GPA 1.9 thì em có tốt nghiệp được không?",
    "Em muốn tốt nghiệp sớm một kỳ thì cần điều kiện gì?",
    "Em đi làm thêm nhiều, học kỳ này chỉ đăng ký 10 tín chỉ có sao không?",
]

# Câu NGOÀI phạm vi: kho không có, BẮT BUỘC phải bị chặn.
OUT_SCOPE = [
    "Trường có bán trú cho sinh viên không?",
    "Giá vé máy bay đi Đà Nẵng bao nhiêu?",
    "Cách nấu phở bò ngon nhất?",
    "Đội tuyển Việt Nam đá với Thái Lan lúc mấy giờ?",
    "Thủ đô của nước Pháp là gì?",
    "Trường có ký túc xá cho sinh viên nước ngoài không?",
    "Lịch nghỉ Tết Nguyên đán năm nay thế nào?",
    "Hôm nay thời tiết Hà Nội ra sao?",
]


def _probe(q):
    hits = retriever.retrieve(q, config.RAG_TOP_K)
    top_rr = hits[0].get("rerank_score") if hits else None
    top_dense = max((h.get("score") or 0) for h in hits) if hits else 0
    return top_rr, top_dense, retriever.has_relevant(hits), hits


def main():
    print("Đang nạp mô hình truy xuất ...")
    t0 = time.time()
    retriever.retrieve("khởi động", 3)
    print(f"  nạp xong sau {time.time() - t0:.1f}s\n")

    print(f"Cấu hình: cand={config.RETRIEVE_CANDIDATES} bm25={config.BM25_CANDIDATES} "
          f"mở_rộng={config.QUERY_EXPANSION} ghép_Điều={config.PARENT_EXPAND}")
    print(f"Ngưỡng  : RERANK_MIN_SCORE={config.RERANK_MIN_SCORE} "
          f"DENSE_MIN_SCORE={config.DENSE_MIN_SCORE}\n")

    rows, lat = [], []
    for label, qs in (("TRONG", IN_SCOPE), ("TƯ VẤN", TU_VAN), ("NGOÀI", OUT_SCOPE)):
        print(f"=== {label} phạm vi ===")
        for q in qs:
            t = time.time()
            rr, dense, ok, _ = _probe(q)
            lat.append(time.time() - t)
            rows.append((label, q, rr, dense, ok))
            # TRONG phạm vi mà ok=False, hoặc NGOÀI mà ok=True -> sai
            bad = (label == "NGOÀI") == ok
            print(f"  {'✗' if bad else ' '} rr={rr:.4f} dense={dense:.3f} "
                  f"{'nhận' if ok else 'CHẶN'}  {q[:52]}")
        print()

    ins = [r for r in rows if r[0] in ("TRONG", "TƯ VẤN")]
    outs = [r for r in rows if r[0] == "NGOÀI"]
    print("=== Khoảng cách hai vùng (căn cứ chọn ngưỡng) ===")
    print(f"  rerank : TRONG thấp nhất {min(r[2] for r in ins):.4f} | "
          f"NGOÀI cao nhất {max(r[2] for r in outs):.4f}")
    print(f"  dense  : TRONG thấp nhất {min(r[3] for r in ins):.3f} | "
          f"NGOÀI cao nhất {max(r[3] for r in outs):.3f}")

    miss = [r for r in ins if not r[4]]
    qua = [r for r in outs if r[4]]
    print(f"\n  [TẦNG 1] Chặn nhầm câu hợp lệ: {len(miss)}/{len(ins)}"
          f"{'  ✅' if not miss else '  ❌ PHẢI BẰNG 0'}")
    for r in miss:
        print(f"      {r[1]}  (rr={r[2]:.4f} dense={r[3]:.3f})")
    print(f"  [TẦNG 1] Câu ngoài phạm vi đi qua sàn: {len(qua)}/{len(outs)} "
          f"— bình thường, tầng 2 (LLM) mới là chỗ từ chối.")

    lat = sorted(lat)
    print(f"\n  Độ trễ truy xuất: trung vị {lat[len(lat)//2]*1000:.0f}ms | "
          f"cao nhất {lat[-1]*1000:.0f}ms")

    if "--llm" in sys.argv:
        _do_tang_2()


def _do_tang_2():
    """Đo tầng 2: đưa thẳng câu ngoài phạm vi cho LLM xem nó có tự từ chối không."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import rag

    print("\n=== [TẦNG 2] LLM có tự từ chối câu ngoài phạm vi không? ===")
    llm, tok = rag._load_llm()
    sai = []
    for q in OUT_SCOPE:
        hits = retriever.retrieve(q, config.RAG_TOP_K)
        ctx, _ = rag._build_context(hits, q)
        msgs = [{"role": "system", "content": rag.SYSTEM_PROMPT},
                {"role": "user", "content": f"TÀI LIỆU:\n{ctx}\n\nCÂU HỎI: {q}"}]
        inp = tok([rag._chat_text(tok, msgs)], return_tensors="pt").to(llm.device)
        out = llm.generate(**inp, **rag._gen_kwargs(tok))
        rep = rag._strip_think(
            tok.decode(out[0][inp.input_ids.shape[1]:], skip_special_tokens=True).strip())
        tu_choi = rag._la_tu_choi(rep, rag._ctx_dieu_map(ctx))
        if not tu_choi:
            sai.append((q, rep))
        print(f"  {'✓ từ chối' if tu_choi else '✗ TRẢ LỜI'}  {q[:55]}")
        print(f"      {rep[:130]}")
    print(f"\n  [TẦNG 2] Tự từ chối đúng: {len(OUT_SCOPE) - len(sai)}/{len(OUT_SCOPE)}"
          f"{'  ✅' if not sai else '  ❌ có câu bị bịa'}")


if __name__ == "__main__":
    main()
