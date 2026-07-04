"""Giai đoạn 5: Giao diện web chatbot (Gradio) cho cố vấn học tập VIU.

Nạp model 1 lần khi khởi động, phục vụ nhiều người qua trình duyệt. Câu trả lời
hiện dần (streaming) và kèm nguồn trích dẫn.

Cách chạy (nên trong screen để chạy nền lâu dài):
    conda activate test
    python src/Phase5-UI/app.py
Rồi mở trình duyệt:
    - Trên chính máy chủ:  http://localhost:7860
    - Máy khác cùng mạng LAN:  http://<IP-máy-chủ>:7860   (xem IP bằng lệnh `hostname -I`)
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Phase3-RAG"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import rag

import gradio as gr

DESCRIPTION = (
    "Trợ lý AI trả lời câu hỏi về **quy chế, chương trình đào tạo, tuyển sinh** và "
    "**tư vấn lộ trình học tập** cho sinh viên Trường ĐHCN Việt - Hung. "
    "Câu trả lời dựa trên tài liệu chính thức của trường và có trích dẫn nguồn. "
    "⚠️ Thông tin mang tính tham khảo — trường hợp quan trọng hãy xác nhận lại với "
    "phòng đào tạo / cố vấn học tập."
)

EXAMPLES = [
    "Sinh viên bị cảnh báo học tập trong những trường hợp nào?",
    "Điều kiện để được xét tốt nghiệp là gì?",
    "Học phần Mạng máy tính của ngành Khoa học máy tính có mấy tín chỉ?",
    "Em còn nợ 3 môn và CPA 1.9, nên làm gì để ra trường đúng hạn?",
]


def _as_text(content):
    """Ép nội dung tin nhắn về chuỗi (Gradio 6 có thể trả list/dict cho content)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for p in content:
            if isinstance(p, str):
                out.append(p)
            elif isinstance(p, dict):
                out.append(p.get("text") or p.get("content") or "")
        return " ".join(out)
    if isinstance(content, dict):
        return content.get("text") or content.get("content") or ""
    return str(content) if content is not None else ""


def _history_to_pairs(history):
    """Đổi history dạng messages của Gradio -> danh sách (câu hỏi, câu trả lời)."""
    pairs, pending = [], None
    for m in history:
        role = m.get("role") if isinstance(m, dict) else None
        content = _as_text(m.get("content") if isinstance(m, dict) else None)
        # bỏ phần '📚 Nguồn tham khảo' đã gắn ở câu trả lời trước cho gọn ngữ cảnh
        content = content.split("\n\n---\n📚")[0].strip()
        if role == "user":
            pending = content
        elif role == "assistant" and pending is not None:
            pairs.append((pending, content))
            pending = None
    return pairs[-config.UI_HISTORY_TURNS:]  # chỉ giữ vài lượt gần nhất


def chat_fn(message, history):
    """Hàm trả lời cho Gradio ChatInterface (generator, streaming)."""
    pairs = _history_to_pairs(history)
    partial, sources = "", []
    for partial, sources in rag.answer_stream(message, pairs):
        yield partial
    if sources:
        refs = "\n".join(f"- {s}" for s in sources)
        yield partial + "\n\n---\n📚 **Nguồn tham khảo:**\n" + refs


def main():
    print("Đang nạp model (embedding + rerank + LLM)... vui lòng chờ ~1 phút.")
    rag._load_llm()                 # nạp LLM + adapter
    list(rag.answer_stream("xin chào", []))[:1]  # làm nóng retriever/reranker
    print("✅ Sẵn sàng. Khởi động giao diện web...")

    demo = gr.ChatInterface(
        fn=chat_fn,
        title="🎓 Cố vấn học tập AI — ĐHCN Việt - Hung",
        description=DESCRIPTION,
        examples=EXAMPLES,
        concurrency_limit=1,   # 1 GPU -> xử lý tuần tự, tránh tranh model
    )
    demo.launch(server_name="0.0.0.0", server_port=config.UI_PORT, share=False)


if __name__ == "__main__":
    main()
