# -*- coding: utf-8 -*-
"""منطق العمل: الفواتير، الشفتات، المخزون، التقارير (من غير واجهة علشان يبقى قابل للاختبار)."""
from db import now

EPS = 0.005

def current_shift(db, uid):
    return db.one("SELECT * FROM shifts WHERE user_id=? AND closed IS NULL ORDER BY id DESC LIMIT 1", (uid,))

def open_shift(db, uid, cash):
    return db.x("INSERT INTO shifts(user_id,opened,opening_cash) VALUES(?,?,?)", (uid, now(), cash))

def shift_summary(db, sid):
    sh = db.one("SELECT * FROM shifts WHERE id=?", (sid,))
    r = db.one("""SELECT COUNT(*) n, COALESCE(SUM(total),0) total,
        COALESCE(SUM(CASE WHEN method IN ('cash','credit') THEN paid END),0) cash,
        COALESCE(SUM(CASE WHEN method='card' THEN paid END),0) card,
        COALESCE(SUM(total-paid),0) credit FROM sales WHERE shift_id=? AND voided=0""", (sid,))
    exp = db.one("SELECT COALESCE(SUM(amount),0) v FROM expenses WHERE shift_id=?", (sid,))["v"]
    cp = db.one("SELECT COALESCE(SUM(amount),0) v FROM cust_payments WHERE shift_id=? AND amount>0", (sid,))["v"]
    d = dict(r); d.update(opening=sh["opening_cash"], expenses=exp, cust_payments=cp,
                          expected=sh["opening_cash"] + r["cash"] + cp - exp)
    return d

def close_shift(db, sid, counted, note=""):
    db.x("UPDATE shifts SET closed=?, closing_cash=?, note=? WHERE id=?", (now(), counted, note, sid))

def line_total(it):
    return (it["price"] + sum(a[1] for a in it["addons"])) * it["qty"]

def save_sale(db, user_id, shift_id, cart, discount, method, tendered, customer_id=None, allow_negative=True):
    """cart: [{pid,name,qty,price,cost,addons:[(name,price)]}] -> (sale_dict, items)"""
    if not cart: raise ValueError("الفاتورة فاضية")
    subtotal = sum(line_total(i) for i in cart)
    discount = max(0.0, min(discount, subtotal))
    total = round(subtotal - discount, 2)
    paid = total if method == "card" else min(max(tendered, 0.0), total)
    debt = round(total - paid, 2)
    if debt > EPS and not customer_id: raise ValueError("الفاتورة فيها مبلغ آجل - اختار العميل")
    if not allow_negative:
        for i in cart:
            if i["pid"]:
                st = db.one("SELECT stock,name FROM products WHERE id=?", (i["pid"],))
                if st and st["stock"] < i["qty"]: raise ValueError("الرصيد غير كافي: %s" % st["name"])
    c = db.con
    try:
        cur = c.execute("INSERT INTO sales(user_id,shift_id,customer_id,subtotal,discount,total,paid,method,created) VALUES(?,?,?,?,?,?,?,?,?)",
                        (user_id, shift_id, customer_id, subtotal, discount, total, paid, method, now()))
        sid = cur.lastrowid
        items = []
        for i in cart:
            ad = "، ".join(a[0] for a in i["addons"]); at = sum(a[1] for a in i["addons"])
            c.execute("INSERT INTO sale_items(sale_id,product_id,name,qty,price,cost,addons,addons_total) VALUES(?,?,?,?,?,?,?,?)",
                      (sid, i["pid"], i["name"], i["qty"], i["price"], i.get("cost", 0), ad, at))
            items.append(dict(name=i["name"], qty=i["qty"], price=i["price"], addons=ad, addons_total=at))
            if i["pid"]:
                c.execute("UPDATE products SET stock=stock-? WHERE id=?", (i["qty"], i["pid"]))
                c.execute("INSERT INTO stock_log(product_id,delta,reason,user_id,created) VALUES(?,?,?,?,?)",
                          (i["pid"], -i["qty"], "بيع فاتورة %d" % sid, user_id, now()))
        if debt > EPS:
            c.execute("UPDATE customers SET balance=balance+? WHERE id=?", (debt, customer_id))
        c.commit()
    except Exception:
        c.rollback(); raise
    sale = dict(db.one("SELECT * FROM sales WHERE id=?", (sid,)))
    return sale, items

def void_sale(db, sale_id, uid):
    s = db.one("SELECT * FROM sales WHERE id=?", (sale_id,))
    if not s or s["voided"]: raise ValueError("الفاتورة ملغية بالفعل")
    c = db.con
    try:
        c.execute("UPDATE sales SET voided=1 WHERE id=?", (sale_id,))
        for it in c.execute("SELECT * FROM sale_items WHERE sale_id=?", (sale_id,)).fetchall():
            if it["product_id"]:
                c.execute("UPDATE products SET stock=stock+? WHERE id=?", (it["qty"], it["product_id"]))
                c.execute("INSERT INTO stock_log(product_id,delta,reason,user_id,created) VALUES(?,?,?,?,?)",
                          (it["product_id"], it["qty"], "إلغاء فاتورة %d" % sale_id, uid, now()))
        debt = s["total"] - s["paid"]
        if debt > EPS and s["customer_id"]:
            c.execute("UPDATE customers SET balance=balance-? WHERE id=?", (debt, s["customer_id"]))
        c.commit()
    except Exception:
        c.rollback(); raise

