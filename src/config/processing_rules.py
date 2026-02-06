"""
Verarbeitungsregeln fuer die automatische Dokumenten-Klassifikation.

Diese Datei enthaelt konfigurierbare Regeln fuer:
- BiPRO-Kategorien fuer automatische Box-Zuordnung
- GDV-Dateiendungen
- XML-Rohdateien-Patterns
- Courtage/Provisions-Schluesselwoerter
- Sach/Leben Kategorisierung

Die Regeln koennen spaeter ueber eine UI angepasst werden.

BiPRO-Kategorien basierend auf SmartAdmin/IWM FinanzOffice Analyse (2026-02-04):
- Quelle: F:/00___AGENT/BIPRO_CODE_DETAILS.md
- Format: 9-stellig (XXXYYYZZZ = Hauptbereich/Teilbereich1/Teilbereich2)
"""

from typing import Dict, List, Any, Optional
from enum import Enum


# ============================================================================
# PDF VALIDATION STATUS / REASON CODES
# ============================================================================

class PDFValidationStatus(Enum):
    """
    Technische Validierungsstatus fuer PDF-Dateien.
    
    Diese Codes beschreiben den technischen Zustand einer PDF-Datei,
    NICHT die fachliche Kategorie (courtage, sach, leben, etc.).
    
    Verwendung:
    - OK: PDF ist gueltig und kann verarbeitet werden
    - PDF_ENCRYPTED: Passwortgeschuetzt, kann nicht gelesen werden
    - PDF_CORRUPT: Strukturell defekt, nicht reparierbar
    - PDF_INCOMPLETE: Download unvollstaendig oder abgebrochen
    - PDF_XFA: Enthaelt XFA-Formulare, KI-Verarbeitung problematisch
    - PDF_REPAIRED: War defekt, wurde erfolgreich repariert
    - PDF_NO_PAGES: PDF hat keine Seiten
    - PDF_LOAD_ERROR: Konnte nicht geladen werden (generischer Fehler)
    """
    OK = "OK"
    PDF_ENCRYPTED = "PDF_ENCRYPTED"
    PDF_CORRUPT = "PDF_CORRUPT"
    PDF_INCOMPLETE = "PDF_INCOMPLETE"
    PDF_XFA = "PDF_XFA"
    PDF_REPAIRED = "PDF_REPAIRED"
    PDF_NO_PAGES = "PDF_NO_PAGES"
    PDF_LOAD_ERROR = "PDF_LOAD_ERROR"


def get_validation_status_description(status: PDFValidationStatus) -> str:
    """
    Gibt eine lesbare Beschreibung fuer einen Validierungsstatus zurueck.
    
    Args:
        status: PDFValidationStatus Enum-Wert
        
    Returns:
        Deutsche Beschreibung des Status
    """
    descriptions = {
        PDFValidationStatus.OK: "PDF ist gueltig",
        PDFValidationStatus.PDF_ENCRYPTED: "PDF ist passwortgeschuetzt",
        PDFValidationStatus.PDF_CORRUPT: "PDF ist strukturell defekt",
        PDFValidationStatus.PDF_INCOMPLETE: "PDF-Download war unvollstaendig",
        PDFValidationStatus.PDF_XFA: "PDF enthaelt XFA-Formulare",
        PDFValidationStatus.PDF_REPAIRED: "PDF wurde erfolgreich repariert",
        PDFValidationStatus.PDF_NO_PAGES: "PDF hat keine Seiten",
        PDFValidationStatus.PDF_LOAD_ERROR: "PDF konnte nicht geladen werden",
    }
    return descriptions.get(status, "Unbekannter Status")


# ============================================================================
# GDV FALLBACK KONSTANTEN
# ============================================================================

# Fallback-Werte fuer GDV-Metadaten wenn Parsing fehlschlaegt
GDV_FALLBACK_VU = "Xvu"      # Unbekannter Versicherer
GDV_FALLBACK_DATE = "kDatum"  # Kein Datum gefunden

# Reason-Codes fuer GDV-Parsing-Probleme
class GDVParseStatus(Enum):
    """
    Status der GDV-Metadaten-Extraktion.
    """
    OK = "OK"
    NO_VORSATZ = "GDV_NO_VORSATZ"       # Kein 0001-Satz gefunden
    ENCODING_ERROR = "GDV_ENCODING"     # Encoding-Fehler
    INVALID_FORMAT = "GDV_INVALID"      # Ungueltiges Format
    VU_MISSING = "GDV_VU_MISSING"       # VU-Nummer fehlt
    DATE_MISSING = "GDV_DATE_MISSING"   # Datum fehlt
    PARTIAL = "GDV_PARTIAL"             # Nur teilweise extrahiert


