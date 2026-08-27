"""Hoş geldiniz / aktivasyon e-postası (SMTP veya Resend)."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import streamlit as st


def mail_configured() -> bool:
    try:
        if (st.secrets.get("RESEND_API_KEY") or "").strip():
            return True
        host = (st.secrets.get("SMTP_HOST") or "").strip()
        user = (st.secrets.get("SMTP_USER") or "").strip()
        password = (st.secrets.get("SMTP_PASSWORD") or "").strip()
        return bool(host and user and password)
    except Exception:
        return False


def _from_address() -> str:
    try:
        return (
            (st.secrets.get("MAIL_FROM") or "").strip()
            or (st.secrets.get("SMTP_FROM") or "").strip()
            or (st.secrets.get("SMTP_USER") or "").strip()
            or "noreply@adaso.org.tr"
        )
    except Exception:
        return "noreply@adaso.org.tr"


def _welcome_html(
    *,
    full_name: str,
    firma_adi: str,
    code: str,
) -> str:
    ad = (full_name or "").strip() or "Değerli kullanıcı"
    firma = (firma_adi or "").strip() or "tesisiniz"
    return f"""
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#E8EEF3;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#E8EEF3;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0"
             style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;
                    border:1px solid #D5DEE7;box-shadow:0 8px 28px rgba(11,31,51,0.06);">
        <tr>
          <td style="background:linear-gradient(135deg,#0B1F33,#0D7377);padding:28px 32px;color:#fff;">
            <div style="font-size:12px;letter-spacing:0.14em;text-transform:uppercase;opacity:0.75;font-weight:600;">
              Adana Sanayi Odası
            </div>
            <div style="font-size:22px;font-weight:600;margin-top:8px;line-height:1.3;">
              Kurumsal Su Ayak İzi
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px 8px 32px;color:#1C2B36;">
            <p style="margin:0 0 12px 0;font-size:17px;font-weight:600;">Hoş geldiniz, {ad}</p>
            <p style="margin:0 0 14px 0;font-size:14.5px;line-height:1.65;color:#3D4F5F;">
              <strong>{firma}</strong> için Kurumsal Su Ayak İzi Yönetim Sistemi hesabınızı
              oluşturma talebiniz alındı. Güvenliğiniz için e-posta adresinizi
              aşağıdaki aktivasyon kodu ile doğrulamanız gerekmektedir.
            </p>
            <p style="margin:0 0 8px 0;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;
                      color:#5A6B7A;font-weight:600;">Aktivasyon kodu</p>
            <div style="display:inline-block;background:#F1F7F8;border:1px solid #C5DCE0;
                        border-radius:12px;padding:14px 28px;font-size:28px;letter-spacing:0.35em;
                        font-weight:700;color:#0B1F33;font-family:Consolas,Monaco,monospace;">
              {code}
            </div>
            <p style="margin:18px 0 0 0;font-size:13.5px;line-height:1.6;color:#5A6B7A;">
              Kod <strong>15 dakika</strong> geçerlidir. Bu talebi siz oluşturmadıysanız
              bu e-postayı yok sayabilirsiniz.
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 32px 28px 32px;">
            <div style="border-top:1px solid #E4EAF0;padding-top:16px;font-size:12.5px;
                        color:#7A8B99;line-height:1.55;">
              Bu sistem Adana Sanayi Odası bünyesinde sanayi tesislerinin su ayak izi
              raporlaması için kullanılmaktadır.<br/>
              Saygılarımızla,<br/>
              <strong style="color:#3D4F5F;">ADASO · Kurumsal Su Ayak İzi Ekibi</strong>
            </div>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _welcome_text(*, full_name: str, firma_adi: str, code: str) -> str:
    ad = (full_name or "").strip() or "Değerli kullanıcı"
    firma = (firma_adi or "").strip() or "tesisiniz"
    return (
        f"Hoş geldiniz, {ad}\n\n"
        f"{firma} için Kurumsal Su Ayak İzi hesabı oluşturma talebiniz alındı.\n\n"
        f"Aktivasyon kodunuz: {code}\n"
        f"Kod 15 dakika geçerlidir.\n\n"
        f"ADASO · Kurumsal Su Ayak İzi Ekibi"
    )


def send_activation_email(
    to_email: str,
    *,
    code: str,
    full_name: str = "",
    firma_adi: str = "",
) -> tuple[bool, str]:
    if not mail_configured():
        return (
            False,
            "E-posta ayarı yok. secrets.toml içine SMTP_* veya RESEND_API_KEY ekleyin.",
        )
    subject = "Hoş geldiniz — Su Ayak İzi aktivasyon kodunuz"
    html = _welcome_html(full_name=full_name, firma_adi=firma_adi, code=code)
    text = _welcome_text(full_name=full_name, firma_adi=firma_adi, code=code)
    try:
        if (st.secrets.get("RESEND_API_KEY") or "").strip():
            return _send_resend(to_email, subject, html, text)
        return _send_smtp(to_email, subject, html, text)
    except Exception as e:
        return False, f"E-posta gönderilemedi: {e}"


def _send_resend(
    to_email: str, subject: str, html: str, text: str
) -> tuple[bool, str]:
    import urllib.request
    import json

    api_key = st.secrets["RESEND_API_KEY"].strip()
    payload = {
        "from": _from_address(),
        "to": [to_email.strip()],
        "subject": subject,
        "html": html,
        "text": text,
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status >= 400:
            return False, f"Resend hatası: HTTP {resp.status}"
    return True, "Aktivasyon e-postası gönderildi."


def _send_smtp(
    to_email: str, subject: str, html: str, text: str
) -> tuple[bool, str]:
    host = st.secrets["SMTP_HOST"].strip()
    port = int(st.secrets.get("SMTP_PORT") or 587)
    user = st.secrets["SMTP_USER"].strip()
    password = st.secrets["SMTP_PASSWORD"].strip()
    use_tls = str(st.secrets.get("SMTP_TLS", "true")).lower() in ("1", "true", "yes")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _from_address()
    msg["To"] = to_email.strip()
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls()
        server.login(user, password)
        server.sendmail(msg["From"], [to_email.strip()], msg.as_string())
    return True, "Aktivasyon e-postası gönderildi."
