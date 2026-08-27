"""Firma profili — widget state silinse bile kalıcı saklama."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import streamlit as st

from services.tenant_paths import logo_dir, logo_file

YILLAR = ["2024", "2025", "2026", "2027", "2028", "2029", "2030"]

_DEFAULTS: dict[str, Any] = {
    "firma_adi": "",
    "sektor": "",
    "lokasyon": "",
    "rapor_yili": "2026",
    "yetkili": "",
    "email": "",
    "telefon": "",
    "rapor_tarihi": None,
    "logo_path": "",
}


def ensure_firma_profil() -> dict[str, Any]:
    if "firma_profil" not in st.session_state:
        st.session_state.firma_profil = dict(_DEFAULTS)
    if "logo_path" not in st.session_state.firma_profil:
        st.session_state.firma_profil["logo_path"] = ""
    # Sadece bu tenant'ın logosu varsa bağla
    lf = logo_file()
    if lf.exists() and not st.session_state.firma_profil.get("logo_path"):
        st.session_state.firma_profil["logo_path"] = str(lf.resolve())
    return st.session_state.firma_profil


def get_firma() -> dict[str, Any]:
    return dict(ensure_firma_profil())


def firma_adi_var() -> bool:
    return bool(str(get_firma().get("firma_adi", "")).strip())


def save_firma_profil(**kwargs: Any) -> None:
    profil = ensure_firma_profil()
    for key, value in kwargs.items():
        if key in _DEFAULTS:
            profil[key] = value
    st.session_state.firma_profil = profil


def save_firma_logo(uploaded_file: Any) -> str:
    """Yüklenen logoyu PNG olarak tenant logos altına kaydeder."""
    from PIL import Image

    dest_dir = logo_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    raw = uploaded_file.getvalue()
    img = Image.open(io.BytesIO(raw))
    if img.mode in ("RGBA", "P"):
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    max_side = 1600
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    dest = logo_file().resolve()
    img.save(dest, format="PNG", optimize=True)
    save_firma_profil(logo_path=str(dest))
    return str(dest)


def clear_firma_logo() -> None:
    for p in logo_dir().glob("firma_logo.*"):
        try:
            p.unlink()
        except OSError:
            pass
    legacy = Path(__file__).resolve().parent.parent / "logos" / "firma_logo.png"
    if legacy.exists():
        try:
            legacy.unlink()
        except OSError:
            pass
    save_firma_profil(logo_path="")


def get_logo_path() -> str | None:
    path = (get_firma().get("logo_path") or "").strip()
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates.append(logo_file())
    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            resolved = str(p.resolve())
            if get_firma().get("logo_path") != resolved:
                save_firma_profil(logo_path=resolved)
            return resolved
    return None
