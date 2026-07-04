"""Test RAG+LLM theo LÔ câu hỏi (nạp model 1 lần) — đánh giá chatbot trước khi deploy.

Khác với rag.py (hỏi lẻ / chat tương tác), file này chạy 1 danh sách câu hỏi liền
mạch để bạn soát chất lượng có hệ thống (đúng quy chế? có bịa? có trích nguồn?).

Cách dùng:
    conda activate test
    python src/Phase3-RAG/test_rag.py                 # bộ câu hỏi mẫu sẵn có
    python src/Phase3-RAG/test_rag.py my_questions.txt # file: mỗi dòng 1 câu hỏi
    python src/Phase3-RAG/test_rag.py --base           # dùng model GỐC (so sánh với fine-tuned)
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import rag

# Bộ câu hỏi mẫu, phủ các nhóm: quy chế · khung chương trình · tư vấn · ngoài phạm vi
DEFAULT_QUESTIONS = [
    "Sinh viên bị cảnh báo học tập trong những trường hợp nào?",
    "Điều kiện để được xét tốt nghiệp là gì?",
    "Em bị CPA 1.5 ở năm hai thì có bị buộc thôi học không?",
    "Học phần Mạng máy tính của ngành Khoa học máy tính có mấy tín chỉ?",
    "Thời gian đào tạo tối đa của sinh viên là bao lâu?",
    "Em còn nợ 3 môn và CPA 1.9, nên làm gì để ra trường đúng hạn?",
    "Trường có bán trú cho sinh viên không?",  # ngoài phạm vi -> phải nói không tìm thấy
]


def main():
    args = [a for a in sys.argv[1:]]
    if "--base" in args:
        config.USE_FINETUNED = False
        args.remove("--base")
        print(">>> Dùng MODEL GỐC (không adapter)\n")
    else:
        print(">>> Dùng MODEL FINE-TUNED (nếu có adapter)\n")

    if args and pathlib.Path(args[0]).exists():
        questions = [l.strip() for l in open(args[0], encoding="utf-8") if l.strip()]
    else:
        questions = DEFAULT_QUESTIONS

    rag._load_llm()  # nạp model 1 lần
    for i, q in enumerate(questions, 1):
        print(f"\n{'#'*70}\n[{i}/{len(questions)}] {q}")
        rag.answer(q)


if __name__ == "__main__":
    main()
