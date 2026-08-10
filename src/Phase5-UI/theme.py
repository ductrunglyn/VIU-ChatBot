"""Nhận diện thương hiệu cho giao diện web: màu, logo, CSS.

Tách riêng khỏi app.py để phần logic hội thoại không bị lẫn với phần trình bày.

Màu và logo lấy từ chính bộ nhận diện của Trường ĐHCN Việt - Hung:
    xanh  #0082BC   (chữ lồng VH và tên trường)
    cam   #EA902F   (dòng "VIET HUNG INDUSTRIAL UNIVERSITY")
"""
from __future__ import annotations
import base64
import pathlib

ASSETS = pathlib.Path(__file__).resolve().parents[2] / "assets"
LOGO = ASSETS / "viu_logo.png"          # chữ lồng VH, nền trong suốt
LOCKUP = ASSETS / "viu_lockup.png"      # logo + tên trường đầy đủ

BLUE = "#0082BC"
BLUE_DARK = "#00629A"
ORANGE = "#EA902F"


def data_uri(path: pathlib.Path) -> str:
    """Nhúng ảnh thẳng vào HTML dạng base64.

    Cách này tránh phải mở thêm đường dẫn tệp tĩnh cho máy chủ, và ảnh hiện ngay
    cả khi trang được mở từ máy khác trong mạng LAN.
    """
    if not path.exists():
        return ""
    return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}"


def header_html() -> str:
    src = data_uri(LOCKUP)
    logo = (f'<img src="{src}" alt="Trường Đại học Công nghiệp Việt - Hung" '
            f'class="viu-lockup">') if src else ""
    return f"""
<div class="viu-header">
  {logo}
  <div class="viu-header-text">
    <h1>Cố vấn học tập AI</h1>
    <p>Giải đáp quy chế đào tạo · chuẩn đầu ra · học phí · lộ trình học tập</p>
  </div>
</div>
"""


def sidebar_brand_html() -> str:
    src = data_uri(LOGO)
    img = f'<img src="{src}" alt="VIU" class="viu-mark">' if src else ""
    return f"""
<div class="viu-brand">
  {img}
  <div>
    <strong>ĐHCN Việt - Hung</strong>
    <span>Trợ lý học vụ</span>
  </div>
</div>
"""


CSS = f"""
:root {{
  --viu-blue: {BLUE};
  --viu-blue-dark: {BLUE_DARK};
  --viu-orange: {ORANGE};
}}

.gradio-container {{ max-width: 100% !important; }}

/* ---- Dải tiêu đề ---- */
.viu-header {{
  display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
  padding: 18px 24px; margin-bottom: 12px;
  border-radius: 14px;
  background: linear-gradient(100deg, #ffffff 0%, #eaf6fc 55%, #d7edf8 100%);
  border: 1px solid rgba(0, 130, 188, .18);
}}
.viu-header .viu-lockup {{ height: 62px; width: auto; }}
.viu-header-text h1 {{
  margin: 0; font-size: 1.45rem; font-weight: 700; color: var(--viu-blue-dark);
  line-height: 1.25;
}}
.viu-header-text p {{ margin: 4px 0 0; font-size: .92rem; color: #4a5c68; }}

/* Nền tối: dải tiêu đề chuyển sang tông đậm cho dễ đọc */
.dark .viu-header {{
  background: linear-gradient(100deg, #10202b 0%, #123246 60%, #0d2939 100%);
  border-color: rgba(0, 130, 188, .35);
}}
.dark .viu-header-text h1 {{ color: #7ecbee; }}
.dark .viu-header-text p {{ color: #a9bcc8; }}

/* ---- Khối thương hiệu trong thanh bên ---- */
.viu-brand {{ display: flex; align-items: center; gap: 12px; padding: 4px 2px 14px; }}
.viu-brand .viu-mark {{ height: 40px; width: auto; }}
.viu-brand strong {{ display: block; font-size: .98rem; color: var(--viu-blue-dark); }}
.viu-brand span {{ font-size: .8rem; color: #6b7c88; }}
.dark .viu-brand strong {{ color: #7ecbee; }}

/* ---- Danh sách đoạn chat ---- */
.viu-convo-btn {{
  text-align: left !important; justify-content: flex-start !important;
  font-weight: 400 !important; font-size: .88rem !important;
  padding: 8px 10px !important; margin-bottom: 2px !important;
  border: none !important; background: transparent !important;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.viu-convo-btn:hover {{ background: rgba(0, 130, 188, .10) !important; }}
.viu-convo-active {{
  background: rgba(0, 130, 188, .16) !important;
  font-weight: 600 !important; color: var(--viu-blue-dark) !important;
  box-shadow: inset 3px 0 0 var(--viu-blue) !important;
}}
.dark .viu-convo-active {{ color: #7ecbee !important; }}
.viu-del-btn {{
  min-width: 32px !important; max-width: 32px !important;
  padding: 8px 0 !important; border: none !important;
  background: transparent !important; opacity: .45;
}}
.viu-del-btn:hover {{ opacity: 1; color: #d64545 !important; }}
.viu-newchat {{
  background: var(--viu-blue) !important; color: #fff !important;
  border: none !important; font-weight: 600 !important; margin-bottom: 10px !important;
}}
.viu-newchat:hover {{ background: var(--viu-blue-dark) !important; }}
.viu-sidebar-title {{
  font-size: .74rem; letter-spacing: .06em; text-transform: uppercase;
  color: #8a99a5; margin: 6px 2px 6px;
}}

/* ---- Khu hội thoại ---- */
.viu-chatbot {{ border-radius: 14px !important; }}
.viu-send {{
  background: var(--viu-blue) !important; color: #fff !important;
  border: none !important; font-weight: 600 !important;
}}
.viu-send:hover {{ background: var(--viu-blue-dark) !important; }}
.viu-example-btn {{
  font-size: .84rem !important; font-weight: 400 !important;
  border: 1px solid rgba(0, 130, 188, .35) !important;
  background: transparent !important; border-radius: 999px !important;
  padding: 6px 14px !important;
}}
.viu-example-btn:hover {{ background: rgba(0, 130, 188, .10) !important; }}

/* ---- Chân trang ---- */
.viu-foot {{
  margin-top: 10px; padding: 10px 4px; font-size: .8rem; color: #7b8a95;
  border-top: 1px solid rgba(0, 0, 0, .06); text-align: center;
}}
.viu-foot b {{ color: var(--viu-orange); }}
"""
