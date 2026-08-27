"""
Mavi su kanıt belgeleri (su faturaları) — kayıt, depolama ve tutarlılık kontrolü.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

KANIT_ROOT = Path(__file__).resolve().parent.parent / "data" / "kanit"

KAYNAK_SEBEKE = "Şebeke"
KAYNAK_KUYU = "Kuyu / Yeraltı"
KAYNAK_KAYNAK = "Kaynak Suları"
KAYNAK_SECENEKLERI = [KAYNAK_SEBEKE, KAYNAK_KUYU, KAYNAK_KAYNAK]

# Mutlak tolerans (m³) ve göreli tolerans (oran)
TOLERANS_M3 = 1.0
TOLERANS_ORAN = 0.01  # %1


def _tenant_root() -> Path:
    """Bulut oturumunda firma_id ile klasör izolasyonu."""
    try:
        from services import auth

        u = auth.current_user()
        if u and u.firma_id and not auth.is_local_mode():
            d = KANIT_ROOT / u.firma_id
            d.mkdir(parents=True, exist_ok=True)
            return d
    except Exception:
        pass
    return KANIT_ROOT


def _yil_dir(yil: str | int) -> Path:
    d = _tenant_root() / str(yil)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _kayit_path(yil: str | int) -> Path:
    return _yil_dir(yil) / "kayitlar.json"


def _load_kayitlar(yil: str | int) -> list[dict[str, Any]]:
    path = _kayit_path(yil)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_kayitlar(yil: str | int, kayitlar: list[dict[str, Any]]) -> None:
    path = _kayit_path(yil)
    path.write_text(
        json.dumps(kayitlar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def file_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_duplicate(
    yil: str | int,
    *,
    content_hash: str | None = None,
    dosya_adi: str | None = None,
    size: int | None = None,
) -> dict[str, Any] | None:
    """Aynı içerik veya aynı ad+boyut ile kayıtlı fatura var mı?"""
    for k in _load_kayitlar(yil):
        if content_hash and k.get("content_hash") and k["content_hash"] == content_hash:
            return k
        if (
            content_hash
            and k.get("dosya_yolu")
            and Path(k["dosya_yolu"]).exists()
        ):
            try:
                existing = file_content_hash(Path(k["dosya_yolu"]).read_bytes())
                if existing == content_hash:
                    return k
            except OSError:
                pass
        if (
            dosya_adi
            and size is not None
            and k.get("dosya_adi") == dosya_adi
            and k.get("dosya_boyut") == size
        ):
            return k
    return None


def list_faturalar(yil: str | int) -> list[dict[str, Any]]:
    return _load_kayitlar(yil)


def fatura_ekle(
    yil: str | int,
    *,
    kaynak: str,
    m3: float,
    fatura_no: str = "",
    donem: str = "",
    uploaded_file: Any = None,
    notlar: str = "",
    ocr_m3: float | None = None,
    ocr_yontem: str = "",
    allow_duplicate: bool = False,
) -> dict[str, Any]:
    """Fatura kaydı ekler; dosya varsa diske yazar. Aynı dosya tekrarında hata verir."""
    if kaynak not in KAYNAK_SECENEKLERI:
        raise ValueError(f"Geçersiz kaynak: {kaynak}")
    m3_f = float(m3)
    if m3_f < 0:
        raise ValueError("Fatura m³ değeri negatif olamaz.")

    kayit_id = str(uuid.uuid4())[:8]
    dosya_adi = ""
    dosya_yolu = ""
    dosya_boyut = 0
    content_hash = ""

    if uploaded_file is not None:
        raw = uploaded_file.getvalue()
        raw_name = Path(getattr(uploaded_file, "name", "fatura.bin")).name
        dosya_boyut = len(raw)
        content_hash = file_content_hash(raw)
        if not allow_duplicate:
            dup = find_duplicate(
                yil,
                content_hash=content_hash,
                dosya_adi=raw_name,
                size=dosya_boyut,
            )
            if dup:
                raise ValueError(
                    f"Bu fatura zaten kayıtlı (ID: {dup.get('id')}, "
                    f"{dup.get('m3')} m³, dosya: {dup.get('dosya_adi')}). "
                    "Çift kayıt engellendi."
                )
        safe = re.sub(r"[^\w.\-]+", "_", raw_name, flags=re.UNICODE)
        if not safe:
            safe = "fatura.bin"
        dest_name = f"{kayit_id}_{safe}"
        dest = _yil_dir(yil) / dest_name
        dest.write_bytes(raw)
        dosya_adi = raw_name
        dosya_yolu = str(dest.resolve())
        # Bulut oturumunda Storage'a da kopyala (başarısız olsa yerel kalır)
        try:
            from services.cloud_files import upload_kanit_bytes

            cloud_path = upload_kanit_bytes(
                yil=yil,
                file_name=dest_name,
                data=raw,
                content_type="application/pdf"
                if raw_name.lower().endswith(".pdf")
                else "application/octet-stream",
            )
            if cloud_path:
                # kayit dict'ine sonra eklenecek
                pass
        except Exception:
            cloud_path = None
    else:
        cloud_path = None

    kayit = {
        "id": kayit_id,
        "kaynak": kaynak,
        "fatura_no": str(fatura_no or "").strip(),
        "donem": str(donem or "").strip(),
        "m3": round(m3_f, 2),
        "dosya_adi": dosya_adi,
        "dosya_yolu": dosya_yolu,
        "dosya_boyut": dosya_boyut,
        "content_hash": content_hash,
        "cloud_path": cloud_path,
        "notlar": str(notlar or "").strip(),
        "ocr_m3": ocr_m3,
        "ocr_yontem": ocr_yontem or "",
        "yuklenme": datetime.now().isoformat(timespec="seconds"),
    }
    kayitlar = _load_kayitlar(yil)
    kayitlar.append(kayit)
    _save_kayitlar(yil, kayitlar)
    return kayit


def dedupe_faturalar(yil: str | int) -> list[str]:
    """İçerik hash / ad+boyut tekrarlarını siler; silinen id listesi döner."""
    kayitlar = _load_kayitlar(yil)
    seen_hash: set[str] = set()
    seen_name_size: set[tuple[str, int]] = set()
    keep: list[dict[str, Any]] = []
    silinen: list[str] = []

    for k in kayitlar:
        ch = k.get("content_hash") or ""
        if not ch and k.get("dosya_yolu") and Path(k["dosya_yolu"]).exists():
            try:
                ch = file_content_hash(Path(k["dosya_yolu"]).read_bytes())
                k["content_hash"] = ch
            except OSError:
                pass
        key_ns = (str(k.get("dosya_adi") or ""), int(k.get("dosya_boyut") or 0))
        is_dup = False
        if ch and ch in seen_hash:
            is_dup = True
        elif key_ns[0] and key_ns[1] and key_ns in seen_name_size:
            is_dup = True
        if is_dup:
            silinen.append(str(k.get("id")))
            path = Path(k.get("dosya_yolu") or "")
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
            continue
        if ch:
            seen_hash.add(ch)
        if key_ns[0] and key_ns[1]:
            seen_name_size.add(key_ns)
        keep.append(k)

    if silinen:
        _save_kayitlar(yil, keep)
    return silinen


def fatura_sil(yil: str | int, kayit_id: str) -> bool:
    kayitlar = _load_kayitlar(yil)
    yeni = []
    silindi = False
    for k in kayitlar:
        if str(k.get("id")) == str(kayit_id):
            silindi = True
            path = Path(k.get("dosya_yolu") or "")
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
            continue
        yeni.append(k)
    if silindi:
        _save_kayitlar(yil, yeni)
    return silindi


def fatura_toplamlari(yil: str | int) -> dict[str, float]:
    """Kaynak tipine göre fatura m³ toplamları."""
    totals = {KAYNAK_SEBEKE: 0.0, KAYNAK_KUYU: 0.0, KAYNAK_KAYNAK: 0.0}
    for k in _load_kayitlar(yil):
        kaynak = k.get("kaynak")
        if kaynak in totals:
            totals[kaynak] += float(k.get("m3") or 0.0)
    return {k: round(v, 2) for k, v in totals.items()}


def _tolerans(girilen: float) -> float:
    return max(TOLERANS_M3, abs(girilen) * TOLERANS_ORAN)


def karsilastir_mavi_su(
    yil: str | int,
    sebeke: float,
    kuyu: float,
    kaynak: float,
) -> dict[str, Any]:
    """
    Girilen mavi su değerleri ile fatura toplamlarını karşılaştırır.

    Dönüş:
      eslesme: bool (fatura yoksa True — uyarı yok, sadece bilgi)
      fatura_var: bool
      satirlar: her kaynak için detay
      uyari_mesajlari: list[str]
      ozet: kısa metin
    """
    sebeke = float(sebeke or 0.0)
    kuyu = float(kuyu or 0.0)
    kaynak = float(kaynak or 0.0)
    fatura_sum = fatura_toplamlari(yil)
    kayitlar = _load_kayitlar(yil)
    fatura_var = len(kayitlar) > 0

    eslestirme = [
        (KAYNAK_SEBEKE, sebeke, "Şebeke"),
        (KAYNAK_KUYU, kuyu, "Kuyu / Yeraltı"),
        (KAYNAK_KAYNAK, kaynak, "Kaynak Suları"),
    ]

    satirlar: list[dict[str, Any]] = []
    uyarilar: list[str] = []
    eslesme = True

    for kaynak_key, girilen, etiket in eslestirme:
        fatura_m3 = fatura_sum.get(kaynak_key, 0.0)
        fark = round(girilen - fatura_m3, 2)
        tol = _tolerans(girilen if girilen > 0 else fatura_m3)
        kaynakta_fatura = any(k.get("kaynak") == kaynak_key for k in kayitlar)

        if not kaynakta_fatura and girilen <= 0:
            durum = "fatura_yok"
            uyumlu = True
        elif not kaynakta_fatura and girilen > 0:
            # Girilen var ama kanıt yok → tam uyum sayma
            durum = "kanit_eksik"
            uyumlu = False
            eslesme = False
            uyarilar.append(
                f"{etiket}: sisteme {girilen:,.2f} m³ girilmiş ancak bu kaynak için "
                "fatura kanıtı yok.".replace(",", "X").replace(".", ",").replace("X", ".")
            )
        elif abs(fark) <= tol:
            durum = "uyumlu"
            uyumlu = True
        else:
            durum = "uyumsuz"
            uyumlu = False
            eslesme = False
            yon = "fazla" if fark > 0 else "eksik"
            uyarilar.append(
                f"{etiket}: sisteme girilen {girilen:,.2f} m³, fatura toplamı "
                f"{fatura_m3:,.2f} m³ (fark {abs(fark):,.2f} m³ — girilen {yon}). "
                f"Tolerans: ±{tol:,.2f} m³.".replace(",", "X").replace(".", ",").replace("X", ".")
            )

        durum_label = {
            "uyumlu": "Uyumlu",
            "fatura_yok": "Fatura yok",
            "kanit_eksik": "Kanıt eksik",
            "uyumsuz": "Uyumsuz",
        }.get(durum, durum)

        satirlar.append(
            {
                "Kaynak": etiket,
                "Girilen (m³)": round(girilen, 2),
                "Fatura Toplamı (m³)": round(fatura_m3, 2),
                "Fark (m³)": fark,
                "Durum": durum_label,
                "uyumlu": uyumlu,
            }
        )

    girilen_toplam = round(sebeke + kuyu + kaynak, 2)
    fatura_toplam = round(sum(fatura_sum.values()), 2)
    toplam_fark = round(girilen_toplam - fatura_toplam, 2)

    # Toplam fark toleransı aşarsa da uyumsuz say
    if fatura_var and abs(toplam_fark) > _tolerans(girilen_toplam if girilen_toplam > 0 else fatura_toplam):
        eslesme = False

    if not fatura_var:
        ozet = "Henüz fatura kanıtı yüklenmedi. Karşılaştırma için su faturası ekleyin."
    elif eslesme:
        ozet = (
            f"Fatura toplamları ile girilen mavi su verileri uyumlu "
            f"(girilen {girilen_toplam:,.2f} m³ · fatura {fatura_toplam:,.2f} m³)."
            .replace(",", "X").replace(".", ",").replace("X", ".")
        )
    else:
        ozet = (
            f"Uyarı: Girilen mavi su ile fatura kanıtları uyuşmuyor veya eksik "
            f"(girilen {girilen_toplam:,.2f} m³ · fatura {fatura_toplam:,.2f} m³ · "
            f"fark {toplam_fark:,.2f} m³)."
            .replace(",", "X").replace(".", ",").replace("X", ".")
        )

    return {
        "eslesme": eslesme if fatura_var else True,
        "fatura_var": fatura_var,
        "fatura_adedi": len(kayitlar),
        "girilen_toplam": girilen_toplam,
        "fatura_toplam": fatura_toplam,
        "toplam_fark": toplam_fark,
        "satirlar": satirlar,
        "uyari_mesajlari": uyarilar,
        "ozet": ozet,
        "yil": str(yil),
    }


def ozet_payload(yil: str | int, sebeke: float, kuyu: float, kaynak: float) -> dict[str, Any]:
    """Rapor / snapshot için sadeleştirilmiş kanıt özeti."""
    cmp = karsilastir_mavi_su(yil, sebeke, kuyu, kaynak)
    kayitlar = _load_kayitlar(yil)
    return {
        "yil": str(yil),
        "fatura_adedi": cmp["fatura_adedi"],
        "fatura_toplam_m3": cmp["fatura_toplam"],
        "girilen_toplam_m3": cmp["girilen_toplam"],
        "eslesme": cmp["eslesme"],
        "fatura_var": cmp["fatura_var"],
        "ozet": cmp["ozet"],
        "uyari_mesajlari": cmp["uyari_mesajlari"],
        "faturalar": [
            {
                "id": k.get("id"),
                "kaynak": k.get("kaynak"),
                "fatura_no": k.get("fatura_no"),
                "donem": k.get("donem"),
                "m3": k.get("m3"),
                "dosya_adi": k.get("dosya_adi"),
            }
            for k in kayitlar
        ],
    }
