"""
ACENCIA ATLAS - Archiv Worker-Klassen

Alle QThread-Worker fuer das Dokumentenarchiv.
Extrahiert aus archive_boxes_view.py (Schritt 3 Refactoring).
"""

from typing import Optional, List
from pathlib import Path
import os
import logging
import tempfile

from PySide6.QtCore import Qt, Signal, QThread

from api.client import APIClient
from api.documents import (
    DocumentsAPI, Document, BoxStats, SearchResult,
    safe_cache_filename
)

logger = logging.getLogger(__name__)


class DocumentHistoryWorker(QThread):
    """
    Worker zum asynchronen Laden der Dokument-Historie.
    
    Laedt die Aenderungshistorie eines Dokuments aus dem activity_log
    via GET /documents/{id}/history.
    """
    finished = Signal(int, list)    # doc_id, history_entries
    error = Signal(int, str)        # doc_id, error_message
    
    def __init__(self, api_client: APIClient, doc_id: int, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.doc_id = doc_id
    
    def run(self):
        try:
            docs_api = DocumentsAPI(self.api_client)
            history = docs_api.get_document_history(self.doc_id)
            if history is not None:
                self.finished.emit(self.doc_id, history)
            else:
                self.error.emit(self.doc_id, "Historie konnte nicht geladen werden")
        except Exception as e:
            logger.error(f"Fehler beim Laden der Dokument-Historie: {e}")
            self.error.emit(self.doc_id, str(e))


class CacheDocumentLoadWorker(QThread):
    """
    Worker zum Laden von Dokumenten ueber den zentralen Cache-Service.
    
    Laedt ALLE Dokumente in einem API-Call in den Cache,
    filtert dann client-seitig nach box_type und is_archived.
    
    Vorteil gegenueber DocumentLoadWorker:
    - 1 API-Call statt N (pro Box)
    - Cache wird fuer alle Boxen befuellt
    - Nachfolgende Box-Wechsel sind instant (aus Cache)
    """
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, cache_service, box_type: str = None, 
                 is_archived: bool = None, force_refresh: bool = True):
        super().__init__()
        self._cache = cache_service
        self.box_type = box_type
        self.is_archived = is_archived
        self.force_refresh = force_refresh
    
    def run(self):
        try:
            # Laedt ALLE Dokumente in Cache (1 API-Call), filtert lokal
            docs = self._cache.get_documents(
                box_type=self.box_type, 
                force_refresh=self.force_refresh
            )
            
            # is_archived Filter client-seitig anwenden
            if self.is_archived is True:
                docs = [d for d in docs if d.is_archived]
            elif self.is_archived is False:
                docs = [d for d in docs if not d.is_archived]
            
            self.finished.emit(docs)
        except Exception as e:
            self.error.emit(str(e))


class MissingAiDataWorker(QThread):
    """
    Hintergrund-Worker der Dokumente ohne AI-Data (Text-Extraktion) prueft.
    
    Wird einmal beim Archiv-Start ausgefuehrt. Findet Dokumente die
    serverseitig hochgeladen wurden (z.B. Scans via Power Automate)
    und fuer die noch kein Volltext extrahiert wurde.
    
    Fuer jedes solche Dokument: Download -> Text extrahieren -> save_ai_data.
    Dadurch werden auch Scan-Duplikate erkannt.
    """
    finished = Signal(int)  # Anzahl verarbeiteter Dokumente
    
    def __init__(self, docs_api):
        super().__init__()
        self._docs_api = docs_api
    
    def run(self):
        import tempfile
        import time
        from services.early_text_extract import extract_and_save_text
        
        try:
            missing = self._docs_api.get_missing_ai_data_documents()
            if not missing:
                self.finished.emit(0)
                return
            
            processed = 0
            for doc_info in missing:
                doc_id = doc_info.get('id')
                filename = doc_info.get('original_filename', '')
                if not doc_id:
                    continue
                
                try:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        file_path = self._docs_api.download(
                            doc_id, tmp_dir, filename_override=filename
                        )
                        if file_path:
                            extract_and_save_text(
                                self._docs_api, doc_id, file_path, filename
                            )
                            processed += 1
                except Exception:
                    pass  # Einzelne Fehler ueberspringen
                
                time.sleep(0.2)  # Server nicht ueberlasten
            
            self.finished.emit(processed)
        except Exception:
            self.finished.emit(0)


