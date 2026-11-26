# -*- coding: utf-8 -*-
"""طبقة قاعدة البيانات (SQLite) - ملف واحد بيتحفظ في AppData."""
import os, sqlite3, sys
from datetime import datetime

def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "CashierPro")
    os.makedirs(d, exist_ok=True)
    return d

DB_PATH = os.path.join(data_dir(), "cashier.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE, phone TEXT UNIQUE,
  pass_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'cashier', active INTEGER NOT NULL DEFAULT 1,
  created TEXT);
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY, barcode TEXT UNIQUE, name TEXT NOT NULL, category TEXT DEFAULT '',
  price REAL NOT NULL DEFAULT 0, cost REAL NOT NULL DEFAULT 0, stock REAL NOT NULL DEFAULT 0,
  min_stock REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS addons(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, price REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS customers(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT DEFAULT '', balance REAL NOT NULL DEFAULT 0, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS shifts(
  id INTEGER PRIMARY KEY, user_id INTEGER, opened TEXT, closed TEXT,
  opening_cash REAL DEFAULT 0, closing_cash REAL, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS sales(
  id INTEGER PRIMARY KEY, user_id INTEGER, shift_id INTEGER, customer_id INTEGER,
  subtotal REAL, discount REAL DEFAULT 0, total REAL, paid REAL DEFAULT 0,
  method TEXT DEFAULT 'cash', created TEXT, voided INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sale_items(
  id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, name TEXT, qty REAL,
  price REAL, cost REAL DEFAULT 0, addons TEXT DEFAULT '', addons_total REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS expenses(
  id INTEGER PRIMARY KEY, title TEXT, amount REAL, user_id INTEGER, shift_id INTEGER, created TEXT, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS cust_payments(
  id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, user_id INTEGER, shift_id INTEGER, created TEXT, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS stock_log(
  id INTEGER PRIMARY KEY, product_id INTEGER, delta REAL, reason TEXT, user_id INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS otp(
  id INTEGER PRIMARY KEY, user_id INTEGER, code_hash TEXT, expires TEXT, attempts INTEGER DEFAULT 0, used INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_sales_created ON sales(created);
CREATE INDEX IF NOT EXISTS ix_exp_created ON expenses(created);
"""

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class DB:
    def __init__(self, path=DB_PATH):
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys=ON")
        self.con.executescript(SCHEMA)
        self.con.commit()

    def q(self, sql, args=()):
        return self.con.execute(sql, args).fetchall()

    def one(self, sql, args=()):
        return self.con.execute(sql, args).fetchone()

    def x(self, sql, args=()):
        cur = self.con.execute(sql, args)
        self.con.commit()
        return cur.lastrowid

    # settings
    def get(self, key, default=""):
        r = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return r["value"] if r else default

    def set(self, key, value):
        self.x("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, str(value)))

    def backup(self, dest):
        b = sqlite3.connect(dest)
        with b:
            self.con.backup(b)
        b.close()
