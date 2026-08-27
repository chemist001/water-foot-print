"""Raporlama — özet, profesyonel PDF, yerel kayıt."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from services.app_state import calc_inputs_changed, save_app_state
from services.calc import format_m3
from services.docx_report import generate_docx_bytes
from services.firma_state import firma_adi_var, get_firma, get_logo_path
from services.kanit import ozet_payload
from services.pdf_report import generate_pdf_bytes
from services.storage import raporu_kaydet


def _default_sistem_siniri() -> pd.DataFrame:
    rows = []
    if (
        float(st.session_state.get("mavi_sebeke", 0) or 0)
        + float(st.session_state.get("mavi_yeralti", 0) or 0)
        + float(st.session_state.get("mavi_kaynak", 0) or 0)
    ) > 0:
        rows.append({
            "Bileşen": "Mavi Su",
            "Kaynak": "Şebeke / Kuyu / Kaynak",
            "Veri Kaynağı": "Sayaç ve Fatura",
            "Veri Doğrulama": "Tüketim Kayıtları",
            "Açıklama (Diğer)": "",
        })
    if float(st.session_state.get("yesil_yagmur", 0) or 0) > 0:
        rows.append({
            "Bileşen": "Yeşil Su",
            "Kaynak": "Yağmur Suyu",
            "Veri Kaynağı": "Meteorolojik Veri",
            "Veri Doğrulama": "İç Kayıtlar",
            "Açıklama (Diğer)": "",
        })
    if float(st.session_state.get("gri_debi", 0) or 0) > 0:
        rows.append({
            "Bileşen": "Gri Su",
            "Kaynak": "Endüstriyel Atıksu",
            "Veri Kaynağı": "Analiz Raporları",
            "Veri Doğrulama": "Laboratuvar Beyanı",
            "Açıklama (Diğer)": "",
        })
    cols = ["Bileşen", "Kaynak", "Veri Kaynağı", "Veri Doğrulama", "Açıklama (Diğer)"]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def _payload() -> dict:
    firma = get_firma()
    snap = st.session_state.get("calc_snapshot") or {}
    hedefler = st.session_state.get("hedef_tablosu", pd.DataFrame())
    if isinstance(hedefler, pd.DataFrame):
        hedefler_list = hedefler.to_dict(orient="records") if not hedefler.empty else []
    else:
        hedefler_list = []

    sorumlular = st.session_state.get("sorumlu_kisiler_tablosu", pd.DataFrame())
    if isinstance(sorumlular, pd.DataFrame):
        sorumlular_list = sorumlular.to_dict(orient="records") if not sorumlular.empty else []
    else:
        sorumlular_list = []

    sistem = st.session_state.get("sistem_siniri_tablosu")
    if sistem is None or (isinstance(sistem, pd.DataFrame) and sistem.empty):
        sistem = _default_sistem_siniri()
        st.session_state.sistem_siniri_tablosu = sistem
    if isinstance(sistem, pd.DataFrame):
        sistem_list = sistem.to_dict(orient="records") if not sistem.empty else []
    else:
        sistem_list = sistem or []

    kpi = {}
    if st.session_state.get("kpi_hesaplandi"):
        kpi = {
            "uretim_birimi": st.session_state.get("kpi_uretim_birimi", "ton"),
            "spesifik_su": st.session_state.get("kpi_spesifik_su"),
            "spesifik_atiksu": st.session_state.get("kpi_spesifik_atiksu"),
            "evsel_su": st.session_state.get("kpi_evsel_su_gosterge"),
            "evsel_atiksu": st.session_state.get("kpi_evsel_atiksu_gosterge"),
        }

    return {
        "firma_adi": firma.get("firma_adi") or "Belirtilmedi",
        "sektor": firma.get("sektor") or "Belirtilmedi",
        "lokasyon": firma.get("lokasyon") or "Belirtilmedi",
        "yetkili": firma.get("yetkili") or "Belirtilmedi",
        "email": firma.get("email") or "Belirtilmedi",
        "telefon": firma.get("telefon") or "Belirtilmedi",
        "rapor_yili": firma.get("rapor_yili") or "2026",
        "rapor_tarihi": firma.get("rapor_tarihi"),
        "logo_path": get_logo_path() or firma.get("logo_path") or "",
        "mavi_su": snap.get("sonuc_mavi", st.session_state.get("sonuc_mavi")),
        "yesil_su": snap.get("sonuc_yesil", st.session_state.get("sonuc_yesil")),
        "gri_su": snap.get("sonuc_gri", st.session_state.get("sonuc_gri")),
        "toplam_su": snap.get("sonuc_toplam", st.session_state.get("sonuc_toplam")),
        "gri_kritik": snap.get("gri_kritik_parametre", st.session_state.get("gri_kritik_parametre")),
        "gri_detay": snap.get("gri_parametre_sonuclari", st.session_state.get("gri_parametre_sonuclari")) or [],
        "mavi_sebeke": snap.get("mavi_sebeke", st.session_state.get("mavi_sebeke", 0.0)),
        "mavi_yeralti": snap.get("mavi_yeralti", st.session_state.get("mavi_yeralti", 0.0)),
        "mavi_kaynak": snap.get("mavi_kaynak", st.session_state.get("mavi_kaynak", 0.0)),
        "yesil_yagmur": snap.get("yesil_yagmur", st.session_state.get("yesil_yagmur", 0.0)),
        "gri_debi": snap.get("gri_debi", st.session_state.get("gri_debi", 0.0)),
        "hedefler": hedefler_list,
        "sorumlular": sorumlular_list,
        "sistem_siniri": sistem_list,
        "veri_kalitesi": st.session_state.get("veri_kalitesi_aciklama", ""),
        "kpi": kpi,
        # Her export anında güncel kanıt özeti (bayat session değeri kullanma)
        "mavi_kanit": ozet_payload(
            firma.get("rapor_yili") or "2026",
            snap.get("mavi_sebeke", st.session_state.get("mavi_sebeke", 0.0)),
            snap.get("mavi_yeralti", st.session_state.get("mavi_yeralti", 0.0)),
            snap.get("mavi_kaynak", st.session_state.get("mavi_kaynak", 0.0)),
        ),
    }


def render() -> None:
    from services.demo import banner, is_demo

    banner()
    st.markdown(
        '<p class="page-title">Raporlama</p>'
        '<p class="page-sub">Sonuç özeti, ISO 14046 uyumlu profesyonel PDF ve yerel kayıt.</p>',
        unsafe_allow_html=True,
    )

    if is_demo():
        st.caption("Demo: ekran özetleri açık · PDF / Word / kaydet kapalı.")

    if not st.session_state.get("hesaplandi"):
        st.warning("Önce **Veri Girişi** sekmesinde hesaplama yapın.")
        return

    if calc_inputs_changed():
        st.warning(
            "Veri girişi son hesaplamadan sonra değişti. "
            "Güncel rapor için **Veri Girişi** sekmesinde yeniden **Hesapla**'ya basın."
        )
        stale = True
    else:
        stale = False

    firma = get_firma()
    if firma_adi_var():
        st.caption(f"Rapor firması: **{firma.get('firma_adi')}** ({firma.get('rapor_yili', '—')})")
    else:
        st.warning("Firma adı kayıtlı değil. **Firma Bilgileri** sekmesinde **Firma Bilgilerini Kaydet**’e basın.")

    mavi = st.session_state.sonuc_mavi or 0.0
    yesil = st.session_state.sonuc_yesil or 0.0
    gri = st.session_state.sonuc_gri or 0.0
    toplam = st.session_state.sonuc_toplam or (mavi + yesil + gri)
    kritik = st.session_state.get("gri_kritik_parametre") or "—"

    st.markdown("### Su Ayak İzi Sonuçları")
    c1, c2, c3 = st.columns(3)
    c1.metric("Mavi Su Ayak İzi", format_m3(mavi, "m³/yıl"))
    c2.metric("Yeşil Su Ayak İzi", format_m3(yesil, "m³/yıl"))
    c3.metric("Gri Su Ayak İzi", format_m3(gri, "m³/yıl"), help=f"Kritik parametre: {kritik}")
    st.info(f"**Toplam Tesis Su Ayak İzi:** {format_m3(toplam, 'm³/yıl')}")

    st.markdown("### Su Ayak İzi Dağılımı")
    df = pd.DataFrame({
        "Bileşen": ["Mavi Su", "Yeşil Su", "Gri Su"],
        "Hacim (m³/yıl)": [mavi, yesil, gri],
    })
    fig = px.pie(
        df,
        values="Hacim (m³/yıl)",
        names="Bileşen",
        hole=0.4,
        color="Bileşen",
        color_discrete_map={"Mavi Su": "#A8D5E5", "Yeşil Su": "#B8DDB5", "Gri Su": "#D5D0E0"},
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=340, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        st.markdown('<div class="section-label">Veri Kalitesi (rapora yansır)</div>', unsafe_allow_html=True)
        st.text_area(
            "Metodoloji / veri kalitesi açıklaması",
            key="veri_kalitesi_aciklama",
            height=100,
            placeholder="Boş bırakılırsa raporda standart metin kullanılır.",
            label_visibility="collapsed",
        )

    with st.container(border=True):
        st.markdown('<div class="section-label">Sistem Sınırı Tablosu</div>', unsafe_allow_html=True)
        if "sistem_siniri_tablosu" not in st.session_state or st.session_state.sistem_siniri_tablosu.empty:
            st.session_state.sistem_siniri_tablosu = _default_sistem_siniri()
        st.session_state.sistem_siniri_tablosu = st.data_editor(
            st.session_state.sistem_siniri_tablosu,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="sistem_siniri_editor",
            column_config={
                "Bileşen": st.column_config.SelectboxColumn(
                    options=["Mavi Su", "Yeşil Su", "Gri Su"], required=True
                ),
                "Kaynak": st.column_config.TextColumn(),
                "Veri Kaynağı": st.column_config.SelectboxColumn(
                    options=["Sayaç ve Fatura", "Analiz Raporları", "Sayaç", "Tahmin/Beyan", "Meteorolojik Veri", "Diğer"]
                ),
                "Veri Doğrulama": st.column_config.SelectboxColumn(
                    options=["Tüketim Kayıtları", "Fatura Kontrolü", "Laboratuvar Beyanı", "İç Kayıtlar", "Diğer"]
                ),
                "Açıklama (Diğer)": st.column_config.TextColumn(),
            },
        )

    with st.container(border=True):
        st.markdown('<div class="section-label">Sürdürülebilirlik Hedefleri</div>', unsafe_allow_html=True)
        st.caption("Rapora eklenecek aksiyon hedefleri. Yeni satır için tablonun altını kullanın.")
        if "hedef_tablosu" not in st.session_state:
            st.session_state.hedef_tablosu = pd.DataFrame(columns=["Hedef Yılı", "Hedef Açıklaması"])
        st.session_state.hedef_tablosu = st.data_editor(
            st.session_state.hedef_tablosu,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="hedef_editor",
        )

    st.divider()
    st.markdown("### Rapor Çıktıları")

    from services.demo import is_demo, reports_locked_message

    if is_demo():
        # Demo'da önceki oturumda üretilmiş indirme kalmasın
        st.session_state.pop("_pdf_bytes", None)
        st.session_state.pop("_pdf_name", None)
        st.session_state.pop("_docx_bytes", None)
        st.session_state.pop("_docx_name", None)
        reports_locked_message()
        return

    logo_ok = bool(get_logo_path())
    if logo_ok:
        st.caption(f"Kapak logosu hazır: `{get_logo_path()}`")
    else:
        st.warning("Kapak logosu yok. Firma Bilgileri’nden logo seçin (otomatik kaydedilir).")

    st.write(
        "PDF (basım) ve Word (düzenlenebilir) çıktı üretebilirsiniz. "
        "Word dosyasını Microsoft Word veya LibreOffice ile açıp metinleri değiştirebilirsiniz."
    )

    b1, b2, b3 = st.columns(3)
    with b1:
        olustur_pdf = st.button(
            "PDF Oluştur", type="primary", use_container_width=True, disabled=stale
        )
    with b2:
        olustur_word = st.button("Word Oluştur", use_container_width=True, disabled=stale)
    with b3:
        from services.storage import use_cloud

        kaydet_label = "Buluta Kaydet" if use_cloud() else "Yerel Kaydet"
        kaydet = st.button(kaydet_label, use_container_width=True, disabled=stale)

    if olustur_pdf:
        if not firma_adi_var():
            st.error("Lütfen Firma Adını giriniz (Firma Bilgileri sekmesinden kaydedin).")
        else:
            try:
                data = _payload()
                with st.spinner("PDF oluşturuluyor…"):
                    pdf_bytes = generate_pdf_bytes(data)
                st.session_state["_pdf_bytes"] = pdf_bytes
                safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in data["firma_adi"])[:40]
                st.session_state["_pdf_name"] = f"Su_Ayak_Izi_Raporu_{safe_name}.pdf"
                if data.get("logo_path"):
                    st.success("PDF hazır (logo dahil).")
                else:
                    st.success("PDF hazır (logo bulunamadı — kapakta logo yok).")
            except Exception as e:
                st.error(f"PDF oluşturma hatası: {e}")

    if olustur_word:
        if not firma_adi_var():
            st.error("Lütfen Firma Adını giriniz (Firma Bilgileri sekmesinden kaydedin).")
        else:
            try:
                data = _payload()
                with st.spinner("Word raporu oluşturuluyor…"):
                    docx_bytes = generate_docx_bytes(data)
                st.session_state["_docx_bytes"] = docx_bytes
                safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in data["firma_adi"])[:40]
                st.session_state["_docx_name"] = f"Su_Ayak_Izi_Raporu_{safe_name}.docx"
                st.success("Word raporu hazır — indirip düzenleyebilirsiniz.")
            except Exception as e:
                st.error(f"Word oluşturma hatası: {e}")

    if kaydet:
        data = _payload()
        if not firma_adi_var():
            st.error("Lütfen Firma Adını giriniz (Firma Bilgileri).")
        elif data["mavi_su"] is None:
            st.error("Önce hesaplama yapın.")
        else:
            rid = raporu_kaydet(data)
            save_app_state()
            from services.storage import use_cloud

            if use_cloud():
                st.success(f"Rapor buluta kaydedildi (ID: {rid}).")
            else:
                st.success(f"Rapor yerel olarak kaydedildi (ID: {rid}).")

    d1, d2 = st.columns(2)
    with d1:
        if st.session_state.get("_pdf_bytes"):
            st.download_button(
                label="PDF İndir",
                data=st.session_state["_pdf_bytes"],
                file_name=st.session_state.get("_pdf_name", "Su_Ayak_Izi_Raporu.pdf"),
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
    with d2:
        if st.session_state.get("_docx_bytes"):
            st.download_button(
                label="Word İndir (.docx)",
                data=st.session_state["_docx_bytes"],
                file_name=st.session_state.get("_docx_name", "Su_Ayak_Izi_Raporu.docx"),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

    st.caption("Yerel sürüm: AI danışman ve bulut kaydı yoktur. Raporlar `data/raporlar` klasörüne yazılır.")
