"""Kayıt aktivasyon kodu — e-posta doğrulama adımı."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

import streamlit as st

from services import auth
from services.mailer import mail_configured, send_activation_email

CODE_TTL_MINUTES = 15
CODE_LENGTH = 6


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def generate_code() -> str:
    n = secrets.randbelow(10**CODE_LENGTH)
    return f"{n:0{CODE_LENGTH}d}"


def pending() -> dict[str, Any] | None:
    data = st.session_state.get("pending_activation")
    return data if isinstance(data, dict) else None


def clear_pending() -> None:
    st.session_state.pop("pending_activation", None)


def _store_pending(
    *,
    email: str,
    password: str,
    full_name: str,
    firma_adi: str,
    code: str,
    mode: str,
    mailed: bool,
) -> None:
    st.session_state.pending_activation = {
        "mode": mode,
        "email": email,
        "password": password,
        "full_name": full_name.strip(),
        "firma_adi": firma_adi.strip(),
        "code_hash": _hash_code(code),
        "display_code": None if mailed else code,  # SMTP yoksa ekranda göster
        "mailed": mailed,
        "expires_at": (datetime.now() + timedelta(minutes=CODE_TTL_MINUTES)).isoformat(
            timespec="seconds"
        ),
        "attempts": 0,
    }


def start_registration(
    email: str,
    password: str,
    *,
    full_name: str = "",
    firma_adi: str = "",
) -> tuple[bool, str]:
    """
    SMTP/Resend varsa güzel hoş geldiniz maili + kod.
    Yoksa kod üretilir ve ekranda gösterilir (Supabase free mail güvenilir değil).
    """
    if not auth.cloud_configured():
        return False, "Bulut yapılandırması yok."

    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Geçerli bir e-posta girin."
    if len(password) < 6:
        return False, "Şifre en az 6 karakter olmalı."
    if not firma_adi.strip():
        return False, "Firma adı gerekli."

    code = generate_code()

    if mail_configured():
        ok, msg = send_activation_email(
            email,
            code=code,
            full_name=full_name,
            firma_adi=firma_adi,
        )
        if not ok:
            # Mail başarısız → ekran koduna düş
            _store_pending(
                email=email,
                password=password,
                full_name=full_name,
                firma_adi=firma_adi,
                code=code,
                mode="screen",
                mailed=False,
            )
            return True, ""
        _store_pending(
            email=email,
            password=password,
            full_name=full_name,
            firma_adi=firma_adi,
            code=code,
            mode="custom",
            mailed=True,
        )
        return True, ""

    _store_pending(
        email=email,
        password=password,
        full_name=full_name,
        firma_adi=firma_adi,
        code=code,
        mode="screen",
        mailed=False,
    )
    return True, ""


def resend_code() -> tuple[bool, str]:
    data = pending()
    if not data:
        return False, "Bekleyen kayıt yok."

    code = generate_code()
    if mail_configured():
        ok, _msg = send_activation_email(
            data["email"],
            code=code,
            full_name=data.get("full_name") or "",
            firma_adi=data.get("firma_adi") or "",
        )
        if ok:
            data["code_hash"] = _hash_code(code)
            data["display_code"] = None
            data["mailed"] = True
            data["mode"] = "custom"
            data["expires_at"] = (
                datetime.now() + timedelta(minutes=CODE_TTL_MINUTES)
            ).isoformat(timespec="seconds")
            data["attempts"] = 0
            st.session_state.pending_activation = data
            return True, ""

    data["code_hash"] = _hash_code(code)
    data["display_code"] = code
    data["mailed"] = False
    data["mode"] = "screen"
    data["expires_at"] = (
        datetime.now() + timedelta(minutes=CODE_TTL_MINUTES)
    ).isoformat(timespec="seconds")
    data["attempts"] = 0
    st.session_state.pending_activation = data
    return True, ""



def verify_and_register(code: str) -> tuple[bool, str]:
    data = pending()
    if not data:
        return False, "Bekleyen kayıt yok. Lütfen yeniden kayıt olun."

    code = (code or "").strip()
    if not code:
        return False, "Aktivasyon kodunu girin."

    try:
        exp = datetime.fromisoformat(data["expires_at"])
    except (KeyError, ValueError):
        clear_pending()
        return False, "Aktivasyon süresi geçersiz. Yeniden kayıt olun."

    if datetime.now() > exp:
        clear_pending()
        return False, "Aktivasyon kodunun süresi doldu. Yeniden kayıt olun."

    attempts = int(data.get("attempts") or 0) + 1
    data["attempts"] = attempts
    st.session_state.pending_activation = data
    if attempts > 8:
        clear_pending()
        return False, "Çok fazla hatalı deneme. Yeniden kayıt olun."

    if _hash_code(code) != data.get("code_hash"):
        return False, "Aktivasyon kodu hatalı."

    ok, msg = auth.register(
        data["email"],
        data["password"],
        full_name=data.get("full_name") or "",
        firma_adi=data.get("firma_adi") or "",
    )
    if not ok and (
        "already" in msg.lower()
        or "registered" in msg.lower()
        or "exists" in msg.lower()
    ):
        ok, msg = auth.login(data["email"], data["password"])
        if ok:
            clear_pending()
            return True, "Bu e-posta zaten kayıtlıydı — giriş yapıldı."
    if ok:
        clear_pending()
    return ok, msg
