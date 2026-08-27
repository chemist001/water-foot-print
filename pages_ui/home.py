"""Ana Sayfa — bilgilendirme, KPI özeti, pastel grafikler."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.calc import format_m3
from services.firma_state import get_firma

SVG_MAVI = """<svg width="64" height="64" viewBox="0 0 64 64" fill="none"><path d="M32 8C32 8 16 28 16 40a16 16 0 0032 0C48 28 32 8 32 8z" fill="#A8D5E5"/><path d="M32 18c0 0-9 12-9 20a9 9 0 0018 0c0-8-9-20-9-20z" fill="#7EB8D4" opacity=".55"/><circle cx="26" cy="38" r="3" fill="#FFF" opacity=".55"/></svg>"""
SVG_YESIL = """<svg width="64" height="64" viewBox="0 0 64 64" fill="none"><ellipse cx="34" cy="34" rx="18" ry="22" transform="rotate(-25 34 34)" fill="#B8DDB5"/><path d="M28 48c8-6 14-16 16-26" stroke="#6FA86A" stroke-width="2.2" stroke-linecap="round"/><circle cx="22" cy="22" r="5" fill="#D6EEF6" opacity=".7"/></svg>"""
SVG_GRI = """<svg width="64" height="64" viewBox="0 0 64 64" fill="none"><rect x="10" y="14" width="44" height="36" rx="10" fill="#D5D0E0"/><path d="M14 34c4-4 8-4 12 0s8 4 12 0 8-4 12 0" stroke="#8B849C" stroke-width="2.4" stroke-linecap="round" fill="none"/><path d="M14 42c4-4 8-4 12 0s8 4 12 0 8-4 12 0" stroke="#B0A9C0" stroke-width="2" stroke-linecap="round" fill="none"/></svg>"""
SVG_BM = """<svg width="64" height="64" viewBox="0 0 64 64" fill="none"><rect x="16" y="10" width="32" height="44" rx="4" fill="#A8D5E5"/><rect x="22" y="18" width="20" height="3" rx="1.5" fill="#FFF" opacity=".75"/><circle cx="32" cy="44" r="7" fill="#7EB8D4"/><path d="M29 44l2 2 4-4" stroke="#FFF" stroke-width="1.8" stroke-linecap="round"/></svg>"""
SVG_BY = """<svg width="64" height="64" viewBox="0 0 64 64" fill="none"><rect x="16" y="10" width="32" height="44" rx="4" fill="#B8DDB5"/><rect x="22" y="18" width="20" height="3" rx="1.5" fill="#FFF" opacity=".75"/><circle cx="32" cy="44" r="7" fill="#6FA86A"/><path d="M29 44l2 2 4-4" stroke="#FFF" stroke-width="1.8" stroke-linecap="round"/></svg>"""
SVG_BT = """<svg width="64" height="64" viewBox="0 0 64 64" fill="none"><rect x="16" y="10" width="32" height="44" rx="4" fill="#9DD4D0"/><rect x="22" y="18" width="20" height="3" rx="1.5" fill="#FFF" opacity=".75"/><circle cx="32" cy="44" r="7" fill="#4FA8A2"/><path d="M29 44l2 2 4-4" stroke="#FFF" stroke-width="1.8" stroke-linecap="round"/></svg>"""


def _card(css: str, chip: str, chip_txt: str, svg: str, title: str, body: str) -> str:
    return f"""<div class="info-card {css}"><div class="visual">{svg}</div>
    <span class="chip {chip}">{chip_txt}</span><h4>{title}</h4>{body}</div>"""


def _grafikler(mavi: float, yesil: float, gri: float) -> None:
    pastel = {"Mavi Su": "#A8D5E5", "Yeşil Su": "#B8DDB5", "Gri Su": "#D5D0E0"}
    df = pd.DataFrame({"Bileşen": list(pastel), "Değer (m³/yıl)": [mavi, yesil, gri]})
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(df, x="Bileşen", y="Değer (m³/yıl)", color="Bileşen", color_discrete_map=pastel, text="Değer (m³/yıl)")
        fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside", marker_line_width=0)
        fig.update_layout(title="Bileşen Toplamları", showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", height=360, yaxis=dict(gridcolor="#E8EEF3", title=""), xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure(data=[go.Pie(
            labels=df["Bileşen"], values=df["Değer (m³/yıl)"], hole=0.55,
            marker=dict(colors=[pastel[c] for c in df["Bileşen"]], line=dict(color="#F4F7FA", width=2)),
            textinfo="percent+label",
        )])
        fig.update_layout(title="Dağılım", paper_bgcolor="rgba(0,0,0,0)", height=360, showlegend=False,
                          annotations=[dict(text=f"<b>{mavi+yesil+gri:,.0f}</b><br>m³/yıl", x=0.5, y=0.5, showarrow=False)])
        st.plotly_chart(fig, use_container_width=True)


def render() -> None:
    st.markdown(
        """
        <h1 style="margin:0;font-size:1.75rem;color:#0B1F33;">Kurumsal Su Ayak İzi Dashboard</h1>
        <p style="color:#5A6B7A;margin:0.4rem 0 1.25rem 0;font-size:0.95rem;">
        Su ayak izi bileşenleri, Su Verimliliği Yönetmeliği belge seviyeleri ve tesis sonuç özeti.</p>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """<div class="intro-banner"><h3>Su Ayak İzi ve Su Verimliliği Yönetmeliği</h3>
        <p><strong>Su ayak izi</strong>, bir ürünün, sürecin veya tesisin tatlı su kullanımını nicel olarak ifade eder;
        mavi, yeşil ve gri bileşenlerden oluşur. 27 Aralık 2024 tarihli <strong>Su Verimliliği Yönetmeliği</strong>
        ile yükümlü kurumlar su verimliliği sistemi kurarak Mavi, Yeşil ve (gönüllü) Turkuaz belgelendirme
        seviyeleriyle ilişkilendirilir. Bu uygulama yerel olarak çalışır; bulut hesabı gerektirmez.</p></div>""",
        unsafe_allow_html=True,
    )

    st.markdown('<p class="section-heading">Su Ayak İzi Bileşenleri</p><p class="section-desc">Üç temel bileşenin kısa tanımları.</p>', unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown(_card("mavi", "chip-mavi", "Mavi Su", SVG_MAVI, "Mavi Su Ayak İzi",
            "<p>Yüzey ve yeraltı tatlı su kaynaklarından çekilen su. Şebeke, kuyu ve kaynak suları bu kapsamdadır.</p>"), unsafe_allow_html=True)
    with d2:
        st.markdown(_card("yesil", "chip-yesil", "Yeşil Su", SVG_YESIL, "Yeşil Su Ayak İzi",
            "<p>Yağış kaynaklı suyun proses, buharlaşma veya sulama yoluyla kullanımı. Fiilen kullanılan yağmur suyu dikkate alınır.</p>"), unsafe_allow_html=True)
    with d3:
        st.markdown(_card("gri", "chip-gri", "Gri Su", SVG_GRI, "Gri Su Ayak İzi",
            "<p>Kirleticilerin alıcı ortamda seyreltilmesi için gereken tatlı su eşdeğeri. Kritik parametre en yüksek sonucu verir.</p>"), unsafe_allow_html=True)

    st.markdown(
        '<p class="section-heading">Su Verimliliği Belgeleri</p>'
        '<p class="section-desc">Mavi, Yeşil ve Turkuaz belge seviyeleri (genel özet; ayrıntı Ek-3/4/5).</p>',
        unsafe_allow_html=True,
    )
    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown(_card("mavi", "chip-mavi", "Temel seviye", SVG_BM, "Mavi Su Verimliliği Belgesi",
            "<p>Sistem kurulumu ve temel izleme.</p><ul><li>Sorumlulukların tanımlanması</li><li>Ölçüm, kayıt ve izleme</li><li>Temel iyileştirme planı</li></ul>"), unsafe_allow_html=True)
    with b2:
        st.markdown(_card("yesil", "chip-yesil", "İleri seviye", SVG_BY, "Yeşil Su Verimliliği Belgesi",
            "<p>İleri verimlilik ve alternatif kaynaklar.</p><ul><li>Kayıpların azaltılması</li><li>Yağmur / gri su kullanımı</li><li>Sektörel Ek-4 kriterleri</li></ul>"), unsafe_allow_html=True)
    with b3:
        st.markdown(_card("turkuaz", "chip-turkuaz", "Gönüllü üst seviye", SVG_BT, "Turkuaz Su Verimliliği Belgesi",
            "<p>Gönüllü en üst seviye.</p><ul><li>Yüksek geri kazanım</li><li>Sürekli iyileştirme</li><li>ISO 46001 / 14046 uyumu</li></ul>"), unsafe_allow_html=True)

    st.markdown(
        '<div class="note-soft"><strong>Not:</strong> Ayak izi bileşenleri (mavi/yeşil/gri) ile belge seviyeleri '
        "(mavi/yeşil/turkuaz) farklı kavramlardır. Resmi kriterler için yönetmelik ve suverimliligi.gov.tr esas alınmalıdır.</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<p class="section-heading">Tesis Sonuç Özeti</p><p class="section-desc">Veri Girişi hesaplamasının özeti.</p>', unsafe_allow_html=True)
    mavi, yesil, gri, toplam = (
        st.session_state.sonuc_mavi,
        st.session_state.sonuc_yesil,
        st.session_state.sonuc_gri,
        st.session_state.sonuc_toplam,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mavi Su", format_m3(mavi if st.session_state.hesaplandi else None, "m³"))
    c2.metric("Yeşil Su", format_m3(yesil if st.session_state.hesaplandi else None, "m³"))
    c3.metric("Gri Su", format_m3(gri if st.session_state.hesaplandi else None, "m³/yıl"))
    c4.metric("Genel Toplam", format_m3(toplam if st.session_state.hesaplandi else None, "m³/yıl"))

    if st.session_state.hesaplandi and None not in (mavi, yesil, gri):
        st.markdown('<div class="panel" style="padding-bottom:0.5rem;"><div class="panel-title">Su Ayak İzi Dağılımı</div>'
                    '<div class="panel-sub">Mavi, yeşil ve gri su ayak izi toplamları.</div></div>', unsafe_allow_html=True)
        _grafikler(float(mavi), float(yesil), float(gri))
    else:
        st.info("Henüz hesaplama yok. **Veri Girişi** sekmesinden **Hesapla** butonunu kullanın.")

    profil = get_firma()
    firma = profil.get("firma_adi") or "—"
    sektor = profil.get("sektor") or "—"
    lokasyon = profil.get("lokasyon") or "—"
    yil = profil.get("rapor_yili") or "—"
    st.markdown("<br/>", unsafe_allow_html=True)
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns(4)
        f1.markdown(f"**Firma**<br/>{firma}", unsafe_allow_html=True)
        f2.markdown(f"**Sektör**<br/>{sektor}", unsafe_allow_html=True)
        f3.markdown(f"**Lokasyon**<br/>{lokasyon}", unsafe_allow_html=True)
        f4.markdown(f"**Raporlama yılı**<br/>{yil}", unsafe_allow_html=True)
