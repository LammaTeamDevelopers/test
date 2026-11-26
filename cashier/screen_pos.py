# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
import ops, printing
from ui_common import Table, ask_form, num, money, center

METHODS = {"نقدي": "cash", "بطاقة": "card", "آجل": "credit"}

class POS(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app, self.db = app, app.db
        self.cart = []; self.customers = []
        # ---------- يمين: الفاتورة ----------
        right = ttk.Frame(self); right.pack(side="right", fill="y", padx=8, pady=8)
        ttk.Label(right, text="الفاتورة الحالية", style="Title.TLabel").pack(anchor="e")
        self.ct = Table(right, [("name", "الصنف", 190), ("qty", "الكمية", 60), ("price", "السعر", 70), ("tot", "الإجمالي", 80)], height=11)
        self.ct.pack(fill="x", pady=4)
        br = ttk.Frame(right); br.pack(fill="x")
        for t, c in (("حذف", self.del_line), ("إضافات", self.line_addons), ("تعديل السعر", self.line_price), ("−", lambda: self.chg(-1)), ("+", lambda: self.chg(1))):
            ttk.Button(br, text=t, width=9 if len(t) > 1 else 3, command=c).pack(side="right", padx=2)
        fr = ttk.Frame(right); fr.pack(fill="x", pady=6)
        self.disc = ttk.Entry(fr, width=8, justify="center"); self.disc.grid(row=0, column=0, padx=3)
        self.dtype = ttk.Combobox(fr, values=["مبلغ", "%"], width=6, state="readonly"); self.dtype.set("مبلغ"); self.dtype.grid(row=0, column=1)
        ttk.Label(fr, text="الخصم").grid(row=0, column=2, padx=6)
        self.disc.bind("<KeyRelease>", lambda e: self.totals())
        self.dtype.bind("<<ComboboxSelected>>", lambda e: self.totals())
        self.method = ttk.Combobox(fr, values=list(METHODS), width=10, state="readonly", justify="right"); self.method.set("نقدي")
        self.method.grid(row=1, column=0, columnspan=2, pady=4, sticky="e"); ttk.Label(fr, text="طريقة الدفع").grid(row=1, column=2)
        self.paid = ttk.Entry(fr, width=10, justify="center"); self.paid.grid(row=2, column=0, columnspan=2, sticky="e")
        ttk.Label(fr, text="المدفوع").grid(row=2, column=2)
        self.cust = ttk.Combobox(fr, width=22, state="readonly", justify="right"); self.cust.grid(row=3, column=0, columnspan=2, pady=4)
        ttk.Label(fr, text="العميل").grid(row=3, column=2)
        ttk.Button(fr, text="+", width=3, command=self.new_customer).grid(row=3, column=3)
        self.lbl_total = ttk.Label(right, text="0", style="Total.TLabel"); self.lbl_total.pack(anchor="e")
        self.lbl_sub = ttk.Label(right, text=""); self.lbl_sub.pack(anchor="e")
        ttk.Button(right, text="دفع وطباعة  (F12)", style="Big.TButton", command=self.pay).pack(fill="x", pady=6)
        ttk.Button(right, text="إلغاء الفاتورة  (Esc)", command=self.reset).pack(fill="x")
        # ---------- شمال: الأصناف ----------
        left = ttk.Frame(self); left.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        top = ttk.Frame(left); top.pack(fill="x")
        self.bc = ttk.Entry(top, font=("Tahoma", 16), justify="center"); self.bc.pack(side="right", fill="x", expand=True)
        ttk.Label(top, text=" الباركود (F2) ").pack(side="right")
        self.bc.bind("<Return>", self.scan)
        sr = ttk.Frame(left); sr.pack(fill="x", pady=6)
        self.cat = ttk.Combobox(sr, state="readonly", width=16, justify="right"); self.cat.pack(side="left")
        self.cat.bind("<<ComboboxSelected>>", lambda e: self.load_products())
        self.q = ttk.Entry(sr, justify="right"); self.q.pack(side="right", fill="x", expand=True)
        ttk.Label(sr, text=" بحث بالاسم ").pack(side="right")
        self.q.bind("<KeyRelease>", lambda e: self.load_products())
        self.pt = Table(left, [("name", "الصنف", 260), ("price", "السعر", 80), ("stock", "المخزون", 80), ("cat", "التصنيف", 110)], height=16)
        self.pt.pack(fill="both", expand=True)
        self.pt.tv.bind("<Double-1>", lambda e: self.add_selected()); self.pt.tv.bind("<Return>", lambda e: self.add_selected())
        self.status = ttk.Label(left, text="", foreground="#a00"); self.status.pack(anchor="e")
        self.load_customers(); self.load_cats(); self.load_products(); self.bc.focus_set()
        top_ = self.winfo_toplevel()
        top_.bind("<F2>", lambda e: self.bc.focus_set()); top_.bind("<F12>", lambda e: self.pay()); top_.bind("<Escape>", lambda e: self.reset())

    # ----- بيانات -----
    def load_cats(self):
        cats = [r[0] for r in self.db.q("SELECT DISTINCT category FROM products WHERE active=1 AND category<>'' ORDER BY 1")]
        self.cat["values"] = ["الكل"] + cats; self.cat.set("الكل")
    def load_products(self):
        q, cat = self.q.get().strip(), self.cat.get()
        sql, a = "SELECT * FROM products WHERE active=1", []
        if q: sql += " AND (name LIKE ? OR barcode LIKE ?)"; a += ["%" + q + "%"] * 2
        if cat and cat != "الكل": sql += " AND category=?"; a.append(cat)
        self.pt.clear()
        for p in self.db.q(sql + " ORDER BY name LIMIT 500", a):
            self.pt.add((p["name"], money(p["price"]), money(p["stock"]), p["category"]), iid=p["id"],
                        tags=("low",) if p["stock"] <= p["min_stock"] and p["min_stock"] > 0 else ())
    def load_customers(self):
        self.customers = self.db.q("SELECT * FROM customers ORDER BY name")
        self.cust["values"] = ["(بدون عميل)"] + ["%s %s" % (c["name"], c["phone"]) for c in self.customers]; self.cust.current(0)
    def new_customer(self):
        r = ask_form(self, "عميل جديد", [("n", "الاسم", "", "text"), ("p", "الموبايل", "", "text")])
        if r and r["n"]:
            cid = ops.add_customer(self.db, r["n"], r["p"], 0, self.app.user["id"]); self.load_customers()
            self.cust.current(1 + [c["id"] for c in self.customers].index(cid))

    # ----- الفاتورة -----
    def scan(self, _=None):
        code = self.bc.get().strip(); self.bc.delete(0, "end"); self.status.config(text="")
        if not code: return
        qty = 1.0
        if "*" in code:
            a, code = code.split("*", 1); qty = num(a, 1.0) or 1.0
        p = self.db.one("SELECT * FROM products WHERE barcode=? AND active=1", (code,)) or \
            self.db.one("SELECT * FROM products WHERE name=? AND active=1", (code,))
        if not p:
            self.bell(); self.status.config(text="الباركود غير موجود: " + code); return
        self.add(p, qty)
    def bell(self):
        try: self.bell_()
        except Exception: pass
    def bell_(self): self.winfo_toplevel().bell()
    def add_selected(self):
        i = self.pt.sel()
        if i: self.add(self.db.one("SELECT * FROM products WHERE id=?", (i,)), 1.0)
    def add(self, p, qty):
        for k, l in enumerate(self.cart):
            if l["pid"] == p["id"] and not l["addons"] and l["price"] == p["price"]:
                l["qty"] += qty; self.refresh(select=k); return
        self.cart.append(dict(pid=p["id"], name=p["name"], qty=qty, price=p["price"], cost=p["cost"], addons=[]))
        self.refresh(select=len(self.cart) - 1)
    def line(self):
        i = self.ct.sel(); return (int(i), self.cart[int(i)]) if i is not None else (None, None)
    def chg(self, d):
        i, l = self.line()
        if l is None: return
        l["qty"] += d
        if l["qty"] <= 0: self.cart.pop(i)
        self.refresh(select=min(i, len(self.cart) - 1))
    def del_line(self):
        i, l = self.line()
        if l is not None: self.cart.pop(i); self.refresh()
    def line_price(self):
        if not self.app.is_admin and self.db.get("cashier_can_edit_price", "0") != "1":
            messagebox.showwarning("صلاحيات", "تغيير السعر للمدير فقط", parent=self); return
        i, l = self.line()
        if l is None: return
        r = ask_form(self, "تعديل السعر", [("p", "السعر الجديد", money(l["price"]), "text")])
        if r and num(r["p"]) is not None and num(r["p"]) >= 0: l["price"] = num(r["p"]); self.refresh(select=i)
    def line_addons(self):
        i, l = self.line()
        if l is None: return
        ad = self.db.q("SELECT * FROM addons WHERE active=1 ORDER BY name")
        if not ad: messagebox.showinfo("إضافات", "مفيش إضافات مسجلة. ضيفها من الشريط العلوي (إضافات).", parent=self); return
        d = tk.Toplevel(self); d.title("اختيار الإضافات"); d.transient(self.winfo_toplevel()); vs = []
        for a in ad:
            v = tk.BooleanVar(value=any(x[0] == a["name"] for x in l["addons"])); vs.append((a, v))
            ttk.Checkbutton(d, text="%s   (+%s)" % (a["name"], money(a["price"])), variable=v).pack(anchor="e", padx=20, pady=3)
        def ok():
            l["addons"] = [(a["name"], a["price"]) for a, v in vs if v.get()]; d.destroy(); self.refresh(select=i)
        ttk.Button(d, text="تم", command=ok).pack(pady=8); center(d, self.winfo_toplevel()); d.grab_set()
    def subtotal(self): return sum(ops.line_total(l) for l in self.cart)
    def discount(self):
        v = num(self.disc.get(), 0) or 0; s = self.subtotal()
        return min(s, s * v / 100.0 if self.dtype.get() == "%" else v)
    def total(self): return round(self.subtotal() - self.discount(), 2)
    def totals(self):
        self.lbl_total.config(text=money(self.total())); self.lbl_sub.config(text="الأصناف: %d   |   قبل الخصم: %s" % (len(self.cart), money(self.subtotal())))
    def refresh(self, select=None):
        self.ct.clear()
        for k, l in enumerate(self.cart):
            nm = l["name"] + (" (+%s)" % "، ".join(a[0] for a in l["addons"]) if l["addons"] else "")
            self.ct.add((nm, money(l["qty"]), money(l["price"] + sum(a[1] for a in l["addons"])), money(ops.line_total(l))), iid=k)
        if select is None and self.cart: select = len(self.cart) - 1
        if select is not None and self.cart: self.ct.tv.selection_set(str(select)); self.ct.tv.see(str(select))
        self.totals()
    def reset(self):
        self.cart = []; self.disc.delete(0, "end"); self.paid.delete(0, "end"); self.cust.current(0); self.method.set("نقدي")
        self.refresh(); self.bc.focus_set()

    def pay(self):
        if not self.cart: return
        if not self.app.ensure_shift(): return
        method = METHODS[self.method.get()]; total = self.total()
        t = num(self.paid.get())
        tendered = total if (t is None and method != "credit") else (t or 0.0)
        ci = self.cust.current(); cid = self.customers[ci - 1]["id"] if ci > 0 else None
        try:
            sale, items = ops.save_sale(self.db, self.app.user["id"], self.app.shift["id"], self.cart, self.discount(), method,
                                        tendered, cid, self.db.get("allow_negative", "1") == "1")
        except ValueError as e:
            messagebox.showwarning("تنبيه", str(e), parent=self); return
        rc = dict(sale); rc["paid"] = tendered if method == "cash" else sale["paid"]
        cname = self.customers[ci - 1]["name"] if ci > 0 else ""
        lines = printing.build_receipt(self.db, rc, items, self.app.user["name"], cname)
        try:
            printed = printing.print_receipt(self.db, lines)
        except Exception as e:
            printed = False; messagebox.showwarning("الطباعة", "تم حفظ الفاتورة لكن الطباعة فشلت:\n%s" % e, parent=self)
        change = tendered - total if method == "cash" else 0
        if not printed and self.db.get("printer_mode", "none") == "none":
            self.preview(lines)
        elif change > 0.005:
            messagebox.showinfo("الباقي للعميل", "الباقي: %s" % money(change), parent=self)
        self.reset(); self.load_products(); self.load_customers()
    def preview(self, lines):
        d = tk.Toplevel(self); d.title("معاينة الفاتورة"); t = tk.Text(d, width=44, height=26, font=("Courier New", 10)); t.pack(padx=8, pady=8)
        t.insert("1.0", printing.receipt_text(lines, 42)); t.config(state="disabled")
        ttk.Button(d, text="إغلاق", command=d.destroy).pack(pady=6); center(d, self.winfo_toplevel()); d.bind("<Return>", lambda e: d.destroy())

    def on_barcode(self, code):      # من سكانر السيريال
        self.bc.delete(0, "end"); self.bc.insert(0, code); self.scan()
