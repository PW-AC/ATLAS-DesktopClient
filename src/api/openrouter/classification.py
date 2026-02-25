"""
KI-Klassifikations-Methoden fuer die OpenRouter-Pipeline.

Enthaelt OpenRouterClassificationMixin mit allen Klassifikations-,
Triage- und Entity-Extraktions-Methoden.
"""

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_VISION_MODEL = "openai/gpt-4o"
DEFAULT_EXTRACT_MODEL = "openai/gpt-4o-mini"
DEFAULT_TRIAGE_MODEL = "openai/gpt-4o-mini"

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


class OpenRouterClassificationMixin:
    """Mixin mit Klassifikations-Methoden fuer OpenRouterClient."""
    
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
    
    def extract_entities(self, text: str, 
                         model: str = DEFAULT_EXTRACT_MODEL) -> 'ExtractedDocumentData':
        """
        Extrahiert Entitaeten aus Text mittels Structured Output.
        
        Args:
            text: Zu analysierender Text
            model: LLM-Modell
            
        Returns:
            ExtractedDocumentData mit gefundenen Entitaeten
        """
        from .models import ExtractedDocumentData
        from .utils import _safe_json_loads
        
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
                    extract_model: str = DEFAULT_EXTRACT_MODEL) -> 'ExtractedDocumentData':
        """
        Vollstaendiger Workflow: PDF -> OCR -> Entity-Extraktion.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            vision_model: Modell fuer OCR
            extract_model: Modell fuer Entity-Extraktion
            
        Returns:
            ExtractedDocumentData mit allen gefundenen Informationen
        """
        from .models import ExtractedDocumentData
        
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
    
    def process_pdf_smart(self, pdf_path: str) -> Tuple['ExtractedDocumentData', str]:
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
        from .models import ExtractedDocumentData
        
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
    
    def classify_document(self, text: str, 
                          model: str = DEFAULT_EXTRACT_MODEL) -> 'DocumentClassification':
        """
        Klassifiziert ein Dokument direkt in eine Box.
        
        Args:
            text: Extrahierter Text aus dem Dokument
            model: LLM-Modell
            
        Returns:
            DocumentClassification mit Ziel-Box und Metadaten
        """
        from .models import DocumentClassification
        from .utils import _safe_json_loads
        
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
    
    def classify_pdf(self, pdf_path: str) -> 'DocumentClassification':
        """
        Klassifiziert ein PDF direkt.
        
        1. Text aus PDF extrahieren (direkt oder via OCR)
        2. Text an classify_document() uebergeben
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            
        Returns:
            DocumentClassification
        """
        from .models import DocumentClassification
        
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
        from .utils import _safe_json_loads
        
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
    
    def classify_document_smart(self, text: str) -> 'DocumentClassification':
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
        from .models import DocumentClassification
        
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
    
    def classify_pdf_smart(self, pdf_path: str) -> 'DocumentClassification':
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
        from .models import DocumentClassification
        
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
        from .utils import _safe_json_loads
        
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
        from .utils import _build_keyword_hints
        
        logger.info(f"Sparten-Klassifikation (minimal): {pdf_path}")
        
        # Text extrahieren (erste 2 Seiten)
        text = self._extract_relevant_text(pdf_path, for_triage=True)
        
        if not text.strip():
            # Stufe A: Lokale OCR via Tesseract (kostenlos, ~50-300ms)
            text = self.ocr_pdf_local(pdf_path, max_pages=2, dpi=200)
        
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
        keyword_hint = _build_keyword_hints(text)
        if keyword_hint:
            logger.info(f"Keyword-Konflikt erkannt: {keyword_hint.strip()}")
        
        # =====================================================
        # STUFE 1: GPT-4o-mini (schnell, guenstig)
        # =====================================================
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
                result_stage2["confidence"] = "medium"
                
                s1_usage = result.get('_usage', {})
                s2_usage = result_stage2.get('_usage', {})
                result_stage2['_usage'] = {
                    'prompt_tokens': (s1_usage.get('prompt_tokens') or 0) + (s2_usage.get('prompt_tokens') or 0),
                    'completion_tokens': (s1_usage.get('completion_tokens') or 0) + (s2_usage.get('completion_tokens') or 0),
                    'total_tokens': (s1_usage.get('total_tokens') or 0) + (s2_usage.get('total_tokens') or 0),
                }
                s1_cost = result.get('_server_cost_usd', 0) or 0
                s2_cost = result_stage2.get('_server_cost_usd', 0) or 0
                result_stage2['_server_cost_usd'] = s1_cost + s2_cost
                result_stage2['_provider'] = result_stage2.get('_provider') or result.get('_provider', 'unknown')
                
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
        from .utils import _safe_json_loads
        
        if custom_prompt:
            prompt = custom_prompt.replace('{text}', text)
        else:
            prompt = '''Klassifiziere dieses Versicherungsdokument in eine Sparte.

SPARTEN:
- courtage: Provisionsabrechnungen/Courtageabrechnungen vom VU an den MAKLER/VERMITTLER.
  Erkennungsmerkmale: Provisionsliste, Courtageabrechnung, Vermittlerabrechnung,
  Buchnote, Provisionskonto, Kontoauszug mit Provisions-/Courtagebetraegen,
  DI-Provision, Bestandsprovision, Abschlussprovision, Stornoreserve,
  Verguetungsdatenblatt, Verguetungsnachweis, Provisionsnachweis, Inkassoprovision,
  Saldo aus Provisionen, Courtagenote.
  Auch wenn "Kontoauszug" draufsteht: wenn Provisionen/Courtage aufgefuehrt werden = courtage!
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
- Unfallversicherung = IMMER sach! Auch wenn Todesfallsumme, Invaliditaet,
  Progressionsstaffel oder Beitragsinformation erwaehnt wird!
  Beispiel: "Zurich Unfallversicherung Beitragsinformation" = sach, NICHT kranken!
  Invaliditaet + Progression = typisch Unfall = sach. NIEMALS kranken!
- PrivatSchutzversicherung, Kombi-Schutz, Buendelpolice = sach (Haftpflicht+Unfall+Hausrat)
- NICHT leben: Todesfallsumme/Invaliditaet bei Unfallversicherung
- Schadenlisten / Schadenaufstellungen / Schadenstatistiken = IMMER sach
- Dokumente ueber Fahrzeuge / Fahrzeugerprobung = sach (KFZ-Versicherung)

VU-SPARTEN-KUERZEL (haeufig in Dokumenten):
- MKF, MFK = Motor-Kraftfahrt = sach
- RR, RS = Rechtsschutz = sach
- HV, PHV = Haftpflicht = sach
- HR = Hausrat = sach
- WG, WGB = Wohngebaeude = sach
- UV, UNF = Unfall = sach
- KFZ, KH = Kraftfahrt = sach
- LV, LEB = Leben = leben
- BU = Berufsunfaehigkeit = leben
- KV, PKV = Kranken = kranken

REGELN:
1. Courtage wenn Hauptzweck = Provisionsabrechnung/Vermittlerabrechnung/Buchnote/
   Provisionskonto fuer Makler. Auch Kontoauszuege mit Provisionsbetraegen!
2. Kuendigung/Mahnung/Zahlungserinnerung/Rueckstandsliste/Lastschriftproblem/
   Adressaenderung/Nachtrag/Beitragsrechnung
   -> IMMER nach SPARTE des zugrundeliegenden Versicherungsvertrags zuordnen!
   Beispiel: Kuendigung einer Wohngebaeudeversicherung = "sach", nicht "sonstige"
   Beispiel: Kuendigung einer Unfallversicherung = "sach", nicht "leben"!
   Beispiel: Rueckstandsliste fuer KFZ-Vertrag (MKF) = "sach", nicht "sonstige"!
   Beispiel: Zahlungserinnerung fuer Rechtsschutz = "sach", nicht "sonstige"!
3. Bei Zweifel zwischen Sach und Sonstige -> IMMER Sach
4. Bei Zweifel zwischen Sach und Leben -> Sach bevorzugen (ausser eindeutig Lebensversicherung/Rente/BU)
5. "sonstige" nur wenn wirklich KEINE Versicherungssparte erkennbar ist
6. Wenn ein Dokument Versicherungsnummern (VS-Nr, VN, VSNR, Policennummer) oder
   Mahnbetraege/Rueckstaende enthaelt, ist es ein Versicherungsdokument und
   gehoert in eine Sparte, NICHT in sonstige

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
        from .utils import _safe_json_loads
        
        if custom_prompt:
            prompt = custom_prompt.replace('{text}', text)
        else:
            prompt = '''Analysiere dieses Versicherungsdokument detailliert.

