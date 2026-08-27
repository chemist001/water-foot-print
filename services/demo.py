"""
Demo oturumu — kayıtsız misafir.

Kayıtlı kullanıcı (e-posta/şifre) → tam yetki.
Demo girişi → rapor PDF/Word/kaydet kapalı.
"""

from __future__ import annotations

import streamlit as st


def is_demo() -> bool:
    """Yalnızca demo misafir oturumu; giriş yapmış kullanıcı asla demo değildir."""
    if st.session_state.get("auth_user") is not None:
        return False
    return bool(st.session_state.get("demo_guest", False))


def enter_demo() -> None:
    """Kayıtsız demo oturumu başlatır."""
    from services import auth

    auth.logout()
    st.session_state.demo_guest = True
    st.session_state.pop("force_local_mode", None)
    st.session_state.pop("_workspace_key", None)
    st.session_state.pop("_app_state_loaded", None)


def exit_demo() -> None:
    st.session_state.demo_guest = False
    st.session_state.pop("force_local_mode", None)
    st.session_state.pop("_workspace_key", None)
    st.session_state.pop("_app_state_loaded", None)


def banner() -> None:
    if not is_demo():
        return
    st.markdown(
        """
        <div style="margin:0 0 1rem 0;padding:0.75rem 1rem;border-radius:10px;
                    background:rgba(180,83,9,0.12);border:1px solid rgba(180,83,9,0.35);
                    color:#7C2D12;font-size:0.9rem;line-height:1.45;">
          <strong>DEMO</strong> — Kayıtsız deneme. Rapor oluşturma (PDF / Word / kaydet) kapalıdır.
          Tam özellik için giriş yapın veya kayıt olun.
        </div>
        """,
        unsafe_allow_html=True,
    )


def reports_locked_message() -> None:
    st.info(
        "Demo girişinde rapor oluşturma (PDF / Word / kaydet) kapalıdır. "
        "Hesaplama ve ekran özetlerini kullanabilirsiniz. "
        "Tam erişim için e-posta ile giriş yapın."
    )
