# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
import ops
from db import now
from ui_common import Table, ask_form, num, money, center

def header(parent, title, buttons, search=None):
    f = ttk.Frame(parent); f.pack(fill="x", padx=10, pady=8)
    ttk.Label(f, text=title, style="Title.TLabel").pack(side="right")
    for t, c in buttons: ttk.Button(f, text=t, command=c).pack(side="left", padx=3)
    e = None
    if search:
        e = ttk.Entry(f, width=24, justify="right"); e.pack(side="right", padx=14); e.bind("<KeyRelease>", lambda ev: search())
        ttk.Label(f, text="بحث:").pack(side="right")
    return e

# ------------------------------------------------------------ الأصناف
class Products(ttk.Frame):
    FIELDS = [("name", "اسم الصنف", "", "text"), ("barcode", "الباركود (فاضي = تلقائي)", "", "text"), ("category", "التصنيف", "", "text"),
              ("price", "سعر البيع", "0", "text"), ("cost", "سعر التكلفة", "0", "text"), ("stock", "الكمية الحالية", "0", "text"),
              ("min_stock", "حد الطلب (تنبيه النواقص)", "0", "text")]
    def __init__(self, parent, app):
        super().__init__(parent); self.app, self.db = app, app.db
        self.q = header(self, "الأصناف", [("تغيير الأسعار", self.bulk_price), ("حذف", self.delete), ("تعديل", self.edit), ("صنف جديد", self.new)], self.load)
        self.t = Table(self, [("bc", "الباركود", 130), ("name", "الاسم", 230), ("cat", "التصنيف", 110), ("price", "السعر", 80),
                              ("cost", "التكلفة", 80), ("stock", "المخزون", 80), ("min", "حد الطلب", 80)], height=20)
        self.t.pack(fill="both", expand=True, padx=10, pady=4); self.t.tv.bind("<Double-1>", lambda e: self.edit()); self.load()
    def load(self):
        q = self.q.get().strip(); self.t.clear()
        sql, a = "SELECT * FROM products WHERE active=1", []
        if q: sql += " AND (name LIKE ? OR barcode LIKE ? OR category LIKE ?)"; a = ["%" + q + "%"] * 3
        for p in self.db.q(sql + " ORDER BY name", a):
            self.t.add((p["barcode"], p["name"], p["category"], money(p["price"]), money(p["cost"]), money(p["stock"]), money(p["min_stock"])), iid=p["id"])
    def _save(self, r, pid=None):
        n = r["name"]; v = {k: num(r[k], None) for k in ("price", "cost", "stock", "min_stock")}
        if not n or any(x is None or (k != "stock" and x < 0) for k, x in v.items()):
            messagebox.showwarning("بيانات ناقصة", "راجع الاسم والأرقام", parent=self); return False
        bc = r["barcode"] or None
        try:
            if pid is None:
                pid = self.db.x("INSERT INTO products(barcode,name,category,price,cost,stock,min_stock) VALUES(?,?,?,?,?,?,?)",
                                (bc, n, r["category"], v["price"], v["cost"], v["stock"], v["min_stock"]))
                if not bc: self.db.x("UPDATE products SET barcode=? WHERE id=?", ("2%07d" % pid, pid))
            else:
                self.db.x("UPDATE products SET barcode=?,name=?,category=?,price=?,cost=?,stock=?,min_stock=? WHERE id=?",
                          (bc or "2%07d" % pid, n, r["category"], v["price"], v["cost"], v["stock"], v["min_stock"], pid))
        except Exception as e:
            messagebox.showwarning("خطأ", "الباركود مستخدم قبل كده" if "UNIQUE" in str(e) else str(e), parent=self); return False
        return True
    def new(self):
        r = ask_form(self, "صنف جديد", self.FIELDS)
        if r and self._save(r): self.load()
    def edit(self):
        i = self.t.sel()
        if not i: return
        p = self.db.one("SELECT * FROM products WHERE id=?", (i,))
        vals = [p["name"], p["barcode"], p["category"], money(p["price"]), money(p["cost"]), money(p["stock"]), money(p["min_stock"])]
        r = ask_form(self, "تعديل صنف", [(f[0], f[1], v, "text") for f, v in zip(self.FIELDS, vals)])
        if r and self._save(r, int(i)): self.load()
    def delete(self):
        i = self.t.sel()
        if i and messagebox.askyesno("حذف", "حذف الصنف؟ (الفواتير القديمة مش هتتأثر)", parent=self):
            self.db.x("UPDATE products SET active=0, barcode=NULL WHERE id=?", (i,)); self.load()
    def bulk_price(self):
        cats = ["كل الأصناف"] + [r[0] for r in self.db.q("SELECT DISTINCT category FROM products WHERE active=1 AND category<>''")]
        ops_ = ["زيادة بنسبة %", "تخفيض بنسبة %", "زيادة بمبلغ", "تخفيض بمبلغ", "تحديد سعر موحد"]
        r = ask_form(self, "تغيير الأسعار", [("scope", "على", "كل الأصناف", cats), ("op", "العملية", ops_[0], ops_), ("v", "القيمة", "10", "text"),
                                            ("rnd", "تقريب لأقرب (0 = بدون)", "0", "text")], ok="تطبيق")
        v = num(r["v"]) if r else None
        if not r or v is None or v < 0: return
        rnd = num(r["rnd"], 0) or 0
        rows = self.db.q("SELECT id,price FROM products WHERE active=1" + ("" if r["scope"] == "كل الأصناف" else " AND category=?"),
                         () if r["scope"] == "كل الأصناف" else (r["scope"],))
        if not messagebox.askyesno("تأكيد", "هيتم تغيير سعر %d صنف. متأكد؟" % len(rows), parent=self): return
        for p in rows:
            o, x = p["price"], r["op"]
            n = o * (1 + v / 100) if x.startswith("زيادة بنسبة") else o * (1 - v / 100) if x.startswith("تخفيض بنسبة") else \
                o + v if x == "زيادة بمبلغ" else o - v if x == "تخفيض بمبلغ" else v
            if rnd > 0: n = round(n / rnd) * rnd
            self.db.con.execute("UPDATE products SET price=? WHERE id=?", (round(max(n, 0), 2), p["id"]))
        self.db.con.commit(); self.load()

