# -*- coding: utf-8 -*-
"""طباعة الريسيت: 
  windows  = أي طابعة متعرفة على ويندوز (أفضل خيار للعربي - الدرايفر بيتولى الحروف)
  winraw   = ESC/POS خام عبر طابعة ويندوز (يفتح الدرج ويقص الورق)
  network  = طابعة شبكة IP:9100
  serial   = طابعة/درج على منفذ COM
  none     = معاينة فقط"""
import socket, sys

try:
    import win32print, win32ui, win32con
    HAVE_WIN = True
except Exception:
    HAVE_WIN = False

def list_printers():
    if not HAVE_WIN: return []
    try:
        return [p[2] for p in win32print.EnumPrinters(2 | 4)]
    except Exception:
        return []

def money(v):
    s = ("%.2f" % float(v))
    return s[:-3] if s.endswith(".00") else s

def build_receipt(db, sale, items, user_name, customer_name=""):
    """يرجع قائمة أسطر: ('c',txt) ('lr',left,right) ('r',txt) ('sep',) ('big',txt)"""
    L = [("big", db.get("shop_name", "المحل") or "المحل")]
    for k in ("shop_address", "shop_phone"):
        if db.get(k): L.append(("c", db.get(k)))
    L += [("sep",), ("lr", "فاتورة رقم", str(sale["id"])), ("lr", "التاريخ", sale["created"]),
          ("lr", "الكاشير", user_name)]
    if customer_name: L.append(("lr", "العميل", customer_name))
    L.append(("sep",))
    for it in items:
        L.append(("r", it["name"]))
        L.append(("lr", "%s × %s" % (money(it["qty"]), money(it["price"])), money(it["qty"] * it["price"])))
        if it["addons"]:
            L.append(("r", "  + " + it["addons"]))
            L.append(("lr", "  إضافات", money(it["addons_total"] * it["qty"])))
    L.append(("sep",))
    L.append(("lr", "الإجمالي الفرعي", money(sale["subtotal"])))
    if sale["discount"]: L.append(("lr", "الخصم", "-" + money(sale["discount"])))
    L.append(("big", "الإجمالي: " + money(sale["total"])))
    L.append(("lr", "المدفوع", money(sale["paid"])))
    rest = sale["paid"] - sale["total"]
    if rest >= 0: L.append(("lr", "الباقي", money(rest)))
    else: L.append(("lr", "متبقي آجل", money(-rest)))
    L += [("sep",), ("c", db.get("receipt_footer", "شكراً لزيارتكم"))]
    return L

def receipt_text(lines, width=42):
    out = []
    for l in lines:
        k = l[0]
        if k == "sep": out.append("-" * width)
        elif k in ("c", "big"): out.append(l[1].center(width))
        elif k == "r": out.append(l[1].rjust(width))
        elif k == "lr":
            left, right = l[1], l[2]
            out.append(right + " " * max(1, width - len(left) - len(right)) + left)
    return "\n".join(out)

def _escpos_bytes(lines, db):
    width = int(db.get("paper_chars", "42") or 42)
    cp = int(db.get("escpos_codepage", "22") or 22)
    enc = db.get("escpos_encoding", "cp1256") or "cp1256"
    b = b"\x1b@" + b"\x1bt" + bytes([cp])
    for l in lines:
        if l[0] == "big":
            b += b"\x1b\x61\x01\x1d!\x11" + l[1].encode(enc, "replace") + b"\x1d!\x00\n"
        else:
            txt = receipt_text([l], width)
            b += b"\x1b\x61\x00" + txt.encode(enc, "replace") + b"\n"
    b += b"\n\n\n\x1dV\x42\x00"
    if db.get("open_drawer", "0") == "1": b += b"\x1bp\x00\x19\xfa"
    return b

DRAWER = b"\x1bp\x00\x19\xfa"

