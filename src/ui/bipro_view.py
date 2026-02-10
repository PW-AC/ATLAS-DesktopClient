"""
ACENCIA ATLAS - BiPRO Datenabruf View

Ansicht für BiPRO-Verbindungen und Lieferungsabruf.

Design: ACENCIA Corporate Identity
"""

from typing import Optional, List
from datetime import datetime
import tempfile
import os
import base64
import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# PDF-Validierung
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QTextEdit, QProgressDialog, QFileDialog,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QCheckBox, QFrame, QProgressBar, QApplication
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QFont, QColor, QPainter

from api.client import APIClient
from api.vu_connections import VUConnectionsAPI, VUConnection, VUCredentials
from api.documents import DocumentsAPI
from bipro.categories import get_category_name, get_category_short_name, get_category_icon

# ACENCIA Design Tokens
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, WARNING, ERROR, INFO,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style
)


def mime_to_extension(mime_type: str) -> str:
    """
    Konvertiert MIME-Type zu Dateiendung.
    
    Args:
        mime_type: MIME-Type (z.B. 'application/pdf')
        
    Returns:
        Dateiendung mit Punkt (z.B. '.pdf')
    """
    if not mime_type:
        return '.pdf'  # Default bei BiPRO
    
    # MIME-Type normalisieren (nur Hauptteil, ohne Parameter)
    mime_type = mime_type.split(';')[0].strip().lower()
    
    # Mapping der gängigen MIME-Types
    mime_map = {
        'application/pdf': '.pdf',
        'image/pdf': '.pdf',
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/tiff': '.tiff',
        'image/tif': '.tif',
        'image/bmp': '.bmp',
        'text/plain': '.txt',
        'text/xml': '.xml',
        'application/xml': '.xml',
        'text/html': '.html',
        'application/msword': '.doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.ms-excel': '.xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/zip': '.zip',
        'application/x-zip-compressed': '.zip',
        'application/octet-stream': '.pdf',  # Fallback: Oft sind das PDFs bei BiPRO
    }
    
    return mime_map.get(mime_type, '.pdf')  # Default: .pdf (häufigster Fall bei BiPRO)


def format_date_german(date_str: str) -> str:
    """
    Konvertiert ISO-Datum (YYYY-MM-DD oder YYYY-MM-DDTHH:MM:SS) ins deutsche Format (DD.MM.YYYY).
    """
    if not date_str:
        return ""
    
    try:
        # Nur Datumsteil nehmen (vor T)
        date_part = date_str.split('T')[0] if 'T' in date_str else date_str
        
        # YYYY-MM-DD parsen
        parts = date_part.split('-')
        if len(parts) == 3:
            year, month, day = parts
            return f"{day}.{month}.{year}"
    except (ValueError, AttributeError, IndexError):
        # Ungueltiges Datumsformat - Originalwert zurueckgeben
        pass
    
    return date_str


def format_datetime_german(date_str: str) -> str:
    """
    Konvertiert ISO-Datetime ins deutsche Format (DD.MM.YYYY HH:MM).
    """
    if not date_str:
        return ""
    
    try:
        if 'T' in date_str:
            date_part, time_part = date_str.split('T')
            time_short = time_part[:5]  # HH:MM
            
            parts = date_part.split('-')
            if len(parts) == 3:
                year, month, day = parts
                return f"{day}.{month}.{year} {time_short}"
        else:
            return format_date_german(date_str)
    except (ValueError, AttributeError, IndexError):
        # Ungueltiges Datumsformat - Originalwert zurueckgeben
        pass
    
    return date_str


class FetchShipmentsWorker(QThread):
    """Worker zum Abrufen von Lieferungen."""
    finished = Signal(list)  # Liste von ShipmentInfo
    error = Signal(str)
    progress = Signal(str)
    
    def __init__(self, credentials: VUCredentials, vu_name: str, 
                 sts_url: str = "", transfer_url: str = "", consumer_id: str = ""):
        super().__init__()
        self.credentials = credentials
        self.vu_name = vu_name
        self.sts_url = sts_url
        self.transfer_url = transfer_url
        self.consumer_id = consumer_id
    
    def run(self):
        try:
            auth_info = "Zertifikat" if self.credentials.uses_certificate else "Username/Password"
            self.progress.emit(f"Verbinde mit {self.vu_name} ({auth_info})...")
            
            from bipro.transfer_service import TransferServiceClient, BiPROCredentials
            
            # BiPROCredentials mit STS-URL, Transfer-URL und Consumer-ID
            import logging
            logging.getLogger(__name__).info(f"Worker consumer_id: '{self.consumer_id}'")
            
            bipro_creds = BiPROCredentials(
                username=self.credentials.username,
                password=self.credentials.password,
                endpoint_url=self.transfer_url,  # Transfer-URL als Haupt-URL
                sts_endpoint_url=self.sts_url,   # STS-URL separat
                vu_name=self.vu_name,
                consumer_id=self.consumer_id or "",
                pfx_path=getattr(self.credentials, 'pfx_path', ''),
                pfx_password=getattr(self.credentials, 'pfx_password', ''),
                jks_path=getattr(self.credentials, 'jks_path', ''),
                jks_password=getattr(self.credentials, 'jks_password', ''),
                jks_alias=getattr(self.credentials, 'jks_alias', ''),
                jks_key_password=getattr(self.credentials, 'jks_key_password', '')
            )
            
            with TransferServiceClient(bipro_creds) as client:
                self.progress.emit("Rufe Lieferungen ab...")
                shipments = client.list_shipments(confirmed=True)
                self.finished.emit(shipments)
                
        except ImportError as e:
            self.error.emit(f"Fehlende Bibliothek: {e}")
        except Exception as e:
            self.error.emit(str(e))


