"""Geçmiş raporlar — yerel JSON listesi, PDF/Word, oturuma yükleme."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.app_state import load_report_into_session
from services.calc import format_m3
from services.docx_report import generate_docx_bytes
from services.pdf_report import generate_pdf_bytes
from services.storage import gecmis_raporlari_getir, rapor_sil


def render() -> None:
    from services import auth
    from services.demo import banner, is_demo, reports_locked_message
    from services.storage import use_cloud

    banner()

    if use_cloud():
        alt = (
            "Buluttaki raporlar — ADASO tüm firmaları, firma kullanıcısı yalnız kendi tesisini görür."
            if auth.is_adaso()
            else "Firmanıza ait bulut raporları."
        )
    else:
        alt = "Bu bilgisayarda kaydedilmiş su ayak izi raporları."

    st.markdown(
        f'<p class="page-title">Geçmiş Raporlar</p>'
        f'<p class="page-sub">{alt}</p>',
        unsafe_allow_html=True,
    )

    if st.button("Listeyi yenile"):
        st.rerun()

    raporlar = gecmis_raporlari_getir()
    if not raporlar:
        st.info(
            "Henüz kayıtlı rapor yok."
            + (" Demo sürümünde yeni rapor kaydı da kapalıdır." if is_demo() else " Raporlama sekmesinden **Kaydet** kullanın.")
        )
        return

    df = pd.DataFrame(raporlar)
    goster = pd.DataFrame({
        "ID": df.get("id"),
        "Firma": df.get("firma_adi"),
        "Mavi (m³)": df.get("mavi_su"),
        "Yeşil (m³)": df.get("yesil_su"),
        "Gri (m³)": df.get("gri_su"),
        "Toplam (m³)": df.get("toplam_su"),
        "Tarih": df.get("olusturma_tarihi"),
    })
    st.dataframe(goster, use_container_width=True, hide_index=True)

    secenekler = {
        f"{r.get('firma_adi', 'Rapor')} — {r.get('olusturma_tarihi', '')[:16]} [{r.get('id')}]": r
        for r in raporlar
    }
    etiket = st.selectbox("Rapor seçin", options=["Seçiniz…"] + list(secenekler.keys()))
    if etiket == "Seçiniz…":
        return

    secilen = secenekler[etiket]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mavi", format_m3(secilen.get("mavi_su"), "m³"))
    c2.metric("Yeşil", format_m3(secilen.get("yesil_su"), "m³"))
    c3.metric("Gri", format_m3(secilen.get("gri_su"), "m³/yıl"))
    c4.metric("Toplam", format_m3(secilen.get("toplam_su"), "m³/yıl"))

    st.caption(
        f"Rapor tarihi: **{secilen.get('rapor_tarihi', '—')}** · "
        f"Kayıt: **{secilen.get('olusturma_tarihi', '—')[:19]}**"
    )

    if is_demo():
        reports_locked_message()
        if st.button("Oturuma Yükle", use_container_width=True):
            load_report_into_session(secilen)
            st.success("Rapor oturuma yüklendi. Diğer sekmelerden inceleyebilirsiniz.")
            st.rerun()
        return

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        try:
            pdf_bytes = generate_pdf_bytes(secilen)
            st.download_button(
                "PDF İndir",
                data=pdf_bytes,
                file_name=f"rapor_{secilen.get('id', 'x')}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"PDF hatası: {e}")

    with b2:
        try:
            docx_bytes = generate_docx_bytes(secilen)
            st.download_button(
                "Word İndir",
                data=docx_bytes,
                file_name=f"rapor_{secilen.get('id', 'x')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Word hatası: {e}")

    with b3:
        if st.button("Oturuma Yükle", use_container_width=True):
            load_report_into_session(secilen)
            st.success("Rapor oturuma yüklendi. Diğer sekmelerden düzenleyebilirsiniz.")
            st.rerun()

    with b4:
        onay = st.checkbox("Silmeyi onaylıyorum", key=f"sil_onay_{secilen.get('id')}")
        if st.button("Sil", use_container_width=True, disabled=not onay):
            if rapor_sil(str(secilen.get("id"))):
                st.success("Rapor silindi.")
                st.rerun()
            else:
                st.error("Silinemedi.")