class MultiUploadWorker(QThread):
    """Worker zum Hochladen mehrerer Dateien.
    
    Phase 1: Alle ZIPs/MSGs rekursiv entpacken -> flache Job-Liste
    Phase 2: Parallele Uploads via ThreadPoolExecutor (max. 5 gleichzeitig)
    
    Jeder Upload-Thread bekommt eine eigene requests.Session (thread-safe).
    """
    MAX_UPLOAD_WORKERS = 5
    
    file_finished = Signal(str, object)  # filename, Document or None
    file_error = Signal(str, str)  # filename, error message
    all_finished = Signal(int, int)  # erfolge, fehler
    progress = Signal(int, int, str)  # current, total, filename
    
    def __init__(self, docs_api: DocumentsAPI, file_paths: list, source_type: str):
        super().__init__()
        self.docs_api = docs_api
        self.file_paths = file_paths
        self.source_type = source_type
    
    def _prepare_single_file(self, fp, jobs, api_client):
        """Bereitet eine Einzeldatei vor: Bild→PDF-Konvertierung + PDF-Unlock."""
        from services.pdf_unlock import unlock_pdf_if_needed
        from services.image_converter import is_image_file, convert_image_to_pdf

        if is_image_file(fp):
            import tempfile as _tf
            td = _tf.mkdtemp(prefix="atlas_img_")
            self._temp_dirs.append(td)
            import os
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
                unlock_pdf_if_needed(fp, api_client=api_client)
            except ValueError as e:
                logger.warning(str(e))
            jobs.append((fp, None))

    def _expand_all_files(self, file_paths):
        """Phase 1: Entpackt alle ZIPs/MSGs rekursiv und liefert flache Upload-Job-Liste.
        
        Returns:
            Liste von (path, box_type_or_None) Tupeln.
            box_type=None bedeutet Eingangsbox, 'roh' = Roh-Archiv.
        """
        import tempfile
        from services.msg_handler import is_msg_file, extract_msg_attachments
        from services.zip_handler import is_zip_file, extract_zip_contents

        jobs = []

        for fp in file_paths:
            if is_zip_file(fp):
                td = tempfile.mkdtemp(prefix="atlas_zip_")
                self._temp_dirs.append(td)
                zr = extract_zip_contents(fp, td, api_client=self.docs_api.client)
                if zr.error:
                    self._errors.append((Path(fp).name, zr.error))
                    jobs.append((fp, 'roh'))
                    continue
                for ext in zr.extracted_paths:
                    if is_msg_file(ext):
                        md = tempfile.mkdtemp(prefix="atlas_msg_", dir=td)
                        mr = extract_msg_attachments(ext, md, api_client=self.docs_api.client)
                        if mr.error:
                            self._errors.append((Path(ext).name, mr.error))
                        else:
                            for att in mr.attachment_paths:
                                self._prepare_single_file(att, jobs, self.docs_api.client)
                        jobs.append((ext, 'roh'))
                    else:
                        self._prepare_single_file(ext, jobs, self.docs_api.client)
                jobs.append((fp, 'roh'))

            elif is_msg_file(fp):
                td = tempfile.mkdtemp(prefix="atlas_msg_")
                self._temp_dirs.append(td)
                mr = extract_msg_attachments(fp, td, api_client=self.docs_api.client)
                if mr.error:
                    self._errors.append((Path(fp).name, mr.error))
                    continue
                for att in mr.attachment_paths:
                    if is_zip_file(att):
                        zd = tempfile.mkdtemp(prefix="atlas_zip_", dir=td)
                        zr = extract_zip_contents(att, zd, api_client=self.docs_api.client)
                        if zr.error:
                            self._errors.append((Path(att).name, zr.error))
                        else:
                            for ext in zr.extracted_paths:
                                self._prepare_single_file(ext, jobs, self.docs_api.client)
                        jobs.append((att, 'roh'))
                    else:
                        self._prepare_single_file(att, jobs, self.docs_api.client)
                jobs.append((fp, 'roh'))

            else:
                self._prepare_single_file(fp, jobs, self.docs_api.client)

        return jobs
    
    def _upload_single(self, path: str, source_type: str, box_type: str = None):
        """Thread-safe Upload einer einzelnen Datei mit per-Thread API-Client.
        
        Returns:
            (filename, success, doc_or_error_str)
        """
        import threading
        name = Path(path).name
        try:
            # Per-Thread API-Client (eigene requests.Session)
            tid = threading.get_ident()
            if tid not in self._thread_apis:
                from api.client import APIClient
                client = APIClient(self.docs_api.client.config)
                client.set_token(self.docs_api.client._token)
                self._thread_apis[tid] = DocumentsAPI(client)
            docs_api = self._thread_apis[tid]

            if box_type:
                doc = docs_api.upload(path, source_type, box_type=box_type)
            else:
                doc = docs_api.upload(path, source_type)
            if doc:
                # Fruehe Text-Extraktion fuer Inhaltsduplikat-Erkennung
                if box_type != 'roh':
                    try:
                        from services.early_text_extract import extract_and_save_text
                        extract_and_save_text(docs_api, doc.id, path, name)
                    except Exception:
                        pass  # Darf Upload nicht abbrechen
                return (name, True, doc)
            else:
                return (name, False, "Upload fehlgeschlagen")
        except Exception as e:
            return (name, False, str(e))
    
    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self._temp_dirs = []
        self._errors = []
        self._thread_apis = {}

        # Phase 1: Alle Dateien entpacken (sequentiell, lokal)
        jobs = self._expand_all_files(self.file_paths)
        total = len(jobs)
        self.progress.emit(0, total, "")

        # Fehler aus Phase 1 emittieren
        for name, error in self._errors:
            self.file_error.emit(name, error)

        # Phase 2: Parallele Uploads
        erfolge = 0
        fehler = len(self._errors)
        uploaded = 0

        workers = min(self.MAX_UPLOAD_WORKERS, max(1, total))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._upload_single, path, self.source_type, box_type): path
                for path, box_type in jobs
            }
            for future in as_completed(futures):
                name, success, result = future.result()
                uploaded += 1
                self.progress.emit(uploaded, total, name)
                if success:
                    erfolge += 1
                    self.file_finished.emit(name, result)
                else:
                    fehler += 1
                    self.file_error.emit(name, result)

        # Temporaere Verzeichnisse aufraeumen
        import shutil
        for td in self._temp_dirs:
            try:
                shutil.rmtree(td, ignore_errors=True)
            except Exception:
                pass
        
        self.all_finished.emit(erfolge, fehler)