SPARTEN:
- courtage: Provisionsabrechnungen/Courtageabrechnungen fuer Makler.
  Erkennungsmerkmale: Provisionsliste, Courtageabrechnung, Vermittlerabrechnung,
  Buchnote, Provisionskonto, Kontoauszug mit Provisions-/Courtagebetraegen,
  DI-Provision, Bestandsprovision, Abschlussprovision, Stornoreserve,
  Verguetungsdatenblatt, Verguetungsnachweis, Provisionsnachweis, Inkassoprovision,
  Saldo aus Provisionen, Courtagenote.
  Auch wenn "Kontoauszug" draufsteht: wenn Provisionen/Courtage aufgefuehrt werden = courtage!
- sach: KFZ, Haftpflicht, PHV, Tierhalterhaftpflicht, Hausrat, Wohngebaeude, Unfall,
  Unfallversicherung, Rechtsschutz, Gewerbe, Betriebshaftpflicht, Glas, Reise,
  Gebaeudeversicherung, PrivatSchutzversicherung, Kombi-Schutz, Buendelversicherung,
  Schadenaufstellung, Schadenliste, Schadenstatistik, Schadenhistorie, Schadenquote,
  Fahrzeug, Fahrzeugerprobung
- leben: Lebensversicherung, Rente, BU, Riester, Ruerup, Pensionskasse, bAV, Sterbegeld
- kranken: PKV, Krankenzusatz, Zahnzusatz, Pflege, Krankentagegeld
- sonstige: Wenn wirklich KEINE Versicherungssparte erkennbar ist

