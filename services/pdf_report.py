"""
Profesyonel kurumsal su ayak izi PDF raporu
(Eski vodaX / ISO 14046 rapor şablonuna dayalı, yerel sürüm).
"""

from __future__ import annotations

import os
import tempfile
import textwrap
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF

from services.logo_utils import header_logo_pair_mm
from services.report_utils import format_rapor_tarihi

ROOT = Path(__file__).resolve().parent.parent
LOCAL_FONT_REG = ROOT / "fonts" / "arial.ttf"
LOCAL_FONT_BOLD = ROOT / "fonts" / "arialbd.ttf"
WIN_FONT_REG = Path(r"C:\Windows\Fonts\arial.ttf")
WIN_FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
LOGO_ADASO = ROOT / "logos" / "adaso_logo.png"

HEADER_TOP_Y = 8.0
HEADER_LINE_Y = 21.0
PAGE_W_MM = 210.0
MARGIN_LR = 10.0


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _safe(text: Any) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return "-"
    return str(text)


def _resolve_fonts() -> tuple[str | None, str | None]:
    if LOCAL_FONT_REG.exists() and LOCAL_FONT_BOLD.exists():
        return str(LOCAL_FONT_REG), str(LOCAL_FONT_BOLD)
    if WIN_FONT_REG.exists() and WIN_FONT_BOLD.exists():
        return str(WIN_FONT_REG), str(WIN_FONT_BOLD)
    return None, None


class ProfessionalPDF(FPDF):
    def __init__(self, font_name: str = "Helvetica", firma_logo_path: str | None = None):
        super().__init__()
        self._font_name = font_name
        self._firma_logo_path = (firma_logo_path or "").strip() or None

    def header(self) -> None:
        # Kapak (sayfa 1) hariç tüm sayfalar
        if self.page_no() <= 1:
            return
        self.set_line_width(0.8)
        self.set_draw_color(13, 115, 119)
        self.line(MARGIN_LR, HEADER_LINE_Y, PAGE_W_MM - MARGIN_LR, HEADER_LINE_Y)

        adaso_size, firma_size = header_logo_pair_mm(
            LOGO_ADASO,
            self._firma_logo_path,
        )

        # Sol üst: ADASO
        adaso_w, adaso_h = adaso_size
        if adaso_h > 0:
            try:
                self.image(
                    str(LOGO_ADASO.resolve()),
                    x=MARGIN_LR + 2,
                    y=HEADER_TOP_Y,
                    w=adaso_w,
                    h=adaso_h,
                )
            except Exception:
                pass

        # Sağ üst: firma — ADASO ile aynı yükseklik, sağa hizalı
        if firma_size and self._firma_logo_path:
            firma_w, firma_h = firma_size
            if firma_h > 0:
                try:
                    firma_x = PAGE_W_MM - MARGIN_LR - firma_w
                    self.image(
                        str(Path(self._firma_logo_path).resolve()),
                        x=firma_x,
                        y=HEADER_TOP_Y,
                        w=firma_w,
                        h=firma_h,
                    )
                except Exception:
                    pass

        self.set_y(HEADER_LINE_Y + 4)

    def footer(self) -> None:
        self.set_y(-20)
        self.set_font(self._font_name, "", 8)
        self.set_text_color(80, 80, 80)
        self.cell(100, 10, txt="Kurumsal Su Ayak İzi Raporu", ln=False, align="L")
        self.cell(90, 10, txt=f"Sayfa {self.page_no()}/{{nb}}", ln=False, align="R")


