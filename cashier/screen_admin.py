# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import auth, ops, printing, notify
from db import now
from ui_common import Table, ask_form, num, money, center
from screen_data import header

# ------------------------------------------------------------ التقارير وكشف الحساب
class Reports(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent); self.app, self.db = app, app.db
        header(self, "التقارير وكشف الحساب", [])
        f = ttk.Frame(self); f.pack(fill="x", padx=10)
        t = now()[:10]
        self.d1 = ttk.Entry(f, width=12, justify="center"); self.d2 = ttk.Entry(f, width=12, justify="center")
        self.users = self.db.q("SELECT id,name FROM users ORDER BY name")
        self.u = ttk.Combobox(f, values=["كل المستخدمين"] + [x["name"] for x in self.users], state="readonly", width=16); self.u.current(0)
        self.u.pack(side="right"); ttk.Label(f, text=" المستخدم ").pack(side="right")
        self.d2.pack(side="right"); ttk.Label(f, text=" إلى ").pack(side="right"); self.d1.pack(side="right"); ttk.Label(f, text="من ").pack(side="right")
        self.d1.insert(0, t); self.d2.insert(0, t)
        ttk.Button(f, text="عرض", command=self.load).pack(side="right", padx=8)
        for lbl, a, b in (("اليوم", 0, 0), ("الشهر", 1, 0)):
            ttk.Button(f, text=lbl, command=lambda m=a: self.quick(m)).pack(side="right", padx=2)
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=8)
        self.sum = ttk.Frame(nb); self.sl = ttk.Frame(nb); self.pr = ttk.Frame(nb); self.ex = ttk.Frame(nb)
        for fr, t_ in ((self.ex, "المصروفات"), (self.pr, "الأصناف والأرباح"), (self.sl, "الفواتير"), (self.sum, "الملخص")): nb.add(fr, text=t_)
        nb.select(self.sum)
        self.sum_lbl = ttk.Label(self.sum, justify="right", font=("Tahoma", 14)); self.sum_lbl.pack(anchor="e", padx=20, pady=20)
        self.st = Table(self.sl, [("id", "رقم", 60), ("d", "التاريخ", 140), ("u", "الكاشير", 90), ("c", "العميل", 100), ("m", "الدفع", 60),
                                  ("t", "الإجمالي", 80), ("p", "المدفوع", 80), ("s", "الحالة", 70)], height=13); self.st.pack(fill="both", expand=True)
        bf = ttk.Frame(self.sl); bf.pack(fill="x", pady=4)
        ttk.Button(bf, text="تصدير", command=lambda: self.st.export(self)).pack(side="left", padx=3)
        ttk.Button(bf, text="إلغاء الفاتورة", command=self.void).pack(side="left", padx=3)
        ttk.Button(bf, text="عرض / إعادة طباعة", command=self.reprint).pack(side="left", padx=3)
        self.pt = Table(self.pr, [("n", "الصنف", 240), ("q", "الكمية", 80), ("s", "المبيعات", 100), ("p", "الربح", 100)], height=13); self.pt.pack(fill="both", expand=True)
        ttk.Button(self.pr, text="تصدير", command=lambda: self.pt.export(self)).pack(anchor="w", pady=4)
        self.et = Table(self.ex, [("d", "التاريخ", 140), ("t", "البند", 220), ("a", "المبلغ", 90), ("u", "المستخدم", 100)], height=13); self.et.pack(fill="both", expand=True)
        self.load()
    def quick(self, m):
        t = now()[:10]; self.d1.delete(0, "end"); self.d1.insert(0, t[:8] + "01" if m else t); self.d2.delete(0, "end"); self.d2.insert(0, t); self.load()
    def uid(self):
        i = self.u.current(); return self.users[i - 1]["id"] if i > 0 else None
    def load(self):
        a, b, u = self.d1.get(), self.d2.get(), self.uid(); s = ops.summary(self.db, a, b, u)
        self.sum_lbl.config(text=("عدد الفواتير: %d\nإجمالي المبيعات: %s\nإجمالي الخصومات: %s\n"
            "نقدي: %s   |   بطاقة: %s   |   آجل: %s\nتكلفة البضاعة المباعة: %s\nالمصروفات: %s\n"
            "━━━━━━━━━━━━━━━━\nصافي الربح: %s") % (s["n"], money(s["total"]), money(s["disc"]), money(s["cash"]), money(s["card"]),
            money(s["credit"]), money(s["cost"]), money(s["expenses"]), money(s["profit"])))
        self.st.clear()
        for r in ops.sales_list(self.db, a, b, u):
            self.st.add((r["id"], r["created"], r["uname"], r["cname"] or "", {"cash": "نقدي", "card": "بطاقة", "credit": "آجل"}[r["method"]],
                         money(r["total"]), money(r["paid"]), "ملغية" if r["voided"] else "سليمة"), iid=r["id"], tags=("void",) if r["voided"] else ())
        self.pt.clear()
        for r in ops.top_products(self.db, a, b): self.pt.add((r["name"], money(r["qty"]), money(r["sales"]), money(r["profit"])))
        self.et.clear()
        for e in ops.expenses_list(self.db, a, b):
            if u is None or e["user_id"] == u: self.et.add((e["created"], e["title"], money(e["amount"]), e["uname"]))
    def void(self):
        i = self.st.sel()
        if i and messagebox.askyesno("إلغاء", "إلغاء الفاتورة %s وإرجاع المخزون؟" % i, parent=self):
            try: ops.void_sale(self.db, int(i), self.app.user["id"]); self.load()
            except ValueError as e: messagebox.showwarning("تنبيه", str(e), parent=self)
    def reprint(self):
        i = self.st.sel()
        if not i: return
        s = dict(self.db.one("SELECT * FROM sales WHERE id=?", (i,)))
        items = [dict(r) for r in self.db.q("SELECT * FROM sale_items WHERE sale_id=?", (i,))]
        u = self.db.one("SELECT name FROM users WHERE id=?", (s["user_id"],)); c = self.db.one("SELECT name FROM customers WHERE id=?", (s["customer_id"],))
        lines = printing.build_receipt(self.db, s, items, u["name"] if u else "", c["name"] if c else "")
        try:
            if not printing.print_receipt(self.db, lines): raise RuntimeError("none")
        except Exception:
            d = tk.Toplevel(self); t = tk.Text(d, width=44, height=26, font=("Courier New", 10)); t.pack(padx=8, pady=8)
            t.insert("1.0", printing.receipt_text(lines)); t.config(state="disabled")

