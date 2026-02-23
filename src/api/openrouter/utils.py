"""
Hilfsfunktionen fuer die OpenRouter KI-Pipeline.

Enthaelt JSON-Parsing, Slug-Generierung und Keyword-Conflict-Hints.
"""

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def _safe_json_loads(s: str) -> Optional[dict]:
    """
    Robustes JSON-Parsing mit Fallbacks.
    
    Behandelt:
    - Whitespace
    - Codefences (```json ... ```)
    - Prefixes/Suffixes
    
    Args:
        s: String der JSON enthalten sollte
        
    Returns:
        Geparstes dict oder None
    """
    if not s:
        return None
    
    s = s.strip()
    
    # Codefences entfernen
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s, flags=re.IGNORECASE)
    s = s.strip()
    
    # Direkter Versuch
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    
    # Fallback: Erstes {...} Objekt extrahieren
    match = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    logger.warning(f"JSON-Parsing fehlgeschlagen: {s[:100]}...")
    return None


def slug_de(s: str, max_len: int = 40) -> str:
    """
    Erzeugt einen sicheren Dateinamen-Slug aus einem deutschen String.
    
    - Ersetzt Sonderzeichen durch Unterstriche
    - Normalisiert & zu 'und'
    - Entfernt doppelte Unterstriche
    - Begrenzt die Laenge
    
    Args:
        s: Eingabestring
        max_len: Maximale Laenge
        
    Returns:
        Sicherer Slug
    """
    s = (s or "").strip()
    
    # Spezielle Ersetzungen
    s = s.replace("&", "und")
    s = s.replace("+", "")
    
    # Nur erlaubte Zeichen behalten, Rest wird _
    s = re.sub(r"[^\wäöüÄÖÜß-]+", "_", s, flags=re.UNICODE)
    
    # Doppelte Unterstriche entfernen
    s = re.sub(r"_+", "_", s)
    
    # Fuehrende/Trailing Underscores entfernen
    s = s.strip("_")
    
    # Laenge begrenzen
    if len(s) > max_len:
        s = s[:max_len].rstrip("_")
    
    return s if s else "Unbekannt"


# ============================================================================
# KEYWORD-CONFLICT-HINTS (lokal, 0 Tokens, ~0.1ms CPU)
# Generiert Hints NUR bei widerspruechlichen Keywords im PDF-Text.
# Die KI entscheidet weiterhin selbst -- Hints sind reine Zusatz-Information.
# ============================================================================

_COURTAGE_KEYWORDS = [
    'vergütungsdatenblatt', 'verguetungsdatenblatt',
    'vergütungsabrechnung', 'verguetungsabrechnung',
    'provisionsabrechnung', 'courtageabrechnung',
    'courtagenote', 'provisionsnote',
    'vermittlerabrechnung', 'inkassoprovision',
]
_SACH_KEYWORDS = [
    'unfallversicherung', 'haftpflichtversicherung',
    'hausratversicherung', 'wohngebäudeversicherung',
    'rechtsschutzversicherung', 'kfz-versicherung',
    'sachversicherung',
]
_LEBEN_KEYWORDS = [
    'lebensversicherung', 'rentenversicherung',
    'berufsunfähigkeit', 'altersvorsorge', 'altersversorgung',
    'pensionskasse', 'risikoleben', 'sterbegeld',
]
_KRANKEN_KEYWORDS = [
    'krankenversicherung', 'krankenzusatz',
    'zahnzusatz', 'krankentagegeld',
]


def _build_keyword_hints(text: str) -> str:
    """Generiert Hint-String NUR bei Keyword-Konflikten oder bekannten Problemmustern.
    
    Bei eindeutigen oder keinen Keywords: leerer String (0 extra Tokens).
    Laeuft lokal auf bereits extrahiertem Text (~0.1ms reine CPU-Arbeit).
    
    Konflikt-Faelle:
    - Courtage-Keyword + Leben/Sach/Kranken-Keyword gleichzeitig
    - "Kontoauszug" + "Provision"/"Courtage" (ohne sonstigen Courtage-Keyword)
    - Sach-Keyword allein (KI hat hier nachweislich versagt -> Sicherheits-Hint)
    
    Args:
        text: Bereits extrahierter PDF-Text (aus _extract_relevant_text)
        
    Returns:
        Hint-String (z.B. '[KEYWORD-ANALYSE: ...]\\n\\n') oder leerer String
    """
    if not text:
        return ''
    
    text_lower = text.lower()

    found_courtage = [kw for kw in _COURTAGE_KEYWORDS if kw in text_lower]
    found_sach = [kw for kw in _SACH_KEYWORDS if kw in text_lower]
    found_leben = [kw for kw in _LEBEN_KEYWORDS if kw in text_lower]
    found_kranken = [kw for kw in _KRANKEN_KEYWORDS if kw in text_lower]
    has_kontoauszug_provision = (
        'kontoauszug' in text_lower
        and ('provision' in text_lower or 'courtage' in text_lower)
    )

    hints = []

    # KONFLIKT 1: Courtage-Keyword + andere Sparte gleichzeitig
    if found_courtage and (found_leben or found_sach or found_kranken):
        hints.append(f'Courtage-Keyword "{found_courtage[0]}" gefunden.')
        if found_leben:
            hints.append(
                f'"{found_leben[0]}" ist wahrscheinlich VU-Name, '
                f'NICHT Sparten-Indikator!'
            )
        hints.append('Courtage-Keywords haben Vorrang -> wahrscheinlich courtage.')

    # KONFLIKT 2: Kontoauszug + Provision (ohne sonstigen Courtage-Keyword)
    elif has_kontoauszug_provision and not found_courtage:
        hints.append(
            '"Kontoauszug" + "Provision/Courtage" gefunden '
            '-> wahrscheinlich courtage (VU-Provisionskonto, nicht Bankauszug).'
        )

    # PROBLEMFALL 3: Sach-Keyword allein (KI hat hier nachweislich versagt)
    elif found_sach and not found_courtage:
        hints.append(
            f'"{found_sach[0]}" gefunden '
            f'-> sach ({found_sach[0]} gehoert immer zur Sachversicherung).'
        )

    # Alle anderen Faelle: KEIN Hint (0 extra Tokens)
    if not hints:
        return ''

    return '[KEYWORD-ANALYSE: ' + ' '.join(hints) + ']\n\n'
