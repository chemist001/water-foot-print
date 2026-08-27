"""Su ayak izi hesaplama yardımcıları."""

from __future__ import annotations

import math


def format_m3(value: float | None, birim: str = "m³") -> str:
    if value is None:
        return f"— {birim}"
    return f"{value:,.2f} {birim}".replace(",", "X").replace(".", ",").replace("X", ".")


def hesapla_mavi_su(sebeke: float, kuyu: float, kaynak: float) -> float:
    return float(sebeke) + float(kuyu) + float(kaynak)


def hesapla_yesil_su(yagmur: float) -> float:
    return float(yagmur)


def hesapla_gri_parametre(
    V: float, C_eff: float, C_max: float, C_nat: float
) -> tuple[float | None, str | None]:
    for name, val in (("V", V), ("C_eff", C_eff), ("C_max", C_max), ("C_nat", C_nat)):
        try:
            f = float(val)
        except (TypeError, ValueError):
            return None, f"{name} geçersiz sayı."
        if not math.isfinite(f):
            return None, f"{name} boş veya geçersiz (NaN/Inf)."
    if C_max <= C_nat:
        return None, "C_max, C_nat değerinden büyük olmalıdır (alıcı ortam kapasitesi)."
    if C_eff < C_nat:
        return 0.0, None  # Seyreltme gerekmiyor — Hoekstra: negatif → 0
    denominator = C_max - C_nat
    if abs(denominator) < 1e-12:
        return None, "C_max − C_nat = 0 (sıfıra bölme). C_max ve C_nat farklı olmalıdır."
    raw = float(V) * (float(C_eff) - float(C_nat)) / denominator
    return max(0.0, float(raw)), None


def hesapla_gri_su(
    V: float,
    parametreler: list[dict],
) -> tuple[float | None, str | None, list[dict], list[str]]:
    hatalar: list[str] = []
    detaylar: list[dict] = []

    try:
        V = float(V)
    except (TypeError, ValueError):
        return None, None, [], ["Atıksu debisi (V) geçersiz."]
    if not math.isfinite(V):
        return None, None, [], ["Atıksu debisi (V) geçersiz."]
    if V < 0:
        return None, None, [], ["Atıksu debisi (V) negatif olamaz."]
    if V == 0:
        return 0.0, "—", [], []

    if not parametreler:
        return None, None, [], ["Atıksu debisi > 0 iken en az bir kirlilik parametresi girilmelidir."]

    for p in parametreler:
        ad = str(p.get("ad", "")).strip() or "İsimsiz"
        try:
            C_eff = float(p["C_eff"])
            C_max = float(p["C_max"])
            C_nat = float(p["C_nat"])
        except (TypeError, ValueError, KeyError):
            hatalar.append(f"{ad}: Geçersiz sayısal değer.")
            continue
        if not all(math.isfinite(x) for x in (C_eff, C_max, C_nat)):
            hatalar.append(f"{ad}: Boş veya geçersiz hücre (NaN).")
            continue

        sonuc, hata = hesapla_gri_parametre(V, C_eff, C_max, C_nat)
        if hata:
            hatalar.append(f"{ad}: {hata}")
            continue

        detaylar.append(
            {
                "Parametre": ad,
                "C_eff": C_eff,
                "C_max": C_max,
                "C_nat": C_nat,
                "Gri Su (m³/yıl)": sonuc,
            }
        )

    if not detaylar:
        return None, None, detaylar, hatalar or ["Hesaplanabilir parametre bulunamadı."]

    kritik = max(detaylar, key=lambda x: x["Gri Su (m³/yıl)"])
    return kritik["Gri Su (m³/yıl)"], kritik["Parametre"], detaylar, hatalar