def _send_raw(db, data):
    mode = db.get("printer_mode", "none")
    if mode == "network":
        host = db.get("printer_ip", "")
        port = int(db.get("printer_port", "9100") or 9100)
        with socket.create_connection((host, port), timeout=6) as s: s.sendall(data)
    elif mode == "serial":
        import serial
        with serial.Serial(db.get("printer_com", "COM1"), int(db.get("printer_baud", "9600") or 9600), timeout=3) as s:
            s.write(data)
    elif mode == "winraw":
        if not HAVE_WIN: raise RuntimeError("pywin32 غير متاح")
        h = win32print.OpenPrinter(db.get("printer_name"))
        try:
            win32print.StartDocPrinter(h, 1, ("Receipt", None, "RAW"))
            win32print.StartPagePrinter(h); win32print.WritePrinter(h, data)
            win32print.EndPagePrinter(h); win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)

def _print_gdi(lines, db):
    if not HAVE_WIN: raise RuntimeError("pywin32 غير متاح (الطباعة عبر درايفر ويندوز بتشتغل على ويندوز بس)")
    name = db.get("printer_name") or win32print.GetDefaultPrinter()
    dc = win32ui.CreateDC(); dc.CreatePrinterDC(name)
    W = dc.GetDeviceCaps(win32con.HORZRES)
    dpi = dc.GetDeviceCaps(win32con.LOGPIXELSX) or 203
    base = int(dpi * 0.115)          # ~ حجم خط 8-9 نقطة
    def mk(h, bold=False):
        return win32ui.CreateFont({"name": db.get("receipt_font", "Tahoma"), "height": -h, "weight": 700 if bold else 400, "charset": 178})
    f, fb = mk(base), mk(int(base * 1.5), True)
    dc.StartDoc("Receipt"); dc.StartPage()
    y = 10; M = 8
    RTL = 0x00020000  # DT_RTLREADING
    for l in lines:
        k = l[0]
        if k == "big":
            dc.SelectObject(fb); h = dc.GetTextExtent("Ag")[1] + 4
            dc.DrawText(l[1], (M, y, W - M, y + h), win32con.DT_CENTER | RTL | win32con.DT_SINGLELINE); y += h
        else:
            dc.SelectObject(f); h = dc.GetTextExtent("Ag")[1] + 2
            if k == "sep":
                dc.MoveTo((M, y + h // 2)); dc.LineTo((W - M, y + h // 2))
            elif k == "c":
                dc.DrawText(l[1], (M, y, W - M, y + h), win32con.DT_CENTER | RTL | win32con.DT_SINGLELINE)
            elif k == "r":
                dc.DrawText(l[1], (M, y, W - M, y + h), win32con.DT_RIGHT | RTL | win32con.DT_SINGLELINE)
            elif k == "lr":
                dc.DrawText(l[1], (M, y, W - M, y + h), win32con.DT_RIGHT | RTL | win32con.DT_SINGLELINE)
                dc.DrawText(l[2], (M, y, W - M, y + h), win32con.DT_LEFT | win32con.DT_SINGLELINE)
            y += h
    dc.EndPage(); dc.EndDoc(); dc.DeleteDC()
    if db.get("open_drawer", "0") == "1":
        try:
            h = win32print.OpenPrinter(name)
            win32print.StartDocPrinter(h, 1, ("Drawer", None, "RAW")); win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, DRAWER); win32print.EndPagePrinter(h); win32print.EndDocPrinter(h)
            win32print.ClosePrinter(h)
        except Exception:
            pass

def print_receipt(db, lines):
    mode = db.get("printer_mode", "none")
    if mode == "none": return False
    if mode == "windows": _print_gdi(lines, db)
    else: _send_raw(db, _escpos_bytes(lines, db))
    return True

def open_drawer(db):
    mode = db.get("printer_mode", "none")
    if mode in ("network", "serial", "winraw"): _send_raw(db, DRAWER)
    elif mode == "windows" and HAVE_WIN:
        h = win32print.OpenPrinter(db.get("printer_name") or win32print.GetDefaultPrinter())
        win32print.StartDocPrinter(h, 1, ("Drawer", None, "RAW")); win32print.StartPagePrinter(h)
        win32print.WritePrinter(h, DRAWER); win32print.EndPagePrinter(h); win32print.EndDocPrinter(h)
        win32print.ClosePrinter(h)
