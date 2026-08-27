"""
Word (.docx) su ayak izi raporu — PDF ile aynı yapı / içerik, düzenlenebilir.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

from services.logo_utils import header_logo_pair_mm
from services.report_utils import format_rapor_tarihi

ROOT = Path(__file__).resolve().parent.parent
LOGO_ADASO = ROOT / "logos" / "adaso_logo.png"

TEAL = "0D7377"
NAVY = "0B1F33"
GRAY_FILL = "F0F0F0"
YELLOW_FILL = "FFC000"
LIGHT_GRAY = "DCDCDC"
LIGHT_BLUE = "E8EEF3"

def _set_word_footer(section) -> None:
    """Alt bilgi: başlık + sayfa numarası."""
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.clear()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Kurumsal Su Ayak İzi Raporu   ·   Sayfa ")
    _set_run(run, size=8, color_hex="505050")
    run_pg = p.add_run()
    _set_run(run_pg, size=8, color_hex="505050")
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run_pg._r.append(fld_begin)
    run_pg._r.append(instr)
    run_pg._r.append(fld_end)


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _safe(text: Any) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return "-"
    return str(text)


def _set_cell_shading(cell, hex_color: str) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def _set_run(run, size=11, bold=False, color_hex: str | None = None) -> None:
    run.font.size = Pt(size)
    run.bold = bold
    run.font.name = "Arial"
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:ascii"), "Arial")
    rFonts.set(qn("w:hAnsi"), "Arial")
    rFonts.set(qn("w:eastAsia"), "Arial")
    if color_hex:
        run.font.color.rgb = RGBColor.from_string(color_hex)


def _banner(doc: Document, text: str) -> None:
    """PDF'deki teal dolu bölüm başlığı."""
    table = doc.add_table(rows=1, cols=1)
    table.autofit = True
    cell = table.rows[0].cells[0]
    _set_cell_shading(cell, TEAL)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    _set_run(run, size=14, bold=True, color_hex="FFFFFF")
    doc.add_paragraph()


def _subhead(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    _set_run(run, size=12, bold=True, color_hex=NAVY)


def _body(doc: Document, text: str, center: bool = False) -> None:
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    _set_run(run, size=11, bold=False)


def _body_bold(doc: Document, text: str, center: bool = False, size: int = 12) -> None:
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    _set_run(run, size=size, bold=True, color_hex=NAVY)


def _kv_table(doc: Document, rows: list[tuple[str, str]]) -> None:
    """PDF 1.1 kuruluş bilgileri tarzı: sol gri etiket, sağ değer."""
    table = doc.add_table(rows=len(rows), cols=2)
    table.style = "Table Grid"
    for i, (label, val) in enumerate(rows):
        c0, c1 = table.rows[i].cells
        _set_cell_shading(c0, GRAY_FILL)
        c0.text = ""
        c1.text = ""
        r0 = c0.paragraphs[0].add_run(label)
        r1 = c1.paragraphs[0].add_run(_safe(val))
        _set_run(r0, size=10, bold=True)
        _set_run(r1, size=10)
        c0.width = Cm(5.5)
        c1.width = Cm(11.5)
    doc.add_paragraph()


def _styled_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    header_fill: str = NAVY,
    header_font_white: bool = True,
    center: bool = True,
) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        _set_cell_shading(cell, header_fill)
        cell.text = ""
        p = cell.paragraphs[0]
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        _set_run(run, size=10, bold=True, color_hex="FFFFFF" if header_font_white else NAVY)
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            cell = table.rows[r_i + 1].cells[c_i]
            cell.text = ""
            p = cell.paragraphs[0]
            if center:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(_safe(val))
            _set_run(run, size=10)
    doc.add_paragraph()


def _as_df(obj: Any, columns: list[str]) -> pd.DataFrame:
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, list):
        return pd.DataFrame(obj) if obj else pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)


