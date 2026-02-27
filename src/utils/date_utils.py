"""
Datums-Hilfsfunktionen.
"""


def format_date_german(date_str: str) -> str:
    """Konvertiert ISO-Datum/Datetime ins deutsche Format (DD.MM.YYYY).

    Unterstuetzt: 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SS', 'YYYY-MM-DD HH:MM:SS'
    """
    if not date_str:
        return ""
    try:
        date_part = date_str.strip()
        if 'T' in date_part:
            date_part = date_part.split('T')[0]
        elif ' ' in date_part:
            date_part = date_part.split(' ')[0]
        parts = date_part.split('-')
        if len(parts) == 3:
            year, month, day = parts
            return f"{day}.{month}.{year}"
    except (ValueError, IndexError):
        pass
    return date_str
