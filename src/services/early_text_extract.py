"""
Fruehe Text-Extraktion fuer Upload-Duplikat-Erkennung.

Wird direkt nach dem Upload aufgerufen, BEVOR die KI-Verarbeitung laeuft.
Extrahiert den Volltext der Datei und speichert ihn in document_ai_data.
Dadurch werden Inhaltsduplikate sofort in der Eingangsbox erkannt.

Die spaetere KI-Verarbeitung ueberschreibt den Eintrag per Upsert
und ergaenzt die KI-Felder (ai_full_response, ai_model, etc.).
"""

import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def extract_and_save_text(
    docs_api,
    doc_id: int,
    local_file_path: str,
    filename: Optional[str] = None,
) -> Optional[dict]:
    """
    Extrahiert Text aus einer lokalen Datei und speichert ihn via API.
    
    Wird nach dem Upload aufgerufen, wenn die Datei noch lokal verfuegbar ist.
    Gibt die API-Response zurueck (inkl. content_duplicate_of_id wenn Duplikat).
    
    Args:
        docs_api: DocumentsAPI-Instanz (thread-safe: pro Thread eigene Instanz)
        doc_id: ID des hochgeladenen Dokuments
        local_file_path: Pfad zur lokalen Datei (muss noch existieren)
        filename: Dateiname (fuer Logging, optional)
        
    Returns:
        API-Response-Dict oder None bei Fehler. Enthaelt ggf.:
        - content_duplicate_of_id: ID des Originals
        - content_duplicate_of_filename: Name des Originals
    """
    if not os.path.exists(local_file_path):
        return None
    
    display_name = filename or os.path.basename(local_file_path)
    
    try:
        # Text extrahieren
        extracted_text, pages_with_text = _extract_text(local_file_path)
        
        if not extracted_text or not extracted_text.strip():
            # Kein Text extrahierbar -- trotzdem speichern mit method=none
            data = {
                'extracted_text': None,
                'extracted_text_sha256': None,
                'extraction_method': 'none',
                'extracted_page_count': 0,
                'text_char_count': None,
            }
        else:
            text_sha256 = hashlib.sha256(
                extracted_text.encode('utf-8')
            ).hexdigest()
            data = {
                'extracted_text': extracted_text,
                'extracted_text_sha256': text_sha256,
                'extraction_method': 'text',
                'extracted_page_count': pages_with_text,
                'text_char_count': len(extracted_text),
            }
        
        # API-Call (Upsert -- spaetere KI-Verarbeitung ueberschreibt)
        result = docs_api.save_ai_data(doc_id, data)
        
        if result:
            dup_id = result.get('content_duplicate_of_id')
            if dup_id:
                dup_name = result.get('content_duplicate_of_filename', '?')
                logger.info(
                    f"Fruehe Duplikat-Erkennung: {display_name} (ID {doc_id}) "
                    f"ist inhaltlich identisch mit {dup_name} (ID {dup_id})"
                )
        
        return result
        
    except Exception as e:
        # Fehler hier duerfen den Upload NICHT abbrechen
        logger.debug(f"Fruehe Text-Extraktion fehlgeschlagen fuer {display_name}: {e}")
        return None


def _extract_text(file_path: str) -> tuple:
    """
    Extrahiert Text aus einer Datei.
    
    - PDF: PyMuPDF (alle Seiten)
    - Text-Dateien (XML, GDV, CSV, etc.): Direkt lesen
    - Sonstige: Leerer String
    
    Returns:
        (extracted_text: str, pages_with_text: int)
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        return _extract_pdf_text(file_path)
    elif ext in ('.xml', '.gdv', '.txt', '.csv', '.tsv', '.dat', '.vwb'):
        return _extract_plain_text(file_path)
    else:
        return ("", 0)


def _extract_pdf_text(pdf_path: str) -> tuple:
    """PDF-Text mit PyMuPDF extrahieren."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ("", 0)
    
    extracted_text = ""
    pages_with_text = 0
    
    try:
        pdf_doc = fitz.open(pdf_path)
        for page in pdf_doc:
            page_text = page.get_text("text")
            if page_text and page_text.strip():
                extracted_text += page_text + "\n"
                pages_with_text += 1
        pdf_doc.close()
    except Exception as e:
        logger.debug(f"PDF-Text-Extraktion fehlgeschlagen: {e}")
    
    return (extracted_text, pages_with_text)


def _extract_plain_text(file_path: str) -> tuple:
    """Textdateien direkt lesen (Multi-Encoding)."""
    encodings = ['utf-8', 'cp1252', 'latin-1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                text = f.read()
            return (text, 1)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return ("", 0)
