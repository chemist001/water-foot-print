"""
Su faturası PDF/görsellerinden m³ (ve mümkünse fatura no / dönem) otomatik okuma.

Öncelik: **SARFİYAT** satırındaki değer (ASKİ / belediye faturaları).
Akış:
1) PDF metin çıkarma (pymupdf / pypdf)
2) Aday yoksa veya SARFİYAT bulunamadıysa OCR (yüksek çözünürlük)
3) SARFİYAT / tüketim kalıplarıyla m³ puanlama
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

# Türkçe sayı: 1.234,56 veya 1234,56 veya 1234.56
_NUM = r"(?P<num>\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)"

# m³ etiketleri (OCR bozulmaları dahil)
_M3_UNIT = r"(?:m\s*[³³3]|m3|mt[uü]p|metrek[uü]p|m\s*³)"

# SARFİYAT + OCR bozulmaları (S/5, İ/I/1, boşluk)
_SARFIYAT = (
    r"(?:s|5)\s*a\s*r\s*f\s*[iıiİI1l]\s*y\s*a\s*t"
)

_CONTEXT_KEYWORDS = (
    "sarfiyat",
    "sarfi yat",
    "sarfıyat",
    "tüketim",
    "tuketim",
    "kullanım",
    "kullanim",
    "çekim",
    "cekim",
    "fark",
    "sayac",
    "sayaç",
    "endeks",
    "su miktar",
    "su tuket",
    "su tüket",
    "miktar",
    "hacim",
    "toplam tuket",
    "toplam tüket",
    "fatura miktar",
    "brut tuket",
    "brüt tüket",
    "net tuket",
    "net tüket",
)

_EXCLUDE_KEYWORDS = (
    "tl/m",
    "tl / m",
    "birim fiyat",
    "birim bedel",
    "kdv",
    "tutar",
    "bedel",
    "ücret",
    "ucret",
    "fiyat",
    "borç",
    "borc",
    "ödeme",
    "odeme",
    "iban",
    "vergi",
    "toplam tutar",
    "genel toplam",
    "ödenen",
    "odenen",
    "gecikme",
)


def _parse_tr_number(raw: str) -> float | None:
    s = (raw or "").strip().replace(" ", "").replace("\u00a0", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        val = float(s)
    except ValueError:
        return None
    if val < 0 or val > 50_000_000:
        return None
    return val


def _normalize_text(text: str) -> str:
    t = text.replace("\u00a0", " ")
    t = t.replace("³", "3").replace("²", "2")
    t = re.sub(r"[|]", "I", t)
    # OCR: SARFİYAT bozulmalarını sadeleştir
    t = re.sub(
        r"(?i)(s|5)\s*a\s*r\s*f\s*[iıiİI1l]\s*y\s*a\s*t",
        "SARFIYAT",
        t,
    )
    return t


def _fold(s: str) -> str:
    return (
        s.lower()
        .replace("ı", "i")
        .replace("İ", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ç", "c")
    )


def _score_candidate(value: float, context: str, has_unit: bool, *, sarfiyat: bool = False) -> float:
    ctx = _fold(context)
    score = 0.0
    if sarfiyat:
        score += 12.0  # birincil kaynak
    if has_unit:
        score += 5.0
    for kw in _CONTEXT_KEYWORDS:
        if _fold(kw) in ctx:
            score += 3.0
            break
    for kw in _EXCLUDE_KEYWORDS:
        if _fold(kw) in ctx:
            score -= 5.0
            break
    # Yanında yalnız "TL" varsa (birim fiyat satırı) cezalandır
    if re.search(r"(?i)\btl\b", context) and not has_unit and not sarfiyat:
        score -= 3.0
    if 1 <= value <= 500_000:
        score += 1.5
    if 10 <= value <= 50_000:
        score += 1.0
    if value < 1:
        score -= 2.0
    if not has_unit and not sarfiyat and value >= 1000 and abs(value - round(value)) < 1e-9:
        score -= 0.5
    return score


def _add_candidate(
    found: dict[float, dict[str, Any]],
    *,
    val: float,
    score: float,
    ctx: str,
    raw: str,
) -> None:
    key = round(val, 2)
    prev = found.get(key)
    if prev is None or score > prev["skor"]:
        found[key] = {
            "m3": key,
            "skor": round(score, 2),
            "baglam": " ".join(ctx.split())[:160],
            "ham": raw,
        }


def _extract_sarfiyat_values(text_n: str, found: dict[float, dict[str, Any]]) -> None:
    """SARFİYAT satırı / yanındaki sayıyı birincil aday olarak ekler."""
    lines = text_n.splitlines()

    def _is_unit_price_context(local: str) -> bool:
        low = _fold(local)
        if "birim" in low:
            return True
        if re.search(r"(?i)tl\s*/\s*m", local):
            return True
        if re.search(r"(?i)\btl\b", local) and re.search(_M3_UNIT, local, re.I):
            # "12,50 TL/m3" birim fiyat
            return True
        return False

    # Tek satır: SARFIYAT ... 1.250,00
    pat_same = re.compile(
        rf"(?i)(?:SARFIYAT|{_SARFIYAT})\s*[:=]?\s*{_NUM}(?:\s*{_M3_UNIT})?",
    )
    for m in pat_same.finditer(text_n):
        raw = m.group("num")
        val = _parse_tr_number(raw)
        if val is None:
            continue
        ctx = text_n[max(0, m.start() - 20) : min(len(text_n), m.end() + 30)]
        if _is_unit_price_context(ctx):
            continue
        has_unit = bool(re.search(_M3_UNIT, m.group(0), re.IGNORECASE))
        score = _score_candidate(val, ctx, has_unit, sarfiyat=True) + 3.0
        _add_candidate(found, val=val, score=score, ctx=ctx, raw=raw)

    # Tablo: önce aynı satır, yoksa sonraki satırlar
    for i, line in enumerate(lines):
        if not re.search(rf"(?i)SARFIYAT|{_SARFIYAT}", line):
            continue
        m_label = re.search(rf"(?i)SARFIYAT|{_SARFIYAT}", line)
        after = line[m_label.end() :] if m_label else ""
        same_line_nums: list[tuple[float, str, str]] = []
        for m in re.finditer(_NUM, after):
            raw = m.group("num")
            if raw.strip() in {"3", "2"}:
                continue
            val = _parse_tr_number(raw)
            if val is None:
                continue
            local = after[max(0, m.start() - 10) : m.end() + 20]
            if _is_unit_price_context(local):
                continue
            same_line_nums.append((val, raw, "SARFIYAT " + line.strip()))

        if same_line_nums:
            for val, raw, ctx in same_line_nums:
                score = _score_candidate(val, ctx, False, sarfiyat=True) + 5.0
                _add_candidate(found, val=val, score=score, ctx=ctx, raw=raw)
            continue

        # Aynı satırda sayı yoksa sonraki 2 satıra bak (OCR satır kırılması)
        for j in range(i + 1, min(i + 3, len(lines))):
            nxt = lines[j]
            if _is_unit_price_context(nxt) or "birim" in _fold(nxt):
                continue
            if re.search(r"(?i)madde|bor[cç]\s*neden|kapama", nxt):
                continue
            for m in re.finditer(_NUM, nxt):
                raw = m.group("num")
                if raw.strip() in {"3", "2"}:
                    continue
                val = _parse_tr_number(raw)
                if val is None:
                    continue
                local = nxt[max(0, m.start() - 10) : m.end() + 15]
                if _is_unit_price_context(local):
                    continue
                score = _score_candidate(val, "SARFIYAT " + nxt, False, sarfiyat=True)
                if val >= 1:
                    score += 2.0
                _add_candidate(found, val=val, score=score, ctx="SARFIYAT " + nxt.strip(), raw=raw)
            if re.search(_NUM, nxt):
                break


def extract_m3_candidates(text: str) -> list[dict[str, Any]]:
    """Metinden m³ adaylarını çıkarır; skora göre sıralı. SARFİYAT öncelikli."""
    if not text or not text.strip():
        return []
    text_n = _normalize_text(text)
    found: dict[float, dict[str, Any]] = {}

    # 1) SARFİYAT önceliği
    _extract_sarfiyat_values(text_n, found)

    patterns = [
        re.compile(rf"{_NUM}\s*{_M3_UNIT}", re.IGNORECASE),
        re.compile(rf"{_M3_UNIT}\s*[:=]?\s*{_NUM}", re.IGNORECASE),
        re.compile(
            rf"(?:t[uü]ketim|kullan[iı]m|su\s*miktar[iı]?|endeks\s*fark[iı]?|"
            rf"sayac\s*fark[iı]?|saya[cç]\s*fark[iı]?)\s*[:=]?\s*{_NUM}",
            re.IGNORECASE,
        ),
    ]

    for pat in patterns:
        for m in pat.finditer(text_n):
            raw = m.group("num")
            if raw.strip() in {"3", "2"} and re.search(
                r"m\s*" + re.escape(raw), m.group(0), re.IGNORECASE
            ):
                continue
            val = _parse_tr_number(raw)
            if val is None:
                continue
            start = max(0, m.start() - 40)
            end = min(len(text_n), m.end() + 40)
            ctx = text_n[start:end]
            # "TL/m³ 12,50" birim fiyatını tüketim sanma
            if re.search(r"(?i)tl\s*/\s*m|birim\s*fiyat", ctx):
                continue
            # Eşleşmeden hemen önce "TL/" varsa birim fiyattır
            prefix = text_n[max(0, m.start() - 8) : m.start()]
            if re.search(r"(?i)tl\s*/\s*$", prefix) or re.search(r"(?i)/\s*$", prefix):
                continue
            has_unit = bool(re.search(_M3_UNIT, m.group(0), re.IGNORECASE))
            sarfiyat = "sarfiyat" in _fold(ctx)
            score = _score_candidate(val, ctx, has_unit, sarfiyat=sarfiyat)
            _add_candidate(found, val=val, score=score, ctx=ctx, raw=raw)

    for line in text_n.splitlines():
        low = _fold(line)
        if not any(
            k in low
            for k in ("sarfiyat", "tuketim", "tüketim", "kullanim", "kullanım", "miktar")
        ):
            continue
        if any(_fold(k) in low for k in _EXCLUDE_KEYWORDS):
            continue
        line_masked = re.sub(_M3_UNIT, " m_kup ", line, flags=re.IGNORECASE)
        for m in re.finditer(_NUM, line_masked):
            raw = m.group("num")
            if raw.strip() in {"3", "2"}:
                continue
            val = _parse_tr_number(raw)
            if val is None:
                continue
            sarfiyat = "sarfiyat" in low
            score = _score_candidate(val, line, False, sarfiyat=sarfiyat) + 1.0
            _add_candidate(found, val=val, score=score, ctx=line[:120], raw=raw)

    return sorted(found.values(), key=lambda x: (-x["skor"], -x["m3"]))


def extract_fatura_meta(text: str) -> dict[str, str]:
    """Fatura no ve dönem için basit çıkarım."""
    meta = {"fatura_no": "", "donem": ""}
    if not text:
        return meta
    t = _normalize_text(text)

    for pat in (
        r"(?:fatura\s*(?:no|numaras[iı]?|num\.?)\s*[:=]?\s*)([A-Z0-9\-/]{4,})",
        r"(?:belge\s*no\s*[:=]?\s*)([A-Z0-9\-/]{4,})",
        r"(?:FaturaNo|FATURA\s*NO)\s*[:=]?\s*([A-Z0-9\-/]{4,})",
    ):
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            meta["fatura_no"] = m.group(1).strip()
            break

    for pat in (
        r"(?:d[oö]nem|fatura\s*d[oö]nemi)\s*[:=]?\s*([0-9]{1,2}[.\/\-][0-9]{4}"
        r"(?:\s*[-–]\s*[0-9]{1,2}[.\/\-][0-9]{4})?)",
        r"(?:d[oö]nem|fatura\s*d[oö]nemi)\s*[:=]?\s*((?:Ocak|Şubat|Subat|Mart|Nisan|May[iı]s|"
        r"Haziran|Temmuz|A[gğ]ustos|Eyl[uü]l|Ekim|Kas[iı]m|Aral[iı]k)\s*20\d{2})",
        r"(20\d{2})\s*[-/]\s*(0?[1-9]|1[0-2])",
    ):
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            meta["donem"] = m.group(1).strip()
            break

    return meta


def _extract_text_pymupdf(data: bytes) -> str:
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore
        except ImportError:
            return ""
    parts: list[str] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            parts.append(page.get_text("text") or "")
            # Bazı faturalarda blocks daha iyi
            try:
                blocks = page.get_text("blocks") or []
                for b in blocks:
                    if len(b) >= 5 and isinstance(b[4], str):
                        parts.append(b[4])
            except Exception:
                pass
    return "\n".join(parts)


def _extract_text_pypdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return ""


_OCR_ENGINE = None


def _get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE
    from rapidocr_onnxruntime import RapidOCR

    _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def _box_center(box) -> tuple[float, float]:
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _ocr_image_to_items(img_bytes: bytes) -> list[dict[str, Any]]:
    """OCR → [{text, x, y, score}] konum bilgili liste."""
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return []

    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        max_side = 2800
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side))
        if max(img.size) < 900:
            scale = 900 / max(img.size)
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.Resampling.LANCZOS,
            )
        arr = np.array(img)
        engine = _get_ocr_engine()
        result, _ = engine(arr)
        if not result:
            return []
        items: list[dict[str, Any]] = []
        for item in result:
            if len(item) < 2 or not item[1]:
                continue
            box = item[0]
            cx, cy = _box_center(box)
            items.append(
                {
                    "text": str(item[1]).strip(),
                    "x": cx,
                    "y": cy,
                    "score": float(item[2]) if len(item) > 2 else 0.0,
                }
            )
        return items
    except Exception:
        return []


def _ocr_image_bytes(img_bytes: bytes) -> str:
    items = _ocr_image_to_items(img_bytes)
    return "\n".join(i["text"] for i in items)


def _is_sarfiyat_label(text: str) -> bool:
    t = _fold(_normalize_text(text)).replace(" ", "")
    return "sarfiyat" in t


def _extract_number_token(text: str) -> float | None:
    """Tek başına sayı veya başındaki sayı."""
    t = (text or "").strip().replace(" ", "")
    m = re.match(rf"^{_NUM}$", t)
    if not m:
        m = re.search(rf"{_NUM}", t)
        if not m:
            return None
        # "63-(1)" gibi madde numaralarını ele
        if re.search(r"madde|-\s*\(\d", t, re.I):
            return None
    return _parse_tr_number(m.group("num"))


def extract_sarfiyat_spatial(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    SARFİYAT etiketi ile aynı yatay satırdaki (benzer Y) ve sağındaki sayıyı bulur.
    ASKİ tarzı kolonlu faturalar için.
    """
    labels = [i for i in items if _is_sarfiyat_label(i["text"])]
    if not labels:
        return None

    best: dict[str, Any] | None = None
    for lab in labels:
        ly, lx = lab["y"], lab["x"]
        # Aynı satır: Y farkı küçük; sağda veya yakın solda sayı
        row = []
        for it in items:
            if it is lab:
                continue
            if abs(it["y"] - ly) > 35:
                continue
            # Sağ taraftaki hukuki metin kolonunu ele (çok sağda uzun metin)
            if it["x"] > lx + 450 and len(it["text"]) > 20:
                continue
            if re.search(r"(?i)madde|bor[cç]|kapama|a[cç]ma", it["text"]):
                continue
            val = _extract_number_token(it["text"])
            if val is None:
                continue
            if val < 0.01 or val > 5_000_000:
                continue
            # Tercih: etiketin sağında
            dx = it["x"] - lx
            row.append((dx, abs(it["y"] - ly), val, it))

        if not row:
            continue
        # Önce sağdaki en yakın, yoksa satırdaki en yakın
        right = [r for r in row if r[0] >= -20]
        pool = right if right else row
        pool.sort(key=lambda r: (r[1], abs(r[0])))
        dx, dy, val, it = pool[0]
        cand = {
            "m3": round(val, 2),
            "skor": 25.0,
            "baglam": f"SARFIYAT(satir) {lab['text']} -> {it['text']}",
            "ham": it["text"],
        }
        if best is None or cand["skor"] > best["skor"]:
            best = cand
    return best