def adjust_stock(db, pid, delta, reason, uid):
    db.con.execute("UPDATE products SET stock=stock+? WHERE id=?", (delta, pid))
    db.con.execute("INSERT INTO stock_log(product_id,delta,reason,user_id,created) VALUES(?,?,?,?,?)", (pid, delta, reason, uid, now()))
    db.con.commit()

def add_customer(db, name, phone="", opening=0.0, uid=None):
    cid = db.x("INSERT INTO customers(name,phone,balance) VALUES(?,?,?)", (name, phone, opening))
    if abs(opening) > EPS:
        db.x("INSERT INTO cust_payments(customer_id,amount,user_id,created,note) VALUES(?,?,?,?,?)",
             (cid, -opening, uid, now(), "رصيد افتتاحي"))
    return cid

def customer_payment(db, cid, amount, uid, shift_id, note=""):
    db.x("INSERT INTO cust_payments(customer_id,amount,user_id,shift_id,created,note) VALUES(?,?,?,?,?,?)",
         (cid, amount, uid, shift_id, now(), note))
    db.x("UPDATE customers SET balance=balance-? WHERE id=?", (amount, cid))

def add_expense(db, title, amount, uid, shift_id, notes=""):
    return db.x("INSERT INTO expenses(title,amount,user_id,shift_id,created,notes) VALUES(?,?,?,?,?,?)",
                (title, amount, uid, shift_id, now(), notes))

# ---------- تقارير ----------
def _rng(d1, d2): return d1 + " 00:00:00", d2 + " 23:59:59"

def summary(db, d1, d2, uid=None):
    a, b = _rng(d1, d2); uf = " AND s.user_id=%d" % uid if uid else ""
    s = db.one("""SELECT COUNT(*) n, COALESCE(SUM(total),0) total, COALESCE(SUM(discount),0) disc,
        COALESCE(SUM(CASE WHEN method IN ('cash','credit') THEN paid END),0) cash, COALESCE(SUM(CASE WHEN method='card' THEN paid END),0) card,
        COALESCE(SUM(total-paid),0) credit FROM sales s WHERE created BETWEEN ? AND ? AND voided=0""" + uf, (a, b))
    cost = db.one("""SELECT COALESCE(SUM(i.cost*i.qty),0) v FROM sale_items i JOIN sales s ON s.id=i.sale_id
        WHERE s.created BETWEEN ? AND ? AND s.voided=0""" + uf, (a, b))["v"]
    ef = " AND user_id=%d" % uid if uid else ""
    exp = db.one("SELECT COALESCE(SUM(amount),0) v FROM expenses WHERE created BETWEEN ? AND ?" + ef, (a, b))["v"]
    d = dict(s); d.update(cost=cost, expenses=exp, profit=s["total"] - cost - exp)
    return d

def sales_list(db, d1, d2, uid=None):
    a, b = _rng(d1, d2); uf = " AND s.user_id=%d" % uid if uid else ""
    return db.q("""SELECT s.*, u.name uname, c.name cname FROM sales s LEFT JOIN users u ON u.id=s.user_id
        LEFT JOIN customers c ON c.id=s.customer_id WHERE s.created BETWEEN ? AND ?""" + uf + " ORDER BY s.id DESC", (a, b))

def top_products(db, d1, d2):
    a, b = _rng(d1, d2)
    return db.q("""SELECT i.name, SUM(i.qty) qty, SUM((i.price+i.addons_total)*i.qty) sales,
        SUM((i.price+i.addons_total-i.cost)*i.qty) profit FROM sale_items i JOIN sales s ON s.id=i.sale_id
        WHERE s.created BETWEEN ? AND ? AND s.voided=0 GROUP BY i.name ORDER BY sales DESC""", (a, b))

def expenses_list(db, d1, d2):
    a, b = _rng(d1, d2)
    return db.q("SELECT e.*, u.name uname FROM expenses e LEFT JOIN users u ON u.id=e.user_id WHERE e.created BETWEEN ? AND ? ORDER BY e.id DESC", (a, b))

def customer_statement(db, cid):
    rows = []
    for s in db.q("SELECT id,created,total,paid FROM sales WHERE customer_id=? AND voided=0", (cid,)):
        rows.append((s["created"], "فاتورة %d" % s["id"], s["total"] - s["paid"], 0.0))
    for p in db.q("SELECT created,amount,note FROM cust_payments WHERE customer_id=?", (cid,)):
        if p["amount"] >= 0: rows.append((p["created"], "دفعة" + (" - " + p["note"] if p["note"] else ""), 0.0, p["amount"]))
        else: rows.append((p["created"], p["note"] or "رصيد سابق", -p["amount"], 0.0))
    rows.sort(key=lambda r: r[0]); bal = 0.0; out = []
    for d, what, debit, credit in rows:
        bal += debit - credit; out.append((d, what, debit, credit, bal))
    return out
