"""
ACENCIA ATLAS - BiPRO Worker-Klassen

QThread-basierte Worker fuer BiPRO-Operationen:
- FetchShipmentsWorker: Lieferungen abrufen
- DownloadShipmentWorker: Einzeldownload + PDF-Validierung
- AcknowledgeShipmentWorker: Empfangsbestaetigung senden
- MailImportWorker: IMAP-Poll + Attachment-Download + Pipeline
- ParallelDownloadManager: Parallele Downloads mit ThreadPoolExecutor

Ausgelagert aus bipro_view.py (Schritt 2 Refactoring).
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

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

logger = logging.getLogger(__name__)

from PySide6.QtCore import Signal, QThread

from api.vu_connections import VUCredentials
from bipro.categories import get_category_short_name
from bipro.mtom_parser import parse_mtom_response, split_multipart
from bipro.transfer_service import SharedTokenManager, BiPROCredentials
from bipro.rate_limiter import AdaptiveRateLimiter


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


class PreviewAllShipmentsWorker(QThread):
    """Worker der listShipments fuer alle VUs im Hintergrund ausfuehrt.

    Holt Credentials und ruft list_shipments pro VU -- alles im Worker-Thread,
    damit der Main-Thread nie blockiert wird.
    """
    finished = Signal(list)       # [(vu_name, [ShipmentInfo, ...]), ...]
    vu_error = Signal(str, str)   # (vu_name, error_msg)
    progress = Signal(str)

    def __init__(self, connections: list, vu_api, cert_config_loader=None):
        """
        Args:
            connections: Liste aktiver VUConnection-Objekte
            vu_api: VUConnectionsAPI-Instanz (thread-safe HTTP-Calls)
            cert_config_loader: Callable(connection_id) -> dict (Zertifikats-Config)
        """
        super().__init__()
        self._connections = connections
        self._vu_api = vu_api
        self._cert_config_loader = cert_config_loader

    def _resolve_credentials(self, conn):
        """Holt Credentials fuer eine VU-Verbindung (laeuft im Worker-Thread)."""
        if conn.auth_type == 'certificate':
            if not self._cert_config_loader:
                return None
            cert_config = self._cert_config_loader(conn.id)
            if not cert_config:
                return None
            cert_format = cert_config.get('cert_format', 'pfx')
            if cert_format == 'jks':
                return VUCredentials(
                    username="", password="",
                    jks_path=cert_config.get('jks_path', ''),
                    jks_password=cert_config.get('jks_password', ''),
                    jks_alias=cert_config.get('jks_alias', ''),
                    jks_key_password=cert_config.get('jks_key_password', ''),
                )
            return VUCredentials(
                username="", password="",
                pfx_path=cert_config.get('pfx_path', ''),
                pfx_password=cert_config.get('pfx_password', ''),
            )
        try:
            return self._vu_api.get_credentials(conn.id)
        except Exception:
            return None

    def run(self):
        from bipro.transfer_service import TransferServiceClient, BiPROCredentials
        results = []
        total = len(self._connections)
        for i, conn in enumerate(self._connections):
            vu_name = conn.vu_name
            try:
                self.progress.emit(f"{vu_name} ({i + 1}/{total})...")
                creds = self._resolve_credentials(conn)
                if not creds:
                    logger.warning(f"Preview: Keine Credentials fuer {vu_name}")
                    self.vu_error.emit(vu_name, "Credentials nicht verfuegbar")
                    results.append((vu_name, []))
                    continue
                bipro_creds = BiPROCredentials(
                    username=creds.username,
                    password=creds.password,
                    endpoint_url=conn.get_effective_transfer_url(),
                    sts_endpoint_url=conn.get_effective_sts_url(),
                    vu_name=vu_name,
                    consumer_id=conn.consumer_id or '',
                    pfx_path=getattr(creds, 'pfx_path', ''),
                    pfx_password=getattr(creds, 'pfx_password', ''),
                    jks_path=getattr(creds, 'jks_path', ''),
                    jks_password=getattr(creds, 'jks_password', ''),
                    jks_alias=getattr(creds, 'jks_alias', ''),
                    jks_key_password=getattr(creds, 'jks_key_password', ''),
                )
                with TransferServiceClient(bipro_creds) as client:
                    shipments = client.list_shipments(confirmed=True)
                    results.append((vu_name, shipments))
            except Exception as e:
                logger.warning(f"Preview fehlgeschlagen fuer {vu_name}: {e}")
                self.vu_error.emit(vu_name, str(e))
                results.append((vu_name, []))
        self.finished.emit(results)


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
                if len(self.shipment_ids) <= 3:
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
                else:
                    import concurrent.futures
                    import threading
                    lock = threading.Lock()
                    
                    def _ack_single(sid):
                        try:
                            if client.acknowledge_shipment(sid):
                                with lock:
                                    successful.append(sid)
                                self.progress.emit(f"  OK: {sid}")
                            else:
                                with lock:
                                    failed.append(sid)
                                self.progress.emit(f"  FEHLER: {sid}")
                        except Exception as e:
                            with lock:
                                failed.append(sid)
                            self.progress.emit(f"  FEHLER bei {sid}: {e}")
                    
                    max_workers = min(4, len(self.shipment_ids))
                    self.progress.emit(f"Quittiere {len(self.shipment_ids)} Lieferungen parallel ({max_workers} gleichzeitig)...")
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                        pool.map(_ack_single, self.shipment_ids)
            
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

    def _prepare_single_file(self, fp, jobs, temp_base):
        """Bereitet eine Einzeldatei vor: Bild→PDF-Konvertierung + PDF-Unlock."""
        from services.pdf_unlock import unlock_pdf_if_needed
        from services.image_converter import is_image_file, convert_image_to_pdf
        import os

        if is_image_file(fp):
            td = tempfile.mkdtemp(prefix="atlas_mail_img_", dir=temp_base)
            base = os.path.splitext(os.path.basename(fp))[0]
            pdf_out = os.path.join(td, base + '.pdf')
            pdf_path = convert_image_to_pdf(fp, pdf_out)
            if pdf_path:
                jobs.append((pdf_path, None))
                jobs.append((fp, 'roh'))
            else:
                jobs.append((fp, None))
        else:
            try:
                unlock_pdf_if_needed(fp, api_client=self._api_client)
            except Exception:
                pass
            jobs.append((fp, None))

    def _expand_attachment(self, file_path: str, temp_base: str):
        """Verarbeitet einen heruntergeladenen Anhang durch die Pipeline.
        
        Returns:
            Liste von (path, box_type) Tupeln. box_type=None -> Eingangsbox, 'roh' -> Roh-Archiv.
        """
        from services.msg_handler import is_msg_file, extract_msg_attachments
        from services.zip_handler import is_zip_file, extract_zip_contents

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
                        mr = extract_msg_attachments(ext, md, api_client=self._api_client)
                        if mr.error:
                            errors.append(mr.error)
                        else:
                            for att in mr.attachment_paths:
                                self._prepare_single_file(att, jobs, temp_base)
                        jobs.append((ext, 'roh'))
                    else:
                        self._prepare_single_file(ext, jobs, temp_base)
                jobs.append((file_path, 'roh'))

        elif is_msg_file(file_path):
            td = tempfile.mkdtemp(prefix="atlas_mail_msg_", dir=temp_base)
            mr = extract_msg_attachments(file_path, td, api_client=self._api_client)
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
                                self._prepare_single_file(ext, jobs, temp_base)
                        jobs.append((att, 'roh'))
                    else:
                        self._prepare_single_file(att, jobs, temp_base)
            jobs.append((file_path, 'roh'))

        else:
            self._prepare_single_file(file_path, jobs, temp_base)

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
                # Fruehe Text-Extraktion fuer Inhaltsduplikat-Erkennung
                if box_type != 'roh':
                    try:
                        from services.early_text_extract import extract_and_save_text
                        extract_and_save_text(docs_api, doc.id, file_path, name)
                    except Exception:
                        pass  # Darf Upload nicht abbrechen
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

class ParallelDownloadManager(QThread):
    """
    Manager für parallele BiPRO-Downloads mit Token-Sharing und Rate Limiting.
    
    Downloads UND Uploads laufen komplett in Worker-Threads (per-Thread API-Client).
    Der Main-Thread wird nicht blockiert.
    
    Features:
    - Parallele Downloads mit konfigurierbarer Worker-Anzahl (Standard: 5)
    - Thread-safe Token-Sharing (Token wird nur 1x geholt)
    - Adaptives Rate Limiting (HTTP 429/503 Erkennung)
    - Automatische Retries bei Fehlern (max. 3 Versuche)
    - Keine Dokumentenverluste durch Retry-Queue
    - Per-Thread API-Clients fuer thread-safe Uploads
    - Early Text Extraction fuer Inhaltsduplikat-Erkennung
    
    Signals:
    - progress_updated: (current, total, docs_count, failed_count, active_workers)
    - shipment_uploaded: (shipment_id, doc_count, upload_errors)
    - log_message: (message)
    - all_finished: (stats_dict)
    - error: (error_message)
    """
    
    progress_updated = Signal(int, int, int, int, int)  # current, total, docs, failed, active_workers
    shipment_uploaded = Signal(str, int, int)  # shipment_id, doc_count, upload_errors
    log_message = Signal(str)
    all_finished = Signal(dict)  # stats
    error = Signal(str)
    
    DEFAULT_MAX_WORKERS = 10
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_INITIAL_BACKOFF = 1.0
    DEFAULT_MAX_BACKOFF = 30.0
    DEFAULT_RECOVERY_THRESHOLD = 10
    
    def __init__(
        self,
        credentials: 'VUCredentials',
        vu_name: str,
        shipments: list,
        sts_url: str,
        transfer_url: str,
        consumer_id: str = "",
        max_workers: int = None,
        api_client: 'APIClient' = None,
        parent=None
    ):
        super().__init__(parent)
        
        self.credentials = credentials
        self.vu_name = vu_name
        self.shipments = shipments
        self.sts_url = sts_url
        self.transfer_url = transfer_url
        self.consumer_id = consumer_id
        self._api_client = api_client
        
        self._configured_workers = max_workers or self.DEFAULT_MAX_WORKERS
        self.max_workers = min(self._configured_workers, len(shipments))
        
        self._download_queue: queue.Queue = queue.Queue()
        self._token_manager: Optional[SharedTokenManager] = None
        self._rate_limiter: Optional[AdaptiveRateLimiter] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        
        # Per-Thread API-Clients (thread_id -> DocumentsAPI)
        self._thread_apis: dict = {}
        self._thread_apis_lock = threading.Lock()
        
        self._stats_lock = threading.Lock()
        self._stats = {
            'total': len(shipments),
            'success': 0,
            'failed': 0,
            'docs': 0,
            'events': 0,
            'retries': 0,
            'failed_ids': []
        }
        self._processed_count = 0
        
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
        Erstellt eine Session pro Thread fuer TCP/TLS Connection-Pooling.
        
        Args:
            worker_id: ID des Workers (für Logging)
        """
        session = requests.Session()
        session.verify = True
        session.trust_env = False
        session.proxies = {'http': '', 'https': ''}

        if self._token_manager and self._token_manager.uses_certificate():
            cert_config = self._token_manager.get_cert_config()
            if cert_config:
                session.cert = cert_config

        try:
            while not self._cancelled and not self._shutdown_event.is_set():
                active_workers = self._rate_limiter.get_active_workers()
                if worker_id >= active_workers:
                    time.sleep(0.5)
                    continue
                
                self._rate_limiter.wait_if_needed()
                
                try:
                    shipment_info = self._download_queue.get(timeout=0.5)
                except queue.Empty:
                    break
                
                logger.info(f"Worker {worker_id}: Got shipment from queue: {shipment_info.keys()}")
                
                try:
                    shipment_id = shipment_info['id']
                    category = shipment_info.get('category', '')
                    created_at = shipment_info.get('created_at', '')
                    retry_count = shipment_info.get('_retry_count', 0)
                    
                    logger.info(f"Worker {worker_id}: Shipment {shipment_id}, created_at type: {type(created_at)}, value: {repr(created_at)}")
                except Exception as e:
                    logger.error(f"Worker {worker_id}: Fehler beim Extrahieren der Shipment-Daten: {e}")
                    self._download_queue.task_done()
                    continue
                
                try:
                    documents, raw_xml_path = self._download_shipment(
                        shipment_id, category, created_at, session=session
                    )
                    
                    self._rate_limiter.on_success(shipment_id)
                    
                    upload_errors, event_created = self._upload_shipment_docs(
                        shipment_id, documents, raw_xml_path, category
                    )
                    
                    with self._stats_lock:
                        self._stats['success'] += 1
                        self._stats['docs'] += len(documents)
                        if event_created:
                            self._stats['events'] += 1
                        self._processed_count += 1
                        current = self._processed_count
                        total = self._stats['total']
                        docs = self._stats['docs']
                        failed = self._stats['failed']
                    
                    active = self._rate_limiter.get_active_workers()
                    self.progress_updated.emit(current, total, docs, failed, active)
                    self.shipment_uploaded.emit(shipment_id, len(documents), upload_errors)
                    
                    if len(documents) == 0 and event_created:
                        self.log_message.emit(f"  [OK] Lieferung {shipment_id}: 0 Dateien \u2013 1 Meldung")
                    else:
                        self.log_message.emit(f"  [OK] Lieferung {shipment_id}: {len(documents)} Dokument(e)")
                    
                except Exception as e:
                    error_str = str(e)
                    status_code = self._extract_status_code(e)
                    
                    if status_code and self._rate_limiter.is_rate_limit_status(status_code):
                        should_retry = self._rate_limiter.on_rate_limit(status_code, shipment_id)
                    else:
                        should_retry = self._rate_limiter.on_error(shipment_id, error_str, status_code)
                    
                    if should_retry and retry_count < self.DEFAULT_MAX_RETRIES:
                        shipment_info['_retry_count'] = retry_count + 1
                        self._download_queue.put(shipment_info)
                        
                        with self._stats_lock:
                            self._stats['retries'] += 1
                        
                        self.log_message.emit(
                            f"  [RETRY] Lieferung {shipment_id}: {error_str[:80]} "
                            f"(Versuch {retry_count + 1}/{self.DEFAULT_MAX_RETRIES})"
                        )
                    else:
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
        finally:
            session.close()
    
    def _get_thread_api(self):
        """Gibt eine thread-lokale DocumentsAPI-Instanz zurueck."""
        if not self._api_client:
            return None
        tid = threading.get_ident()
        with self._thread_apis_lock:
            if tid not in self._thread_apis:
                from api.client import APIClient
                from api.documents import DocumentsAPI
                client = APIClient(self._api_client.config)
                client.set_token(self._api_client._token)
                self._thread_apis[tid] = DocumentsAPI(client)
            return self._thread_apis[tid]
    
    def _preprocess_file(self, filepath: str, filename: str,
                         category: str, docs_api) -> list:
        """Bereitet eine Datei vor dem Upload vor (ZIP/GDV/PDF-Handling).

        Returns:
            Liste von (filepath, box_type_override) Tuples.
            box_type_override=None bedeutet Standard-Eingangsbox.
        """
        ext = os.path.splitext(filename)[1].lower()
        combined_name = filename.lower()

        if ext == '.zip' or combined_name.endswith('.zip.gdv'):
            return self._preprocess_zip(filepath, filename, docs_api)

        if ext in ('.gdv',):
            return [(filepath, None)]

        if ext == '.pdf':
            try:
                from services.pdf_unlock import unlock_pdf_if_needed
                unlock_pdf_if_needed(filepath, api_client=docs_api.client if docs_api else None)
            except Exception as e:
                logger.debug(f"PDF-Unlock fehlgeschlagen fuer {filename}: {e}")
            return [(filepath, None)]

        return [(filepath, None)]

    def _preprocess_zip(self, filepath: str, filename: str, docs_api) -> list:
        """Entpackt ZIP-Dateien mit Passwort-Check.

        Returns:
            Liste von (filepath, box_type_override) Tuples.
        """
        jobs = []
        try:
            from services.zip_handler import extract_zip_contents
            api_client = docs_api.client if docs_api else None
            result = extract_zip_contents(filepath, api_client=api_client)

            if result.error:
                self.log_message.emit(f"    [ZIP-FEHLER] {filename}: {result.error}")
                jobs.append((filepath, None))
                return jobs

            for extracted_path in result.extracted_paths:
                ext = os.path.splitext(extracted_path)[1].lower()
                if ext == '.pdf':
                    try:
                        from services.pdf_unlock import unlock_pdf_if_needed
                        unlock_pdf_if_needed(extracted_path, api_client=api_client)
                    except Exception:
                        pass
                jobs.append((extracted_path, None))

            jobs.append((filepath, 'roh'))
            self.log_message.emit(
                f"    [ZIP] {filename}: {len(result.extracted_paths)} Datei(en) entpackt"
            )
        except Exception as e:
            logger.warning(f"ZIP-Verarbeitung fehlgeschlagen: {e}")
            jobs.append((filepath, None))

        return jobs

    def _upload_shipment_docs(self, shipment_id: str, documents: list,
                              raw_xml_path: str, category: str) -> tuple:
        """Laedt Dokumente und Raw-XML im Worker-Thread hoch.

        Returns:
            Tuple (upload_errors: int, event_created: bool)
        """
        docs_api = self._get_thread_api()
        if not docs_api:
            return (0, False)

        upload_errors = 0
        event_created = False
        vu_name = self.vu_name

        for doc in documents:
            try:
                validation_status = doc.get('validation_status')
                is_valid = doc.get('is_valid', True)
                filepath = doc['filepath']
                filename = doc.get('filename', doc.get('original_filename', ''))

                if not is_valid and validation_status:
                    self.log_message.emit(
                        f"    [PDF-PROBLEM] {filename or 'unbekannt'}: {validation_status}"
                    )
                    docs_api.upload(
                        file_path=filepath,
                        source_type='bipro_auto',
                        shipment_id=shipment_id,
                        vu_name=vu_name,
                        bipro_category=category,
                        validation_status=validation_status,
                        box_type='sonstige'
                    )
                    continue

                upload_jobs = self._preprocess_file(filepath, filename, category, docs_api)

                for job_path, box_override in upload_jobs:
                    try:
                        upload_kwargs = dict(
                            file_path=job_path,
                            source_type='bipro_auto',
                            shipment_id=shipment_id,
                            vu_name=vu_name,
                            bipro_category=category,
                            validation_status=validation_status if validation_status else 'OK',
                        )
                        if box_override:
                            upload_kwargs['box_type'] = box_override

                        uploaded = docs_api.upload(**upload_kwargs)

                        if uploaded and box_override != 'roh':
                            try:
                                from services.early_text_extract import extract_and_save_text
                                extract_and_save_text(
                                    docs_api, uploaded.id, job_path,
                                    os.path.basename(job_path)
                                )
                            except Exception:
                                pass
                    except Exception as e:
                        upload_errors += 1
                        self.log_message.emit(
                            f"    [!] Upload fehlgeschlagen: {os.path.basename(job_path)}: {e}"
                        )
            except Exception as e:
                upload_errors += 1
                self.log_message.emit(
                    f"    [!] Upload fehlgeschlagen: {doc.get('filename', 'unbekannt')}: {e}"
                )

        raw_doc_id = None
        no_binary_docs = (len(documents) == 0)

        if no_binary_docs:
            metadata = self._extract_soap_metadata(raw_xml_path, category)
            if metadata:
                new_name = self._build_descriptive_xml_name(
                    metadata, shipment_id, vu_name
                )
                renamed_path = os.path.join(os.path.dirname(raw_xml_path), new_name)
                try:
                    os.rename(raw_xml_path, renamed_path)
                    raw_xml_path = renamed_path
                except OSError:
                    pass

        try:
            uploaded_raw = docs_api.upload(
                file_path=raw_xml_path,
                source_type='bipro_auto',
                shipment_id=shipment_id,
                vu_name=vu_name,
                box_type='roh'
            )
            if uploaded_raw:
                raw_doc_id = uploaded_raw.id
        except Exception as e:
            self.log_message.emit(f"    [!] Raw XML Upload fehlgeschlagen: {e}")

        if no_binary_docs and metadata:
            self._create_bipro_event(
                docs_api, shipment_id, category, vu_name, metadata, raw_doc_id
            )
            event_created = True

        # Temp-Dateien aufraumen
        try:
            temp_dir = os.path.dirname(raw_xml_path)
            if temp_dir and 'bipro_parallel_' in temp_dir:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

        return (upload_errors, event_created)

    def _extract_soap_metadata(self, xml_path: str, category: str) -> dict:
        """Extrahiert strukturierte Metadaten aus einer SOAP-XML-Huellkurve."""
        import re
        try:
            with open(xml_path, 'r', encoding='utf-8', errors='replace') as f:
                xml_text = f.read()
        except Exception:
            return {}

        def _find(pattern_options):
            for p in pattern_options:
                m = re.search(p, xml_text, re.DOTALL)
                if m:
                    return m.group(1).strip()
            return None

        meta = {}

        meta['vsnr'] = _find([
            r'<[^>]*?Versicherungsscheinnummer[^>]*>([^<]+)<',
        ])
        meta['vu_bafin_nr'] = _find([
            r'<[^>]*?Unternehmensnummer[^>]*>([^<]+)<',
        ])
        meta['sparte'] = _find([
            r'<[^>]*?Sparte[^>]*>([^<]+)<',
        ])
        meta['vermittler_nr'] = _find([
            r'<[^>]*?Vermittlernummer[^>]*>([^<]+)<',
        ])
        meta['freitext'] = _find([
            r'<[^>]*?Freitext[^>]*>([^<]+)<',
        ])
        meta['kurzbeschreibung'] = _find([
            r'<[^>]*?Kurzbeschreibung[^>]*>([^<]+)<',
        ])
        meta['referenced_filename'] = _find([
            r'<[^>]*?Dateiname[^>]*>([^<]+)<',
        ])

        name_parts = []
        nachname = _find([r'<[^>]*?Nachname[^>]*>([^<]+)<'])
        vorname = _find([r'<[^>]*?Vorname[^>]*>([^<]+)<'])
        firma = _find([r'<[^>]*?Firmenname[^>]*>([^<]+)<'])
        if firma:
            name_parts.append(firma)
        if nachname:
            name_parts.append(nachname)
        if vorname:
            name_parts.append(vorname)
        if name_parts:
            meta['vn_name'] = ' '.join(name_parts)

        addr_parts = []
        strasse = _find([r'<[^>]*?Strasse[^>]*>([^<]+)<'])
        plz = _find([r'<[^>]*?Postleitzahl[^>]*>([^<]+)<'])
        ort = _find([r'<[^>]*?Ort[^>]*>([^<]+)<'])
        if strasse:
            addr_parts.append(strasse)
        if plz and ort:
            addr_parts.append(f"{plz} {ort}")
        elif ort:
            addr_parts.append(ort)
        if addr_parts:
            meta['vn_address'] = ', '.join(addr_parts)

        erstelldatum = _find([r'<[^>]*?Erstelldatum[^>]*>([^<]+)<'])
        if erstelldatum:
            try:
                d = erstelldatum[:10]
                meta['shipment_date'] = d
            except Exception:
                pass

        meta = {k: v for k, v in meta.items() if v}
        return meta

    def _determine_event_type(self, category: str) -> str:
        """Bestimmt den event_type anhand der BiPRO-Kategorie."""
        if category and category.startswith('999'):
            from config.processing_rules import BIPRO_XML_ONLY_CATEGORIES
            if category in BIPRO_XML_ONLY_CATEGORIES:
                return BIPRO_XML_ONLY_CATEGORIES[category]
            return 'gdv_announced'
        if category and category.startswith('14'):
            return 'status_message'
        return 'document_xml'

    def _build_descriptive_xml_name(self, metadata: dict,
                                    shipment_id: str, vu_name: str) -> str:
        """Baut einen beschreibenden Dateinamen fuer die Roh-XML."""
        parts = []
        parts.append(vu_name or 'BiPRO')

        category_name = get_category_short_name(
            metadata.get('bipro_category', '')
        ) if metadata.get('bipro_category') else None
        if not category_name:
            category_name = 'Daten'
        parts.append(category_name)

        if metadata.get('vsnr'):
            parts.append(f"VSNR-{metadata['vsnr']}")

        if metadata.get('shipment_date'):
            parts.append(metadata['shipment_date'][:10])
        else:
            parts.append(datetime.now().strftime('%Y-%m-%d'))

        parts.append(str(shipment_id))

        safe = '_'.join(parts)
        safe = ''.join(c if (c.isalnum() or c in '-_.') else '_' for c in safe)
        return f"{safe}.xml"

    def _create_bipro_event(self, docs_api, shipment_id: str, category: str,
                            vu_name: str, metadata: dict,
                            raw_document_id: int = None) -> None:
        """Erstellt einen BiPRO-Event-Eintrag auf dem Server."""
        try:
            from api.bipro_events import BiproEventsAPI
            events_api = BiproEventsAPI(docs_api.client)

            event_type = self._determine_event_type(category)
            category_name_str = get_category_short_name(category) if category else None

            data = {
                'shipment_id': str(shipment_id),
                'vu_name': vu_name,
                'vu_bafin_nr': metadata.get('vu_bafin_nr'),
                'bipro_category': category,
                'category_name': category_name_str,
                'event_type': event_type,
                'vsnr': metadata.get('vsnr'),
                'vn_name': metadata.get('vn_name'),
                'vn_address': metadata.get('vn_address'),
                'sparte': metadata.get('sparte'),
                'vermittler_nr': metadata.get('vermittler_nr'),
                'freitext': metadata.get('freitext'),
                'kurzbeschreibung': metadata.get('kurzbeschreibung'),
                'referenced_filename': metadata.get('referenced_filename'),
                'shipment_date': metadata.get('shipment_date'),
                'raw_document_id': raw_document_id,
            }
            events_api.create_event(data)
        except Exception as e:
            logger.debug(f"BiPRO-Event erstellen fehlgeschlagen: {e}")
    
    def _download_shipment(self, shipment_id, category, created_at, session=None):
        """
        Lädt eine einzelne Lieferung herunter.
        
        Args:
            shipment_id: ID der Lieferung
            category: BiPRO-Kategorie
            created_at: Erstellungsdatum
            session: Optionaler requests.Session zur Wiederverwendung
            
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
        
        temp_session = None
        if session is None:
            temp_session = requests.Session()
            temp_session.verify = True
            temp_session.trust_env = False
            temp_session.proxies = {'http': '', 'https': ''}

            if self._token_manager and self._token_manager.uses_certificate():
                cert_config = self._token_manager.get_cert_config()
                if cert_config:
                    temp_session.cert = cert_config

            session = temp_session
        
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
                documents, metadata = parse_mtom_response(raw_content, content_type)
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
                parts = split_multipart(raw_content, content_type)
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
                    from config.processing_rules import PDFValidationStatus
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
            if temp_session:
                temp_session.close()
    
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
        from config.processing_rules import PDFValidationStatus
        
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
        from config.processing_rules import PDFValidationStatus
        
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
