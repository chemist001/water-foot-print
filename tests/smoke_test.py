"""
Kurumsal Su Ayak İzi — otomatik smoke test.
Çalıştırma: python tests/smoke_test.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.calc import (  # noqa: E402
    hesapla_gri_parametre,
    hesapla_gri_su,
    hesapla_mavi_su,
    hesapla_yesil_su,
)
from services.docx_report import generate_docx_bytes  # noqa: E402
from services.pdf_report import generate_pdf_bytes  # noqa: E402
from services.report_utils import format_rapor_tarihi  # noqa: E402
from services.storage import rapor_getir, raporu_kaydet, rapor_sil  # noqa: E402


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_calc() -> None:
    mavi = hesapla_mavi_su(1000, 500, 50)
    assert_true(mavi == 1550, f"mavi={mavi}")
    yesil = hesapla_yesil_su(120)
    assert_true(yesil == 120, f"yesil={yesil}")

    # V=0 → gri 0
    gri, kritik, _, hatalar = hesapla_gri_su(0, [])
    assert_true(gri == 0.0 and kritik == "—" and not hatalar, "V=0 gri")

    # KOİ örneği: V=10000, C_eff=200, C_max=300, C_nat=0 → 6666.67
    params = [{"ad": "KOİ", "C_eff": 200.0, "C_max": 300.0, "C_nat": 0.0}]
    gri, kritik, detay, hatalar = hesapla_gri_su(10000, params)
    assert_true(gri is not None and abs(gri - 6666.67) < 0.1, f"gri={gri}")
    assert_true(kritik == "KOİ", f"kritik={kritik}")
    assert_true(len(detay) == 1, "detay")

    # C_max <= C_nat hata
    sonuc, hata = hesapla_gri_parametre(1000, 50, 30, 40)
    assert_true(sonuc is None and hata is not None, "C_max<=C_nat")

    # C_eff < C_nat → 0
    sonuc, hata = hesapla_gri_parametre(1000, 10, 300, 50)
    assert_true(sonuc == 0.0 and hata is None, "C_eff<C_nat")


def test_report_date() -> None:
    assert_true(format_rapor_tarihi(date(2026, 8, 10)) == "10.08.2026", "date")
    assert_true(format_rapor_tarihi("2026-08-10") == "10.08.2026", "iso")
    assert_true(format_rapor_tarihi("2026-08-10T14:30:00") == "10.08.2026", "iso datetime")
    assert_true(format_rapor_tarihi(None) == "Belirtilmedi", "none")


def _sample_payload() -> dict:
    logo = ROOT / "logos" / "adaso_logo.png"
    return {
        "firma_adi": "Test Sanayi A.Ş.",
        "sektor": "Tekstil",
        "lokasyon": "Adana OSB",
        "yetkili": "Test Yetkili",
        "email": "test@firma.com",
        "telefon": "+90 322 000 00 00",
        "rapor_yili": "2026",
        "rapor_tarihi": "2026-08-10",
        "logo_path": str(logo) if logo.exists() else "",
        "mavi_su": 1550.0,
        "yesil_su": 120.0,
        "gri_su": 6666.67,
        "toplam_su": 8336.67,
        "gri_kritik": "KOİ",
        "gri_detay": [
            {"Parametre": "KOİ", "C_eff": 200, "C_max": 300, "C_nat": 0, "Gri Su (m³/yıl)": 6666.67}
        ],
        "mavi_sebeke": 1000.0,
        "mavi_yeralti": 500.0,
        "mavi_kaynak": 50.0,
        "yesil_yagmur": 120.0,
        "gri_debi": 10000.0,
        "hedefler": [{"Hedef Yılı": "2027", "Hedef Açıklaması": "Su tüketimini %5 azaltmak"}],
        "sorumlular": [{"Sorumlu Kişi": "Ali Veli", "Görev": "EHS Müdürü", "İletişim": "a@firma.com"}],
        "sistem_siniri": [{
            "Bileşen": "Mavi Su",
            "Kaynak": "Şebeke",
            "Veri Kaynağı": "Sayaç ve Fatura",
            "Veri Doğrulama": "Tüketim Kayıtları",
            "Açıklama (Diğer)": "",
        }],
        "veri_kalitesi": "Test veri kalitesi açıklaması.",
        "kpi": {
            "uretim_birimi": "ton",
            "spesifik_su": 12.5,
            "spesifik_atiksu": 3.2,
            "evsel_su": 85.0,
            "evsel_atiksu": 70.0,
        },
        "mavi_kanit": {
            "yil": "2026",
            "fatura_adedi": 2,
            "fatura_toplam_m3": 1550.0,
            "girilen_toplam_m3": 1550.0,
            "eslesme": True,
            "fatura_var": True,
            "ozet": "Fatura toplamları ile girilen mavi su verileri uyumlu.",
            "uyari_mesajlari": [],
            "faturalar": [
                {"kaynak": "Şebeke", "fatura_no": "F1", "donem": "2026", "m3": 1000.0, "dosya_adi": "f1.pdf"},
                {"kaynak": "Kuyu / Yeraltı", "fatura_no": "F2", "donem": "2026", "m3": 550.0, "dosya_adi": ""},
            ],
        },
    }


def test_pdf_word() -> None:
    data = _sample_payload()
    pdf = generate_pdf_bytes(data)
    docx = generate_docx_bytes(data)
    assert_true(len(pdf) > 5000, f"pdf too small: {len(pdf)}")
    assert_true(len(docx) > 5000, f"docx too small: {len(docx)}")
    assert_true(pdf[:4] == b"%PDF", "pdf magic")
    assert_true(docx[:2] == b"PK", "docx zip magic")


def test_storage() -> None:
    data = _sample_payload()
    rid = raporu_kaydet(data)
    assert_true(len(rid) == 8, f"rid={rid}")
    loaded = rapor_getir(rid)
    assert_true(loaded is not None, "load")
    assert_true(loaded["mavi_su"] == 1550.0, "mavi persisted")
    assert_true(loaded["mavi_sebeke"] == 1000.0, "input persisted")
    # PDF from stored
    pdf = generate_pdf_bytes(loaded)
    assert_true(len(pdf) > 5000, "pdf from storage")
    docx = generate_docx_bytes(loaded)
    assert_true(len(docx) > 5000, "docx from storage")
    assert_true(rapor_sil(rid), "delete")


def test_kanit_karsilastirma() -> None:
    from services.kanit import (
        KAYNAK_SEBEKE,
        fatura_ekle,
        fatura_sil,
        karsilastir_mavi_su,
        list_faturalar,
    )

    yil = "_test_2025"
    # Temizle
    for k in list_faturalar(yil):
        fatura_sil(yil, k["id"])

    # Uyumlu senaryo
    a = fatura_ekle(yil, kaynak=KAYNAK_SEBEKE, m3=600.0, fatura_no="A1", donem="Ocak")
    b = fatura_ekle(yil, kaynak=KAYNAK_SEBEKE, m3=400.0, fatura_no="A2", donem="Şubat")
    cmp = karsilastir_mavi_su(yil, sebeke=1000.0, kuyu=0.0, kaynak=0.0)
    assert_true(cmp["eslesme"] is True, f"should match: {cmp}")
    assert_true(cmp["fatura_toplam"] == 1000.0, f"toplam={cmp['fatura_toplam']}")

    # Uyumsuz
    cmp2 = karsilastir_mavi_su(yil, sebeke=1500.0, kuyu=0.0, kaynak=0.0)
    assert_true(cmp2["eslesme"] is False, "should mismatch")
    assert_true(len(cmp2["uyari_mesajlari"]) >= 1, "uyari")

    # Kuyu girilmiş ama fatura yok → uyumlu sayılmamalı
    cmp3 = karsilastir_mavi_su(yil, sebeke=1000.0, kuyu=200.0, kaynak=0.0)
    assert_true(cmp3["eslesme"] is False, "kuyu kanitsiz uyumlu olmamali")

    fatura_sil(yil, a["id"])
    fatura_sil(yil, b["id"])


def test_gri_nan() -> None:
    from services.calc import hesapla_gri_su

    gri, _, _, hatalar = hesapla_gri_su(
        1000,
        [{"ad": "KOI", "C_eff": float("nan"), "C_max": 300, "C_nat": 0}],
    )
    assert_true(gri is None, "nan kabul edilmemeli")
    assert_true(bool(hatalar), f"hatalar={hatalar}")


def test_fatura_ocr_parse() -> None:
    from services.fatura_ocr import extract_fatura_meta, extract_m3_candidates

    sample = """
    ASCI SU FATURASI
    Fatura No: 2025-00412
    Dönem: Ocak 2025
    Önceki endeks: 10.200
    Son endeks: 11.450
    Tüketim: 1.250,00 m³
    Su bedeli: 45.000,00 TL
    KDV: 9.000,00 TL
    Genel Toplam: 54.000,00 TL
    """
    adaylar = extract_m3_candidates(sample)
    assert_true(len(adaylar) >= 1, "aday yok")
    assert_true(adaylar[0]["m3"] == 1250.0, f"beklenen 1250, gelen {adaylar[0]}")
    meta = extract_fatura_meta(sample)
    assert_true("2025-00412" in meta["fatura_no"], f"fatura_no={meta}")
    assert_true("Ocak" in meta["donem"] or "2025" in meta["donem"], f"donem={meta}")

    # SARFİYAT önceliği (ASKİ tarzı) — spatial satır simülasyonu
    aski = """
    İÇME SUYU
    SARFİYAT          3.450,00
    BİRİM FİYAT       12,50 TL/m3
    SU BEDELİ         43.125,00 TL
    """
    adaylar2 = extract_m3_candidates(aski)
    assert_true(len(adaylar2) >= 1, "sarfiyat aday yok")
    assert_true(adaylar2[0]["m3"] == 3450.0, f"sarfiyat beklenen 3450, gelen {adaylar2[0]}")
    assert_true("sarfiyat" in adaylar2[0]["baglam"].lower().replace("ı", "i"), "baglam sarfiyat")

    # OCR bozulmuş SARFIYAT + sonraki satır
    aski2 = "SARFIYAT\n1.875,50\nTL/m3 8,20"
    adaylar3 = extract_m3_candidates(aski2)
    assert_true(adaylar3[0]["m3"] == 1875.5, f"satir alti {adaylar3[0]}")

    # MADDE 63 tuzağı — spatial
    from services.fatura_ocr import extract_sarfiyat_spatial

    items = [
        {"text": "SARFiYAT", "x": 191.0, "y": 1258.0, "score": 0.9},
        {"text": "25", "x": 287.0, "y": 1258.0, "score": 0.9},
        {
            "text": "A.H. ve T.Y. MADDE 63-(1)Borc Nedeniyle Kapama",
            "x": 1141.0,
            "y": 1274.5,
            "score": 0.9,
        },
    ]
    sp = extract_sarfiyat_spatial(items)
    assert_true(sp is not None and sp["m3"] == 25.0, f"spatial beklenen 25, gelen {sp}")


def main() -> int:
    tests = [
        ("Hesaplama", test_calc),
        ("Tarih formatı", test_report_date),
        ("PDF / Word", test_pdf_word),
        ("Yerel depolama", test_storage),
        ("Fatura kanıt karşılaştırma", test_kanit_karsilastirma),
        ("Fatura OCR parse", test_fatura_ocr_parse),
        ("Gri NaN koruması", test_gri_nan),
    ]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  OK  {name}")
            passed += 1
        except Exception as e:
            print(f" FAIL {name}: {e}")
    print(f"\n{passed}/{len(tests)} test geçti.")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
