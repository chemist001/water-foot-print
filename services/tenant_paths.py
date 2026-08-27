"""Firma / oturum bazlı yerel depolama yolları."""

from __future__ import annotations

from pathlib import Path

from services import auth

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def tenant_storage_key() -> str:
    """Bulut: firma_id (yoksa user_id). Yerel: 'local'."""
    if auth.is_local_mode() or not auth.is_logged_in():
        return "local"
    user = auth.current_user()
    if user and user.firma_id:
        return str(user.firma_id)
    if user and user.id:
        return f"user_{user.id}"
    return "local"


def tenant_dir() -> Path:
    key = tenant_storage_key()
    if key == "local":
        # Geriye uyum: yerel tek kullanıcı kök data/
        return DATA
    d = DATA / "tenants" / key
    d.mkdir(parents=True, exist_ok=True)
    return d


def app_state_path() -> Path:
    if tenant_storage_key() == "local":
        return DATA / "app_state.json"
    return tenant_dir() / "app_state.json"


def logo_dir() -> Path:
    if tenant_storage_key() == "local":
        d = DATA / "logos"
    else:
        d = tenant_dir() / "logos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def logo_file() -> Path:
    return logo_dir() / "firma_logo.png"
