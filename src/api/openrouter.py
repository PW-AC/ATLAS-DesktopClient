"""
OpenRouter API Client fuer KI-basierte PDF-Benennung

Verwendet Vision-Modelle fuer OCR und Structured Outputs fuer Entity-Extraktion.
"""

import base64
import json
import logging
import os
import re
import tempfile
import time
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import requests

from .client import APIClient, APIError

logger = logging.getLogger(__name__)

# KI-Pipeline Backpressure-Kontrolle
# Begrenzt parallele KI-Aufrufe um Server-Ueberlastung zu vermeiden
DEFAULT_MAX_CONCURRENT_AI_CALLS = 5
_ai_semaphore: Optional[threading.Semaphore] = None
_ai_semaphore_lock = threading.Lock()
_ai_queue_depth = 0  # Monitoring: Anzahl wartender Aufrufe


def get_ai_semaphore(max_concurrent: int = DEFAULT_MAX_CONCURRENT_AI_CALLS) -> threading.Semaphore:
    """
    Gibt die globale KI-Semaphore zurueck (Singleton).
    
    Begrenzt die Anzahl gleichzeitiger KI-Aufrufe fuer Backpressure-Kontrolle.
    """
    global _ai_semaphore
    with _ai_semaphore_lock:
        if _ai_semaphore is None:
            _ai_semaphore = threading.Semaphore(max_concurrent)
            logger.info(f"KI-Semaphore initialisiert: max {max_concurrent} parallele Aufrufe")
    return _ai_semaphore


def get_ai_queue_depth() -> int:
    """Gibt die aktuelle Anzahl wartender KI-Aufrufe zurueck (Monitoring)."""
    return _ai_queue_depth


def _increment_queue_depth():
    """Erhoeht den Queue-Tiefe-Zaehler (Thread-safe)."""
    global _ai_queue_depth
    with _ai_semaphore_lock:
        _ai_queue_depth += 1


def _decrement_queue_depth():
    """Verringert den Queue-Tiefe-Zaehler (Thread-safe)."""
    global _ai_queue_depth
    with _ai_semaphore_lock:
        _ai_queue_depth = max(0, _ai_queue_depth - 1)

# OpenRouter API Konfiguration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_VISION_MODEL = "openai/gpt-4o"
DEFAULT_EXTRACT_MODEL = "openai/gpt-4o-mini"  # Stufe 2: gpt-4o-mini statt gpt-4o (~17x guenstiger)
DEFAULT_TRIAGE_MODEL = "openai/gpt-4o-mini"  # Guenstiges Modell fuer schnelle Kategorisierung
DEFAULT_OCR_MODEL = "openai/gpt-4o-mini"  # OCR: gpt-4o-mini hat Vision-Support und ist ~17x guenstiger

# Retry-Konfiguration
MAX_RETRIES = 4
RETRY_STATUS_CODES = {429, 502, 503, 504}
RETRY_BACKOFF_FACTOR = 1.5

# ============================================================================
# TRIAGE-SYSTEM (Stufe 1: Schnelle Kategorisierung)
# ============================================================================

# Kompakter Triage-Prompt - entscheidet ob Detailanalyse noetig
TRIAGE_PROMPT = '''Ist dieses Dokument ein Versicherungsdokument das analysiert werden soll?

JA ("dokument") wenn es eines davon ist:
- Versicherungsschein, Police, Nachtrag, Antrag
- Mahnung, Beitragserinnerung, Rechnung
- Kuendigung, Schadensmeldung
- Vermittlerinformation
- Courtage-/Provisionsabrechnung

NEIN ("sonstige") wenn:
- Kein Versicherungsbezug
- Werbung, Newsletter
- Unklar/nicht lesbar

TEXT:
{text_preview}
'''

# JSON Schema fuer Triage (minimal)
TRIAGE_SCHEMA = {
    "name": "document_triage",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["dokument", "sonstige"],
                "description": "dokument = Versicherungsdokument zur Analyse, sonstige = nicht analysieren"
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "low"],
                "description": "Sicherheit der Zuordnung"
            },
            "detected_insurer": {
                "type": ["string", "null"],
                "description": "Erkannter Versicherer (kurz, ohne Rechtsform)"
            }
        },
        "required": ["category", "confidence", "detected_insurer"],
        "additionalProperties": False
    }
}


# ============================================================================
# HILFSFUNKTIONEN
# ============================================================================

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
    # - Nur Courtage-Keywords -> KI schafft das korrekt
    # - Nur Leben-Keywords -> KI schafft das korrekt
    # - Nur Kranken-Keywords -> KI schafft das korrekt
    # - Keine Keywords -> KI wie gehabt
    if not hints:
        return ''

    return '[KEYWORD-ANALYSE: ' + ' '.join(hints) + ']\n\n'


@dataclass
class DocumentClassification:
    """
    Ergebnis der KI-Klassifikation eines Dokuments.
    
    Bestimmt direkt die Ziel-Box und extrahiert Metadaten fuer Benennung.
    """
    # Ziel-Box (direkt von KI bestimmt)
    target_box: str  # 'courtage', 'sach', 'leben', 'kranken', 'sonstige'
    confidence: str  # 'high', 'medium', 'low'
    reasoning: str  # Kurze Begruendung
    
    # Metadaten fuer Benennung
    insurer: Optional[str] = None
    document_date_iso: Optional[str] = None
    date_granularity: Optional[str] = None  # 'day', 'month', 'year'
    document_type: Optional[str] = None  # z.B. "Privathaftpflicht", "Rentenversicherung"
    insurance_type: Optional[str] = None  # 'Leben', 'Sach', 'Kranken' (wichtig bei Courtage!)
    
    # Rohdaten
    raw_response: dict = field(default_factory=dict)
    
    def generate_filename(self, original_extension: str = ".pdf") -> str:
        """
        Generiert Dateinamen nach Schema:
        
        - Courtage: Versicherer_Courtage_Sparte_Datum.ext 
          (z.B. Helvetia_Courtage_Leben_2025-01-15.pdf)
        - Andere: Versicherer_Sparte_Dokumenttyp_Datum.ext 
          (z.B. SV_SparkassenVersicherung_Sach_Mahnung_2026-02-03.pdf)
        
        Verwendet slug_de() fuer sichere Dateinamen.
        """
        parts = []
        
        # 1. Versicherer (max 35 Zeichen fuer laengere Namen)
        insurer_slug = slug_de(self.insurer, max_len=35) if self.insurer else "Unbekannt"
        parts.append(insurer_slug)
        
        # 2. Bei Courtage: "Courtage" + Sparte
        if self.target_box == 'courtage':
            parts.append("Courtage")
            if self.insurance_type:
                parts.append(self.insurance_type)  # Leben, Sach, Kranken
        else:
            # 3. Bei anderen: Sparte + Dokumenttyp
            if self.insurance_type:
                parts.append(self.insurance_type)  # Leben, Sach, Kranken
            
            if self.document_type:
                # Dokumenttyp-Mapping fuer konsistente Namen
                doc_type_map = {
                    'mahnung': 'Mahnung',
                    'beitragserinnerung': 'Mahnung',
                    'zahlungserinnerung': 'Mahnung',
                    'letzte beitragserinnerung': 'Mahnung',
                    'police': 'Police',
                    'versicherungsschein': 'Police',
                    'nachtrag': 'Nachtrag',
                    'rechnung': 'Rechnung',
                    'beitragsrechnung': 'Rechnung',
                    'kuendigung': 'Kuendigung',
                    'kuendigungsbestaetigung': 'Kuendigung',
                    'schadensmeldung': 'Schaden',
                    'schadensabrechnung': 'Schaden',
                    'vermittlerinformation': 'Info',
                    'antrag': 'Antrag',
                }
                doc_type_lower = self.document_type.lower()
                normalized_type = doc_type_map.get(doc_type_lower, self.document_type)
                parts.append(slug_de(normalized_type, max_len=20))
        
        # 4. Datum
        if self.document_date_iso:
            if self.date_granularity == 'year':
                parts.append(self.document_date_iso[:4])  # YYYY
            elif self.date_granularity == 'month':
                parts.append(self.document_date_iso[:7])  # YYYY-MM
            else:
                parts.append(self.document_date_iso)  # YYYY-MM-DD
        
        # Zusammenfuegen
        filename = "_".join(p for p in parts if p)
        
        # Fallback wenn leer
        if not filename or filename == "Unbekannt":
            filename = "Dokument"
        
        if not original_extension.startswith('.'):
            original_extension = '.' + original_extension
        
        return filename + original_extension


