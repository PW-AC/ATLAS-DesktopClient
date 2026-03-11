# -*- coding: utf-8 -*-
"""Workforce UI - Hilfsfunktionen."""

from datetime import datetime


def format_date_de(value: str) -> str:
    """
    Formatiert ISO-Datums-/Zeit-String ins deutsche Format.

    - "2024-03-10T14:30:00" / "2024-03-10 14:30:00" -> "10.03.2024 14:30"
    - "2024-03-10" -> "10.03.2024"
    - "-", "?", leer -> unveraendert zurueck
    """
    if not value or str(value).strip() in ("-", "?"):
        return value if value else "-"
    try:
        s = str(value).strip()
        # ISO mit T: 2024-03-10T14:30:00 oder 2024-03-10T14:30:00.123Z
        if "T" in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00")[:19])
            return dt.strftime("%d.%m.%Y %H:%M")
        # Space-Format (Backend): 2024-03-10 14:30:00 oder 2024-03-10 14:30
        if len(s) >= 19 and s[10] == " ":
            dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d.%m.%Y %H:%M")
        if len(s) >= 16 and s[10] == " ":
            dt = datetime.strptime(s[:16], "%Y-%m-%d %H:%M")
            return dt.strftime("%d.%m.%Y %H:%M")
        # Nur Datum
        if len(s) >= 10:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        return value
    except (ValueError, TypeError):
        return value
