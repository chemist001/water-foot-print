"""Rapor depolama: yerel disk veya Supabase (firma izolasyonu)."""

from __future__ import annotations

from typing import Any

from services import auth
from services import storage_local as local


def use_cloud() -> bool:
    return (
        auth.cloud_configured()
        and not auth.is_local_mode()
        and auth.is_logged_in()
        and auth.current_user() is not None
        and auth.current_user().firma_id is not None
    )


def raporu_kaydet(payload: dict[str, Any]) -> str:
    from services.demo import is_demo

    if is_demo():
        raise RuntimeError("Demo sürümünde rapor kaydı kapalıdır.")
    if use_cloud():
        return _cloud_kaydet(payload)
    return local.raporu_kaydet(payload)


def gecmis_raporlari_getir() -> list[dict[str, Any]]:
    if use_cloud():
        return _cloud_liste()
    return local.gecmis_raporlari_getir()


def rapor_getir(rapor_id: str) -> dict[str, Any] | None:
    if use_cloud():
        return _cloud_getir(rapor_id)
    return local.rapor_getir(rapor_id)


def rapor_sil(rapor_id: str) -> bool:
    if use_cloud():
        return _cloud_sil(rapor_id)
    return local.rapor_sil(rapor_id)


def _cloud_client():
    client = auth.get_supabase()
    if not client:
        raise RuntimeError("Supabase client yok")
    sess = __import__("streamlit").session_state.get("sb_session")
    if sess:
        try:
            client.auth.set_session(sess["access_token"], sess["refresh_token"])
        except Exception:
            pass
    return client


def _cloud_kaydet(payload: dict[str, Any]) -> str:
    user = auth.current_user()
    assert user and user.firma_id
    client = _cloud_client()
    calc = payload.get("calc") or {}
    row = {
        "firma_id": user.firma_id,
        "user_id": user.id,
        "firma_adi": payload.get("firma_adi") or user.firma_adi,
        "mavi_su": float(calc.get("mavi") or 0),
        "yesil_su": float(calc.get("yesil") or 0),
        "gri_su": float(calc.get("gri") or 0),
        "toplam_su": float(calc.get("toplam") or 0),
        "rapor_yili": str(payload.get("rapor_yili") or ""),
        "payload": payload,
    }
    res = client.table("raporlar").insert(row).execute()
    if not res.data:
        raise RuntimeError("Bulut kaydı başarısız")
    return str(res.data[0]["id"])


def _cloud_liste() -> list[dict[str, Any]]:
    client = _cloud_client()
    # RLS: firma kendi kayıtlarını, ADASO hepsini görür
    res = (
        client.table("raporlar")
        .select("*")
        .order("olusturma_tarihi", desc=True)
        .execute()
    )
    out: list[dict[str, Any]] = []
    for row in res.data or []:
        out.append(_row_to_rapor(row))
    return out


def _cloud_getir(rapor_id: str) -> dict[str, Any] | None:
    client = _cloud_client()
    res = (
        client.table("raporlar")
        .select("*")
        .eq("id", rapor_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    return _row_to_rapor(res.data[0])


def _cloud_sil(rapor_id: str) -> bool:
    client = _cloud_client()
    try:
        client.table("raporlar").delete().eq("id", rapor_id).execute()
        return True
    except Exception:
        return False


def _row_to_rapor(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    merged = {
        **payload,
        "id": str(row.get("id") or payload.get("id") or ""),
        "olusturma_tarihi": str(
            row.get("olusturma_tarihi") or payload.get("olusturma_tarihi") or ""
        ),
        "firma_adi": row.get("firma_adi") or payload.get("firma_adi"),
        "mavi_su": row.get("mavi_su"),
        "yesil_su": row.get("yesil_su"),
        "gri_su": row.get("gri_su"),
        "toplam_su": row.get("toplam_su"),
        "rapor_yili": row.get("rapor_yili") or payload.get("rapor_yili"),
        "_cloud": True,
        "_firma_id": row.get("firma_id"),
    }
    return merged