@dataclass
class ExtractedDocumentData:
    """Extrahierte Daten aus einem Versicherungsdokument (Legacy)."""
    insurer: Optional[str] = None
    document_date: Optional[str] = None  # Originales Format aus dem Text
    document_date_iso: Optional[str] = None  # ISO-8601 Format (YYYY-MM-DD)
    date_granularity: Optional[str] = None  # 'day', 'month', 'year'
    typ: Optional[str] = None  # Leben, Kranken, Sach
    is_courtage: bool = False  # Ist es eine Provisionsabrechnung?
    raw_response: dict = field(default_factory=dict)
    
    @property
    def versicherungstyp(self) -> Optional[str]:
        """Alias fuer typ."""
        return self.typ
    
    def generate_filename(self, original_extension: str = ".pdf") -> str:
        """
        Generiert einen Dateinamen nach dem Schema: Versicherer_Typ_Datum.ext
        
        Fuer Courtage-Dokumente: Versicherer_Courtage_Datum.ext
        Verwendet slug_de() fuer sichere Dateinamen.
        """
        parts = []
        
        # Versicherer (mit slug_de fuer sichere Zeichen)
        parts.append(slug_de(self.insurer, max_len=30))
        
        # Bei Courtage-Dokumenten speziellen Typ verwenden
        if self.is_courtage:
            parts.append("Courtage")
        elif self.typ:
            typ = self.typ
            # Kurzform verwenden
            typ_map = {
                'lebensversicherung': 'Leben',
                'krankenversicherung': 'Kranken',
                'sachversicherung': 'Sach',
                'leben': 'Leben',
                'kranken': 'Kranken',
                'sach': 'Sach',
            }
            typ = typ_map.get(typ.lower(), typ)
            parts.append(slug_de(typ, max_len=20))
        
        # Datum (mit Granularitaet)
        if self.document_date_iso:
            if self.date_granularity == 'year':
                date_str = self.document_date_iso[:4]  # YYYY
            elif self.date_granularity == 'month':
                date_str = self.document_date_iso[:7]  # YYYY-MM
            else:
                date_str = self.document_date_iso
            parts.append(date_str)
        
        # Zusammenfuegen
        filename = "_".join(parts)
        
        # Extension hinzufuegen
        if not original_extension.startswith('.'):
            original_extension = '.' + original_extension
        
        return filename + original_extension


