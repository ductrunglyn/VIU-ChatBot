"""Đọc văn bản từ tệp Word 97-2003 (.doc) — định dạng nhị phân OLE2.

Thư viện python-docx chỉ đọc được .docx (XML). Với .doc cũ, mô-đun này phân tích
trực tiếp cấu trúc tệp theo đặc tả Microsoft Word Binary File Format:

  - Tệp .doc là một OLE2 compound file, văn bản nằm trong luồng "WordDocument".
  - Khối FIB (File Information Block) ở đầu luồng cho biết vị trí văn bản.
  - Tệp lưu kiểu "complex" (fast-save) không lưu văn bản liền mạch mà chia thành
    nhiều mảnh; bảng mảnh (piece table) nằm trong luồng "1Table"/"0Table" và cho
    biết mỗi mảnh nằm ở đâu, mã hóa CP1252 hay UTF-16LE.

Cách dùng: extract_doc_text(Path("tep.doc")) -> str
"""
from __future__ import annotations
import struct
from pathlib import Path

# Vị trí các trường trong FIB (theo đặc tả [MS-DOC])
_OFF_FLAGS = 0x000A     # cờ, chứa fComplex và fWhichTblStm
_OFF_FC_MIN = 0x0018    # vị trí bắt đầu văn bản (khi không complex)
_OFF_FC_MAC = 0x001C    # vị trí kết thúc văn bản
_OFF_FC_CLX = 0x01A2    # vị trí bảng Clx trong luồng Table
_OFF_LCB_CLX = 0x01A6   # độ dài bảng Clx

_FLAG_COMPLEX = 0x0004
_FLAG_WHICH_TBL = 0x0200


_ALLOWED_CTRL = "\r\n\t\x07\x0b\x0c\x13\x14\x15\x1e\x1f\x01\x02\x08"


def _score(text: str) -> float:
    """Tỉ lệ ký tự hợp lệ — dùng để chọn bảng mã đúng."""
    if not text:
        return 0.0
    bad = sum(1 for c in text
              if c == "�" or (ord(c) < 32 and c not in _ALLOWED_CTRL))
    return 1.0 - bad / len(text)


def _decode_piece(data: bytes, is_ansi: bool) -> str:
    if is_ansi:
        return data.decode("cp1252", errors="replace")
    return data.decode("utf-16-le", errors="replace")


def _decode_auto(data: bytes) -> str:
    """Tự nhận diện bảng mã: Word lưu văn bản dạng 8-bit (CP1252) hoặc UTF-16LE.

    Cờ trong FIB không phải lúc nào cũng phản ánh đúng, nên chọn theo tỉ lệ ký tự
    hợp lệ của từng cách giải mã.
    """
    best, best_score = "", -1.0
    for enc in ("utf-16-le", "cp1252"):
        try:
            s = data.decode(enc, errors="replace")
        except Exception:  # noqa: BLE001
            continue
        sc = _score(s)
        if sc > best_score:
            best, best_score = s, sc
    return best


def _parse_piece_table(table: bytes, fc_clx: int, lcb_clx: int):
    """Tách bảng mảnh (piece table) từ luồng Table. Trả về danh sách (cp_start, fc, is_ansi)."""
    clx = table[fc_clx:fc_clx + lcb_clx]
    i = 0
    # Clx gồm dãy phần tử: 0x01 = Prc (bỏ qua), 0x02 = Pcdt (bảng mảnh cần tìm)
    while i < len(clx):
        kind = clx[i]
        if kind == 0x01:                      # Prc: bỏ qua theo độ dài khai báo
            if i + 3 > len(clx):
                break
            cb = struct.unpack_from("<H", clx, i + 1)[0]
            i += 3 + cb
        elif kind == 0x02:                    # Pcdt: bảng mảnh
            lcb = struct.unpack_from("<I", clx, i + 1)[0]
            pcdt = clx[i + 5:i + 5 + lcb]
            n = (len(pcdt) - 4) // 12         # mỗi mảnh: 4 byte CP + 8 byte PCD
            cps = [struct.unpack_from("<I", pcdt, 4 * k)[0] for k in range(n + 1)]
            pieces = []
            base = 4 * (n + 1)
            for k in range(n):
                fc_raw = struct.unpack_from("<I", pcdt, base + 8 * k + 2)[0]
                is_ansi = bool(fc_raw & 0x40000000)
                fc = (fc_raw & ~0xC0000000) // 2 if is_ansi else (fc_raw & ~0xC0000000)
                pieces.append((cps[k], cps[k + 1], fc, is_ansi))
            return pieces
        else:
            break
    return []


def extract_doc_text(path: Path) -> str:
    """Trích toàn bộ văn bản từ tệp .doc (Word 97-2003)."""
    import olefile

    path = Path(path)
    if not olefile.isOleFile(str(path)):
        raise ValueError(f"'{path.name}' không phải tệp .doc hợp lệ (OLE2).")

    ole = olefile.OleFileIO(str(path))
    try:
        doc = ole.openstream("WordDocument").read()
        flags = struct.unpack_from("<H", doc, _OFF_FLAGS)[0]
        complex_fmt = bool(flags & _FLAG_COMPLEX)
        tbl_name = "1Table" if (flags & _FLAG_WHICH_TBL) else "0Table"

        if not complex_fmt or not ole.exists(tbl_name):
            # Văn bản lưu liền mạch: đọc thẳng theo fcMin..fcMac
            fc_min = struct.unpack_from("<I", doc, _OFF_FC_MIN)[0]
            fc_mac = struct.unpack_from("<I", doc, _OFF_FC_MAC)[0]
            return _clean(_decode_auto(doc[fc_min:fc_mac]))

        table = ole.openstream(tbl_name).read()
        fc_clx = struct.unpack_from("<I", doc, _OFF_FC_CLX)[0]
        lcb_clx = struct.unpack_from("<I", doc, _OFF_LCB_CLX)[0]
        pieces = _parse_piece_table(table, fc_clx, lcb_clx)
        if not pieces:
            fc_min = struct.unpack_from("<I", doc, _OFF_FC_MIN)[0]
            fc_mac = struct.unpack_from("<I", doc, _OFF_FC_MAC)[0]
            return _clean(_decode_auto(doc[fc_min:fc_mac]))

        out = []
        for cp_start, cp_end, fc, is_ansi in pieces:
            n_chars = cp_end - cp_start
            n_bytes = n_chars if is_ansi else n_chars * 2
            out.append(_decode_piece(doc[fc:fc + n_bytes], is_ansi))
        return _clean("".join(out))
    finally:
        ole.close()


def _clean(text: str) -> str:
    """Đổi ký tự điều khiển riêng của Word thành ký tự văn bản thường."""
    repl = {
        "\r": "\n",      # kết thúc đoạn
        "\x07": "\n",    # kết thúc ô/hàng bảng
        "\x0b": "\n",    # ngắt dòng mềm
        "\x0c": "\n",    # ngắt trang
        "\x1e": "-",     # gạch nối không ngắt
        "\x1f": "",      # gạch nối tùy chọn
        "\xa0": " ",     # khoảng trắng không ngắt
        "\x13": "", "\x14": "", "\x15": "",   # dấu trường (field)
        "\x01": "", "\x02": "", "\x08": "",   # ký tự nhúng ảnh/đối tượng
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()
