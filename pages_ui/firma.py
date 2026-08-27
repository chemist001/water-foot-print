"""Firma Bilgileri sayfası."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

from services.app_state import save_app_state
from services.firma_state import (
    YILLAR,
    clear_firma_logo,
    ensure_firma_profil,
    get_logo_path,
    save_firma_logo,
    save_firma_profil,
)


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def render() -> None:
    st.markdown(
        '<p class="page-title">Firma Bilgileri</p>'
        '<p class="page-sub">Raporlamaya konu firmanın kimlik, iletişim, logo ve sorumlu kişi bilgileri.</p>',
        unsafe_allow_html=True,
    )

    profil = ensure_firma_profil()
    yil = profil.get("rapor_yili") or "2026"
    yil_index = YILLAR.index(yil) if yil in YILLAR else YILLAR.index("2026")

    with st.form("firma_form", clear_on_submit=False):
        st.markdown('<div class="section-label">Temel Bilgiler</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            firma_adi = st.text_input(
                "Firma adı / unvanı",
                value=profil.get("firma_adi", ""),
                placeholder="Örn. ABC Sanayi A.Ş.",
            )
            sektor = st.text_input(
                "Sektör",
                value=profil.get("sektor", ""),
                placeholder="Örn. Tekstil",
            )
            lokasyon = st.text_input(
                "Lokasyon / adres",
                value=profil.get("lokasyon", ""),
                placeholder="Örn. Kocaeli / Gebze",
            )
            rapor_yili = st.selectbox(
                "Raporlama yılı",
                options=YILLAR,
                index=yil_index,
            )
        with c2:
            yetkili = st.text_input(
                "Yetkili kişi",
                value=profil.get("yetkili", ""),
                placeholder="Ad Soyad",
            )
            email = st.text_input(
                "E-posta",
                value=profil.get("email", ""),
                placeholder="ornek@firma.com",
            )
            telefon = st.text_input(
                "Telefon",
                value=profil.get("telefon", ""),
                placeholder="+90 …",
            )
            rapor_tarihi = st.date_input(
                "Rapor tarihi",
                value=profil.get("rapor_tarihi"),
            )

        kaydet = st.form_submit_button("Firma Bilgilerini Kaydet", type="primary")

    if kaydet:
        if not str(firma_adi).strip():
            st.error("Firma adı boş olamaz.")
        elif str(email).strip() and not _EMAIL_RE.match(str(email).strip()):
            st.error("Geçerli bir e-posta adresi girin (örn. ad@firma.com).")
        else:
            save_firma_profil(
                firma_adi=str(firma_adi).strip(),
                sektor=str(sektor).strip(),
                lokasyon=str(lokasyon).strip(),
                rapor_yili=rapor_yili,
                yetkili=str(yetkili).strip(),
                email=str(email).strip(),
                telefon=str(telefon).strip(),
                rapor_tarihi=rapor_tarihi,
            )
            save_app_state()
            st.success("Firma bilgileri kaydedildi. Raporlama sekmesine geçebilirsiniz.")

    st.markdown("<br/>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="section-label">Firma Logosu</div>', unsafe_allow_html=True)
        st.caption(
            "PNG veya JPG seçin — dosya seçilir seçilmez kaydedilir. "
            "Logo PDF/Word kapak sayfasının ortasında görünür."
        )
        col_up, col_prev = st.columns([1.2, 1])
        with col_up:
            uploaded = st.file_uploader(
                "Logo dosyası",
                type=["png", "jpg", "jpeg", "webp"],
                key="firma_logo_uploader",
                label_visibility="collapsed",
            )
            if uploaded is not None:
                # Aynı dosyayı tekrar tekrar kaydetmeyi önle
                sig = f"{uploaded.name}:{uploaded.size}"
                if st.session_state.get("_logo_upload_sig") != sig:
                    try:
                        path = save_firma_logo(uploaded)
                        st.session_state["_logo_upload_sig"] = sig
                        st.success(f"Logo kaydedildi: `{Path(path).name}`")
                    except Exception as e:
                        st.error(f"Logo kaydedilemedi: {e}")

            if st.button("Logoyu Kaldır", use_container_width=False):
                clear_firma_logo()
                st.session_state.pop("_logo_upload_sig", None)
                st.info("Logo kaldırıldı.")
                st.rerun()

        with col_prev:
            logo_path = get_logo_path()
            if logo_path:
                st.markdown("**Önizleme (kapak ortası)**")
                st.image(logo_path, width=220)
                st.caption(str(Path(logo_path).resolve()))
            else:
                st.warning("Henüz kayıtlı logo yok. Lütfen bir dosya seçin.")

    st.markdown("<br/>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="section-label">Su Yönetimi Sorumluları</div>', unsafe_allow_html=True)
        st.caption("Raporda yer alacak sorumlu kişi listesi.")
        if "sorumlu_kisiler_tablosu" not in st.session_state:
            st.session_state.sorumlu_kisiler_tablosu = pd.DataFrame(
                columns=["Sorumlu Kişi", "Görev", "İletişim"]
            )
        edited = st.data_editor(
            st.session_state.sorumlu_kisiler_tablosu,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="sorumlular_editor",
        )
        st.session_state.sorumlu_kisiler_tablosu = edited
        if st.button("Sorumluları Kaydet"):
            save_app_state()
            st.success("Sorumlu listesi kaydedildi.")

    guncel = ensure_firma_profil()
    if str(guncel.get("firma_adi", "")).strip():
        logo_notu = " · logo var" if get_logo_path() else ""
        st.caption(
            f"Kayıtlı firma: **{guncel['firma_adi']}** · "
            f"{guncel.get('sektor') or '—'} · {guncel.get('rapor_yili') or '—'}{logo_notu}"
        )
