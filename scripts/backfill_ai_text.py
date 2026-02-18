"""
Backfill-Script: Volltext fuer bestehende Dokumente extrahieren.

Einmalig ausfuehren, um fuer alle bestehenden Dokumente den extrahierten
PDF-Text in die document_ai_data Tabelle zu schreiben.

Nur Text-Extraktion -- kein KI-Re-Run. KI-Felder bleiben NULL fuer
Altdokumente.

Aufruf:
    cd "X:\\projekte\\5510_GDV Tool V1"
    python scripts/backfill_ai_text.py

Optionen:
    --dry-run       Nur zaehlen, nichts schreiben
    --skip-non-pdf  Nicht-PDF-Dateien ueberspringen (Standard: auch Text-Dateien verarbeiten)
    --limit N       Nur N Dokumente verarbeiten (fuer Tests)
    --delay SECS    Wartezeit zwischen API-Calls in Sekunden (Standard: 0.3)
"""

import sys
import os
import time
import hashlib
import tempfile
import argparse
import logging

# Projekt-Root zum Path hinzufuegen
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.api.client import APIClient, APIConfig, APIError
from src.api.auth import AuthAPI
from src.api.documents import DocumentsAPI, Document

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("backfill")


def extract_pdf_text(pdf_path: str) -> tuple:
    """
    Extrahiert Volltext ueber ALLE Seiten einer PDF mit PyMuPDF.
    
    Returns:
        Tuple (extracted_text: str, pages_with_text: int, total_pages: int)
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF nicht installiert! pip install PyMuPDF")
        return ("", 0, 0)
    
    extracted_text = ""
    pages_with_text = 0
    total_pages = 0
    
    try:
        pdf_doc = fitz.open(pdf_path)
        total_pages = len(pdf_doc)
        for page in pdf_doc:
            page_text = page.get_text("text")
            if page_text and page_text.strip():
                extracted_text += page_text + "\n"
                pages_with_text += 1
        pdf_doc.close()
    except Exception as e:
        logger.warning(f"PDF-Extraktion fehlgeschlagen: {e}")
    
    return (extracted_text, pages_with_text, total_pages)


def extract_text_file(file_path: str) -> tuple:
    """
    Liest Textdateien (GDV, XML, CSV, etc.) als Klartext.
    
    Returns:
        Tuple (extracted_text: str, 1, 1)
    """
    encodings = ['utf-8', 'cp1252', 'latin-1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                text = f.read()
            return (text, 1, 1)
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    logger.warning(f"Konnte Textdatei nicht lesen: {file_path}")
    return ("", 0, 1)


def is_pdf(filename: str) -> bool:
    """Prueft ob Datei eine PDF ist."""
    return filename.lower().endswith('.pdf')


def is_text_file(filename: str) -> bool:
    """Prueft ob Datei eine Textdatei ist (XML, GDV, CSV, etc.)."""
    text_extensions = {'.xml', '.gdv', '.txt', '.csv', '.tsv', '.dat', '.vwb'}
    _, ext = os.path.splitext(filename.lower())
    return ext in text_extensions


def login_interactive(client: APIClient) -> bool:
    """Interaktiver Login mit Benutzername/Passwort."""
    auth = AuthAPI(client)
    
    # Versuche Auto-Login
    auto_state = auth.try_auto_login()
    if auto_state and auto_state.is_authenticated:
        logger.info(f"Auto-Login erfolgreich: {auto_state.user.username}")
        return True
    
    # Manueller Login
    print("\n--- ACENCIA ATLAS Login ---")
    username = input("Benutzername: ").strip()
    password = input("Passwort: ").strip()
    
    if not username or not password:
        logger.error("Benutzername und Passwort erforderlich")
        return False
    
    state = auth.login(username, password)
    if state.is_authenticated:
        logger.info(f"Angemeldet als: {state.user.username}")
        return True
    
    logger.error("Login fehlgeschlagen")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Backfill: Volltext fuer bestehende Dokumente extrahieren"
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Nur zaehlen, nichts schreiben')
    parser.add_argument('--skip-non-pdf', action='store_true',
                        help='Nicht-PDF-Dateien ueberspringen')
    parser.add_argument('--limit', type=int, default=0,
                        help='Nur N Dokumente verarbeiten')
    parser.add_argument('--delay', type=float, default=0.3,
                        help='Wartezeit zwischen API-Calls (Sekunden)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("  ACENCIA ATLAS - Backfill: Volltext-Extraktion")
    print("  Nur Text -- kein KI-Re-Run")
    if args.dry_run:
        print("  *** DRY RUN - keine Aenderungen ***")
    print("=" * 60)
    
    # API-Client + Login
    client = APIClient(APIConfig())
    if not login_interactive(client):
        sys.exit(1)
    
    docs_api = DocumentsAPI(client)
    
    # Alle Dokumente laden (inkl. archivierte)
    logger.info("Lade Dokumentenliste vom Server...")
    all_docs = docs_api.list_documents()
    archived_docs = docs_api.list_documents(is_archived=True)
    
    # Zusammenfuegen und deduplizieren
    doc_map = {}
    for doc in all_docs + archived_docs:
        doc_map[doc.id] = doc
    all_docs_unique = sorted(doc_map.values(), key=lambda d: d.id)
    
    logger.info(f"Gesamt: {len(all_docs_unique)} Dokumente gefunden")
    
    # Filtern: Welche Dateitypen?
    processable = []
    skipped_type = 0
    for doc in all_docs_unique:
        if is_pdf(doc.filename):
            processable.append(doc)
        elif not args.skip_non_pdf and is_text_file(doc.filename):
            processable.append(doc)
        else:
            skipped_type += 1
    
    logger.info(f"Verarbeitbar: {len(processable)} Dokumente ({skipped_type} nach Dateityp uebersprungen)")
    
    if args.limit > 0:
        processable = processable[:args.limit]
        logger.info(f"Limit: Nur {len(processable)} Dokumente verarbeiten")
    
    if args.dry_run:
        pdf_count = sum(1 for d in processable if is_pdf(d.filename))
        text_count = len(processable) - pdf_count
        print(f"\nDry Run Zusammenfassung:")
        print(f"  PDFs:        {pdf_count}")
        print(f"  Textdateien: {text_count}")
        print(f"  Uebersprungen: {skipped_type}")
        print(f"  Gesamt:      {len(all_docs_unique)}")
        print(f"\nKeine Aenderungen vorgenommen.")
        return
    
    # Verarbeitung
    stats = {
        'success': 0,
        'skipped_exists': 0,
        'skipped_no_text': 0,
        'failed_download': 0,
        'failed_save': 0,
        'errors': 0,
    }
    
    total = len(processable)
    start_time = time.time()
    
    for idx, doc in enumerate(processable, 1):
        progress = f"[{idx}/{total}]"
        
        try:
            # 1. Pruefen ob bereits AI-Daten vorhanden
            existing = docs_api.get_ai_data(doc.id)
            if existing and existing.get('extracted_text'):
                logger.info(f"{progress} Uebersprungen (bereits vorhanden): {doc.filename}")
                stats['skipped_exists'] += 1
                time.sleep(args.delay / 2)  # Weniger Delay bei Skip
                continue
            
            # 2. Datei herunterladen
            with tempfile.TemporaryDirectory() as tmp_dir:
                file_path = docs_api.download(doc.id, tmp_dir, 
                                               filename_override=doc.filename)
                if not file_path:
                    logger.warning(f"{progress} Download fehlgeschlagen: {doc.filename}")
                    stats['failed_download'] += 1
                    time.sleep(args.delay)
                    continue
                
                # 3. Text extrahieren
                if is_pdf(doc.filename):
                    extracted_text, pages_with_text, total_pages = extract_pdf_text(file_path)
                    extraction_method = 'text'
                elif is_text_file(doc.filename):
                    extracted_text, pages_with_text, total_pages = extract_text_file(file_path)
                    extraction_method = 'text'
                else:
                    stats['skipped_no_text'] += 1
                    continue
            
            # 4. Leerer Text?
            if not extracted_text or not extracted_text.strip():
                logger.info(f"{progress} Kein Text extrahierbar: {doc.filename}")
                # Trotzdem speichern mit extraction_method='none'
                text_sha256 = None
                extraction_method = 'none'
                text_char_count = 0
                extracted_text_to_save = None
                pages_with_text = 0
            else:
                text_sha256 = hashlib.sha256(
                    extracted_text.encode('utf-8')
                ).hexdigest()
                text_char_count = len(extracted_text)
                extracted_text_to_save = extracted_text
            
            # 5. API-Call: Speichern
            data = {
                'extracted_text': extracted_text_to_save if extraction_method != 'none' else None,
                'extracted_text_sha256': text_sha256 if extraction_method != 'none' else None,
                'extraction_method': extraction_method,
                'extracted_page_count': pages_with_text,
                'text_char_count': text_char_count if extraction_method != 'none' else None,
                # KI-Felder bewusst NULL (kein Re-Run)
                'ai_full_response': None,
                'ai_prompt_text': None,
                'ai_model': None,
                'ai_prompt_version': None,
                'ai_stage': 'none',
                'ai_response_char_count': None,
                'prompt_tokens': None,
                'completion_tokens': None,
                'total_tokens': None,
            }
            
            success = docs_api.save_ai_data(doc.id, data)
            if success:
                chars = text_char_count if extraction_method != 'none' else 0
                logger.info(f"{progress} OK: {doc.filename} ({chars:,} Zeichen, {pages_with_text} Seiten)")
                stats['success'] += 1
            else:
                logger.warning(f"{progress} Speichern fehlgeschlagen: {doc.filename}")
                stats['failed_save'] += 1
            
        except Exception as e:
            logger.error(f"{progress} Fehler bei {doc.filename}: {e}")
            stats['errors'] += 1
        
        # Rate Limiting
        time.sleep(args.delay)
    
    # Zusammenfassung
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("  Backfill abgeschlossen")
    print("=" * 60)
    print(f"  Dauer:              {elapsed:.1f}s ({elapsed/60:.1f} Min)")
    print(f"  Erfolgreich:        {stats['success']}")
    print(f"  Bereits vorhanden:  {stats['skipped_exists']}")
    print(f"  Kein Text:          {stats['skipped_no_text']}")
    print(f"  Download-Fehler:    {stats['failed_download']}")
    print(f"  Speicher-Fehler:    {stats['failed_save']}")
    print(f"  Sonstige Fehler:    {stats['errors']}")
    print(f"  Gesamt verarbeitet: {total}")
    print("=" * 60)


if __name__ == '__main__':
    main()