WICHTIG: Unfallversicherung = IMMER sach! Auch bei Todesfallsumme, Invaliditaet,
Progressionsstaffel oder Beitragsinformation! Invaliditaet + Progression = Unfall = sach!
WICHTIG: Schadenlisten/Schadenaufstellungen = IMMER sach!
WICHTIG: Wenn Versicherungsnummern (VS-Nr, VN, VSNR, Policennummer) oder
Mahnbetraege/Rueckstaende enthalten -> Sparte zuordnen, NICHT sonstige!

VU-SPARTEN-KUERZEL: MKF/MFK = KFZ = sach, RR/RS = Rechtsschutz = sach,
HV/PHV = Haftpflicht = sach, HR = Hausrat = sach, WG/WGB = Wohngebaeude = sach,
UV/UNF = Unfall = sach, LV/LEB = Leben = leben, BU = Berufsunfaehigkeit = leben,
KV/PKV = Kranken = kranken

REGELN:
1. Courtage wenn Hauptzweck = Provisionsabrechnung/Vermittlerabrechnung/Buchnote/
   Provisionskonto. Auch Kontoauszuege mit Provisionsbetraegen!
2. Kuendigung/Mahnung/Zahlungserinnerung/Rueckstandsliste/Beitragsrechnung
   -> nach Sparte des zugrundeliegenden Vertrags zuordnen!
   Beispiel: Rueckstandsliste fuer KFZ (MKF) = "sach", nicht "sonstige"!
   Beispiel: Zahlungserinnerung fuer Rechtsschutz = "sach", nicht "sonstige"!
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