class PreviewDownloadWorker(QThread):
    """
    Worker zum Herunterladen einer Datei fuer die Vorschau.
    
    Optimierungen:
    - filename_override: Spart get_document() API-Call (Filename bereits bekannt)
    - cache_dir: Persistenter Cache fuer Vorschauen (gleiche Datei nur 1x downloaden)
    """
    download_finished = Signal(object)  # saved_path oder None
    download_error = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI, doc_id: int, target_dir: str,
                 filename: str = None, cache_dir: str = None):
        super().__init__()
        self.docs_api = docs_api
        self.doc_id = doc_id
        self.target_dir = target_dir
        self.filename = filename
        self.cache_dir = cache_dir
        self._cancelled = False
    
    def cancel(self):
        """Markiert den Download als abgebrochen."""
        self._cancelled = True
    
    def run(self):
        try:
            if self._cancelled:
                self.download_finished.emit(None)
                return
            
            # Cache-Check: Datei bereits lokal vorhanden?
            if self.cache_dir and self.filename:
                cache_name = safe_cache_filename(self.doc_id, self.filename)
                cached_path = os.path.join(self.cache_dir, cache_name)
                if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
                    logger.info(f"Vorschau aus Cache: {cached_path}")
                    self.download_finished.emit(cached_path)
                    return
            
            # Download mit filename_override (spart get_document API-Call)
            download_dir = self.cache_dir or self.target_dir
            cache_name = safe_cache_filename(self.doc_id, self.filename) if self.cache_dir and self.filename else self.filename
            result = self.docs_api.download(
                self.doc_id, download_dir, 
                filename_override=cache_name
            )
            
            if self._cancelled:
                self.download_finished.emit(None)
                return
            self.download_finished.emit(result)
        except Exception as e:
            self.download_error.emit(str(e))


