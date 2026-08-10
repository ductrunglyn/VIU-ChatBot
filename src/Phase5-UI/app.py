"""Giai đoạn 5: Giao diện web chatbot (Gradio) cho cố vấn học tập VIU.

Nạp model 1 lần khi khởi động, phục vụ nhiều người qua trình duyệt. Câu trả lời
hiện dần (streaming) và kèm nguồn trích dẫn.

Giao diện gồm thanh bên lưu LỊCH SỬ CÁC ĐOẠN CHAT: sinh viên mở lại đoạn cũ, đổi
tên hoặc xóa. Lịch sử được lưu bằng gr.BrowserState, tức là nằm trong trình duyệt
của chính sinh viên — máy chủ KHÔNG lưu nội dung hỏi đáp của ai cả, nên vừa không
cần cơ sở dữ liệu vừa tránh chuyện người này thấy đoạn chat của người kia.

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
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Phase3-RAG"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import config
import rag
import theme

import gradio as gr

EXAMPLES = [
    "Sinh viên bị cảnh báo học tập trong những trường hợp nào?",
    "Điều kiện để được xét tốt nghiệp là gì?",
    "Trường công nhận những chứng chỉ ngoại ngữ nào?",
    "Em còn nợ 3 môn và CPA 1.9, nên làm gì để ra trường đúng hạn?",
    "Nộp học phí muộn thì bị xử lý thế nào?",
]

WELCOME = (
    "Chào em 👋 Cô/thầy là trợ lý cố vấn học tập của **Trường ĐHCN Việt - Hung**.\n\n"
    "Em cứ hỏi về quy chế đào tạo, chuẩn đầu ra ngoại ngữ – tin học, học phí, "
    "đào tạo trực tuyến hay lộ trình học tập nhé. Mọi câu trả lời đều dựa trên "
    "văn bản chính thức của Nhà trường và có ghi rõ nguồn."
)

NEW_TITLE = "Đoạn chat mới"
SOURCE_SEP = "\n\n---\n📚 **Nguồn tham khảo:**\n"


# ---------------------------------------------------------------- trạng thái
def _blank_convo() -> dict:
    return {"id": uuid.uuid4().hex, "title": NEW_TITLE, "messages": []}


def _empty_store() -> dict:
    c = _blank_convo()
    return {"convos": [c], "active": c["id"]}


def _normalize(store) -> dict:
    """Chuẩn hóa dữ liệu đọc từ trình duyệt (có thể rỗng, cũ, hoặc hỏng)."""
    if not isinstance(store, dict) or not isinstance(store.get("convos"), list):
        return _empty_store()
    convos = [c for c in store["convos"]
              if isinstance(c, dict) and c.get("id") and isinstance(c.get("messages"), list)]
    if not convos:
        return _empty_store()
    ids = {c["id"] for c in convos}
    active = store.get("active") if store.get("active") in ids else convos[0]["id"]
    return {"convos": convos, "active": active}


def _find(store: dict, cid: str):
    return next((c for c in store["convos"] if c["id"] == cid), None)


def _active(store: dict) -> dict:
    return _find(store, store["active"]) or store["convos"][0]


def _title_from(text: str) -> str:
    t = " ".join((text or "").split())
    return (t[:38] + "…") if len(t) > 38 else (t or NEW_TITLE)


# ------------------------------------------------------- ghép ngữ cảnh cho RAG
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


def _history_to_pairs(messages):
    """Đổi lịch sử dạng messages -> danh sách (câu hỏi, câu trả lời) cho rag."""
    pairs, pending = [], None
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else None
        content = _as_text(m.get("content") if isinstance(m, dict) else None)
        # bỏ phần '📚 Nguồn tham khảo' đã gắn ở câu trả lời trước cho gọn ngữ cảnh
        content = content.split("\n\n---\n📚")[0].strip()
        if role == "user":
            pending = content
        elif role == "assistant" and pending is not None:
            pairs.append((pending, content))
            pending = None
    return pairs[-config.UI_HISTORY_TURNS:]   # chỉ giữ vài lượt gần nhất


# ------------------------------------------------------------------ sự kiện
def on_load(store):
    """Khi mở trang: khôi phục đoạn chat đang dở từ trình duyệt."""
    store = _normalize(store)
    return store, _active(store)["messages"]


def on_submit(message, store):
    """Nhận câu hỏi: ghi vào đoạn chat hiện tại rồi xóa ô nhập."""
    message = (message or "").strip()
    store = _normalize(store)
    if not message:
        return store, _active(store)["messages"], ""
    convo = _active(store)
    convo["messages"] = convo["messages"] + [{"role": "user", "content": message}]
    if convo["title"] == NEW_TITLE:
        convo["title"] = _title_from(message)
    return store, convo["messages"], ""


def on_stream(store):
    """Sinh câu trả lời, hiện dần từng đoạn."""
    store = _normalize(store)
    messages = list(_active(store)["messages"])
    if not messages or messages[-1].get("role") != "user":
        yield messages
        return

    question = _as_text(messages[-1]["content"])
    pairs = _history_to_pairs(messages[:-1])

    messages.append({"role": "assistant", "content": ""})
    partial, sources = "", []
    for partial, sources in rag.answer_stream(question, pairs):
        messages[-1]["content"] = partial
        yield messages
    if sources:
        messages[-1]["content"] = partial + SOURCE_SEP + "\n".join(f"- {s}" for s in sources)
    yield messages


def on_finish(store, messages):
    """Chốt câu trả lời vào lịch sử để lần sau mở lại vẫn còn."""
    store = _normalize(store)
    _active(store)["messages"] = messages or []
    return store


def on_new(store):
    store = _normalize(store)
    # Đoạn chat hiện tại chưa hỏi gì thì dùng luôn, khỏi tạo thêm đoạn rỗng.
    if not _active(store)["messages"]:
        return store, []
    convo = _blank_convo()
    store["convos"] = [convo] + store["convos"]
    store["active"] = convo["id"]
    return store, []


def on_select(store, cid):
    store = _normalize(store)
    if _find(store, cid):
        store["active"] = cid
    return store, _active(store)["messages"]


def on_delete(store, cid):
    store = _normalize(store)
    store["convos"] = [c for c in store["convos"] if c["id"] != cid]
    if not store["convos"]:
        store = _empty_store()
    elif store["active"] == cid:
        store["active"] = store["convos"][0]["id"]
    return store, _active(store)["messages"]


# -------------------------------------------------------------------- giao diện
def build_ui():
    # Gradio 6 chuyển css/theme sang launch(); ở đây chỉ khai báo cấu trúc trang.
    with gr.Blocks(title="Cố vấn học tập AI — ĐHCN Việt - Hung",
                   fill_height=True) as demo:
        # Lịch sử nằm trong trình duyệt của sinh viên, không lưu trên máy chủ.
        store = gr.BrowserState(_empty_store(), storage_key="viu_chat_history_v1")

        with gr.Sidebar(width=290):
            gr.HTML(theme.sidebar_brand_html())
            btn_new = gr.Button("＋  Đoạn chat mới", elem_classes="viu-newchat")
            gr.HTML('<div class="viu-sidebar-title">Lịch sử trò chuyện</div>')
            convo_list = gr.Column()

        gr.HTML(theme.header_html())

        chatbot = gr.Chatbot(
            label=None, height="62vh", elem_classes="viu-chatbot", resizable=True,
            avatar_images=(None, str(theme.LOGO) if theme.LOGO.exists() else None),
            placeholder=f"<div style='padding:8px 4px'>{WELCOME}</div>",
        )

        with gr.Row():
            box = gr.Textbox(
                placeholder="Nhập câu hỏi của em… (Enter để gửi)",
                show_label=False, scale=9, lines=1, max_lines=6, autofocus=True,
            )
            btn_send = gr.Button("Gửi", scale=1, elem_classes="viu-send")

        with gr.Row():
            for q in EXAMPLES:
                gr.Button(q, elem_classes="viu-example-btn", size="sm").click(
                    lambda q=q: q, outputs=box)

        gr.HTML(
            '<div class="viu-foot">Thông tin mang tính tham khảo — trường hợp quan '
            'trọng em hãy xác nhận lại với <b>Phòng Quản lý đào tạo</b> hoặc '
            '<b>cố vấn học tập</b> của lớp.</div>'
        )

        # ---- Danh sách đoạn chat: vẽ lại mỗi khi lịch sử thay đổi ----
        @gr.render(inputs=store, triggers=[demo.load, store.change])
        def _render_list(s):
            s = _normalize(s)
            with convo_list:
                for c in s["convos"]:
                    with gr.Row(equal_height=True):
                        cls = "viu-convo-btn" + (
                            " viu-convo-active" if c["id"] == s["active"] else "")
                        gr.Button(c["title"], elem_classes=cls, scale=9).click(
                            on_select, [store, gr.State(c["id"])], [store, chatbot])
                        gr.Button("🗑", elem_classes="viu-del-btn", scale=1).click(
                            on_delete, [store, gr.State(c["id"])], [store, chatbot])

        # ---- Luồng hỏi - đáp ----
        for trigger in (box.submit, btn_send.click):
            (trigger(on_submit, [box, store], [store, chatbot, box])
             .then(on_stream, store, chatbot, concurrency_limit=1)  # 1 GPU -> tuần tự
             .then(on_finish, [store, chatbot], store))

        btn_new.click(on_new, store, [store, chatbot])
        demo.load(on_load, store, [store, chatbot])

    return demo


def main():
    print("Đang nạp model (embedding + rerank + LLM)... vui lòng chờ ~1 phút.")
    rag._load_llm()                 # nạp LLM + adapter
    list(rag.answer_stream("xin chào", []))[:1]  # làm nóng retriever/reranker
    print("✅ Sẵn sàng. Khởi động giao diện web...")

    build_ui().launch(
        server_name="0.0.0.0", server_port=config.UI_PORT, share=False,
        css=theme.CSS,
        favicon_path=str(theme.LOGO) if theme.LOGO.exists() else None,
        allowed_paths=[str(theme.ASSETS)],   # cho phép phục vụ ảnh đại diện trợ lý
    )


if __name__ == "__main__":
    main()