# ------------------------------------------------------------ الشفت
class Shift(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent); self.app, self.db = app, app.db
        header(self, "الشفت", [])
        self.lbl = ttk.Label(self, justify="right", font=("Tahoma", 14)); self.lbl.pack(anchor="e", padx=24, pady=16)
        bf = ttk.Frame(self); bf.pack(pady=6)
        self.b = ttk.Button(bf, text="", command=self.toggle); self.b.pack(side="left", padx=6); self.render()
        ttk.Label(self, text="الشفتات السابقة", style="Title.TLabel").pack(anchor="e", padx=24, pady=(20, 4))
        self.t = Table(self, [("id", "#", 40), ("u", "المستخدم", 100), ("o", "الفتح", 140), ("c", "الإغلاق", 140), ("oc", "عهدة", 70), ("cc", "الجرد الفعلي", 90)], height=8)
        self.t.pack(fill="both", expand=True, padx=24, pady=4)
        for s in self.db.q("SELECT s.*,u.name un FROM shifts s LEFT JOIN users u ON u.id=s.user_id ORDER BY s.id DESC LIMIT 100"):
            self.t.add((s["id"], s["un"], s["opened"], s["closed"] or "مفتوح", money(s["opening_cash"]), "" if s["closing_cash"] is None else money(s["closing_cash"])))
    def render(self):
        sh = self.app.shift
        if not sh: self.lbl.config(text="مفيش شفت مفتوح"); self.b.config(text="فتح شفت جديد"); return
        s = ops.shift_summary(self.db, sh["id"])
        self.lbl.config(text="شفت رقم %d - فُتح %s\nعدد الفواتير: %d     إجمالي المبيعات: %s\nنقدي (للدرج): %s     بطاقة: %s     آجل: %s\n"
                        "عهدة الفتح: %s     تحصيل عملاء: %s     مصروفات: %s\n━━━━━━━━━━━━━━━━\nالمتوقع في الدرج: %s" %
                        (sh["id"], sh["opened"], s["n"], money(s["total"]), money(s["cash"]), money(s["card"]), money(s["credit"]),
                         money(s["opening"]), money(s["cust_payments"]), money(s["expenses"]), money(s["expected"])))
        self.b.config(text="إغلاق الشفت")
    def toggle(self):
        if not self.app.shift:
            self.app.ensure_shift(); self.render(); return
        s = ops.shift_summary(self.db, self.app.shift["id"])
        r = ask_form(self, "إغلاق الشفت", [("c", "النقدية الفعلية في الدرج (المتوقع: %s)" % money(s["expected"]), money(s["expected"]), "text"), ("n", "ملاحظات", "", "text")], ok="إغلاق")
        c = num(r["c"]) if r else None
        if c is None: return
        ops.close_shift(self.db, self.app.shift["id"], c, r["n"]); diff = c - s["expected"]
        messagebox.showinfo("تم إغلاق الشفت", "الفرق: %s  (%s)" % (money(diff), "زيادة" if diff > 0 else "عجز" if diff < 0 else "مظبوط"), parent=self)
        self.app.shift = None; self.render()