class MultiDownloadWorker(QThread):
    """Worker zum Herunterladen mehrerer Dateien im Hintergrund."""
    file_finished = Signal(int, str, str)  # doc_id, filename, saved_path
    file_error = Signal(int, str, str)  # doc_id, filename, error message
    all_finished = Signal(int, int, list, list)  # erfolge, fehler, fehler_liste, erfolgreiche_doc_ids
    progress = Signal(int, int, str)  # current, total, filename
    
    def __init__(self, docs_api: DocumentsAPI, documents: list, target_dir: str):
        super().__init__()
        self.docs_api = docs_api
        self.documents = documents  # List[Document]
        self.target_dir = target_dir
        self._cancelled = False
    
    def cancel(self):
        """Bricht den Download ab."""
        self._cancelled = True
    
    def run(self):
        erfolge = 0
        fehler = 0
        fehler_liste = []
        erfolgreiche_doc_ids = []  # IDs der erfolgreich heruntergeladenen Dokumente
        total = len(self.documents)
        
        for i, doc in enumerate(self.documents):
            if self._cancelled:
                break
            
            self.progress.emit(i + 1, total, doc.original_filename)
            
            try:
                result = self.docs_api.download(
                    doc.id, self.target_dir,
                    filename_override=doc.original_filename
                )
                if result:
                    self.file_finished.emit(doc.id, doc.original_filename, result)
                    erfolgreiche_doc_ids.append(doc.id)
                    erfolge += 1
                else:
                    error_msg = "Download fehlgeschlagen"
                    self.file_error.emit(doc.id, doc.original_filename, error_msg)
                    fehler_liste.append(f"{doc.original_filename}: {error_msg}")
                    fehler += 1
            except Exception as e:
                error_msg = str(e)
                self.file_error.emit(doc.id, doc.original_filename, error_msg)
                fehler_liste.append(f"{doc.original_filename}: {error_msg}")
                fehler += 1
        
        self.all_finished.emit(erfolge, fehler, fehler_liste, erfolgreiche_doc_ids)


