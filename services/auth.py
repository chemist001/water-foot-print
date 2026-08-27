"""
Kimlik doğrulama ve çok kullanıcı oturumu (Supabase).

Bulut yapılandırılmamışsa yerel moda düşer — mevcut tek kullanıcılı akış bozulmaz.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

ROLE_FIRMA = "firma_kullanici"
ROLE_ADASO = "adaso_yonetici"


@dataclass
class AuthUser:
    id: str
    email: str
    full_name: str
    role: str
    firma_id: str | None
    firma_adi: str | None


def cloud_configured() -> bool:
    try:
        url = (st.secrets.get("SUPABASE_URL") or "").strip()
        key = (st.secrets.get("SUPABASE_KEY") or "").strip()
        return bool(url and key)
    except Exception:
        return False


@st.cache_resource
def get_supabase():
    if not cloud_configured():
        return None
    from supabase import create_client

    return create_client(
        st.secrets["SUPABASE_URL"].strip(),
        st.secrets["SUPABASE_KEY"].strip(),
    )


def _restore_session(client) -> None:
    sess = st.session_state.get("sb_session")
    if not sess or not client:
        return
    try:
        client.auth.set_session(sess["access_token"], sess["refresh_token"])
    except Exception:
        st.session_state.pop("sb_session", None)
        st.session_state.pop("auth_user", None)


def current_user() -> AuthUser | None:
    return st.session_state.get("auth_user")


def is_logged_in() -> bool:
    return current_user() is not None


def is_adaso() -> bool:
    u = current_user()
    return bool(u and u.role == ROLE_ADASO)


def is_local_mode() -> bool:
    """Yerel / demo misafir — bulut oturumu yok."""
    return not cloud_configured() or bool(st.session_state.get("demo_guest", False))


def require_cloud_login() -> bool:
    """True = giriş zorunlu. Demo misafir bu kontrolü atlar."""
    if not cloud_configured():
        return False
    if st.session_state.get("demo_guest"):
        return False
    return True


def _fetch_profile(client, user_id: str) -> dict[str, Any] | None:
    try:
        res = (
            client.table("profiles")
            .select("id,email,full_name,role,firma_id, firmalar(ad)")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
    except Exception:
        # firmalar join çalışmazsa düz select
        try:
            res = (
                client.table("profiles")
                .select("*")
                .eq("id", user_id)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception:
            return None
    return None


def _profile_to_user(profile: dict[str, Any], fallback_email: str = "") -> AuthUser:
    firma = profile.get("firmalar")
    firma_adi = None
    if isinstance(firma, dict):
        firma_adi = firma.get("ad")
    elif isinstance(firma, list) and firma:
        firma_adi = firma[0].get("ad")
    full_name = str(profile.get("full_name") or "").strip()
    meta = profile.get("_meta") or {}
    if not full_name and isinstance(meta, dict):
        full_name = str(meta.get("full_name") or "").strip()
    return AuthUser(
        id=str(profile.get("id") or ""),
        email=str(profile.get("email") or fallback_email or ""),
        full_name=full_name,
        role=str(profile.get("role") or ROLE_FIRMA),
        firma_id=str(profile["firma_id"]) if profile.get("firma_id") else None,
        firma_adi=firma_adi,
    )


def login(email: str, password: str) -> tuple[bool, str]:
    client = get_supabase()
    if not client:
        return False, "Bulut yapılandırması yok (SUPABASE_URL / SUPABASE_KEY)."
    try:
        resp = client.auth.sign_in_with_password(
            {"email": email.strip(), "password": password}
        )
        if not resp.user or not resp.session:
            return False, "Giriş başarısız."
        st.session_state.sb_session = {
            "access_token": resp.session.access_token,
            "refresh_token": resp.session.refresh_token,
        }
        profile = _fetch_profile(client, resp.user.id)
        if not profile:
            profile = {
                "id": resp.user.id,
                "email": resp.user.email,
                "full_name": "",
                "role": ROLE_FIRMA,
                "firma_id": None,
            }
        meta = getattr(resp.user, "user_metadata", None) or {}
        if isinstance(meta, dict):
            profile["_meta"] = meta
            if not profile.get("full_name") and meta.get("full_name"):
                profile["full_name"] = meta["full_name"]
        user = _profile_to_user(profile, resp.user.email or "")
        user = _ensure_firma_bound(client, user)
        st.session_state.auth_user = user
        st.session_state.demo_guest = False
        st.session_state.pop("force_local_mode", None)
        st.session_state.pop("_workspace_key", None)
        st.session_state.pop("_app_state_loaded", None)
        return True, "Giriş başarılı."

    except Exception as e:
        return False, f"Giriş hatası: {e}"


def register(
    email: str,
    password: str,
    *,
    full_name: str = "",
    firma_adi: str = "",
) -> tuple[bool, str]:
    client = get_supabase()
    if not client:
        return False, "Bulut yapılandırması yok."
    if len(password) < 6:
        return False, "Şifre en az 6 karakter olmalı."
    if not firma_adi.strip():
        return False, "Firma adı gerekli."
    try:
        resp = client.auth.sign_up(
            {
                "email": email.strip(),
                "password": password,
                "options": {
                    "data": {
                        "full_name": full_name.strip(),
                        "firma_adi": firma_adi.strip(),
                        "role": ROLE_FIRMA,
                    }
                },
            }
        )
        if resp.user is None:
            return False, "Kayıt tamamlanamadı."
        # E-posta onayı açıksa session gelmeyebilir
        if resp.session:
            st.session_state.sb_session = {
                "access_token": resp.session.access_token,
                "refresh_token": resp.session.refresh_token,
            }
            profile = _fetch_profile(client, resp.user.id) or {
                "id": resp.user.id,
                "email": resp.user.email,
                "full_name": full_name,
                "role": ROLE_FIRMA,
                "firma_id": None,
                "firmalar": {"ad": firma_adi},
            }
            user = _profile_to_user(profile, resp.user.email or email)
            user = _ensure_firma_bound(client, user, firma_adi=firma_adi)
            st.session_state.auth_user = user
            st.session_state.demo_guest = False
            st.session_state.pop("force_local_mode", None)
            st.session_state.pop("_workspace_key", None)
            st.session_state.pop("_app_state_loaded", None)
            return True, "Kayıt ve giriş başarılı."
        return True, "Kayıt alındı. E-posta onayı gerekiyorsa onaylayıp giriş yapın."
    except Exception as e:
        return False, f"Kayıt hatası: {e}"


def _ensure_firma_bound(
    client, user: AuthUser, *, firma_adi: str = ""
) -> AuthUser:
    """Trigger kaçırırsa firma oluşturup profile bağlar."""
    if user.firma_id or user.role == ROLE_ADASO:
        return user
    ad = (firma_adi or user.firma_adi or "").strip()
    if _is_placeholder_firma(ad, user.email):
        # Önce kayıt metadata / ad soyad; asla "Yeni Tesis" yazma
        ad = (user.full_name or "").strip() or (user.email or "Kullanıcı").split("@")[0]
    ad = ad.strip()
    if not ad:
        return user
    try:
        # Tercihen RPC (RLS güvenli)
        try:
            rpc = client.rpc("create_firma_for_me", {"p_ad": ad}).execute()
            firma_id = rpc.data
            if firma_id:
                return AuthUser(
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=user.role,
                    firma_id=str(firma_id),
                    firma_adi=ad,
                )
        except Exception:
            pass
        firma_res = client.table("firmalar").insert({"ad": ad}).execute()
        if not firma_res.data:
            return user
        firma_id = firma_res.data[0]["id"]
        client.table("profiles").update({"firma_id": firma_id}).eq(
            "id", user.id
        ).execute()
        return AuthUser(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            firma_id=str(firma_id),
            firma_adi=ad,
        )
    except Exception:
        return user


def logout() -> None:
    client = get_supabase()
    try:
        if client:
            client.auth.sign_out()
    except Exception:
        pass
    st.session_state.pop("sb_session", None)
    st.session_state.pop("auth_user", None)
    st.session_state.pop("_workspace_key", None)
    st.session_state.pop("_app_state_loaded", None)


def continue_local() -> None:
    """Geriye uyum: demo misafir oturumu."""
    from services.demo import enter_demo

    enter_demo()


def bootstrap_auth() -> None:
    """Uygulama açılışında oturumu yenile."""
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = None
    if "demo_guest" not in st.session_state:
        st.session_state.demo_guest = False
    if st.session_state.get("demo_guest"):
        return
    if not cloud_configured():
        return
    client = get_supabase()
    _restore_session(client)
    if st.session_state.get("auth_user"):
        return
    sess = st.session_state.get("sb_session")
    if not sess or not client:
        return
    try:
        user_resp = client.auth.get_user()
        if user_resp and user_resp.user:
            profile = _fetch_profile(client, user_resp.user.id)
            if profile:
                st.session_state.auth_user = _profile_to_user(
                    profile, user_resp.user.email or ""
                )
    except Exception:
        st.session_state.pop("sb_session", None)
        st.session_state.auth_user = None


def _format_display_name(full_name: str) -> str:
    """'erdem polat' → 'Erdem POLAT' (son kelime büyük)."""
    parts = [p for p in (full_name or "").strip().split() if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:1].upper() + parts[0][1:].lower()
    first = " ".join(p[:1].upper() + p[1:].lower() for p in parts[:-1])
    last = parts[-1].upper()
    return f"{first} {last}"


def _is_placeholder_firma(ad: str | None, email: str | None = None) -> bool:
    s = (ad or "").strip()
    if not s:
        return True
    low = s.lower()
    if low in ("yeni tesis", "adsız firma", "firma atanmadı"):
        return True
    if low.startswith("firma-"):
        return True
    if "@" in s:
        return True
    if email and low == email.strip().lower():
        return True
    return False


def session_display_name() -> str:
    """Kayıttaki firma adı veya kullanıcı adı (yer tutucu değil)."""
    u = current_user()
    if not u:
        return ""
    # 1) Oturumdaki firma profili (kayıt / form)
    try:
        profil = st.session_state.get("firma_profil") or {}
        pad = str(profil.get("firma_adi") or "").strip()
        if pad and not _is_placeholder_firma(pad, u.email):
            return pad
        yetkili = str(profil.get("yetkili") or "").strip()
        if yetkili:
            return _format_display_name(yetkili) or yetkili
    except Exception:
        pass
    # 2) Auth profilindeki firma
    if u.firma_adi and not _is_placeholder_firma(u.firma_adi, u.email):
        return u.firma_adi.strip()
    # 3) Kayıttaki ad soyad
    name = _format_display_name(u.full_name)
    if name:
        return name
    return (u.email or "Kullanıcı").strip()


def session_display_label() -> str:
    from services.demo import is_demo

    if is_demo():
        return "OTURUM: Demo"
    return f"OTURUM: {session_display_name()}"


def tenant_label() -> str:
    if current_user():
        return session_display_label()
    if is_local_mode():
        return "Yerel mod"
    return "Oturum yok"


def tenant_caption_lines() -> tuple[str, str | None]:
    """Geriye uyum: tek satır etiket."""
    return session_display_label(), None