# ------------------------------------------------------------ الإضافات
class Addons(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent); self.app, self.db = app, app.db
        header(self, "الإضافات (مثل: سكر زيادة، جبنة، حجم كبير)", [("حذف", self.delete), ("تعديل", self.edit), ("إضافة جديدة", self.new)])
        self.t = Table(self, [("name", "اسم الإضافة", 300), ("price", "السعر", 100)], height=18)
        self.t.pack(fill="both", expand=True, padx=10, pady=4); self.t.tv.bind("<Double-1>", lambda e: self.edit()); self.load()
    def load(self):
        self.t.clear()
        for a in self.db.q("SELECT * FROM addons WHERE active=1 ORDER BY name"): self.t.add((a["name"], money(a["price"])), iid=a["id"])
    def new(self):
        r = ask_form(self, "إضافة جديدة", [("n", "الاسم", "", "text"), ("p", "السعر", "0", "text")])
        if r and r["n"] and num(r["p"]) is not None: self.db.x("INSERT INTO addons(name,price) VALUES(?,?)", (r["n"], num(r["p"]))); self.load()
    def edit(self):
        i = self.t.sel()
        if not i: return
        a = self.db.one("SELECT * FROM addons WHERE id=?", (i,))
        r = ask_form(self, "تعديل إضافة", [("n", "الاسم", a["name"], "text"), ("p", "السعر", money(a["price"]), "text")])
        if r and r["n"] and num(r["p"]) is not None: self.db.x("UPDATE addons SET name=?,price=? WHERE id=?", (r["n"], num(r["p"]), i)); self.load()
    def delete(self):
        i = self.t.sel()
        if i and messagebox.askyesno("حذف", "حذف الإضافة؟", parent=self): self.db.x("UPDATE addons SET active=0 WHERE id=?", (i,)); self.load()