def _ocr_pdf_pages_spatial(
    data: bytes, max_pages: int = 2
) -> tuple[str, list[dict[str, Any]]]:
    """PDF sayfalarından metin + konumlu OCR öğeleri."""
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore
        except ImportError:
            return "", []

    texts: list[str] = []
    all_items: list[dict[str, Any]] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            mat = pymupdf.Matrix(2.8, 2.8)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            items = _ocr_image_to_items(img_bytes)
            if items:
                # Sayfa ofseti (çok sayfalı birleştirme)
                y_off = i * 5000
                for it in items:
                    all_items.append({**it, "y": it["y"] + y_off})
                texts.append("\n".join(it["text"] for it in items))
    return "\n".join(texts), all_items


def _ocr_pdf_pages(data: bytes, max_pages: int = 4) -> str:
    text, _ = _ocr_pdf_pages_spatial(data, max_pages=max_pages)
    return text


def _needs_ocr(text: str) -> bool:
    """Metin var ama SARFİYAT / m³ yoksa OCR'a git."""
    if len((text or "").strip()) < 40:
        return True
    folded = _fold(_normalize_text(text))
    if "sarfiyat" in folded:
        # Metinde SARFIYAT var ama yanındaki sayı yoksa yine OCR
        aday = extract_m3_candidates(text)
        if aday and "sarfiyat" in _fold(aday[0].get("baglam") or ""):
            return False
        return True
    if extract_m3_candidates(text):
        return False
    return True