# ------------------------------------------------------------ المستخدمين
class Users(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent); self.app, self.db = app, app.db
        header(self, "المستخدمين والشفتات", [("إيقاف / تفعيل", self.toggle), ("تغيير كلمة السر", self.reset), ("مستخدم جديد", self.new)])
        self.t = Table(self, [("n", "الاسم", 160), ("e", "الإيميل", 190), ("p", "الموبايل", 120), ("r", "الصلاحية", 80), ("a", "الحالة", 70)], height=16)
        self.t.pack(fill="both", expand=True, padx=10, pady=6); self.load()
    def load(self):
        self.t.clear()
        for u in self.db.q("SELECT * FROM users ORDER BY id"):
            self.t.add((u["name"], u["email"] or "", u["phone"] or "", "مدير" if u["role"] == "admin" else "كاشير", "نشط" if u["active"] else "موقوف"), iid=u["id"])
    def new(self):
        r = ask_form(self, "مستخدم جديد", [("n", "الاسم", "", "text"), ("i", "الإيميل أو رقم الموبايل", "", "text"), ("p", "كلمة السر", "", "password"), ("r", "الصلاحية", "كاشير", ["كاشير", "مدير"])])
        if not r: return
        uid, err = auth.register(self.db, r["n"], r["i"], r["p"], "admin" if r["r"] == "مدير" else "cashier")
        if err: messagebox.showwarning("خطأ", err, parent=self)
        self.load()
    def reset(self):
        i = self.t.sel()
        if not i: return
        r = ask_form(self, "كلمة سر جديدة", [("p", "كلمة السر الجديدة", "", "password")])
        if r:
            err = auth.set_password(self.db, int(i), r["p"]); messagebox.showinfo("تم", "تم التغيير", parent=self) if not err else messagebox.showwarning("خطأ", err, parent=self)
    def toggle(self):
        i = self.t.sel()
        if not i: return
        if int(i) == self.app.user["id"]: messagebox.showwarning("تنبيه", "مينفعش توقف حسابك", parent=self); return
        self.db.x("UPDATE users SET active=1-active WHERE id=?", (i,)); self.load()

# ------------------------------------------------------------ الإعدادات
PRINTER_MODES = [("none", "بدون طباعة (معاينة فقط)"), ("windows", "طابعة ويندوز (الأفضل للعربي)"), ("winraw", "ESC/POS خام عبر طابعة ويندوز"),
                 ("network", "طابعة شبكة (IP)"), ("serial", "منفذ COM / سيريال")]
TABS = [
 ("بيانات المحل", [("shop_name", "اسم المحل", "e"), ("shop_address", "العنوان", "e"), ("shop_phone", "تليفون المحل", "e"),
                   ("receipt_footer", "نص أسفل الفاتورة", "e"), ("allow_negative", "السماح بالبيع لو الرصيد صفر", "c"),
                   ("cashier_can_edit_price", "السماح للكاشير بتعديل السعر في الفاتورة", "c")]),
 ("الطباعة والدرج", [("printer_mode", "نوع الطابعة", PRINTER_MODES), ("printer_name", "اسم الطابعة (ويندوز)", "printer"), ("printer_ip", "IP الطابعة", "e"),
                     ("printer_port", "بورت الشبكة", "e"), ("printer_com", "منفذ COM (مثال COM3)", "e"), ("printer_baud", "Baud", "e"),
                     ("paper_chars", "عدد الحروف في السطر (42 لـ 80mm، 32 لـ 58mm)", "e"), ("escpos_codepage", "رقم Code Page للعربي (جرّب 22 أو 50 أو 28)", "e"),
                     ("receipt_font", "خط الطباعة (وضع ويندوز)", "e"), ("open_drawer", "فتح درج الفلوس بعد كل فاتورة", "c")]),
 ("الباركود", [("scanner_com", "سكانر سيريال COM (اتركه فاضي لو USB عادي)", "e"), ("scanner_baud", "Baud السكانر", "e")]),
 ("الإرسال (OTP)", [("smtp_user", "Gmail المرسل", "e"), ("smtp_pass", "App Password من جوجل (16 حرف)", "p"), ("smtp_host", "SMTP Host", "e"), ("smtp_port", "SMTP Port", "e"),
                    ("twilio_sid", "Twilio Account SID (SMS)", "e"), ("twilio_token", "Twilio Auth Token", "p"), ("twilio_from", "رقم Twilio المرسل", "e"),
                    ("wa_token", "WhatsApp Cloud API Token", "p"), ("wa_phone_id", "WhatsApp Phone Number ID", "e"),
                    ("wa_template", "اسم قالب OTP المعتمد", "e"), ("wa_lang", "لغة القالب (ar)", "e")]),
]
DEFAULTS = {"shop_name": "محلي", "allow_negative": "1", "smtp_host": "smtp.gmail.com", "smtp_port": "465", "printer_port": "9100", "printer_baud": "9600",
            "paper_chars": "42", "escpos_codepage": "22", "receipt_font": "Tahoma", "wa_lang": "ar", "receipt_footer": "شكراً لزيارتكم", "scanner_baud": "9600"}