class DownloadShipmentWorker(QThread):
    """Worker zum Herunterladen einer Lieferung."""
    finished = Signal(str, list, str)  # shipment_id, documents, raw_xml_path
    error = Signal(str)
    progress = Signal(str)
    
    def __init__(self, credentials: VUCredentials, vu_name: str, shipment_id: str, 
                 sts_url: str = "", transfer_url: str = "",
                 category: str = "", created_at: str = "", consumer_id: str = ""):
        super().__init__()
        self.credentials = credentials
        self.vu_name = vu_name
        self.shipment_id = shipment_id
        self.sts_url = sts_url
        self.transfer_url = transfer_url
        self.category = category
        self.created_at = created_at
        self.consumer_id = consumer_id
        self._temp_dir: Optional[str] = None  # Fuer Cleanup bei Fehler
    
    def _make_safe_filename(self, name: str) -> str:
        """Erstellt einen sicheren Dateinamen."""
        # Ungültige Zeichen entfernen
        safe = "".join(c if c.isalnum() or c in '._-' else '_' for c in name)
        return safe[:50]  # Maximale Länge
    
    def _get_date_for_filename(self) -> str:
        """Extrahiert Datum für Dateinamen (YYYY-MM-DD)."""
        if self.created_at:
            # Nur Datumsteil
            return self.created_at.split('T')[0] if 'T' in self.created_at else self.created_at
        return datetime.now().strftime('%Y-%m-%d')
    
    def run(self):
        try:
            self.progress.emit(f"Lade Lieferung {self.shipment_id}...")
            
            from bipro.transfer_service import TransferServiceClient, BiPROCredentials
            
            bipro_creds = BiPROCredentials(
                username=self.credentials.username,
                password=self.credentials.password,
                endpoint_url=self.transfer_url,
                sts_endpoint_url=self.sts_url,
                vu_name=self.vu_name,
                consumer_id=self.consumer_id,
                pfx_path=getattr(self.credentials, 'pfx_path', ''),
                pfx_password=getattr(self.credentials, 'pfx_password', ''),
                jks_path=getattr(self.credentials, 'jks_path', ''),
                jks_password=getattr(self.credentials, 'jks_password', ''),
                jks_alias=getattr(self.credentials, 'jks_alias', ''),
                jks_key_password=getattr(self.credentials, 'jks_key_password', '')
            )
            
            with TransferServiceClient(bipro_creds) as client:
                auth_info = "Zertifikat" if bipro_creds.uses_certificate else "STS-Token"
                self.progress.emit(f"Authentifiziere ({auth_info})...")
                content = client.get_shipment(self.shipment_id)
                
                # Dokumente in temporäre Dateien speichern
                saved_docs = []
                self._temp_dir = tempfile.mkdtemp(prefix='bipro_')
                
                # Datum und VU-Name für Dateinamen
                date_str = self._get_date_for_filename()
                vu_safe = self._make_safe_filename(self.vu_name)
                category_name = get_category_short_name(self.category)
                category_safe = self._make_safe_filename(category_name)
                
                # Raw XML mit besserem Namen speichern
                # Format: Lieferung_Roh_DATUM_VERSICHERER_ID.xml
                raw_filename = f"Lieferung_Roh_{date_str}_{vu_safe}_{self.shipment_id}.xml"
                raw_xml_path = os.path.join(self._temp_dir, raw_filename)
                with open(raw_xml_path, 'w', encoding='utf-8') as f:
                    f.write(content.raw_xml)
                
                self.progress.emit(f"Verarbeite {len(content.documents)} Dokument(e)...")
                
                for i, doc in enumerate(content.documents):
                    original_filename = doc.get('filename', f'doc_{i+1}.bin')
                    
                    # Dateiendung extrahieren - MIME-Type als Fallback
                    ext = os.path.splitext(original_filename)[1]
                    if not ext or ext.lower() in ('.bin', ''):
                        doc_mime = doc.get('mime_type', 'application/octet-stream')
                        ext = mime_to_extension(doc_mime)
                    
                    # Neuer Dateiname: Lieferung_Dok_DATUM_VERSICHERER_KATEGORIE_ID_NR.ext
                    new_filename = f"Lieferung_Dok_{date_str}_{vu_safe}_{category_safe}_{self.shipment_id}_{i+1}{ext}"
                    filepath = os.path.join(self._temp_dir, new_filename)
                    
                    try:
                        # Bytes direkt oder Base64 dekodieren
                        if 'content_bytes' in doc:
                            content_bytes = doc['content_bytes']
                        elif 'content_base64' in doc:
                            content_bytes = base64.b64decode(doc['content_base64'])
                        else:
                            self.progress.emit(f"  Kein Inhalt in {original_filename}")
                            continue
                        
                        with open(filepath, 'wb') as f:
                            f.write(content_bytes)
                        
                        saved_docs.append({
                            'filename': new_filename,
                            'original_filename': original_filename,
                            'filepath': filepath,
                            'size': len(content_bytes),
                            'mime_type': doc.get('mime_type', 'application/octet-stream')
                        })
                        self.progress.emit(f"  Gespeichert: {new_filename} ({len(content_bytes):,} Bytes)")
                    except Exception as e:
                        self.progress.emit(f"  Fehler bei {original_filename}: {e}")
                
                self.finished.emit(self.shipment_id, saved_docs, raw_xml_path)
                
        except Exception as e:
            import traceback
            # Cleanup bei Fehler: Temporaeres Verzeichnis loeschen
            self._cleanup_temp_dir()
            self.error.emit(f"{str(e)}\n\n{traceback.format_exc()}")
    
    def _cleanup_temp_dir(self):
        """Loescht das temporaere Verzeichnis wenn es existiert."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                import shutil
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                self._temp_dir = None
            except Exception:
                pass  # Best effort cleanup


class AcknowledgeShipmentWorker(QThread):
    """Worker zum Quittieren von Lieferungen."""
    finished = Signal(list, list)  # erfolgreiche IDs, fehlgeschlagene IDs
    progress = Signal(str)
    
    def __init__(self, credentials: VUCredentials, shipment_ids: list, 
                 sts_url: str = "", transfer_url: str = "", consumer_id: str = ""):
        super().__init__()
        self.credentials = credentials
        self.shipment_ids = shipment_ids
        self.sts_url = sts_url
        self.transfer_url = transfer_url
        self.consumer_id = consumer_id
    
    def run(self):
        try:
            from bipro.transfer_service import TransferServiceClient, BiPROCredentials
            
            bipro_creds = BiPROCredentials(
                username=self.credentials.username,
                password=self.credentials.password,
                endpoint_url=self.transfer_url,
                sts_endpoint_url=self.sts_url,
                consumer_id=self.consumer_id,
                pfx_path=getattr(self.credentials, 'pfx_path', ''),
                pfx_password=getattr(self.credentials, 'pfx_password', ''),
                jks_path=getattr(self.credentials, 'jks_path', ''),
                jks_password=getattr(self.credentials, 'jks_password', ''),
                jks_alias=getattr(self.credentials, 'jks_alias', ''),
                jks_key_password=getattr(self.credentials, 'jks_key_password', '')
            )
            
            successful = []
            failed = []
            
            with TransferServiceClient(bipro_creds) as client:
                for shipment_id in self.shipment_ids:
                    self.progress.emit(f"Quittiere Lieferung {shipment_id}...")
                    try:
                        if client.acknowledge_shipment(shipment_id):
                            successful.append(shipment_id)
                            self.progress.emit(f"  OK: {shipment_id}")
                        else:
                            failed.append(shipment_id)
                            self.progress.emit(f"  FEHLER: {shipment_id}")
                    except Exception as e:
                        failed.append(shipment_id)
                        self.progress.emit(f"  FEHLER bei {shipment_id}: {e}")
            
            self.finished.emit(successful, failed)
            
        except Exception as e:
            self.progress.emit(f"FEHLER: {e}")
            self.finished.emit([], self.shipment_ids)


# =============================================================================
# MAIL IMPORT WORKER - IMAP-Mails abrufen und Anhaenge importieren
# =============================================================================

class MailImportWorker(QThread):
    """Worker zum Abrufen von IMAP-Mails und Import der Anhaenge in die Eingangsbox.
    
    Ablauf:
      1. IMAP-Poll (Server-seitig: neue Mails abrufen, Anhaenge in Staging speichern)
      2. Pending Attachments vom Server holen
      3. Jeden Anhang herunterladen und durch Pipeline verarbeiten (PDF/ZIP/MSG)
      4. Verarbeitete Dateien parallel in die Eingangsbox hochladen
      5. Anhaenge als importiert markieren
    
    Verwendet ThreadPoolExecutor fuer parallele Downloads und Uploads (max 4 Worker).
    """
    progress = Signal(str)              # Status-Text fuer Log
    progress_count = Signal(int, int)   # (current, total) fuer Fortschrittsbalken
    phase_changed = Signal(str, int)    # (phase_title, total_items) - neuer Progress-Toast
    completed = Signal(dict)            # Ergebnis-Statistiken
    error = Signal(str)                 # Fehlermeldung
    
    MAX_WORKERS = 4

    def __init__(self, api_client, account_id: int):
        super().__init__()
        self._api_client = api_client
        self._account_id = account_id

    def _expand_attachment(self, file_path: str, temp_base: str):
        """Verarbeitet einen heruntergeladenen Anhang durch die Pipeline.
        
        Returns:
            Liste von (path, box_type) Tupeln. box_type=None -> Eingangsbox, 'roh' -> Roh-Archiv.
        """
        from services.msg_handler import is_msg_file, extract_msg_attachments
        from services.zip_handler import is_zip_file, extract_zip_contents
        from services.pdf_unlock import unlock_pdf_if_needed

        jobs = []
        errors = []

        if is_zip_file(file_path):
            td = tempfile.mkdtemp(prefix="atlas_mail_zip_", dir=temp_base)
            zr = extract_zip_contents(file_path, td, api_client=self._api_client)
            if zr.error:
                errors.append(zr.error)
                jobs.append((file_path, 'roh'))
            else:
                for ext in zr.extracted_paths:
                    if is_msg_file(ext):
                        md = tempfile.mkdtemp(prefix="atlas_mail_msg_", dir=td)
                        mr = extract_msg_attachments(ext, md)
                        if mr.error:
                            errors.append(mr.error)
                        else:
                            for att in mr.attachment_paths:
                                try:
                                    unlock_pdf_if_needed(att)
                                except Exception:
                                    pass
                                jobs.append((att, None))
                        jobs.append((ext, 'roh'))
                    else:
                        try:
                            unlock_pdf_if_needed(ext)
                        except Exception:
                            pass
                        jobs.append((ext, None))
                jobs.append((file_path, 'roh'))

        elif is_msg_file(file_path):
            td = tempfile.mkdtemp(prefix="atlas_mail_msg_", dir=temp_base)
            mr = extract_msg_attachments(file_path, td)
            if mr.error:
                errors.append(mr.error)
            else:
                for att in mr.attachment_paths:
                    if is_zip_file(att):
                        zd = tempfile.mkdtemp(prefix="atlas_mail_zip_", dir=td)
                        zr = extract_zip_contents(att, zd, api_client=self._api_client)
                        if zr.error:
                            errors.append(zr.error)
                        else:
                            for ext in zr.extracted_paths:
                                try:
                                    unlock_pdf_if_needed(ext)
                                except Exception:
                                    pass
                                jobs.append((ext, None))
                        jobs.append((att, 'roh'))
                    else:
                        try:
                            unlock_pdf_if_needed(att)
                        except Exception:
                            pass
                        jobs.append((att, None))
            jobs.append((file_path, 'roh'))

        else:
            try:
                unlock_pdf_if_needed(file_path)
            except Exception:
                pass
            jobs.append((file_path, None))

        return jobs, errors

    def _upload_single(self, file_path: str, box_type: str = None):
        """Thread-safe Upload einer einzelnen Datei mit per-Thread API-Client.
        
        Returns:
            (filename, success, doc_or_error_str)
        """
        from pathlib import Path
        name = Path(file_path).name
        try:
            tid = threading.get_ident()
            if tid not in self._thread_apis:
                from api.client import APIClient
                from api.documents import DocumentsAPI
                client = APIClient(self._api_client.config)
                client.set_token(self._api_client._token)
                self._thread_apis[tid] = DocumentsAPI(client)
            docs_api = self._thread_apis[tid]

            if box_type:
                doc = docs_api.upload(file_path, 'imap_import', box_type=box_type)
            else:
                doc = docs_api.upload(file_path, 'imap_import')
            if doc:
                return (name, True, doc)
            else:
                return (name, False, "Upload fehlgeschlagen")
        except Exception as e:
            return (name, False, str(e))

    def _process_attachment(self, att: dict, temp_base: str, email_api):
        """Verarbeitet einen einzelnen Anhang: Download -> Pipeline -> Upload -> Markieren.
        
        Returns:
            (success: bool, errors: list)
        """
        from pathlib import Path

        att_id = att.get('id')
        att_filename = att.get('original_filename', att.get('filename', f'attachment_{att_id}'))
        errors = []

        try:
            # Download in Temp-Verzeichnis
            safe_name = att_filename.replace('/', '_').replace('\\', '_')
            local_path = os.path.join(temp_base, f"{att_id}_{safe_name}")
            email_api.download_attachment(att_id, local_path)

            # Pipeline: ZIP/MSG/PDF Verarbeitung
            upload_jobs, expand_errors = self._expand_attachment(local_path, temp_base)
            if expand_errors:
                errors.extend(expand_errors)

            # Parallele Uploads via ThreadPoolExecutor
            first_doc_id = None
            upload_success = False
            
            num_workers = min(self.MAX_WORKERS, max(1, len(upload_jobs)))
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {
                    executor.submit(self._upload_single, fp, bt): (fp, bt)
                    for fp, bt in upload_jobs
                }
                for future in as_completed(futures):
                    fp, bt = futures[future]
                    try:
                        name, success, result = future.result()
                        if success and first_doc_id is None and bt != 'roh':
                            first_doc_id = result.id if hasattr(result, 'id') else None
                            upload_success = True
                    except Exception as upload_err:
                        errors.append(f"Upload {Path(fp).name}: {upload_err}")

            # Anhang als importiert/fehlgeschlagen markieren
            if upload_success and first_doc_id:
                try:
                    email_api.mark_attachment_imported(att_id, first_doc_id)
                except Exception:
                    pass
                return (True, errors)
            elif upload_jobs:
                try:
                    email_api.mark_attachment_imported(att_id, 0)
                except Exception:
                    pass
                return (True, errors)
            else:
                try:
                    email_api.mark_attachment_failed(
                        att_id, "Keine Dateien zum Upload nach Verarbeitung"
                    )
                except Exception:
                    pass
                return (False, errors)

        except Exception as e:
            logger.error(f"Fehler bei Anhang {att_filename}: {e}")
            errors.append(f"{att_filename}: {e}")
            try:
                email_api.mark_attachment_failed(att_id, str(e))
            except Exception:
                pass
            return (False, errors)

    def run(self):
        import shutil
        from api.smartscan import EmailAccountsAPI

        email_api = EmailAccountsAPI(self._api_client)
        self._thread_apis = {}  # thread_id -> DocumentsAPI

        stats = {
            'new_mails': 0,
            'new_attachments': 0,
            'total_pending': 0,
            'imported': 0,
            'failed': 0,
            'errors': []
        }
        temp_base = tempfile.mkdtemp(prefix="atlas_mail_import_")

        try:
            # ==============================================
            # PHASE 1: IMAP-Poll (Server-seitig)
            # ==============================================
            from i18n.de import BIPRO_MAIL_FETCH_PHASE_POLL, BIPRO_MAIL_FETCH_PHASE_IMPORT
            self.phase_changed.emit(BIPRO_MAIL_FETCH_PHASE_POLL, 0)
            self.progress.emit("Rufe E-Mail-Postfach ab...")
            try:
                poll_result = email_api.poll_inbox(self._account_id)
                stats['new_mails'] = poll_result.get('new_mails', 0)
                stats['new_attachments'] = poll_result.get('new_attachments', 0)
                poll_errors = poll_result.get('errors', [])
                if poll_errors:
                    stats['errors'].extend(poll_errors)

                if stats['new_mails'] > 0:
                    self.progress.emit(
                        f"{stats['new_mails']} neue Mail(s) mit "
                        f"{stats['new_attachments']} Anhang/Anhaenge gefunden"
                    )
                else:
                    self.progress.emit("Keine neuen Mails im Postfach")
            except Exception as e:
                self.progress.emit(f"IMAP-Poll Fehler: {e}")
                stats['errors'].append(str(e))

            # ==============================================
            # PHASE 2: Anhaenge herunterladen + verarbeiten + hochladen
            # ==============================================
            self.progress.emit("Lade unverarbeitete Anhaenge...")
            try:
                pending = email_api.get_pending_attachments()
            except Exception as e:
                self.error.emit(f"Fehler beim Laden der Anhaenge: {e}")
                return

            stats['total_pending'] = len(pending)
            if not pending:
                self.progress.emit("Keine unverarbeiteten Anhaenge vorhanden")
                self.completed.emit(stats)
                return

            total = len(pending)
            # Phase 2 Toast starten
            self.phase_changed.emit(BIPRO_MAIL_FETCH_PHASE_IMPORT, total)
            self.progress.emit(f"{total} Anhang/Anhaenge werden verarbeitet...")
            self.progress_count.emit(0, total)

            # --- Download, Pipeline, Upload, Markieren ---
            for idx, att in enumerate(pending, 1):
                att_filename = att.get('original_filename', att.get('filename', f'attachment_{att.get("id")}'))
                self.progress.emit(f"Verarbeite {idx}/{total}: {att_filename}")
                self.progress_count.emit(idx, total)

                success, att_errors = self._process_attachment(att, temp_base, email_api)
                if att_errors:
                    stats['errors'].extend(att_errors)
                if success:
                    stats['imported'] += 1
                else:
                    stats['failed'] += 1

            self.progress.emit("Mail-Import abgeschlossen")
            self.progress_count.emit(total, total)
            self.completed.emit(stats)

        except Exception as e:
            logger.error(f"MailImportWorker Fehler: {e}")
            self.error.emit(str(e))
        finally:
            # Temp-Verzeichnis aufraeumen
            try:
                shutil.rmtree(temp_base, ignore_errors=True)
            except Exception:
                pass
            self._thread_apis = {}


# =============================================================================
# PARALLEL DOWNLOAD MANAGER - Parallele BiPRO-Downloads
# =============================================================================

from bipro.transfer_service import SharedTokenManager, BiPROCredentials
from bipro.rate_limiter import AdaptiveRateLimiter


class ParallelDownloadManager(QThread):
    """
    Manager für parallele BiPRO-Downloads mit Token-Sharing und Rate Limiting.
    
    Features:
    - Parallele Downloads mit konfigurierbarer Worker-Anzahl (Standard: 5)
    - Thread-safe Token-Sharing (Token wird nur 1x geholt)
    - Adaptives Rate Limiting (HTTP 429/503 Erkennung)
    - Automatische Retries bei Fehlern (max. 3 Versuche)
    - Keine Dokumentenverluste durch Retry-Queue
    
    Signals:
    - progress_updated: (current, total, docs_count, failed_count, active_workers)
    - download_finished: (shipment_id, documents, raw_xml_path, category)
    - log_message: (message)
    - all_finished: (stats_dict)
    - error: (error_message)
    """
    
    # Signals für UI-Updates (thread-safe)
    progress_updated = Signal(int, int, int, int, int)  # current, total, docs, failed, active_workers
    download_finished = Signal(str, list, str, str)  # shipment_id, docs, xml_path, category
    log_message = Signal(str)
    all_finished = Signal(dict)  # stats
    error = Signal(str)
    
    # Konfiguration (kann über processing_rules.py überschrieben werden)
    DEFAULT_MAX_WORKERS = 10  # Erhöht von 5 auf 10 für bessere Performance
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_INITIAL_BACKOFF = 1.0
    DEFAULT_MAX_BACKOFF = 30.0
    DEFAULT_RECOVERY_THRESHOLD = 10
    
    def __init__(
        self,
        credentials: 'VUCredentials',
        vu_name: str,
        shipments: list,  # Liste von Dicts mit 'id', 'category', 'created_at'
        sts_url: str,
        transfer_url: str,
        consumer_id: str = "",
        max_workers: int = None,
        parent=None
    ):
        super().__init__(parent)
        
        self.credentials = credentials
        self.vu_name = vu_name
        self.shipments = shipments
        self.sts_url = sts_url
        self.transfer_url = transfer_url
        self.consumer_id = consumer_id
        
        # Worker-Pool Konfiguration - automatisch an Anzahl der Lieferungen anpassen
        self._configured_workers = max_workers or self.DEFAULT_MAX_WORKERS
        self.max_workers = min(self._configured_workers, len(shipments))
        
        # Interne Verwaltung
        self._download_queue: queue.Queue = queue.Queue()
        self._token_manager: Optional[SharedTokenManager] = None
        self._rate_limiter: Optional[AdaptiveRateLimiter] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        
        # Statistiken (thread-safe)
        self._stats_lock = threading.Lock()
        self._stats = {
            'total': len(shipments),
            'success': 0,
            'failed': 0,
            'docs': 0,
            'retries': 0,
            'failed_ids': []
        }
        self._processed_count = 0
        
        # Abbruch-Flag
        self._cancelled = False
        self._shutdown_event = threading.Event()
    
    def cancel(self):
        """Bricht den Download-Vorgang ab."""
        self._cancelled = True
        self._shutdown_event.set()
        self.log_message.emit("Download wird abgebrochen...")
    
    def run(self):
        """Hauptmethode - wird in separatem Thread ausgeführt."""
        try:
            # BiPRO-Credentials erstellen
            bipro_creds = BiPROCredentials(
                username=self.credentials.username,
                password=self.credentials.password,
                endpoint_url=self.transfer_url,
                sts_endpoint_url=self.sts_url,
                vu_name=self.vu_name,
                consumer_id=self.consumer_id,
                pfx_path=getattr(self.credentials, 'pfx_path', ''),
                pfx_password=getattr(self.credentials, 'pfx_password', ''),
                jks_path=getattr(self.credentials, 'jks_path', ''),
                jks_password=getattr(self.credentials, 'jks_password', ''),
                jks_alias=getattr(self.credentials, 'jks_alias', ''),
                jks_key_password=getattr(self.credentials, 'jks_key_password', '')
            )
            
            # Token-Manager initialisieren (1x für alle Worker)
            self.log_message.emit("Initialisiere Token-Manager...")
            self._token_manager = SharedTokenManager(bipro_creds)
            if not self._token_manager.initialize():
                self.error.emit("Konnte Token-Manager nicht initialisieren")
                return
            
            # Rate Limiter initialisieren
            self._rate_limiter = AdaptiveRateLimiter(
                max_workers=self.max_workers,
                min_workers=1,
                initial_backoff=self.DEFAULT_INITIAL_BACKOFF,
                max_backoff=self.DEFAULT_MAX_BACKOFF,
                max_retries=self.DEFAULT_MAX_RETRIES,
                recovery_threshold=self.DEFAULT_RECOVERY_THRESHOLD
            )
            
            # Queue mit Shipments befüllen
            for shipment in self.shipments:
                self._download_queue.put(shipment)
            
            # Log-Nachricht mit Erklärung wenn Worker-Anzahl reduziert wurde
            if self.max_workers < self._configured_workers:
                self.log_message.emit(
                    f"Starte parallelen Download: {len(self.shipments)} Lieferung(en), "
                    f"{self.max_workers} Worker (angepasst von {self._configured_workers})"
                )
            else:
                self.log_message.emit(
                    f"Starte parallelen Download: {len(self.shipments)} Lieferung(en), "
                    f"{self.max_workers} Worker"
                )
            
            # ThreadPoolExecutor starten
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                self._executor = executor
                futures = []
                
                # Worker-Tasks starten
                for i in range(self.max_workers):
                    if self._cancelled:
                        break
                    future = executor.submit(self._worker_loop, i)
                    futures.append(future)
                
                # Auf Abschluss warten
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Worker-Fehler: {e}")
            
            # Abschluss
            if self._cancelled:
                self.log_message.emit("Download abgebrochen")
            else:
                self.log_message.emit("Alle Downloads abgeschlossen")
            
            # Finale Statistiken
            with self._stats_lock:
                final_stats = self._stats.copy()
                # Failed IDs aus Rate Limiter holen
                if self._rate_limiter:
                    final_stats['failed_ids'] = list(self._rate_limiter.get_failed_shipments())
            
            self.all_finished.emit(final_stats)
            
        except Exception as e:
            import traceback
            error_msg = f"Paralleler Download fehlgeschlagen: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.error.emit(str(e))
        
        finally:
            # Aufräumen
            if self._token_manager:
                try:
                    self._token_manager.close()
                except Exception:
                    pass
    
    def _worker_loop(self, worker_id: int):
        """
        Worker-Loop: Holt Shipments aus Queue und lädt sie herunter.
        
        Args:
            worker_id: ID des Workers (für Logging)
        """
        while not self._cancelled and not self._shutdown_event.is_set():
            # Prüfen ob Worker aktiv sein darf (Rate Limiting)
            active_workers = self._rate_limiter.get_active_workers()
            if worker_id >= active_workers:
                # Dieser Worker ist deaktiviert (Rate Limit)
                time.sleep(0.5)
                continue
            
            # Backoff warten falls nötig
            self._rate_limiter.wait_if_needed()
            
            try:
                # Nächstes Item aus Queue (mit Timeout)
                shipment_info = self._download_queue.get(timeout=0.5)
            except queue.Empty:
                # Queue leer - Worker beenden
                break
            
            logger.info(f"Worker {worker_id}: Got shipment from queue: {shipment_info.keys()}")
            
            try:
                shipment_id = shipment_info['id']
                category = shipment_info.get('category', '')
                created_at = shipment_info.get('created_at', '')
                retry_count = shipment_info.get('_retry_count', 0)
                
                # Debug: Type prüfen
                logger.info(f"Worker {worker_id}: Shipment {shipment_id}, created_at type: {type(created_at)}, value: {repr(created_at)}")
            except Exception as e:
                logger.error(f"Worker {worker_id}: Fehler beim Extrahieren der Shipment-Daten: {e}")
                self._download_queue.task_done()
                continue
            
            try:
                # Download durchführen
                documents, raw_xml_path = self._download_shipment(
                    shipment_id, category, created_at
                )
                
                # Erfolg!
                self._rate_limiter.on_success(shipment_id)
                
                with self._stats_lock:
                    self._stats['success'] += 1
                    self._stats['docs'] += len(documents)
                    self._processed_count += 1
                    current = self._processed_count
                    total = self._stats['total']
                    docs = self._stats['docs']
                    failed = self._stats['failed']
                
                # UI-Update emittieren
                active = self._rate_limiter.get_active_workers()
                self.progress_updated.emit(current, total, docs, failed, active)
                self.download_finished.emit(shipment_id, documents, raw_xml_path, category)
                self.log_message.emit(f"  [OK] Lieferung {shipment_id}: {len(documents)} Dokument(e)")
                
            except Exception as e:
                error_str = str(e)
                status_code = self._extract_status_code(e)
                
                # Rate Limit prüfen
                if status_code and self._rate_limiter.is_rate_limit_status(status_code):
                    should_retry = self._rate_limiter.on_rate_limit(status_code, shipment_id)
                else:
                    should_retry = self._rate_limiter.on_error(shipment_id, error_str, status_code)
                
                if should_retry and retry_count < self.DEFAULT_MAX_RETRIES:
                    # Zurück in Queue für Retry
                    shipment_info['_retry_count'] = retry_count + 1
                    self._download_queue.put(shipment_info)
                    
                    with self._stats_lock:
                        self._stats['retries'] += 1
                    
                    self.log_message.emit(
                        f"  [RETRY] Lieferung {shipment_id}: {error_str[:80]} "
                        f"(Versuch {retry_count + 1}/{self.DEFAULT_MAX_RETRIES})"
                    )
                else:
                    # Endgültig fehlgeschlagen
                    with self._stats_lock:
                        self._stats['failed'] += 1
                        self._stats['failed_ids'].append(shipment_id)
                        self._processed_count += 1
                        current = self._processed_count
                        total = self._stats['total']
                        docs = self._stats['docs']
                        failed = self._stats['failed']
                    
                    active = self._rate_limiter.get_active_workers()
                    self.progress_updated.emit(current, total, docs, failed, active)
                    self.log_message.emit(f"  [FEHLER] Lieferung {shipment_id}: {error_str[:100]}")
            
            finally:
                self._download_queue.task_done()
    
    def _download_shipment(self, shipment_id, category, created_at):
        """
        Lädt eine einzelne Lieferung herunter.
        
        Args:
            shipment_id: ID der Lieferung
            category: BiPRO-Kategorie
            created_at: Erstellungsdatum
            
        Returns:
            Tuple (documents_list, raw_xml_path)
        """
        logger.info(f"_download_shipment START: {shipment_id}, created_at={repr(created_at)}")
        
        # Token holen (thread-safe)
        token = self._token_manager.get_valid_token()
        if not token and not self._token_manager.uses_certificate():
            raise Exception("Kein gültiges Token verfügbar")
        
        # SOAP-Header bauen (thread-safe)
        soap_header = self._token_manager.build_soap_header()
        
        # Consumer-ID XML
        consumer_id_xml = ""
        consumer_id = self._token_manager.get_consumer_id()
        if consumer_id:
            consumer_id_xml = f"<nac:ConsumerID>{consumer_id}</nac:ConsumerID>"
        
        # SOAP Request Body
        body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:tran="http://www.bipro.net/namespace/transfer"
                  xmlns:nac="http://www.bipro.net/namespace/nachrichten"
                  xmlns:bas="http://www.bipro.net/namespace/basis">
   {soap_header}
   <soapenv:Body>
      <tran:getShipment>
         <tran:Request>
            <nac:BiPROVersion>2.6.1.1.0</nac:BiPROVersion>
            {consumer_id_xml}
            <tran:ID>{shipment_id}</tran:ID>
         </tran:Request>
      </tran:getShipment>
   </soapenv:Body>
</soapenv:Envelope>'''
        
        # Headers
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': ''  # Leer für VEMA und Degenia
        }
        
        # Eigene Session für diesen Request (thread-safe)
        session = requests.Session()
        session.verify = True
        session.trust_env = False
        session.proxies = {'http': '', 'https': ''}
        
        # Zertifikat von Token-Manager übernehmen falls vorhanden
        if self._token_manager.uses_certificate():
            base_session = self._token_manager.get_session()
            if hasattr(base_session, 'cert') and base_session.cert:
                session.cert = base_session.cert
        
        try:
            response = session.post(
                self._token_manager.get_transfer_url(),
                data=body.encode('utf-8'),
                headers=headers,
                timeout=120
            )
            
            # Status-Code prüfen
            if response.status_code == 429:
                raise Exception(f"Rate Limit (HTTP 429)")
            elif response.status_code == 503:
                raise Exception(f"Service Unavailable (HTTP 503)")
            elif response.status_code >= 400:
                raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
            
            # Response parsen (MTOM oder XML)
            documents = []
            raw_content = response.content
            content_type = response.headers.get('Content-Type', '')
            is_mtom = 'multipart' in content_type.lower() or raw_content[:2] == b'--'
            
            if is_mtom:
                documents, metadata = self._parse_mtom_response(raw_content, content_type)
            else:
                documents, metadata = self._parse_xml_response(response.text)
            
            # Temporäres Verzeichnis erstellen
            temp_dir = tempfile.mkdtemp(prefix='bipro_parallel_')
            
            logger.info(f"_download_shipment: Vor created_at Verarbeitung, type={type(created_at)}, value={repr(created_at)}")
            
            # Datum für Dateinamen - sicherstellen dass created_at ein String ist
            created_at_str = str(created_at) if created_at else ''
            
            logger.info(f"_download_shipment: Nach str() Konversion, created_at_str={repr(created_at_str)}")
            
            date_str = created_at_str.split('T')[0] if created_at_str and 'T' in created_at_str else (
                created_at_str if created_at_str else datetime.now().strftime('%Y-%m-%d')
            )
            
            logger.info(f"_download_shipment: date_str={repr(date_str)}")
            vu_safe = self._make_safe_filename(self.vu_name)
            category_name = get_category_short_name(category)
            category_safe = self._make_safe_filename(category_name)
            
            # Raw XML speichern
            raw_filename = f"Lieferung_Roh_{date_str}_{vu_safe}_{shipment_id}.xml"
            raw_xml_path = os.path.join(temp_dir, raw_filename)
            
            # XML-Teil extrahieren
            if is_mtom:
                parts = self._split_multipart(raw_content, content_type)
                raw_xml = parts[0].decode('utf-8', errors='replace') if parts else response.text
            else:
                raw_xml = response.text
            
            with open(raw_xml_path, 'w', encoding='utf-8') as f:
                f.write(raw_xml)
            
            # Dokumente speichern
            saved_docs = []
            for i, doc in enumerate(documents):
                original_filename = doc.get('filename', f'doc_{i+1}.bin')
                ext = os.path.splitext(original_filename)[1]
                
                # Endung aus MIME-Type ableiten wenn keine sinnvolle Endung vorhanden
                if not ext or ext.lower() in ('.bin', ''):
                    mime_type = doc.get('mime_type', 'application/octet-stream')
                    ext = mime_to_extension(mime_type)
                
                new_filename = f"Lieferung_Dok_{date_str}_{vu_safe}_{category_safe}_{shipment_id}_{i+1}{ext}"
                filepath = os.path.join(temp_dir, new_filename)
                
                # Bytes holen
                if 'content_bytes' in doc:
                    content_bytes = doc['content_bytes']
                elif 'content_base64' in doc:
                    content_bytes = base64.b64decode(doc['content_base64'])
                else:
                    continue
                
                with open(filepath, 'wb') as f:
                    f.write(content_bytes)
                
                # PDF-Validierung fuer PDF-Dateien mit Reason-Codes
                is_valid = True
                validation_status = None
                if ext.lower() == '.pdf':
                    from src.config.processing_rules import PDFValidationStatus
                    is_valid, validation_status = self._validate_pdf(
                        filepath, 
                        expected_size=len(content_bytes)
                    )
                    if not is_valid:
                        logger.warning(
                            f"PDF-Problem erkannt: {new_filename} - "
                            f"Status: {validation_status.value if validation_status else 'UNKNOWN'}"
                        )
                
                # Cross-Check: BiPRO-Code 999xxx (GDV) aber Datei hat .pdf Endung
                # GDV-Dateien sind Fixed-Width-Text, keine PDFs
                category_str = str(category) if category else ''
                if category_str.startswith('999') and ext.lower() == '.pdf':
                    if not content_bytes[:4].startswith(b'%PDF'):
                        logger.warning(
                            f"BiPRO-Code {category_str} (GDV) aber Inhalt ist kein PDF "
                            f"(Magic-Bytes: {content_bytes[:8]!r}). "
                            f"Datei '{new_filename}' ist wahrscheinlich eine GDV-Textdatei."
                        )
                
                saved_docs.append({
                    'filename': new_filename,
                    'original_filename': original_filename,
                    'filepath': filepath,
                    'size': len(content_bytes),
                    'mime_type': doc.get('mime_type', 'application/octet-stream'),
                    'is_valid': is_valid,
                    'validation_status': validation_status.value if validation_status else None
                })
            
            return saved_docs, raw_xml_path
            
        finally:
            session.close()
    
    def _parse_mtom_response(self, raw_content: bytes, content_type: str) -> tuple:
        """
        Parst MTOM/XOP Multipart Response.
        
        Verbesserte Version mit korrekter Body-Extraktion um PDF-Korruption zu vermeiden.
        """
        import re
        
        documents = []
        metadata = {}
        
        # Boundary extrahieren
        boundary = self._extract_boundary(content_type)
        if not boundary:
            return documents, metadata
        
        parts = self._split_multipart(raw_content, content_type)
        
        for part in parts[1:]:  # Erster Part ist XML
            # Content-ID und Content-Type aus Part-Header extrahieren
            # Finde den Separator zwischen Header und Body
            header_end_crlf = part.find(b'\r\n\r\n')
            header_end_lf = part.find(b'\n\n')
            
            # Wähle den früheren (korrekten) Separator
            if header_end_crlf != -1 and (header_end_lf == -1 or header_end_crlf < header_end_lf):
                header_end = header_end_crlf
                separator_len = 4  # \r\n\r\n
            elif header_end_lf != -1:
                header_end = header_end_lf
                separator_len = 2  # \n\n
            else:
                continue
            
            header = part[:header_end].decode('utf-8', errors='replace')
            body = part[header_end + separator_len:]  # Korrekte Separator-Länge
            
            # Filename aus Content-Disposition extrahieren
            filename_match = re.search(r'name="([^"]+)"', header)
            if not filename_match:
                filename_match = re.search(r'Content-ID:\s*<([^>]+)>', header)
            
            filename = filename_match.group(1) if filename_match else f"doc_{len(documents) + 1}.bin"
            
            # Content-Type
            ct_match = re.search(r'Content-Type:\s*([^\r\n]+)', header, re.IGNORECASE)
            mime_type = ct_match.group(1).strip() if ct_match else 'application/octet-stream'
            
            # Trailing CRLF/LF konsistent strippen (Boundary-Artefakte)
            if body.endswith(b'\r\n'):
                body = body[:-2]
            elif body.endswith(b'\n'):
                body = body[:-1]
            
            # Nur binäre Inhalte (keine XML-Teile)
            # Prüfe Magic Bytes statt strip() zu verwenden
            is_xml = body[:5] == b'<?xml' or body[:100].lstrip()[:5] == b'<?xml'
            
            if body and len(body) > 100 and not is_xml:
                # Magic-Byte-Validierung: Content-Type vs. tatsaechlicher Inhalt
                if 'pdf' in mime_type.lower() and not body[:4].startswith(b'%PDF'):
                    actual_magic = body[:8] if len(body) >= 8 else body
                    logger.warning(
                        f"MTOM: Content-Type ist {mime_type} aber Magic-Bytes "
                        f"sind {actual_magic!r} (kein %PDF). "
                        f"Filename={filename}, Size={len(body)} Bytes"
                    )
                
                documents.append({
                    'filename': filename,
                    'content_bytes': body,
                    'mime_type': mime_type
                })
        
        return documents, metadata
    
    def _parse_xml_response(self, xml_text: str) -> tuple:
        """Parst Standard XML Response (Base64-encoded)."""
        import re
        
        documents = []
        metadata = {}
        
        # Base64-Inhalte extrahieren
        doc_matches = re.findall(
            r'<(?:\w+:)?Dokument[^>]*>.*?<(?:\w+:)?Inhalt>([^<]+)</(?:\w+:)?Inhalt>.*?</(?:\w+:)?Dokument>',
            xml_text, re.DOTALL
        )
        
        for i, content_b64 in enumerate(doc_matches):
            try:
                documents.append({
                    'filename': f'doc_{i + 1}.pdf',
                    'content_base64': content_b64.strip(),
                    'mime_type': 'application/pdf'
                })
            except Exception:
                pass
        
        return documents, metadata
    
    def _extract_boundary(self, content_type: str) -> Optional[bytes]:
        """Extrahiert Boundary aus Content-Type."""
        import re
        match = re.search(r'boundary="([^"]+)"', content_type)
        if not match:
            match = re.search(r'boundary=([^;\s]+)', content_type)
        if match:
            return match.group(1).encode('utf-8')
        return None
    
    def _split_multipart(self, content: bytes, content_type: str) -> list:
        """
        Splittet Multipart-Content in Parts.
        
        WICHTIG: Kein strip() auf den gesamten Part, da dies Binärdaten
        beschädigen kann (z.B. wenn ein PDF zufällig mit Whitespace-ähnlichen
        Bytes endet).
        """
        boundary = self._extract_boundary(content_type)
        if not boundary:
            return []
        
        delimiter = b'--' + boundary
        parts = content.split(delimiter)
        
        # Erste und letzte Parts sind leer/Terminator
        valid_parts = []
        for part in parts[1:]:
            # Nur führende CRLF/LF entfernen (nicht strip()!)
            # Der Part beginnt oft mit \r\n nach dem Boundary
            if part.startswith(b'\r\n'):
                part = part[2:]
            elif part.startswith(b'\n'):
                part = part[1:]
            
            # Prüfe ob es ein End-Marker ist (--) 
            # oder leerer Content
            if not part or part == b'--' or part.startswith(b'--'):
                continue
            
            # Trailing CRLF entfernen (vor dem nächsten Boundary)
            # Aber NUR CRLF/LF, nicht andere Bytes!
            if part.endswith(b'\r\n'):
                part = part[:-2]
            elif part.endswith(b'\n'):
                part = part[:-1]
            
            if part:
                valid_parts.append(part)
        
        return valid_parts
    
    def _validate_pdf(self, filepath: str, expected_size: int = None) -> tuple:
        """
        Validiert und repariert eine PDF-Datei mit PyMuPDF.
        
        Diese Funktion:
        1. Prueft ob Download vollstaendig (Content-Length vs Dateigroesse)
        2. Prueft auf Verschluesselung
        3. Prueft auf XFA-Formulare
        4. Versucht Seiten zu laden
        5. Bei Problemen: Versucht Reparatur mit PyMuPDF
        
        Args:
            filepath: Pfad zur PDF-Datei
            expected_size: Erwartete Dateigroesse aus Content-Length Header (optional)
            
        Returns:
            Tuple (is_valid: bool, validation_status: PDFValidationStatus)
            - is_valid: True wenn PDF gueltig (evtl. nach Reparatur)
            - validation_status: Reason-Code fuer den Zustand
        """
        from src.config.processing_rules import PDFValidationStatus
        
        if not FITZ_AVAILABLE:
            # Wenn PyMuPDF nicht verfuegbar, nehme an dass PDF OK ist
            return (True, PDFValidationStatus.OK)
        
        try:
            # 1. Pruefe ob Download vollstaendig (Content-Length Check)
            actual_size = os.path.getsize(filepath)
            if expected_size is not None and actual_size != expected_size:
                logger.warning(
                    f"PDF unvollstaendig: erwartet {expected_size} Bytes, "
                    f"tatsaechlich {actual_size} Bytes: {filepath}"
                )
                return (False, PDFValidationStatus.PDF_INCOMPLETE)
            
            # 2. Erste Pruefung: Sind die Magic Bytes korrekt?
            with open(filepath, 'rb') as f:
                header = f.read(8)
                if not header.startswith(b'%PDF'):
                    logger.warning(f"Keine PDF-Magic-Bytes: {filepath}")
                    # Versuche trotzdem mit PyMuPDF zu oeffnen (kann manchmal reparieren)
            
            # 3. Versuche PDF normal zu oeffnen
            doc = None
            try:
                doc = fitz.open(filepath)
                
                # 4. Pruefe auf Verschluesselung
                if doc.is_encrypted:
                    doc.close()
                    logger.warning(f"PDF ist verschluesselt: {filepath}")
                    return (False, PDFValidationStatus.PDF_ENCRYPTED)
                
                # 5. Pruefe auf XFA-Formulare (problematisch fuer KI)
                if hasattr(doc, 'xfa') and doc.xfa:
                    logger.warning(f"PDF enthaelt XFA-Formulare: {filepath}")
                    # XFA ist nicht blockierend, aber warnen
                    # Dokument kann trotzdem verarbeitet werden, aber KI hat evtl. Probleme
                
                # 6. Pruefe ob mindestens eine Seite vorhanden
                if doc.page_count < 1:
                    doc.close()
                    logger.warning(f"PDF hat 0 Seiten: {filepath}")
                    return (False, PDFValidationStatus.PDF_NO_PAGES)
                
                # 7. Versuche erste Seite zu laden (tiefere Validierung)
                try:
                    page = doc.load_page(0)
                    _ = page.get_text()  # Tiefere Validierung
                except Exception as page_error:
                    doc.close()
                    logger.warning(f"PDF-Seite nicht ladbar: {filepath} - {page_error}")
                    # Versuche Reparatur
                    return self._attempt_pdf_repair(filepath)
                
                # Pruefe ob XFA vorhanden (Return mit Warnung aber OK)
                has_xfa = hasattr(doc, 'xfa') and doc.xfa
                doc.close()
                
                if has_xfa:
                    return (True, PDFValidationStatus.PDF_XFA)
                return (True, PDFValidationStatus.OK)
                
            except Exception as e:
                if doc:
                    try:
                        doc.close()
                    except Exception:
                        pass
                logger.info(f"PDF-Oeffnung fehlgeschlagen, versuche Reparatur: {filepath} - {e}")
                return self._attempt_pdf_repair(filepath)
            
        except Exception as e:
            logger.debug(f"PDF-Validierung fehlgeschlagen: {filepath} - {e}")
            return (False, PDFValidationStatus.PDF_LOAD_ERROR)
    
    def _attempt_pdf_repair(self, filepath: str) -> tuple:
        """
        Versucht eine defekte PDF zu reparieren.
        
        Args:
            filepath: Pfad zur PDF-Datei
            
        Returns:
            Tuple (is_valid: bool, validation_status: PDFValidationStatus)
        """
        from src.config.processing_rules import PDFValidationStatus
        
        try:
            # PyMuPDF kann defekte PDFs oft reparieren beim Speichern
            doc = fitz.open(filepath)
            
            # Pruefe auf Verschluesselung auch bei Reparatur
            if doc.is_encrypted:
                doc.close()
                return (False, PDFValidationStatus.PDF_ENCRYPTED)
            
            if doc.page_count < 1:
                doc.close()
                return (False, PDFValidationStatus.PDF_NO_PAGES)
            
            # Speichere mit Reparatur-Optionen
            # garbage=4 = maximale Bereinigung
            # deflate=True = Komprimierung
            # clean=True = Bereinigung von Redundanzen
            repaired_path = filepath + '.repaired'
            doc.save(
                repaired_path,
                garbage=4,
                deflate=True,
                clean=True
            )
            doc.close()
            
            # Ersetze Original mit reparierter Version
            import shutil
            shutil.move(repaired_path, filepath)
            
            # Verifiziere reparierte Datei
            doc = fitz.open(filepath)
            if doc.page_count > 0:
                try:
                    page = doc.load_page(0)
                    _ = page.get_text()
                    doc.close()
                    logger.info(f"PDF erfolgreich repariert: {filepath}")
                    return (True, PDFValidationStatus.PDF_REPAIRED)
                except Exception:
                    doc.close()
                    return (False, PDFValidationStatus.PDF_CORRUPT)
            
            doc.close()
            return (False, PDFValidationStatus.PDF_CORRUPT)
            
        except Exception as repair_error:
            logger.warning(f"PDF-Reparatur fehlgeschlagen: {filepath} - {repair_error}")
            # Aufraeumen falls .repaired Datei existiert
            repaired_path = filepath + '.repaired'
            if os.path.exists(repaired_path):
                try:
                    os.remove(repaired_path)
                except OSError:
                    pass
            return (False, PDFValidationStatus.PDF_CORRUPT)
    
    def _make_safe_filename(self, name: str) -> str:
        """Erstellt sicheren Dateinamen."""
        safe = "".join(c if c.isalnum() or c in '._-' else '_' for c in name)
        return safe[:50]
    
    def _extract_status_code(self, exception: Exception) -> Optional[int]:
        """Extrahiert HTTP Status Code aus Exception."""
        import re
        error_str = str(exception)
        
        # "HTTP 429" oder "(HTTP 503)" Pattern
        match = re.search(r'HTTP\s*(\d{3})', error_str)
        if match:
            return int(match.group(1))
        
        # requests.HTTPError
        if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
            return exception.response.status_code
        
        return None


# =============================================================================
# PROGRESS OVERLAY - Einheitliche Fortschrittsanzeige
# =============================================================================

class BiPROProgressOverlay(QWidget):
    """
    Einheitliche Fortschrittsfläche für BiPRO-Abruf und KI-Verarbeitung.
    
    Zeigt:
    - Titel (statusabhängig)
    - Fortschrittsbalken (0-100%)
    - Status-Text mit Zahlen
    - Fazit nach Abschluss (kein Popup!)
    """
    
    # Signal wenn Overlay geschlossen werden soll (nach Fazit-Anzeige)
    close_requested = Signal()
    
    # Phasen-Konstanten
    PHASE_DOWNLOAD = "download"
    PHASE_AI = "ai"
    PHASE_COMPLETE = "complete"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setVisible(False)
        
        self._phase = self.PHASE_DOWNLOAD
        self._total = 0
        self._current = 0
        self._stats = {
            'download_success': 0,
            'download_failed': 0,
            'download_docs': 0,
            'download_retries': 0,
            'ai_processed': 0,
            'ai_classified': 0,
            'ai_manual': 0
        }
        
        # Parallele Download-Infos
        self._max_workers = 10  # Synchron mit ParallelDownloadManager
        self._active_workers = 10
        
        self._setup_ui()
        
        # Auto-Close Timer (nach Fazit)
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._on_auto_close)
    
    def _setup_ui(self):
        """UI aufbauen."""
        # Hauptlayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Zentrierter Container
        container = QFrame()
        container.setObjectName("progressContainer")
        container.setStyleSheet(f"""
            QFrame#progressContainer {{
                background-color: rgba(255, 255, 255, 0.98);
                border-radius: {RADIUS_MD};
                border: 2px solid {PRIMARY_500};
            }}
        """)
        container.setMinimumWidth(450)
        container.setMaximumWidth(550)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(32, 28, 32, 28)
        container_layout.setSpacing(16)
        
        # Titel
        self._title_label = QLabel("BiPRO-Dokumente werden abgerufen")
        self._title_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 18px;
            font-weight: 600;
            color: {PRIMARY_900};
        """)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self._title_label)
        
        # Untertitel (Anzahl verfügbar)
        self._subtitle_label = QLabel("")
        self._subtitle_label.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {TEXT_SECONDARY};
        """)
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self._subtitle_label)
        
        container_layout.addSpacing(8)
        
        # Fortschrittsbalken
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 6px;
                background-color: {BG_SECONDARY};
                height: 24px;
                text-align: center;
                font-family: {FONT_BODY};
                font-size: 13px;
                font-weight: 500;
            }}
            QProgressBar::chunk {{
                background-color: {PRIMARY_500};
                border-radius: 5px;
            }}
        """)
        container_layout.addWidget(self._progress_bar)
        
        # Status-Text (z.B. "30 von 60 Dokumenten geladen")
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {TEXT_PRIMARY};
            font-weight: 500;
        """)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self._status_label)
        
        # Worker-Status (für parallele Downloads)
        self._worker_label = QLabel("")
        self._worker_label.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {TEXT_SECONDARY};
        """)
        self._worker_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._worker_label.setVisible(False)
        container_layout.addWidget(self._worker_label)
        
        container_layout.addSpacing(8)
        
        # Fazit-Bereich (initial versteckt)
        self._summary_frame = QFrame()
        self._summary_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        summary_layout = QVBoxLayout(self._summary_frame)
        summary_layout.setSpacing(6)
        
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {TEXT_PRIMARY};
            line-height: 1.5;
        """)
        self._summary_label.setWordWrap(True)
        summary_layout.addWidget(self._summary_label)
        
        self._summary_frame.setVisible(False)
        container_layout.addWidget(self._summary_frame)
        
        # Fertig-Indikator (initial versteckt)
        self._done_label = QLabel("✓ Fertig")
        self._done_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14px;
            font-weight: 600;
            color: {SUCCESS};
        """)
        self._done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_label.setVisible(False)
        container_layout.addWidget(self._done_label)
        
        # Container zentrieren
        layout.addStretch()
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(container)
        h_layout.addStretch()
        layout.addLayout(h_layout)
        layout.addStretch()
    
    def paintEvent(self, event):
        """Zeichnet halbtransparenten Hintergrund."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        super().paintEvent(event)
    
    # =========================================================================
    # PHASE 1: Download
    # =========================================================================
    
    def start_download_phase(self, total_shipments: int, max_workers: int = 1, parallel: bool = False):
        """
        Startet Phase 1: Download.
        
        Args:
            total_shipments: Gesamtanzahl Lieferungen
            max_workers: Maximale Worker-Anzahl (für parallelen Modus)
            parallel: True wenn paralleler Download-Modus aktiv
        """
        self._phase = self.PHASE_DOWNLOAD
        self._total = total_shipments
        self._current = 0
        self._max_workers = max_workers
        self._active_workers = max_workers
        self._stats = {
            'download_success': 0,
            'download_failed': 0,
            'download_docs': 0,
            'download_retries': 0,
            'ai_processed': 0,
            'ai_classified': 0,
            'ai_manual': 0
        }
        
        self._title_label.setText("BiPRO-Dokumente werden abgerufen")
        
        if parallel:
            self._subtitle_label.setText(f"{total_shipments} Lieferung(en) verfügbar (parallel)")
            self._worker_label.setText(f"{max_workers}/{max_workers} Worker aktiv")
            self._worker_label.setVisible(True)
        else:
            self._subtitle_label.setText(f"{total_shipments} Lieferung(en) verfügbar")
            self._worker_label.setVisible(False)
        
        self._status_label.setText("Starte Download...")
        self._progress_bar.setValue(0)
        
        self._summary_frame.setVisible(False)
        self._done_label.setVisible(False)
        
        self.setGeometry(self.parent().rect() if self.parent() else self.rect())
        self.raise_()
        self.setVisible(True)
        QApplication.processEvents()
    
    def update_download_progress(self, current: int, docs_count: int = 0, success: bool = True):
        """Aktualisiert den Download-Fortschritt (für sequentiellen Modus)."""
        self._current = current
        
        if success:
            self._stats['download_success'] += 1
            self._stats['download_docs'] += docs_count
        else:
            self._stats['download_failed'] += 1
        
        # Prozent berechnen
        percent = int((current / self._total) * 100) if self._total > 0 else 0
        self._progress_bar.setValue(percent)
        
        # Status-Text
        self._status_label.setText(f"{current} von {self._total} Lieferung(en) geladen")
        QApplication.processEvents()
    
    def update_parallel_progress(self, current: int, total: int, docs_count: int, 
                                  failed_count: int, active_workers: int):
        """
        Aktualisiert den Fortschritt für parallelen Download-Modus.
        
        Thread-safe: Kann von Worker-Threads aufgerufen werden.
        
        Args:
            current: Anzahl verarbeiteter Lieferungen
            total: Gesamtanzahl Lieferungen
            docs_count: Gesamtanzahl heruntergeladener Dokumente
            failed_count: Anzahl fehlgeschlagener Lieferungen
            active_workers: Aktuell aktive Worker-Anzahl
        """
        self._current = current
        self._total = total
        self._active_workers = active_workers
        self._stats['download_success'] = current - failed_count
        self._stats['download_failed'] = failed_count
        self._stats['download_docs'] = docs_count
        
        # Prozent berechnen
        percent = int((current / total) * 100) if total > 0 else 0
        self._progress_bar.setValue(percent)
        
        # Status-Text
        self._status_label.setText(f"{current} von {total} Lieferung(en) geladen ({docs_count} Dokumente)")
        
        # Worker-Status aktualisieren
        if active_workers < self._max_workers:
            # Rate Limiting aktiv - gelbe Warnung
            self._worker_label.setText(
                f"{active_workers}/{self._max_workers} Worker aktiv (Rate Limit)"
            )
            self._worker_label.setStyleSheet(f"""
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                color: {WARNING};
                font-weight: 500;
            """)
        else:
            self._worker_label.setText(f"{active_workers}/{self._max_workers} Worker aktiv")
            self._worker_label.setStyleSheet(f"""
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                color: {TEXT_SECONDARY};
            """)
        
        QApplication.processEvents()
    
    # =========================================================================
    # PHASE 2: KI-Verarbeitung
    # =========================================================================
    
    def start_ai_phase(self, total_docs: int):
        """Startet Phase 2: KI-Verarbeitung."""
        self._phase = self.PHASE_AI
        self._total = total_docs
        self._current = 0
        
        self._title_label.setText("Dokumente werden analysiert")
        self._subtitle_label.setText(f"{total_docs} Dokument(e) zur Analyse")
        self._status_label.setText("KI-Analyse läuft...")
        self._progress_bar.setValue(0)
        QApplication.processEvents()
    
    def update_ai_progress(self, current: int, classified: bool = True):
        """Aktualisiert den KI-Fortschritt."""
        self._current = current
        self._stats['ai_processed'] += 1
        
        if classified:
            self._stats['ai_classified'] += 1
        else:
            self._stats['ai_manual'] += 1
        
        # Prozent berechnen
        percent = int((current / self._total) * 100) if self._total > 0 else 0
        self._progress_bar.setValue(percent)
        
        # Status-Text
        self._status_label.setText(f"KI analysiert Dokumente ({current} / {self._total})")
        QApplication.processEvents()
    
    # =========================================================================
    # PHASE 3: Abschluss
    # =========================================================================
    
    def show_completion(self, auto_close_seconds: int = 5):
        """
        Zeigt das Fazit an.
        
        Args:
            auto_close_seconds: Nach wie vielen Sekunden automatisch schließen (0 = nie)
        """
        self._phase = self.PHASE_COMPLETE
        
        self._title_label.setText("Verarbeitung abgeschlossen")
        self._subtitle_label.setText("")
        self._progress_bar.setValue(100)
        self._status_label.setText("")
        
        # Fazit zusammenstellen
        lines = []
        
        # Download-Statistiken
        if self._stats['download_success'] > 0 or self._stats['download_failed'] > 0:
            total_shipments = self._stats['download_success'] + self._stats['download_failed']
            lines.append(f"📥 {self._stats['download_success']} von {total_shipments} Lieferung(en) erfolgreich abgerufen")
            lines.append(f"📄 {self._stats['download_docs']} Dokument(e) ins Archiv übertragen")
            if self._stats['download_failed'] > 0:
                lines.append(f"⚠️ {self._stats['download_failed']} Lieferung(en) fehlgeschlagen")
        
        # KI-Statistiken (falls KI-Phase durchlaufen wurde)
        if self._stats['ai_processed'] > 0:
            lines.append("")  # Leerzeile
            lines.append(f"🤖 {self._stats['ai_classified']} Dokument(e) automatisch klassifiziert")
            if self._stats['ai_manual'] > 0:
                lines.append(f"👤 {self._stats['ai_manual']} Dokument(e) erfordern manuelle Prüfung")
        
        self._summary_label.setText("\n".join(lines))
        self._summary_frame.setVisible(True)
        self._done_label.setVisible(True)
        
        # Auto-Close starten
        if auto_close_seconds > 0:
            self._auto_close_timer.start(auto_close_seconds * 1000)
        
        QApplication.processEvents()
    
    def _on_auto_close(self):
        """Wird nach Auto-Close Timeout aufgerufen."""
        self.hide()
        self.close_requested.emit()
    
    def hide(self):
        """Versteckt das Overlay und stoppt Timer."""
        self._auto_close_timer.stop()
        super().hide()
    
    def mousePressEvent(self, event):
        """Klick auf Overlay schließt es (nur wenn fertig)."""
        if self._phase == self.PHASE_COMPLETE:
            self.hide()
            self.close_requested.emit()
        # Während Download/AI: Event konsumieren aber nicht schließen
        event.accept()


class AddConnectionDialog(QDialog):
    """Dialog zum Hinzufuegen einer VU-Verbindung."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Neue VU-Verbindung")
        self.setMinimumWidth(550)
        self._pfx_path = ""
        self._jks_path = ""
        self._selected_cert_id = ""  # ID des ausgewählten Zertifikats aus Einstellungen
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.vu_name_input = QLineEdit()
        self.vu_name_input.setPlaceholderText("z.B. Degenia, Gothaer, HDI...")
        form.addRow("VU Name:", self.vu_name_input)
        
        self.vu_number_input = QLineEdit()
        self.vu_number_input.setPlaceholderText("z.B. 12345 (optional)")
        form.addRow("VU Nummer:", self.vu_number_input)
        
        # STS-URL (BiPRO 410 - Authentifizierung)
        self.sts_url_input = QLineEdit()
        self.sts_url_input.setPlaceholderText("https://.../STS/UserPasswordLogin...")
        self.sts_url_input.setToolTip("BiPRO 410 Security Token Service URL")
        form.addRow("STS-URL:", self.sts_url_input)
        
        # Transfer-URL (BiPRO 430 - Dokumentenabruf)
        self.transfer_url_input = QLineEdit()
        self.transfer_url_input.setPlaceholderText("https://.../Transfer/Service...")
        self.transfer_url_input.setToolTip("BiPRO 430 Transfer Service URL (optional, wird abgeleitet)")
        form.addRow("Transfer-URL:", self.transfer_url_input)
        
        # Ableiten-Button
        derive_row = QHBoxLayout()
        derive_row.addStretch()
        self.derive_btn = QPushButton("URLs ableiten")
        self.derive_btn.setToolTip("Versucht die fehlende URL aus der vorhandenen abzuleiten")
        self.derive_btn.clicked.connect(self._derive_urls)
        derive_row.addWidget(self.derive_btn)
        form.addRow("", derive_row)
        
        # Consumer-ID (Applikationskennung)
        self.consumer_id_input = QLineEdit()
        self.consumer_id_input.setPlaceholderText("z.B. 046_11077 (optional, für VEMA etc.)")
        self.consumer_id_input.setToolTip("Applikationskennung / Consumer-ID - wird von einigen Versicherern wie VEMA verlangt")
        form.addRow("Consumer-ID:", self.consumer_id_input)
        
        # Legacy endpoint_input für Kompatibilität (versteckt)
        self.endpoint_input = QLineEdit()
        self.endpoint_input.setVisible(False)
        
        # Auth-Typ mit Zertifikat-Option
        self.auth_type_combo = QComboBox()
        self.auth_type_combo.addItem("STS-Token (Username/Password)", "sts")
        self.auth_type_combo.addItem("X.509 Zertifikat (easy Login)", "certificate")
        self.auth_type_combo.addItem("HTTP Basic Auth", "basic")
        self.auth_type_combo.currentIndexChanged.connect(self._on_auth_type_changed)
        form.addRow("Auth-Typ:", self.auth_type_combo)
        
        layout.addLayout(form)
        
        # === Username/Password Bereich ===
        self.credentials_group = QGroupBox("Zugangsdaten")
        cred_layout = QFormLayout(self.credentials_group)
        
        self.username_input = QLineEdit()
        cred_layout.addRow("Benutzername:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        cred_layout.addRow("Passwort:", self.password_input)
        
        layout.addWidget(self.credentials_group)
        
        # === Zertifikat Bereich ===
        self.certificate_group = QGroupBox("Zertifikat (easy Login)")
        cert_layout = QVBoxLayout(self.certificate_group)
        
        # Info-Text
        info_label = QLabel(
            "Mit einem easy Login Zertifikat koennen Sie auf 54+ Versicherer zugreifen.\n"
            "Unterstuetzte Formate: PFX/P12 (Windows) oder JKS (Java KeyStore)"
        )
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        cert_layout.addWidget(info_label)
        
        # Format-Auswahl
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Format:"))
        self.cert_format_combo = QComboBox()
        self.cert_format_combo.addItem("PFX / P12 (Windows)", "pfx")
        self.cert_format_combo.addItem("JKS (Java KeyStore)", "jks")
        self.cert_format_combo.currentIndexChanged.connect(self._on_cert_format_changed)
        format_row.addWidget(self.cert_format_combo)
        format_row.addStretch()
        cert_layout.addLayout(format_row)
        
        # === PFX-Bereich ===
        self.pfx_widget = QWidget()
        pfx_layout = QVBoxLayout(self.pfx_widget)
        pfx_layout.setContentsMargins(0, 0, 0, 0)
        
        # Quelle-Auswahl: Datei oder aus Einstellungen
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Quelle:"))
        self.cert_source_combo = QComboBox()
        self.cert_source_combo.addItem("Datei auswählen", "file")
        self.cert_source_combo.addItem("Aus Einstellungen", "settings")
        self.cert_source_combo.currentIndexChanged.connect(self._on_cert_source_changed)
        source_row.addWidget(self.cert_source_combo)
        source_row.addStretch()
        pfx_layout.addLayout(source_row)
        
        # Datei-Auswahl Widget
        self.pfx_file_widget = QWidget()
        pfx_file_layout = QVBoxLayout(self.pfx_file_widget)
        pfx_file_layout.setContentsMargins(0, 8, 0, 0)
        
        pfx_row = QHBoxLayout()
        self.pfx_path_label = QLabel("Keine Datei ausgewaehlt")
        self.pfx_path_label.setStyleSheet("color: #999;")
        pfx_row.addWidget(self.pfx_path_label, 1)
        
        self.pfx_browse_btn = QPushButton("PFX/P12 waehlen...")
        self.pfx_browse_btn.clicked.connect(self._browse_pfx)
        pfx_row.addWidget(self.pfx_browse_btn)
        pfx_file_layout.addLayout(pfx_row)
        
        pfx_pw_layout = QFormLayout()
        self.pfx_password_input = QLineEdit()
        self.pfx_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pfx_password_input.setPlaceholderText("Passwort fuer die PFX-Datei")
        pfx_pw_layout.addRow("Passwort:", self.pfx_password_input)
        pfx_file_layout.addLayout(pfx_pw_layout)
        
        pfx_layout.addWidget(self.pfx_file_widget)
        
        # Einstellungen-Auswahl Widget
        self.pfx_settings_widget = QWidget()
        pfx_settings_layout = QVBoxLayout(self.pfx_settings_widget)
        pfx_settings_layout.setContentsMargins(0, 8, 0, 0)
        
        self.cert_select_combo = QComboBox()
        self._refresh_cert_combo()
        pfx_settings_layout.addWidget(self.cert_select_combo)
        
        # Zertifikat-Info
        self.cert_info_label = QLabel("")
        self.cert_info_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        pfx_settings_layout.addWidget(self.cert_info_label)
        self.cert_select_combo.currentIndexChanged.connect(self._on_cert_selected)
        
        pfx_settings_layout.addWidget(QLabel("Passwort:"))
        self.cert_settings_password = QLineEdit()
        self.cert_settings_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.cert_settings_password.setPlaceholderText("Zertifikat-Passwort")
        pfx_settings_layout.addWidget(self.cert_settings_password)
        
        self.pfx_settings_widget.setVisible(False)
        pfx_layout.addWidget(self.pfx_settings_widget)
        
        cert_layout.addWidget(self.pfx_widget)
        
        # === JKS-Bereich ===
        self.jks_widget = QWidget()
        jks_layout = QVBoxLayout(self.jks_widget)
        jks_layout.setContentsMargins(0, 0, 0, 0)
        
        jks_row = QHBoxLayout()
        self.jks_path_label = QLabel("Keine Datei ausgewaehlt")
        self.jks_path_label.setStyleSheet("color: #999;")
        jks_row.addWidget(self.jks_path_label, 1)
        
        self.jks_browse_btn = QPushButton("JKS waehlen...")
        self.jks_browse_btn.clicked.connect(self._browse_jks)
        jks_row.addWidget(self.jks_browse_btn)
        jks_layout.addLayout(jks_row)
        
        jks_form = QFormLayout()
        self.jks_password_input = QLineEdit()
        self.jks_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.jks_password_input.setPlaceholderText("KeyStore-Passwort")
        jks_form.addRow("KeyStore-PW:", self.jks_password_input)
        
        self.jks_alias_input = QLineEdit()
        self.jks_alias_input.setPlaceholderText("(leer = erstes Zertifikat)")
        jks_form.addRow("Alias:", self.jks_alias_input)
        
        self.jks_key_password_input = QLineEdit()
        self.jks_key_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.jks_key_password_input.setPlaceholderText("(leer = KeyStore-PW)")
        jks_form.addRow("Key-PW:", self.jks_key_password_input)
        
        jks_layout.addLayout(jks_form)
        self.jks_widget.setVisible(False)
        cert_layout.addWidget(self.jks_widget)
        
        self.certificate_group.setVisible(False)
        layout.addWidget(self.certificate_group)
        
        # Bekannte Endpoints - Dropdown mit allen VUs (SmartAdmin)
        known_group = QGroupBox("Bekannte Versicherer (SmartAdmin)")
        known_layout = QVBoxLayout(known_group)
        
        # SmartAdmin-Flow Checkbox
        self.use_smartadmin_check = QCheckBox("SmartAdmin-Authentifizierung verwenden")
        self.use_smartadmin_check.setToolTip(
            "Aktiviert den SmartAdmin-Auth-Flow mit vordefinierten Endpunkten und Auth-Typen.\n"
            "Wenn deaktiviert, wird die bisherige Authentifizierung verwendet."
        )
        self.use_smartadmin_check.setChecked(True)  # Standard: SmartAdmin nutzen
        self.use_smartadmin_check.stateChanged.connect(self._on_smartadmin_changed)
        known_layout.addWidget(self.use_smartadmin_check)
        
        # Dropdown mit allen bekannten Endpunkten
        dropdown_row = QHBoxLayout()
        dropdown_row.addWidget(QLabel("Versicherer:"))
        
        self.known_endpoints_combo = QComboBox()
        self.known_endpoints_combo.setMinimumWidth(300)
        self._smartadmin_company_key = ""  # Speichert den SmartAdmin-Key
        self._populate_known_endpoints()
        dropdown_row.addWidget(self.known_endpoints_combo, 1)
        
        apply_btn = QPushButton("Übernehmen")
        apply_btn.clicked.connect(self._apply_known_endpoint)
        dropdown_row.addWidget(apply_btn)
        
        known_layout.addLayout(dropdown_row)
        
        # Info-Label für den ausgewählten Endpunkt
        self.endpoint_info_label = QLabel("")
        self.endpoint_info_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        self.endpoint_info_label.setWordWrap(True)
        known_layout.addWidget(self.endpoint_info_label)
        self.known_endpoints_combo.currentIndexChanged.connect(self._on_known_endpoint_changed)
        
        layout.addWidget(known_group)
        
        # Inline-Status-Label fuer Validierungsfehler (statt modaler Dialoge)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #dc2626; font-size: 12px; padding: 4px 8px;")
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _show_validation_error(self, message: str):
        """Zeigt eine Validierungsfehlermeldung inline an."""
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #dc2626; font-size: 12px; padding: 4px 8px;")
        self._status_label.setVisible(True)
    
    def _show_validation_info(self, message: str):
        """Zeigt einen Validierungshinweis inline an."""
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #1e40af; font-size: 12px; padding: 4px 8px;")
        self._status_label.setVisible(True)
    
    def _clear_status(self):
        """Loescht die Status-Anzeige."""
        self._status_label.setText("")
        self._status_label.setVisible(False)
    
    def _on_auth_type_changed(self, index):
        """Zeigt/versteckt Felder je nach Auth-Typ."""
        self._clear_status()
        auth_type = self.auth_type_combo.currentData()
        is_certificate = (auth_type == "certificate")
        
        self.credentials_group.setVisible(not is_certificate)
        self.certificate_group.setVisible(is_certificate)
    
    def _on_cert_source_changed(self, index):
        """Wechselt zwischen Datei-Auswahl und Einstellungen."""
        source = self.cert_source_combo.currentData()
        self.pfx_file_widget.setVisible(source == "file")
        self.pfx_settings_widget.setVisible(source == "settings")
        if source == "settings":
            self._refresh_cert_combo()
    
    def _refresh_cert_combo(self):
        """Aktualisiert das Dropdown mit verfügbaren Zertifikaten."""
        self.cert_select_combo.clear()
        try:
            from config.certificates import get_certificate_manager
            manager = get_certificate_manager()
            certs = manager.list_certificates()
            
            if not certs:
                self.cert_select_combo.addItem("-- Keine Zertifikate in Einstellungen --", "")
            else:
                self.cert_select_combo.addItem("-- Zertifikat auswählen --", "")
                for cert in certs:
                    status = " (ABGELAUFEN)" if cert.is_expired else ""
                    self.cert_select_combo.addItem(f"{cert.name}{status}", cert.id)
        except Exception as e:
            self.cert_select_combo.addItem(f"Fehler: {e}", "")
    
    def _on_cert_selected(self, index):
        """Zeigt Info zum ausgewählten Zertifikat."""
        cert_id = self.cert_select_combo.currentData()
        self._selected_cert_id = cert_id or ""
        
        if not cert_id:
            self.cert_info_label.setText("")
            return
        
        try:
            from config.certificates import get_certificate_manager
            manager = get_certificate_manager()
            cert = manager.get_certificate(cert_id)
            if cert:
                from datetime import datetime
                valid_until = datetime.fromisoformat(cert.valid_until.replace('Z', '+00:00'))
                date_str = valid_until.strftime('%d.%m.%Y')
                self.cert_info_label.setText(
                    f"Inhaber: {cert.subject_cn}\n"
                    f"Gültig bis: {date_str}"
                )
        except Exception:
            self.cert_info_label.setText("")
    
    def _on_cert_format_changed(self, index):
        """Zeigt/versteckt PFX/JKS-Felder je nach Format."""
        cert_format = self.cert_format_combo.currentData()
        is_pfx = (cert_format == "pfx")
        
        self.pfx_widget.setVisible(is_pfx)
        self.jks_widget.setVisible(not is_pfx)
    
    def _browse_pfx(self):
        """Oeffnet Dateidialog fuer PFX-Auswahl."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "PFX-Zertifikat auswaehlen",
            "",
            "PFX-Dateien (*.pfx *.p12);;Alle Dateien (*.*)"
        )
        if file_path:
            self._pfx_path = file_path
            # Nur Dateiname anzeigen
            filename = os.path.basename(file_path)
            self.pfx_path_label.setText(filename)
            self.pfx_path_label.setStyleSheet("color: #080; font-weight: bold;")
    
    def _browse_jks(self):
        """Oeffnet Dateidialog fuer JKS-Auswahl."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "JKS-Zertifikat auswaehlen",
            "",
            "JKS-Dateien (*.jks);;Alle Dateien (*.*)"
        )
        if file_path:
            self._jks_path = file_path
            filename = os.path.basename(file_path)
            self.jks_path_label.setText(filename)
            self.jks_path_label.setStyleSheet("color: #080; font-weight: bold;")
    
    def _on_smartadmin_changed(self, state):
        """Wird aufgerufen wenn SmartAdmin-Checkbox geändert wird."""
        use_smartadmin = self.use_smartadmin_check.isChecked()
        # Info-Label aktualisieren
        if use_smartadmin:
            self.endpoint_info_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        else:
            self.endpoint_info_label.setStyleSheet("color: #999; font-size: 11px; padding: 4px;")
        self._on_known_endpoint_changed(self.known_endpoints_combo.currentIndex())
    
    def _populate_known_endpoints(self):
        """Füllt das Dropdown mit allen SmartAdmin-Endpunkten."""
        self.known_endpoints_combo.clear()
        self.known_endpoints_combo.addItem("-- Versicherer auswählen --", "")
        
        try:
            from config.smartadmin_endpoints import SMARTADMIN_COMPANIES
            
            # Nach Namen sortieren
            sorted_companies = sorted(SMARTADMIN_COMPANIES.items(), key=lambda x: x[1].name)
            
            for key, company in sorted_companies:
                auth_types = company.get_auth_types()
                
                # Auth-Typ Indikator
                suffix = ""
                if "Certificate" in auth_types:
                    suffix = " [Zertifikat]"
                elif "TGICCertificate" in auth_types or "TGICmTAN" in auth_types:
                    suffix = " [TGIC]"
                elif "Ticket" in auth_types:
                    suffix = " [EasyLogin]"
                elif "Strong" in auth_types:
                    suffix = " [2FA]"
                # Weak braucht kein Suffix
                
                # URL-Status
                has_url = bool(company.get_sts_url() or company.get_transfer_url())
                if not has_url:
                    suffix += " (URL fehlt)"
                
                self.known_endpoints_combo.addItem(f"{company.name}{suffix}", key)
        except Exception as e:
            self.known_endpoints_combo.addItem(f"Fehler: {e}", "")
    
    def _on_known_endpoint_changed(self, index):
        """Zeigt Info zum ausgewählten SmartAdmin-Endpunkt."""
        key = self.known_endpoints_combo.currentData()
        if not key:
            self.endpoint_info_label.setText("")
            self._smartadmin_company_key = ""
            return
        
        try:
            from config.smartadmin_endpoints import SMARTADMIN_COMPANIES
            company = SMARTADMIN_COMPANIES.get(key)
            
            if not company:
                self.endpoint_info_label.setText("")
                return
            
            self._smartadmin_company_key = key
            
            auth_types = company.get_auth_types()
            auth_label = ", ".join(auth_types) if auth_types else "Keine"
            
            sts_url = company.get_sts_url()
            transfer_url = company.get_transfer_url()
            extranet_url = company.get_extranet_url()
            
            info_parts = [f"Auth-Typen: {auth_label}"]
            if sts_url:
                info_parts.append(f"STS: {sts_url[:60]}...")
            if transfer_url:
                info_parts.append(f"Transfer: {transfer_url[:60]}...")
            if extranet_url:
                info_parts.append(f"Extranet: {extranet_url[:60]}...")
            if company.easylogin_vuid:
                info_parts.append(f"EasyLogin-ID: {company.easylogin_vuid}")
            
            if self.use_smartadmin_check.isChecked():
                info_parts.append("\n✓ SmartAdmin-Flow wird verwendet")
            
            self.endpoint_info_label.setText("\n".join(info_parts))
        except Exception as e:
            self.endpoint_info_label.setText(f"Fehler: {e}")
    
    def _apply_known_endpoint(self):
        """Übernimmt den ausgewählten SmartAdmin-Endpunkt in die Felder."""
        key = self.known_endpoints_combo.currentData()
        if not key:
            return
        
        try:
            from config.smartadmin_endpoints import SMARTADMIN_COMPANIES
            company = SMARTADMIN_COMPANIES.get(key)
            
            if not company:
                return
            
            # SmartAdmin-Key speichern
            self._smartadmin_company_key = key
            
            # Felder füllen
            self.vu_name_input.setText(company.name)
            
            # URLs setzen
            sts_url = company.get_sts_url() or ""
            transfer_url = company.get_transfer_url() or ""
            
            self.sts_url_input.setText(sts_url)
            self.transfer_url_input.setText(transfer_url)
            
            # Legacy-Feld für Kompatibilität
            self.endpoint_input.setText(transfer_url or sts_url)
            
            # Auth-Typ basierend auf verfügbaren Typen
            auth_types = company.get_auth_types()
            
            # Zertifikat-Auth wenn nötig
            cert_types = ["Certificate", "TGICCertificate", "TGICmTAN"]
            needs_cert = any(t in auth_types for t in cert_types)
            
            if needs_cert:
                for i in range(self.auth_type_combo.count()):
                    if self.auth_type_combo.itemData(i) == "certificate":
                        self.auth_type_combo.setCurrentIndex(i)
                        break
            else:  # Password (Weak, Strong, Ticket)
                for i in range(self.auth_type_combo.count()):
                    if self.auth_type_combo.itemData(i) == "sts":
                        self.auth_type_combo.setCurrentIndex(i)
                        break
            
            # URLs automatisch ableiten wenn nur eine vorhanden
            if sts_url and not transfer_url:
                self._derive_urls()
            elif transfer_url and not sts_url:
                self._derive_urls()
            
            # Info aktualisieren
            self._on_known_endpoint_changed(self.known_endpoints_combo.currentIndex())
                
        except Exception as e:
            self._show_validation_error(f"SmartAdmin-Endpunkt konnte nicht geladen werden: {e}")
    
    def _derive_urls(self):
        """Leitet die fehlende URL aus der vorhandenen ab."""
        from api.vu_connections import derive_sts_url, derive_transfer_url
        
        sts_url = self.sts_url_input.text().strip()
        transfer_url = self.transfer_url_input.text().strip()
        
        # Wenn STS vorhanden, Transfer ableiten
        if sts_url and not transfer_url:
            derived = derive_transfer_url(sts_url)
            if derived and derived != sts_url:
                self.transfer_url_input.setText(derived)
                self.transfer_url_input.setStyleSheet("color: #666;")  # Abgeleitet
        
        # Wenn Transfer vorhanden, STS ableiten
        elif transfer_url and not sts_url:
            derived = derive_sts_url(transfer_url)
            if derived and derived != transfer_url:
                self.sts_url_input.setText(derived)
                self.sts_url_input.setStyleSheet("color: #666;")  # Abgeleitet
        
        # Beide leer - nichts tun
        elif not sts_url and not transfer_url:
            self._show_validation_info(
                "Bitte mindestens eine URL (STS oder Transfer) eingeben."
            )
    
    def _fill_endpoint(self, name: str, url: str, auth_type: str = "sts"):
        if name:
            self.vu_name_input.setText(name)
        self.endpoint_input.setText(url)
        
        # Auth-Typ setzen
        for i in range(self.auth_type_combo.count()):
            if self.auth_type_combo.itemData(i) == auth_type:
                self.auth_type_combo.setCurrentIndex(i)
                break
    
    def _validate_and_accept(self):
        """Validiert die Eingaben vor dem Akzeptieren."""
        self._clear_status()
        auth_type = self.auth_type_combo.currentData()
        
        if not self.vu_name_input.text().strip():
            self._show_validation_error("Bitte VU-Name eingeben.")
            return
        
        # Mindestens eine URL muss vorhanden sein
        sts_url = self.sts_url_input.text().strip()
        transfer_url = self.transfer_url_input.text().strip()
        
        if not sts_url and not transfer_url:
            self._show_validation_error("Bitte mindestens eine URL (STS oder Transfer) eingeben.")
            return
        
        if auth_type == "certificate":
            cert_format = self.cert_format_combo.currentData()
            cert_source = self.cert_source_combo.currentData()
            
            if cert_format == "pfx":
                if cert_source == "settings":
                    # Zertifikat aus Einstellungen
                    if not self._selected_cert_id:
                        self._show_validation_error("Bitte Zertifikat aus Einstellungen auswählen.")
                        return
                    if not self.cert_settings_password.text():
                        self._show_validation_error("Bitte Passwort für das Zertifikat eingeben.")
                        return
                else:
                    # Datei manuell auswählen
                    if not self._pfx_path:
                        self._show_validation_error("Bitte PFX-Zertifikat auswaehlen.")
                        return
                    if not os.path.exists(self._pfx_path):
                        self._show_validation_error("PFX-Datei nicht gefunden.")
                        return
            else:  # jks
                if not self._jks_path:
                    self._show_validation_error("Bitte JKS-Zertifikat auswaehlen.")
                    return
                if not os.path.exists(self._jks_path):
                    self._show_validation_error("JKS-Datei nicht gefunden.")
                    return
        else:
            if not self.username_input.text():
                self._show_validation_error("Bitte Benutzername eingeben.")
                return
            if not self.password_input.text():
                self._show_validation_error("Bitte Passwort eingeben.")
                return
        
        self.accept()
    
    def get_data(self) -> dict:
        auth_type = self.auth_type_combo.currentData()
        
        # URLs sammeln
        sts_url = self.sts_url_input.text().strip()
        transfer_url = self.transfer_url_input.text().strip()
        
        data = {
            'vu_name': self.vu_name_input.text().strip(),
            'vu_number': self.vu_number_input.text().strip() or None,
            'endpoint_url': transfer_url or sts_url,  # Legacy-Feld
            'sts_url': sts_url,
            'transfer_url': transfer_url,
            'auth_type': auth_type,
        }
        
        if auth_type == "certificate":
            data['username'] = ""
            data['password'] = ""
            
            cert_format = self.cert_format_combo.currentData()
            cert_source = self.cert_source_combo.currentData()
            
            if cert_format == "pfx":
                data['cert_format'] = 'pfx'
                
                if cert_source == "settings" and self._selected_cert_id:
                    # Pfad aus CertificateManager holen
                    try:
                        from config.certificates import get_certificate_manager
                        manager = get_certificate_manager()
                        cert = manager.get_certificate(self._selected_cert_id)
                        if cert:
                            data['pfx_path'] = cert.full_path
                            data['pfx_password'] = self.cert_settings_password.text()
                            data['cert_id'] = self._selected_cert_id  # Für spätere Referenz
                        else:
                            data['pfx_path'] = ""
                            data['pfx_password'] = ""
                    except Exception:
                        data['pfx_path'] = ""
                        data['pfx_password'] = ""
                else:
                    data['pfx_path'] = self._pfx_path
                    data['pfx_password'] = self.pfx_password_input.text()
                
                data['jks_path'] = ""
                data['jks_password'] = ""
                data['jks_alias'] = ""
                data['jks_key_password'] = ""
            else:  # jks
                data['cert_format'] = 'jks'
                data['pfx_path'] = ""
                data['pfx_password'] = ""
                data['jks_path'] = self._jks_path
                data['jks_password'] = self.jks_password_input.text()
                data['jks_alias'] = self.jks_alias_input.text().strip()
                data['jks_key_password'] = self.jks_key_password_input.text()
        else:
            data['username'] = self.username_input.text()
            data['password'] = self.password_input.text()
            data['cert_format'] = ''
            data['pfx_path'] = ""
            data['pfx_password'] = ""
            data['jks_path'] = ""
            data['jks_password'] = ""
            data['jks_alias'] = ""
            data['jks_key_password'] = ""
        
        # SmartAdmin-Felder
        data['use_smartadmin_flow'] = self.use_smartadmin_check.isChecked()
        data['smartadmin_company_key'] = self._smartadmin_company_key if self.use_smartadmin_check.isChecked() else None
        
        # Consumer-ID
        data['consumer_id'] = self.consumer_id_input.text().strip() or None
        
        # Extranet-URL aus SmartAdmin übernehmen falls vorhanden
        if data['use_smartadmin_flow'] and self._smartadmin_company_key:
            try:
                from config.smartadmin_endpoints import SMARTADMIN_COMPANIES
                company = SMARTADMIN_COMPANIES.get(self._smartadmin_company_key)
                if company:
                    extranet = company.get_extranet_url()
                    if extranet:
                        data['extranet_url'] = extranet
            except Exception:
                pass
        
        return data