# ------------------------------------------------------------ العملاء
class Customers(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent); self.app, self.db = app, app.db
        self.q = header(self, "العملاء", [("كشف حساب", self.statement), ("تسديد دفعة", self.pay), ("تعديل", self.edit), ("عميل جديد", self.new)], self.load)
        self.t = Table(self, [("name", "الاسم", 220), ("phone", "الموبايل", 130), ("bal", "المديونية (عليه)", 120), ("notes", "ملاحظات", 200)], height=18)
        self.t.pack(fill="both", expand=True, padx=10, pady=4); self.t.tv.bind("<Double-1>", lambda e: self.statement())
        self.tot = ttk.Label(self, text=""); self.tot.pack(anchor="e", padx=14, pady=4); self.load()
    def load(self):
        q = self.q.get().strip(); self.t.clear(); s = 0
        for c in self.db.q("SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name", ("%" + q + "%",) * 2):
            self.t.add((c["name"], c["phone"], money(c["balance"]), c["notes"]), iid=c["id"]); s += c["balance"]
        self.tot.config(text="إجمالي المديونيات: " + money(s))
    def new(self):
        r = ask_form(self, "عميل جديد", [("n", "الاسم", "", "text"), ("p", "الموبايل", "", "text"), ("o", "رصيد سابق (عليه)", "0", "text")])
        if r and r["n"]: ops.add_customer(self.db, r["n"], r["p"], num(r["o"], 0) or 0, self.app.user["id"]); self.load()
    def edit(self):
        i = self.t.sel()
        if not i: return
        c = self.db.one("SELECT * FROM customers WHERE id=?", (i,))
        r = ask_form(self, "تعديل عميل", [("n", "الاسم", c["name"], "text"), ("p", "الموبايل", c["phone"], "text"), ("t", "ملاحظات", c["notes"], "text")])
        if r and r["n"]: self.db.x("UPDATE customers SET name=?,phone=?,notes=? WHERE id=?", (r["n"], r["p"], r["t"], i)); self.load()
    def pay(self):
        i = self.t.sel()
        if not i or not self.app.ensure_shift(): return
        r = ask_form(self, "تسديد دفعة", [("a", "المبلغ المدفوع", "", "text"), ("n", "ملاحظة", "", "text")])
        a = num(r["a"]) if r else None
        if a and a > 0: ops.customer_payment(self.db, int(i), a, self.app.user["id"], self.app.shift["id"], r["n"]); self.load()
    def statement(self):
        i = self.t.sel()
        if not i: return
        c = self.db.one("SELECT * FROM customers WHERE id=?", (i,))
        d = tk.Toplevel(self); d.title("كشف حساب: " + c["name"]); d.geometry("700x460")
        t = Table(d, [("d", "التاريخ", 140), ("w", "البيان", 200), ("dr", "مدين (عليه)", 100), ("cr", "دائن (دفع)", 100), ("b", "الرصيد", 100)], height=16)
        t.pack(fill="both", expand=True, padx=8, pady=8)
        for r in ops.customer_statement(self.db, int(i)): t.add((r[0], r[1], money(r[2]), money(r[3]), money(r[4])))
        bf = ttk.Frame(d); bf.pack(pady=6); ttk.Button(bf, text="تصدير Excel/CSV", command=lambda: t.export(d)).pack(side="left", padx=4)
        ttk.Label(bf, text="الرصيد الحالي: " + money(c["balance"]), style="Title.TLabel").pack(side="left", padx=20)