class Settings(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent); self.app, self.db = app, app.db; self.w = {}
        header(self, "الإعدادات", [("نسخة احتياطية", self.backup), ("حفظ", self.save)])
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=6)
        for title, fields in reversed(TABS):
            fr = ttk.Frame(nb); nb.add(fr, text=title)
            for r, (key, label, kind) in enumerate(fields):
                ttk.Label(fr, text=label).grid(row=r, column=1, sticky="e", padx=10, pady=4); val = self.db.get(key, DEFAULTS.get(key, ""))
                if kind == "c": v = tk.BooleanVar(value=val == "1"); w = ttk.Checkbutton(fr, variable=v); w.var = v
                elif isinstance(kind, list):
                    w = ttk.Combobox(fr, state="readonly", values=[l for _, l in kind], width=34); w.set(dict(kind).get(val, kind[0][1])); w.map = kind
                elif kind == "printer":
                    w = ttk.Combobox(fr, values=printing.list_printers(), width=34); w.set(val)
                else: w = ttk.Entry(fr, width=36, justify="left", show="*" if kind == "p" else ""); w.insert(0, val)
                w.grid(row=r, column=0, sticky="w", padx=10, pady=4); self.w[key] = w
        nb.select(nb.tabs()[-1])
        tf = ttk.Frame(self); tf.pack(fill="x", padx=10, pady=6)
        for t, c in (("تجربة درج", self.t_drawer), ("تجربة طباعة", self.t_print), ("تجربة واتساب", lambda: self.t_otp("whatsapp")),
                     ("تجربة SMS", lambda: self.t_otp("sms")), ("تجربة إيميل", lambda: self.t_otp("email"))):
            ttk.Button(tf, text=t, command=c).pack(side="right", padx=3)
        ttk.Label(self, text="تجارب الإرسال بتبعت كود لحسابك الحالي. اضغط (حفظ) الأول.", foreground="#666").pack(anchor="e", padx=14)
    def save(self, quiet=False):
        for k, w in self.w.items():
            if hasattr(w, "var"): v = "1" if w.var.get() else "0"
            elif hasattr(w, "map"): v = next((a for a, l in w.map if l == w.get()), w.map[0][0])
            else: v = w.get().strip()
            self.db.set(k, v)
        self.app.start_scanner()
        if quiet is not True: messagebox.showinfo("الإعدادات", "تم الحفظ", parent=self)
    def t_print(self):
        self.save(True)
        s = dict(id=0, created=now(), subtotal=25, discount=0, total=25, paid=30)
        try:
            if not printing.print_receipt(self.db, printing.build_receipt(self.db, s, [dict(name="صنف تجريبي", qty=1, price=25, addons="", addons_total=0)], self.app.user["name"])):
                messagebox.showinfo("تجربة", "نوع الطابعة 'بدون طباعة'", parent=self)
        except Exception as e: messagebox.showerror("فشلت الطباعة", str(e), parent=self)
    def t_drawer(self):
        self.save(True)
        try: printing.open_drawer(self.db)
        except Exception as e: messagebox.showerror("خطأ", str(e), parent=self)
    def t_otp(self, ch):
        self.save(True)
        try: notify.send_otp(self.db, ch, self.app.user, "123456"); messagebox.showinfo("تم", "اتبعتت رسالة تجريبية (الكود 123456)", parent=self)
        except notify.NotifyError as e: messagebox.showerror("فشل الإرسال", str(e), parent=self)
    def backup(self):
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".db", initialfile="cashier-backup-%s.db" % now()[:10], filetypes=[("Database", "*.db")])
        if p: self.db.backup(p); messagebox.showinfo("نسخة احتياطية", "تم", parent=self)
