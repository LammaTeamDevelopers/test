# -*- coding: utf-8 -*-
"""كاشير برو - برنامج نقطة بيع خفيف (Python 3.8 / Tkinter / SQLite)"""
import os, queue, re, shutil, sys, threading, time
import tkinter as tk
from tkinter import ttk, messagebox
import auth, notify, ops
from db import DB, now, DB_PATH
from ui_common import setup_style, center, ask_form, num
from screen_pos import POS
from screen_data import Products, Addons, Customers, Inventory, Expenses
from screen_admin import Reports, Shift, Users, Settings

APP_NAME = "كاشير برو"
SCREENS = [  # (مفتاح, عنوان, class, للمدير فقط)
    ("pos", "نقطة البيع", POS, False), ("products", "الأصناف", Products, True), ("addons", "الإضافات", Addons, True),
    ("customers", "العملاء", Customers, False), ("inventory", "الجرد", Inventory, True), ("expenses", "المصروفات", Expenses, False),
    ("reports", "التقارير وكشف الحساب", Reports, True), ("shift", "الشفت", Shift, False),
    ("users", "المستخدمين", Users, True), ("settings", "الإعدادات", Settings, True)]
BAR = "#1f3a5f"; BTN = "#2c5282"; BTN_ACTIVE = "#3b6db3"; GREEN = "#2f855a"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME); self.geometry("1150x700"); self.minsize(980, 600); setup_style(self)
        self.db = DB(); self.user = None; self.shift = None; self.screen = None; self.scan_q = queue.Queue(); self._scan_stop = None
        self.protocol("WM_DELETE_WINDOW", self.on_close); self.show_login(); self.after(300, self.poll_scan)

    @property
    def is_admin(self): return bool(self.user and self.user["role"] == "admin")

    def clear(self):
        for w in self.winfo_children(): w.destroy()
        self.screen = None
        for k in ("<F2>", "<F12>", "<Escape>"): self.unbind(k)

    # ---------------------------------------------------------- الدخول
    def show_login(self):
        self.clear(); self.user = None; self.shift = None
        outer = ttk.Frame(self); outer.pack(expand=True)
        first = self.db.one("SELECT COUNT(*) c FROM users")["c"] == 0
        ttk.Label(outer, text=APP_NAME, font=("Tahoma", 30, "bold"), foreground=BAR).pack(pady=(0, 4))
        ttk.Label(outer, text="إنشاء حساب المدير (أول تسجيل)" if first else "تسجيل الدخول", style="Title.TLabel").pack(pady=(0, 14))
        card = ttk.Frame(outer, padding=10); card.pack()
        rows = []
        if first: rows.append(("name", "الاسم", False))
        rows += [("ident", "الإيميل أو رقم الموبايل", False), ("pw", "كلمة السر", True)]
        if first: rows.append(("pw2", "تأكيد كلمة السر", True))
        ent = {}
        for i, (k, lbl, secret) in enumerate(rows):
            ttk.Label(card, text=lbl).grid(row=i, column=1, sticky="e", padx=8, pady=6)
            e = ttk.Entry(card, width=32, justify="left", show="*" if secret else "", font=("Tahoma", 12)); e.grid(row=i, column=0, pady=6); ent[k] = e
        showv = tk.BooleanVar()
        def tog():
            for k in ("pw", "pw2"):
                if k in ent: ent[k].config(show="" if showv.get() else "*")
        ttk.Checkbutton(card, text="إظهار كلمة السر", variable=showv, command=tog).grid(row=len(rows), column=0, sticky="e")
        msg = ttk.Label(outer, text="", foreground="#b00020"); msg.pack(pady=4)
        def go(_=None):
            if first:
                if ent["pw"].get() != ent["pw2"].get(): msg.config(text="كلمتين السر مش متطابقين"); return
                uid, err = auth.register(self.db, ent["name"].get(), ent["ident"].get(), ent["pw"].get(), "admin")
                if err: msg.config(text=err); return
                if not self.db.get("shop_name"): self.db.set("shop_name", "محلي")
            u, err = auth.login(self.db, ent["ident"].get(), ent["pw"].get())
            if err: msg.config(text=err); return
            self.user = u; self.start_session()
        ttk.Button(outer, text="إنشاء الحساب والدخول" if first else "دخول", style="Big.TButton", command=go).pack(fill="x", padx=30)
        if not first: ttk.Button(outer, text="نسيت كلمة السر؟", command=self.forgot).pack(pady=8)
        self.bind("<Return>", go); list(ent.values())[0].focus_set()

    def forgot(self):
        d = tk.Toplevel(self); d.title("استعادة كلمة السر"); d.transient(self); d.resizable(False, False)
        chans = {"إيميل (Gmail)": "email", "رسالة SMS": "sms", "واتساب": "whatsapp"}
        st = {"uid": None, "last": 0}
        ttk.Label(d, text="الإيميل أو رقم الموبايل").grid(row=0, column=1, sticky="e", padx=10, pady=6)
        ident = ttk.Entry(d, width=30); ident.grid(row=0, column=0, padx=10)
        ttk.Label(d, text="إرسال الكود عن طريق").grid(row=1, column=1, sticky="e", padx=10, pady=6)
        ch = ttk.Combobox(d, values=list(chans), state="readonly", width=27); ch.current(0); ch.grid(row=1, column=0)
        msg = ttk.Label(d, text="", wraplength=360, foreground="#444"); msg.grid(row=5, column=0, columnspan=2, pady=6)
        ttk.Label(d, text="الكود (6 أرقام)").grid(row=3, column=1, sticky="e", padx=10, pady=6)
        code = ttk.Entry(d, width=30); code.grid(row=3, column=0)
        ttk.Label(d, text="كلمة السر الجديدة").grid(row=4, column=1, sticky="e", padx=10, pady=6)
        npw = ttk.Entry(d, width=30, show="*"); npw.grid(row=4, column=0)
        def send():
            if time.time() - st["last"] < 60: msg.config(text="استنى دقيقة قبل ما تطلب كود تاني"); return
            u = auth.find_user(self.db, ident.get()); st["last"] = time.time()
            if u and u["active"]:
                c = auth.create_otp(self.db, u["id"]); st["uid"] = u["id"]
                try: notify.send_otp(self.db, chans[ch.get()], u, c)
                except notify.NotifyError as e: msg.config(text=str(e)); st["uid"] = None; return
            msg.config(text="لو الحساب موجود فهيوصله كود صالح 10 دقايق. اكتب الكود وكلمة السر الجديدة.")
        def reset():
            if not st["uid"]: msg.config(text="اطلب الكود الأول"); return
            ok, err = auth.verify_otp(self.db, st["uid"], code.get())
            if not ok: msg.config(text=err); return
            err = auth.set_password(self.db, st["uid"], npw.get())
            if err: msg.config(text=err); return
            messagebox.showinfo("تم", "تم تغيير كلمة السر. سجّل دخول بيها.", parent=d); d.destroy()
        ttk.Button(d, text="إرسال الكود", command=send).grid(row=2, column=0, pady=6)
        ttk.Button(d, text="تغيير كلمة السر", command=reset).grid(row=6, column=0, pady=10)
        center(d, self); ident.focus_set(); d.grab_set()

    # ---------------------------------------------------------- الجلسة
    def start_session(self):
        self.shift = ops.current_shift(self.db, self.user["id"])
        self.clear(); self.unbind("<Return>")
        bar = tk.Frame(self, bg=BAR); bar.pack(fill="x")
        self.btns = {}
        def mk(text, cmd, bg=BTN):
            b = tk.Button(bar, text=text, command=cmd, bg=bg, fg="white", activebackground=BTN_ACTIVE, activeforeground="white", relief="flat",
                          font=("Tahoma", 10, "bold"), padx=10, pady=8, bd=0, cursor="hand2"); b.pack(side="right", padx=1, pady=4); return b
        for key, title, cls, adm in SCREENS:
            if adm and not self.is_admin: continue
            self.btns[key] = mk(title, lambda k=key: self.go(k))
        if self.is_admin:  # اختصارات الإضافة السريعة
            tk.Frame(bar, width=14, bg=BAR).pack(side="right")
            mk("+ صنف", lambda: self.quick("products", "new"), GREEN); mk("+ إضافة", lambda: self.quick("addons", "new"), GREEN)
            mk("تغيير الأسعار", lambda: self.quick("products", "bulk_price"), "#b7791f")
        tk.Button(bar, text="خروج", command=self.logout, bg="#9b2c2c", fg="white", relief="flat", font=("Tahoma", 10, "bold"), padx=10, pady=8, bd=0).pack(side="left", padx=4)
        self.who = tk.Label(bar, bg=BAR, fg="#cbd5e0", font=("Tahoma", 10)); self.who.pack(side="left", padx=10)
        self.body = ttk.Frame(self); self.body.pack(fill="both", expand=True)
        self.ensure_shift(); self.update_who(); self.go("pos"); self.start_scanner()

    def update_who(self):
        s = ("شفت #%d مفتوح" % self.shift["id"]) if self.shift else "لا يوجد شفت مفتوح"
        self.who.config(text="%s (%s)  |  %s" % (self.user["name"], "مدير" if self.is_admin else "كاشير", s))

    def go(self, key):
        if self.screen is not None: self.screen.destroy()
        for k in ("<F2>", "<F12>", "<Escape>"): self.unbind(k)
        cls = next(c for k, t, c, a in SCREENS if k == key)
        self.screen = cls(self.body, self); self.screen.pack(fill="both", expand=True)
        for k, b in self.btns.items(): b.config(bg=BTN_ACTIVE if k == key else BTN)
        self.cur = key

    def quick(self, key, action):
        self.go(key); getattr(self.screen, action)()

    def ensure_shift(self):
        if self.shift: return True
        r = ask_form(self, "فتح شفت جديد", [("c", "النقدية في الدرج (العهدة)", "0", "text")], ok="فتح الشفت")
        if not r or num(r["c"]) is None: return False
        self.shift = ops.current_shift(self.db, self.user["id"]) or self.db.one("SELECT * FROM shifts WHERE id=?", (ops.open_shift(self.db, self.user["id"], num(r["c"])),))
        self.update_who(); return True

    def logout(self):
        if self.shift and not messagebox.askyesno("خروج", "الشفت لسه مفتوح. تسجيل الخروج من غير إغلاقه؟\n(تقدر تقفله من شاشة الشفت)", parent=self): return
        self.show_login()

    # ---------------------------------------------------------- سكانر سيريال (اختياري)
    def start_scanner(self):
        if self._scan_stop: self._scan_stop.set(); self._scan_stop = None
        com = self.db.get("scanner_com")
        if not com: return
        stop = threading.Event(); self._scan_stop = stop; baud = int(num(self.db.get("scanner_baud", "9600"), 9600))
        def run():
            try:
                import serial; s = serial.Serial(com, baud, timeout=0.5)
            except Exception: return
            buf = b""
            while not stop.is_set():
                try: buf += s.read(64)
                except Exception: break
                while True:
                    m = re.search(rb"[\r\n]", buf)
                    if not m: break
                    line, buf = buf[:m.start()].strip(), buf[m.end():]
                    if line: self.scan_q.put(line.decode("ascii", "ignore"))
            try: s.close()
            except Exception: pass
        threading.Thread(target=run, daemon=True).start()
    def poll_scan(self):
        try:
            while True:
                code = self.scan_q.get_nowait()
                if getattr(self, "cur", "") == "pos" and isinstance(self.screen, POS): self.screen.on_barcode(code)
        except queue.Empty: pass
        self.after(200, self.poll_scan)

    # ---------------------------------------------------------- خروج + نسخة احتياطية تلقائية
    def on_close(self):
        try:
            d = os.path.join(os.path.expanduser("~"), "Documents", "CashierPro_Backups"); os.makedirs(d, exist_ok=True)
            self.db.backup(os.path.join(d, "cashier_%s.db" % time.strftime("%Y%m%d")))
            for f in sorted(os.listdir(d))[:-14]: os.remove(os.path.join(d, f))
        except Exception: pass
        if self._scan_stop: self._scan_stop.set()
        self.destroy()

if __name__ == "__main__":
    App().mainloop()
