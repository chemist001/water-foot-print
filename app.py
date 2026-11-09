"""
Kurumsal Su Ayak İzi Dashboard

Giriş yapan kullanıcılar tam yetki.
Kayıtsız «Demo olarak dene» → kısıtlı (rapor oluşturma kapalı).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pages_ui import firma, gecmis, home, kpi, login, raporlama, veri_girisi
from pages_ui.theme import apply_theme
from services import auth
from services.demo import banner, exit_demo, is_demo
from services.workspace import ensure_workspace_bound

st.set_page_config(
    page_title="Kurumsal Su Ayak İzi",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state() -> None:
    defaults = {
        "sonuc_mavi": None,
        "sonuc_yesil": None,
        "sonuc_gri": None,
        "sonuc_toplam": None,
        "gri_kritik_parametre": None,
        "gri_parametre_sonuclari": None,
        "hesaplandi": False,
        "kpi_hesaplandi": False,
        "gri_parametre_df": pd.DataFrame(
            [
                {"Parametre": "KOİ", "C_eff (mg/L)": 0.0, "C_max (mg/L)": 0.0, "C_nat (mg/L)": 0.0},
                {"Parametre": "BOİ", "C_eff (mg/L)": 0.0, "C_max (mg/L)": 0.0, "C_nat (mg/L)": 0.0},
            ]
        ),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    ensure_workspace_bound()


auth.bootstrap_auth()
init_session_state()
apply_theme()

if auth.require_cloud_login() and not auth.is_logged_in():
    login.render_login()
    st.stop()

banner()

with st.sidebar:
    st.markdown(
        """
        <div style="padding: 0.35rem 0 0.85rem 0;">
            <div style="font-size: 1.1rem; font-weight: 600; line-height: 1.3; color: #E8EEF3;">
                Su Ayak İzi<br/>Yönetim Sistemi
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_demo():
        st.markdown(
            '<div style="font-size:0.72rem;font-weight:700;letter-spacing:0.08em;'
            'color:#FBBF24;margin:0 0 0.55rem 0;">DEMO SÜRÜM</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div style="background:#152A3D;border:1px solid rgba(255,255,255,0.14);
                        border-radius:10px;padding:0.7rem 0.85rem;margin-bottom:0.65rem;">
              <div style="font-size:0.92rem;font-weight:600;line-height:1.35;color:#F2F6F9;">
                OTURUM: Demo
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif auth.is_logged_in():
        oturum_text = auth.session_display_label()
        st.markdown(
            f"""
            <div style="background:#152A3D;border:1px solid rgba(255,255,255,0.14);
                        border-radius:10px;padding:0.7rem 0.85rem;margin-bottom:0.65rem;">
              <div style="font-size:0.92rem;font-weight:600;line-height:1.35;color:#F2F6F9;
                          letter-spacing:0.02em;">{oturum_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if auth.is_logged_in() or is_demo():
        st.markdown(
            """
            <style>
            div[data-testid="stSidebar"] div[data-testid="stButton"] > button,
            div[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"],
            div[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"] {
                background: #2A455C !important;
                background-image: none !important;
                border: 1px solid rgba(255,255,255,0.26) !important;
                color: #FFFFFF !important;
                font-weight: 700 !important;
                border-radius: 8px !important;
                opacity: 1 !important;
                box-shadow: none !important;
            }
            div[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
                background: #35556F !important;
                border-color: rgba(255,255,255,0.4) !important;
                color: #FFFFFF !important;
                opacity: 1 !important;
            }
            div[data-testid="stSidebar"] div[data-testid="stButton"] > button p,
            div[data-testid="stSidebar"] div[data-testid="stButton"] > button span,
            div[data-testid="stSidebar"] div[data-testid="stButton"] > button div {
                color: #FFFFFF !important;
                opacity: 1 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        btn = "Giriş ekranına dön" if is_demo() else "Çıkış yap"
        if st.button(btn, use_container_width=True, type="primary"):
            auth.logout()
            exit_demo()
            st.rerun()

    st.divider()
    sayfa = st.radio(
        "Navigasyon",
        options=[
            "Ana Sayfa",
            "Firma Bilgileri",
            "Veri Girişi",
            "Performans (KPI)",
            "Raporlama",
            "Geçmiş Raporlar",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    if is_demo():
        st.caption("v1.1 · Demo (kayıtsız)")
    elif auth.is_logged_in():
        st.caption("v1.1 · Bulut")
    else:
        st.caption("v1.1 · Yerel")

if sayfa == "Ana Sayfa":
    home.render()
elif sayfa == "Firma Bilgileri":
    firma.render()
elif sayfa == "Veri Girişi":
    veri_girisi.render()
elif sayfa == "Performans (KPI)":
    kpi.render()
elif sayfa == "Raporlama":
    raporlama.render()
else:
    gecmis.render()
