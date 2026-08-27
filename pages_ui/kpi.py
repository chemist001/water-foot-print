"""Performans KPI sayfası."""

from __future__ import annotations

import streamlit as st

from services.app_state import build_kpi_snapshot, save_app_state
from services.calc import format_m3


def render() -> None:
    st.markdown(
        '<p class="page-title">Performans (KPI)</p>'
        '<p class="page-sub">Spesifik su tüketimi ve evsel verimlilik göstergeleri.</p>',
        unsafe_allow_html=True,
    )

    if not st.session_state.get("hesaplandi"):
        st.warning("Önce **Veri Girişi** sekmesinde su ayak izi hesaplaması yapın.")
        return

    with st.container(border=True):
        st.markdown('<div class="section-label">Üretim ve Tesis</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        uretim = c1.number_input("Yıllık üretim miktarı", min_value=0.0, step=1.0, key="kpi_uretim")
        birimler = ["ton", "adet", "m³", "MWh", "kg"]
        birim = c2.selectbox("Birim", birimler, key="kpi_uretim_birimi")
        gun = c3.number_input("Yıllık çalışma günü", min_value=0.0, step=1.0, key="kpi_calisma_gunu")
        personel = c4.number_input("Personel sayısı", min_value=0.0, step=1.0, key="kpi_personel")

    st.markdown("<br/>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="section-label">Evsel ve Diğer Tüketimler (m³/yıl)</div>', unsafe_allow_html=True)
        r1 = st.columns(3)
        evsel = r1[0].number_input("Evsel su", min_value=0.0, step=1.0, key="kpi_evsel_su")
        sulama = r1[1].number_input("Yeşil alan sulama", min_value=0.0, step=1.0, key="kpi_sulama")
        yangin = r1[2].number_input("Yangın hattı", min_value=0.0, step=1.0, key="kpi_yangin")
        r2 = st.columns(3)
        arac = r2[0].number_input("Araç yıkama / zemin", min_value=0.0, step=1.0, key="kpi_arac")
        geri = r2[1].number_input("Geri kazanım suyu", min_value=0.0, step=1.0, key="kpi_geri")
        evsel_atik = r2[2].number_input("Evsel atıksu", min_value=0.0, step=1.0, key="kpi_evsel_atik")

    toplam_giren = (
        float(st.session_state.get("mavi_sebeke", 0.0))
        + float(st.session_state.get("mavi_yeralti", 0.0))
        + float(st.session_state.get("mavi_kaynak", 0.0))
    )
    proses_atiksu = float(st.session_state.get("gri_debi", 0.0))

    st.caption(
        f"Veri Girişi’nden alınan toplam giren su: **{format_m3(toplam_giren, 'm³')}** · "
        f"Atıksu debisi (V): **{format_m3(proses_atiksu, 'm³/yıl')}**"
    )

    if st.button("KPI Göstergelerini Hesapla", type="primary"):
        if uretim <= 0:
            st.error("Yıllık üretim miktarı 0'dan büyük olmalıdır.")
        elif gun <= 0 or personel <= 0:
            st.error("Çalışma günü ve personel sayısı 0'dan büyük olmalıdır.")
        else:
            net_proses = max(0.0, toplam_giren - (evsel + sulama + yangin + arac + geri))
            if net_proses < toplam_giren * 0.05 and toplam_giren > 0:
                st.warning(
                    "Net proses suyu, toplam giren sudan çok düşük. "
                    "Evsel/diğer tüketim kalemlerini kontrol edin."
                )
            spesifik_su = net_proses / uretim
            spesifik_atiksu = proses_atiksu / uretim
            payda = gun * personel
            sp_evsel = (evsel * 1000) / payda
            sp_evsel_atik = (evsel_atik * 1000) / payda

            st.session_state.kpi_net_proses = net_proses
            st.session_state.kpi_spesifik_su = spesifik_su
            st.session_state.kpi_spesifik_atiksu = spesifik_atiksu
            st.session_state.kpi_evsel_su_gosterge = sp_evsel
            st.session_state.kpi_evsel_atiksu_gosterge = sp_evsel_atik
            st.session_state.kpi_hesaplandi = True
            st.session_state.kpi_snapshot = build_kpi_snapshot()
            save_app_state()
            st.success("Verimlilik göstergeleri hesaplandı.")

    if st.session_state.get("kpi_hesaplandi"):
        st.markdown('<div class="section-label">Proses Verimliliği</div>', unsafe_allow_html=True)
        a, b = st.columns(2)
        a.metric(
            "Spesifik Su Tüketimi",
            f"{st.session_state.kpi_spesifik_su:,.2f} m³/{birim}".replace(",", "X").replace(".", ",").replace("X", "."),
            help=f"Net proses suyu: {st.session_state.kpi_net_proses:,.1f} m³",
        )
        b.metric(
            "Spesifik Atıksu Oluşumu",
            f"{st.session_state.kpi_spesifik_atiksu:,.2f} m³/{birim}".replace(",", "X").replace(".", ",").replace("X", "."),
        )
        st.markdown('<div class="section-label">Evsel Verimlilik</div>', unsafe_allow_html=True)
        c, d = st.columns(2)
        c.metric("Spesifik Evsel Su", f"{st.session_state.kpi_evsel_su_gosterge:,.2f} L/kişi.gün".replace(",", "X").replace(".", ",").replace("X", "."))
        d.metric("Spesifik Evsel Atıksu", f"{st.session_state.kpi_evsel_atiksu_gosterge:,.2f} L/kişi.gün".replace(",", "X").replace(".", ",").replace("X", "."))