# ============================================================================
# DOKUMENT STATE MACHINE
# ============================================================================

class DocumentProcessingStatus(Enum):
    """
    Vollstaendige Zustandsmaschine fuer Dokumentenverarbeitung.
    
    Statusuebergaenge:
        downloaded -> validated -> classified -> renamed -> archived
                |          |             |           |
                v          v             v           v
           quarantined   error        error       error
    
    Jeder Uebergang soll atomar und geloggt werden.
    Abwaertskompatibel: alte Werte (pending, processing, completed) bleiben gueltig.
    """
    # Neue granulare Status
    DOWNLOADED = "downloaded"      # Datei vom BiPRO heruntergeladen
    VALIDATED = "validated"        # PDF-Validierung durchgefuehrt
    CLASSIFIED = "classified"      # KI/Regel-Klassifikation abgeschlossen
    RENAMED = "renamed"            # Dateiname angepasst
    ARCHIVED = "archived"          # In Ziel-Box verschoben
    QUARANTINED = "quarantined"    # In Quarantaene (z.B. ungueltiges Format, nicht verarbeitbar)
    ERROR = "error"                # Fehler aufgetreten (mit Reason-Code)
    
    # Legacy-Status (abwaertskompatibel)
    PENDING = "pending"            # Wartet auf Verarbeitung
    PROCESSING = "processing"      # Wird gerade verarbeitet
    COMPLETED = "completed"        # Verarbeitung abgeschlossen
    
    @classmethod
    def is_valid_transition(cls, from_status, to_status) -> bool:
        """
        Prueft ob ein Statusuebergang gueltig ist.
        
        Args:
            from_status: Aktueller Status (String oder Enum)
            to_status: Ziel-Status (String oder Enum)
            
        Returns:
            True wenn Uebergang erlaubt
        """
        # Strings zu Enums konvertieren wenn noetig
        if isinstance(from_status, str):
            try:
                from_status = cls(from_status)
            except ValueError:
                return False
        
        if isinstance(to_status, str):
            try:
                to_status = cls(to_status)
            except ValueError:
                return False
        
        # Erlaubte Uebergaenge
        valid_transitions = {
            # Neue Uebergaenge
            cls.DOWNLOADED: [cls.VALIDATED, cls.QUARANTINED, cls.ERROR, cls.PROCESSING],
            cls.VALIDATED: [cls.CLASSIFIED, cls.QUARANTINED, cls.ERROR],
            cls.CLASSIFIED: [cls.RENAMED, cls.ARCHIVED, cls.ERROR],
            cls.RENAMED: [cls.ARCHIVED, cls.ERROR],
            cls.ARCHIVED: [cls.ERROR],  # Re-Processing nur ueber Reset
            cls.QUARANTINED: [cls.DOWNLOADED, cls.ERROR],  # Retry nach Korrektur
            cls.ERROR: [cls.DOWNLOADED, cls.PENDING, cls.QUARANTINED],  # Retry erlaubt
            
            # Legacy-Uebergaenge
            cls.PENDING: [cls.PROCESSING, cls.DOWNLOADED, cls.ERROR],
            cls.PROCESSING: [cls.COMPLETED, cls.CLASSIFIED, cls.VALIDATED, cls.ERROR, cls.QUARANTINED],
            cls.COMPLETED: [cls.ARCHIVED, cls.ERROR],
        }
        
        allowed = valid_transitions.get(from_status, [])
        return to_status in allowed
    
    @classmethod
    def get_status_description(cls, status: 'DocumentProcessingStatus') -> str:
        """
        Gibt eine lesbare Beschreibung fuer einen Status zurueck.
        """
        descriptions = {
            cls.DOWNLOADED: "Heruntergeladen",
            cls.VALIDATED: "Validiert",
            cls.CLASSIFIED: "Klassifiziert",
            cls.RENAMED: "Umbenannt",
            cls.ARCHIVED: "Archiviert",
            cls.QUARANTINED: "In Quarantaene",
            cls.ERROR: "Fehler",
            cls.PENDING: "Wartend",
            cls.PROCESSING: "In Verarbeitung",
            cls.COMPLETED: "Abgeschlossen",
        }
        return descriptions.get(status, "Unbekannt")


# ============================================================================
# BiPRO-KATEGORIEN fuer automatische Box-Zuordnung
# ============================================================================

