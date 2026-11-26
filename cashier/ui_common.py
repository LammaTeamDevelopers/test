# -*- coding: utf-8 -*-
import csv, tkinter as tk
from tkinter import ttk, messagebox, filedialog

_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")

def num(s, default=None):
    try:
        return float(str(s).translate(_AR).replace("٬", "").replace(",", ".").strip())
    except Exception:
        return default

def money(v):
    s = "%.2f" % float(v or 0)
    return s[:-3] if s.endswith(".00") else s

def setup_style(root):
    st = ttk.Style()
    try: st.theme_use("clam")
    except Exception: pass
    root.option_add("*Font", ("Tahoma", 11))
    st.configure("Treeview", rowheight=26, font=("Tahoma", 11))
    st.configure("Treeview.Heading", font=("Tahoma", 11, "bold"))
    st.configure("TButton", font=("Tahoma", 10, "bold"), padding=(8, 5))
    st.configure("Big.TButton", font=("Tahoma", 15, "bold"), padding=12)
    st.configure("Total.TLabel", font=("Tahoma", 28, "bold"), foreground="#0b6b2f")
    st.configure("Title.TLabel", font=("Tahoma", 16, "bold"))

def center(win, parent=None):
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    if parent is not None:
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
    else:
        x = (win.winfo_screenwidth() - w) // 2; y = (win.winfo_screenheight() - h) // 2
    win.geometry("+%d+%d" % (max(0, x), max(0, y)))

class Table(ttk.Frame):
    """جدول RTL: أول عمود بيظهر على اليمين. cols=[(key,title,width)]"""
    def __init__(self, parent, cols, height=14):
        super().__init__(parent)
        self.cols = cols
        keys = [c[0] for c in cols][::-1]
        self.tv = ttk.Treeview(self, columns=keys, show="headings", height=height, selectmode="browse")
        for k, t, w in cols:
            self.tv.heading(k, text=t); self.tv.column(k, width=w, anchor="center")
        sb = ttk.Scrollbar(self, command=self.tv.yview); self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="left", fill="y"); self.tv.pack(side="right", fill="both", expand=True)
        self.tv.tag_configure("low", background="#ffe3e3"); self.tv.tag_configure("void", foreground="#999999")
    def clear(self): self.tv.delete(*self.tv.get_children())
    def add(self, values, iid=None, tags=()):
        self.tv.insert("", "end", iid=None if iid is None else str(iid), values=list(values)[::-1], tags=tags)
    def sel(self):
        s = self.tv.selection(); return s[0] if s else None
    def rows(self):
        return [list(self.tv.item(i, "values"))[::-1] for i in self.tv.get_children()]
    def export(self, parent=None):
        p = filedialog.asksaveasfilename(parent=parent, defaultextension=".csv", filetypes=[("CSV (Excel)", "*.csv")])
        if not p: return
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow([c[1] for c in self.cols]); w.writerows(self.rows())
        messagebox.showinfo("تصدير", "تم حفظ الملف", parent=parent)

def ask_form(parent, title, fields, ok="حفظ"):
    """fields: (key,label,default,kind) kind: 'text'|'password'|list(of choices). يرجع dict أو None"""
    d = tk.Toplevel(parent); d.title(title); d.transient(parent.winfo_toplevel()); d.resizable(False, False)
    widgets = {}
    for i, (key, label, default, kind) in enumerate(fields):
        ttk.Label(d, text=label).grid(row=i, column=1, sticky="e", padx=10, pady=5)
        if isinstance(kind, list):
            w = ttk.Combobox(d, values=kind, state="readonly", justify="right", width=28)
            w.set(default if default in kind else kind[0])
        else:
            w = ttk.Entry(d, justify="right", width=30, show="*" if kind == "password" else "")
            w.insert(0, "" if default is None else str(default))
        w.grid(row=i, column=0, padx=10, pady=5); widgets[key] = w
    res = {}
    def ok_():
        res.update({k: w.get().strip() for k, w in widgets.items()}); d.destroy()
    bf = ttk.Frame(d); bf.grid(row=len(fields), column=0, columnspan=2, pady=10)
    ttk.Button(bf, text="إلغاء", command=d.destroy).pack(side="left", padx=6)
    ttk.Button(bf, text=ok, command=ok_).pack(side="left", padx=6)
    d.bind("<Return>", lambda e: ok_()); d.bind("<Escape>", lambda e: d.destroy())
    first = widgets[fields[0][0]]; center(d, parent.winfo_toplevel()); first.focus_set(); d.grab_set(); d.wait_window()
    return res or None
