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
DEFAULT_MAX_CONCURRENT_AI_CALLS = 3
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
DEFAULT_EXTRACT_MODEL = "openai/gpt-4o"
DEFAULT_TRIAGE_MODEL = "openai/gpt-4o-mini"  # Guenstiges Modell fuer schnelle Kategorisierung

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
    
    def _ensure_api_key(self) -> str:
        """Holt den API-Key vom Server falls noch nicht vorhanden."""
        if self._api_key:
            return self._api_key
        
        logger.info("Hole OpenRouter API-Key vom Server...")
        
        try:
            response = self.api_client.get("/ai/key")
            if response.get('success') and response.get('data', {}).get('api_key'):
                self._api_key = response['data']['api_key']
                logger.info("API-Key erhalten")
                return self._api_key
            else:
                raise APIError("API-Key nicht in Antwort enthalten")
        except APIError as e:
            logger.error(f"Fehler beim Abrufen des API-Keys: {e}")
            raise
    
    def get_credits(self) -> Optional[dict]:
        """
        Ruft das aktuelle OpenRouter-Guthaben ab.
        
        Returns:
            dict mit 'balance', 'total_credits', 'total_usage' und 'currency' oder None bei Fehler
            
        Beispiel-Antwort von OpenRouter /api/v1/credits:
        {
            "data": {
                "total_credits": 100.5,
                "total_usage": 25.75
            }
        }
        """
        try:
            api_key = self._ensure_api_key()
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = self._session.get(
                f"{OPENROUTER_BASE_URL}/credits",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    total_credits = data['data'].get('total_credits', 0)
                    total_usage = data['data'].get('total_usage', 0)
                    
                    # Berechne verbleibendes Guthaben
                    balance = total_credits - total_usage
                    
                    return {
                        'total_credits': total_credits,
                        'total_usage': total_usage,
                        'balance': balance,
                        'currency': 'USD'
                    }
            
            logger.warning(f"Credits-Abfrage fehlgeschlagen: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            logger.warning(f"Fehler beim Abrufen der Credits: {e}")
            return None
    
    def _openrouter_request(self, messages: List[dict], model: str = DEFAULT_VISION_MODEL,
                            response_format: dict = None, max_tokens: int = 4096) -> dict:
        """
        Sendet eine Anfrage an OpenRouter mit Retry-Logik und Backpressure-Kontrolle.
        
        BACKPRESSURE: Verwendet Semaphore um parallele KI-Aufrufe zu begrenzen.
        Dies verhindert Server-Ueberlastung bei hohem Dokumenten-Durchsatz.
        
        Args:
            messages: Chat-Nachrichten
            model: Modell-ID
            response_format: Optional - Structured Output Schema
            max_tokens: Maximale Ausgabelaenge
            
        Returns:
            API-Antwort als dict
            
        Raises:
            APIError: Nach MAX_RETRIES fehlgeschlagenen Versuchen
        """
        api_key = self._ensure_api_key()
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://acencia.info",
            "X-Title": "BiPRO-GDV Tool"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens
        }
        
        if response_format:
            payload["response_format"] = response_format
        
        # BACKPRESSURE: Semaphore verwenden
        semaphore = get_ai_semaphore()
        _increment_queue_depth()
        queue_depth = get_ai_queue_depth()
        
        if queue_depth > 1:
            logger.debug(f"KI-Queue-Tiefe: {queue_depth} wartende Aufrufe")
        
        logger.debug(f"OpenRouter Request: model={model}, messages={len(messages)}, queue_depth={queue_depth}")
        
        last_error = None
        
        # Semaphore erwerben (blockiert wenn zu viele parallele Aufrufe)
        semaphore.acquire()
        try:
            for attempt in range(MAX_RETRIES):
                try:
                    response = self._session.post(
                        f"{OPENROUTER_BASE_URL}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=120  # Vision-Calls koennen lange dauern
                    )
                    
                    # Retryable Status Codes
                    if response.status_code in RETRY_STATUS_CODES:
                        wait_time = RETRY_BACKOFF_FACTOR * (attempt + 1)
                        logger.warning(
                            f"OpenRouter HTTP {response.status_code}, "
                            f"Retry {attempt + 1}/{MAX_RETRIES} in {wait_time:.1f}s"
                        )
                        time.sleep(wait_time)
                        continue
                    
                    # Nicht-retryable Fehler
                    if response.status_code != 200:
                        error_data = response.json() if response.text else {}
                        error_msg = error_data.get('error', {}).get('message', f"HTTP {response.status_code}")
                        logger.error(f"OpenRouter Fehler: {error_msg}")
                        raise APIError(f"OpenRouter Fehler: {error_msg}", status_code=response.status_code)
                    
                    # Erfolg
                    return response.json()
                    
                except requests.RequestException as e:
                    last_error = e
                    wait_time = RETRY_BACKOFF_FACTOR * (attempt + 1)
                    logger.warning(
                        f"OpenRouter Netzwerkfehler: {e}, "
                        f"Retry {attempt + 1}/{MAX_RETRIES} in {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)
            
            # Alle Retries fehlgeschlagen
            logger.error(f"OpenRouter nach {MAX_RETRIES} Versuchen nicht erreichbar")
            raise APIError(f"OpenRouter dauerhaft nicht erreichbar: {last_error}")
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
    
    def extract_text_from_images(self, images_b64: List[str], 
                                  model: str = DEFAULT_VISION_MODEL) -> str:
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
                    "Achte besonders auf: Versicherer-Name, Datum, Dokumenttyp."
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
        
        response = self._openrouter_request(messages, model=model, max_tokens=8192)
        
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
    
    def classify_sparte_with_date(self, pdf_path: str) -> dict:
        """
        Zweistufige Klassifikation mit Confidence-Scoring (nur PDFs).
        
        Stufe 1: GPT-4o-mini (2 Seiten, schnell + guenstig)
          -> confidence "high"/"medium" -> fertig
          -> confidence "low" -> Stufe 2
        
        Stufe 2: GPT-4o (5 Seiten, praeziser)
          -> Endgueltiges Ergebnis inkl. Dokumentname bei "sonstige"
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            
        Returns:
            {"sparte": ..., "confidence": ..., "document_date_iso": ..., "vu_name": ..., "document_name": ...}
        """
        logger.info(f"Sparten-Klassifikation (minimal): {pdf_path}")
        
        # Text extrahieren (erste 2 Seiten)
        text = self._extract_relevant_text(pdf_path, for_triage=True)
        
        if not text.strip():
            # Fallback zu OCR
            try:
                images = self.pdf_to_images(pdf_path, max_pages=1)
                if images:
                    text = self.extract_text_from_images(images[:1])
            except Exception as e:
                logger.error(f"OCR fehlgeschlagen: {e}")
                return {"sparte": "sonstige", "confidence": "low", "document_date_iso": None, 
                        "vu_name": None, "document_name": None}
        
        if not text.strip():
            return {"sparte": "sonstige", "confidence": "low", "document_date_iso": None, 
                    "vu_name": None, "document_name": None}
        
        # =====================================================
        # STUFE 1: GPT-4o-mini (schnell, guenstig)
        # =====================================================
        result = self._classify_sparte_request(
            text[:2500], 
            model=DEFAULT_TRIAGE_MODEL
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
        # STUFE 2: GPT-4o bei "low" Confidence (nur PDFs)
        # =====================================================
        if confidence == "low" and pdf_path.lower().endswith('.pdf'):
            logger.info(f"Confidence 'low' -> Stufe 2 mit GPT-4o (mehr Text, praeziser)")
            
            # Mehr Text: 5 Seiten statt 2
            full_text = self._extract_relevant_text(pdf_path, for_triage=False)
            if not full_text.strip():
                full_text = text  # Fallback auf vorherigen Text
            
            result_stage2 = self._classify_sparte_detail(
                full_text[:5000],
                model=DEFAULT_EXTRACT_MODEL
            )
            
            if result_stage2:
                logger.info(
                    f"Stufe 2 (GPT-4o): sparte={result_stage2.get('sparte')}, "
                    f"document_name={result_stage2.get('document_name')}, "
                    f"VU={result_stage2.get('vu_name')}"
                )
                # Stufe 2 Ergebnis hat Vorrang
                result_stage2["confidence"] = "medium"  # Stufe 2 ist mindestens medium
                return result_stage2
        
        return result
    
    def _classify_sparte_request(self, text: str, model: str = DEFAULT_TRIAGE_MODEL) -> Optional[dict]:
        """
        Stufe 1: Schnelle Sparten-Klassifikation mit Confidence-Scoring.
        
        Args:
            text: Extrahierter Text
            model: LLM-Modell
            
        Returns:
            {"sparte": ..., "confidence": ..., "document_date_iso": ..., "vu_name": ...}
        """
        prompt = '''Klassifiziere dieses Versicherungsdokument in eine Sparte.

SPARTEN:
- courtage: NUR Provisionsabrechnungen/Courtageabrechnungen vom VU an den MAKLER/VERMITTLER
  MUSS enthalten: Auflistung von Vertraegen mit Provisionssaetzen/Courtagebetraegen
  NICHT courtage: Beitragsrechnungen, Kuendigungen, Policen, Nachtraege, Mahnungen,
  Adressaenderungen, Schadensmeldungen, Zahlungserinnerungen, Antraege - auch wenn
  sie von einer Versicherung kommen! Courtage = PROVISION FUER DEN MAKLER.

- sach: KFZ, Haftpflicht, Privathaftpflicht, PHV, Tierhalterhaftpflicht, Hundehaftpflicht,
  Hausrat, Wohngebaeude, Unfall, Rechtsschutz, Gewerbe, Betriebshaftpflicht, Glas, Reise,
  Gebaeudeversicherung, Inhaltsversicherung, Bauherrenhaftpflicht, Elektronik

- leben: Lebensversicherung, Rente, Rentenversicherung, BU, Berufsunfaehigkeit, Riester,
  Ruerup, Pensionskasse, Pensionsfonds, Altersvorsorge, bAV, betriebliche Altersversorgung,
  Sterbegeld, Risikoleben, fondsgebunden, Kapitalversicherung

- kranken: PKV, Krankenzusatz, Zahnzusatz, Pflege, Krankentagegeld, Krankenhaustagegeld

- sonstige: Nur wenn KEINE der obigen Sparten passt

REGELN:
1. Courtage NUR wenn Hauptzweck = Provisionsabrechnung fuer Makler mit Provisionsliste
2. Kuendigung/Mahnung/Zahlungserinnerung/Lastschriftproblem/Adressaenderung/Nachtrag/Beitragsrechnung
   -> IMMER nach SPARTE des zugrundeliegenden Versicherungsvertrags zuordnen!
   Beispiel: Kuendigung einer Wohngebaeudeversicherung = "sach", nicht "sonstige"
   Beispiel: Lastschrift-Rueckgabe bei KFZ-Versicherung = "sach", nicht "sonstige"
3. Bei Zweifel zwischen Sach und Sonstige -> IMMER Sach
4. "sonstige" nur wenn wirklich KEINE Sparte erkennbar ist

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
            
            response = self._openrouter_request(
                messages,
                model=model,
                response_format=response_format,
                max_tokens=150
            )
            
            if response.get('choices'):
                content = response['choices'][0].get('message', {}).get('content', '')
                result = _safe_json_loads(content)
                if result and "sparte" in result:
                    return result
                
        except Exception as e:
            logger.error(f"Stufe-1-Klassifikation fehlgeschlagen: {e}")
        
        return None
    
    def _classify_sparte_detail(self, text: str, model: str = DEFAULT_EXTRACT_MODEL) -> Optional[dict]:
        """
        Stufe 2: Detaillierte Klassifikation mit GPT-4o.
        
        Wird nur bei "low" Confidence aus Stufe 1 aufgerufen.
        Gibt zusaetzlich einen Dokumentnamen zurueck (besonders bei "sonstige").
        
        Args:
            text: Mehr Text (5 Seiten)
            model: Staerkeres LLM-Modell (GPT-4o)
            
        Returns:
            {"sparte": ..., "document_date_iso": ..., "vu_name": ..., "document_name": ...}
        """
        prompt = '''Analysiere dieses Versicherungsdokument detailliert.

SPARTEN:
- courtage: NUR Provisionsabrechnungen/Courtageabrechnungen fuer Makler
- sach: KFZ, Haftpflicht, PHV, Tierhalterhaftpflicht, Hausrat, Wohngebaeude, Unfall, 
  Rechtsschutz, Gewerbe, Betriebshaftpflicht, Glas, Reise, Gebaeudeversicherung
- leben: Lebensversicherung, Rente, BU, Riester, Ruerup, Pensionskasse, bAV, Sterbegeld
- kranken: PKV, Krankenzusatz, Zahnzusatz, Pflege, Krankentagegeld
- sonstige: Wenn KEINE Sparte passt (z.B. allgemeiner Schriftwechsel, Maklervertrag)

REGELN:
1. Courtage NUR bei Provisionsabrechnungen mit Provisionsliste
2. Kuendigung/Mahnung/Beitragsrechnung -> nach Sparte des Vertrags zuordnen
3. Bei Zweifel zwischen Sach und Sonstige -> Sach bevorzugen
4. Bei "sonstige": Gib einen kurzen Dokumentnamen als document_name zurueck!
   Beispiele: "Schriftwechsel", "Maklervertrag", "Vollmacht", "Begleitschreiben", 
   "Vermittlerinfo", "Allgemeine_Information"

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
            
            response = self._openrouter_request(
                messages,
                model=model,
                response_format=response_format,
                max_tokens=200
            )
            
            if response.get('choices'):
                content = response['choices'][0].get('message', {}).get('content', '')
                result = _safe_json_loads(content)
                if result and "sparte" in result:
                    return result
                
        except Exception as e:
            logger.error(f"Stufe-2-Klassifikation fehlgeschlagen: {e}")
        
        return None