def _read_upload_bytes(uploaded_file: Any) -> tuple[bytes, str]:
    name = Path(getattr(uploaded_file, "name", "dosya")).name
    data = uploaded_file.getvalue()
    return data, name


def analyze_fatura_file(uploaded_file: Any) -> dict[str, Any]:
    """
    Yüklenen PDF/görseli analiz eder.
    Öncelik: SARFİYAT ile aynı satırdaki m³ (spatial OCR).
    """
    data, name = _read_upload_bytes(uploaded_file)
    ext = Path(name).suffix.lower()
    text = ""
    yontem = "none"
    uyarilar: list[str] = []
    spatial_items: list[dict[str, Any]] = []

    if ext == ".pdf":
        text = _extract_text_pymupdf(data) or _extract_text_pypdf(data)
        # ASKİ tarzı faturalarda metin dağınık → her zaman spatial OCR dene
        ocr_text, spatial_items = _ocr_pdf_pages_spatial(data, max_pages=2)
        if ocr_text.strip():
            text = (text + "\n" + ocr_text).strip()
            yontem = "ocr" if len((_extract_text_pymupdf(data) or "").strip()) < 40 else "mixed"
        elif text.strip():
            yontem = "text"
        else:
            uyarilar.append(
                "PDF'den metin okunamadı. SARFİYAT satırındaki m³ değerini elle girin."
            )
    elif ext in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}:
        spatial_items = _ocr_image_to_items(data)
        text = "\n".join(i["text"] for i in spatial_items)
        yontem = "ocr" if text.strip() else "none"
        if not text.strip():
            uyarilar.append(
                "Görselden metin okunamadı. SARFİYAT satırındaki m³ değerini elle girin."
            )
    else:
        uyarilar.append(f"Desteklenmeyen dosya türü: {ext}")

    adaylar = extract_m3_candidates(text)

    # Spatial SARFİYAT — en yüksek öncelik
    spatial = extract_sarfiyat_spatial(spatial_items) if spatial_items else None
    if spatial:
        # Başa koy / skor güncelle
        adaylar = [spatial] + [a for a in adaylar if abs(a["m3"] - spatial["m3"]) > 0.01]

    # MADDE / hukuki metin adaylarını ele
    adaylar = [
        a
        for a in adaylar
        if not re.search(r"(?i)madde|bor[cç]\s*neden|kapama", a.get("baglam") or "")
    ]

    meta = extract_fatura_meta(text)
    onerilen = adaylar[0]["m3"] if adaylar else None
    guven = "yok"
    sarfiyat_bulundu = bool(
        spatial
        or any("sarfiyat" in _fold(a.get("baglam") or "") for a in adaylar)
    )
    if adaylar:
        top = adaylar[0]["skor"]
        if spatial or top >= 12:
            guven = "yuksek"
        elif top >= 6:
            guven = "orta"
        else:
            guven = "dusuk"
            uyarilar.append(
                "Otomatik okunan değerlerin güveni düşük; faturadaki SARFİYAT (m³) ile doğrulayın."
            )
    elif text.strip():
        uyarilar.append(
            "Metin okundu ancak SARFİYAT / m³ değeri bulunamadı. "
            "Faturadaki SARFİYAT satırını kontrol edip değeri elle girin."
        )

    return {
        "dosya_adi": name,
        "yontem": yontem,
        "metin_uzunluk": len(text or ""),
        "adaylar": adaylar[:8],
        "onerilen_m3": onerilen,
        "fatura_no": meta.get("fatura_no") or "",
        "donem": meta.get("donem") or "",
        "uyarilar": uyarilar,
        "guven": guven,
        "metin_ornek": (text or "")[:800],
        "sarfiyat_bulundu": sarfiyat_bulundu,
    }


def analyze_fatura_path(path: str | Path) -> dict[str, Any]:
    """Diskteki dosya için analiz (test / geçmiş)."""
    p = Path(path)
    raw = p.read_bytes()

    class _F:
        name = p.name

        def getvalue(self) -> bytes:
            return raw

    return analyze_fatura_file(_F())
