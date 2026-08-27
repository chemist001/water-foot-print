"""Supabase Storage — fatura / kanıt dosyaları (firma klasörü)."""

from __future__ import annotations

from typing import Any

from services import auth

BUCKET = "kanit"


def _client_with_session():
    client = auth.get_supabase()
    if not client:
        return None
    import streamlit as st

    sess = st.session_state.get("sb_session")
    if sess:
        try:
            client.auth.set_session(sess["access_token"], sess["refresh_token"])
        except Exception:
            pass
    return client


def upload_kanit_bytes(
    *,
    yil: str | int,
    file_name: str,
    data: bytes,
    content_type: str = "application/pdf",
) -> str | None:
    """
    kanit/{firma_id}/{yil}/{file_name} yoluna yükler.
    Başarılıysa storage path; yoksa None.
    """
    user = auth.current_user()
    if not user or not user.firma_id or auth.is_local_mode():
        return None
    client = _client_with_session()
    if not client:
        return None
    path = f"{user.firma_id}/{yil}/{file_name}"
    try:
        client.storage.from_(BUCKET).upload(
            path,
            data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return path
    except Exception:
        return None
