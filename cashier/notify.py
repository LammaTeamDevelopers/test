# -*- coding: utf-8 -*-
"""إرسال كود OTP: Gmail (SMTP) / SMS و WhatsApp عبر Twilio أو WhatsApp Cloud API.
الإعدادات بتتحط من شاشة الإعدادات وبتتخزن في قاعدة البيانات."""
import base64, json, smtplib, ssl, urllib.parse, urllib.request, urllib.error
from email.mime.text import MIMEText
from email.header import Header

class NotifyError(Exception): pass

def _msg(code, shop):
    return "كود استعادة كلمة المرور لبرنامج %s هو: %s\nصالح لمدة 10 دقائق. لا تشاركه مع أي شخص." % (shop or "الكاشير", code)

def send_email(db, to, code):
    user, pw = db.get("smtp_user"), db.get("smtp_pass")
    if not user or not pw: raise NotifyError("إعدادات الجيميل غير مكتملة (الإعدادات > الإرسال)")
    host, port = db.get("smtp_host", "smtp.gmail.com"), int(db.get("smtp_port", "465") or 465)
    m = MIMEText(_msg(code, db.get("shop_name")), "plain", "utf-8")
    m["Subject"] = Header("كود استعادة كلمة المرور", "utf-8"); m["From"] = user; m["To"] = to
    try:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
            s.login(user, pw); s.sendmail(user, [to], m.as_string())
    except Exception as e:
        raise NotifyError("فشل إرسال الإيميل: %s" % e)

def _post(url, data=None, headers=None, as_json=False):
    body = json.dumps(data).encode() if as_json else urllib.parse.urlencode(data).encode()
    h = dict(headers or {}); h["Content-Type"] = "application/json" if as_json else "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, body, h)
    try:
        return urllib.request.urlopen(req, timeout=20).read()
    except urllib.error.HTTPError as e:
        raise NotifyError("رفض المزوّد الطلب (%s): %s" % (e.code, e.read()[:200].decode("utf-8", "ignore")))
    except Exception as e:
        raise NotifyError("تعذر الاتصال: %s" % e)

def send_sms(db, phone, code):
    sid, tok, frm = db.get("twilio_sid"), db.get("twilio_token"), db.get("twilio_from")
    if not (sid and tok and frm): raise NotifyError("إعدادات الـ SMS (Twilio) غير مكتملة")
    auth = base64.b64encode(("%s:%s" % (sid, tok)).encode()).decode()
    _post("https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json" % sid,
          {"To": phone, "From": frm, "Body": _msg(code, db.get("shop_name"))}, {"Authorization": "Basic " + auth})

def send_whatsapp(db, phone, code):
    tok, pid = db.get("wa_token"), db.get("wa_phone_id")
    if not (tok and pid): raise NotifyError("إعدادات WhatsApp Cloud API غير مكتملة")
    tpl = db.get("wa_template")  # قالب OTP معتمد من ميتا (مطلوب لبدء المحادثة)
    to = phone.lstrip("+")
    if tpl:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "template",
                   "template": {"name": tpl, "language": {"code": db.get("wa_lang", "ar")},
                                "components": [{"type": "body", "parameters": [{"type": "text", "text": code}]},
                                               {"type": "button", "sub_type": "url", "index": "0",
                                                "parameters": [{"type": "text", "text": code}]}]}}
    else:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text",
                   "text": {"body": _msg(code, db.get("shop_name"))}}
    _post("https://graph.facebook.com/v19.0/%s/messages" % pid, payload, {"Authorization": "Bearer " + tok}, as_json=True)

def send_otp(db, channel, user, code):
    if channel == "email":
        if not user["email"]: raise NotifyError("الحساب ده مالوش إيميل")
        send_email(db, user["email"], code)
    elif channel in ("sms", "whatsapp"):
        if not user["phone"]: raise NotifyError("الحساب ده مالوش رقم موبايل")
        (send_sms if channel == "sms" else send_whatsapp)(db, user["phone"], code)
    else:
        raise NotifyError("قناة غير معروفة")
