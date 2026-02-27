"""
Relevanz-Bestimmung für Provisionsbuchungen.

Reine Geschäftsregeln – bestimmt ob ein Datensatz für die
Provisionsabrechnung relevant ist oder nicht.

Regeln:
  Allianz:   courtage_rate < 20 → irrelevant
  SwissLife: buchungsart_raw not in ('BARM', 'APG') → irrelevant
  VB:        buchungsart_raw = 'dy' → irrelevant
             konditionssatz not in ('15', '35', '50') → irrelevant
"""

from typing import Optional


# VU-spezifische Schwellwerte
ALLIANZ_MIN_COURTAGE_RATE = 20.0
SWISSLIFE_AP_ARTEN = frozenset({'BARM', 'APG'})
VB_IRRELEVANT_ART = 'dy'
VB_RELEVANTE_KONDITIONSSAETZE = frozenset({'15', '35', '50'})


def is_commission_relevant(
    vu_name: Optional[str],
    courtage_rate: Optional[float] = None,
    buchungsart_raw: Optional[str] = None,
    konditionssatz: Optional[str] = None,
) -> bool:
    """Bestimmt ob eine Provisionsbuchung relevant ist.

    Args:
        vu_name: Name des Versicherers (Allianz, SwissLife, VB).
        courtage_rate: Courtagesatz (Allianz Spalte K).
        buchungsart_raw: Rohwert der Buchungsart.
        konditionssatz: Konditionssatz (VB Spalte M).

    Returns:
        True wenn relevant, False wenn irrelevant.
    """
    if not vu_name:
        return True

    vu = vu_name.strip()

    if vu == 'Allianz':
        return _is_allianz_relevant(courtage_rate)
    elif vu == 'SwissLife':
        return _is_swisslife_relevant(buchungsart_raw)
    elif vu == 'VB':
        return _is_vb_relevant(buchungsart_raw, konditionssatz)

    return True


def _is_allianz_relevant(courtage_rate: Optional[float]) -> bool:
    """Allianz: courtage_rate muss >= 20 sein."""
    if courtage_rate is None:
        return True
    return courtage_rate >= ALLIANZ_MIN_COURTAGE_RATE


def _is_swisslife_relevant(buchungsart_raw: Optional[str]) -> bool:
    """SwissLife: Buchungsart muss BARM oder APG sein.

    Fehlende/leere Buchungsart = irrelevant (Gleichverhalten mit PHP-Backend).
    """
    if not buchungsart_raw or not buchungsart_raw.strip():
        return False
    return buchungsart_raw.strip().upper() in SWISSLIFE_AP_ARTEN


def _is_vb_relevant(
    buchungsart_raw: Optional[str],
    konditionssatz: Optional[str],
) -> bool:
    """VB: 'dy' ist irrelevant; Konditionssatz muss 15, 35 oder 50 sein."""
    if buchungsart_raw and buchungsart_raw.strip().lower() == VB_IRRELEVANT_ART:
        return False
    if konditionssatz is not None:
        kond = str(konditionssatz).strip()
        if kond and kond not in VB_RELEVANTE_KONDITIONSSAETZE:
            return False
    return True


def classify_buchungsart(vu_name: str, buchungsart_raw: Optional[str]) -> str:
    """Buchungsart in einheitlichen Enum-Wert übersetzen.

    Returns: 'ap', 'bp', 'rueckbelastung', 'sonstige'
    """
    s = str(buchungsart_raw or '').strip().upper()
    if not s:
        return 'ap'

    if s in ('RB', 'ST', 'STORNO', 'RÜCK', 'RUECK', 'RÜCKBELASTUNG'):
        return 'rueckbelastung'
    if s in ('BP', 'FP', 'FOLGEPROV', 'BESTANDSPROV', 'BEST'):
        return 'bp'
    if s in ('AP', 'EV', 'EV-PF', 'ABSCHL', 'ABSCHLUSSPROV'):
        return 'ap'

    if vu_name == 'SwissLife':
        if s in SWISSLIFE_AP_ARTEN:
            return 'ap'

    if vu_name == 'VB':
        if s == VB_IRRELEVANT_ART.upper():
            return 'sonstige'

    return 'sonstige'