# Courtage/Provision -> Courtage Box
BIPRO_COURTAGE_CODES = [
    "300001000",  # VU-VM-Abrechnung: Provisionsabrechnung
    "300002000",  # VU-VM-Abrechnung: Courtageabrechnung
    "300003000",  # VU-VM-Abrechnung: Vergütungsübersicht
    # Hinweis: 300er-Bereich = VU-VM-Abrechnung (Provision)
]

# VU-Dokumente nach Geschäftsvorfall -> Sach/Leben/Kranken
# Diese Codes werden per Sparten-KI weiterverarbeitet
BIPRO_VU_DOCUMENT_CODES = {
    # 100 - Antrag-Neugeschäft
    "100007000": "police",       # Policierung / Dokument erstellt
    "100002000": "eingang",      # Eingangsbestätigung
    "100001000": "antrag",       # Antragsversand
    "100005000": "nachfrage",    # Nachfrage
    
    # 110 - Partner-Änderung
    "110011000": "adresse",      # Adressänderung -> Vertragsdokumente
    
    # 120 - Vertrag-Änderung
    "120010000": "nachtrag",     # Vertragsumstellung / Nachtrag
    "120016000": "erhoehung",    # Erhöhung
    "120017000": "dynamik",      # Dynamik
    
    # 140 - Beitrag-Inkasso
    "140012000": "mahnung",      # Beitragsrückstand / Mahnung
    "140013000": "rechnung",     # Beitragsrechnung
    "140011000": "bankdaten",    # Bankverbindung fehlt
    
    # 150 - Versicherungsfall-Leistung
    "150013000": "schaden",      # Schaden
    "150010000": "ablauf",       # Ablauf
    
    # 160 - Kündigung
    "160010000": "kuendigung",   # Kündigung durch Kunde
    "160011000": "kuendigung",   # Kündigung durch Gesellschaft
}

# BiPRO-Codes fuer GDV-Dateien (Bestandsdaten)
# Diese Dateien haben oft .pdf Endung, sind aber tatsaechlich GDV-Datensaetze
BIPRO_GDV_CODES = [
    "999010010",  # GDV Bestandsdaten - Bestand (ersichtlich aus BiPRO-Logs)
    "999010000",  # GDV Bestandsdaten - Allgemein
    "999011000",  # GDV Bestandsdaten - Variante
    # 999er-Bereich = GDV-Datenaustausch
]

# Spezielle BiPRO-Codes die NICHT zur KI gehen
BIPRO_SKIP_AI_CODES = [
    # GDV-Codes brauchen keine KI
    "999010010",
    "999010000",
    "999011000",
]