# ------------------------------------------------------------ الجرد
class Inventory(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent); self.app, self.db = app, app.db; self.low = tk.BooleanVar(value=False)
        self.q = header(self, "الجرد والمخزون", [("حركة المخزون", self.log), ("إضافة كمية (شراء)", self.add_qty), ("تسجيل جرد فعلي", self.count)], self.load)
        ttk.Checkbutton(self, text="النواقص فقط", variable=self.low, command=self.load).pack(anchor="e", padx=14)
        self.t = Table(self, [("bc", "الباركود", 120), ("name", "الصنف", 230), ("stock", "الرصيد بالنظام", 100), ("min", "حد الطلب", 80),
                              ("cost", "التكلفة", 80), ("val", "قيمة المخزون", 100)], height=18)
        self.t.pack(fill="both", expand=True, padx=10, pady=4); self.t.tv.bind("<Double-1>", lambda e: self.count())
        bf = ttk.Frame(self); bf.pack(fill="x", padx=10, pady=4); self.tot = ttk.Label(bf, text=""); self.tot.pack(side="right")
        ttk.Button(bf, text="تصدير", command=lambda: self.t.export(self)).pack(side="left"); self.load()
    def load(self):
        q = self.q.get().strip(); self.t.clear(); tv = 0
        for p in self.db.q("SELECT * FROM products WHERE active=1 AND (name LIKE ? OR barcode LIKE ?) ORDER BY name", ("%" + q + "%",) * 2):
            low = p["stock"] <= p["min_stock"] and p["min_stock"] > 0
            if self.low.get() and not low: continue
            v = p["stock"] * p["cost"]; tv += v
            self.t.add((p["barcode"], p["name"], money(p["stock"]), money(p["min_stock"]), money(p["cost"]), money(v)), iid=p["id"], tags=("low",) if low else ())
        self.tot.config(text="إجمالي قيمة المخزون (بسعر التكلفة): " + money(tv))
    def count(self):
        i = self.t.sel()
        if not i: return
        p = self.db.one("SELECT * FROM products WHERE id=?", (i,))
        r = ask_form(self, "جرد: " + p["name"], [("c", "الكمية الفعلية (اللي عدّيتها)", money(p["stock"]), "text")], ok="تسجيل")
        c = num(r["c"]) if r else None
        if c is not None and c >= 0:
            ops.adjust_stock(self.db, p["id"], c - p["stock"], "جرد فعلي (النظام %s ← الفعلي %s)" % (money(p["stock"]), money(c)), self.app.user["id"]); self.load()
    def add_qty(self):
        i = self.t.sel()
        if not i: return
        p = self.db.one("SELECT * FROM products WHERE id=?", (i,))
        r = ask_form(self, "إضافة كمية: " + p["name"], [("q", "الكمية الواردة", "", "text"), ("c", "سعر التكلفة الجديد (اختياري)", "", "text")])
        q = num(r["q"]) if r else None
        if q and q > 0:
            ops.adjust_stock(self.db, p["id"], q, "وارد مشتريات", self.app.user["id"])
            if num(r["c"]) is not None: self.db.x("UPDATE products SET cost=? WHERE id=?", (num(r["c"]), p["id"]))
            self.load()
    def log(self):
        d = tk.Toplevel(self); d.title("حركة المخزون"); d.geometry("700x460")
        t = Table(d, [("d", "التاريخ", 140), ("p", "الصنف", 200), ("x", "التغيير", 70), ("r", "السبب", 250)], height=16); t.pack(fill="both", expand=True, padx=8, pady=8)
        for r in self.db.q("SELECT l.*, p.name FROM stock_log l LEFT JOIN products p ON p.id=l.product_id ORDER BY l.id DESC LIMIT 500"):
            t.add((r["created"], r["name"], money(r["delta"]), r["reason"]))

# ------------------------------------------------------------ المصروفات
class Expenses(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent); self.app, self.db = app, app.db
        header(self, "المصروفات", [("حذف", self.delete), ("تصدير", lambda: self.t.export(self)), ("مصروف جديد", self.new)])
        f = ttk.Frame(self); f.pack(fill="x", padx=10)
        today = now()[:10]
        self.d1 = ttk.Entry(f, width=12, justify="center"); self.d2 = ttk.Entry(f, width=12, justify="center")
        self.d2.pack(side="right"); ttk.Label(f, text=" إلى ").pack(side="right"); self.d1.pack(side="right"); ttk.Label(f, text="من (YYYY-MM-DD) ").pack(side="right")
        self.d1.insert(0, today[:8] + "01"); self.d2.insert(0, today)
        ttk.Button(f, text="عرض", command=self.load).pack(side="right", padx=8)
        self.t = Table(self, [("d", "التاريخ", 140), ("t", "البند", 220), ("a", "المبلغ", 90), ("u", "المستخدم", 110), ("n", "ملاحظات", 180)], height=16)
        self.t.pack(fill="both", expand=True, padx=10, pady=6); self.tot = ttk.Label(self, style="Title.TLabel"); self.tot.pack(anchor="e", padx=14); self.load()
    def load(self):
        self.t.clear(); s = 0
        for e in ops.expenses_list(self.db, self.d1.get(), self.d2.get()):
            self.t.add((e["created"], e["title"], money(e["amount"]), e["uname"], e["notes"]), iid=e["id"]); s += e["amount"]
        self.tot.config(text="الإجمالي: " + money(s))
    def new(self):
        if not self.app.ensure_shift(): return
        r = ask_form(self, "مصروف جديد", [("t", "البند (كهرباء، بضاعة، إيجار...)", "", "text"), ("a", "المبلغ", "", "text"), ("n", "ملاحظات", "", "text")])
        a = num(r["a"]) if r else None
        if r and r["t"] and a and a > 0: ops.add_expense(self.db, r["t"], a, self.app.user["id"], self.app.shift["id"], r["n"]); self.load()
    def delete(self):
        i = self.t.sel()
        if not self.app.is_admin: messagebox.showwarning("صلاحيات", "الحذف للمدير فقط", parent=self); return
        if i and messagebox.askyesno("حذف", "حذف المصروف؟", parent=self): self.db.x("DELETE FROM expenses WHERE id=?", (i,)); self.load()
