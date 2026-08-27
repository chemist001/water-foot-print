"""Veri Girişi — mavi / yeşil / gri hesaplama + mavi su fatura kanıtı."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.app_state import build_calc_snapshot, save_app_state
from services.calc import (
    format_m3,
    hesapla_gri_su,
    hesapla_mavi_su,
    hesapla_yesil_su,
)
from services.firma_state import get_firma
from services.fatura_ocr import analyze_fatura_file
from services.kanit import (
    KAYNAK_SEBEKE,
    KAYNAK_SECENEKLERI,
    dedupe_faturalar,
    fatura_ekle,
    fatura_sil,
    fatura_toplamlari,
    karsilastir_mavi_su,
    list_faturalar,
    ozet_payload,
)


def _rapor_yili() -> str:
    return str(get_firma().get("rapor_yili") or "2026")


def _apply_ocr_to_form(result: dict) -> None:
    """OCR sonucunu form alanlarına yazar (widget oluşturulmadan önce)."""
    if result.get("onerilen_m3") is not None:
        st.session_state["kanit_m3"] = float(result["onerilen_m3"])
    if result.get("fatura_no") and not str(st.session_state.get("kanit_fatura_no") or "").strip():
        st.session_state["kanit_fatura_no"] = result["fatura_no"]
    if result.get("donem") and not str(st.session_state.get("kanit_donem") or "").strip():
        st.session_state["kanit_donem"] = result["donem"]


def _render_mavi_kanit(yil: str) -> None:
    st.markdown("<br/>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            '<div class="section-label">Su Faturası Kanıt Belgeleri</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"**{yil}** yılı için istediğiniz kadar fatura yükleyebilirsiniz. "
            "Sistem her faturada **SARFİYAT** satırındaki m³ değerini okumaya çalışır; "
            "yanlışsa tabloda düzeltebilirsiniz. "
            "Toplamlar şebeke / kuyu / kaynak girdileriyle karşılaştırılır "
            "(tolerans: ±1 m³ veya %1)."
        )

        with st.expander("Fatura yükle (çoklu)", expanded=True):
            kaynak_varsayilan = st.selectbox(
                "Bu yükleme için kaynak tipi",
                KAYNAK_SECENEKLERI,
                key="kanit_kaynak_toplu",
            )
            uploaded_files = st.file_uploader(
                "PDF / JPG / PNG — birden fazla seçebilirsiniz",
                type=["pdf", "jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                key="kanit_dosyalar",
            )

            if uploaded_files:
                sig = "|".join(f"{f.name}:{f.size}" for f in uploaded_files)
                if st.session_state.get("_kanit_batch_sig") != sig:
                    results = []
                    progress = st.progress(0.0, text="Faturalar okunuyor…")
                    for i, f in enumerate(uploaded_files):
                        progress.progress(
                            (i) / max(len(uploaded_files), 1),
                            text=f"Okunuyor: {f.name}",
                        )
                        try:
                            r = analyze_fatura_file(f)
                        except Exception as e:
                            r = {
                                "dosya_adi": f.name,
                                "onerilen_m3": None,
                                "adaylar": [],
                                "fatura_no": "",
                                "donem": "",
                                "yontem": "none",
                                "guven": "yok",
                                "uyarilar": [str(e)],
                                "sarfiyat_bulundu": False,
                            }
                        r["_file_idx"] = i
                        r["_file_name"] = f.name
                        r["_file_size"] = f.size
                        results.append(r)
                    progress.progress(1.0, text="Okuma tamamlandı")
                    st.session_state["_kanit_batch_sig"] = sig
                    st.session_state["_kanit_batch_results"] = results
                    # Düzenlenebilir tablo başlangıcı
                    st.session_state["_kanit_batch_rows"] = [
                        {
                            "Dosya": r.get("dosya_adi") or r.get("_file_name"),
                            "Kaynak": kaynak_varsayilan,
                            "Fatura No": r.get("fatura_no") or "",
                            "Dönem": r.get("donem") or "",
                            "m³": float(r["onerilen_m3"])
                            if r.get("onerilen_m3") is not None
                            else 0.0,
                            "OCR": (
                                f"{r.get('onerilen_m3')} ({r.get('guven')})"
                                if r.get("onerilen_m3") is not None
                                else "okunamadı"
                            ),
                            "_idx": r.get("_file_idx", i),
                        }
                        for i, r in enumerate(results)
                    ]

            batch_rows = st.session_state.get("_kanit_batch_rows")
            if uploaded_files and batch_rows:
                st.markdown("**Okunan faturalar — kaydetmeden önce m³ değerlerini kontrol edin**")
                for r in st.session_state.get("_kanit_batch_results") or []:
                    if r.get("onerilen_m3") is not None and r.get("sarfiyat_bulundu"):
                        st.caption(
                            f"✓ {r.get('dosya_adi')}: SARFİYAT → "
                            f"**{r['onerilen_m3']:,.2f} m³**".replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )
                    elif r.get("onerilen_m3") is not None:
                        st.caption(
                            f"⚠ {r.get('dosya_adi')}: öneri {r['onerilen_m3']} m³ "
                            f"(SARFİYAT net değil — kontrol edin)"
                        )
                    else:
                        st.caption(f"✗ {r.get('dosya_adi')}: otomatik okunamadı")
                    for u in (r.get("uyarilar") or [])[:2]:
                        st.caption(f"  · {u}")

                edited = st.data_editor(
                    pd.DataFrame(batch_rows),
                    num_rows="fixed",
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Dosya": st.column_config.TextColumn(disabled=True),
                        "Kaynak": st.column_config.SelectboxColumn(
                            options=KAYNAK_SECENEKLERI, required=True
                        ),
                        "Fatura No": st.column_config.TextColumn(),
                        "Dönem": st.column_config.TextColumn(),
                        "m³": st.column_config.NumberColumn(
                            min_value=0.0, format="%.2f", required=True
                        ),
                        "OCR": st.column_config.TextColumn(disabled=True),
                        "_idx": None,
                    },
                    key="kanit_batch_editor",
                )
                st.session_state["_kanit_batch_rows"] = edited.to_dict(orient="records")

                if st.button("Seçilen faturaları kaydet", type="primary", key="kanit_toplu_kaydet"):
                    kaydedilen = 0
                    hatalar = []
                    files_by_idx = {i: f for i, f in enumerate(uploaded_files)}
                    ocr_by_idx = {
                        r.get("_file_idx", i): r
                        for i, r in enumerate(st.session_state.get("_kanit_batch_results") or [])
                    }
                    for row in edited.to_dict(orient="records"):
                        try:
                            m3_val = float(row.get("m³") or 0)
                        except (TypeError, ValueError):
                            m3_val = 0.0
                        if m3_val <= 0:
                            hatalar.append(f"{row.get('Dosya')}: m³ boş/geçersiz — atlandı")
                            continue
                        idx = int(row.get("_idx", -1))
                        fobj = files_by_idx.get(idx)
                        ocr = ocr_by_idx.get(idx) or {}
                        try:
                            fatura_ekle(
                                yil,
                                kaynak=str(row.get("Kaynak") or kaynak_varsayilan),
                                m3=m3_val,
                                fatura_no=str(row.get("Fatura No") or ""),
                                donem=str(row.get("Dönem") or ""),
                                uploaded_file=fobj,
                                notlar="",
                                ocr_m3=(
                                    float(ocr["onerilen_m3"])
                                    if ocr.get("onerilen_m3") is not None
                                    else None
                                ),
                                ocr_yontem=str(ocr.get("yontem") or ""),
                            )
                            kaydedilen += 1
                        except Exception as e:
                            hatalar.append(f"{row.get('Dosya')}: {e}")

                    if kaydedilen or hatalar:
                        save_app_state()
                        st.session_state.pop("_kanit_batch_sig", None)
                        st.session_state.pop("_kanit_batch_results", None)
                        st.session_state.pop("_kanit_batch_rows", None)
                        st.session_state["_kanit_batch_msg"] = {
                            "ok": kaydedilen,
                            "hatalar": hatalar,
                        }
                        st.rerun()

            # Önceki toplu kayıt mesajları
            batch_msg = st.session_state.pop("_kanit_batch_msg", None)
            if isinstance(batch_msg, dict):
                if batch_msg.get("ok"):
                    st.success(f"{batch_msg['ok']} fatura kaydedildi.")
                for h in batch_msg.get("hatalar") or []:
                    st.warning(h)

            st.divider()
            st.caption("Tek fatura için hızlı ekleme (dosyasız / elle)")
            c1, c2, c3 = st.columns(3)
            with c1:
                kaynak_tek = st.selectbox("Kaynak", KAYNAK_SECENEKLERI, key="kanit_kaynak_tek")
            with c2:
                m3_tek = st.number_input(
                    "m³", min_value=0.0, step=1.0, format="%.2f", key="kanit_m3_tek"
                )
            with c3:
                donem_tek = st.text_input("Dönem", key="kanit_donem_tek", placeholder="Örn. Eylül 2025")
            if st.button("Elle kayıt ekle", key="kanit_elle_kaydet"):
                if m3_tek <= 0:
                    st.error("m³ 0'dan büyük olmalı.")
                else:
                    fatura_ekle(
                        yil,
                        kaynak=kaynak_tek,
                        m3=m3_tek,
                        donem=donem_tek,
                        fatura_no="",
                    )
                    save_app_state()
                    st.success("Kayıt eklendi.")
                    st.rerun()

        faturalar = list_faturalar(yil)
        if faturalar:
            c_btn1, c_btn2, c_btn3 = st.columns(3)
            with c_btn1:
                if st.button("Çift faturaları temizle", key="kanit_dedupe"):
                    silinen = dedupe_faturalar(yil)
                    if silinen:
                        save_app_state()
                        st.success(f"{len(silinen)} çift kayıt silindi: {', '.join(silinen)}")
                        st.rerun()
                    else:
                        st.info("Çift kayıt bulunamadı.")
            with c_btn2:
                if st.button("Fatura toplamını mavi alanlara yaz", key="kanit_to_sebeke"):
                    # Widget key'leri bu run'da zaten oluştuğu için değeri
                    # bir sonraki run'ın başında uygula.
                    st.session_state["_apply_fatura_to_mavi"] = True
                    st.rerun()
            with c_btn3:
                st.caption(f"Kayıtlı fatura: **{len(faturalar)}** adet")

            st.markdown("**Kayıtlı faturalar**")
            df = pd.DataFrame(faturalar)
            goster = pd.DataFrame(
                {
                    "ID": df.get("id"),
                    "Kaynak": df.get("kaynak"),
                    "Fatura No": df.get("fatura_no"),
                    "Dönem": df.get("donem"),
                    "m³": df.get("m3"),
                    "Dosya": df.get("dosya_adi"),
                }
            )
            st.dataframe(goster, use_container_width=True, hide_index=True)
            st.caption(
                f"Fatura toplamı: **{sum(float(f.get('m3') or 0) for f in faturalar):,.2f} m³**"
                .replace(",", "X").replace(".", ",").replace("X", ".")
            )

            sil_id = st.selectbox(
                "Silinecek fatura",
                options=["—"] + [str(f.get("id")) for f in faturalar],
                key="kanit_sil_id",
            )
            if sil_id != "—" and st.button("Seçili faturayı sil", key="kanit_sil_btn"):
                if fatura_sil(yil, sil_id):
                    save_app_state()
                    st.success("Fatura silindi.")
                    st.rerun()
                else:
                    st.error("Silinemedi.")
        else:
            st.info("Bu yıl için henüz fatura kanıtı yok.")

        girilen_sebeke = float(st.session_state.get("mavi_sebeke", 0.0) or 0.0)
        sonuc_mavi = st.session_state.get("sonuc_mavi")
        if (
            st.session_state.get("hesaplandi")
            and sonuc_mavi is not None
            and abs(
                float(sonuc_mavi)
                - (
                    girilen_sebeke
                    + float(st.session_state.get("mavi_yeralti", 0) or 0)
                    + float(st.session_state.get("mavi_kaynak", 0) or 0)
                )
            )
            > 0.05
        ):
            st.warning(
                f"Son hesaplanan mavi su (**{float(sonuc_mavi):,.2f} m³**) ile "
                "şu anki girdiler uyuşmuyor. **Hesapla**'ya yeniden basın."
                .replace(",", "X").replace(".", ",").replace("X", ".")
            )

        cmp = karsilastir_mavi_su(
            yil,
            girilen_sebeke,
            st.session_state.get("mavi_yeralti", 0.0),
            st.session_state.get("mavi_kaynak", 0.0),
        )
        st.markdown("**Tutarlılık kontrolü**")
        st.dataframe(
            pd.DataFrame(cmp["satirlar"])[
                ["Kaynak", "Girilen (m³)", "Fatura Toplamı (m³)", "Fark (m³)", "Durum"]
            ],
            use_container_width=True,
            hide_index=True,
        )
        if not cmp["fatura_var"]:
            st.caption(cmp["ozet"])
        elif cmp["eslesme"]:
            st.success(cmp["ozet"])
        else:
            st.error(cmp["ozet"])
            for msg in cmp["uyari_mesajlari"]:
                st.warning(msg)


def render() -> None:
    st.markdown(
        '<p class="page-title">Veri Girişi</p>'
        '<p class="page-sub">Mavi, yeşil ve gri su verilerini girin; <strong>Hesapla</strong> ile sonuçları görün.</p>',
        unsafe_allow_html=True,
    )

    yil = _rapor_yili()
    st.caption(f"Raporlama yılı: **{yil}** (Firma Bilgileri’nden değişir)")

    # Widget'lardan ÖNCE: fatura toplamını şebeke alanlarına uygula
    if st.session_state.pop("_apply_fatura_to_mavi", None):
        toplamlar = fatura_toplamlari(yil)
        st.session_state["mavi_sebeke"] = float(toplamlar.get(KAYNAK_SEBEKE, 0.0))
        st.session_state["mavi_yeralti"] = float(toplamlar.get("Kuyu / Yeraltı", 0.0))
        st.session_state["mavi_kaynak"] = float(toplamlar.get("Kaynak Suları", 0.0))
        st.session_state["_fatura_to_mavi_ok"] = True

    if st.session_state.pop("_fatura_to_mavi_ok", None):
        st.success(
            "Şebeke / kuyu / kaynak alanlarına fatura toplamı yazıldı. "
            "Sonucu güncellemek için **Hesapla**'ya basın."
        )

    tab_mavi, tab_yesil, tab_gri = st.tabs(["Mavi Su", "Yeşil Su", "Gri Su"])

    with tab_mavi:
        st.markdown(
            '<span class="badge-blue">MAVİ SU</span>'
            '<p style="color:#5A6B7A;font-size:0.9rem;margin:0.65rem 0 0.35rem 0;">'
            "Şebeke + kuyu + kaynak = Mavi Su Ayak İzi.</p>"
            '<p class="unit-hint">Birim: m³ / yıl</p>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.number_input(
                    "Şebeke Suyu Tüketimi (m³)",
                    min_value=0.0,
                    step=10.0,
                    format="%.2f",
                    key="mavi_sebeke",
                )
            with c2:
                st.number_input(
                    "Yeraltı Suyu / Kuyu Çekimi (m³)",
                    min_value=0.0,
                    step=10.0,
                    format="%.2f",
                    key="mavi_yeralti",
                )
            with c3:
                st.number_input(
                    "Kaynak Suları (Damacana, bardak vb.) (m³)",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                    key="mavi_kaynak",
                )
        onizleme = hesapla_mavi_su(
            st.session_state.get("mavi_sebeke", 0.0),
            st.session_state.get("mavi_yeralti", 0.0),
            st.session_state.get("mavi_kaynak", 0.0),
        )
        st.caption(f"Önizleme — Mavi su toplamı: **{format_m3(onizleme, 'm³')}**")

        _render_mavi_kanit(yil)

    with tab_yesil:
        st.markdown(
            '<span class="badge-green">YEŞİL SU</span>'
            '<p style="color:#5A6B7A;font-size:0.9rem;margin:0.65rem 0 0.85rem 0;">'
            "Yağmur suyu kullanımı = Yeşil Su.</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="info-note"><strong>Sanayi tesisleri:</strong> Yalnızca proseste kullanılan / buharlaşan '
            "yıllık yağmur suyu miktarını giriniz.</div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            col, _ = st.columns([1, 1])
            with col:
                st.number_input(
                    "Proseste Kullanılan/Buharlaşan Yıllık Yağmur Suyu Miktarı (m³)",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                    key="yesil_yagmur",
                )

    with tab_gri:
        st.markdown(
            '<span class="badge-grey">GRİ SU</span>'
            '<p style="color:#5A6B7A;font-size:0.9rem;margin:0.65rem 0 0.85rem 0;">'
            "Atıksu debisi (V) ve parametre bazlı C<sub>eff</sub>, C<sub>max</sub>, C<sub>nat</sub>.</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="formula-note"><strong>Formül:</strong> '
            "Gri Su = V × (C<sub>eff</sub> − C<sub>nat</sub>) / (C<sub>max</sub> − C<sub>nat</sub>). "
            "En büyük sonuç kritik parametredir.</div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            col, _ = st.columns([1, 1])
            with col:
                st.number_input(
                    "Atıksu Debisi V (m³/yıl)",
                    min_value=0.0,
                    step=10.0,
                    format="%.2f",
                    key="gri_debi",
                )

        with st.container(border=True):
            st.markdown(
                '<div class="section-label">Kirlilik Parametreleri</div>',
                unsafe_allow_html=True,
            )
            edited = st.data_editor(
                st.session_state.gri_parametre_df,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Parametre": st.column_config.TextColumn("Parametre", required=True),
                    "C_eff (mg/L)": st.column_config.NumberColumn(
                        "C_eff (mg/L)", min_value=0.0, format="%.2f"
                    ),
                    "C_max (mg/L)": st.column_config.NumberColumn(
                        "C_max (mg/L)", min_value=0.0, format="%.2f"
                    ),
                    "C_nat (mg/L)": st.column_config.NumberColumn(
                        "C_nat (mg/L)", min_value=0.0, format="%.2f"
                    ),
                },
                key="gri_parametre_editor",
            )
            st.session_state["_gri_parametre_edited"] = edited

    st.divider()
    if st.button("Hesapla", type="primary", use_container_width=False):
        mavi = hesapla_mavi_su(
            st.session_state.get("mavi_sebeke", 0.0),
            st.session_state.get("mavi_yeralti", 0.0),
            st.session_state.get("mavi_kaynak", 0.0),
        )
        yesil = hesapla_yesil_su(st.session_state.get("yesil_yagmur", 0.0))
        df = st.session_state.get("_gri_parametre_edited", st.session_state.gri_parametre_df).copy()
        st.session_state.gri_parametre_df = df

        parametreler = []
        for _, row in df.iterrows():
            ad = row.get("Parametre")
            if pd.isna(ad) or str(ad).strip() == "":
                continue
            parametreler.append(
                {
                    "ad": str(ad).strip(),
                    "C_eff": row.get("C_eff (mg/L)", 0.0),
                    "C_max": row.get("C_max (mg/L)", 0.0),
                    "C_nat": row.get("C_nat (mg/L)", 0.0),
                }
            )

        V = float(st.session_state.get("gri_debi", 0.0))
        gri, kritik, detaylar, hatalar = hesapla_gri_su(V, parametreler)
        for h in hatalar:
            st.warning(h)

        kanit = karsilastir_mavi_su(
            yil,
            st.session_state.get("mavi_sebeke", 0.0),
            st.session_state.get("mavi_yeralti", 0.0),
            st.session_state.get("mavi_kaynak", 0.0),
        )
        st.session_state.mavi_kanit_ozet = ozet_payload(
            yil,
            st.session_state.get("mavi_sebeke", 0.0),
            st.session_state.get("mavi_yeralti", 0.0),
            st.session_state.get("mavi_kaynak", 0.0),
        )
        if kanit["fatura_var"] and not kanit["eslesme"]:
            st.error(kanit["ozet"])
            for msg in kanit["uyari_mesajlari"]:
                st.warning(msg)
        elif kanit["fatura_var"]:
            st.success(kanit["ozet"])

        if gri is None:
            st.error(
                "Gri su hesaplanamadı. C_max > C_nat ve geçerli parametreler girildiğinden emin olun."
            )
            st.session_state.hesaplandi = False
            st.session_state.sonuc_mavi = mavi
            st.session_state.sonuc_yesil = yesil
            st.session_state.sonuc_gri = None
            st.session_state.sonuc_toplam = None
            st.session_state.gri_kritik_parametre = None
            st.session_state.gri_parametre_sonuclari = None
        else:
            st.session_state.sonuc_mavi = mavi
            st.session_state.sonuc_yesil = yesil
            st.session_state.sonuc_gri = gri
            st.session_state.sonuc_toplam = mavi + yesil + gri
            st.session_state.gri_kritik_parametre = kritik
            st.session_state.gri_parametre_sonuclari = detaylar
            st.session_state.hesaplandi = True
            st.session_state.calc_snapshot = build_calc_snapshot()
            save_app_state()
            if V == 0:
                st.info("Atıksu debisi 0 — gri su ayak izi 0 kabul edildi.")
            st.success("Hesaplama tamamlandı.")

    if st.session_state.hesaplandi:
        st.markdown(
            '<div class="section-label">Hesaplama Sonuçları</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mavi Su", format_m3(st.session_state.sonuc_mavi, "m³"))
        c2.metric("Yeşil Su", format_m3(st.session_state.sonuc_yesil, "m³"))
        c3.metric("Gri Su", format_m3(st.session_state.sonuc_gri, "m³/yıl"))
        c4.metric("Genel Toplam", format_m3(st.session_state.sonuc_toplam, "m³/yıl"))
        if st.session_state.gri_parametre_sonuclari:
            with st.expander("Gri su parametre detayları"):
                st.dataframe(
                    pd.DataFrame(st.session_state.gri_parametre_sonuclari)[
                        ["Parametre", "C_eff", "C_max", "C_nat", "Gri Su (m³/yıl)"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
        kanit_ozet = st.session_state.get("mavi_kanit_ozet")
        if isinstance(kanit_ozet, dict) and kanit_ozet.get("fatura_var"):
            with st.expander("Mavi su fatura tutarlılığı"):
                if kanit_ozet.get("eslesme"):
                    st.success(kanit_ozet.get("ozet", ""))
                else:
                    st.error(kanit_ozet.get("ozet", ""))
                    for msg in kanit_ozet.get("uyari_mesajlari") or []:
                        st.warning(msg)