class EditConnectionDialog(QDialog):
    """Dialog zum Bearbeiten einer VU-Verbindung mit PFX/JKS-Unterstuetzung."""
    
    def __init__(self, connection: VUConnection, credentials: Optional[VUCredentials], 
                 cert_config: dict = None, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.credentials = credentials
        self.cert_config = cert_config or {}
        self._password_changed = False
        self._pfx_path = self.cert_config.get('pfx_path', '')
        self._jks_path = self.cert_config.get('jks_path', '')
        self._cert_changed = False
        
        self.setWindowTitle(f"Verbindung bearbeiten - {connection.vu_name}")
        self.setMinimumWidth(550)
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.vu_name_input = QLineEdit(connection.vu_name)
        form.addRow("VU Name:", self.vu_name_input)
        
        self.vu_number_input = QLineEdit(connection.vu_number or "")
        form.addRow("VU Nummer:", self.vu_number_input)
        
        self.endpoint_input = QLineEdit(connection.endpoint_url)
        form.addRow("Endpoint URL:", self.endpoint_input)
        
        # Auth-Typ mit Zertifikat-Option (Signal wird spaeter verbunden!)
        self.auth_type_combo = QComboBox()
        self.auth_type_combo.addItem("STS-Token (Username/Password)", "sts")
        self.auth_type_combo.addItem("X.509 Zertifikat (easy Login)", "certificate")
        self.auth_type_combo.addItem("WS-Security Username", "wsse")
        self.auth_type_combo.addItem("HTTP Basic Auth", "basic")
        # NICHT hier connecten - erst nachdem alle Widgets erstellt sind!
        form.addRow("Auth-Typ:", self.auth_type_combo)
        
        self.is_active_check = QCheckBox("Aktiv")
        self.is_active_check.setChecked(connection.is_active)
        form.addRow("Status:", self.is_active_check)
        
        layout.addLayout(form)
        
        # === Username/Password Bereich ===
        self.credentials_group = QGroupBox("Zugangsdaten")
        creds_layout = QFormLayout(self.credentials_group)
        
        self.username_input = QLineEdit()
        if credentials and credentials.username != '__certificate__':
            self.username_input.setText(credentials.username)
        creds_layout.addRow("Benutzername:", self.username_input)
        
        # Passwort-Zeile mit Anzeigen-Button
        pw_layout = QHBoxLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        if credentials and credentials.password != '__certificate__':
            self.password_input.setText(credentials.password)
        self.password_input.textChanged.connect(self._on_password_changed)
        pw_layout.addWidget(self.password_input)
        
        self.show_pw_btn = QPushButton("Anzeigen")
        self.show_pw_btn.setMaximumWidth(70)
        self.show_pw_btn.setCheckable(True)
        self.show_pw_btn.toggled.connect(self._toggle_password_visibility)
        pw_layout.addWidget(self.show_pw_btn)
        
        creds_layout.addRow("Passwort:", pw_layout)
        
        self.pw_hint = QLabel("")
        self.pw_hint.setStyleSheet("color: #666; font-style: italic;")
        creds_layout.addRow("", self.pw_hint)
        
        layout.addWidget(self.credentials_group)
        
        # === Zertifikat Bereich ===
        self.certificate_group = QGroupBox("Zertifikat (easy Login)")
        cert_layout = QVBoxLayout(self.certificate_group)
        
        # Info-Text
        info_label = QLabel(
            "Mit einem easy Login Zertifikat koennen Sie auf 54+ Versicherer zugreifen.\n"
            "Unterstuetzte Formate: PFX/P12 (Windows) oder JKS (Java KeyStore)"
        )
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        cert_layout.addWidget(info_label)
        
        # Format-Auswahl
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Format:"))
        self.cert_format_combo = QComboBox()
        self.cert_format_combo.addItem("PFX / P12 (Windows)", "pfx")
        self.cert_format_combo.addItem("JKS (Java KeyStore)", "jks")
        self.cert_format_combo.currentIndexChanged.connect(self._on_cert_format_changed)
        # Aktuelles Format setzen
        current_format = self.cert_config.get('cert_format', 'pfx')
        if current_format == 'jks':
            self.cert_format_combo.setCurrentIndex(1)
        format_row.addWidget(self.cert_format_combo)
        format_row.addStretch()
        cert_layout.addLayout(format_row)
        
        # === PFX-Bereich ===
        self.pfx_widget = QWidget()
        pfx_layout = QVBoxLayout(self.pfx_widget)
        pfx_layout.setContentsMargins(0, 0, 0, 0)
        
        pfx_row = QHBoxLayout()
        self.pfx_path_label = QLabel("Keine Datei ausgewaehlt")
        if self._pfx_path:
            self.pfx_path_label.setText(os.path.basename(self._pfx_path))
            self.pfx_path_label.setStyleSheet("color: #080; font-weight: bold;")
        else:
            self.pfx_path_label.setStyleSheet("color: #999;")
        pfx_row.addWidget(self.pfx_path_label, 1)
        
        self.pfx_browse_btn = QPushButton("PFX/P12 waehlen...")
        self.pfx_browse_btn.clicked.connect(self._browse_pfx)
        pfx_row.addWidget(self.pfx_browse_btn)
        pfx_layout.addLayout(pfx_row)
        
        pfx_pw_layout = QFormLayout()
        self.pfx_password_input = QLineEdit()
        self.pfx_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pfx_password_input.setPlaceholderText("Passwort fuer die PFX-Datei")
        if self.cert_config.get('pfx_password'):
            self.pfx_password_input.setText(self.cert_config['pfx_password'])
        pfx_pw_layout.addRow("Passwort:", self.pfx_password_input)
        pfx_layout.addLayout(pfx_pw_layout)
        
        cert_layout.addWidget(self.pfx_widget)
        
        # === JKS-Bereich ===
        self.jks_widget = QWidget()
        jks_layout = QVBoxLayout(self.jks_widget)
        jks_layout.setContentsMargins(0, 0, 0, 0)
        
        jks_row = QHBoxLayout()
        self.jks_path_label = QLabel("Keine Datei ausgewaehlt")
        if self._jks_path:
            self.jks_path_label.setText(os.path.basename(self._jks_path))
            self.jks_path_label.setStyleSheet("color: #080; font-weight: bold;")
        else:
            self.jks_path_label.setStyleSheet("color: #999;")
        jks_row.addWidget(self.jks_path_label, 1)
        
        self.jks_browse_btn = QPushButton("JKS waehlen...")
        self.jks_browse_btn.clicked.connect(self._browse_jks)
        jks_row.addWidget(self.jks_browse_btn)
        jks_layout.addLayout(jks_row)
        
        jks_form = QFormLayout()
        self.jks_password_input = QLineEdit()
        self.jks_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.jks_password_input.setPlaceholderText("KeyStore-Passwort")
        if self.cert_config.get('jks_password'):
            self.jks_password_input.setText(self.cert_config['jks_password'])
        jks_form.addRow("KeyStore-PW:", self.jks_password_input)
        
        self.jks_alias_input = QLineEdit()
        self.jks_alias_input.setPlaceholderText("(leer = erstes Zertifikat)")
        if self.cert_config.get('jks_alias'):
            self.jks_alias_input.setText(self.cert_config['jks_alias'])
        jks_form.addRow("Alias:", self.jks_alias_input)
        
        self.jks_key_password_input = QLineEdit()
        self.jks_key_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.jks_key_password_input.setPlaceholderText("(leer = KeyStore-PW)")
        if self.cert_config.get('jks_key_password'):
            self.jks_key_password_input.setText(self.cert_config['jks_key_password'])
        jks_form.addRow("Key-PW:", self.jks_key_password_input)
        
        jks_layout.addLayout(jks_form)
        self.jks_widget.setVisible(current_format == 'jks')
        self.pfx_widget.setVisible(current_format != 'jks')
        cert_layout.addWidget(self.jks_widget)
        
        layout.addWidget(self.certificate_group)
        
        # Jetzt Signal verbinden und Auth-Typ setzen (NACHDEM alle Widgets erstellt)
        self.auth_type_combo.currentIndexChanged.connect(self._on_auth_type_changed)
        for i in range(self.auth_type_combo.count()):
            if self.auth_type_combo.itemData(i) == connection.auth_type:
                self.auth_type_combo.setCurrentIndex(i)
                break
        # Initial: Richtige Gruppe anzeigen
        self._on_auth_type_changed(0)
        
        # Inline-Status-Label fuer Validierungsfehler (statt modaler Dialoge)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #dc2626; font-size: 12px; padding: 4px 8px;")
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _show_validation_error(self, message: str):
        """Zeigt eine Validierungsfehlermeldung inline an."""
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #dc2626; font-size: 12px; padding: 4px 8px;")
        self._status_label.setVisible(True)
    
    def _clear_status(self):
        """Loescht die Status-Anzeige."""
        self._status_label.setText("")
        self._status_label.setVisible(False)
    
    def _on_auth_type_changed(self, index):
        """Zeigt/versteckt Felder je nach Auth-Typ."""
        self._clear_status()
        auth_type = self.auth_type_combo.currentData()
        is_certificate = (auth_type == "certificate")
        
        self.credentials_group.setVisible(not is_certificate)
        self.certificate_group.setVisible(is_certificate)
    
    def _on_cert_format_changed(self, index):
        """Zeigt/versteckt PFX/JKS-Felder je nach Format."""
        cert_format = self.cert_format_combo.currentData()
        is_pfx = (cert_format == "pfx")
        
        self.pfx_widget.setVisible(is_pfx)
        self.jks_widget.setVisible(not is_pfx)
    
    def _browse_pfx(self):
        """Oeffnet Dateidialog fuer PFX-Auswahl."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "PFX-Zertifikat auswaehlen",
            "",
            "PFX-Dateien (*.pfx *.p12);;Alle Dateien (*.*)"
        )
        if file_path:
            self._pfx_path = file_path
            self._cert_changed = True
            filename = os.path.basename(file_path)
            self.pfx_path_label.setText(filename)
            self.pfx_path_label.setStyleSheet("color: #080; font-weight: bold;")
    
    def _browse_jks(self):
        """Oeffnet Dateidialog fuer JKS-Auswahl."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "JKS-Zertifikat auswaehlen",
            "",
            "JKS-Dateien (*.jks);;Alle Dateien (*.*)"
        )
        if file_path:
            self._jks_path = file_path
            self._cert_changed = True
            filename = os.path.basename(file_path)
            self.jks_path_label.setText(filename)
            self.jks_path_label.setStyleSheet("color: #080; font-weight: bold;")
    
    def _toggle_password_visibility(self, show: bool):
        if show:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_pw_btn.setText("Verbergen")
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_pw_btn.setText("Anzeigen")
    
    def _on_password_changed(self):
        if self.credentials and self.password_input.text() != self.credentials.password:
            self._password_changed = True
            self.pw_hint.setText("Passwort wird geaendert")
        else:
            self._password_changed = False
            self.pw_hint.setText("")
    
    def _validate_and_accept(self):
        """Validiert die Eingaben vor dem Akzeptieren."""
        self._clear_status()
        auth_type = self.auth_type_combo.currentData()
        
        if not self.vu_name_input.text().strip():
            self._show_validation_error("Bitte VU-Name eingeben.")
            return
        
        if not self.endpoint_input.text().strip():
            self._show_validation_error("Bitte Endpoint-URL eingeben.")
            return
        
        if auth_type == "certificate":
            cert_format = self.cert_format_combo.currentData()
            if cert_format == "pfx":
                if not self._pfx_path:
                    self._show_validation_error("Bitte PFX-Zertifikat auswaehlen.")
                    return
                if not os.path.exists(self._pfx_path):
                    self._show_validation_error("PFX-Datei nicht gefunden.")
                    return
            else:  # jks
                if not self._jks_path:
                    self._show_validation_error("Bitte JKS-Zertifikat auswaehlen.")
                    return
                if not os.path.exists(self._jks_path):
                    self._show_validation_error("JKS-Datei nicht gefunden.")
                    return
        else:
            # Username/Password Auth
            if not self.username_input.text().strip():
                self._show_validation_error("Bitte Benutzername eingeben.")
                return
        
        self.accept()
    
    def get_data(self) -> dict:
        auth_type = self.auth_type_combo.currentData()
        
        data = {
            'vu_name': self.vu_name_input.text().strip(),
            'vu_number': self.vu_number_input.text().strip() or None,
            'endpoint_url': self.endpoint_input.text().strip(),
            'auth_type': auth_type,
            'is_active': self.is_active_check.isChecked(),
        }
        
        if auth_type == "certificate":
            data['username'] = '__certificate__'
            data['password'] = '__certificate__'
            data['password_changed'] = False
            
            cert_format = self.cert_format_combo.currentData()
            if cert_format == "pfx":
                data['cert_format'] = 'pfx'
                data['pfx_path'] = self._pfx_path
                data['pfx_password'] = self.pfx_password_input.text()
                data['jks_path'] = ""
                data['jks_password'] = ""
                data['jks_alias'] = ""
                data['jks_key_password'] = ""
            else:  # jks
                data['cert_format'] = 'jks'
                data['pfx_path'] = ""
                data['pfx_password'] = ""
                data['jks_path'] = self._jks_path
                data['jks_password'] = self.jks_password_input.text()
                data['jks_alias'] = self.jks_alias_input.text().strip()
                data['jks_key_password'] = self.jks_key_password_input.text()
            
            data['cert_changed'] = self._cert_changed
        else:
            data['username'] = self.username_input.text()
            data['password'] = self.password_input.text()
            data['password_changed'] = self._password_changed or (self.credentials is None)
            data['cert_format'] = ''
            data['pfx_path'] = ""
            data['pfx_password'] = ""
            data['jks_path'] = ""
            data['jks_password'] = ""
            data['jks_alias'] = ""
            data['jks_key_password'] = ""
            data['cert_changed'] = False
        
        return data