class OpenRouterClient:
    """
    Client fuer OpenRouter API zur PDF-Analyse.
    
    Workflow:
    1. PDF zu Bildern konvertieren
    2. Vision-Modell: OCR (Bilder -> Text)
    3. LLM mit Structured Output: Entity-Extraktion (Text -> JSON)
    """
    
    # Prompt fuer Entity-Extraktion
    EXTRACTION_PROMPT = '''Du bist ein KI-System, das strukturierte Daten aus Text extrahiert.

Aufgabe:
Extrahiere die folgenden Entitaeten aus dem bereitgestellten Eingabetext. Bei den Dokumenten handelt es sich ausschliesslich um Versicherer-Dokumente.

Fokus-Entitaeten:
- Versicherer ("Insurer")
- Datum des Dokuments ("DocumentDate")
- Versicherungstyp ("Typ") - (Leben, Kranken oder Sach)
- Provisionsabrechnung ("IsCourtage") - Ist es ein Courtage/Provisions-Dokument?

Regeln fuer "Insurer":
- Erkenne den Versicherer-Namen aus dem Text, z. B. "Allianz", "RheinLand", "HDI", "R+V", "Volkswohl Bund".
- Gib den Namen moeglichst kurz und eindeutig zurueck (ohne Rechtsform: z. B. "Allianz" statt "Allianz Versicherungs-AG").

Regeln fuer "DocumentDate":
- Das Datum kann in folgenden Formen vorkommen:
  - TT.MM.JJJJ (z. B. "31.12.2025")
  - MM.JJJJ (z. B. "12.2025")
  - JJJJ (z. B. "2025", nur verwenden, wenn eindeutig als Dokumentjahr erkennbar)
- "value": immer exakt die Form aus dem Text.
- "normalized_iso": Datum im ISO-8601-Format:
  - TT.MM.JJJJ -> JJJJ-MM-TT (z. B. "31.12.2025" -> "2025-12-31")
  - MM.JJJJ -> auf den 1. des Monats setzen (z. B. "12.2025" -> "2025-12-01")
  - JJJJ -> auf den 1.1. setzen (z. B. "2025" -> "2025-01-01")
- "granularity": "day" fuer TT.MM.JJJJ, "month" fuer MM.JJJJ, "year" fuer JJJJ
- Falls kein Datum sicher bestimmbar ist: alle Werte = null.

Regeln fuer "Typ":
- Erkenne den Versicherungstyp aus dem Text.
- Gib "Leben", "Kranken" oder "Sach" zurueck.

WICHTIG - Kategoriezuordnung:
- "Sach" = Haftpflicht, Privathaftpflicht, Hausrat, Wohngebaeude, KFZ, Auto, Unfall, Rechtsschutz, Glas, Gewerbe, Transport, Betriebshaftpflicht
- "Leben" = Lebensversicherung, Rente, Rentenversicherung, Altersvorsorge, Berufsunfaehigkeit, BU, Risikoleben, Kapitalversicherung, Fondsgebunden
- "Kranken" = Krankenversicherung, PKV, GKV, Krankenzusatz, Zahnzusatz, Pflegeversicherung, Krankentagegeld

Bei Unklarheit: null. Aber wenn ein Schluesselwort wie "Haftpflicht" oder "Hausrat" vorkommt, ist es IMMER "Sach"!

Regeln fuer "IsCourtage":
- Setze auf true wenn es sich um eines der folgenden Dokumente handelt:
  - Provisionsabrechnung
  - Courtage-Abrechnung
  - Vermittlerverguetung
  - Verguetungsabrechnung
  - Abschlussverguetung
  - Provisionsliste
  - Commission Statement
  - Verguetungsnachweis
  - Provisionsnachweis
  - Vermittlerabrechnung
- Bei anderen Dokumenten: false.

Allgemeine Regeln:
- Triff keine spekulativen Annahmen.
- Wenn eine Entitaet nicht sicher identifiziert werden kann, setze deren Werte auf null.

Eingabetext:
{text}
'''

    # JSON Schema fuer Structured Output
    EXTRACTION_SCHEMA = {
        "name": "document_entities",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "Insurer": {
                    "type": ["string", "null"],
                    "description": "Name des Versicherers (kurz, ohne Rechtsform)"
                },
                "DocumentDate": {
                    "type": ["object", "null"],
                    "properties": {
                        "value": {
                            "type": ["string", "null"],
                            "description": "Datum wie im Text gefunden"
                        },
                        "normalized_iso": {
                            "type": ["string", "null"],
                            "description": "Datum im ISO-8601 Format (YYYY-MM-DD)"
                        },
                        "granularity": {
                            "type": ["string", "null"],
                            "enum": ["day", "month", "year"],
                            "description": "Genauigkeit des Datums (null wenn unbekannt)"
                        }
                    },
                    "required": ["value", "normalized_iso", "granularity"],
                    "additionalProperties": False
                },
                "Typ": {
                    "type": ["string", "null"],
                    "enum": ["Leben", "Kranken", "Sach"],
                    "description": "Versicherungstyp (null wenn unbekannt)"
                },
                "IsCourtage": {
                    "type": "boolean",
                    "description": "Ist es eine Provisions-/Courtage-Abrechnung?"
                }
            },
            "required": ["Insurer", "DocumentDate", "Typ", "IsCourtage"],
            "additionalProperties": False
        }
    }
    
    def __init__(self, api_client: APIClient):
        """
        Initialisiert den OpenRouter Client.
        
        Args:
            api_client: APIClient-Instanz fuer Server-Kommunikation
        """
        self.api_client = api_client
        self._api_key: Optional[str] = None
        self._session = requests.Session()
        
        self._cost_calculator = None
        try:
            from services.cost_calculator import CostCalculator
            self._cost_calculator = CostCalculator()
            self._cost_calculator.load_pricing_from_api(api_client)
        except Exception as e:
            logger.debug(f"CostCalculator nicht verfuegbar: {e}")
    
    def _ensure_api_key(self) -> str:
        """
        SV-004: API-Key wird nicht mehr vom Server geholt.
        Klassifikation laeuft jetzt ueber Server-Proxy POST /ai/classify.
        Diese Methode existiert nur noch fuer Abwaertskompatibilitaet.
        """
        # SV-004 Fix: Key wird nicht mehr benoetigt, Proxy uebernimmt
        return "proxy-mode"
    
    def get_credits(self) -> Optional[dict]:
        """
        Ruft Guthaben/Usage ueber Server-Proxy ab.
        Unterstuetzt OpenRouter (balance) und OpenAI (monthly usage).
        
        Returns:
            dict mit 'provider' und provider-spezifischen Feldern, oder None bei Fehler.
            OpenRouter: balance, total_credits, total_usage, currency
            OpenAI: total_usage (USD), period
        """
        try:
            response = self.api_client.get("/ai/credits")
            
            if response.get('success') and response.get('data'):
                data = response['data']
                provider = data.get('provider', 'openrouter')
                
                if provider == 'openai':
                    return {
                        'provider': 'openai',
                        'total_usage': data.get('total_usage'),
                        'period': data.get('period', ''),
                        'currency': 'USD'
                    }
                
                inner = data.get('data', data)
                total_credits = inner.get('total_credits', 0)
                total_usage = inner.get('total_usage', 0)
                balance = total_credits - total_usage
                
                return {
                    'provider': 'openrouter',
                    'total_credits': total_credits,
                    'total_usage': total_usage,
                    'balance': balance,
                    'currency': 'USD'
                }
            
            logger.warning("Credits-Abfrage ueber Proxy fehlgeschlagen")
            return None
            
        except Exception as e:
            logger.warning(f"Fehler beim Abrufen der Credits (Proxy): {e}")
            return None
    
    def _openrouter_request(self, messages: List[dict], model: str = DEFAULT_VISION_MODEL,
                            response_format: dict = None, max_tokens: int = 4096) -> dict:
        """
        SV-004 Fix: Sendet Anfragen ueber den Server-Proxy statt direkt an OpenRouter.
        
        Der Server-Proxy (POST /ai/classify) injiziert den API-Key serverseitig
        und reduziert PII aus dem Text (SV-013).
        
        BACKPRESSURE: Verwendet Semaphore um parallele KI-Aufrufe zu begrenzen.
        
        Args:
            messages: Chat-Nachrichten
            model: Modell-ID
            response_format: Optional - Structured Output Schema
            max_tokens: Maximale Ausgabelaenge
            
        Returns:
            API-Antwort als dict (OpenRouter-Format)
            
        Raises:
            APIError: Bei Proxy- oder OpenRouter-Fehlern
        """
        # BACKPRESSURE: Semaphore verwenden
        semaphore = get_ai_semaphore()
        _increment_queue_depth()
        queue_depth = get_ai_queue_depth()
        
        if queue_depth > 1:
            logger.debug(f"KI-Queue-Tiefe: {queue_depth} wartende Aufrufe")
        
        logger.debug(f"OpenRouter Proxy Request: model={model}, messages={len(messages)}, queue_depth={queue_depth}")
        
        # Proxy-Payload: Server fuegt API-Key hinzu
        proxy_payload = {
            "messages": messages,
            "model": model,
            "max_tokens": max_tokens
        }
        if response_format:
            proxy_payload["response_format"] = response_format
        
        last_error = None
        
        # Semaphore erwerben (blockiert wenn zu viele parallele Aufrufe)
        semaphore.acquire()
        try:
            for attempt in range(MAX_RETRIES):
                try:
                    # SV-004: Ueber unseren Server-Proxy statt direkt an OpenRouter
                    response = self.api_client.post(
                        "/ai/classify",
                        json_data=proxy_payload
                    )
                    
                    # Server-Proxy gibt KI-Antwort in 'data' zurueck
                    if response.get('success') and response.get('data'):
                        data = response['data']
                        cost_info = data.get('_cost', {})
                        if cost_info.get('provider'):
                            logger.info(f"KI-Request via Provider: {cost_info['provider']}")
                        return data
                    
                    # Fehler vom Proxy
                    error_msg = response.get('error', 'Unbekannter Proxy-Fehler')
                    logger.error(f"AI-Proxy Fehler: {error_msg}")
                    raise APIError(f"AI-Proxy Fehler: {error_msg}")
                    
                except APIError as e:
                    # Retryable Status Codes
                    if hasattr(e, 'status_code') and e.status_code in RETRY_STATUS_CODES:
                        wait_time = RETRY_BACKOFF_FACTOR * (attempt + 1)
                        logger.warning(
                            f"AI-Proxy HTTP {e.status_code}, "
                            f"Retry {attempt + 1}/{MAX_RETRIES} in {wait_time:.1f}s"
                        )
                        time.sleep(wait_time)
                        continue
                    raise
                    
                except requests.RequestException as e:
                    last_error = e
                    wait_time = RETRY_BACKOFF_FACTOR * (attempt + 1)
                    logger.warning(
                        f"AI-Proxy Netzwerkfehler: {e}, "
                        f"Retry {attempt + 1}/{MAX_RETRIES} in {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)
            
            # Alle Retries fehlgeschlagen
            logger.error(f"AI-Proxy nach {MAX_RETRIES} Versuchen nicht erreichbar")
            raise APIError(f"AI-Proxy dauerhaft nicht erreichbar: {last_error}")
        finally:
            # BACKPRESSURE: Semaphore freigeben und Queue-Tiefe verringern
            semaphore.release()
            _decrement_queue_depth()
    
    def pdf_to_images(self, pdf_path: str, max_pages: int = 5, dpi: int = 150) -> List[str]:
        """
        Konvertiert ein PDF zu Base64-codierten Bildern.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            max_pages: Maximale Anzahl Seiten (fuer Kosten-/Performance-Optimierung)
            dpi: Aufloesung der Bilder
            
        Returns:
            Liste von Base64-Strings (PNG-Format)
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "PyMuPDF nicht installiert.\n"
                "Bitte installieren: pip install PyMuPDF"
            )
        
        logger.info(f"Konvertiere PDF zu Bildern: {pdf_path}")
        
        images = []
        doc = fitz.open(pdf_path)
        
        try:
            num_pages = min(len(doc), max_pages)
            logger.debug(f"PDF hat {len(doc)} Seiten, verarbeite {num_pages}")
            
            for page_num in range(num_pages):
                page = doc[page_num]
                
                # Seite zu Bild rendern
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # Als PNG in Base64 kodieren
                png_data = pix.tobytes("png")
                b64_data = base64.b64encode(png_data).decode('utf-8')
                images.append(b64_data)
                
                logger.debug(f"Seite {page_num + 1}/{num_pages} konvertiert")
        finally:
            doc.close()
        
        logger.info(f"{len(images)} Seite(n) konvertiert")
        return images
    
    def ocr_pdf_local(self, pdf_path: str, max_pages: int = 2, dpi: int = 150) -> str:
        """
        Lokale OCR fuer Bild-PDFs via Tesseract (kostenlos, kein API-Call).
        
        Rendert PDF-Seiten lokal zu Bildern und extrahiert Text mit Tesseract OCR.
        Deutlich guenstiger als Cloud-OCR (GPT-4o Vision), fuer gedruckte
        Versicherungsdokumente mit Standardlayout voellig ausreichend.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            max_pages: Maximale Anzahl Seiten fuer OCR
            dpi: Aufloesung fuer Rendering (150 = gute Balance Qualitaet/Speed)
            
        Returns:
            Extrahierter Text (leer wenn Tesseract nicht verfuegbar)
            
        Raises:
            Keine - gibt leeren String bei Fehler zurueck (Fallback auf Cloud-OCR)
        """
        try:
            import pytesseract
            from PIL import Image
            import io
        except ImportError:
            logger.debug("pytesseract/Pillow nicht installiert, ueberspringe lokale OCR")
            return ""
        
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return ""
        
        # Tesseract-Pfad konfigurieren (Windows Standard-Installation)
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        for tess_path in tesseract_paths:
            if os.path.isfile(tess_path):
                pytesseract.pytesseract.tesseract_cmd = tess_path
                break
        
        try:
            doc = fitz.open(pdf_path)
            num_pages = min(len(doc), max_pages)
            all_text = []
            
            for page_num in range(num_pages):
                page = doc[page_num]
                
                # Seite zu Bild rendern (150 DPI fuer gute OCR-Qualitaet)
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # PyMuPDF Pixmap -> PIL Image (fuer pytesseract)
                png_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(png_data))
                
                # Tesseract OCR (deutsch + englisch)
                page_text = pytesseract.image_to_string(
                    pil_image, 
                    lang='deu+eng',
                    config='--psm 6'  # Uniform block of text
                )
                
                if page_text.strip():
                    all_text.append(page_text.strip())
            
            doc.close()
            
            result = '\n\n'.join(all_text)
            if result:
                logger.info(f"Lokale OCR (Tesseract): {len(result)} Zeichen aus {num_pages} Seite(n)")
            else:
                logger.debug(f"Lokale OCR: kein Text erkannt in {num_pages} Seite(n)")
            
            return result
            
        except pytesseract.TesseractNotFoundError:
            logger.warning(
                "Tesseract OCR nicht installiert. "
                "Bitte installieren: https://github.com/UB-Mannheim/tesseract/wiki"
            )
            return ""
        except Exception as e:
            logger.warning(f"Lokale OCR fehlgeschlagen: {e}")
            return ""
    
    def extract_text_from_images(self, images_b64: List[str], 
                                  model: str = DEFAULT_OCR_MODEL) -> str:
        """
        Extrahiert Text aus Bildern mittels Vision-Modell (OCR).
        
        Args:
            images_b64: Liste von Base64-codierten Bildern
            model: Vision-Modell
            
        Returns:
            Extrahierter Text
        """
        if not images_b64:
            return ""
        
        logger.info(f"OCR fuer {len(images_b64)} Bild(er) via {model}...")
        
        # Inhalt fuer Vision-Request bauen
        content = [
            {
                "type": "text",
                "text": (
                    "Lies dieses Versicherungsdokument vollstaendig aus. "
                    "Gib den gesamten Text zurueck, Zeile fuer Zeile. "
                    "Achte besonders auf: Versicherer-Name (VU), Datum, Dokumenttyp, "
                    "Versicherungssparte (z.B. Sach, Leben, Kranken, KFZ, Haftpflicht), "
                    "Versicherungsscheinnummern (VS-Nr), Vertragsnummern und Policennummern. "
                    "Bei Tabellen: Spaltenkoepfe und erste Datenzeilen wiedergeben."
                )
            }
        ]
        
        # Bilder hinzufuegen
        for img_b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}"
                }
            })
        
        messages = [{"role": "user", "content": content}]
        
        response = self._openrouter_request(messages, model=model, max_tokens=2000)
        
        # Text aus Antwort extrahieren
        text = ""
        if response.get('choices'):
            text = response['choices'][0].get('message', {}).get('content', '')
        
        logger.info(f"OCR abgeschlossen: {len(text)} Zeichen")
        return text
    
    def extract_entities(self, text: str, 
                         model: str = DEFAULT_EXTRACT_MODEL) -> ExtractedDocumentData:
        """
        Extrahiert Entitaeten aus Text mittels Structured Output.
        
        Args:
            text: Zu analysierender Text
            model: LLM-Modell
            
        Returns:
            ExtractedDocumentData mit gefundenen Entitaeten
        """
        if not text or not text.strip():
            logger.warning("Leerer Text, keine Entity-Extraktion moeglich")
            return ExtractedDocumentData()
        
        logger.info(f"Entity-Extraktion via {model}...")
        
        # Prompt mit Text fuellen
        prompt = self.EXTRACTION_PROMPT.format(text=text[:15000])  # Limit fuer Token
        
        messages = [{"role": "user", "content": prompt}]
        
        response_format = {
            "type": "json_schema",
            "json_schema": self.EXTRACTION_SCHEMA
        }
        
        response = self._openrouter_request(
            messages, 
            model=model, 
            response_format=response_format,
            max_tokens=1024
        )
        
        # JSON aus Antwort parsen
        result = ExtractedDocumentData()
        result.raw_response = response
        
        if response.get('choices'):
            content = response['choices'][0].get('message', {}).get('content', '')
            data = _safe_json_loads(content)
            
            if data:
                logger.debug(f"Extrahierte Daten: {data}")
                
                result.insurer = data.get('Insurer')
                
                doc_date = data.get('DocumentDate')
                if doc_date and isinstance(doc_date, dict):
                    result.document_date = doc_date.get('value')
                    result.document_date_iso = doc_date.get('normalized_iso')
                    result.date_granularity = doc_date.get('granularity')
                
                result.typ = data.get('Typ')
                result.is_courtage = bool(data.get('IsCourtage', False))
        
        logger.info(f"Extraktion abgeschlossen: Insurer={result.insurer}, "
                    f"Typ={result.typ}, Date={result.document_date_iso}, "
                    f"IsCourtage={result.is_courtage}")
        return result
    
    def process_pdf(self, pdf_path: str, 
                    vision_model: str = DEFAULT_VISION_MODEL,
                    extract_model: str = DEFAULT_EXTRACT_MODEL) -> ExtractedDocumentData:
        """
        Vollstaendiger Workflow: PDF -> OCR -> Entity-Extraktion.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            vision_model: Modell fuer OCR
            extract_model: Modell fuer Entity-Extraktion
            
        Returns:
            ExtractedDocumentData mit allen gefundenen Informationen
        """
        logger.info(f"Starte PDF-Verarbeitung: {pdf_path}")
        
        # 1. PDF zu Bildern
        images = self.pdf_to_images(pdf_path)
        
        if not images:
            logger.warning("Keine Bilder aus PDF extrahiert")
            return ExtractedDocumentData()
        
        # 2. OCR
        text = self.extract_text_from_images(images, model=vision_model)
        
        if not text:
            logger.warning("Kein Text aus Bildern extrahiert")
            return ExtractedDocumentData()
        
        # 3. Entity-Extraktion
        result = self.extract_entities(text, model=extract_model)
        
        logger.info(f"PDF-Verarbeitung abgeschlossen")
        return result
    
    def check_pdf_needs_ocr(self, pdf_path: str) -> bool:
        """
        Prueft ob ein PDF OCR benoetigt oder bereits Text enthaelt.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            
        Returns:
            True wenn OCR benoetigt wird (kein/wenig Text im PDF)
        """
        try:
            import fitz
        except ImportError:
            return True  # Im Zweifel OCR machen
        
        try:
            doc = fitz.open(pdf_path)
            total_text = ""
            
            for page_num in range(min(len(doc), 3)):  # Erste 3 Seiten pruefen
                page = doc[page_num]
                total_text += page.get_text()
            
            doc.close()
            
            # Wenn weniger als 50 Zeichen, braucht es OCR
            needs_ocr = len(total_text.strip()) < 50
            logger.debug(f"PDF hat {len(total_text)} Zeichen Text, needs_ocr={needs_ocr}")
            return needs_ocr
            
        except Exception as e:
            logger.warning(f"Fehler beim Pruefen des PDFs: {e}")
            return True  # Im Zweifel OCR machen
    
    def process_pdf_smart(self, pdf_path: str) -> Tuple[ExtractedDocumentData, str]:
        """
        Intelligenter Workflow der erst prueft ob OCR noetig ist.
        
        Wenn das PDF bereits Text enthaelt, wird dieser direkt verwendet.
        Sonst wird Vision-OCR verwendet.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            
        Returns:
            Tuple von (ExtractedDocumentData, method_used)
            method_used: 'text_extraction' oder 'vision_ocr'
        """
        logger.info(f"Smart PDF-Verarbeitung: {pdf_path}")
        
        try:
            import fitz
            
            # Versuche direkten Text zu extrahieren
            doc = fitz.open(pdf_path)
            text = ""
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text += page.get_text() + "\n"
            
            doc.close()
            
            # Wenn genuegend Text vorhanden, direkt Entity-Extraktion
            if len(text.strip()) > 100:
                logger.info(f"PDF hat direkten Text ({len(text)} Zeichen), ueberspringe OCR")
                result = self.extract_entities(text)
                return result, 'text_extraction'
            
        except Exception as e:
            logger.debug(f"Direkte Text-Extraktion fehlgeschlagen: {e}")
        
        # Fallback: Vision-OCR
        logger.info("Verwende Vision-OCR")
        result = self.process_pdf(pdf_path)
        return result, 'vision_ocr'
    
    # ========================================================================
    # KLASSIFIKATIONS-METHODEN (v0.9.1 - verbesserte Erkennung)
    # ========================================================================
    
    # Verbesserter Prompt mit klarer Trennung: Dokumenttyp vs. Sparte
    CLASSIFICATION_PROMPT = '''Analysiere dieses Versicherungsdokument und extrahiere alle Informationen.

SCHRITT 1 - SPARTE ERKENNEN (fuer Box-Zuordnung):
- Sach: KFZ, Haftpflicht, Privathaftpflicht, PHV, Hausrat, Wohngebaeude, Unfall, Rechtsschutz, Glas, Reise, Tierhalterhaftpflicht, Hundehaftpflicht, Gewerbe, Betriebshaftpflicht, Gebaeudeversicherung
- Leben: Lebensversicherung, Rentenversicherung, BU, Riester, Ruerup, Pensionskasse, Altersvorsorge
- Kranken: PKV, Krankenzusatz, Zahnzusatz, Pflegeversicherung
- Courtage: NUR wenn Hauptzweck = Provisionsabrechnung (Tabelle mit Vertraegen + Provisionssaetzen)

SCHRITT 2 - DOKUMENTTYP ERKENNEN (fuer Dateinamen):
Moegliche Dokumenttypen:
- Police, Versicherungsschein, Nachtrag, Antrag
- Mahnung, Beitragserinnerung, Zahlungserinnerung
- Rechnung, Beitragsrechnung
- Kuendigung, Kuendigungsbestaetigung
- Schadensmeldung, Schadensabrechnung
- Vermittlerinformation
- Courtageabrechnung, Provisionsabrechnung

SCHRITT 3 - VERSICHERER ERKENNEN:
Suche im Text nach dem Versicherungsunternehmen. Beispiele:
- "SV SparkassenVersicherung" -> "SV SparkassenVersicherung"
- "Allianz Versicherungs-AG" -> "Allianz"
- "Wuerttembergische Lebensversicherung AG" -> "Wuerttembergische"
WICHTIG: Kurzform ohne Rechtsform (AG, GmbH, etc.)

SCHRITT 4 - DATUM ERKENNEN:
Suche nach Dokumentdatum (nicht Vertragsbeginn!). Typische Stellen:
- "Stuttgart, 03.02.2026" -> 2026-02-03
- Briefdatum oben rechts
- "Datum:" Feld

Extrahiere:
- insurance_type: Sach/Leben/Kranken (bestimmt die Box!)
- document_type: Der echte Dokumenttyp (Mahnung, Police, Rechnung, etc.)
- insurer: Versicherer-Kurzname
- document_date_iso: YYYY-MM-DD
- is_courtage: true nur bei Provisionsabrechnungen

TEXT:
{text}
'''

    # JSON Schema fuer Klassifikation (v0.9.1)
    CLASSIFICATION_SCHEMA = {
        "name": "document_classification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "insurance_type": {
                    "type": ["string", "null"],
                    "enum": ["Leben", "Sach", "Kranken"],
                    "description": "Versicherungssparte (bestimmt die Box: Sach->sach, Leben->leben, Kranken->kranken)"
                },
                "document_type": {
                    "type": ["string", "null"],
                    "description": "Dokumenttyp: Police, Nachtrag, Mahnung, Beitragserinnerung, Rechnung, Kuendigung, Schadensmeldung, Vermittlerinformation, etc."
                },
                "insurer": {
                    "type": ["string", "null"],
                    "description": "Versicherer-Kurzname ohne Rechtsform (z.B. 'Allianz', 'SV SparkassenVersicherung', 'Wuerttembergische')"
                },
                "document_date_iso": {
                    "type": ["string", "null"],
                    "description": "Dokumentdatum (Briefdatum) im ISO-Format YYYY-MM-DD"
                },
                "date_granularity": {
                    "type": ["string", "null"],
                    "enum": ["day", "month", "year"],
                    "description": "Genauigkeit des Datums"
                },
                "is_courtage": {
                    "type": "boolean",
                    "description": "true NUR wenn Hauptzweck = Provisionsabrechnung/Courtageabrechnung"
                },
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Wie sicher ist die Zuordnung?"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Kurze Begruendung (max 80 Zeichen)"
                }
            },
            "required": ["insurance_type", "document_type", "insurer", "document_date_iso", "date_granularity", "is_courtage", "confidence", "reasoning"],
            "additionalProperties": False
        }
    }
    
    # =========================================================================
    # LEGACY: Vollstaendige KI-Klassifikation (Token-intensiv)
    # Diese Funktionen sind noch verfuegbar, werden aber nicht mehr
    # standardmaessig verwendet. Stattdessen: classify_courtage_minimal()
    # und classify_sparte_only() fuer Token-Optimierung.
    # =========================================================================
    
    def classify_document(self, text: str, 
                          model: str = DEFAULT_EXTRACT_MODEL) -> DocumentClassification:
        """
        Klassifiziert ein Dokument direkt in eine Box.
        
        Args:
            text: Extrahierter Text aus dem Dokument
            model: LLM-Modell
            
        Returns:
            DocumentClassification mit Ziel-Box und Metadaten
        """
        if not text or not text.strip():
            logger.warning("Leerer Text, Fallback zu 'sonstige'")
            return DocumentClassification(
                target_box='sonstige',
                confidence='low',
                reasoning='Kein Text im Dokument'
            )
        
        logger.info(f"Klassifiziere Dokument via {model}...")
        
        # Prompt mit Text fuellen
        prompt = self.CLASSIFICATION_PROMPT.format(text=text[:12000])  # Token-Limit
        
        messages = [{"role": "user", "content": prompt}]
        
        response_format = {
            "type": "json_schema",
            "json_schema": self.CLASSIFICATION_SCHEMA
        }
        
        response = self._openrouter_request(
            messages,
            model=model,
            response_format=response_format,
            max_tokens=500
        )
        
        # JSON parsen
        result = DocumentClassification(
            target_box='sonstige',
            confidence='low',
            reasoning='Parsing fehlgeschlagen'
        )
        result.raw_response = response
        
        if response.get('choices'):
            content = response['choices'][0].get('message', {}).get('content', '')
            data = _safe_json_loads(content)
            
            if data:
                logger.debug(f"Klassifikation Rohdaten: {data}")
                
                # Felder extrahieren
                result.confidence = data.get('confidence', 'low')
                result.reasoning = data.get('reasoning', '')
                result.insurer = data.get('insurer')
                result.document_date_iso = data.get('document_date_iso')
                result.date_granularity = data.get('date_granularity')
                result.document_type = data.get('document_type')
                result.insurance_type = data.get('insurance_type')
                
                # Box bestimmen basierend auf is_courtage und insurance_type
                is_courtage = data.get('is_courtage', False)
                insurance_type = data.get('insurance_type')
                
                if is_courtage:
                    result.target_box = 'courtage'
                elif insurance_type == 'Sach':
                    result.target_box = 'sach'
                elif insurance_type == 'Leben':
                    result.target_box = 'leben'
                elif insurance_type == 'Kranken':
                    result.target_box = 'kranken'
                else:
                    result.target_box = 'sonstige'
        
        logger.info(
            f"Klassifikation: {result.target_box} ({result.confidence}) "
            f"- {result.reasoning} [type={result.document_type}, insurer={result.insurer}]"
        )
        return result
    
    def classify_pdf(self, pdf_path: str) -> DocumentClassification:
        """
        Klassifiziert ein PDF direkt.
        
        1. Text aus PDF extrahieren (direkt oder via OCR)
        2. Text an classify_document() uebergeben
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            
        Returns:
            DocumentClassification
        """
        logger.info(f"Klassifiziere PDF: {pdf_path}")
        
        text = ""
        
        try:
            import fitz
            
            # Erst direkten Text versuchen
            doc = fitz.open(pdf_path)
            for page_num in range(min(len(doc), 5)):  # Max 5 Seiten
                page = doc[page_num]
                text += page.get_text() + "\n"
            doc.close()
            
            # Wenn wenig Text, OCR verwenden
            if len(text.strip()) < 100:
                logger.info("Wenig direkter Text, verwende Vision-OCR")
                images = self.pdf_to_images(pdf_path, max_pages=3)
                if images:
                    text = self.extract_text_from_images(images)
                    
        except Exception as e:
            logger.error(f"Text-Extraktion fehlgeschlagen: {e}")
            # Fallback zu OCR
            try:
                images = self.pdf_to_images(pdf_path, max_pages=3)
                if images:
                    text = self.extract_text_from_images(images)
            except Exception as e2:
                logger.error(f"OCR fehlgeschlagen: {e2}")
        
        if not text.strip():
            return DocumentClassification(
                target_box='sonstige',
                confidence='low',
                reasoning='Kein Text extrahierbar'
            )
        
        return self.classify_document(text)
    
    # ========================================================================
    # ZWEISTUFIGES KI-SYSTEM (v0.9.0)
    # ========================================================================
    
    def triage_document(self, text: str, 
                        model: str = DEFAULT_TRIAGE_MODEL) -> dict:
        """
        Stufe 1: Schnelle Kategorisierung mit GPT-4o-mini.
        
        Verwendet minimalen Token-Verbrauch fuer grobe Klassifikation.
        Nur erste 2500 Zeichen werden analysiert.
        
        Args:
            text: Dokumenttext (wird auf 2500 Zeichen gekuerzt)
            model: Triage-Modell (default: GPT-4o-mini)
            
        Returns:
            dict mit 'category', 'confidence', 'detected_insurer'
        """
        # Nur Vorschau verwenden (Token sparen)
        text_preview = text[:2500] if text else ""
        
        if not text_preview.strip():
            logger.warning("Triage: Kein Text vorhanden")
            return {
                "category": "sonstige",
                "confidence": "low",
                "detected_insurer": None
            }
        
        logger.info(f"Triage via {model} ({len(text_preview)} Zeichen)...")
        
        prompt = TRIAGE_PROMPT.format(text_preview=text_preview)
        messages = [{"role": "user", "content": prompt}]
        
        response_format = {
            "type": "json_schema",
            "json_schema": TRIAGE_SCHEMA
        }
        
        response = self._openrouter_request(
            messages,
            model=model,
            response_format=response_format,
            max_tokens=100  # Sehr kurze Antwort erwartet
        )
        
        # JSON parsen
        result = {
            "category": "sonstige",
            "confidence": "low",
            "detected_insurer": None
        }
        
        if response.get('choices'):
            content = response['choices'][0].get('message', {}).get('content', '')
            data = _safe_json_loads(content)
            
            if data:
                result["category"] = data.get("category", "sonstige")
                result["confidence"] = data.get("confidence", "low")
                result["detected_insurer"] = data.get("detected_insurer")
        
        logger.info(f"Triage: {result['category']} ({result['confidence']})")
        return result
    
    def classify_document_smart(self, text: str) -> DocumentClassification:
        """
        Zweistufige Klassifikation: Triage -> Detail bei Bedarf.
        
        Stufe 1 (GPT-4o-mini): Schnelle Kategorisierung - ist es ein Versicherungsdokument?
        Stufe 2 (GPT-4o): Detaillierte Analyse (Sparte, Dokumenttyp, Versicherer, Datum)
        
        Bei 'sonstige' in Stufe 1 wird KEINE teure Detailanalyse gemacht.
        
        Args:
            text: Vollstaendiger Dokumenttext
            
        Returns:
            DocumentClassification mit allen Metadaten
        """
        # Stufe 1: Triage - ist es ein Versicherungsdokument?
        triage = self.triage_document(text)
        
        # Bei 'sonstige': Einfache Zuordnung, keine weitere KI
        if triage["category"] == "sonstige":
            logger.info("Triage -> sonstige, ueberspringe Detailanalyse")
            return DocumentClassification(
                target_box='sonstige',
                confidence='low',
                reasoning='Triage: kein Versicherungsdokument',
                insurer=triage.get("detected_insurer")
            )
        
        # Stufe 2: Detailanalyse fuer alle Versicherungsdokumente
        logger.info(f"Triage -> {triage['category']}, starte Detailanalyse")
        return self.classify_document(text)
    
    def classify_pdf_smart(self, pdf_path: str) -> DocumentClassification:
        """
        Zweistufige PDF-Klassifikation mit intelligenter Text-Extraktion.
        
        1. Text extrahieren (direkt oder OCR)
        2. Triage mit Vorschau (GPT-4o-mini)
        3. Bei Bedarf: Detailanalyse (GPT-4o)
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            
        Returns:
            DocumentClassification
        """
        logger.info(f"Smart PDF-Klassifikation: {pdf_path}")
        
        # Text extrahieren (fuer Triage reicht Vorschau)
        text = self._extract_relevant_text(pdf_path, for_triage=False)
        
        if not text.strip():
            # Fallback zu OCR wenn kein Text
            logger.info("Kein direkter Text, verwende Vision-OCR")
            try:
                images = self.pdf_to_images(pdf_path, max_pages=3)
                if images:
                    text = self.extract_text_from_images(images)
            except Exception as e:
                logger.error(f"OCR fehlgeschlagen: {e}")
        
        if not text.strip():
            return DocumentClassification(
                target_box='sonstige',
                confidence='low',
                reasoning='Kein Text extrahierbar'
            )
        
        return self.classify_document_smart(text)
    
    def _extract_relevant_text(self, pdf_path: str, for_triage: bool = False) -> str:
        """
        Extrahiert nur relevante Textteile aus PDF.
        
        Optimiert fuer Token-Verbrauch:
        - Triage: Nur erste Seite, max 2500 Zeichen
        - Detail: Erste 3 Seiten, max 10000 Zeichen
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            for_triage: True = minimale Extraktion fuer Triage
            
        Returns:
            Extrahierter Text
        """
        try:
            import fitz
            
            doc = fitz.open(pdf_path)
            text = ""
            
            if for_triage:
                # Erste 2 Seiten fuer Triage (manche Dokumente haben Begleitschreiben auf S.1)
                max_pages = min(2, len(doc))
                for i in range(max_pages):
                    text += doc[i].get_text() + "\n"
                text = text[:3000]
            else:
                # Erste 3 Seiten fuer Detailanalyse
                max_pages = min(3, len(doc))
                for i in range(max_pages):
                    text += doc[i].get_text() + "\n"
                text = text[:10000]
            
            doc.close()
            
            logger.debug(f"Text extrahiert: {len(text)} Zeichen (for_triage={for_triage})")
            return text
            
        except Exception as e:
            logger.warning(f"Text-Extraktion fehlgeschlagen: {e}")
            return ""
    
    # =========================================================================
    # MINIMALE KI-KLASSIFIKATION (Token-optimiert)
    # Fuer BiPRO-Code-basierte Vorsortierung
    # =========================================================================
    
    def classify_courtage_minimal(self, pdf_path: str) -> Optional[dict]:
        """
        Minimale Klassifikation fuer Courtage-Dokumente.
        
        Extrahiert NUR: insurer, document_date_iso
        Token-optimiert: ~200 Token pro Request
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            
        Returns:
            {"insurer": "...", "document_date_iso": "YYYY-MM-DD"} oder None
        """
        logger.info(f"Courtage-Klassifikation (minimal): {pdf_path}")
        
        # Text extrahieren (nur erste Seite)
        text = self._extract_relevant_text(pdf_path, for_triage=True)
        
        if not text.strip():
            # Fallback zu OCR
            try:
                images = self.pdf_to_images(pdf_path, max_pages=1)
                if images:
                    text = self.extract_text_from_images(images[:1])  # Nur erste Seite
            except Exception as e:
                logger.error(f"OCR fehlgeschlagen: {e}")
                return None
        
        if not text.strip():
            logger.warning("Kein Text extrahierbar")
            return None
        
        # Minimaler Prompt - nur VU und Datum
        prompt = '''Extrahiere aus diesem Courtage-/Provisionsdokument:
1. Versicherer-Name (kurz, ohne Rechtsform wie "AG", "GmbH")
2. Dokumentdatum (YYYY-MM-DD Format)

TEXT:
{text}

Antwort NUR als JSON:
{{"insurer": "Name", "document_date_iso": "YYYY-MM-DD"}}
'''.format(text=text[:2000])  # Max 2000 Zeichen
        
        # Schema fuer Structured Output
        schema = {
            "name": "courtage_minimal",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "insurer": {
                        "type": ["string", "null"],
                        "description": "Versicherer-Name (kurz)"
                    },
                    "document_date_iso": {
                        "type": ["string", "null"],
                        "description": "Datum im ISO-Format YYYY-MM-DD"
                    }
                },
                "required": ["insurer", "document_date_iso"],
                "additionalProperties": False
            }
        }
        
        try:
            messages = [{"role": "user", "content": prompt}]
            
            response_format = {
                "type": "json_schema",
                "json_schema": schema
            }
            
            response = self._openrouter_request(
                messages,
                model=DEFAULT_TRIAGE_MODEL,
                response_format=response_format,
                max_tokens=150
            )
            
            if response.get('choices'):
                content = response['choices'][0].get('message', {}).get('content', '')
                result = _safe_json_loads(content)
                
                if result:
                    logger.info(f"Courtage minimal: {result}")
                    # Interne Metadaten durchreichen (mit _ Prefix, abwaertskompatibel)
                    result['_usage'] = response.get('usage', {})
                    result['_raw_response'] = content
                    result['_prompt_text'] = prompt
                    result['_ai_model'] = DEFAULT_TRIAGE_MODEL
                    result['_ai_stage'] = 'courtage_minimal'
                    return result
                
        except Exception as e:
            logger.error(f"Courtage-Klassifikation fehlgeschlagen: {e}")
        
        return None
    
    def classify_sparte_only(self, pdf_path: str) -> str:
        """
        Minimale Klassifikation: Bestimmt NUR die Sparte.
        Wrapper fuer classify_sparte_with_date - gibt nur Sparte zurueck.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            
        Returns:
            "sach" | "leben" | "kranken" | "sonstige"
        """
        result = self.classify_sparte_with_date(pdf_path)
        return result.get('sparte', 'sonstige')
    
    def classify_sparte_with_date(self, pdf_path: str,
                                   stage1_prompt: str = None,
                                   stage1_model: str = None,
                                   stage1_max_tokens: int = None,
                                   stage2_enabled: bool = True,
                                   stage2_prompt: str = None,
                                   stage2_model: str = None,
                                   stage2_max_tokens: int = None,
                                   stage2_trigger: str = 'low') -> dict:
        """
        Zweistufige Klassifikation mit Confidence-Scoring (nur PDFs).
        
        Stufe 1: GPT-4o-mini (2 Seiten, schnell + guenstig)
          -> confidence "high"/"medium" -> fertig
          -> confidence "low" -> Stufe 2
        
        Stufe 2: GPT-4o-mini (5 Seiten, praeziser) - optional deaktivierbar
          -> Endgueltiges Ergebnis inkl. Dokumentname bei "sonstige"
        
        Alle Parameter sind optional -- ohne Parameter werden die Hardcoded-Defaults
        verwendet (Abwaertskompatibilitaet).
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            stage1_prompt: Optionaler benutzerdefinierter Prompt fuer Stufe 1
            stage1_model: Optionales Modell fuer Stufe 1
            stage1_max_tokens: Optionale max_tokens fuer Stufe 1
            stage2_enabled: Ob Stufe 2 aktiv ist (Default: True)
            stage2_prompt: Optionaler benutzerdefinierter Prompt fuer Stufe 2
            stage2_model: Optionales Modell fuer Stufe 2
            stage2_max_tokens: Optionale max_tokens fuer Stufe 2
            stage2_trigger: Wann Stufe 2 ausloesen: 'low' oder 'low_medium'
            
        Returns:
            {"sparte": ..., "confidence": ..., "document_date_iso": ..., "vu_name": ..., "document_name": ...}
        """
        logger.info(f"Sparten-Klassifikation (minimal): {pdf_path}")
        
        # Text extrahieren (erste 2 Seiten)
        text = self._extract_relevant_text(pdf_path, for_triage=True)
        
        if not text.strip():
            # Stufe A: Lokale OCR via Tesseract (kostenlos, ~50-200ms)
            text = self.ocr_pdf_local(pdf_path, max_pages=2, dpi=150)
        
        if not text.strip():
            # Stufe B: Cloud-OCR als letzter Fallback (teuer, nur wenn Tesseract fehlt/versagt)
            try:
                images = self.pdf_to_images(pdf_path, max_pages=2, dpi=100)
                if images:
                    logger.info("Lokale OCR lieferte keinen Text, nutze Cloud-OCR als Fallback")
                    text = self.extract_text_from_images(images[:2])
            except Exception as e:
                logger.error(f"Cloud-OCR fehlgeschlagen: {e}")
                return {"sparte": "sonstige", "confidence": "low", "document_date_iso": None, 
                        "vu_name": None, "document_name": None}
        
        if not text.strip():
            return {"sparte": "sonstige", "confidence": "low", "document_date_iso": None, 
                    "vu_name": None, "document_name": None}
        
        # Keyword-Conflict-Check auf bereits extrahiertem Text (~0.1ms, 0 Tokens)
        # Generiert Hint NUR bei widerspruechlichen Keywords, sonst leerer String
        keyword_hint = _build_keyword_hints(text)
        if keyword_hint:
            logger.info(f"Keyword-Konflikt erkannt: {keyword_hint.strip()}")
        
        # =====================================================
        # STUFE 1: GPT-4o-mini (schnell, guenstig)
        # =====================================================
        # Bei Konflikt: Hint vor Text stellen (Text kuerzen um Gesamtlaenge zu halten)
        if keyword_hint:
            text_limit = max(2000, 2500 - len(keyword_hint))
            input_text_s1 = keyword_hint + text[:text_limit]
        else:
            input_text_s1 = text[:2500]
        
        result = self._classify_sparte_request(
            input_text_s1, 
            model=stage1_model or DEFAULT_TRIAGE_MODEL,
            custom_prompt=stage1_prompt,
            custom_max_tokens=stage1_max_tokens,
        )
        
        if not result:
            return {"sparte": "sonstige", "confidence": "low", "document_date_iso": None, 
                    "vu_name": None, "document_name": None}
        
        confidence = result.get("confidence", "medium")
        sparte = result.get("sparte", "sonstige")
        
        logger.info(
            f"Stufe 1 (mini): sparte={sparte}, confidence={confidence}, "
            f"VU={result.get('vu_name')}"
        )
        
        # =====================================================
        # STUFE 2: Detail-Klassifikation bei niedriger Confidence
        # =====================================================
        # Trigger bestimmen: 'low' = nur bei low, 'low_medium' = bei low oder medium
        should_trigger_stage2 = False
        if stage2_trigger == 'low_medium':
            should_trigger_stage2 = confidence in ("low", "medium")
        else:
            should_trigger_stage2 = confidence == "low"
        
        if should_trigger_stage2 and pdf_path.lower().endswith('.pdf') and stage2_enabled:
            s2_model = stage2_model or DEFAULT_EXTRACT_MODEL
            logger.info(f"Confidence '{confidence}' -> Stufe 2 mit {s2_model} (mehr Text, praeziser)")
            
            # Mehr Text: 5 Seiten statt 2
            full_text = self._extract_relevant_text(pdf_path, for_triage=False)
            if not full_text.strip():
                full_text = text  # Fallback auf vorherigen Text
            
            # Gleicher Hint auch fuer Stufe 2 (falls Konflikt erkannt)
            if keyword_hint:
                text_limit_s2 = max(4000, 5000 - len(keyword_hint))
                input_text_s2 = keyword_hint + full_text[:text_limit_s2]
            else:
                input_text_s2 = full_text[:5000]
            
            result_stage2 = self._classify_sparte_detail(
                input_text_s2,
                model=s2_model,
                custom_prompt=stage2_prompt,
                custom_max_tokens=stage2_max_tokens,
            )
            
            if result_stage2:
                logger.info(
                    f"Stufe 2 ({s2_model}): sparte={result_stage2.get('sparte')}, "
                    f"document_name={result_stage2.get('document_name')}, "
                    f"VU={result_stage2.get('vu_name')}"
                )
                # Stufe 2 Ergebnis hat Vorrang
                result_stage2["confidence"] = "medium"  # Stufe 2 ist mindestens medium
                
                # Aggregierte Metadaten: Stufe 1 + Stufe 2
                s1_usage = result.get('_usage', {})
                s2_usage = result_stage2.get('_usage', {})
                result_stage2['_usage'] = {
                    'prompt_tokens': (s1_usage.get('prompt_tokens') or 0) + (s2_usage.get('prompt_tokens') or 0),
                    'completion_tokens': (s1_usage.get('completion_tokens') or 0) + (s2_usage.get('completion_tokens') or 0),
                    'total_tokens': (s1_usage.get('total_tokens') or 0) + (s2_usage.get('total_tokens') or 0),
                }
                # Kosten aggregieren: Stage 1 + Stage 2
                s1_cost = result.get('_server_cost_usd', 0) or 0
                s2_cost = result_stage2.get('_server_cost_usd', 0) or 0
                result_stage2['_server_cost_usd'] = s1_cost + s2_cost
                result_stage2['_provider'] = result_stage2.get('_provider') or result.get('_provider', 'unknown')
                
                # Beide Raw-Responses + Prompts sammeln
                result_stage2['_raw_response'] = {
                    'stage1': result.get('_raw_response', ''),
                    'stage2': result_stage2.get('_raw_response', '')
                }
                result_stage2['_prompt_text'] = {
                    'stage1': result.get('_prompt_text', ''),
                    'stage2': result_stage2.get('_prompt_text', '')
                }
                result_stage2['_ai_model'] = f"{stage1_model or DEFAULT_TRIAGE_MODEL}+{s2_model}"
                result_stage2['_ai_stage'] = 'triage_and_detail'
                return result_stage2
        
        # Nur Stufe 1 -- Metadaten ergaenzen
        result['_ai_model'] = DEFAULT_TRIAGE_MODEL
        result['_ai_stage'] = 'triage_only'
        return result
    
    def _classify_sparte_request(self, text: str, model: str = DEFAULT_TRIAGE_MODEL,
                                 custom_prompt: str = None,
                                 custom_max_tokens: int = None) -> Optional[dict]:
        """
        Stufe 1: Schnelle Sparten-Klassifikation mit Confidence-Scoring.
        
        Args:
            text: Extrahierter Text
            model: LLM-Modell
            custom_prompt: Optionaler benutzerdefinierter Prompt (mit {text} Platzhalter)
            custom_max_tokens: Optionale max_tokens
            
        Returns:
            {"sparte": ..., "confidence": ..., "document_date_iso": ..., "vu_name": ...}
        """
        if custom_prompt:
            # .replace() statt .format() verwenden, da der Prompt JSON-Beispiele
            # mit {}-Klammern enthaelt (z.B. {"sparte": "..."}) die .format()
            # faelschlicherweise als Platzhalter interpretieren wuerde (KeyError)
            prompt = custom_prompt.replace('{text}', text)
        else:
            prompt = '''Klassifiziere dieses Versicherungsdokument in eine Sparte.

SPARTEN:
- courtage: NUR Provisionsabrechnungen/Courtageabrechnungen vom VU an den MAKLER/VERMITTLER
  MUSS enthalten: Auflistung von Vertraegen mit Provisionssaetzen/Courtagebetraegen
  NICHT courtage: Beitragsrechnungen, Kuendigungen, Policen, Nachtraege, Mahnungen,
  Adressaenderungen, Schadensmeldungen, Zahlungserinnerungen, Antraege - auch wenn
  sie von einer Versicherung kommen! Courtage = PROVISION FUER DEN MAKLER.

- sach: KFZ, Haftpflicht, Privathaftpflicht, PHV, Tierhalterhaftpflicht, Hundehaftpflicht,
  Hausrat, Wohngebaeude, Unfall, Unfallversicherung, Rechtsschutz, Gewerbe,
  Betriebshaftpflicht, Glas, Reise, Gebaeudeversicherung, Inhaltsversicherung,
  Bauherrenhaftpflicht, Elektronik, PrivatSchutzversicherung, Kombi-Schutz, Buendelversicherung,
  Schadenaufstellung, Schadenliste, Schadenstatistik, Schadenhistorie, Schadenquote,
  Fahrzeug, Fahrzeugerprobung, Fahrzeugschein, Fahrzeugbrief

- leben: Lebensversicherung, Rente, Rentenversicherung, BU, Berufsunfaehigkeit, Riester,
  Ruerup, Pensionskasse, Pensionsfonds, Altersvorsorge, bAV, betriebliche Altersversorgung,
  Sterbegeld, Risikoleben, fondsgebunden, Kapitalversicherung

- kranken: PKV, Krankenzusatz, Zahnzusatz, Pflege, Krankentagegeld, Krankenhaustagegeld

- sonstige: Nur wenn wirklich KEINE der obigen Sparten erkennbar ist

WICHTIG - HAEUFIGE VERWECHSLUNGEN:
- Unfallversicherung = IMMER sach! Auch wenn Todesfallsumme, Invaliditaet oder
  Progressionsstaffel erwaehnt wird - das sind Unfallleistungen, NICHT Lebensversicherung!
- PrivatSchutzversicherung, Kombi-Schutz, Buendelpolice = sach (Haftpflicht+Unfall+Hausrat)
- NICHT leben: Todesfallsumme/Invaliditaet bei Unfallversicherung
- Schadenlisten / Schadenaufstellungen / Schadenstatistiken = IMMER sach
- Dokumente ueber Fahrzeuge / Fahrzeugerprobung = sach (KFZ-Versicherung)

REGELN:
1. Courtage NUR wenn Hauptzweck = Provisionsabrechnung fuer Makler mit Provisionsliste
2. Kuendigung/Mahnung/Zahlungserinnerung/Lastschriftproblem/Adressaenderung/Nachtrag/Beitragsrechnung
   -> IMMER nach SPARTE des zugrundeliegenden Versicherungsvertrags zuordnen!
   Beispiel: Kuendigung einer Wohngebaeudeversicherung = "sach", nicht "sonstige"
   Beispiel: Kuendigung einer Unfallversicherung = "sach", nicht "leben"!
3. Bei Zweifel zwischen Sach und Sonstige -> IMMER Sach
4. Bei Zweifel zwischen Sach und Leben -> Sach bevorzugen (ausser eindeutig Lebensversicherung/Rente/BU)
5. "sonstige" nur wenn wirklich KEINE Versicherungssparte erkennbar ist
6. Wenn ein Dokument Versicherungsnummern (VS-Nr, VN, Policennummer) enthaelt, ist es ein
   Versicherungsdokument und gehoert in eine Sparte, NICHT in sonstige

CONFIDENCE:
- "high": Sparte ist eindeutig erkennbar (z.B. "Wohngebaeudeversicherung", "Provisionsabrechnung")
- "medium": Sparte ist wahrscheinlich, aber nicht 100%% sicher
- "low": Sparte unklar, Dokument passt nicht eindeutig in eine Sparte

TEXT:
{text}

JSON: {{"sparte": "...", "confidence": "high"|"medium"|"low", "document_date_iso": "YYYY-MM-DD" oder null, "vu_name": "..." oder null}}
'''.format(text=text)
        
        schema = {
            "name": "sparte_with_confidence",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "sparte": {
                        "type": "string",
                        "enum": ["courtage", "sach", "leben", "kranken", "sonstige"],
                        "description": "Versicherungssparte. courtage NUR bei Provisionsabrechnungen fuer Makler."
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Wie sicher ist die Sparten-Zuordnung?"
                    },
                    "document_date_iso": {
                        "type": ["string", "null"],
                        "description": "Dokumentdatum als YYYY-MM-DD oder null"
                    },
                    "vu_name": {
                        "type": ["string", "null"],
                        "description": "Name der Versicherungsgesellschaft oder null"
                    }
                },
                "required": ["sparte", "confidence", "document_date_iso", "vu_name"],
                "additionalProperties": False
            }
        }
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response_format = {"type": "json_schema", "json_schema": schema}
            effective_max_tokens = custom_max_tokens or 150
            
            estimate = None
            if self._cost_calculator:
                try:
                    estimate = self._cost_calculator.estimate_from_messages(
                        messages, model, effective_max_tokens
                    )
                except Exception:
                    pass
            
            response = self._openrouter_request(
                messages,
                model=model,
                response_format=response_format,
                max_tokens=effective_max_tokens
            )
            
            if response.get('choices'):
                content = response['choices'][0].get('message', {}).get('content', '')
                result = _safe_json_loads(content)
                if result and "sparte" in result:
                    usage = response.get('usage', {})
                    result['_usage'] = usage
                    result['_raw_response'] = content
                    result['_prompt_text'] = prompt
                    
                    server_cost = response.get('_cost', {})
                    result['_server_cost_usd'] = float(server_cost.get('real_cost_usd', 0))
                    result['_provider'] = server_cost.get('provider', 'unknown')
                    
                    if self._cost_calculator and usage:
                        try:
                            real = self._cost_calculator.calculate_real_cost(usage, model)
                            result['_estimated_cost_usd'] = estimate.estimated_cost_usd if estimate else None
                            result['_real_cost_usd'] = real.real_cost_usd
                        except Exception:
                            pass
                    
                    return result
                
        except Exception as e:
            logger.error(f"Stufe-1-Klassifikation fehlgeschlagen: {e}")
        
        return None
    
    def _classify_sparte_detail(self, text: str, model: str = DEFAULT_EXTRACT_MODEL,
                                custom_prompt: str = None,
                                custom_max_tokens: int = None) -> Optional[dict]:
        """
        Stufe 2: Detaillierte Klassifikation mit staerkerem Modell.
        
        Wird nur bei niedriger Confidence aus Stufe 1 aufgerufen.
        Gibt zusaetzlich einen Dokumentnamen zurueck (besonders bei "sonstige").
        
        Args:
            text: Mehr Text (5 Seiten)
            model: LLM-Modell
            custom_prompt: Optionaler benutzerdefinierter Prompt (mit {text} Platzhalter)
            custom_max_tokens: Optionale max_tokens
            
        Returns:
            {"sparte": ..., "document_date_iso": ..., "vu_name": ..., "document_name": ...}
        """
        if custom_prompt:
            # .replace() statt .format() - siehe Kommentar in _classify_sparte_request
            prompt = custom_prompt.replace('{text}', text)
        else:
            prompt = '''Analysiere dieses Versicherungsdokument detailliert.

SPARTEN:
- courtage: NUR Provisionsabrechnungen/Courtageabrechnungen fuer Makler
- sach: KFZ, Haftpflicht, PHV, Tierhalterhaftpflicht, Hausrat, Wohngebaeude, Unfall,
  Unfallversicherung, Rechtsschutz, Gewerbe, Betriebshaftpflicht, Glas, Reise,
  Gebaeudeversicherung, PrivatSchutzversicherung, Kombi-Schutz, Buendelversicherung,
  Schadenaufstellung, Schadenliste, Schadenstatistik, Schadenhistorie, Schadenquote,
  Fahrzeug, Fahrzeugerprobung
- leben: Lebensversicherung, Rente, BU, Riester, Ruerup, Pensionskasse, bAV, Sterbegeld
- kranken: PKV, Krankenzusatz, Zahnzusatz, Pflege, Krankentagegeld
- sonstige: Wenn wirklich KEINE Versicherungssparte erkennbar ist

WICHTIG: Unfallversicherung = IMMER sach (auch bei Todesfallsumme/Invaliditaet)!
WICHTIG: Schadenlisten/Schadenaufstellungen = IMMER sach!
WICHTIG: Wenn Versicherungsnummern (VS-Nr, VN, Policennummer) enthalten -> Sparte zuordnen, NICHT sonstige!

REGELN:
1. Courtage NUR bei Provisionsabrechnungen mit Provisionsliste
2. Kuendigung/Mahnung/Beitragsrechnung -> nach Sparte des Vertrags zuordnen
3. Bei Zweifel zwischen Sach und Sonstige -> Sach bevorzugen
4. Bei Zweifel zwischen Sach und Leben -> Sach bevorzugen (ausser eindeutig Lebensversicherung/Rente/BU)
5. Bei "sonstige": Gib einen kurzen Dokumentnamen als document_name zurueck!
   Beispiele: "Schriftwechsel", "Maklervertrag", "Vollmacht", "Begleitschreiben", 
   "Vermittlerinfo", "Allgemeine_Information"
6. "sonstige" nur wenn wirklich KEIN Versicherungsbezug erkennbar ist

TEXT:
{text}

JSON: {{"sparte": "...", "document_date_iso": "YYYY-MM-DD" oder null, "vu_name": "..." oder null, "document_name": "..." oder null}}
'''.format(text=text)
        
        schema = {
            "name": "sparte_detail",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "sparte": {
                        "type": "string",
                        "enum": ["courtage", "sach", "leben", "kranken", "sonstige"],
                        "description": "Versicherungssparte"
                    },
                    "document_date_iso": {
                        "type": ["string", "null"],
                        "description": "Dokumentdatum als YYYY-MM-DD oder null"
                    },
                    "vu_name": {
                        "type": ["string", "null"],
                        "description": "Name der Versicherungsgesellschaft oder null"
                    },
                    "document_name": {
                        "type": ["string", "null"],
                        "description": "Kurzer Dokumentname bei sonstige (z.B. Schriftwechsel, Vollmacht)"
                    }
                },
                "required": ["sparte", "document_date_iso", "vu_name", "document_name"],
                "additionalProperties": False
            }
        }
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response_format = {"type": "json_schema", "json_schema": schema}
            effective_max_tokens = custom_max_tokens or 200
            
            estimate = None
            if self._cost_calculator:
                try:
                    estimate = self._cost_calculator.estimate_from_messages(
                        messages, model, effective_max_tokens
                    )
                except Exception:
                    pass
            
            response = self._openrouter_request(
                messages,
                model=model,
                response_format=response_format,
                max_tokens=effective_max_tokens
            )
            
            if response.get('choices'):
                content = response['choices'][0].get('message', {}).get('content', '')
                result = _safe_json_loads(content)
                if result and "sparte" in result:
                    usage = response.get('usage', {})
                    result['_usage'] = usage
                    result['_raw_response'] = content
                    result['_prompt_text'] = prompt
                    
                    server_cost = response.get('_cost', {})
                    result['_server_cost_usd'] = float(server_cost.get('real_cost_usd', 0))
                    result['_provider'] = server_cost.get('provider', 'unknown')
                    
                    if self._cost_calculator and usage:
                        try:
                            real = self._cost_calculator.calculate_real_cost(usage, model)
                            result['_estimated_cost_usd'] = estimate.estimated_cost_usd if estimate else None
                            result['_real_cost_usd'] = real.real_cost_usd
                        except Exception:
                            pass
                    
                    return result
                
        except Exception as e:
            logger.error(f"Stufe-2-Klassifikation fehlgeschlagen: {e}")
        
        return None