class BoxDownloadWorker(QThread):
    """
    Worker zum Herunterladen aller Dokumente einer Box.
    
    Laedt alle nicht-archivierten Dokumente aus einer Box herunter.
    Optional: ZIP-Erstellung nach Download.
    """
    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(int, int, list, list)  # erfolge, fehler, fehler_liste, erfolgreiche_doc_ids
    status = Signal(str)  # Status-Meldung (z.B. "Erstelle ZIP...")
    error = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI, box_type: str, 
                 target_path: str, mode: str = 'folder'):
        """
        Args:
            docs_api: DocumentsAPI-Instanz
            box_type: Box-Typ ('gdv', 'courtage', etc.)
            target_path: Ziel-Pfad (Ordner fuer 'folder', .zip Datei fuer 'zip')
            mode: 'zip' oder 'folder'
        """
        super().__init__()
        self.docs_api = docs_api
        self.box_type = box_type
        self.target_path = target_path
        self.mode = mode
        self._cancelled = False
    
    def cancel(self):
        """Bricht den Download ab."""
        self._cancelled = True
    
    def run(self):
        import zipfile
        
        try:
            # 1. Alle nicht-archivierten Dokumente der Box laden
            documents = self.docs_api.list_documents(
                box_type=self.box_type, 
                is_archived=False
            )
            
            if not documents:
                self.finished.emit(0, 0, [], [])
                return
            
            total = len(documents)
            erfolge = 0
            fehler = 0
            fehler_liste = []
            erfolgreiche_doc_ids = []
            
            # 2. Zielverzeichnis bestimmen
            if self.mode == 'zip':
                # Temp-Verzeichnis fuer ZIP-Modus
                temp_dir = tempfile.mkdtemp(prefix='bipro_box_download_')
                download_dir = temp_dir
            else:
                download_dir = self.target_path
                os.makedirs(download_dir, exist_ok=True)
            
            # 3. Dokumente herunterladen
            for i, doc in enumerate(documents):
                if self._cancelled:
                    break
                
                self.progress.emit(i + 1, total, doc.original_filename)
                
                try:
                    result = self.docs_api.download(
                        doc.id, download_dir,
                        filename_override=doc.original_filename
                    )
                    if result:
                        erfolgreiche_doc_ids.append(doc.id)
                        erfolge += 1
                    else:
                        fehler_liste.append(f"{doc.original_filename}: Download fehlgeschlagen")
                        fehler += 1
                except Exception as e:
                    fehler_liste.append(f"{doc.original_filename}: {str(e)}")
                    fehler += 1
            
            # 4. ZIP erstellen wenn gewuenscht
            if self.mode == 'zip' and erfolge > 0 and not self._cancelled:
                from i18n.de import BOX_DOWNLOAD_CREATING_ZIP
                self.status.emit(BOX_DOWNLOAD_CREATING_ZIP)
                
                try:
                    with zipfile.ZipFile(self.target_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for filename in os.listdir(download_dir):
                            file_path = os.path.join(download_dir, filename)
                            if os.path.isfile(file_path):
                                zf.write(file_path, filename)
                except Exception as e:
                    self.error.emit(f"ZIP-Erstellung fehlgeschlagen: {e}")
                    return
                finally:
                    # Temp-Verzeichnis aufraeumen
                    import shutil
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception:
                        pass
            
            self.finished.emit(erfolge, fehler, fehler_liste, erfolgreiche_doc_ids)
            
        except Exception as e:
            self.error.emit(str(e))


class CreditsWorker(QThread):
    """Worker zum Abrufen der KI-Provider Credits/Usage."""
    finished = Signal(object)  # dict oder None
    
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
    
    def run(self):
        try:
            from api.openrouter import OpenRouterClient
            openrouter = OpenRouterClient(self.api_client)
            credits = openrouter.get_credits()
            self.finished.emit(credits)
        except Exception as e:
            logger.debug(f"Credits-Abfrage fehlgeschlagen: {e}")
            self.finished.emit(None)


class CostStatsWorker(QThread):
    """Worker zum Laden der durchschnittlichen Verarbeitungskosten pro Dokument."""
    finished = Signal(float)  # avg_cost_per_document_usd
    
    def __init__(self, api_client):
        super().__init__()
        self._api_client = api_client
    
    def run(self):
        try:
            from api.processing_history import ProcessingHistoryAPI
            history_api = ProcessingHistoryAPI(self._api_client)
            stats = history_api.get_cost_stats()
            if stats:
                avg_cost = float(stats.get('avg_cost_per_document_usd', 0))
                self.finished.emit(avg_cost)
            else:
                self.finished.emit(0.0)
        except Exception as e:
            logger.debug(f"Kosten-Statistik Abfrage fehlgeschlagen: {e}")
            self.finished.emit(0.0)


class DelayedCostWorker(QThread):
    """
    Worker fuer verzoegerten Kosten-Check.
    
    Wartet die angegebene Verzoegerung ab, ruft dann das aktuelle
    OpenRouter-Guthaben ab und berechnet die Kosten.
    """
    finished = Signal(object)  # dict mit Kosten oder None
    countdown = Signal(int)    # Verbleibende Sekunden
    
    def __init__(self, api_client, batch_result, history_entry_id: int, delay_seconds: int = 90):
        super().__init__()
        self.api_client = api_client
        self.batch_result = batch_result
        self.history_entry_id = history_entry_id
        self.delay_seconds = delay_seconds
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        import time
        
        # Countdown abwarten
        for remaining in range(self.delay_seconds, 0, -1):
            if self._cancelled:
                self.finished.emit(None)
                return
            self.countdown.emit(remaining)
            time.sleep(1)
        
        if self._cancelled:
            self.finished.emit(None)
            return
        
        # Jetzt Credits abrufen
        try:
            from api.openrouter import OpenRouterClient
            from services.document_processor import DocumentProcessor
            
            openrouter = OpenRouterClient(self.api_client)
            credits_info = openrouter.get_credits()
            
            if not credits_info:
                logger.warning("Verzoegerter Kosten-Check: Credits-Abfrage fehlgeschlagen")
                self.finished.emit(None)
                return
            
            provider = credits_info.get('provider', 'openrouter')
            if provider == 'openai':
                credits_after = credits_info.get('total_usage', 0.0) or 0.0
            else:
                credits_after = credits_info.get('balance', 0.0)
            
            # Kosten berechnen und in DB loggen
            processor = DocumentProcessor(self.api_client)
            cost_result = processor.log_delayed_costs(
                history_entry_id=self.history_entry_id,
                batch_result=self.batch_result,
                credits_after=credits_after,
                provider=provider
            )
            
            self.finished.emit(cost_result)
            
        except Exception as e:
            logger.error(f"Verzoegerter Kosten-Check fehlgeschlagen: {e}")
            self.finished.emit(None)


class BoxStatsWorker(QThread):
    """Worker zum Laden der Box-Statistiken."""
    finished = Signal(object)  # BoxStats
    error = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI):
        super().__init__()
        self.docs_api = docs_api
    
    def run(self):
        try:
            stats = self.docs_api.get_box_stats()
            self.finished.emit(stats)
        except Exception as e:
            self.error.emit(str(e))


class DocumentMoveWorker(QThread):
    """Worker zum Verschieben von Dokumenten."""
    finished = Signal(int)  # Anzahl verschoben
    error = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI, doc_ids: List[int], target_box: str,
                 processing_status: str = None):
        super().__init__()
        self.docs_api = docs_api
        self.doc_ids = doc_ids
        self.target_box = target_box
        self.processing_status = processing_status
    
    def run(self):
        try:
            moved = self.docs_api.move_documents(
                self.doc_ids, self.target_box,
                processing_status=self.processing_status
            )
            self.finished.emit(moved)
        except Exception as e:
            self.error.emit(str(e))