class BiPROView(QWidget):
    """
    BiPRO Datenabruf-Ansicht.
    
    Zeigt VU-Verbindungen und ermöglicht Lieferungsabruf.
    """
    
    # Signal wenn Dokumente ins Archiv übertragen wurden
    documents_uploaded = Signal()
    
    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        
        self.api_client = api_client
        self.vu_api = VUConnectionsAPI(api_client)
        self.docs_api = DocumentsAPI(api_client)
        
        # Cache-Service fuer VU-Verbindungen
        from services.data_cache import get_cache_service
        self._cache = get_cache_service(api_client)
        # WICHTIG: QueuedConnection verwenden, da Signals aus Background-Thread kommen!
        self._cache.connections_updated.connect(
            self._on_cache_connections_updated,
            Qt.ConnectionType.QueuedConnection
        )
        
        self._connections: List[VUConnection] = []
        self._current_connection: Optional[VUConnection] = None
        self._current_credentials: Optional[VUCredentials] = None
        self._shipments = []
        
        self._fetch_worker = None
        self._download_worker = None
        self._parallel_manager = None  # ParallelDownloadManager für parallele Downloads
        self._acknowledge_worker = None
        self._mail_import_worker = None  # MailImportWorker fuer IMAP-Import
        self._mail_progress_toast = None  # Progress-Toast fuer Mail-Import
        self._download_queue = []
        self._download_stats = {}
        
        # "Alle VUs abholen" State Machine
        self._all_vus_mode = False
        self._vu_queue: list = []  # Queue von VUConnections
        self._all_vus_current_index = 0
        self._all_vus_total = 0
        self._all_vus_stats = {
            'vus_processed': 0, 'total_shipments': 0, 'total_docs': 0, 'vus_skipped': 0
        }
        
        # Liste aller aktiven Worker fuer sauberes Cleanup
        self._active_workers: list = []
        
        self._setup_ui()
        
        # Progress-Overlay erstellen
        self._progress_overlay = BiPROProgressOverlay(self)
        self._progress_overlay.close_requested.connect(self._on_progress_overlay_closed)
        
        self._load_connections(force_refresh=False)  # Aus Cache
    
    def _register_worker(self, worker: QThread):
        """Registriert einen Worker fuer spaeteres Cleanup."""
        if worker not in self._active_workers:
            self._active_workers.append(worker)
            worker.finished.connect(lambda: self._unregister_worker(worker))
    
    def _unregister_worker(self, worker: QThread):
        """Entfernt einen beendeten Worker aus der Liste."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
    
    def cleanup(self):
        """Räumt Worker-Threads auf."""
        # Alle registrierten Worker stoppen
        for worker in self._active_workers[:]:  # Kopie der Liste
            if worker and worker.isRunning():
                logger.info(f"Warte auf Worker: {worker.__class__.__name__}")
                worker.quit()
                if not worker.wait(2000):  # 2 Sekunden Timeout
                    logger.warning(f"Worker {worker.__class__.__name__} antwortet nicht, terminiere...")
                    worker.terminate()
                    worker.wait(1000)
        
        self._active_workers.clear()
        
        # Legacy-Cleanup fuer direkte Worker-Referenzen
        if self._fetch_worker and self._fetch_worker.isRunning():
            self._fetch_worker.quit()
            self._fetch_worker.wait(1000)
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.quit()
            self._download_worker.wait(1000)
        if self._parallel_manager and self._parallel_manager.isRunning():
            self._parallel_manager.cancel()
            self._parallel_manager.wait(2000)
        if self._acknowledge_worker and self._acknowledge_worker.isRunning():
            self._acknowledge_worker.quit()
            self._acknowledge_worker.wait(1000)
    
    def closeEvent(self, event):
        """Wird aufgerufen wenn das Widget geschlossen wird."""
        self.cleanup()
        super().closeEvent(event)
    
    def resizeEvent(self, event):
        """Passt das Progress-Overlay an die Fenstergröße an."""
        super().resizeEvent(event)
        if hasattr(self, '_progress_overlay'):
            self._progress_overlay.setGeometry(self.rect())
    
    def _on_progress_overlay_closed(self):
        """Callback wenn das Progress-Overlay geschlossen wird."""
        # Dokumenten-Liste aktualisieren
        self.documents_uploaded.emit()
    
    def _setup_ui(self):
        """UI aufbauen (ACENCIA Design)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header (ACENCIA Style)
        header = QLabel("BiPRO Datenabruf")
        header.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {TEXT_PRIMARY};
            font-weight: 400;
            padding-bottom: 8px;
        """)
        layout.addWidget(header)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Linke Seite: Verbindungen
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        conn_header = QHBoxLayout()
        conn_header.addWidget(QLabel("VU-Verbindungen"))
        
        add_btn = QPushButton("Hinzufügen")
        add_btn.setStyleSheet(get_button_secondary_style())
        add_btn.clicked.connect(self._add_connection)
        conn_header.addWidget(add_btn)
        
        left_layout.addLayout(conn_header)
        
        self.connections_list = QListWidget()
        self.connections_list.itemClicked.connect(self._on_connection_selected)
        self.connections_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.connections_list.customContextMenuRequested.connect(self._show_connection_context_menu)
        left_layout.addWidget(self.connections_list)
        
        # Buttons unter der Liste
        conn_buttons = QHBoxLayout()
        
        edit_btn = QPushButton("Bearbeiten")
        edit_btn.setToolTip("Verbindung bearbeiten")
        edit_btn.setStyleSheet(get_button_ghost_style())
        edit_btn.clicked.connect(self._edit_connection)
        conn_buttons.addWidget(edit_btn)
        
        show_pw_btn = QPushButton("Passwort")
        show_pw_btn.setToolTip("Passwort anzeigen")
        show_pw_btn.setStyleSheet(get_button_ghost_style())
        show_pw_btn.clicked.connect(self._show_password)
        conn_buttons.addWidget(show_pw_btn)
        
        delete_btn = QPushButton("Löschen")
        delete_btn.setToolTip("Verbindung löschen")
        delete_btn.setStyleSheet(get_button_ghost_style())
        delete_btn.clicked.connect(self._delete_connection)
        conn_buttons.addWidget(delete_btn)
        
        conn_buttons.addStretch()
        left_layout.addLayout(conn_buttons)
        
        splitter.addWidget(left_widget)
        
        # Rechte Seite: Lieferungen
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        # "Mails abholen" Button (IMAP-Import, braucht keine VU-Auswahl)
        from i18n.de import BIPRO_MAIL_FETCH, BIPRO_MAIL_FETCH_TOOLTIP
        self.mail_fetch_btn = QPushButton(f"  {BIPRO_MAIL_FETCH}")
        self.mail_fetch_btn.setFixedHeight(30)
        self.mail_fetch_btn.setToolTip(BIPRO_MAIL_FETCH_TOOLTIP)
        self.mail_fetch_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 14px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #A5D6A7;
                color: #E8F5E9;
            }
        """)
        self.mail_fetch_btn.clicked.connect(self._fetch_mails)
        toolbar.addWidget(self.mail_fetch_btn)
        
        self.download_btn = QPushButton("📥 Ausgewählte herunterladen")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download_selected)
        toolbar.addWidget(self.download_btn)
        
        self.download_all_btn = QPushButton("Alle herunterladen")
        self.download_all_btn.setEnabled(False)
        self.download_all_btn.clicked.connect(self._download_all)
        toolbar.addWidget(self.download_all_btn)
        
        # Separator
        separator_line = QFrame()
        separator_line.setFrameShape(QFrame.Shape.VLine)
        separator_line.setStyleSheet(f"color: {BORDER_DEFAULT};")
        toolbar.addWidget(separator_line)
        
        # "Alle VUs abholen" Button (braucht keine VU-Auswahl)
        from i18n.de import BIPRO_FETCH_ALL, BIPRO_FETCH_ALL_TOOLTIP
        self.fetch_all_vus_btn = QPushButton(BIPRO_FETCH_ALL)
        self.fetch_all_vus_btn.setStyleSheet(get_button_primary_style())
        self.fetch_all_vus_btn.setToolTip(BIPRO_FETCH_ALL_TOOLTIP)
        self.fetch_all_vus_btn.clicked.connect(self._fetch_all_vus)
        toolbar.addWidget(self.fetch_all_vus_btn)
        
        # Quittieren-Button (manuell, nicht automatisch)
        self.acknowledge_btn = QPushButton("Ausgewaehlte quittieren")
        self.acknowledge_btn.setToolTip("Quittiert die ausgewaehlten Lieferungen beim Versicherer.\nACHTUNG: Quittierte Lieferungen werden vom Server geloescht!")
        self.acknowledge_btn.setEnabled(False)
        self.acknowledge_btn.clicked.connect(self._acknowledge_selected)
        toolbar.addWidget(self.acknowledge_btn)
        
        toolbar.addStretch()
        right_layout.addLayout(toolbar)
        
        # Lieferungstabelle
        self.shipments_table = QTableWidget()
        self.shipments_table.setColumnCount(5)
        self.shipments_table.setHorizontalHeaderLabels([
            "ID", "Eingestellt", "Kategorie", "Verfügbar bis", "Transfers"
        ])
        header = self.shipments_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.shipments_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right_layout.addWidget(self.shipments_table)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter)
        
        # Log-Bereich
        log_group = QGroupBox("Protokoll")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
    
    def _log(self, message: str):
        """Nachricht ins Log schreiben."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def _load_connections(self, force_refresh: bool = True):
        """
        VU-Verbindungen laden.
        
        Args:
            force_refresh: True = Vom Server, False = Aus Cache
        """
        if force_refresh:
            self._connections = self.vu_api.list_connections()
            # Cache aktualisieren
            self._cache.invalidate_connections()
        else:
            # Aus Cache versuchen
            cached = self._cache.get_connections(force_refresh=False)
            if cached:
                self._connections = cached
            else:
                # Cache leer -> vom Server laden
                self._connections = self.vu_api.list_connections()
        
        self._update_connections_list()
        self._log(f"{len(self._connections)} VU-Verbindung(en) geladen")
    
    def _update_connections_list(self):
        """Aktualisiert die Verbindungs-Liste in der UI."""
        self.connections_list.clear()
        
        for conn in self._connections:
            item = QListWidgetItem(f"{'🟢' if conn.is_active else '🔴'} {conn.vu_name}")
            item.setData(Qt.ItemDataRole.UserRole, conn)
            self.connections_list.addItem(item)
    
    def _on_cache_connections_updated(self):
        """Callback wenn Cache-Service VU-Verbindungen aktualisiert hat."""
        logger.debug("Cache-Update: VU-Verbindungen")
        self._load_connections(force_refresh=False)
    
    def _add_connection(self):
        """Neue Verbindung hinzufuegen."""
        try:
            dialog = AddConnectionDialog(self)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                
                if not data.get('vu_name') or not data.get('endpoint_url'):
                    self._toast_manager.show_warning("Bitte alle Pflichtfelder ausfuellen.")
                    return
                
                # Bei Zertifikats-Auth: Dummy-Credentials verwenden
                username = data.get('username', '')
                password = data.get('password', '')
                
                if data.get('auth_type') == 'certificate':
                    # Fuer Zertifikat: Platzhalter-Credentials
                    username = '__certificate__'
                    password = '__certificate__'
                
                try:
                    conn_id = self.vu_api.create_connection(
                        vu_name=data['vu_name'],
                        endpoint_url=data['endpoint_url'],
                        username=username,
                        password=password,
                        vu_number=data.get('vu_number'),
                        auth_type=data.get('auth_type', 'sts'),
                        # Erweiterte Felder
                        sts_url=data.get('sts_url', ''),
                        transfer_url=data.get('transfer_url', ''),
                        extranet_url=data.get('extranet_url', ''),
                        # SmartAdmin-Felder
                        use_smartadmin_flow=data.get('use_smartadmin_flow', False),
                        smartadmin_company_key=data.get('smartadmin_company_key'),
                        # Consumer-ID
                        consumer_id=data.get('consumer_id')
                    )
                    
                    if conn_id:
                        # Bei Zertifikats-Auth: Zertifikat-Daten lokal speichern
                        if data.get('auth_type') == 'certificate':
                            self._save_certificate_config(conn_id, data)
                        
                        self._log(f"Verbindung '{data['vu_name']}' erstellt (Auth: {data.get('auth_type', 'sts')})")
                        self._load_connections()
                    else:
                        self._toast_manager.show_error("Verbindung konnte nicht erstellt werden.")
                        
                except Exception as e:
                    self._toast_manager.show_error(f"Fehler beim Erstellen der Verbindung:\n\n{str(e)}")
                    self._log(f"Fehler beim Erstellen: {e}")
                    
        except Exception as e:
            self._toast_manager.show_error(f"Unerwarteter Fehler:\n\n{str(e)}")
            self._log(f"Fehler bei _add_connection: {e}")
    
    def _get_certificate_config_path(self) -> str:
        """Gibt den Pfad zur lokalen Zertifikats-Konfiguration zurueck."""
        import pathlib
        config_dir = pathlib.Path.home() / '.acencia-atlas'
        config_dir.mkdir(exist_ok=True)
        return str(config_dir / 'certificates.json')
    
    def _save_certificate_config(self, connection_id: int, cert_data: dict):
        """Speichert Zertifikats-Konfiguration lokal (UTF-8 fuer Sonderzeichen)."""
        import json
        config_path = self._get_certificate_config_path()
        
        # Bestehende Konfiguration laden
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError, OSError) as e:
                self._log(f"Warnung: Bestehende Zertifikat-Konfiguration konnte nicht geladen werden: {e}")
        
        # Neue Konfiguration speichern (PFX oder JKS)
        config[str(connection_id)] = {
            'cert_format': cert_data.get('cert_format', 'pfx'),
            'pfx_path': cert_data.get('pfx_path', ''),
            'pfx_password': cert_data.get('pfx_password', ''),
            'jks_path': cert_data.get('jks_path', ''),
            'jks_password': cert_data.get('jks_password', ''),
            'jks_alias': cert_data.get('jks_alias', ''),
            'jks_key_password': cert_data.get('jks_key_password', '')
        }
        
        # Explizit UTF-8 fuer Sonderzeichen im Passwort
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        self._log(f"Zertifikat-Konfiguration gespeichert")
    
    def _load_certificate_config(self, connection_id: int) -> dict:
        """Laedt PFX-Konfiguration fuer eine Verbindung (UTF-8 fuer Sonderzeichen)."""
        import json
        config_path = self._get_certificate_config_path()
        
        if not os.path.exists(config_path):
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get(str(connection_id), {})
        except Exception as e:
            self._log(f"Warnung: Zertifikat-Konfiguration konnte nicht geladen werden: {e}")
            return {}
    
    def _get_current_credentials(self, show_errors: bool = True) -> Optional[VUCredentials]:
        """
        Holt Credentials fuer die aktuelle Verbindung.
        
        Unterstuetzt sowohl Username/Password als auch Zertifikats-Auth (easy Login).
        Diese Methode zentralisiert die Credential-Logik fuer alle Download-Operationen.
        
        Args:
            show_errors: Wenn True, werden Fehler als Toast angezeigt
            
        Returns:
            VUCredentials oder None bei Fehler
        """
        if not self._current_connection:
            if show_errors:
                self._toast_manager.show_warning("Keine VU-Verbindung ausgewaehlt.")
            return None
        
        if self._current_connection.auth_type == 'certificate':
            # Zertifikats-Auth: Lokale Konfiguration laden
            self._log("Lade Zertifikat-Konfiguration...")
            cert_config = self._load_certificate_config(self._current_connection.id)
            
            if not cert_config:
                if show_errors:
                    self._toast_manager.show_error(
                        "Zertifikat-Konfiguration nicht gefunden.\n"
                        "Bitte VU-Verbindung loeschen und neu anlegen."
                    )
                return None
            
            cert_format = cert_config.get('cert_format', 'pfx')
            
            if cert_format == 'jks':
                # JKS-Zertifikat
                jks_path = cert_config.get('jks_path', '')
                if not jks_path or not os.path.exists(jks_path):
                    if show_errors:
                        self._toast_manager.show_error(
                            f"JKS-Datei nicht gefunden:\n{jks_path}\nBitte VU-Verbindung aktualisieren."
                        )
                    return None
                
                self._log(f"Verwende JKS: {os.path.basename(jks_path)}")
                return VUCredentials(
                    username="",
                    password="",
                    jks_path=jks_path,
                    jks_password=cert_config.get('jks_password', ''),
                    jks_alias=cert_config.get('jks_alias', ''),
                    jks_key_password=cert_config.get('jks_key_password', '')
                )
            else:
                # PFX-Zertifikat
                pfx_path = cert_config.get('pfx_path', '')
                if not pfx_path or not os.path.exists(pfx_path):
                    if show_errors:
                        self._toast_manager.show_error(
                            f"PFX-Datei nicht gefunden:\n{pfx_path}\nBitte VU-Verbindung aktualisieren."
                        )
                    return None
                
                self._log(f"Verwende PFX: {os.path.basename(pfx_path)}")
                return VUCredentials(
                    username="",
                    password="",
                    pfx_path=pfx_path,
                    pfx_password=cert_config.get('pfx_password', '')
                )
        else:
            # Username/Password vom Server holen
            self._log("Hole Zugangsdaten vom Server...")
            
            try:
                credentials = self.vu_api.get_credentials(self._current_connection.id)
                if not credentials:
                    if show_errors:
                        self._toast_manager.show_error(
                            "Zugangsdaten konnten nicht abgerufen werden.\n"
                            "Bitte VU-Verbindung loeschen und neu anlegen."
                        )
                    return None
                return credentials
            except Exception as e:
                self._log(f"FEHLER: {e}")
                if show_errors:
                    self._toast_manager.show_error(f"Fehler beim Abrufen der Zugangsdaten:\n{e}")
                return None
    
    def _on_connection_selected(self, item: QListWidgetItem):
        """Verbindung ausgewählt - lädt automatisch Lieferungen."""
        conn: VUConnection = item.data(Qt.ItemDataRole.UserRole)
        self._current_connection = conn
        self._current_credentials = None
        self._shipments = []
        self.shipments_table.setRowCount(0)
        
        self.download_btn.setEnabled(False)
        self.download_all_btn.setEnabled(False)
        self.acknowledge_btn.setEnabled(False)
        
        # Automatisch Lieferungen laden wenn Verbindung aktiv ist
        if conn.is_active:
            self._fetch_shipments()
        
        self._log(f"Verbindung '{conn.vu_name}' ausgewählt")
    
    def _show_connection_context_menu(self, position):
        """Kontextmenü für VU-Verbindungen."""
        item = self.connections_list.itemAt(position)
        if not item:
            return
        
        conn: VUConnection = item.data(Qt.ItemDataRole.UserRole)
        
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        menu = QMenu(self)
        
        edit_action = QAction("✏️ Bearbeiten", self)
        edit_action.triggered.connect(self._edit_connection)
        menu.addAction(edit_action)
        
        show_pw_action = QAction("👁️ Passwort anzeigen", self)
        show_pw_action.triggered.connect(self._show_password)
        menu.addAction(show_pw_action)
        
        menu.addSeparator()
        
        delete_action = QAction("🗑️ Löschen", self)
        delete_action.triggered.connect(self._delete_connection)
        menu.addAction(delete_action)
        
        menu.exec(self.connections_list.viewport().mapToGlobal(position))
    
    def _get_selected_connection(self) -> Optional[VUConnection]:
        """Gibt die ausgewählte Verbindung zurück."""
        item = self.connections_list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None
    
    def _show_password(self):
        """Zeigt das Passwort der ausgewählten Verbindung."""
        conn = self._get_selected_connection()
        if not conn:
            self._toast_manager.show_info("Bitte eine Verbindung auswählen.")
            return
        
        # Credentials vom Server holen
        creds = self.vu_api.get_credentials(conn.id)
        
        if creds:
            self._toast_manager.show_info(
                f"Zugangsdaten - {conn.vu_name}\n"
                f"Benutzername: {creds.username}\n"
                f"Passwort: {creds.password}\n"
                f"Endpoint: {conn.endpoint_url}"
            )
        else:
            self._toast_manager.show_error("Zugangsdaten konnten nicht abgerufen werden.")
    
    def _edit_connection(self):
        """Bearbeitet die ausgewaehlte Verbindung."""
        conn = self._get_selected_connection()
        if not conn:
            self._toast_manager.show_info("Bitte eine Verbindung auswaehlen.")
            return
        
        try:
            # Credentials holen fuer das Formular (nur bei Nicht-Zertifikat)
            creds = None
            if conn.auth_type != 'certificate':
                try:
                    creds = self.vu_api.get_credentials(conn.id)
                except Exception as e:
                    self._log(f"Warnung: Credentials konnten nicht geladen werden: {e}")
            
            # Zertifikats-Konfiguration laden
            cert_config = self._load_certificate_config(conn.id)
            
            dialog = EditConnectionDialog(conn, creds, cert_config, self)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                
                # Update auf Server vorbereiten
                update_data = {
                    'vu_name': data['vu_name'],
                    'vu_number': data['vu_number'],
                    'endpoint_url': data['endpoint_url'],
                    'auth_type': data['auth_type'],
                    'is_active': data['is_active']
                }
                
                # Credentials aktualisieren wenn:
                # 1. Passwort geaendert wurde (bei Username/Password Auth)
                # 2. Auth-Typ zu Zertifikat gewechselt (Dummy-Credentials setzen)
                if data.get('password_changed', False):
                    update_data['credentials'] = {
                        'username': data.get('username', ''),
                        'password': data.get('password', '')
                    }
                elif data['auth_type'] == 'certificate' and conn.auth_type != 'certificate':
                    # Wechsel zu Zertifikat-Auth: Dummy-Credentials
                    update_data['credentials'] = {
                        'username': '__certificate__',
                        'password': '__certificate__'
                    }
                
                # Server-Update ausfuehren
                try:
                    success = self.vu_api.update_connection(conn.id, **update_data)
                    
                    if success:
                        # Bei Zertifikats-Auth: Zertifikat-Daten lokal speichern
                        if data['auth_type'] == 'certificate':
                            self._save_certificate_config(conn.id, data)
                        
                        self._log(f"Verbindung '{data['vu_name']}' aktualisiert")
                        self._load_connections()
                    else:
                        self._toast_manager.show_error(
                            "Verbindung konnte nicht aktualisiert werden.\n"
                            "Moeglicherweise ist die Server-Verbindung unterbrochen."
                        )
                except Exception as e:
                    self._toast_manager.show_error(f"Fehler beim Speichern der Verbindung:\n\n{str(e)}")
                    self._log(f"Fehler beim Update: {e}")
                    
        except Exception as e:
            self._toast_manager.show_error(f"Unerwarteter Fehler:\n\n{str(e)}")
            self._log(f"Fehler bei _edit_connection: {e}")
    
    def _delete_connection(self):
        """Löscht die ausgewählte Verbindung."""
        conn = self._get_selected_connection()
        if not conn:
            self._toast_manager.show_info("Bitte eine Verbindung auswählen.")
            return
        
        reply = QMessageBox.question(
            self,
            "Verbindung löschen",
            f"Verbindung '{conn.vu_name}' wirklich löschen?\n\n"
            "Die gespeicherten Zugangsdaten werden unwiderruflich gelöscht.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.vu_api.delete_connection(conn.id):
                self._log(f"Verbindung '{conn.vu_name}' gelöscht")
                self._current_connection = None
                self._load_connections()
            else:
                self._toast_manager.show_error("Verbindung konnte nicht gelöscht werden.")
    
    # ========================================
    # Alle VUs abholen (Orchestrierung)
    # ========================================
    
    def _fetch_all_vus(self):
        """
        Startet den Abruf fuer alle aktiven VU-Verbindungen nacheinander.
        
        Flow: VU1 (fetch → download) → VU2 (fetch → download) → ... → Zusammenfassung
        """
        from i18n.de import (
            BIPRO_FETCH_ALL_NO_ACTIVE, BIPRO_FETCH_ALL_START
        )
        
        # Pruefen ob bereits ein Abruf laeuft
        if self._all_vus_mode:
            return
        
        # Alle aktiven Verbindungen sammeln
        active_connections = [c for c in self._connections if c.is_active]
        
        if not active_connections:
            self._toast_manager.show_info(BIPRO_FETCH_ALL_NO_ACTIVE)
            return
        
        # State Machine initialisieren
        self._all_vus_mode = True
        self._vu_queue = list(active_connections)
        self._all_vus_current_index = 0
        self._all_vus_total = len(active_connections)
        self._all_vus_stats = {
            'vus_processed': 0, 'total_shipments': 0, 
            'total_docs': 0, 'vus_skipped': 0
        }
        
        # UI sperren
        self.fetch_all_vus_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.download_all_btn.setEnabled(False)
        
        self._log(BIPRO_FETCH_ALL_START.format(count=self._all_vus_total))
        
        # Auto-Refresh pausieren (einmalig fuer gesamten Durchlauf)
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.pause_auto_refresh()
        except Exception:
            pass
        
        # Erste VU starten
        self._process_next_vu()
    
    def _process_next_vu(self):
        """Verarbeitet die naechste VU in der Queue."""
        from i18n.de import (
            BIPRO_FETCH_ALL_VU_START, BIPRO_FETCH_ALL_VU_CREDENTIALS_ERROR,
            BIPRO_FETCH_ALL_DONE, BIPRO_FETCH_ALL_IN_PROGRESS
        )
        
        # Queue leer? -> Fertig
        if not self._vu_queue:
            self._on_all_vus_finished()
            return
        
        # Naechste VU aus Queue nehmen
        conn = self._vu_queue.pop(0)
        self._all_vus_current_index += 1
        
        self._log(BIPRO_FETCH_ALL_VU_START.format(
            current=self._all_vus_current_index,
            total=self._all_vus_total,
            vu_name=conn.vu_name
        ))
        
        # Status-Update in Toolbar
        self.fetch_all_vus_btn.setText(
            BIPRO_FETCH_ALL_IN_PROGRESS.format(
                current=self._all_vus_current_index,
                total=self._all_vus_total,
                vu_name=conn.vu_name
            )
        )
        
        # Aktuelle Verbindung setzen (wie bei manueller Auswahl)
        self._current_connection = conn
        self._current_credentials = None
        self._shipments = []
        self.shipments_table.setRowCount(0)
        
        # VU in der Liste visuell auswaehlen
        for i in range(self.connections_list.count()):
            item = self.connections_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) and \
               item.data(Qt.ItemDataRole.UserRole).id == conn.id:
                self.connections_list.setCurrentItem(item)
                break
        
        # Credentials holen (ohne Fehlerdialog - wir ueberspringen bei Problemen)
        self._current_credentials = self._get_current_credentials(show_errors=False)
        if not self._current_credentials:
            self._log(BIPRO_FETCH_ALL_VU_CREDENTIALS_ERROR.format(vu_name=conn.vu_name))
            self._all_vus_stats['vus_skipped'] += 1
            # Naechste VU sofort versuchen
            QTimer.singleShot(100, self._process_next_vu)
            return
        
        # Lieferungen abrufen (FetchShipmentsWorker)
        consumer_id = conn.consumer_id or ""
        self._log(f"STS-URL: {conn.get_effective_sts_url()}")
        self._log(f"Transfer-URL: {conn.get_effective_transfer_url()}")
        
        from ui.bipro_view import FetchShipmentsWorker
        self._fetch_worker = FetchShipmentsWorker(
            self._current_credentials,
            conn.vu_name,
            sts_url=conn.get_effective_sts_url(),
            transfer_url=conn.get_effective_transfer_url(),
            consumer_id=consumer_id
        )
        self._fetch_worker.finished.connect(self._on_all_vus_shipments_loaded)
        self._fetch_worker.error.connect(self._on_all_vus_fetch_error)
        self._fetch_worker.progress.connect(self._log)
        self._register_worker(self._fetch_worker)
        self._fetch_worker.start()
    
    def _on_all_vus_shipments_loaded(self, shipments):
        """Callback wenn Lieferungen fuer eine VU im 'Alle VUs' Modus geladen wurden."""
        from i18n.de import BIPRO_FETCH_ALL_VU_NO_SHIPMENTS
        
        vu_name = self._current_connection.vu_name if self._current_connection else "?"
        self._shipments = shipments
        
        # Tabelle aktualisieren (damit User den Fortschritt sieht)
        self._update_shipments_table(shipments)
        
        if not shipments:
            self._log(BIPRO_FETCH_ALL_VU_NO_SHIPMENTS.format(vu_name=vu_name))
            self._all_vus_stats['vus_skipped'] += 1
            # Naechste VU
            QTimer.singleShot(100, self._process_next_vu)
            return
        
        self._log(f"[{vu_name}] {len(shipments)} Lieferung(en) gefunden - starte Download...")
        
        # Download starten (nutzt die bestehende _download_all Logik)
        # Aber: Credentials sind schon gesetzt, also direkt den Download-Teil ausfuehren
        self._start_download_for_current_vu()
    
    def _on_all_vus_fetch_error(self, error: str):
        """Callback bei Fetch-Fehler im 'Alle VUs' Modus."""
        vu_name = self._current_connection.vu_name if self._current_connection else "?"
        self._log(f"[{vu_name}] FEHLER beim Abrufen: {error}")
        self._all_vus_stats['vus_skipped'] += 1
        # Weiter mit naechster VU
        QTimer.singleShot(100, self._process_next_vu)
    
    def _start_download_for_current_vu(self):
        """Startet den Download fuer die aktuelle VU im 'Alle VUs' Modus."""
        if not self._shipments or not self._current_connection:
            QTimer.singleShot(100, self._process_next_vu)
            return
        
        # Konfiguration laden (VU-spezifische Worker-Anzahl)
        from config.processing_rules import get_bipro_download_config
        vu_name = self._current_connection.vu_name
        parallel_enabled = get_bipro_download_config('parallel_enabled', True)
        max_workers = get_bipro_download_config('max_parallel_workers', 5, vu_name=vu_name)
        
        # Shipment-Infos vorbereiten
        shipment_infos = [
            {
                'id': s.shipment_id,
                'category': str(s.category) if s.category else '',
                'created_at': str(s.created_at) if s.created_at else ''
            }
            for s in self._shipments
        ]
        
        self._download_total = len(shipment_infos)
        self._download_stats = {'success': 0, 'failed': 0, 'docs': 0, 'retries': 0}
        
        if parallel_enabled and len(shipment_infos) > 1:
            # Paralleler Download
            self._log(f"Starte parallelen Download von {self._download_total} Lieferung(en)...")
            
            self._progress_overlay.start_download_phase(
                self._download_total,
                max_workers=max_workers,
                parallel=True
            )
            
            self._parallel_manager = ParallelDownloadManager(
                credentials=self._current_credentials,
                vu_name=vu_name,
                shipments=shipment_infos,
                sts_url=self._current_connection.get_effective_sts_url(),
                transfer_url=self._current_connection.get_effective_transfer_url(),
                consumer_id=self._current_connection.consumer_id or "",
                max_workers=max_workers,
                parent=self
            )
            
            self._parallel_manager.progress_updated.connect(self._on_parallel_progress)
            self._parallel_manager.download_finished.connect(self._on_parallel_download_finished)
            self._parallel_manager.log_message.connect(self._log)
            self._parallel_manager.all_finished.connect(self._on_all_vus_vu_download_complete)
            self._parallel_manager.error.connect(self._on_all_vus_download_error)
            
            self._register_worker(self._parallel_manager)
            self._parallel_manager.start()
        else:
            # Sequentieller Download
            self._log(f"Starte sequentiellen Download von {self._download_total} Lieferung(en)...")
            
            self._download_queue = shipment_infos.copy()
            
            self._progress_overlay.start_download_phase(self._download_total)
            self._process_download_queue()
    
    def _on_all_vus_vu_download_complete(self, stats: dict):
        """Callback wenn alle Downloads einer VU im 'Alle VUs' Modus fertig sind."""
        from i18n.de import BIPRO_FETCH_ALL_VU_DONE
        
        vu_name = self._current_connection.vu_name if self._current_connection else "?"
        
        success = stats.get('success', 0)
        docs = stats.get('docs', 0)
        
        self._all_vus_stats['vus_processed'] += 1
        self._all_vus_stats['total_shipments'] += success
        self._all_vus_stats['total_docs'] += docs
        
        self._log(BIPRO_FETCH_ALL_VU_DONE.format(
            vu_name=vu_name, success=success, docs=docs
        ))
        
        # Statistiken ans Overlay uebergeben
        self._progress_overlay._stats['download_success'] = stats.get('success', 0)
        self._progress_overlay._stats['download_failed'] = stats.get('failed', 0)
        self._progress_overlay._stats['download_docs'] = stats.get('docs', 0)
        
        # Aufräumen
        self._parallel_manager = None
        self._current_credentials = None
        
        # Naechste VU (kurze Pause fuer UI-Updates)
        QTimer.singleShot(200, self._process_next_vu)
    
    def _on_all_vus_download_error(self, error: str):
        """Callback bei Download-Fehler im 'Alle VUs' Modus."""
        vu_name = self._current_connection.vu_name if self._current_connection else "?"
        self._log(f"[{vu_name}] Download-Fehler: {error}")
        self._all_vus_stats['vus_processed'] += 1
        self._parallel_manager = None
        self._current_credentials = None
        # Weiter mit naechster VU
        QTimer.singleShot(200, self._process_next_vu)
    
    def _on_all_vus_finished(self):
        """Wird aufgerufen wenn alle VUs abgearbeitet sind."""
        from i18n.de import BIPRO_FETCH_ALL, BIPRO_FETCH_ALL_DONE
        
        # Auto-Refresh wieder aktivieren
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.resume_auto_refresh()
        except Exception:
            pass
        
        stats = self._all_vus_stats
        self._log(BIPRO_FETCH_ALL_DONE.format(
            total_vus=stats['vus_processed'],
            total_shipments=stats['total_shipments'],
            total_docs=stats['total_docs']
        ))
        
        if stats['vus_skipped'] > 0:
            self._log(f"  Uebersprungen: {stats['vus_skipped']} VU(s)")
        
        # UI entsperren
        self._all_vus_mode = False
        self.fetch_all_vus_btn.setEnabled(True)
        self.fetch_all_vus_btn.setText(BIPRO_FETCH_ALL)
        
        # Fazit im Overlay anzeigen
        self._progress_overlay._stats['download_success'] = stats['total_shipments']
        self._progress_overlay._stats['download_docs'] = stats['total_docs']
        self._progress_overlay.show_completion(auto_close_seconds=10)
        
        # Signal fuer Archiv-Refresh
        self.documents_uploaded.emit()
    
    def _update_shipments_table(self, shipments):
        """Aktualisiert die Lieferungstabelle (fuer Alle-VUs-Modus wiederverwendbar)."""
        self.shipments_table.setRowCount(len(shipments))
        
        for row, ship in enumerate(shipments):
            self.shipments_table.setItem(row, 0, QTableWidgetItem(ship.shipment_id))
            
            # Datum
            created = str(ship.created_at) if ship.created_at else ""
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    created = dt.strftime('%d.%m.%Y %H:%M')
                except (ValueError, AttributeError):
                    pass
            self.shipments_table.setItem(row, 1, QTableWidgetItem(created))
            
            # Kategorie
            cat_code = str(ship.category) if ship.category else ""
            cat_name = get_category_name(cat_code) if cat_code else ""
            cat_icon = get_category_icon(cat_code) if cat_code else ""
            self.shipments_table.setItem(row, 2, QTableWidgetItem(f"{cat_icon} {cat_name}"))
            
            # Verfuegbar bis
            valid_until = str(ship.valid_until) if hasattr(ship, 'valid_until') and ship.valid_until else ""
            if valid_until:
                try:
                    dt = datetime.fromisoformat(valid_until.replace('Z', '+00:00'))
                    valid_until = dt.strftime('%d.%m.%Y %H:%M')
                except (ValueError, AttributeError):
                    pass
            self.shipments_table.setItem(row, 3, QTableWidgetItem(valid_until))
            
            # Transfers
            transfers = str(ship.transfer_count) if hasattr(ship, 'transfer_count') and ship.transfer_count else ""
            self.shipments_table.setItem(row, 4, QTableWidgetItem(transfers))
    
    # ========================================
    # Mail-Import (IMAP -> Eingangsbox)
    # ========================================
    
    def _fetch_mails(self):
        """Mails vom IMAP-Postfach abholen und Anhaenge importieren."""
        from i18n import de as texts
        from api.smartscan import SmartScanAPI, EmailAccountsAPI
        
        if self._mail_import_worker is not None:
            self._toast_manager.show_info(texts.BIPRO_MAIL_FETCH_RUNNING)
            return
        
        # IMAP-Konto ermitteln (aus SmartScan-Settings oder erstes aktives IMAP-Konto)
        account_id = None
        try:
            smartscan_api = SmartScanAPI(self.api_client)
            settings = smartscan_api.get_settings()
            if settings:
                poll_id = settings.get('imap_poll_account_id')
                if poll_id:
                    account_id = int(poll_id)
        except Exception as e:
            logger.warning(f"SmartScan-Settings konnten nicht geladen werden: {e}")
        
        # Fallback: Erstes aktives IMAP-Konto suchen
        if not account_id:
            try:
                email_api = EmailAccountsAPI(self.api_client)
                accounts = email_api.get_accounts()
                for acc in accounts:
                    imap_host = acc.get('imap_host', '')
                    is_active = bool(int(acc.get('is_active', 0) or 0))
                    if imap_host and is_active:
                        account_id = int(acc['id'])
                        break
            except Exception as e:
                logger.warning(f"E-Mail-Konten konnten nicht geladen werden: {e}")
        
        if not account_id:
            self._toast_manager.show_error(texts.BIPRO_MAIL_FETCH_NO_ACCOUNT)
            return
        
        # Button deaktivieren (Toast wird via phase_changed erstellt)
        self.mail_fetch_btn.setEnabled(False)
        self._log(texts.BIPRO_MAIL_FETCH_RUNNING)
        self._mail_progress_toast = None
        
        # Worker starten
        self._mail_import_worker = MailImportWorker(self.api_client, account_id)
        self._mail_import_worker.progress.connect(self._on_mail_import_progress)
        self._mail_import_worker.progress_count.connect(self._on_mail_import_progress_count)
        self._mail_import_worker.phase_changed.connect(self._on_mail_phase_changed)
        self._mail_import_worker.completed.connect(self._on_mail_import_completed)
        self._mail_import_worker.error.connect(self._on_mail_import_error)
        # Cleanup nach Thread-Ende
        self._mail_import_worker.finished.connect(self._cleanup_mail_import_worker)
        self._active_workers.append(self._mail_import_worker)
        self._mail_import_worker.start()
    
    def _on_mail_phase_changed(self, title: str, total: int):
        """Neue Phase im Mail-Import - alten Toast schliessen, neuen oeffnen."""
        # Alten Toast schliessen falls vorhanden
        old_toast = getattr(self, '_mail_progress_toast', None)
        if old_toast:
            old_toast.dismiss()
        
        # Neuen Progress-Toast erstellen
        self._mail_progress_toast = self._toast_manager.show_progress(title)
        if total > 0:
            self._mail_progress_toast.set_progress(0, total)
    
    def _on_mail_import_progress(self, message: str):
        """Fortschritt des Mail-Imports loggen + Toast aktualisieren."""
        self._log(message)
        toast = getattr(self, '_mail_progress_toast', None)
        if toast:
            toast.set_status(message)
    
    def _on_mail_import_progress_count(self, current: int, total: int):
        """Fortschrittsbalken im Toast aktualisieren."""
        toast = getattr(self, '_mail_progress_toast', None)
        if toast:
            toast.set_progress(current, total)
    
    def _on_mail_import_completed(self, stats: dict):
        """Mail-Import abgeschlossen."""
        from i18n import de as texts
        
        self.mail_fetch_btn.setEnabled(True)
        
        # Progress-Toast schliessen
        toast = getattr(self, '_mail_progress_toast', None)
        if toast:
            toast.dismiss()
            self._mail_progress_toast = None
        
        new_mails = stats.get('new_mails', 0)
        imported = stats.get('imported', 0)
        failed = stats.get('failed', 0)
        
        if imported > 0 or new_mails > 0:
            msg = texts.BIPRO_MAIL_FETCH_SUCCESS.format(
                new_mails=new_mails, imported=imported
            )
            if failed > 0:
                msg += f" ({failed} fehlgeschlagen)"
            self._toast_manager.show_success(msg)
            self._log(msg)
            # Archiv-Refresh ausloesen
            self.documents_uploaded.emit()
        else:
            self._toast_manager.show_info(texts.BIPRO_MAIL_FETCH_NO_NEW)
            self._log(texts.BIPRO_MAIL_FETCH_NO_NEW)
        
        # Fehler loggen
        for err in stats.get('errors', []):
            self._log(f"  Fehler: {err}")
    
    def _on_mail_import_error(self, error: str):
        """Fehler beim Mail-Import."""
        from i18n import de as texts
        
        self.mail_fetch_btn.setEnabled(True)
        
        # Progress-Toast schliessen
        toast = getattr(self, '_mail_progress_toast', None)
        if toast:
            toast.dismiss()
            self._mail_progress_toast = None
        
        msg = texts.BIPRO_MAIL_FETCH_ERROR.format(error=error)
        self._toast_manager.show_error(msg)
        self._log(msg)
    
    def _cleanup_mail_import_worker(self):
        """Raeume den MailImportWorker auf nach Thread-Ende."""
        worker = self._mail_import_worker
        self._mail_import_worker = None
        if worker:
            if worker in self._active_workers:
                self._active_workers.remove(worker)
            worker.deleteLater()
    
    # ========================================
    # Einzelne VU - Lieferungen abrufen
    # ========================================
    
    def _fetch_shipments(self):
        """Lieferungen abrufen."""
        if not self._current_connection:
            return
        
        # Credentials holen (unterstuetzt Username/Password UND Zertifikats-Auth)
        self._current_credentials = self._get_current_credentials()
        if not self._current_credentials:
            return  # Fehlermeldung wird von _get_current_credentials() angezeigt
        
        # Alten Worker stoppen falls noch laufend
        if self._fetch_worker and self._fetch_worker.isRunning():
            logger.debug("Stoppe vorherigen Fetch-Worker")
            self._fetch_worker.quit()
            self._fetch_worker.wait(500)  # Kurz warten
        
        # Worker starten
        
        # Debug: Consumer-ID loggen
        consumer_id = self._current_connection.consumer_id or ""
        self._log(f"Consumer-ID aus Verbindung: '{consumer_id}'")
        import logging
        logging.getLogger(__name__).info(f"Consumer-ID aus Verbindung: '{consumer_id}'")
        self._log(f"STS-URL: {self._current_connection.get_effective_sts_url()}")
        self._log(f"Transfer-URL: {self._current_connection.get_effective_transfer_url()}")
        
        self._fetch_worker = FetchShipmentsWorker(
            self._current_credentials,
            self._current_connection.vu_name,
            sts_url=self._current_connection.get_effective_sts_url(),
            transfer_url=self._current_connection.get_effective_transfer_url(),
            consumer_id=consumer_id
        )
        self._fetch_worker.finished.connect(self._on_shipments_loaded)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.progress.connect(self._log)
        self._register_worker(self._fetch_worker)
        self._fetch_worker.start()
    
    def _on_shipments_loaded(self, shipments):
        """Callback wenn Lieferungen geladen."""
        self._shipments = shipments
        
        self.shipments_table.setRowCount(len(shipments))
        
        for row, ship in enumerate(shipments):
            self.shipments_table.setItem(row, 0, QTableWidgetItem(ship.shipment_id))
            
            # Eingestellt-Datum im deutschen Format
            eingestellt_item = QTableWidgetItem(format_datetime_german(ship.created_at))
            eingestellt_item.setToolTip(ship.created_at or "")  # Original als Tooltip
            self.shipments_table.setItem(row, 1, eingestellt_item)
            
            # Kategorie mit Icon und lesbarem Namen
            category_code = ship.category or ""
            icon = get_category_icon(category_code)
            category_name = get_category_short_name(category_code)
            category_item = QTableWidgetItem(f"{icon} {category_name}")
            category_item.setToolTip(f"{get_category_name(category_code)}\nCode: {category_code}")
            self.shipments_table.setItem(row, 2, category_item)
            
            # Verfügbar bis im deutschen Format
            verfuegbar_item = QTableWidgetItem(format_date_german(ship.available_until))
            verfuegbar_item.setToolTip(ship.available_until or "")
            self.shipments_table.setItem(row, 3, verfuegbar_item)
            
            self.shipments_table.setItem(row, 4, QTableWidgetItem(str(ship.transfer_count)))
        
        self.download_btn.setEnabled(len(shipments) > 0)
        self.download_all_btn.setEnabled(len(shipments) > 0)
        self.acknowledge_btn.setEnabled(len(shipments) > 0)
        self._log(f"{len(shipments)} Lieferung(en) gefunden")
        
        # Credentials aus dem Speicher löschen
        self._current_credentials = None
    
    def _on_fetch_error(self, error: str):
        """Callback bei Fehler."""
        self._current_credentials = None
        self._log(f"FEHLER: {error}")
        self._toast_manager.show_error(f"Abruf fehlgeschlagen:\n{error}")
    
    def _download_selected(self):
        """Ausgewählte Lieferung herunterladen."""
        selected = self.shipments_table.selectedItems()
        if not selected:
            self._toast_manager.show_info("Bitte eine Lieferung auswählen.")
            return
        
        row = selected[0].row()
        if row >= len(self._shipments):
            return
        
        shipment = self._shipments[row]
        
        # Credentials holen (unterstuetzt Username/Password UND Zertifikats-Auth)
        self._current_credentials = self._get_current_credentials()
        if not self._current_credentials:
            return  # Fehlermeldung wird von _get_current_credentials() angezeigt
        
        # Alten Worker stoppen falls noch laufend
        if self._download_worker and self._download_worker.isRunning():
            logger.debug("Stoppe vorherigen Download-Worker")
            self._download_worker.quit()
            self._download_worker.wait(500)
        
        self.download_btn.setEnabled(False)
        self.download_all_btn.setEnabled(False)
        
        # Kategorie speichern fuer Upload (wird in _on_download_finished benoetigt)
        self._current_shipment_category = shipment.category or ""
        
        self._download_worker = DownloadShipmentWorker(
            self._current_credentials,
            self._current_connection.vu_name,
            shipment.shipment_id,
            sts_url=self._current_connection.get_effective_sts_url(),
            transfer_url=self._current_connection.get_effective_transfer_url(),
            category=shipment.category or "",
            created_at=shipment.created_at or "",
            consumer_id=self._current_connection.consumer_id or ""
        )
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.progress.connect(self._log)
        self._register_worker(self._download_worker)
        self._download_worker.start()
    
    def _download_all(self):
        """Alle Lieferungen herunterladen (parallel oder sequentiell)."""
        if not self._shipments:
            self._toast_manager.show_info("Keine Lieferungen vorhanden.")
            return
        
        if not self._current_connection:
            self._toast_manager.show_warning("Keine VU-Verbindung ausgewählt.")
            return
        
        # Credentials holen (unterstuetzt Username/Password UND Zertifikats-Auth)
        self._current_credentials = self._get_current_credentials()
        if not self._current_credentials:
            return  # Fehlermeldung wird von _get_current_credentials() angezeigt
        
        # Konfiguration laden (VU-spezifische Worker-Anzahl)
        from config.processing_rules import get_bipro_download_config
        vu_name = self._current_connection.vu_name
        parallel_enabled = get_bipro_download_config('parallel_enabled', True)
        max_workers = get_bipro_download_config('max_parallel_workers', 5, vu_name=vu_name)
        
        # Shipment-Infos für Download vorbereiten
        shipment_infos = [
            {
                'id': s.shipment_id, 
                'category': str(s.category) if s.category else '', 
                'created_at': str(s.created_at) if s.created_at else ''
            }
            for s in self._shipments
        ]
        
        self._download_total = len(shipment_infos)
        self._download_stats = {'success': 0, 'failed': 0, 'docs': 0, 'retries': 0}
        
        # Auto-Refresh pausieren während des Downloads
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.pause_auto_refresh()
            logger.info("Auto-Refresh für BiPRO-Download pausiert")
        except Exception as e:
            logger.warning(f"Auto-Refresh pausieren fehlgeschlagen: {e}")
        
        self.download_btn.setEnabled(False)
        self.download_all_btn.setEnabled(False)
        
        if parallel_enabled and len(shipment_infos) > 1:
            # ===== PARALLELER DOWNLOAD =====
            self._log(f"Starte parallelen Download von {self._download_total} Lieferung(en) mit {max_workers} Workern...")
            
            # Progress-Overlay starten (parallel-Modus)
            self._progress_overlay.start_download_phase(
                self._download_total, 
                max_workers=max_workers, 
                parallel=True
            )
            
            # ParallelDownloadManager erstellen
            self._parallel_manager = ParallelDownloadManager(
                credentials=self._current_credentials,
                vu_name=self._current_connection.vu_name,
                shipments=shipment_infos,
                sts_url=self._current_connection.get_effective_sts_url(),
                transfer_url=self._current_connection.get_effective_transfer_url(),
                consumer_id=self._current_connection.consumer_id or "",
                max_workers=max_workers,
                parent=self
            )
            
            # Signale verbinden
            self._parallel_manager.progress_updated.connect(self._on_parallel_progress)
            self._parallel_manager.download_finished.connect(self._on_parallel_download_finished)
            self._parallel_manager.log_message.connect(self._log)
            self._parallel_manager.all_finished.connect(self._on_parallel_all_finished)
            self._parallel_manager.error.connect(self._on_parallel_error)
            
            # Worker registrieren und starten
            self._register_worker(self._parallel_manager)
            self._parallel_manager.start()
        else:
            # ===== SEQUENTIELLER DOWNLOAD (altes Verhalten) =====
            self._log(f"Starte sequentiellen Download von {self._download_total} Lieferung(en)...")
            
            self._download_queue = shipment_infos.copy()
            
            # Progress-Overlay starten (sequentieller Modus)
            self._progress_overlay.start_download_phase(self._download_total)
            
            self._process_download_queue()
    
    # =========================================================================
    # PARALLEL DOWNLOAD CALLBACKS
    # =========================================================================
    
    def _on_parallel_progress(self, current: int, total: int, docs_count: int, 
                               failed_count: int, active_workers: int):
        """Callback für parallelen Download-Fortschritt."""
        self._progress_overlay.update_parallel_progress(
            current, total, docs_count, failed_count, active_workers
        )
    
    def _on_parallel_download_finished(self, shipment_id: str, documents: list, 
                                        raw_xml_path: str, category: str):
        """Callback wenn eine Lieferung parallel heruntergeladen wurde."""
        # Ins Archiv hochladen (laeuft im Haupt-Thread fuer Thread-Sicherheit)
        vu_name = self._current_connection.vu_name if self._current_connection else None
        upload_failed = 0
        problem_pdfs = 0
        
        for doc in documents:
            try:
                # Bestimme Box und Validierungsstatus
                validation_status = doc.get('validation_status')
                is_valid = doc.get('is_valid', True)
                
                # Bei PDF-Problemen: In Sonstige-Box mit Reason-Code
                if not is_valid and validation_status:
                    problem_pdfs += 1
                    self._log(f"    [PDF-PROBLEM] {doc.get('filename', 'unbekannt')}: {validation_status}")
                    
                    self.docs_api.upload(
                        file_path=doc['filepath'],
                        source_type='bipro_auto',
                        shipment_id=shipment_id,
                        vu_name=vu_name,
                        bipro_category=category,
                        validation_status=validation_status,
                        box_type='sonstige'  # Problematische PDFs direkt in Sonstige-Box
                    )
                else:
                    # Normale Dokumente in Eingangsbox
                    self.docs_api.upload(
                        file_path=doc['filepath'],
                        source_type='bipro_auto',
                        shipment_id=shipment_id,
                        vu_name=vu_name,
                        bipro_category=category,
                        validation_status=validation_status if validation_status else 'OK'
                    )
            except Exception as e:
                upload_failed += 1
                self._log(f"    [!] Upload fehlgeschlagen: {doc.get('filename', 'unbekannt')}: {e}")
        
        if problem_pdfs > 0:
            self._log(f"    [INFO] {problem_pdfs} problematische PDF(s) in Sonstige-Box")
        
        # Raw XML hochladen (direkt ins Roh-Archiv)
        try:
            self.docs_api.upload(
                file_path=raw_xml_path,
                source_type='bipro_auto',
                shipment_id=shipment_id,
                vu_name=vu_name,
                box_type='roh'  # XML Rohdateien direkt ins Roh-Archiv
            )
        except Exception as e:
            self._log(f"    [!] Raw XML Upload fehlgeschlagen: {e}")
    
    def _on_parallel_all_finished(self, stats: dict):
        """Callback wenn alle parallelen Downloads fertig sind."""
        
        # Im "Alle VUs" Modus: An die VU-spezifische Callback weiterleiten
        if self._all_vus_mode:
            self._on_all_vus_vu_download_complete(stats)
            return
        
        # Auto-Refresh wieder aktivieren
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.resume_auto_refresh()
            logger.info("Auto-Refresh nach BiPRO-Download fortgesetzt")
        except Exception as e:
            logger.warning(f"Auto-Refresh fortsetzen fehlgeschlagen: {e}")
        
        self.download_btn.setEnabled(True)
        self.download_all_btn.setEnabled(True)
        self.acknowledge_btn.setEnabled(True)
        self._current_credentials = None
        
        # Statistiken loggen
        self._log(f"=== Alle Downloads abgeschlossen ===")
        self._log(
            f"Erfolgreich: {stats.get('success', 0)}, "
            f"Fehlgeschlagen: {stats.get('failed', 0)}, "
            f"Dokumente: {stats.get('docs', 0)}, "
            f"Retries: {stats.get('retries', 0)}"
        )
        
        # Fehlgeschlagene Lieferungen loggen
        failed_ids = stats.get('failed_ids', [])
        if failed_ids:
            self._log(f"  Fehlgeschlagene Lieferungen: {', '.join(failed_ids[:5])}" + 
                     (f" (+{len(failed_ids)-5} weitere)" if len(failed_ids) > 5 else ""))
        
        # Statistiken ans Overlay übergeben
        self._progress_overlay._stats['download_success'] = stats.get('success', 0)
        self._progress_overlay._stats['download_failed'] = stats.get('failed', 0)
        self._progress_overlay._stats['download_docs'] = stats.get('docs', 0)
        self._progress_overlay._stats['download_retries'] = stats.get('retries', 0)
        
        # Fazit anzeigen
        self._progress_overlay.show_completion(auto_close_seconds=8)
        
        # Manager aufräumen
        self._parallel_manager = None
    
    def _on_parallel_error(self, error: str):
        """Callback bei Fehler im parallelen Download."""
        
        # Im "Alle VUs" Modus: Fehler loggen und weiter
        if self._all_vus_mode:
            self._on_all_vus_download_error(error)
            return
        
        # Auto-Refresh wieder aktivieren
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.resume_auto_refresh()
            logger.info("Auto-Refresh nach BiPRO-Fehler fortgesetzt")
        except Exception as e:
            logger.warning(f"Auto-Refresh fortsetzen fehlgeschlagen: {e}")
        
        self._log(f"FEHLER: {error}")
        self.download_btn.setEnabled(True)
        self.download_all_btn.setEnabled(True)
        self._current_credentials = None
        self._parallel_manager = None
        
        # Overlay schließen
        self._progress_overlay.setVisible(False)
        
        self._toast_manager.show_error(f"Paralleler Download fehlgeschlagen:\n{error}")
    
    # =========================================================================
    # SEQUENTIELLER DOWNLOAD (Legacy)
    # =========================================================================
    
    def _process_download_queue(self):
        """Verarbeitet die nächste Lieferung in der Queue."""
        if not self._download_queue:
            # Fertig!
            self._on_all_downloads_finished()
            return
        
        shipment_info = self._download_queue.pop(0)
        shipment_id = shipment_info['id']
        remaining = len(self._download_queue)
        self._log(f"Lade Lieferung {shipment_id}... (noch {remaining} übrig)")
        
        # Kategorie speichern fuer Upload (wird in _on_queue_download_finished benoetigt)
        self._current_shipment_category = shipment_info.get('category', '')
        
        self._download_worker = DownloadShipmentWorker(
            self._current_credentials,
            self._current_connection.vu_name,
            shipment_id,
            sts_url=self._current_connection.get_effective_sts_url(),
            transfer_url=self._current_connection.get_effective_transfer_url(),
            category=shipment_info['category'],
            created_at=shipment_info['created_at'],
            consumer_id=self._current_connection.consumer_id or ""
        )
        self._download_worker.finished.connect(self._on_queue_download_finished)
        self._download_worker.error.connect(self._on_queue_download_error)
        self._download_worker.progress.connect(self._log)
        self._register_worker(self._download_worker)
        self._download_worker.start()
    
    def _on_queue_download_finished(self, shipment_id: str, documents: list, raw_xml_path: str):
        """Callback für Queue-Download."""
        self._download_stats['success'] += 1
        self._download_stats['docs'] += len(documents)
        
        # Fortschritt aktualisieren (vor Upload, damit User sieht dass Download fertig ist)
        current_progress = self._download_total - len(self._download_queue)
        self._progress_overlay.update_download_progress(
            current=current_progress,
            docs_count=len(documents),
            success=True
        )
        
        # Ins Archiv hochladen
        vu_name = self._current_connection.vu_name if self._current_connection else None
        # BiPRO-Kategorie fuer regelbasierte Sortierung (z.B. "300001000" = Provision -> Courtage)
        bipro_category = getattr(self, '_current_shipment_category', '')
        upload_failed = 0
        
        problem_pdfs = 0
        for doc in documents:
            try:
                # Bestimme Validierungsstatus
                validation_status = doc.get('validation_status')
                is_valid = doc.get('is_valid', True)
                
                # Bei PDF-Problemen: In Sonstige-Box mit Reason-Code
                if not is_valid and validation_status:
                    problem_pdfs += 1
                    self._log(f"    [PDF-PROBLEM] {doc.get('filename', 'unbekannt')}: {validation_status}")
                    
                    self.docs_api.upload(
                        file_path=doc['filepath'],
                        source_type='bipro_auto',
                        shipment_id=shipment_id,
                        vu_name=vu_name,
                        bipro_category=bipro_category,
                        validation_status=validation_status,
                        box_type='sonstige'
                    )
                else:
                    self.docs_api.upload(
                        file_path=doc['filepath'],
                        source_type='bipro_auto',
                        shipment_id=shipment_id,
                        vu_name=vu_name,
                        bipro_category=bipro_category,
                        validation_status=validation_status if validation_status else 'OK'
                    )
            except Exception as e:
                upload_failed += 1
                self._log(f"    [!] Upload fehlgeschlagen: {doc.get('filename', 'unbekannt')}: {e}")
        
        # Raw XML hochladen (ohne Kategorie, da Rohdatei)
        try:
            self.docs_api.upload(
                file_path=raw_xml_path,
                source_type='bipro_auto',
                shipment_id=shipment_id,
                vu_name=vu_name,
                box_type='roh'  # XML Rohdateien direkt ins Roh-Archiv
            )
        except Exception as e:
            self._log(f"    [!] Raw XML Upload fehlgeschlagen: {e}")
        
        # Status-Meldung mit Upload-Info
        if upload_failed > 0 or problem_pdfs > 0:
            self._log(f"  [!] Lieferung {shipment_id}: {len(documents)} Dokument(e), {upload_failed} Upload(s) fehlgeschlagen, {problem_pdfs} PDF-Problem(e)")
        else:
            self._log(f"  [OK] Lieferung {shipment_id}: {len(documents)} Dokument(e)")
        
        # Nächste Lieferung
        self._process_download_queue()
    
    def _on_queue_download_error(self, error: str):
        """Callback für Queue-Download Fehler."""
        self._download_stats['failed'] += 1
        self._log(f"  [!] Fehler: {error[:100]}")
        
        # Fortschritt aktualisieren (auch bei Fehler)
        current_progress = self._download_total - len(self._download_queue)
        self._progress_overlay.update_download_progress(
            current=current_progress,
            docs_count=0,
            success=False
        )
        
        # Trotzdem weitermachen mit nächster Lieferung
        self._process_download_queue()
    
    def _on_all_downloads_finished(self):
        """Callback wenn alle Downloads fertig."""
        
        # Im "Alle VUs" Modus: An die VU-spezifische Callback weiterleiten
        if self._all_vus_mode:
            stats = self._download_stats
            self._on_all_vus_vu_download_complete(stats)
            return
        
        # Auto-Refresh wieder aktivieren
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.resume_auto_refresh()
            logger.info("Auto-Refresh nach sequentiellem Download fortgesetzt")
        except Exception as e:
            logger.warning(f"Auto-Refresh fortsetzen fehlgeschlagen: {e}")
        
        self.download_btn.setEnabled(True)
        self.download_all_btn.setEnabled(True)
        self.acknowledge_btn.setEnabled(True)
        self._current_credentials = None
        
        stats = self._download_stats
        self._log(f"=== Alle Downloads abgeschlossen ===")
        self._log(f"Erfolgreich: {stats['success']}, Fehlgeschlagen: {stats['failed']}, Dokumente: {stats['docs']}")
        
        # Statistiken ans Overlay uebergeben
        self._progress_overlay._stats['download_success'] = stats['success']
        self._progress_overlay._stats['download_failed'] = stats['failed']
        self._progress_overlay._stats['download_docs'] = stats['docs']
        
        # Fazit anzeigen (kein Popup mehr!)
        # Auto-Close nach 8 Sekunden, oder Klick zum Schließen
        self._progress_overlay.show_completion(auto_close_seconds=8)
    
    def _on_download_finished(self, shipment_id: str, documents: list, raw_xml_path: str):
        """Callback wenn einzelner Download fertig."""
        self.download_btn.setEnabled(True)
        self.download_all_btn.setEnabled(True)
        self.acknowledge_btn.setEnabled(True)
        self._current_credentials = None
        
        self._log(f"Lieferung {shipment_id}: {len(documents)} Dokument(e) heruntergeladen")
        
        # ===== AUTOMATISCH INS DOKUMENTENARCHIV HOCHLADEN =====
        uploaded = 0
        failed = 0
        
        # VU-Name für Metadaten
        vu_name = self._current_connection.vu_name if self._current_connection else None
        # BiPRO-Kategorie fuer regelbasierte Sortierung
        bipro_category = getattr(self, '_current_shipment_category', '')
        
        # 1. Alle Dokumente hochladen
        problem_pdfs = 0
        for doc in documents:
            try:
                # Bestimme Validierungsstatus
                validation_status = doc.get('validation_status')
                is_valid = doc.get('is_valid', True)
                
                # Bei PDF-Problemen: In Sonstige-Box mit Reason-Code
                if not is_valid and validation_status:
                    problem_pdfs += 1
                    result = self.docs_api.upload(
                        file_path=doc['filepath'],
                        source_type='bipro_auto',
                        shipment_id=shipment_id,
                        vu_name=vu_name,
                        bipro_category=bipro_category,
                        validation_status=validation_status,
                        box_type='sonstige'
                    )
                    if result:
                        uploaded += 1
                        self._log(f"  [PDF-PROBLEM] {doc['filename']} -> Sonstige ({validation_status})")
                else:
                    result = self.docs_api.upload(
                        file_path=doc['filepath'],
                        source_type='bipro_auto',
                        shipment_id=shipment_id,
                        vu_name=vu_name,
                        bipro_category=bipro_category,
                        validation_status=validation_status if validation_status else 'OK'
                    )
                    if result:
                        uploaded += 1
                        self._log(f"  [OK] {doc['filename']} -> Archiv (BiPRO: {vu_name}, Kat: {bipro_category})")
                    else:
                        failed += 1
                        self._log(f"  [!] {doc['filename']} Upload fehlgeschlagen")
            except Exception as e:
                failed += 1
                self._log(f"  [!] {doc['filename']}: {e}")
        
        # 2. Raw XML auch hochladen (direkt ins Roh-Archiv)
        try:
            result = self.docs_api.upload(
                file_path=raw_xml_path,
                source_type='bipro_auto',
                shipment_id=shipment_id,
                vu_name=vu_name,
                box_type='roh'  # XML Rohdateien direkt ins Roh-Archiv
            )
            if result:
                uploaded += 1
                self._log(f"  [OK] Raw XML -> Roh-Archiv (BiPRO: {vu_name})")
        except Exception as e:
            self._log(f"  [!] Raw XML Upload: {e}")
        
        # Signal für Archiv-Aktualisierung
        if uploaded > 0:
            self.documents_uploaded.emit()
        
        # ===== ZUSAMMENFASSUNG =====
        self._log(f"Archiv-Upload: {uploaded} erfolgreich, {failed} fehlgeschlagen")
        
        # Detaillierte Info-Box
        doc_list = "\n".join([f"  - {d['filename']} ({d['size']:,} Bytes)" for d in documents])
        if not doc_list:
            doc_list = "  (Keine Dokumente in der Lieferung)"
        
        # Status-Meldung
        if failed > 0:
            self._toast_manager.show_warning(
                f"Lieferung {shipment_id}: {uploaded} erfolgreich, {failed} fehlgeschlagen.\n"
                f"Bitte Protokoll prüfen!"
            )
        else:
            self._toast_manager.show_success(
                f"Lieferung {shipment_id}: Alle {uploaded} Datei(en) ins Dokumentenarchiv übertragen."
            )
    
    def _on_download_error(self, error: str):
        """Callback bei Download-Fehler."""
        self.download_btn.setEnabled(True)
        self.download_all_btn.setEnabled(True)
        self.acknowledge_btn.setEnabled(True)
        self._current_credentials = None
        self._log(f"DOWNLOAD-FEHLER: {error}")
        self._toast_manager.show_error(f"Download fehlgeschlagen:\n{error}")
    
    # =========================================================================
    # QUITTIERUNG
    # =========================================================================
    
    def _acknowledge_selected(self):
        """Quittiert die ausgewaehlten Lieferungen."""
        selected_rows = self.shipments_table.selectionModel().selectedRows()
        
        if not selected_rows:
            self._toast_manager.show_info("Bitte waehlen Sie Lieferungen zum Quittieren aus.")
            return
        
        # IDs sammeln
        shipment_ids = []
        for index in selected_rows:
            row = index.row()
            id_item = self.shipments_table.item(row, 0)
            if id_item:
                shipment_ids.append(id_item.text())
        
        if not shipment_ids:
            return
        
        # Warnung anzeigen
        reply = QMessageBox.warning(
            self,
            "Lieferungen quittieren",
            f"ACHTUNG: Sie sind dabei, {len(shipment_ids)} Lieferung(en) zu quittieren.\n\n"
            "Quittierte Lieferungen werden vom Versicherer-Server GELOESCHT\n"
            "und koennen NICHT erneut abgerufen werden!\n\n"
            "Haben Sie alle Dokumente heruntergeladen und gesichert?\n\n"
            "Moechten Sie fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Credentials holen
        if not self._current_connection:
            return
        
        self._log(f"Quittiere {len(shipment_ids)} Lieferung(en)...")
        
        # Credentials je nach Auth-Typ laden
        if self._current_connection.auth_type == 'certificate':
            cert_config = self._load_certificate_config(self._current_connection.id)
            if not cert_config:
                self._toast_manager.show_error("Zertifikat-Konfiguration nicht gefunden.")
                return
            
            cert_format = cert_config.get('cert_format', 'pfx')
            if cert_format == 'jks':
                self._current_credentials = VUCredentials(
                    username="",
                    password="",
                    jks_path=cert_config.get('jks_path', ''),
                    jks_password=cert_config.get('jks_password', ''),
                    jks_alias=cert_config.get('jks_alias', ''),
                    jks_key_password=cert_config.get('jks_key_password', '')
                )
            else:
                self._current_credentials = VUCredentials(
                    username="",
                    password="",
                    pfx_path=cert_config.get('pfx_path', ''),
                    pfx_password=cert_config.get('pfx_password', '')
                )
        else:
            try:
                self._current_credentials = self.vu_api.get_credentials(self._current_connection.id)
            except Exception as e:
                self._log(f"FEHLER: {e}")
                self._toast_manager.show_error(f"Zugangsdaten nicht verfuegbar:\n{e}")
                return
            
            if not self._current_credentials:
                self._toast_manager.show_error("Keine Zugangsdaten verfuegbar.")
                return
        
        # Buttons deaktivieren
        self.acknowledge_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.download_all_btn.setEnabled(False)
        
        # Worker starten
        self._acknowledge_worker = AcknowledgeShipmentWorker(
            self._current_credentials,
            shipment_ids,
            sts_url=self._current_connection.get_effective_sts_url(),
            transfer_url=self._current_connection.get_effective_transfer_url(),
            consumer_id=self._current_connection.consumer_id or ""
        )
        self._acknowledge_worker.progress.connect(self._log)
        self._acknowledge_worker.finished.connect(self._on_acknowledge_finished)
        self._register_worker(self._acknowledge_worker)
        self._acknowledge_worker.start()
    
    def _on_acknowledge_finished(self, successful: list, failed: list):
        """Callback wenn Quittierung abgeschlossen."""
        self.acknowledge_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.download_all_btn.setEnabled(True)
        self._current_credentials = None
        
        self._log(f"=== Quittierung abgeschlossen ===")
        self._log(f"Erfolgreich: {len(successful)}")
        self._log(f"Fehlgeschlagen: {len(failed)}")
        
        if successful:
            # Erfolgreiche aus Tabelle entfernen
            for shipment_id in successful:
                for row in range(self.shipments_table.rowCount()):
                    item = self.shipments_table.item(row, 0)
                    if item and item.text() == shipment_id:
                        self.shipments_table.removeRow(row)
                        # Auch aus _shipments Liste entfernen
                        self._shipments = [s for s in self._shipments if s.shipment_id != shipment_id]
                        break
            
            if failed:
                self._toast_manager.show_warning(
                    f"{len(successful)} Lieferung(en) quittiert.\n"
                    f"{len(failed)} Lieferung(en) fehlgeschlagen."
                )
            else:
                self._toast_manager.show_success(
                    f"{len(successful)} Lieferung(en) erfolgreich quittiert.\n"
                    "Die Lieferungen wurden vom Server entfernt."
                )
        elif failed:
            self._toast_manager.show_error(
                f"Alle {len(failed)} Quittierungen fehlgeschlagen."
            )
