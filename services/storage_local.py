"""Yerel JSON tabanlı rapor depolama."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raporlar"


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat(timespec="seconds")
    if isinstance(obj, date):
        return obj.isoformat()
    if hasattr(obj, "item"):  # numpy / pandas skaler
        try:
            return obj.item()
        except Exception:
            pass
    return str(obj)


def raporu_kaydet(payload: dict[str, Any]) -> str:
    """Raporu diske kaydeder; rapor id döner."""
    _ensure_dir()
    rapor_id = str(uuid.uuid4())[:8]
    kayit = {
        "id": rapor_id,
        "olusturma_tarihi": datetime.now().isoformat(timespec="seconds"),
        **payload,
    }
    path = DATA_DIR / f"{rapor_id}.json"
    path.write_text(
        json.dumps(kayit, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return rapor_id


def gecmis_raporlari_getir() -> list[dict[str, Any]]:
    _ensure_dir()
    raporlar: list[dict[str, Any]] = []
    for path in DATA_DIR.glob("*.json"):
        try:
            raporlar.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    raporlar.sort(key=lambda r: r.get("olusturma_tarihi", ""), reverse=True)
    return raporlar


def rapor_getir(rapor_id: str) -> dict[str, Any] | None:
    path = DATA_DIR / f"{rapor_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def rapor_sil(rapor_id: str) -> bool:
    path = DATA_DIR / f"{rapor_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