def generate_docx_bytes(data: dict[str, Any]) -> bytes:
    company_name = _safe(data.get("firma_adi"))
    address = _safe(data.get("lokasyon"))
    sector = _safe(data.get("sektor"))
    contact_person = _safe(data.get("yetkili"))
    email = _safe(data.get("email"))
    c_phone = _safe(data.get("telefon"))
    rapor_yili = _safe(data.get("rapor_yili") or "2026")
    rapor_tarihi_str = format_rapor_tarihi(data.get("rapor_tarihi"))
    current_year = rapor_yili

    res_blue = float(data.get("mavi_su") or 0.0)
    res_green = float(data.get("yesil_su") or 0.0)
    res_grey = float(data.get("gri_su") or 0.0)
    total_vol = float(data.get("toplam_su") or (res_blue + res_green + res_grey))
    kritik = _safe(data.get("gri_kritik") or "Belirtilmedi")

    duzenlenmis_sorumlular = _as_df(
        data.get("sorumlular"), ["Sorumlu Kişi", "Görev", "İletişim"]
    )
    sistem_siniri_tablosu = _as_df(
        data.get("sistem_siniri"),
        ["Bileşen", "Kaynak", "Veri Kaynağı", "Veri Doğrulama", "Açıklama (Diğer)"],
    )
    duzenlenmis_hedefler = _as_df(
        data.get("hedefler"), ["Hedef Yılı", "Hedef Açıklaması"]
    )

    veri_kalite = (data.get("veri_kalitesi") or "").strip() or (
        "Hesaplamalarda kullanılan su tüketim ve temin verileri, tesisin resmi kayıtları, "
        "sayaç okumaları ve fatura verilerinden derlenmiş olup, veri izlenebilirliği ve "
        "kalitesi ulusal/uluslararası standartlara uygundur."
    )

    doc = Document()
    kpi_data = data.get("kpi") or {}
    for sec in doc.sections:
        sec.top_margin = Cm(2.0)
        sec.bottom_margin = Cm(1.8)
        sec.left_margin = Cm(2.0)
        sec.right_margin = Cm(2.0)
        sec.different_first_page_header_footer = True
        sec.header_distance = Cm(0.4)
        sec.footer_distance = Cm(0.5)
        _set_word_footer(sec)

    # Firma logosu
    firma_logo = (data.get("logo_path") or "").strip()
    if firma_logo:
        firma_logo = str(Path(firma_logo).resolve())
    if not firma_logo or not Path(firma_logo).exists():
        data_logo = ROOT / "data" / "logos" / "firma_logo.png"
        if data_logo.exists():
            firma_logo = str(data_logo.resolve())
        else:
            firma_logo = ""

    # Sayfa 2+ header: sol ADASO, sağ firma (aynı yükseklik)
    adaso_size, firma_size = header_logo_pair_mm(LOGO_ADASO, firma_logo or None)
    adaso_w, adaso_h = adaso_size

    header = doc.sections[0].header
    header.is_linked_to_previous = False
    for p in header.paragraphs:
        p.clear()
    ht = header.add_table(rows=1, cols=2, width=Cm(17))
    ht.autofit = False
    left_cell, right_cell = ht.rows[0].cells
    left_cell.text = ""
    right_cell.text = ""
    lp = left_cell.paragraphs[0]
    lp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if LOGO_ADASO.exists() and adaso_h > 0:
        try:
            lp.add_run().add_picture(
                str(LOGO_ADASO.resolve()),
                width=Mm(adaso_w),
                height=Mm(adaso_h),
            )
        except Exception:
            run = lp.add_run("ADASO")
            _set_run(run, size=9, bold=True, color_hex=TEAL)
    rp = right_cell.paragraphs[0]
    rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if firma_size and firma_logo and Path(firma_logo).exists():
        firma_w, firma_h = firma_size
        if firma_h > 0:
            try:
                rp.add_run().add_picture(
                    firma_logo,
                    width=Mm(firma_w),
                    height=Mm(firma_h),
                )
            except Exception:
                pass

    # İlk sayfa (kapak) header boş kalsın
    first_header = doc.sections[0].first_page_header
    for p in first_header.paragraphs:
        p.clear()

    temp_files: list[str] = []

    try:
        # ----- Kapak (PDF ile aynı) -----
        cover = doc.add_table(rows=1, cols=1)
        cell = cover.rows[0].cells[0]
        _set_cell_shading(cell, TEAL)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("SU AYAK İZİ RAPORU")
        _set_run(run, size=24, bold=True, color_hex="FFFFFF")

        doc.add_paragraph()
        _body_bold(doc, f"{current_year} Dönemi", center=True, size=14)
        doc.add_paragraph()
        _body_bold(doc, company_name, center=True, size=16)

        logo_path = firma_logo
        if logo_path and Path(logo_path).exists():
            try:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run()
                run.add_picture(str(Path(logo_path).resolve()), width=Cm(7.5))
            except Exception:
                _body(doc, "[Logo eklenemedi]", center=True)
        else:
            doc.add_paragraph()
            doc.add_paragraph()

        doc.add_paragraph()
        _body(
            doc,
            f"Bu rapor, {company_name} için ISO 14046 çerçevesinde "
            "kurumsal su ayak izi hesaplama sonuçlarını içerir. "
            "Rapor yerel Kurumsal Su Ayak İzi Dashboard uygulaması ile üretilmiştir.",
            center=True,
        )
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("ISO 14046 çerçevesinde hazırlanmıştır")
        _set_run(run, size=10, bold=True, color_hex=TEAL)

        doc.add_page_break()

        # ----- İçindekiler -----
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("İÇİNDEKİLER")
        _set_run(run, size=16, bold=True, color_hex=NAVY)
        doc.add_paragraph()

        toc = [
            ("1. GİRİŞ", [
                "1.1. Kuruluş Bilgileri",
                "1.2. Tanımlar",
                "1.3. Kuruluş Su Yönetimi ve Sorumlular",
                "1.4. Amaç ve Kapsam",
                "1.5. Hedef Kullanıcı",
                "1.6. ISO 14046:2014 Uygunluk Açıklaması",
            ]),
            ("2. GENEL", [
                "2.1. Raporun Sahibi Olan Kuruluş ve Raporlama Dönemi",
                "2.2. Operasyonel Sınırlar",
            ]),
            ("3. METODOLOJİ", ["3.1. Veri Kalitesi", "3.2. Kabuller", "3.3. Mavi Su Kanıt Belgeleri"]),
            ("4. HESAPLAMALAR", [
                "4.1. Mavi Su Ayak İzi Hesaplamaları",
                "4.2. Yeşil Su Ayak İzi Hesaplamaları",
                "4.3. Gri Su Ayak İzi Hesaplamaları",
            ]),
            ("5. SONUÇ", []),
            ("6. SÜRDÜRÜLEBİLİRLİK HEDEFLERİ", []),
        ]
        if kpi_data.get("spesifik_su") is not None:
            toc.append(("7. PERFORMANS GÖSTERGELERİ (KPI)", []))
        for title, children in toc:
            _subhead(doc, title)
            for ch in children:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.75)
                run = p.add_run(ch)
                _set_run(run, size=11)

        doc.add_page_break()

        # ----- 1. GİRİŞ -----
        _banner(doc, "1. GİRİŞ")
        _subhead(doc, "1.1. Kuruluş Bilgileri")
        adres_txt = address[:80] + ("..." if len(address) > 80 else "")
        _kv_table(
            doc,
            [
                ("Kuruluş Adı", company_name),
                ("Tesis Adresi", adres_txt),
                ("Tesis Sektörü", sector),
                ("İletişim (Tel / E-Mail)", f"{c_phone} / {email}"),
                ("Rapordan Sorumlu Kişi", contact_person),
                ("Raporlama Yılı", rapor_yili),
                ("Rapor Tarihi", rapor_tarihi_str),
            ],
        )

        _subhead(doc, "1.2. Tanımlar")
        _body(
            doc,
            "Mavi Su Ayak İzi: Doğrudan su kaynaklarından (akarsular, göller, yeraltı suyu) "
            "kullanılan su miktarını ifade eder. Suyun bir ürüne, hizmete veya süreçlere dahil "
            "edilmesi sırasında yapılan su çekimini temsil eder.",
        )
        _body(
            doc,
            "Yeşil Su Ayak İzi: Yağış kaynaklı suyun proses veya buharlaşma yoluyla "
            "kullanımını ifade eder.",
        )
        _body(
            doc,
            "Gri Su Ayak İzi: Kirliliği mevcut su kalitesi standartlarına seyreltmek için "
            "gereken tatlı su hacmidir.",
        )

        _subhead(doc, "1.3. Kuruluş Su Yönetimi ve Sorumlular")
        _body(
            doc,
            f"{company_name} olarak raporlama yılında mavi su kapsamında şebeke, kuyu ve "
            "kaynak suları; yeşil su kapsamında yağmur suyu kullanımı; gri su kapsamında "
            "atıksu deşarjı ve kirletici parametreleri değerlendirilmiştir.",
        )
        _body_bold(doc, "Tablo 1: Sorumlu Kişilerin İletişim Bilgileri", size=11)
        s_rows = []
        for _, row in duzenlenmis_sorumlular.iterrows():
            if str(row.get("Görev", "")).strip() == "" and str(row.get("Sorumlu Kişi", "")).strip() == "":
                continue
            s_rows.append([
                _safe(row.get("Sorumlu Kişi")),
                _safe(row.get("Görev")),
                _safe(row.get("İletişim")),
            ])
        if s_rows:
            _styled_table(doc, ["Sorumlu Kişi", "Görev", "İletişim"], s_rows, header_fill=NAVY)
        else:
            _body(doc, "(Sorumlu kişi kaydı bulunmamaktadır.)")

        _subhead(doc, "1.4. Amaç ve Kapsam")
        _body(
            doc,
            f"{company_name} bünyesinde su kullanımı ve su güvenliği hedeflerine ulaşmak "
            f"amacıyla bu rapor hazırlanmıştır. Raporun amacı; {current_year} yılı su "
            "kullanımı ve deşarjına dair hesaplamaların doğrulanması ve şeffaf bir süreç "
            "oluşturulmasıdır.",
        )

        _subhead(doc, "1.5. Hedef Kullanıcı")
        _body(
            doc,
            "Hedef kullanıcılar: üst yönetim, çalışanlar, tedarikçiler ve diğer paydaşlardır. "
            "Rapor, resmi kurum talepleri, sürdürülebilirlik raporlaması ve ilgili "
            "organizasyon taleplerinde kullanılabilir.",
        )

        _subhead(doc, "1.6. Raporun ISO 14046:2014'e Uygunluğuna Dair Açıklama")
        _body(
            doc,
            "Bu rapor, ISO 14046:2014 Water Footprint ilkeleri referans alınarak "
            "hazırlanmıştır. Mavi su ayak izi bu sürümde brüt çekim (şebeke + kuyu + kaynak) "
            "olarak hesaplanır; gri su Hoekstra formülü ile kritik parametre üzerinden "
            "hesaplanır. Rapor bir uygunluk belgesi / sertifika niteliği taşımaz.",
        )

        # ----- 2. GENEL -----
        _banner(doc, "2. GENEL")
        _subhead(doc, "2.1. Raporun Sahibi Olan Kuruluş ve Raporlama Dönemi")
        _body(
            doc,
            f"Raporun sahibi {company_name} olup, rapor 01 Ocak {current_year} - "
            f"31 Aralık {current_year} tarih aralığı için hazırlanmıştır.",
        )
        _subhead(doc, "2.2. Operasyonel Sınırlar")
        _body(
            doc,
            f"Kuruluş bilgilerinde belirtilen adresteki operasyonlar sistem sınırına "
            f"dahildir. {company_name} faaliyetlerinden kaynaklanan su kullanım ve "
            "deşarjının %100'ü hesaplamalara dahil edilmiştir. Bu çalışmada kapıdan "
            "kapıya (Gate-to-Gate) yaklaşımı uygulanmıştır.",
        )

        doc.add_page_break()

        # ----- 3. METODOLOJİ -----
        _banner(doc, "3. METODOLOJİ")
        _subhead(doc, "3.1. Veri Kalitesi")
        _body(doc, veri_kalite)
        _subhead(doc, "3.2. Kabuller")
        _body(
            doc,
            "Gri su ayak izi hesaplarında, parametre bazlı sonuçlar arasından en yüksek "
            f"hacmi veren kritik kirletici ({kritik}) esas alınmıştır. "
            "Formül: V × (C_eff − C_nat) / (C_max − C_nat).",
        )

        kanit = data.get("mavi_kanit") or {}
        _subhead(doc, "3.3. Mavi Su Kanıt Belgeleri (Su Faturaları)")
        if kanit.get("fatura_var"):
            durum = "uyumlu" if kanit.get("eslesme") else "uyumsuz — kontrol gerekli"
            _body(
                doc,
                f"Raporlama yılı {kanit.get('yil', rapor_yili)} için "
                f"{int(kanit.get('fatura_adedi') or 0)} adet su faturası kanıt olarak kaydedilmiştir. "
                f"Fatura toplamı: {_fmt(kanit.get('fatura_toplam_m3'))} m³; "
                f"sisteme girilen mavi su: {_fmt(kanit.get('girilen_toplam_m3'))} m³ "
                f"(durum: {durum}). {_safe(kanit.get('ozet'))}",
            )
            for msg in kanit.get("uyari_mesajlari") or []:
                _body(doc, f"• {_safe(msg)}")
            fat_rows = []
            for frow in (kanit.get("faturalar") or [])[:20]:
                fat_rows.append([
                    _safe(frow.get("kaynak")),
                    _safe(frow.get("fatura_no")),
                    _safe(frow.get("donem")),
                    _fmt(frow.get("m3")),
                    _safe(frow.get("dosya_adi")) or "—",
                ])
            if fat_rows:
                _styled_table(
                    doc,
                    ["Kaynak", "Fatura No", "Dönem", "m³", "Dosya"],
                    fat_rows,
                    header_fill=TEAL,
                )
        else:
            _body(
                doc,
                "Bu rapor döneminde mavi su için sisteme yüklenmiş fatura kanıtı bulunmamaktadır. "
                "İzlenebilirlik için su faturalarının Veri Girişi ekranından eklenmesi önerilir.",
            )

        _body_bold(doc, "Tablo 2: Genel Akış - Sistem Sınırı", size=11)
        diger_gerekli = False
        for _, row in sistem_siniri_tablosu.iterrows():
            aciklama = str(row.get("Açıklama (Diğer)", "")).strip()
            if aciklama not in ("", "-", "nan", "None"):
                diger_gerekli = True
                break

        sys_rows = []
        for _, row in sistem_siniri_tablosu.iterrows():
            bilesen = _safe(row.get("Bileşen"))
            kaynak = _safe(row.get("Kaynak"))
            if bilesen == "-" and kaynak == "-":
                continue
            aciklama = str(row.get("Açıklama (Diğer)", "-")).strip()
            if aciklama in ("", "nan", "None"):
                aciklama = "-"
            if diger_gerekli:
                sys_rows.append([
                    bilesen,
                    kaynak,
                    _safe(row.get("Veri Kaynağı")),
                    _safe(row.get("Veri Doğrulama")),
                    aciklama,
                ])
            else:
                sys_rows.append([
                    bilesen,
                    kaynak,
                    _safe(row.get("Veri Kaynağı")),
                    _safe(row.get("Veri Doğrulama")),
                ])

        if sys_rows:
            if diger_gerekli:
                _styled_table(
                    doc,
                    ["Bileşen", "Kaynak", "Veri Kaynağı", "Veri Doğrulama", "Açıklama (Diğer)"],
                    sys_rows,
                    header_fill=YELLOW_FILL,
                    header_font_white=False,
                )
            else:
                _styled_table(
                    doc,
                    ["Bileşen", "Kaynak", "Veri Kaynağı", "Veri Doğrulama"],
                    sys_rows,
                    header_fill=YELLOW_FILL,
                    header_font_white=False,
                )
        else:
            _body(doc, "(Sistem sınırı tablosu boş.)")

        # ----- 4. HESAPLAMALAR -----
        _banner(doc, "4. HESAPLAMALAR")

        _subhead(doc, "4.1. Mavi Su Ayak İzi Hesaplamaları")
        _body(
            doc,
            "Şebeke, kuyu ve kaynak suları toplamı olarak hesaplanmıştır. "
            f"Şebeke: {_fmt(data.get('mavi_sebeke'))} m³/yıl · "
            f"Kuyu: {_fmt(data.get('mavi_yeralti'))} m³/yıl · "
            f"Kaynak: {_fmt(data.get('mavi_kaynak'))} m³/yıl.",
        )
        _styled_table(
            doc,
            ["Veri Kaynağı", "Toplam Tüketim (m³/yıl)"],
            [["Tesis Mavi Su Ayak İzi Hacmi", _fmt(res_blue)]],
            header_fill=LIGHT_GRAY,
            header_font_white=False,
        )

        _subhead(doc, "4.2. Yeşil Su Ayak İzi Hesaplamaları")
        _body(
            doc,
            "Proseste kullanılan / buharlaşan yağmur suyu miktarıdır. "
            f"Girilen değer: {_fmt(data.get('yesil_yagmur'))} m³/yıl.",
        )
        _styled_table(
            doc,
            ["Veri Kaynağı", "Toplam Tüketim (m³/yıl)"],
            [["Tesis Yeşil Su Ayak İzi Hacmi", _fmt(res_green)]],
            header_fill=LIGHT_GRAY,
            header_font_white=False,
        )

        _subhead(doc, "4.3. Gri Su Ayak İzi Hesaplamaları")
        _body(
            doc,
            "Atıksu debisi ve kirletici parametrelerine göre hesaplanmıştır. "
            f"Kritik parametre: {kritik}.",
        )
        _styled_table(
            doc,
            ["Bileşen / Kritik Kirletici", "Gereken Seyreltme Hacmi (m³/yıl)"],
            [[f"Endüstriyel Atıksu ({kritik})", _fmt(res_grey)]],
            header_fill=LIGHT_GRAY,
            header_font_white=False,
        )

        detay = data.get("gri_detay") or []
        if detay:
            _body_bold(doc, "Parametre Detayları", size=10)
            drows = [
                [
                    _safe(d.get("Parametre")),
                    _fmt(d.get("C_eff")),
                    _fmt(d.get("C_max")),
                    _fmt(d.get("C_nat")),
                    _fmt(d.get("Gri Su (m³/yıl)")),
                ]
                for d in detay
            ]
            _styled_table(
                doc,
                ["Parametre", "C_eff", "C_max", "C_nat", "Gri Su"],
                drows,
                header_fill=LIGHT_BLUE,
                header_font_white=False,
            )

        doc.add_page_break()

        # ----- 5. SONUÇ -----
        _banner(doc, "5. SONUÇ")
        _body_bold(doc, f"Toplam Tesis Su Ayak İzi: {_fmt(total_vol)} m³/yıl", size=12)

        p_blue = (res_blue / total_vol) * 100 if total_vol > 0 else 0
        p_green = (res_green / total_vol) * 100 if total_vol > 0 else 0
        p_grey = (res_grey / total_vol) * 100 if total_vol > 0 else 0
        _styled_table(
            doc,
            ["Bileşen", "Hacim (m³/yıl)", "Dağılım (%)"],
            [
                ["Mavi Su", _fmt(res_blue), f"% {p_blue:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")],
                ["Yeşil Su", _fmt(res_green), f"% {p_green:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")],
                ["Gri Su", _fmt(res_grey), f"% {p_grey:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")],
                ["TOPLAM", _fmt(total_vol), "% 100"],
            ],
            header_fill=NAVY,
        )

        if total_vol > 0:
            etiketler = ["Mavi Su", "Yeşil Su", "Gri Su"]
            degerler = [res_blue, res_green, res_grey]
            renkler = ["#A8D5E5", "#B8DDB5", "#D5D0E0"]
            fig, ax = plt.subplots(figsize=(6, 4), dpi=120)
            ax.pie(
                degerler,
                labels=etiketler,
                autopct="%1.1f%%",
                startangle=90,
                colors=renkler,
                textprops={"fontsize": 10, "weight": "bold"},
                pctdistance=0.8,
                wedgeprops=dict(width=0.35, edgecolor="w"),
            )
            ax.axis("equal")
            ax.set_title("Toplam Su Ayak İzi Bileşimi", fontsize=12, fontweight="bold", pad=16)
            ax.text(
                0, 0, f"TOPLAM:\n{_fmt(total_vol)} m³",
                ha="center", va="center", fontsize=11, fontweight="bold",
            )
            grafik_yolu = os.path.join(tempfile.gettempdir(), "su_ayak_izi_pie_docx.png")
            fig.savefig(grafik_yolu, format="png", dpi=200, bbox_inches="tight")
            plt.close(fig)
            temp_files.append(grafik_yolu)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(grafik_yolu, width=Cm(14))

        # ----- 6. HEDEFLER -----
        gecerli = [
            row
            for _, row in duzenlenmis_hedefler.iterrows()
            if str(row.get("Hedef Açıklaması", "")).strip()
        ]
        if gecerli:
            _banner(doc, "6. SÜRDÜRÜLEBİLİRLİK HEDEFLERİ")
            for hedef in gecerli:
                yil = _safe(hedef.get("Hedef Yılı"))
                acik = _safe(hedef.get("Hedef Açıklaması"))
                _body(doc, f"• {yil} Yılı Hedefi: {acik}")

        kpi = data.get("kpi") or {}
        if kpi.get("spesifik_su") is not None:
            _banner(doc, "7. PERFORMANS GÖSTERGELERİ (KPI)")
            birim = kpi.get("uretim_birimi", "ton")
            _body(doc, f"Spesifik su tüketimi: {_fmt(kpi.get('spesifik_su'))} m³/{birim}")
            _body(doc, f"Spesifik atıksu: {_fmt(kpi.get('spesifik_atiksu'))} m³/{birim}")
            _body(doc, f"Spesifik evsel su: {_fmt(kpi.get('evsel_su'))} L/kişi.gün")
            _body(doc, f"Spesifik evsel atıksu: {_fmt(kpi.get('evsel_atiksu'))} L/kişi.gün")

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        for p in temp_files:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