class DocumentColorWorker(QThread):
    """Worker zum Setzen/Entfernen von Farbmarkierungen im Hintergrund."""
    finished = Signal(int, object)  # count, color (str or None)
    error = Signal(str)

    def __init__(self, docs_api: DocumentsAPI, doc_ids: List[int], color: Optional[str]):
        super().__init__()
        self.docs_api = docs_api
        self.doc_ids = doc_ids
        self.color = color

    def run(self):
        try:
            count = self.docs_api.set_documents_color(self.doc_ids, self.color)
            self.finished.emit(count, self.color)
        except Exception as e:
            self.error.emit(str(e))


class ProcessingWorker(QThread):
    """Worker fuer automatische Dokumentenverarbeitung."""
    finished = Signal(object)  # BatchProcessingResult
    progress = Signal(int, int, str)  # current, total, message
    error = Signal(str)
    
    def __init__(self, api_client: APIClient):
        super().__init__()
        self.api_client = api_client
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        try:
            from services.document_processor import DocumentProcessor
            
            processor = DocumentProcessor(self.api_client)
            
            def on_progress(current, total, msg):
                if not self._cancelled:
                    self.progress.emit(current, total, msg)
            
            # process_inbox gibt jetzt BatchProcessingResult zurueck
            batch_result = processor.process_inbox(progress_callback=on_progress)
            self.finished.emit(batch_result)
            
        except Exception as e:
            logger.exception("ProcessingWorker Fehler")
            self.error.emit(str(e))


class SearchWorker(QThread):
    """
    Worker fuer nicht-blockierende ATLAS Index Volltextsuche.
    
    Fuehrt GET /documents/search?q=... im Hintergrund aus.
    """
    finished = Signal(list)   # List[SearchResult]
    error = Signal(str)       # Fehlermeldung
    
    def __init__(self, api_client: APIClient, query: str, limit: int = 200,
                 include_raw: bool = False, substring: bool = False, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.query = query
        self.limit = limit
        self.include_raw = include_raw
        self.substring = substring
    
    def run(self):
        try:
            docs_api = DocumentsAPI(self.api_client)
            results = docs_api.search_documents(
                self.query, self.limit,
                include_raw=self.include_raw,
                substring=self.substring
            )
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"ATLAS Index Suche fehlgeschlagen: {e}")
            self.error.emit(str(e))


