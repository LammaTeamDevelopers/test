# -*- coding: utf-8 -*-
"""تسجيل الدخول / التسجيل / OTP - كلمات السر مشفرة PBKDF2."""
import hashlib, hmac, os, re, secrets
from datetime import datetime, timedelta
from db import now

ITER = 120000

def hash_pw(pw):
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, ITER)
    return "pbkdf2$%d$%s$%s" % (ITER, salt.hex(), h.hex())

def check_pw(pw, stored):
    try:
        _, it, salt, h = stored.split("$")
        c = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(c.hex(), h)
    except Exception:
        return False

def norm_phone(p):
    """يوحّد الرقم المصري: 01012345678 / +201012345678 -> +201012345678"""
    p = re.sub(r"[^\d+]", "", p or "")
    if p.startswith("00"): p = "+" + p[2:]
    if p.startswith("01") and len(p) == 11: p = "+2" + p
    elif p.startswith("1") and len(p) == 10: p = "+20" + p
    elif p.startswith("20") and not p.startswith("+"): p = "+" + p
    return p

def is_email(s): return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s or ""))
def is_phone(s): return bool(re.match(r"^\+?\d{10,15}$", norm_phone(s)))

def valid_password(pw):
    if len(pw or "") < 6: return "كلمة السر لازم تكون 6 أحرف أو أرقام على الأقل"
    return None

def ident_kind(ident):
    ident = (ident or "").strip()
    if is_email(ident): return "email", ident.lower()
    if is_phone(ident): return "phone", norm_phone(ident)
    return None, None

def register(db, name, ident, pw, role="cashier"):
    kind, val = ident_kind(ident)
    if not name.strip(): return None, "اكتب الاسم"
    if not kind: return None, "اكتب إيميل صحيح أو رقم موبايل صحيح"
    err = valid_password(pw)
    if err: return None, err
    if db.one("SELECT 1 FROM users WHERE %s=?" % kind, (val,)):
        return None, "الحساب ده مسجل قبل كده"
    uid = db.x("INSERT INTO users(name,%s,pass_hash,role,created) VALUES(?,?,?,?,?)" % kind,
               (name.strip(), val, hash_pw(pw), role, now()))
    return uid, None

def login(db, ident, pw):
    kind, val = ident_kind(ident)
    if not kind: return None, "اكتب الإيميل أو رقم الموبايل"
    u = db.one("SELECT * FROM users WHERE %s=?" % kind, (val,))
    if not u or not check_pw(pw, u["pass_hash"]): return None, "البيانات غير صحيحة"
    if not u["active"]: return None, "الحساب موقوف"
    return u, None

def find_user(db, ident):
    kind, val = ident_kind(ident)
    if not kind: return None
    return db.one("SELECT * FROM users WHERE %s=?" % kind, (val,))

# ---- OTP ----
def _otp_hash(code, uid): return hashlib.sha256(("%s:%s" % (uid, code)).encode()).hexdigest()

def create_otp(db, uid, minutes=10):
    code = "%06d" % secrets.randbelow(1000000)
    db.x("UPDATE otp SET used=1 WHERE user_id=?", (uid,))
    db.x("INSERT INTO otp(user_id,code_hash,expires) VALUES(?,?,?)",
         (uid, _otp_hash(code, uid), (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")))
    return code

def verify_otp(db, uid, code):
    r = db.one("SELECT * FROM otp WHERE user_id=? AND used=0 ORDER BY id DESC LIMIT 1", (uid,))
    if not r: return False, "اطلب كود جديد"
    if r["attempts"] >= 5:
        db.x("UPDATE otp SET used=1 WHERE id=?", (r["id"],)); return False, "محاولات كتير، اطلب كود جديد"
    if r["expires"] < now():
        db.x("UPDATE otp SET used=1 WHERE id=?", (r["id"],)); return False, "الكود انتهت صلاحيته"
    db.x("UPDATE otp SET attempts=attempts+1 WHERE id=?", (r["id"],))
    if hmac.compare_digest(r["code_hash"], _otp_hash(code.strip(), uid)):
        db.x("UPDATE otp SET used=1 WHERE id=?", (r["id"],)); return True, None
    return False, "الكود غلط"

def set_password(db, uid, pw):
    err = valid_password(pw)
    if err: return err
    db.x("UPDATE users SET pass_hash=? WHERE id=?", (hash_pw(pw), uid))
    return None