def generate_pdf_bytes(data: dict[str, Any]) -> bytes:
    """data: firma + sonuç + tablolar içeren sözlük."""
    company_name = _safe(data.get("firma_adi"))
    address = _safe(data.get("lokasyon"))
    sector = _safe(data.get("sektor"))
    contact_person = _safe(data.get("yetkili"))
    email = _safe(data.get("email"))
    c_phone = _safe(data.get("telefon"))
    rapor_yili = _safe(data.get("rapor_yili") or "2026")
    rapor_tarihi_str = format_rapor_tarihi(data.get("rapor_tarihi"))

    res_blue = float(data.get("mavi_su") or 0.0)
    res_green = float(data.get("yesil_su") or 0.0)
    res_grey = float(data.get("gri_su") or 0.0)
    total_vol = float(data.get("toplam_su") or (res_blue + res_green + res_grey))
    kritik = _safe(data.get("gri_kritik") or "Belirtilmedi")

    sorumlular = data.get("sorumlular")
    if isinstance(sorumlular, list):
        duzenlenmis_sorumlular = pd.DataFrame(sorumlular)
    elif isinstance(sorumlular, pd.DataFrame):
        duzenlenmis_sorumlular = sorumlular
    else:
        duzenlenmis_sorumlular = pd.DataFrame(columns=["Sorumlu Kişi", "Görev", "İletişim"])

    sistem = data.get("sistem_siniri")
    if isinstance(sistem, list):
        sistem_siniri_tablosu = pd.DataFrame(sistem)
    elif isinstance(sistem, pd.DataFrame):
        sistem_siniri_tablosu = sistem
    else:
        sistem_siniri_tablosu = pd.DataFrame(
            columns=["Bileşen", "Kaynak", "Veri Kaynağı", "Veri Doğrulama", "Açıklama (Diğer)"]
        )

    hedefler = data.get("hedefler")
    if isinstance(hedefler, list):
        duzenlenmis_hedefler = pd.DataFrame(hedefler)
    elif isinstance(hedefler, pd.DataFrame):
        duzenlenmis_hedefler = hedefler
    else:
        duzenlenmis_hedefler = pd.DataFrame(columns=["Hedef Yılı", "Hedef Açıklaması"])

    veri_kalite = (data.get("veri_kalitesi") or "").strip()
    if not veri_kalite:
        veri_kalite = (
            "Hesaplamalarda kullanılan su tüketim ve temin verileri, tesisin resmi kayıtları, "
            "sayaç okumaları ve fatura verilerinden derlenmiş olup, veri izlenebilirliği ve "
            "kalitesi ulusal/uluslararası standartlara uygundur."
        )

    font_reg, font_bold = _resolve_fonts()

    # Firma logosu yolu (kapak ortası + sonraki sayfa sağ üst)
    firma_logo = (data.get("logo_path") or "").strip()
    if firma_logo:
        firma_logo = str(Path(firma_logo).resolve())
    if not firma_logo or not Path(firma_logo).exists():
        # Yalnızca kullanıcının yüklediği logo (örnek/demo logo yok)
        data_logo = ROOT / "data" / "logos" / "firma_logo.png"
        firma_logo = str(data_logo.resolve()) if data_logo.exists() else ""

    pdf = ProfessionalPDF(firma_logo_path=firma_logo or None)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    # Üst boşluk: header logoları için; kapakta header yok ama içerik yine üstten başlar
    pdf.set_margins(left=10, top=12, right=10)

    if font_reg and font_bold:
        pdf.add_font("ArialTR", style="", fname=font_reg, uni=True)
        pdf.add_font("ArialTR", style="B", fname=font_bold, uni=True)
        f = "ArialTR"
    else:
        f = "Helvetica"
    pdf._font_name = f

    current_year = rapor_yili
    temp_files: list[str] = []

    try:
        # ----- Kapak -----
        pdf.add_page()
        pdf.set_font(f, size=24, style="B")
        pdf.set_fill_color(13, 115, 119)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 20, txt="SU AYAK İZİ RAPORU", ln=True, align="C", fill=True)

        pdf.set_text_color(0, 0, 0)
        pdf.ln(10)
        pdf.set_font(f, size=14, style="B")
        pdf.cell(190, 10, txt=f"{current_year} Dönemi", ln=True, align="C")

        pdf.ln(12)
        pdf.set_font(f, size=16, style="B")
        pdf.set_text_color(11, 31, 51)
        pdf.multi_cell(190, 9, txt=company_name, align="C")

        # Kapak ortası: firmanın yüklediği logo
        logo_path = firma_logo
        if logo_path:
            try:
                logo_w = 80
                logo_x = (210 - logo_w) / 2
                logo_y = 100
                pdf.image(logo_path, x=logo_x, y=logo_y, w=logo_w)
            except Exception as logo_err:
                pdf.set_y(120)
                pdf.set_font(f, size=9, style="")
                pdf.set_text_color(180, 80, 80)
                pdf.cell(190, 6, txt=f"[Logo eklenemedi: {logo_err}]", ln=True, align="C")
                pdf.set_text_color(0, 0, 0)

        pdf.set_y(205)
        pdf.set_font(f, size=11, style="")
        pdf.set_text_color(90, 107, 122)
        pdf.multi_cell(
            190,
            6,
            txt=(
                f"Bu rapor, {company_name} için ISO 14046 çerçevesinde "
                "kurumsal su ayak izi hesaplama sonuçlarını içerir. "
                "Rapor yerel Kurumsal Su Ayak İzi Dashboard uygulaması ile üretilmiştir."
            ),
            align="C",
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(8)
        pdf.set_font(f, size=10, style="B")
        pdf.set_text_color(13, 115, 119)
        pdf.cell(190, 8, txt="ISO 14046 çerçevesinde hazırlanmıştır", ln=True, align="C")
        pdf.set_text_color(0, 0, 0)

        # ----- İçindekiler -----
        pdf.add_page()
        pdf.set_font(f, size=16, style="B")
        pdf.cell(190, 10, txt="İÇİNDEKİLER", ln=True, align="C")
        pdf.ln(8)

        kpi_data = data.get("kpi") or {}
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
            pdf.set_font(f, size=12, style="B")
            pdf.cell(190, 8, txt=title, ln=True)
            pdf.set_font(f, size=11, style="")
            for ch in children:
                pdf.cell(10, 6, txt="")
                pdf.cell(180, 6, txt=ch, ln=True)
            pdf.ln(2)

        # ----- 1. Giriş -----
        pdf.add_page()
        pdf.set_fill_color(13, 115, 119)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(f, size=14, style="B")
        pdf.cell(190, 10, txt="1. GİRİŞ", ln=True, align="L", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="1.1. Kuruluş Bilgileri", ln=True)
        pdf.set_font(f, size=10, style="")
        pdf.set_fill_color(240, 240, 240)

        rows_info = [
            ("Kuruluş Adı", company_name),
            ("Tesis Adresi", (address[:80] + ("..." if len(address) > 80 else ""))),
            ("Tesis Sektörü", sector),
            ("İletişim (Tel / E-Mail)", f"{c_phone} / {email}"),
            ("Rapordan Sorumlu Kişi", contact_person),
            ("Raporlama Yılı", rapor_yili),
            ("Rapor Tarihi", rapor_tarihi_str),
        ]
        for label, val in rows_info:
            pdf.cell(60, 8, txt=label, border=1, fill=True)
            pdf.cell(130, 8, txt=_safe(val), border=1, ln=True)

        pdf.ln(8)
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="1.2. Tanımlar", ln=True)
        pdf.set_font(f, size=11, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                "Mavi Su Ayak İzi: Doğrudan su kaynaklarından (akarsular, göller, yeraltı suyu) "
                "kullanılan su miktarını ifade eder.\n\n"
                "Yeşil Su Ayak İzi: Yağış kaynaklı suyun proses veya buharlaşma yoluyla "
                "kullanımını ifade eder.\n\n"
                "Gri Su Ayak İzi: Kirliliği mevcut su kalitesi standartlarına seyreltmek için "
                "gereken tatlı su hacmidir."
            ),
        )

        pdf.ln(6)
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="1.3. Kuruluş Su Yönetimi ve Sorumlular", ln=True)
        pdf.set_font(f, size=11, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                f"{company_name} olarak raporlama yılında mavi su kapsamında şebeke, kuyu ve "
                "kaynak suları; yeşil su kapsamında yağmur suyu kullanımı; gri su kapsamında "
                "atıksu deşarjı ve kirletici parametreleri değerlendirilmiştir."
            ),
        )

        pdf.ln(4)
        pdf.set_font(f, size=11, style="B")
        pdf.cell(190, 8, txt="Tablo 1: Sorumlu Kişilerin İletişim Bilgileri", ln=True)
        pdf.set_font(f, size=10, style="B")
        pdf.set_fill_color(11, 31, 51)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(60, 8, txt="Sorumlu Kişi", border=1, fill=True, align="C")
        pdf.cell(80, 8, txt="Görev", border=1, fill=True, align="C")
        pdf.cell(50, 8, txt="İletişim", border=1, ln=True, fill=True, align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font(f, size=10, style="")
        try:
            for _, row in duzenlenmis_sorumlular.iterrows():
                if str(row.get("Görev", "")).strip() == "" and str(row.get("Sorumlu Kişi", "")).strip() == "":
                    continue
                pdf.cell(60, 8, txt=_safe(row.get("Sorumlu Kişi"))[:30], border=1, align="C")
                pdf.cell(80, 8, txt=_safe(row.get("Görev"))[:45], border=1, align="C")
                pdf.cell(50, 8, txt=_safe(row.get("İletişim"))[:25], border=1, ln=True, align="C")
        except Exception:
            pass

        pdf.add_page()
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="1.4. Amaç ve Kapsam", ln=True)
        pdf.set_font(f, size=11, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                f"{company_name} bünyesinde su kullanımı ve su güvenliği hedeflerine ulaşmak "
                f"amacıyla bu rapor hazırlanmıştır. Raporun amacı; {current_year} yılı su "
                "kullanımı ve deşarjına dair hesaplamaların doğrulanması ve şeffaf bir süreç "
                "oluşturulmasıdır."
            ),
        )

        pdf.ln(4)
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="1.5. Hedef Kullanıcı", ln=True)
        pdf.set_font(f, size=11, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                "Hedef kullanıcılar: üst yönetim, çalışanlar, tedarikçiler ve diğer paydaşlardır. "
                "Rapor, resmi kurum talepleri, sürdürülebilirlik raporlaması ve ilgili "
                "organizasyon taleplerinde kullanılabilir."
            ),
        )

        pdf.ln(4)
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="1.6. Raporun ISO 14046:2014'e Uygunluğuna Dair Açıklama", ln=True)
        pdf.set_font(f, size=11, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                "Bu rapor, ISO 14046:2014 Water Footprint ilkeleri referans alınarak "
                "hazırlanmıştır. Mavi su ayak izi bu sürümde brüt çekim (şebeke + kuyu + kaynak) "
                "olarak hesaplanır; gri su Hoekstra formülü ile kritik parametre üzerinden "
                "hesaplanır. Rapor bir uygunluk belgesi / sertifika niteliği taşımaz."
            ),
        )

        # ----- 2. Genel -----
        pdf.ln(6)
        pdf.set_fill_color(13, 115, 119)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(f, size=14, style="B")
        pdf.cell(190, 10, txt="2. GENEL", ln=True, align="L", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="2.1. Raporun Sahibi Olan Kuruluş ve Raporlama Dönemi", ln=True)
        pdf.set_font(f, size=11, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                f"Raporun sahibi {company_name} olup, rapor 01 Ocak {current_year} - "
                f"31 Aralık {current_year} tarih aralığı için hazırlanmıştır."
            ),
        )

        pdf.ln(4)
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="2.2. Operasyonel Sınırlar", ln=True)
        pdf.set_font(f, size=11, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                f"Kuruluş bilgilerinde belirtilen adresteki operasyonlar sistem sınırına "
                f"dahildir. {company_name} faaliyetlerinden kaynaklanan su kullanım ve "
                "deşarjının %100'ü hesaplamalara dahil edilmiştir. Bu çalışmada kapıdan "
                "kapıya (Gate-to-Gate) yaklaşımı uygulanmıştır."
            ),
        )

        # ----- 3. Metodoloji -----
        pdf.add_page()
        pdf.set_fill_color(13, 115, 119)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(f, size=14, style="B")
        pdf.cell(190, 10, txt="3. METODOLOJİ", ln=True, align="L", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="3.1. Veri Kalitesi", ln=True)
        pdf.set_font(f, size=11, style="")
        pdf.multi_cell(190, 6, txt=veri_kalite)

        pdf.ln(3)
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="3.2. Kabuller", ln=True)
        pdf.set_font(f, size=11, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                "Gri su ayak izi hesaplarında, parametre bazlı sonuçlar arasından en yüksek "
                f"hacmi veren kritik kirletici ({kritik}) esas alınmıştır. "
                "Formül: V × (C_eff − C_nat) / (C_max − C_nat)."
            ),
        )

        # 3.3 Mavi su kanıt
        kanit = data.get("mavi_kanit") or {}
        pdf.ln(3)
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="3.3. Mavi Su Kanıt Belgeleri (Su Faturaları)", ln=True)
        pdf.set_font(f, size=11, style="")
        if kanit.get("fatura_var"):
            durum = "uyumlu" if kanit.get("eslesme") else "uyumsuz — kontrol gerekli"
            pdf.multi_cell(
                190,
                6,
                txt=(
                    f"Raporlama yılı {kanit.get('yil', rapor_yili)} için "
                    f"{int(kanit.get('fatura_adedi') or 0)} adet su faturası kanıt olarak kaydedilmiştir. "
                    f"Fatura toplamı: {_fmt(kanit.get('fatura_toplam_m3'))} m³; "
                    f"sisteme girilen mavi su: {_fmt(kanit.get('girilen_toplam_m3'))} m³ "
                    f"(durum: {durum}). "
                    f"{_safe(kanit.get('ozet'))}"
                ),
            )
            for msg in (kanit.get("uyari_mesajlari") or [])[:5]:
                pdf.set_text_color(180, 80, 0)
                pdf.multi_cell(190, 5, txt=f"• {_safe(msg)}")
                pdf.set_text_color(0, 0, 0)
        else:
            pdf.multi_cell(
                190,
                6,
                txt=(
                    "Bu rapor döneminde mavi su için sisteme yüklenmiş fatura kanıtı bulunmamaktadır. "
                    "İzlenebilirlik için su faturalarının Veri Girişi ekranından eklenmesi önerilir."
                ),
            )

        pdf.ln(4)
        pdf.set_font(f, size=11, style="B")
        pdf.cell(190, 8, txt="Tablo 2: Genel Akış - Sistem Sınırı", ln=True)

        diger_gerekli = False
        try:
            for _, row in sistem_siniri_tablosu.iterrows():
                aciklama = str(row.get("Açıklama (Diğer)", "")).strip()
                if aciklama not in ("", "-", "nan", "None"):
                    diger_gerekli = True
                    break
        except Exception:
            pass

        pdf.set_fill_color(255, 192, 0)
        if diger_gerekli:
            pdf.set_font(f, size=9, style="B")
            for h, w in [
                ("Bileşen", 30), ("Kaynak", 35), ("Veri Kaynağı", 40),
                ("Veri Doğrulama", 40), ("Açıklama (Diğer)", 45),
            ]:
                ln = h == "Açıklama (Diğer)"
                pdf.cell(w, 8, txt=h, border=1, fill=True, align="C", ln=ln)
            pdf.set_font(f, size=9, style="")
        else:
            pdf.set_font(f, size=10, style="B")
            for h, w in [
                ("Bileşen", 40), ("Kaynak", 50), ("Veri Kaynağı", 50), ("Veri Doğrulama", 50),
            ]:
                ln = h == "Veri Doğrulama"
                pdf.cell(w, 8, txt=h, border=1, fill=True, align="C", ln=ln)
            pdf.set_font(f, size=10, style="")

        try:
            for _, row in sistem_siniri_tablosu.iterrows():
                bilesen = _safe(row.get("Bileşen"))
                kaynak = _safe(row.get("Kaynak"))
                veri_kaynagi = _safe(row.get("Veri Kaynağı"))
                veri_dogrulama = _safe(row.get("Veri Doğrulama"))
                aciklama = str(row.get("Açıklama (Diğer)", "-")).strip()
                if aciklama in ("", "nan", "None"):
                    aciklama = "-"
                if bilesen == "-" and kaynak == "-":
                    continue

                if diger_gerekli:
                    satirlar = textwrap.wrap(aciklama, width=25) or ["-"]
                    h = max(8, len(satirlar) * 4)
                    if pdf.get_y() + h > 270:
                        pdf.add_page()
                    x0, y0 = pdf.get_x(), pdf.get_y()
                    pdf.cell(30, h, txt=bilesen[:15], border=1, align="C")
                    pdf.cell(35, h, txt=kaynak[:20], border=1, align="C")
                    pdf.cell(40, h, txt=veri_kaynagi[:22], border=1, align="C")
                    pdf.cell(40, h, txt=veri_dogrulama[:22], border=1, align="C")
                    ax = pdf.get_x()
                    pdf.cell(45, h, txt="", border=1, ln=True)
                    y_off = y0 + (h - (len(satirlar) * 4)) / 2
                    pdf.set_xy(ax, y_off)
                    for s in satirlar:
                        pdf.set_x(ax)
                        pdf.cell(45, 4, txt=s, border=0, align="C", ln=True)
                    pdf.set_xy(x0, y0 + h)
                else:
                    pdf.cell(40, 8, txt=bilesen[:20], border=1, align="C")
                    pdf.cell(50, 8, txt=kaynak[:25], border=1, align="C")
                    pdf.cell(50, 8, txt=veri_kaynagi[:25], border=1, align="C")
                    pdf.cell(50, 8, txt=veri_dogrulama[:25], border=1, ln=True, align="C")
        except Exception:
            pass

        # ----- 4. Hesaplamalar -----
        pdf.ln(6)
        pdf.set_fill_color(13, 115, 119)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(f, size=14, style="B")
        pdf.cell(190, 10, txt="4. HESAPLAMALAR", ln=True, align="L", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        # Mavi
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="4.1. Mavi Su Ayak İzi Hesaplamaları", ln=True)
        pdf.set_font(f, size=10, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                "Şebeke, kuyu ve kaynak suları toplamı olarak hesaplanmıştır. "
                f"Şebeke: {_fmt(data.get('mavi_sebeke'))} m³/yıl · "
                f"Kuyu: {_fmt(data.get('mavi_yeralti'))} m³/yıl · "
                f"Kaynak: {_fmt(data.get('mavi_kaynak'))} m³/yıl."
            ),
        )
        pdf.ln(2)
        pdf.set_font(f, size=10, style="B")
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(95, 8, txt="Veri Kaynağı", border=1, fill=True, align="C")
        pdf.cell(95, 8, txt="Toplam Tüketim (m³/yıl)", border=1, ln=True, fill=True, align="C")
        pdf.set_font(f, size=10, style="")
        pdf.cell(95, 8, txt="Tesis Mavi Su Ayak İzi Hacmi", border=1, align="C")
        pdf.cell(95, 8, txt=_fmt(res_blue), border=1, ln=True, align="C")

        # Yeşil
        pdf.ln(5)
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="4.2. Yeşil Su Ayak İzi Hesaplamaları", ln=True)
        pdf.set_font(f, size=10, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                "Proseste kullanılan / buharlaşan yağmur suyu miktarıdır. "
                f"Girilen değer: {_fmt(data.get('yesil_yagmur'))} m³/yıl."
            ),
        )
        pdf.ln(2)
        pdf.set_font(f, size=10, style="B")
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(95, 8, txt="Veri Kaynağı", border=1, fill=True, align="C")
        pdf.cell(95, 8, txt="Toplam Tüketim (m³/yıl)", border=1, ln=True, fill=True, align="C")
        pdf.set_font(f, size=10, style="")
        pdf.cell(95, 8, txt="Tesis Yeşil Su Ayak İzi Hacmi", border=1, align="C")
        pdf.cell(95, 8, txt=_fmt(res_green), border=1, ln=True, align="C")

        # Gri
        pdf.ln(5)
        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt="4.3. Gri Su Ayak İzi Hesaplamaları", ln=True)
        pdf.set_font(f, size=10, style="")
        pdf.multi_cell(
            190,
            6,
            txt=(
                "Atıksu debisi ve kirletici parametrelerine göre hesaplanmıştır. "
                f"Kritik parametre: {kritik}."
            ),
        )
        pdf.ln(2)
        pdf.set_font(f, size=10, style="B")
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(95, 8, txt="Bileşen / Kritik Kirletici", border=1, fill=True, align="C")
        pdf.cell(95, 8, txt="Gereken Seyreltme Hacmi (m³/yıl)", border=1, ln=True, fill=True, align="C")
        pdf.set_font(f, size=10, style="")
        pdf.cell(95, 8, txt=f"Endüstriyel Atıksu ({kritik})", border=1, align="C")
        pdf.cell(95, 8, txt=_fmt(res_grey), border=1, ln=True, align="C")

        # Detay tablo
        detay = data.get("gri_detay") or []
        if detay:
            pdf.ln(4)
            pdf.set_font(f, size=10, style="B")
            pdf.cell(190, 7, txt="Parametre Detayları", ln=True)
            pdf.set_fill_color(232, 238, 243)
            for h, w in [("Parametre", 40), ("C_eff", 35), ("C_max", 35), ("C_nat", 35), ("Gri Su", 45)]:
                ln = h == "Gri Su"
                pdf.cell(w, 7, txt=h, border=1, fill=True, align="C", ln=ln)
            pdf.set_font(f, size=9, style="")
            for d in detay:
                pdf.cell(40, 7, txt=_safe(d.get("Parametre"))[:18], border=1, align="C")
                pdf.cell(35, 7, txt=_fmt(d.get("C_eff")), border=1, align="C")
                pdf.cell(35, 7, txt=_fmt(d.get("C_max")), border=1, align="C")
                pdf.cell(35, 7, txt=_fmt(d.get("C_nat")), border=1, align="C")
                pdf.cell(45, 7, txt=_fmt(d.get("Gri Su (m³/yıl)")), border=1, ln=True, align="C")

        # ----- 5. Sonuç -----
        pdf.add_page()
        pdf.set_fill_color(13, 115, 119)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(f, size=14, style="B")
        pdf.cell(190, 10, txt="5. SONUÇ", ln=True, align="L", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

        pdf.set_font(f, size=12, style="B")
        pdf.cell(190, 8, txt=f"Toplam Tesis Su Ayak İzi: {_fmt(total_vol)} m³/yıl", ln=True)
        pdf.ln(3)

        pdf.set_fill_color(11, 31, 51)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(f, size=11, style="B")
        pdf.cell(70, 8, txt="Bileşen", border=1, align="C", fill=True)
        pdf.cell(70, 8, txt="Hacim (m³/yıl)", border=1, align="C", fill=True)
        pdf.cell(50, 8, txt="Dağılım (%)", border=1, ln=True, align="C", fill=True)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font(f, size=11, style="")
        p_blue = (res_blue / total_vol) * 100 if total_vol > 0 else 0
        p_green = (res_green / total_vol) * 100 if total_vol > 0 else 0
        p_grey = (res_grey / total_vol) * 100 if total_vol > 0 else 0
        for ad, val, pct in [
            ("Mavi Su", res_blue, p_blue),
            ("Yeşil Su", res_green, p_green),
            ("Gri Su", res_grey, p_grey),
        ]:
            pdf.cell(70, 8, txt=ad, border=1, align="C")
            pdf.cell(70, 8, txt=_fmt(val), border=1, align="C")
            pdf.cell(50, 8, txt=f"% {pct:,.1f}".replace(",", "X").replace(".", ",").replace("X", "."), border=1, ln=True, align="C")

        pdf.set_font(f, size=11, style="B")
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(70, 8, txt="TOPLAM", border=1, align="C", fill=True)
        pdf.cell(70, 8, txt=_fmt(total_vol), border=1, align="C", fill=True)
        pdf.cell(50, 8, txt="% 100", border=1, ln=True, align="C", fill=True)

        # Pasta grafik
        if total_vol > 0:
            pdf.ln(8)
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
            ax.text(0, 0, f"TOPLAM:\n{_fmt(total_vol)} m³", ha="center", va="center", fontsize=11, fontweight="bold")
            grafik_yolu = os.path.join(tempfile.gettempdir(), "su_ayak_izi_pie.png")
            fig.savefig(grafik_yolu, format="png", dpi=200, bbox_inches="tight")
            plt.close(fig)
            temp_files.append(grafik_yolu)
            pdf.image(grafik_yolu, x=35, y=pdf.get_y(), w=140)
            pdf.ln(95)

        # ----- 6. Hedefler -----
        try:
            gecerli = [
                row
                for _, row in duzenlenmis_hedefler.iterrows()
                if str(row.get("Hedef Açıklaması", "")).strip()
            ]
            if gecerli:
                pdf.ln(4)
                pdf.set_fill_color(13, 115, 119)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font(f, size=14, style="B")
                pdf.cell(190, 10, txt="6. SÜRDÜRÜLEBİLİRLİK HEDEFLERİ", ln=True, align="L", fill=True)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(4)
                pdf.set_font(f, size=11, style="")
                for hedef in gecerli:
                    yil = _safe(hedef.get("Hedef Yılı"))
                    acik = _safe(hedef.get("Hedef Açıklaması"))
                    pdf.multi_cell(190, 6, txt=f"• {yil} Yılı Hedefi: {acik}")
        except Exception:
            pass

        # KPI (opsiyonel)
        kpi = data.get("kpi") or {}
        if kpi.get("spesifik_su") is not None:
            pdf.ln(6)
            pdf.set_fill_color(13, 115, 119)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font(f, size=14, style="B")
            pdf.cell(190, 10, txt="7. PERFORMANS GÖSTERGELERİ (KPI)", ln=True, align="L", fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)
            pdf.set_font(f, size=11, style="")
            birim = kpi.get("uretim_birimi", "ton")
            pdf.cell(190, 7, txt=f"Spesifik su tüketimi: {_fmt(kpi.get('spesifik_su'))} m³/{birim}", ln=True)
            pdf.cell(190, 7, txt=f"Spesifik atıksu: {_fmt(kpi.get('spesifik_atiksu'))} m³/{birim}", ln=True)
            pdf.cell(190, 7, txt=f"Spesifik evsel su: {_fmt(kpi.get('evsel_su'))} L/kişi.gün", ln=True)
            pdf.cell(190, 7, txt=f"Spesifik evsel atıksu: {_fmt(kpi.get('evsel_atiksu'))} L/kişi.gün", ln=True)

        out = pdf.output(dest="S")
        if isinstance(out, (bytes, bytearray)):
            return bytes(out)
        return out.encode("latin-1")
    finally:
        for p in temp_files:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