class SmartScanWorker(QThread):
    """Worker fuer SmartScan Versand mit Client-seitigem Chunking."""
    progress = Signal(int, int, str)  # current, total, status
    completed = Signal(int, dict)  # job_id, result  (NICHT 'finished' - wuerde QThread.finished ueberschreiben!)
    error = Signal(str)
    
    def __init__(self, api_client, mode: str, document_ids: list = None,
                 box_type: str = None, archive_after: bool = False,
                 recolor_after: bool = False, recolor_color: str = None):
        super().__init__()
        self._api_client = api_client
        self._mode = mode
        self._document_ids = document_ids
        self._box_type = box_type
        self._archive_after = archive_after
        self._recolor_after = recolor_after
        self._recolor_color = recolor_color
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        import uuid
        try:
            from api.smartscan import SmartScanAPI
            api = SmartScanAPI(self._api_client)
            
            client_request_id = str(uuid.uuid4())[:16]
            
            # Job starten
            result = api.send(
                mode=self._mode,
                document_ids=self._document_ids,
                box_type=self._box_type,
                client_request_id=client_request_id
            )
            
            if not result or not result.get('job_id'):
                self.error.emit("Versand konnte nicht gestartet werden.")
                return
            
            job_id = result['job_id']
            total = result.get('total', 0)
            processed = result.get('processed', 0)
            remaining = result.get('remaining', total)
            
            self.progress.emit(processed, total, "Versendet...")
            
            # Chunks verarbeiten (Server-CHUNK_SIZE=10, daher mehrere Iterationen noetig)
            max_iterations = (total // 5) + 10  # Grosszuegiges Sicherheitslimit
            iteration = 0
            max_chunk_retries = 2
            
            while remaining > 0 and not self._cancelled and iteration < max_iterations:
                iteration += 1
                
                chunk_result = None
                for retry in range(max_chunk_retries + 1):
                    try:
                        chunk_result = api.process_chunk(job_id)
                        if chunk_result and 'remaining' in chunk_result:
                            break
                        logger.warning(f"Chunk-Antwort unvollstaendig (Versuch {retry + 1}): {chunk_result}")
                        chunk_result = None
                    except Exception as e:
                        logger.warning(f"Chunk-Fehler (Versuch {retry + 1}/{max_chunk_retries + 1}): {e}")
                        if retry < max_chunk_retries:
                            import time
                            time.sleep(2 * (retry + 1))
                        else:
                            raise
                
                if not chunk_result or 'remaining' not in chunk_result:
                    self.error.emit("Chunk-Verarbeitung nach Retries fehlgeschlagen.")
                    return
                
                processed += chunk_result.get('processed', 0)
                remaining = chunk_result.get('remaining', 0)
                status = chunk_result.get('status', '')
                
                self.progress.emit(processed, total, f"Versendet: {processed}/{total}")
                
                if remaining == 0 and status in ('sent', 'partial', 'failed'):
                    break
            
            if self._cancelled:
                self.error.emit("Versand abgebrochen.")
                return
            
            # Ergebnis holen
            final = api.get_job_details(job_id)
            
            # Post-Send-Aktionen: Faerben und/oder Archivieren
            if self._document_ids and (self._recolor_after or self._archive_after):
                try:
                    from api.documents import DocumentsAPI
                    docs_api = DocumentsAPI(self._api_client)
                    
                    if self._recolor_after and self._recolor_color:
                        self.progress.emit(processed, total, "Dokumente werden gefaerbt...")
                        docs_api.set_documents_color(self._document_ids, self._recolor_color)
                    
                    if self._archive_after:
                        self.progress.emit(processed, total, "Dokumente werden archiviert...")
                        docs_api.archive_documents(self._document_ids)
                        
                except Exception as e:
                    logger.warning(f"Post-Send-Aktion fehlgeschlagen: {e}")
            
            self.completed.emit(job_id, final or result)
            
        except Exception as e:
            logger.error(f"SmartScan Worker Fehler: {e}")
            self.error.emit(str(e))

class ThumbnailWorker(QThread):
    """Rendert PDF-Thumbnails im Hintergrund, damit die UI nicht blockiert."""
    thumbnail_ready = Signal(int, bytes, int, int)  # page_idx, img_bytes, w, h

    def __init__(self, pdf_path: str, page_count: int):
        super().__init__()
        self._pdf_path = pdf_path
        self._page_count = page_count

    def run(self):
        try:
            import fitz
            try:
                doc = fitz.open(self._pdf_path)
            except Exception:
                with open(self._pdf_path, 'rb') as f:
                    data = f.read()
                doc = fitz.open(stream=data, filetype="pdf")

            for i in range(min(len(doc), self._page_count)):
                page = doc[i]
                zoom = 120.0 / page.rect.width
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                self.thumbnail_ready.emit(i, bytes(pix.samples), pix.width, pix.height)

            doc.close()
        except Exception as e:
            logger.warning(f"Thumbnail-Worker Fehler: {e}")


class DocumentLoadWorker(QThread):
    """Worker zum Laden der Dokumente."""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, docs_api: DocumentsAPI, filters: dict):
        super().__init__()
        self.docs_api = docs_api
        self.filters = filters

    def run(self):
        try:
            docs = self.docs_api.list_documents(**self.filters)
            self.finished.emit(docs)
        except Exception as e:
            self.error.emit(str(e))


class UploadWorker(QThread):
    """Worker zum Hochladen von Dateien."""
    finished = Signal(object)  # Document or None
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, docs_api: DocumentsAPI, file_path: str, source_type: str):
        super().__init__()
        self.docs_api = docs_api
        self.file_path = file_path
        self.source_type = source_type

    def run(self):
        try:
            self.progress.emit("Lade hoch...")
            doc = self.docs_api.upload(self.file_path, self.source_type)
            self.finished.emit(doc)
        except Exception as e:
            self.error.emit(str(e))


