"""Oturum / firma değişince çalışma alanını sıfırla veya doğru tenant state yükle."""

from __future__ import annotations

from copy import deepcopy

import pandas as pd
import streamlit as st

from services import auth
from services.app_state import load_app_state
from services.firma_state import _DEFAULTS, ensure_firma_profil, save_firma_profil
from services.tenant_paths import tenant_storage_key

# Widget / hesaplama anahtarları — tenant değişince temizlenir
_CLEAR_KEYS = (
    "firma_profil",
    "sorumlu_kisiler_tablosu",
    "hedef_tablosu",
    "sistem_siniri_tablosu",
    "veri_kalitesi_aciklama",
    "calc_snapshot",
    "kpi_snapshot",
    "sonuc_mavi",
    "sonuc_yesil",
    "sonuc_gri",
    "sonuc_toplam",
    "gri_kritik_parametre",
    "gri_parametre_sonuclari",
    "hesaplandi",
    "kpi_hesaplandi",
    "gri_parametre_df",
    "_gri_parametre_edited",
    "mavi_sebeke",
    "mavi_yeralti",
    "mavi_kaynak",
    "yesil_yagmur",
    "gri_debi",
    "mavi_kanit_ozet",
    "kanit_m3",
    "kanit_fatura_no",
    "kanit_donem",
    "_kanit_batch_sig",
    "_kanit_batch_results",
    "_kanit_batch_rows",
    "_kanit_batch_msg",
    "_apply_fatura_to_mavi",
    "_fatura_to_mavi_ok",
    "_logo_upload_sig",
    "_pdf_bytes",
    "_pdf_name",
    "_docx_bytes",
    "_docx_name",
    "kpi_uretim",
    "kpi_uretim_birimi",
    "kpi_calisma_gunu",
    "kpi_personel",
    "kpi_evsel_su",
    "kpi_sulama",
    "kpi_yangin",
    "kpi_arac",
    "kpi_geri",
    "kpi_evsel_atik",
    "kpi_net_proses",
    "kpi_spesifik_su",
    "kpi_spesifik_atiksu",
    "kpi_evsel_su_gosterge",
    "kpi_evsel_atiksu_gosterge",
)

_PREFIXES = (
    "kanit_",
    "sil_onay_",
    "firma_logo",
)


def _default_gri_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Parametre": "KOİ", "C_eff (mg/L)": 0.0, "C_max (mg/L)": 0.0, "C_nat (mg/L)": 0.0},
            {"Parametre": "BOİ", "C_eff (mg/L)": 0.0, "C_max (mg/L)": 0.0, "C_nat (mg/L)": 0.0},
        ]
    )


def clear_workspace_session() -> None:
    for key in _CLEAR_KEYS:
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if any(str(key).startswith(p) for p in _PREFIXES):
            st.session_state.pop(key, None)

    st.session_state.firma_profil = deepcopy(_DEFAULTS)
    st.session_state.gri_parametre_df = _default_gri_df()
    st.session_state.hesaplandi = False
    st.session_state.kpi_hesaplandi = False
    st.session_state.sonuc_mavi = None
    st.session_state.sonuc_yesil = None
    st.session_state.sonuc_gri = None
    st.session_state.sonuc_toplam = None
    st.session_state.pop("_app_state_loaded", None)


def seed_from_auth_if_empty() -> None:
    """Yeni bulut firmasında profil boşsa kayıt bilgisinden doldur."""
    user = auth.current_user()
    if not user or auth.is_local_mode():
        return
    profil = ensure_firma_profil()
    updates = {}
    raw_firma = (user.firma_adi or "").strip()
    if not str(profil.get("firma_adi") or "").strip():
        if raw_firma and not auth._is_placeholder_firma(raw_firma, user.email):
            updates["firma_adi"] = raw_firma
        elif user.full_name:
            # Firma adı yoksa en azından yetkili dolsun; firma alanını e-posta ile doldurma
            pass
    if not str(profil.get("email") or "").strip() and user.email:
        updates["email"] = user.email
    if not str(profil.get("yetkili") or "").strip() and user.full_name:
        updates["yetkili"] = user.full_name
    if updates:
        save_firma_profil(**updates)


def ensure_workspace_bound() -> None:
    """
    Tenant değiştiyse oturumu temizle ve o firmaya ait state'i yükle.
    Yeni firmada dosya yoksa boş / auth seed ile başlar.
    """
    key = tenant_storage_key()
    if st.session_state.get("_workspace_key") == key and st.session_state.get(
        "_app_state_loaded"
    ):
        return

    clear_workspace_session()
    st.session_state["_workspace_key"] = key
    loaded = load_app_state()
    if not loaded:
        seed_from_auth_if_empty()
    st.session_state["_app_state_loaded"] = True
