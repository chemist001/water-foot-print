"""Rapor üretimi için ortak yardımcılar."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def format_rapor_tarihi(value: Any) -> str:
    """date, datetime veya ISO/JSON string → dd.mm.yyyy."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "Belirtilmedi"
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, str):
        s = value.strip()
        if "T" in s:
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00")[:19]).strftime("%d.%m.%Y")
            except ValueError:
                pass
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(s[:10], fmt).strftime("%d.%m.%Y")
            except ValueError:
                continue
        return s
    return str(value)


def parse_rapor_tarihi(value: Any) -> date | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")[:19]).date()
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(s[:10], fmt).date()
            except ValueError:
                continue
    return None