class AIRenameWorker(QThread):
    """
    Worker fuer KI-basierte PDF-Benennung.

    Verarbeitet PDFs im Hintergrund mit zweistufigem KI-System:
    1. Laedt PDF herunter
    2. Stufe 1 (Triage): Schnelle Kategorisierung mit GPT-4o-mini
    3. Stufe 2 (Detail): Detailanalyse mit GPT-4o nur bei Bedarf
    4. Umbenennung auf Server
    """
    # Signale
    finished = Signal(list)  # Liste von (doc_id, success, new_name_or_error)
    progress = Signal(int, int, str)  # current, total, current_filename
    single_finished = Signal(int, bool, str)  # doc_id, success, new_name_or_error
    error = Signal(str)

    def __init__(self, api_client, docs_api: DocumentsAPI, documents: List):
        super().__init__()
        self.api_client = api_client
        self.docs_api = docs_api
        self.documents = documents
        self._cancelled = False

    def cancel(self):
        """Abbrechen der Verarbeitung."""
        self._cancelled = True

    def run(self):
        from api.openrouter import OpenRouterClient

        results = []
        total = len(self.documents)

        try:
            # OpenRouter Client initialisieren
            openrouter = OpenRouterClient(self.api_client)

            for i, doc in enumerate(self.documents):
                if self._cancelled:
                    logger.info("KI-Benennung abgebrochen")
                    break

                self.progress.emit(i + 1, total, doc.original_filename)
                logger.info(f"Verarbeite {i+1}/{total}: {doc.original_filename}")

                # Bereits umbenannt? Skip.
                if doc.ai_renamed:
                    logger.info(f"Ueberspringe bereits umbenanntes Dokument: {doc.original_filename}")
                    results.append((doc.id, True, doc.original_filename))
                    self.single_finished.emit(doc.id, True, doc.original_filename)
                    continue

                # Nicht PDF? Skip.
                if not doc.is_pdf:
                    logger.info(f"Ueberspringe Nicht-PDF: {doc.original_filename}")
                    results.append((doc.id, True, doc.original_filename))
                    self.single_finished.emit(doc.id, True, doc.original_filename)
                    continue

                try:
                    # PDF herunterladen (filename_override spart extra API-Call)
                    temp_dir = tempfile.mkdtemp(prefix='bipro_ai_')
                    pdf_path = self.docs_api.download(doc.id, temp_dir, filename_override=doc.original_filename)

                    if not pdf_path or not os.path.exists(pdf_path):
                        raise Exception("Download fehlgeschlagen")

                    # Zweistufige KI-Klassifikation (Triage -> Detail bei Bedarf)
                    classification = openrouter.classify_pdf_smart(pdf_path)
                    logger.info(f"Klassifikation: {classification.target_box} ({classification.confidence})")

                    # Neuen Dateinamen generieren
                    original_ext = os.path.splitext(doc.original_filename)[1] or '.pdf'
                    new_filename = classification.generate_filename(original_ext)

                    # Auf Server umbenennen
                    success = self.docs_api.rename_document(doc.id, new_filename, mark_ai_renamed=True)

                    if success:
                        logger.info(f"Umbenannt: {doc.original_filename} -> {new_filename}")
                        results.append((doc.id, True, new_filename))
                        self.single_finished.emit(doc.id, True, new_filename)
                    else:
                        raise Exception("Server-Update fehlgeschlagen")

                    # Temporaere Dateien aufraeumen
                    try:
                        os.unlink(pdf_path)
                        os.rmdir(temp_dir)
                    except OSError:
                        pass

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Fehler bei {doc.original_filename}: {error_msg}")

                    # Fehler in DB speichern
                    try:
                        self.docs_api.update(doc.id, ai_processing_error=error_msg[:500])
                    except Exception:
                        pass

                    results.append((doc.id, False, error_msg))
                    self.single_finished.emit(doc.id, False, error_msg)

            self.finished.emit(results)

        except Exception as e:
            logger.error(f"AIRenameWorker Fehler: {e}")
            self.error.emit(str(e))


class PDFSaveWorker(QThread):
    """Worker zum asynchronen Speichern eines bearbeiteten PDFs auf dem Server."""
    finished = Signal(bool)   # success
    error = Signal(str)       # error_message

    def __init__(self, docs_api, doc_id: int, file_path: str, parent=None):
        super().__init__(parent)
        self.docs_api = docs_api
        self.doc_id = doc_id
        self.file_path = file_path

    def run(self):
        try:
            success = self.docs_api.replace_document_file(self.doc_id, self.file_path)
            self.finished.emit(success)
        except Exception as e:
            self.error.emit(str(e))


class PDFRefreshWorker(QThread):
    """Aktualisiert Leere-Seiten-Daten und Textinhalt nach PDF-Bearbeitung."""
    finished = Signal(bool)

    def __init__(self, docs_api, doc_id: int, pdf_path: str, parent=None):
        super().__init__(parent)
        self.docs_api = docs_api
        self.doc_id = doc_id
        self.pdf_path = pdf_path

    def run(self):
        try:
            from services.empty_page_detector import get_empty_pages
            empty_indices, total_pages = get_empty_pages(self.pdf_path)
            if total_pages > 0:
                self.docs_api.client.put(
                    f'/documents/{self.doc_id}',
                    json_data={
                        'empty_page_count': len(empty_indices),
                        'total_page_count': total_pages
                    }
                )

            from services.early_text_extract import extract_and_save_text
            extract_and_save_text(self.docs_api, self.doc_id, self.pdf_path)

            self.finished.emit(True)
        except Exception as e:
            logger.error(f"PDF-Refresh nach Bearbeitung fehlgeschlagen fuer Dokument {self.doc_id}: {e}")
            self.finished.emit(False)