PROCESSING_RULES: Dict[str, Any] = {
    # BiPRO-Codes die direkt zur Courtage-Box gehen
    "bipro_courtage_codes": BIPRO_COURTAGE_CODES,
    
    # BiPRO-Codes fuer VU-Dokumente (brauchen Sparten-KI)
    "bipro_vu_document_codes": BIPRO_VU_DOCUMENT_CODES,
    
    # BiPRO-Codes die keine KI-Verarbeitung brauchen
    "bipro_skip_ai_codes": BIPRO_SKIP_AI_CODES,
    # Dateiendungen die EINDEUTIG GDV-Dateien sind (keine Content-Pruefung noetig)
    # .txt wird IMMER als GDV behandelt (BiPRO liefert GDV als .txt)
    "gdv_extensions": [
        ".gdv",
        ".txt",
    ],
    
    # Dateiendungen die per Content geprueft werden muessen
    # Wenn erste Zeile mit '0001' beginnt -> GDV, sonst zur KI
    "gdv_content_check_extensions": [
        "",  # Dateien ohne Endung
    ],
    
    # Bekannte Dateiendungen (keine Magic-Byte-Erkennung noetig)
    # Bei allen ANDEREN Endungen wird der Inhalt geprueft
    "known_extensions": [
        ".pdf",
        ".xml",
        ".gdv",
        ".txt",
        "",  # Dateien ohne Endung
    ],
    
    # Patterns fuer XML-Rohdateien (BiPRO-Lieferungen)
    # * = Wildcard
    "raw_xml_patterns": [
        "Lieferung_Roh_*.xml",
        "*_Roh_*.xml",
        "BiPRO_Raw_*.xml",
    ],
    
    # Schluesselwoerter fuer Courtage/Provisions-Dokumente
    # Case-insensitive Matching
    "courtage_keywords": [
        # Deutsch - Standard
        "Provisionsabrechnung",
        "Courtage",
        "Courtageabrechnung",
        "Vermittlervergütung",
        "Vermittlerverguetung",
        "Vergütungsabrechnung",
        "Verguetungsabrechnung",
        "Abschlussvergütung",
        "Abschlussverguetung",
        "Provisionsliste",
        "Vermittlerabrechnung",
        "Abrechnung Vermittlerprovision",
        "Vergütungsnachweis",
        "Verguetungsnachweis",
        "Provisionsnachweis",
        # Alternative Begriffe
        "Vergütungsübersicht",
        "Verguetungsuebersicht",
        "Vergütungsdatensatz",
        "Verguetungsdatensatz",
        "Vergütungsreport",
        "Verguetungsreport",
        "Abrechnungsdatensatz Vermittlung",
        "Abrechnungslauf Provision",
        "Provisionen-lauf",
        "Courtage-Lauf",
        "Abrechnungsübersicht",
        "Abrechnungsuebersicht",
        # Englisch (technisch)
        "Commission Statement",
        "Commission Settlement",
        # Zusaetzliche Patterns
        "Abrechnung der Vermittlungsvergütung",
        "Abrechnung der Vermittlerverguetung",
        "Abrechnung Geschäftsvorfälle",
        "Abrechnung Geschaeftsvorfaelle",
    ],
    
    # Schluesselwoerter fuer Leben-Versicherungen
    "leben_keywords": [
        "leben",
        "lebensversicherung",
        "life",
        "rente",
        "rentenversicherung",
        "pension",
        "altersvorsorge",
        "berufsunfähigkeit",
        "berufsunfaehigkeit",
        "bu",
        "bu-versicherung",
        "risikoleben",
        "risiko",
        "kapitalversicherung",
        "kapital",
        "fondspolicen",
        "fondsgebunden",
    ],
    
    # Schluesselwoerter fuer Sach-Versicherungen
    "sach_keywords": [
        "sach",
        "sachversicherung",
        "haftpflicht",
        "privathaftpflicht",
        "berufshaftpflicht",
        "hausrat",
        "hausratversicherung",
        "wohngebäude",
        "wohngebaeude",
        "gebäudeversicherung",
        "gebaeudeversicherung",
        "kfz",
        "kfz-versicherung",
        "auto",
        "autoversicherung",
        "unfall",
        "unfallversicherung",
        "rechtsschutz",
        "rechtsschutzversicherung",
        "glas",
        "glasversicherung",
        "elektronik",
        "elektronikversicherung",
        "transport",
        "transportversicherung",
        "gewerbe",
        "gewerbeversicherung",
        "betrieb",
        "betriebshaftpflicht",
        "hundehaftpflicht",
        "pferdehaftpflicht",
        "tierhalterhaftpflicht",
        "reise",
        "reiseversicherung",
        "auslandskranken",
    ],
    
    # Schluesselwoerter fuer Kranken-Versicherungen
    "kranken_keywords": [
        "kranken",
        "krankenversicherung",
        "private kranken",
        "pkv",
        "gesetzliche kranken",
        "gkv",
        "zusatzversicherung",
        "krankenzusatz",
        "zahnzusatz",
        "pflegeversicherung",
        "pflege",
        "krankentagegeld",
        "krankengeld",
    ],
    
    # Maximale Dateigrösse fuer automatische Verarbeitung (in Bytes)
    # Standard: 50 MB
    "max_file_size": 50 * 1024 * 1024,
    
    # Maximale Seitenanzahl fuer PDF-OCR
    "max_pdf_pages": 10,
    
    # Automatische Verarbeitung aktiviert
    "auto_processing_enabled": True,
    
    # Verzoegerung zwischen Dokumenten (in Sekunden)
    # Um API-Rate-Limits zu vermeiden
    "processing_delay": 1.0,
}


# ============================================================================
# BiPRO DOWNLOAD KONFIGURATION
# Einstellungen fuer parallele Downloads mit Rate Limiting
# ============================================================================

