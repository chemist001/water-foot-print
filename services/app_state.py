"""Oturum verilerinin diske kalıcı saklanması (firma, tablolar, hesaplama)."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from services.firma_state import _DEFAULTS, ensure_firma_profil, save_firma_profil
from services.report_utils import parse_rapor_tarihi
from services.tenant_paths import app_state_path


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    return str(obj)


def _df_to_records(df: Any) -> list[dict]:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.to_dict(orient="records")
    return []


def _records_to_df(records: Any, columns: list[str]) -> pd.DataFrame:
    if isinstance(records, list) and records:
        return pd.DataFrame(records)
    return pd.DataFrame(columns=columns)


def save_app_state() -> None:
    """Mevcut oturumu diske yazar (firma/tenant bazlı)."""
    path = app_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    profil = ensure_firma_profil()
    rapor_t = profil.get("rapor_tarihi")
    if hasattr(rapor_t, "isoformat"):
        profil = {**profil, "rapor_tarihi": rapor_t.isoformat()}

    payload = {
        "firma_profil": profil,
        "sorumlu_kisiler_tablosu": _df_to_records(st.session_state.get("sorumlu_kisiler_tablosu")),
        "hedef_tablosu": _df_to_records(st.session_state.get("hedef_tablosu")),
        "sistem_siniri_tablosu": _df_to_records(st.session_state.get("sistem_siniri_tablosu")),
        "veri_kalitesi_aciklama": st.session_state.get("veri_kalitesi_aciklama", ""),
        "calc_snapshot": st.session_state.get("calc_snapshot"),
        "kpi_snapshot": st.session_state.get("kpi_snapshot"),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )


def load_app_state() -> bool:
    """Diskten oturumu yükler (mevcut tenant). Başarılıysa True."""
    path = app_state_path()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    profil = data.get("firma_profil") or {}
    if isinstance(profil, dict):
        merged = dict(_DEFAULTS)
        merged.update({k: v for k, v in profil.items() if k in _DEFAULTS})
        rt = parse_rapor_tarihi(merged.get("rapor_tarihi"))
        merged["rapor_tarihi"] = rt
        save_firma_profil(**merged)

    sorumlular = data.get("sorumlu_kisiler_tablosu")
    if sorumlular:
        st.session_state.sorumlu_kisiler_tablosu = _records_to_df(
            sorumlular, ["Sorumlu Kişi", "Görev", "İletişim"]
        )

    hedefler = data.get("hedef_tablosu")
    if hedefler:
        st.session_state.hedef_tablosu = _records_to_df(hedefler, ["Hedef Yılı", "Hedef Açıklaması"])

    sistem = data.get("sistem_siniri_tablosu")
    if sistem:
        st.session_state.sistem_siniri_tablosu = _records_to_df(
            sistem,
            ["Bileşen", "Kaynak", "Veri Kaynağı", "Veri Doğrulama", "Açıklama (Diğer)"],
        )

    if data.get("veri_kalitesi_aciklama"):
        st.session_state.veri_kalitesi_aciklama = data["veri_kalitesi_aciklama"]

    snap = data.get("calc_snapshot")
    if isinstance(snap, dict):
        st.session_state.calc_snapshot = snap
        _restore_calc_from_snapshot(snap)

    kpi = data.get("kpi_snapshot")
    if isinstance(kpi, dict):
        st.session_state.kpi_snapshot = kpi
        _restore_kpi_from_snapshot(kpi)

    return True


def _restore_calc_from_snapshot(snap: dict) -> None:
    for key in (
        "mavi_sebeke", "mavi_yeralti", "mavi_kaynak", "yesil_yagmur", "gri_debi",
        "sonuc_mavi", "sonuc_yesil", "sonuc_gri", "sonuc_toplam",
        "gri_kritik_parametre", "gri_parametre_sonuclari", "hesaplandi",
    ):
        if key in snap:
            st.session_state[key] = snap[key]

    gri_df = snap.get("gri_parametre_df")
    if isinstance(gri_df, list) and gri_df:
        st.session_state.gri_parametre_df = pd.DataFrame(gri_df)


def _restore_kpi_from_snapshot(kpi: dict) -> None:
    for key, val in kpi.items():
        st.session_state[key] = val


def build_calc_snapshot() -> dict:
    """Hesaplama anındaki girdileri ve sonuçları dondurur."""
    df = st.session_state.get("gri_parametre_df")
    gri_records = df.to_dict(orient="records") if isinstance(df, pd.DataFrame) else []
    return {
        "mavi_sebeke": st.session_state.get("mavi_sebeke", 0.0),
        "mavi_yeralti": st.session_state.get("mavi_yeralti", 0.0),
        "mavi_kaynak": st.session_state.get("mavi_kaynak", 0.0),
        "yesil_yagmur": st.session_state.get("yesil_yagmur", 0.0),
        "gri_debi": st.session_state.get("gri_debi", 0.0),
        "gri_parametre_df": gri_records,
        "sonuc_mavi": st.session_state.get("sonuc_mavi"),
        "sonuc_yesil": st.session_state.get("sonuc_yesil"),
        "sonuc_gri": st.session_state.get("sonuc_gri"),
        "sonuc_toplam": st.session_state.get("sonuc_toplam"),
        "gri_kritik_parametre": st.session_state.get("gri_kritik_parametre"),
        "gri_parametre_sonuclari": st.session_state.get("gri_parametre_sonuclari"),
        "hesaplandi": st.session_state.get("hesaplandi", False),
        "snapshot_zamani": datetime.now().isoformat(timespec="seconds"),
    }


def build_kpi_snapshot() -> dict:
    return {
        "kpi_uretim": st.session_state.get("kpi_uretim", 0.0),
        "kpi_uretim_birimi": st.session_state.get("kpi_uretim_birimi", "ton"),
        "kpi_calisma_gunu": st.session_state.get("kpi_calisma_gunu", 0.0),
        "kpi_personel": st.session_state.get("kpi_personel", 0.0),
        "kpi_evsel_su": st.session_state.get("kpi_evsel_su", 0.0),
        "kpi_sulama": st.session_state.get("kpi_sulama", 0.0),
        "kpi_yangin": st.session_state.get("kpi_yangin", 0.0),
        "kpi_arac": st.session_state.get("kpi_arac", 0.0),
        "kpi_geri": st.session_state.get("kpi_geri", 0.0),
        "kpi_evsel_atik": st.session_state.get("kpi_evsel_atik", 0.0),
        "kpi_net_proses": st.session_state.get("kpi_net_proses"),
        "kpi_spesifik_su": st.session_state.get("kpi_spesifik_su"),
        "kpi_spesifik_atiksu": st.session_state.get("kpi_spesifik_atiksu"),
        "kpi_evsel_su_gosterge": st.session_state.get("kpi_evsel_su_gosterge"),
        "kpi_evsel_atiksu_gosterge": st.session_state.get("kpi_evsel_atiksu_gosterge"),
        "kpi_hesaplandi": st.session_state.get("kpi_hesaplandi", False),
    }


def calc_inputs_changed() -> bool:
    """Widget girdileri son hesaplamadan farklı mı?"""
    snap = st.session_state.get("calc_snapshot")
    if not snap or not snap.get("hesaplandi"):
        return False
    for key in ("mavi_sebeke", "mavi_yeralti", "mavi_kaynak", "yesil_yagmur", "gri_debi"):
        if float(st.session_state.get(key, 0) or 0) != float(snap.get(key, 0) or 0):
            return True

    # Gri parametre tablosu
    cur_df = st.session_state.get("_gri_parametre_edited", st.session_state.get("gri_parametre_df"))
    snap_rows = snap.get("gri_parametre_df") or []
    if isinstance(cur_df, pd.DataFrame):
        cur_rows = cur_df.to_dict(orient="records") if not cur_df.empty else []
    else:
        cur_rows = []

    def _norm(rows: list) -> list[tuple]:
        out = []
        for r in rows:
            try:
                out.append(
                    (
                        str(r.get("Parametre") or r.get("ad") or "").strip(),
                        round(float(r.get("C_eff (mg/L)", r.get("C_eff", 0)) or 0), 6),
                        round(float(r.get("C_max (mg/L)", r.get("C_max", 0)) or 0), 6),
                        round(float(r.get("C_nat (mg/L)", r.get("C_nat", 0)) or 0), 6),
                    )
                )
            except (TypeError, ValueError):
                out.append(("?", 0.0, 0.0, 0.0))
        return sorted(out)

    if _norm(cur_rows) != _norm(snap_rows):
        return True
    return False


def load_report_into_session(report: dict) -> None:
    """Kayıtlı raporu oturuma yükler."""
    firma_keys = (
        "firma_adi", "sektor", "lokasyon", "rapor_yili",
        "yetkili", "email", "telefon", "logo_path",
    )
    profil = {k: report.get(k, "") for k in firma_keys}
    profil["rapor_tarihi"] = parse_rapor_tarihi(report.get("rapor_tarihi"))
    save_firma_profil(**profil)

    st.session_state.sonuc_mavi = report.get("mavi_su")
    st.session_state.sonuc_yesil = report.get("yesil_su")
    st.session_state.sonuc_gri = report.get("gri_su")
    st.session_state.sonuc_toplam = report.get("toplam_su")
    st.session_state.gri_kritik_parametre = report.get("gri_kritik")
    st.session_state.gri_parametre_sonuclari = report.get("gri_detay") or []
    st.session_state.hesaplandi = report.get("mavi_su") is not None

    for key in ("mavi_sebeke", "mavi_yeralti", "mavi_kaynak", "yesil_yagmur", "gri_debi"):
        if key in report:
            st.session_state[key] = report[key]

    # Gri detay → editor tablosu
    gri_detay = report.get("gri_detay") or []
    if gri_detay:
        rows = []
        for d in gri_detay:
            rows.append(
                {
                    "Parametre": d.get("Parametre") or d.get("ad") or "",
                    "C_eff (mg/L)": float(d.get("C_eff") or 0),
                    "C_max (mg/L)": float(d.get("C_max") or 0),
                    "C_nat (mg/L)": float(d.get("C_nat") or 0),
                }
            )
        st.session_state.gri_parametre_df = pd.DataFrame(rows)

    if report.get("sorumlular"):
        st.session_state.sorumlu_kisiler_tablosu = pd.DataFrame(report["sorumlular"])
    if report.get("hedefler"):
        st.session_state.hedef_tablosu = pd.DataFrame(report["hedefler"])
    if report.get("sistem_siniri"):
        st.session_state.sistem_siniri_tablosu = pd.DataFrame(report["sistem_siniri"])
    if report.get("veri_kalitesi"):
        st.session_state.veri_kalitesi_aciklama = report["veri_kalitesi"]
    if report.get("mavi_kanit"):
        st.session_state.mavi_kanit_ozet = report["mavi_kanit"]

    kpi = report.get("kpi") or {}
    if kpi.get("spesifik_su") is not None:
        st.session_state.kpi_hesaplandi = True
        st.session_state.kpi_spesifik_su = kpi.get("spesifik_su")
        st.session_state.kpi_spesifik_atiksu = kpi.get("spesifik_atiksu")
        st.session_state.kpi_evsel_su_gosterge = kpi.get("evsel_su")
        st.session_state.kpi_evsel_atiksu_gosterge = kpi.get("evsel_atiksu")

    gri_df = st.session_state.get("gri_parametre_df")
    gri_records = gri_df.to_dict(orient="records") if isinstance(gri_df, pd.DataFrame) else []
    st.session_state.calc_snapshot = {
        "mavi_sebeke": report.get("mavi_sebeke", 0.0),
        "mavi_yeralti": report.get("mavi_yeralti", 0.0),
        "mavi_kaynak": report.get("mavi_kaynak", 0.0),
        "yesil_yagmur": report.get("yesil_yagmur", 0.0),
        "gri_debi": report.get("gri_debi", 0.0),
        "gri_parametre_df": gri_records,
        "sonuc_mavi": report.get("mavi_su"),
        "sonuc_yesil": report.get("yesil_su"),
        "sonuc_gri": report.get("gri_su"),
        "sonuc_toplam": report.get("toplam_su"),
        "gri_kritik_parametre": report.get("gri_kritik"),
        "gri_parametre_sonuclari": report.get("gri_detay") or [],
        "hesaplandi": True,
        "snapshot_zamani": report.get("olusturma_tarihi", ""),
    }
    save_app_state()
