"""Rapor üstbilgisi logoları — ADASO ile firma logosu aynı yükseklikte."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

# mm — yeşil çizginin (y≈24) üstünde güvenli alan
HEADER_LOGO_MAX_HEIGHT_MM = 9.0
HEADER_LOGO_MAX_WIDTH_MM = 48.0


def _pixel_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def fit_logo_mm(
    path: str | Path,
    target_height_mm: float,
    max_width_mm: float = HEADER_LOGO_MAX_WIDTH_MM,
) -> tuple[float, float]:
    """En-boy oranını koruyarak hedef yüksekliğe sığdır; genişlik üst sınırını aşarsa küçült."""
    p = Path(path)
    if not p.exists():
        return 0.0, 0.0
    w_px, h_px = _pixel_size(p)
    if w_px <= 0 or h_px <= 0:
        return 0.0, 0.0

    aspect = w_px / h_px
    h_mm = float(target_height_mm)
    w_mm = h_mm * aspect
    if w_mm > max_width_mm:
        w_mm = max_width_mm
        h_mm = w_mm / aspect
    return w_mm, h_mm


def header_logo_pair_mm(
    adaso_path: str | Path,
    firma_path: str | Path | None,
) -> tuple[tuple[float, float], tuple[float, float] | None]:
    """
    ADASO referans yüksekliğini hesapla; firma logosunu aynı yüksekliğe getir.
    Dönüş: ((adaso_w, adaso_h), (firma_w, firma_h) | None)
    """
    adaso_p = Path(adaso_path)
    if not adaso_p.exists():
        return (0.0, 0.0), None

    adaso_w, adaso_h = fit_logo_mm(adaso_p, HEADER_LOGO_MAX_HEIGHT_MM)
    if adaso_h <= 0:
        return (0.0, 0.0), None

    if not firma_path:
        return (adaso_w, adaso_h), None
    firma_p = Path(firma_path)
    if not firma_p.exists():
        return (adaso_w, adaso_h), None

    # Firma: ADASO ile birebir aynı yükseklik
    firma_w, firma_h = fit_logo_mm(firma_p, adaso_h)
    return (adaso_w, adaso_h), (firma_w, firma_h)