BIPRO_DOWNLOAD_CONFIG = {
    # Maximale Anzahl paralleler Download-Worker
    # Hoeherer Wert = schneller, aber mehr Server-Last
    # Erhöht auf 10 Worker für bessere Performance
    # AdaptiveRateLimiter reduziert automatisch bei Server-Überlastung
    'max_parallel_workers': 10,
    
    # Minimale Worker-Anzahl bei Rate Limiting
    # Bei HTTP 429/503 wird auf diesen Wert reduziert
    'min_workers_on_rate_limit': 1,
    
    # Initiale Wartezeit bei Rate Limiting (Sekunden)
    # Wird bei wiederholtem Rate Limiting exponentiell erhoeht
    'initial_backoff_seconds': 1.0,
    
    # Maximale Wartezeit bei Rate Limiting (Sekunden)
    # Backoff wird nie hoeher als dieser Wert
    'max_backoff_seconds': 30.0,
    
    # Maximale Retry-Versuche pro Lieferung
    # Nach X Fehlversuchen wird Lieferung als fehlgeschlagen markiert
    'max_retries_per_shipment': 3,
    
    # Erfolgreiche Downloads bis Worker wieder erhoeht wird
    # Nach X Erfolgen wird Worker-Anzahl um 1 erhoeht (bis max_parallel_workers)
    'worker_recovery_after': 10,
    
    # Timeout fuer einzelnen Download (Sekunden)
    'download_timeout': 120,
    
    # Parallele Downloads aktiviert
    # False = sequentieller Download (altes Verhalten)
    'parallel_enabled': True,
}


def get_bipro_download_config(key: str, default: Any = None) -> Any:
    """
    Holt eine BiPRO-Download-Konfiguration.
    
    Args:
        key: Konfigurationsschluessel
        default: Standardwert wenn nicht gefunden
        
    Returns:
        Konfigurationswert oder default
    """
    return BIPRO_DOWNLOAD_CONFIG.get(key, default)


def get_rule(key: str, default: Any = None) -> Any:
    """
    Holt eine Regel aus der Konfiguration.
    
    Args:
        key: Regel-Schluessel
        default: Standardwert wenn nicht gefunden
        
    Returns:
        Regel-Wert oder default
    """
    return PROCESSING_RULES.get(key, default)


def is_gdv_extension(extension: str) -> bool:
    """Prueft ob die Dateiendung eine GDV-Datei markiert."""
    ext = extension.lower() if extension else ""
    return ext in PROCESSING_RULES.get("gdv_extensions", [])


def is_courtage_keyword(text: str) -> bool:
    """Prueft ob der Text Courtage-Schluesselwoerter enthaelt."""
    text_lower = text.lower()
    keywords = PROCESSING_RULES.get("courtage_keywords", [])
    return any(kw.lower() in text_lower for kw in keywords)


def is_leben_keyword(text: str) -> bool:
    """Prueft ob der Text Leben-Schluesselwoerter enthaelt."""
    text_lower = text.lower()
    keywords = PROCESSING_RULES.get("leben_keywords", [])
    return any(kw.lower() in text_lower for kw in keywords)


def is_sach_keyword(text: str) -> bool:
    """Prueft ob der Text Sach-Schluesselwoerter enthaelt."""
    text_lower = text.lower()
    keywords = PROCESSING_RULES.get("sach_keywords", [])
    return any(kw.lower() in text_lower for kw in keywords)


def is_bipro_courtage_code(bipro_category: str) -> bool:
    """
    Prueft ob der BiPRO-Code eine Provisionsabrechnung ist.
    
    Args:
        bipro_category: BiPRO-Kategorie-Code (z.B. "300001000")
        
    Returns:
        True wenn Courtage-Code
    """
    if not bipro_category:
        return False
    courtage_codes = PROCESSING_RULES.get("bipro_courtage_codes", BIPRO_COURTAGE_CODES)
    return bipro_category in courtage_codes


def get_bipro_document_type(bipro_category: str) -> str:
    """
    Gibt den Dokumenttyp fuer einen BiPRO-Code zurueck.
    
    Args:
        bipro_category: BiPRO-Kategorie-Code (z.B. "140012000")
        
    Returns:
        Dokumenttyp (z.B. "mahnung") oder "unbekannt"
    """
    if not bipro_category:
        return "unbekannt"
    vu_codes = PROCESSING_RULES.get("bipro_vu_document_codes", BIPRO_VU_DOCUMENT_CODES)
    return vu_codes.get(bipro_category, "unbekannt")


def is_bipro_gdv_code(bipro_category: str) -> bool:
    """
    Prueft ob der BiPRO-Code eine GDV-Datei markiert.
    
    GDV-Dateien werden oft als .pdf geliefert, enthalten aber
    GDV-Bestandsdaten im Fixed-Width-Format.
    
    Args:
        bipro_category: BiPRO-Kategorie-Code (z.B. "999010010")
        
    Returns:
        True wenn GDV-Code (999er-Bereich)
    """
    if not bipro_category:
        return False
    
    # Explizite GDV-Codes
    gdv_codes = BIPRO_GDV_CODES
    if bipro_category in gdv_codes:
        return True
    
    # 999xxx Bereich ist generell GDV
    return bipro_category.startswith("999")
