"""
ACENCIA ATLAS - Hauptfenster (Hub)

Modernes Hauptfenster mit Sidebar-Navigation und Bereichen:
- BiPRO Datenabruf
- Dokumentenarchiv  
- GDV Editor

Design: ACENCIA Corporate Identity
- Dunkle Sidebar (#001f3d)
- Orange Akzente (#fa9939)
"""

import os
import logging
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QMessageBox, QSizePolicy, QSpacerItem,
    QProgressDialog
)
from ui.toast import ToastManager
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QFont, QIcon, QPixmap, QDragEnterEvent, QDropEvent

logger = logging.getLogger(__name__)

from api.client import APIClient
from api.auth import AuthAPI
from i18n import de as texts

# ACENCIA Design Tokens
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100,
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD, SPACING_SM, SPACING_MD, SPACING_LG,
    SIDEBAR_WIDTH_INT
)


class UpdateCheckWorker(QThread):
    """Prueft periodisch auf Updates im Hintergrund."""
    update_available = Signal(object)  # UpdateInfo
    
    def __init__(self, api_client: APIClient, current_version: str):
        super().__init__()
        self._api_client = api_client
        self._current_version = current_version
    
    def run(self):
        try:
            from services.update_service import UpdateService
            service = UpdateService(self._api_client)
            info = service.check_for_update(self._current_version)
            if info and (info.update_available or info.mandatory):
                self.update_available.emit(info)
        except Exception:
            pass  # Periodischer Check darf nie crashen


class NotificationPollWorker(QThread):
    """Pollt Notification-Summary im Hintergrund (nicht-blockierend)."""
    finished = Signal(dict)
    
    def __init__(self, messages_api, last_message_ts: str = None):
        super().__init__()
        self._api = messages_api
        self._last_message_ts = last_message_ts
    
    def run(self):
        try:
            summary = self._api.get_notifications_summary(
                last_message_ts=self._last_message_ts
            )
            self.finished.emit(summary)
        except Exception:
            self.finished.emit({})  # Polling-Fehler stillschweigend ignorieren


class NavButton(QPushButton):
    """
    Navigations-Button für die dunkle Sidebar.
    ACENCIA Design: Weiß auf dunkelblau, Orange bei aktiv.
    """
    
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.setText(f"  {icon}  {text}")
        self.setCheckable(True)
        self.setMinimumHeight(48)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
                padding: 12px 16px;
                text-align: left;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {SIDEBAR_TEXT};
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
            }}
            QPushButton:checked {{
                background-color: {SIDEBAR_HOVER};
                border-left: 3px solid {ACCENT_500};
                color: {SIDEBAR_TEXT};
                font-weight: 500;
            }}
        """)


class DropUploadWorker(QThread):
    """Worker-Thread zum Hochladen von per Drag & Drop abgelegten Dateien.
    
    Phase 1: Alle ZIPs/MSGs rekursiv entpacken -> flache Job-Liste
    Phase 2: Parallele Uploads via ThreadPoolExecutor (max. 5 gleichzeitig)
    
    Jeder Upload-Thread bekommt eine eigene requests.Session (thread-safe).
    """

    MAX_UPLOAD_WORKERS = 5

    file_finished = Signal(str, object)   # filename, Document or None
    file_error = Signal(str, str)         # filename, error_message
    all_finished = Signal(int, int)       # erfolge, fehler
    progress = Signal(int, int, str)      # current, total, filename

    def __init__(self, api_client, file_paths: List[str]):
        super().__init__()
        self.api_client = api_client
        self.file_paths = file_paths
        self._cancelled = False
        self._executor = None  # BUG-0025: Referenz fuer cancel()

    def cancel(self):
        """BUG-0025 Fix: Bricht den Upload-Worker ab und stoppt den Executor."""
        self._cancelled = True
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _prepare_single_file(self, fp, jobs, api_client):
        """Bereitet eine Einzeldatei vor: Bild→PDF-Konvertierung + PDF-Unlock.
        
        Bei Bilddateien: konvertiertes PDF wird als Job hinzugefuegt,
        Original als Roh-Archiv-Job. Bei allen anderen: unlock + Job.
        """
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
                jobs.append((pdf_path, None))  # konvertiertes PDF -> Eingangsbox
                jobs.append((fp, 'roh'))        # Original-Bild -> Roh-Archiv
            else:
                jobs.append((fp, None))  # Fallback: Bild direkt hochladen
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

        jobs = []  # (path, box_type)

        for fp in file_paths:
            if is_zip_file(fp):
                td = tempfile.mkdtemp(prefix="atlas_zip_")
                self._temp_dirs.append(td)
                zr = extract_zip_contents(fp, td, api_client=self.api_client)
                if zr.error:
                    self._errors.append((Path(fp).name, zr.error))
                    jobs.append((fp, 'roh'))
                    continue
                for ext in zr.extracted_paths:
                    if is_msg_file(ext):
                        md = tempfile.mkdtemp(prefix="atlas_msg_", dir=td)
                        mr = extract_msg_attachments(ext, md, api_client=self.api_client)
                        if mr.error:
                            self._errors.append((Path(ext).name, mr.error))
                        else:
                            for att in mr.attachment_paths:
                                self._prepare_single_file(att, jobs, self.api_client)
                        jobs.append((ext, 'roh'))  # MSG -> roh
                    else:
                        self._prepare_single_file(ext, jobs, self.api_client)
                jobs.append((fp, 'roh'))  # ZIP -> roh

            elif is_msg_file(fp):
                td = tempfile.mkdtemp(prefix="atlas_msg_")
                self._temp_dirs.append(td)
                mr = extract_msg_attachments(fp, td, api_client=self.api_client)
                if mr.error:
                    self._errors.append((Path(fp).name, mr.error))
                    continue
                for att in mr.attachment_paths:
                    if is_zip_file(att):
                        zd = tempfile.mkdtemp(prefix="atlas_zip_", dir=td)
                        zr = extract_zip_contents(att, zd, api_client=self.api_client)
                        if zr.error:
                            self._errors.append((Path(att).name, zr.error))
                        else:
                            for ext in zr.extracted_paths:
                                self._prepare_single_file(ext, jobs, self.api_client)
                        jobs.append((att, 'roh'))  # ZIP-Anhang -> roh
                    else:
                        self._prepare_single_file(att, jobs, self.api_client)
                jobs.append((fp, 'roh'))  # MSG -> roh

            else:
                self._prepare_single_file(fp, jobs, self.api_client)

        return jobs

    def _upload_single(self, path: str, source_type: str, box_type: str = None):
        """Thread-safe Upload einer einzelnen Datei mit per-Thread API-Client.
        
        BUG-0038 Fix: _thread_apis-Zugriff mit Lock geschuetzt.
        
        Returns:
            (filename, success, doc_or_error_str)
        """
        import threading
        name = Path(path).name
        try:
            # Per-Thread API-Client (eigene requests.Session)
            # BUG-0038 Fix: Zugriff auf _thread_apis mit Lock schuetzen
            tid = threading.get_ident()
            with self._thread_apis_lock:
                if tid not in self._thread_apis:
                    from api.client import APIClient
                    from api.documents import DocumentsAPI
                    client = APIClient(self.api_client.config)
                    client.set_token(self.api_client._token)
                    self._thread_apis[tid] = DocumentsAPI(client)
                docs_api = self._thread_apis[tid]

            if box_type:
                doc = docs_api.upload(path, source_type, box_type=box_type)
            else:
                doc = docs_api.upload(path, source_type)
            if doc:
                # Fruehe Text-Extraktion fuer Inhaltsduplikat-Erkennung
                # Datei ist noch lokal verfuegbar, KI-Verarbeitung ueberschreibt spaeter per Upsert
                if box_type != 'roh':  # Roh-Dateien (MSG, ZIP) nicht extrahieren
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
        import shutil
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self._temp_dirs = []
        self._errors = []  # (filename, error) aus Phase 1
        self._thread_apis = {}  # thread_id -> DocumentsAPI
        self._thread_apis_lock = threading.Lock()  # BUG-0038 Fix: Lock fuer _thread_apis

        # Phase 1: Alle Dateien entpacken (sequentiell, lokal)
        jobs = self._expand_all_files(self.file_paths)
        total = len(jobs)
        self.progress.emit(0, total, "")

        # Fehler aus Phase 1 emittieren
        for name, error in self._errors:
            self.file_error.emit(name, error)

        # BUG-0025: Abbruch-Check nach Phase 1
        if self._cancelled:
            self.all_finished.emit(0, len(self._errors))
            return

        # Phase 2: Parallele Uploads
        erfolge = 0
        fehler = len(self._errors)
        uploaded = 0

        workers = min(self.MAX_UPLOAD_WORKERS, max(1, total))
        # BUG-0025 Fix: Executor-Referenz speichern fuer cancel()
        self._executor = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = {
                self._executor.submit(self._upload_single, path, 'manual_upload', box_type): path
                for path, box_type in jobs
            }
            for future in as_completed(futures):
                # BUG-0025 Fix: Abbruch-Check in der Upload-Schleife
                if self._cancelled:
                    # Verbleibende Futures abbrechen
                    for f in futures:
                        f.cancel()
                    break
                try:
                    name, success, result = future.result()
                except Exception:
                    # Future wurde abgebrochen oder Executor heruntergefahren
                    continue
                uploaded += 1
                self.progress.emit(uploaded, total, name)
                if success:
                    erfolge += 1
                    self.file_finished.emit(name, result)
                else:
                    fehler += 1
                    self.file_error.emit(name, result)
        finally:
            self._executor.shutdown(wait=True)
            self._executor = None

        # Temporaere Verzeichnisse aufraeumen
        for td in self._temp_dirs:
            try:
                shutil.rmtree(td, ignore_errors=True)
            except Exception:
                pass

        self.all_finished.emit(erfolge, fehler)


class MainHub(QMainWindow):
    """
    Hauptfenster der ACENCIA ATLAS Anwendung.
    
    Enthält:
    - Sidebar mit Navigation
    - Stacked Widget für die verschiedenen Bereiche
    - Globales Drag & Drop zum Upload in die Eingangsbox
    """
    
    def __init__(self, api_client: APIClient, auth_api: AuthAPI):
        super().__init__()
        
        self.api_client = api_client
        self.auth_api = auth_api
        
        # Lazy-loaded Views
        self._bipro_view = None
        self._archive_view = None
        self._gdv_view = None
        self._admin_view = None
        self._provision_view = None
        self._message_center_view = None
        self._chat_view = None
        
        # Fenstertitel
        username = auth_api.current_user.username if auth_api.current_user else "Unbekannt"
        self.setWindowTitle(f"ACENCIA ATLAS - {username}")
        self.setMinimumSize(1400, 900)
        
        # Update-Check Worker
        self._update_check_worker: UpdateCheckWorker = None
        
        # Drag & Drop Upload State
        self._drop_upload_worker: Optional[DropUploadWorker] = None
        self._drop_progress: Optional[QProgressDialog] = None
        self._drop_results: dict = {'erfolge': [], 'fehler': [], 'doc_ids': [], 'duplikate': 0}
        self._outlook_temp_dirs: List[str] = []  # Temporaere Outlook-Extraktion
        
        # Drag & Drop aktivieren (globales Fenster)
        self.setAcceptDrops(True)
        
        self._setup_ui()
        
        # Globaler Toast-Manager (oben rechts, gestapelt)
        self._toast_manager = ToastManager(self)
        
        # Periodischer Update-Check (alle 30 Minuten, nur im Release-Modus)
        from main import is_dev_mode
        self._update_timer = QTimer(self)
        if not is_dev_mode():
            self._update_timer.timeout.connect(self._check_for_updates)
            self._update_timer.start(30 * 60 * 1000)  # 30 Minuten
        
        # Notification-Poller (dynamisches Intervall je nach aktiver Ansicht)
        self._POLL_INTERVAL_NORMAL = 30_000   # 30s - Standard (BiPRO, Archiv, GDV, Admin)
        self._POLL_INTERVAL_CENTER = 10_000   # 10s - Mitteilungszentrale aktiv
        self._current_poll_interval = self._POLL_INTERVAL_CENTER  # Start = Zentrale
        
        self._notification_poller_timer = QTimer(self)
        self._notification_poller_timer.timeout.connect(self._poll_notifications)
        self._last_message_ts = None
        self._prev_unread_chats = 0
        self._prev_unread_system = 0
        self._messages_api = None  # Wird nach Login gesetzt
        self._notification_poll_worker = None  # Worker-Referenz
        self._notification_poller_timer.start(self._POLL_INTERVAL_CENTER)
        # Sofort einmal pollen
        QTimer.singleShot(2000, self._poll_notifications)
        
        # Standardmaeßig Mitteilungszentrale anzeigen (nach Poller-Init!)
        self._show_message_center()
    
    def _setup_ui(self):
        """UI aufbauen mit ACENCIA Corporate Design."""
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Sidebar (Dunkel - ACENCIA Design) ===
        self._sidebar = QFrame()
        sidebar = self._sidebar  # Kurzreferenz fuer Setup
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH_INT)
        sidebar.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {SIDEBAR_BG};
                border: none;
            }}
        """)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(4)
        
        # Logo/Titel Container
        logo_container = QWidget()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(20, 0, 20, 16)
        logo_layout.setSpacing(8)
        logo_layout.setAlignment(Qt.AlignHCenter)
        
        # App-Logo (Bild)
        logo_image = QLabel()
        logo_image.setAlignment(Qt.AlignCenter)
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled = pixmap.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_image.setPixmap(scaled)
        logo_layout.addWidget(logo_image)
        
        # Titel (ACENCIA Style)
        title = QLabel("ACENCIA ATLAS")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Tenor Sans", 14))
        title.setStyleSheet(f"""
            color: {SIDEBAR_TEXT};
            font-family: {FONT_HEADLINE};
            padding: 0;
        """)
        logo_layout.addWidget(title)
        
        # Untertitel
        subtitle = QLabel("Der Datenkern.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            color: {PRIMARY_500};
            font-size: {FONT_SIZE_CAPTION};
            padding: 0;
        """)
        logo_layout.addWidget(subtitle)
        
        sidebar_layout.addWidget(logo_container)
        
        # Benutzer-Info
        if self.auth_api.current_user:
            user_container = QWidget()
            user_layout = QHBoxLayout(user_container)
            user_layout.setContentsMargins(20, 8, 20, 16)
            
            user_label = QLabel(f"● {self.auth_api.current_user.username}")
            user_label.setStyleSheet(f"""
                color: {PRIMARY_500};
                font-size: {FONT_SIZE_CAPTION};
            """)
            user_layout.addWidget(user_label)
            user_layout.addStretch()
            sidebar_layout.addWidget(user_container)
        
        # Navigation Label
        nav_label = QLabel("BEREICHE")
        nav_label.setStyleSheet(f"""
            color: {PRIMARY_500};
            font-size: {FONT_SIZE_CAPTION};
            padding: 16px 20px 8px 20px;
            letter-spacing: 1px;
        """)
        sidebar_layout.addWidget(nav_label)
        
        # Mitteilungszentrale Button (mit Badge)
        self.btn_center = NavButton("🔔", texts.NAV_MESSAGE_CENTER)
        self.btn_center.clicked.connect(self._show_message_center)
        sidebar_layout.addWidget(self.btn_center)
        
        # Notification Badge (roter Kreis mit Zahl)
        self._notification_badge = QLabel("", self.btn_center)
        self._notification_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {ACCENT_500};
                color: white;
                border-radius: 9px;
                padding: 1px 5px;
                font-size: 10px;
                font-weight: bold;
                min-width: 18px;
            }}
        """)
        self._notification_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._notification_badge.setFixedHeight(18)
        self._notification_badge.move(self.btn_center.width() - 36, 6)
        self._notification_badge.hide()
        
        # BiPRO Button
        self.btn_bipro = NavButton("🔄", "BiPRO Datenabruf")
        self.btn_bipro.clicked.connect(self._show_bipro)
        sidebar_layout.addWidget(self.btn_bipro)
        
        # Archiv Button
        self.btn_archive = NavButton("📁", "Dokumentenarchiv")
        self.btn_archive.clicked.connect(self._show_archive)
        sidebar_layout.addWidget(self.btn_archive)
        
        # GDV Editor Button
        self.btn_gdv = NavButton("📄", "GDV Editor")
        self.btn_gdv.clicked.connect(self._show_gdv)
        sidebar_layout.addWidget(self.btn_gdv)
        
        # Provisionsmanagement Button (nur mit provision_access Recht)
        user_prov = self.auth_api.current_user
        if user_prov and user_prov.has_permission('provision_access'):
            self.btn_provision = NavButton("💰", texts.PROVISION_NAV_TITLE)
            self.btn_provision.setToolTip(texts.PROVISION_NAV_TOOLTIP)
            self.btn_provision.clicked.connect(self._show_provision)
            sidebar_layout.addWidget(self.btn_provision)
        else:
            self.btn_provision = None
        
        # Spacer
        sidebar_layout.addStretch()
        
        # === Admin-Bereich (nur fuer Admins) ===
        self._admin_nav_widgets = []
        user = self.auth_api.current_user
        if user and user.is_admin:
            admin_label = QLabel(texts.NAV_ADMIN)
            admin_label.setStyleSheet(f"""
                color: {PRIMARY_500};
                font-size: {FONT_SIZE_CAPTION};
                padding: 16px 20px 8px 20px;
                letter-spacing: 1px;
            """)
            sidebar_layout.addWidget(admin_label)
            self._admin_nav_widgets.append(admin_label)
            
            self.btn_admin = NavButton("👥", texts.NAV_ADMIN_VIEW)
            self.btn_admin.clicked.connect(self._show_admin)
            sidebar_layout.addWidget(self.btn_admin)
            self._admin_nav_widgets.append(self.btn_admin)
        else:
            self.btn_admin = None
        
        # Abmelden Button (auf dunklem Hintergrund)
        logout_container = QWidget()
        logout_layout = QVBoxLayout(logout_container)
        logout_layout.setContentsMargins(16, 16, 16, 0)
        
        logout_btn = QPushButton("Abmelden")
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {PRIMARY_500};
                border-radius: {RADIUS_MD};
                padding: 10px 16px;
                color: {PRIMARY_500};
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
            }}
            QPushButton:hover {{
                background-color: rgba(136, 169, 195, 0.15);
                border-color: {SIDEBAR_TEXT};
                color: {SIDEBAR_TEXT};
            }}
        """)
        logout_btn.clicked.connect(self._on_logout)
        logout_layout.addWidget(logout_btn)
        sidebar_layout.addWidget(logout_container)
        
        main_layout.addWidget(sidebar)
        
        # === Content Area ===
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background-color: {PRIMARY_0};")
        main_layout.addWidget(self.content_stack)
        
        # Placeholder-Widgets (werden bei Bedarf ersetzt)
        # Index 0: Mitteilungszentrale
        self._placeholder_center = self._create_placeholder(texts.MSG_CENTER_TITLE, texts.MSG_CENTER_LOADING)
        self.content_stack.addWidget(self._placeholder_center)      # Index 0
        
        # Index 1: BiPRO
        self._placeholder_bipro = self._create_placeholder("BiPRO Datenabruf", "Wird geladen...")
        self.content_stack.addWidget(self._placeholder_bipro)       # Index 1
        
        # Index 2: Archiv
        self._placeholder_archive = self._create_placeholder("Dokumentenarchiv", "Wird geladen...")
        self.content_stack.addWidget(self._placeholder_archive)     # Index 2
        
        # Index 3: GDV
        self._placeholder_gdv = self._create_placeholder("GDV Editor", "Wird geladen...")
        self.content_stack.addWidget(self._placeholder_gdv)         # Index 3
        
        # Index 4: Provision (nur mit Recht)
        if self.btn_provision:
            self._placeholder_provision = self._create_placeholder(texts.PROVISION_NAV_TITLE, texts.PROVISION_LOADING)
            self.content_stack.addWidget(self._placeholder_provision)  # Index 4
        
        # Index 5: Admin (nur fuer Admins) -- verschoben wg. Provision
        if self.btn_admin:
            self._placeholder_admin = self._create_placeholder(texts.NAV_ADMIN_VIEW, texts.LOADING)
            self.content_stack.addWidget(self._placeholder_admin)   # Index 5 (oder 4 ohne Provision)
        
        # Index 6: Chat (Vollbild) - Placeholder
        self._placeholder_chat = self._create_placeholder(texts.CHAT_TITLE, texts.MSG_CENTER_LOADING)
        self.content_stack.addWidget(self._placeholder_chat)        # dynamischer Index
    
    def _create_placeholder(self, title: str, subtitle: str) -> QWidget:
        """Erstellt ein Placeholder-Widget im ACENCIA Design."""
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {PRIMARY_0};")
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Tenor Sans", 20))
        title_label.setStyleSheet(f"""
            color: {PRIMARY_900};
            font-family: {FONT_HEADLINE};
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet(f"color: {PRIMARY_500};")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_label)
        
        return widget
    
    def _update_nav_buttons(self, active_btn):
        """Aktualisiert die Navigation-Buttons."""
        all_btns = [self.btn_center, self.btn_bipro, self.btn_archive, self.btn_gdv]
        if self.btn_provision:
            all_btns.append(self.btn_provision)
        if self.btn_admin:
            all_btns.append(self.btn_admin)
        for btn in all_btns:
            btn.setChecked(btn == active_btn)
    
    def _show_message_center(self):
        """Zeigt die Mitteilungszentrale."""
        self._update_nav_buttons(self.btn_center)
        
        if self._message_center_view is None:
            from ui.message_center_view import MessageCenterView
            from api.messages import MessagesAPI
            from api.releases import ReleasesAPI
            
            self._messages_api = MessagesAPI(self.api_client)
            releases_api = ReleasesAPI(self.api_client)
            
            self._message_center_view = MessageCenterView(
                self.api_client, releases_api=releases_api
            )
            self._message_center_view._toast_manager = self._toast_manager
            self._message_center_view.set_messages_api(self._messages_api)
            self._message_center_view.set_releases_api(releases_api)
            self._message_center_view.open_chats_requested.connect(self._show_chat)
            
            # Placeholder ersetzen
            self.content_stack.removeWidget(self._placeholder_center)
            self.content_stack.insertWidget(0, self._message_center_view)
        
        self._message_center_view.refresh()
        self.content_stack.setCurrentIndex(0)
        self._set_polling_interval(self._POLL_INTERVAL_CENTER)
        
        # Sofort Badge aktualisieren (System-Meldungen wurden gerade gelesen)
        QTimer.singleShot(1500, self._refresh_badge_after_read)
    
    def _show_bipro(self):
        """Zeigt den BiPRO-Bereich."""
        self._update_nav_buttons(self.btn_bipro)
        
        if self._bipro_view is None:
            from ui.bipro_view import BiPROView
            self._bipro_view = BiPROView(self.api_client)
            self._bipro_view._toast_manager = self._toast_manager
            self._bipro_view.documents_uploaded.connect(self._on_documents_uploaded)
            # Permission Guards setzen
            self._apply_bipro_permissions()
            
            # Placeholder ersetzen
            self.content_stack.removeWidget(self._placeholder_bipro)
            self.content_stack.insertWidget(1, self._bipro_view)
        
        self.content_stack.setCurrentIndex(1)
        self._set_polling_interval(self._POLL_INTERVAL_NORMAL)
    
    def _show_archive(self):
        """Zeigt das Dokumentenarchiv mit Box-System."""
        self._update_nav_buttons(self.btn_archive)
        
        if self._archive_view is None:
            # Neue Box-basierte Archiv-Ansicht verwenden
            from ui.archive_boxes_view import ArchiveBoxesView
            self._archive_view = ArchiveBoxesView(self.api_client, auth_api=self.auth_api)
            self._archive_view._toast_manager = self._toast_manager
            self._archive_view.open_gdv_requested.connect(self._on_open_gdv_from_archive)
            # Permission Guards setzen
            self._apply_archive_permissions()
            
            # Placeholder ersetzen
            self.content_stack.removeWidget(self._placeholder_archive)
            self.content_stack.insertWidget(2, self._archive_view)
        
        self.content_stack.setCurrentIndex(2)
        self._set_polling_interval(self._POLL_INTERVAL_NORMAL)
    
    def _show_gdv(self):
        """Zeigt den GDV-Editor."""
        self._update_nav_buttons(self.btn_gdv)
        
        if self._gdv_view is None:
            from ui.gdv_editor_view import GDVEditorView
            self._gdv_view = GDVEditorView(self.api_client)
            self._gdv_view._toast_manager = self._toast_manager
            # Permission Guards setzen
            self._apply_gdv_permissions()
            
            # Placeholder ersetzen
            self.content_stack.removeWidget(self._placeholder_gdv)
            self.content_stack.insertWidget(3, self._gdv_view)
        
        self.content_stack.setCurrentIndex(3)
        self._set_polling_interval(self._POLL_INTERVAL_NORMAL)
    
    def _show_settings(self):
        """Öffnet den Einstellungen-Dialog."""
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()
    
    def _get_provision_index(self) -> int:
        """Dynamischer Stack-Index fuer Provision (4 wenn vorhanden)."""
        return 4 if self.btn_provision else -1
    
    def _get_admin_index(self) -> int:
        """Dynamischer Stack-Index fuer Admin."""
        base = 4
        if self.btn_provision:
            base += 1
        return base if self.btn_admin else -1
    
    def _get_chat_index(self) -> int:
        """Dynamischer Stack-Index fuer Chat."""
        base = 4
        if self.btn_provision:
            base += 1
        if self.btn_admin:
            base += 1
        return base
    
    def _show_provision(self):
        """Zeigt das Provisionsmanagement (Vollbild mit eigener Sidebar)."""
        if not self.btn_provision:
            return
        self._update_nav_buttons(self.btn_provision)
        idx = self._get_provision_index()
        
        if self._provision_view is None:
            from ui.provision.provision_hub import ProvisionHub
            self._provision_view = ProvisionHub(self.api_client, self.auth_api)
            self._provision_view._toast_manager = self._toast_manager
            self._provision_view.back_requested.connect(self._leave_provision)
            
            self.content_stack.removeWidget(self._placeholder_provision)
            self.content_stack.insertWidget(idx, self._provision_view)
        
        self._sidebar.hide()
        self.content_stack.setCurrentIndex(idx)
        self._set_polling_interval(self._POLL_INTERVAL_NORMAL)
    
    def _leave_provision(self):
        """Verlaesst das Provisionsmanagement."""
        self._sidebar.show()
        self._show_archive()
    
    def _show_admin(self):
        """Zeigt die Administrations-Ansicht (nur fuer Admins).
        
        Blendet die Hauptsidebar aus, da AdminView eine eigene Sidebar hat.
        """
        if not self.btn_admin:
            return
        self._update_nav_buttons(self.btn_admin)
        idx = self._get_admin_index()
        
        if self._admin_view is None:
            from ui.admin import AdminView
            self._admin_view = AdminView(self.api_client, self.auth_api)
            self._admin_view._toast_manager = self._toast_manager
            self._admin_view.back_requested.connect(self._leave_admin)
            
            self.content_stack.removeWidget(self._placeholder_admin)
            self.content_stack.insertWidget(idx, self._admin_view)
        
        self._sidebar.hide()
        self.content_stack.setCurrentIndex(idx)
        self._set_polling_interval(self._POLL_INTERVAL_NORMAL)
    
    def _show_chat(self):
        """Zeigt die Chat-Vollbild-Ansicht. Sidebar wird versteckt (wie Admin)."""
        if self._chat_view is None:
            from ui.chat_view import ChatView
            from api.chat import ChatAPI
            
            chat_api = ChatAPI(self.api_client)
            self._chat_view = ChatView(chat_api)
            self._chat_view._toast_manager = self._toast_manager
            self._chat_view.back_requested.connect(self._leave_chat)
            
            chat_idx = self._get_chat_index()
            self.content_stack.removeWidget(self._placeholder_chat)
            self.content_stack.insertWidget(chat_idx, self._chat_view)
        
        self._chat_view.refresh()
        self._sidebar.hide()
        chat_idx = self._get_chat_index()
        self.content_stack.setCurrentIndex(chat_idx)
        # Notification-Poller pausieren - ChatRefreshWorker uebernimmt
        self._set_polling_interval(0)
        # Chat-View Auto-Refresh starten (3s Nachrichten-Polling)
        self._chat_view.start_auto_refresh()
    
    def _leave_chat(self):
        """Verlaesst den Chat und zeigt die Mitteilungszentrale."""
        # Chat Auto-Refresh stoppen
        if self._chat_view:
            self._chat_view.stop_auto_refresh()
        self._sidebar.show()
        # Notification-Poller sofort wieder starten + Badge aktualisieren
        self._poll_notifications()
        self._show_message_center()
    
    def _leave_admin(self):
        """Verlässt den Admin-Bereich und zeigt die Hauptsidebar wieder an."""
        self._sidebar.show()
        # SmartScan-Status neu laden (Admin koennte ihn geaendert haben)
        if self._archive_view and hasattr(self._archive_view, '_load_smartscan_status'):
            self._archive_view._load_smartscan_status()
            self._archive_view.sidebar._smartscan_enabled = self._archive_view._smartscan_enabled
        # Zurueck zum Dokumentenarchiv (Standardbereich)
        self._show_archive()
    
    # ================================================================
    # Permission Guards
    # ================================================================
    
    def _apply_bipro_permissions(self):
        """Deaktiviert BiPRO-Buttons basierend auf Rechten."""
        user = self.auth_api.current_user
        if not user:
            return
        
        view = self._bipro_view
        if not view:
            return
        
        if not user.has_permission('bipro_fetch'):
            # Abruf-Buttons deaktivieren
            for attr in ['mail_fetch_btn', 'download_btn', 'download_all_btn', 'fetch_all_vus_btn', 'acknowledge_btn']:
                btn = getattr(view, attr, None)
                if btn:
                    btn.setEnabled(False)
                    btn.setToolTip(texts.PERM_DENIED_BIPRO)
        
        if not user.has_permission('vu_connections_manage'):
            # VU-Verwaltung: Neue-Verbindung-Button deaktivieren falls vorhanden
            for attr in ['derive_btn']:
                btn = getattr(view, attr, None)
                if btn:
                    btn.setEnabled(False)
                    btn.setToolTip(texts.PERM_DENIED_VU)
    
    def _apply_archive_permissions(self):
        """Deaktiviert Archiv-Buttons basierend auf Rechten."""
        user = self.auth_api.current_user
        if not user:
            return
        
        view = self._archive_view
        if not view:
            return
        
        if not user.has_permission('documents_upload'):
            btn = getattr(view, 'upload_btn', None)
            if btn:
                btn.setEnabled(False)
                btn.setToolTip(texts.PERM_DENIED_UPLOAD)
        
        if not user.has_permission('documents_download'):
            btn = getattr(view, 'download_btn', None)
            if btn:
                btn.setEnabled(False)
                btn.setToolTip(texts.PERM_DENIED_DOWNLOAD)
        
        if not user.has_permission('documents_process'):
            btn = getattr(view, 'process_btn', None)
            if btn:
                btn.setEnabled(False)
                btn.setToolTip(texts.PERM_DENIED_PROCESS)
    
    def _apply_gdv_permissions(self):
        """Deaktiviert GDV-Editor-Buttons basierend auf Rechten."""
        user = self.auth_api.current_user
        if not user:
            return
        
        view = self._gdv_view
        if not view:
            return
        
        if not user.has_permission('gdv_edit'):
            # Speichern-Button deaktivieren falls vorhanden
            for attr in ['save_btn', 'btn_save', '_save_btn']:
                btn = getattr(view, attr, None)
                if btn:
                    btn.setEnabled(False)
                    btn.setToolTip(texts.PERM_DENIED_GDV)
    
    def _on_documents_uploaded(self):
        """Callback wenn neue Dokumente hochgeladen wurden."""
        # Archiv-View aktualisieren falls geladen
        if self._archive_view:
            # ArchiveBoxesView verwendet _refresh_all()
            if hasattr(self._archive_view, '_refresh_all'):
                self._archive_view._refresh_all()
            elif hasattr(self._archive_view, 'refresh_documents'):
                self._archive_view.refresh_documents()
    
    def _on_open_gdv_from_archive(self, doc_id: int, filename: str):
        """Öffnet eine GDV-Datei aus dem Archiv im Editor."""
        # Zum GDV-Editor wechseln
        self._show_gdv()
        
        # Datei laden
        if self._gdv_view:
            self._gdv_view.load_from_server(doc_id, filename)
    
    def _on_logout(self):
        """Benutzer abmelden."""
        reply = QMessageBox.question(
            self,
            "Abmelden",
            "Wirklich abmelden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.auth_api.logout()
            self.close()
    
    # ================================================================
    # Notification Polling (dynamisches Intervall)
    # ================================================================
    
    def _set_polling_interval(self, interval_ms: int):
        """Setzt das Polling-Intervall dynamisch.
        
        Wird bei jedem View-Wechsel aufgerufen:
        - 30s normal (BiPRO, Archiv, GDV, Admin)
        - 10s Mitteilungszentrale
        - 0 (pausiert) Chat-Ansicht (ChatRefreshWorker uebernimmt)
        """
        if interval_ms == 0:
            # Pausieren (z.B. wenn ChatView eigenen Refresh hat)
            self._notification_poller_timer.stop()
            self._current_poll_interval = 0
            return
        
        was_stopped = self._current_poll_interval == 0
        if interval_ms != self._current_poll_interval:
            self._current_poll_interval = interval_ms
            self._notification_poller_timer.setInterval(interval_ms)
            if was_stopped:
                self._notification_poller_timer.start(interval_ms)
            # Sofort pollen beim Wechsel auf schnelleres Intervall
            if interval_ms < self._POLL_INTERVAL_NORMAL:
                self._poll_notifications()
    
    def _poll_notifications(self):
        """Polling: Startet Worker fuer nicht-blockierenden API-Call."""
        if not self._messages_api:
            try:
                from api.messages import MessagesAPI
                self._messages_api = MessagesAPI(self.api_client)
            except Exception:
                return
        
        if not self.api_client.is_authenticated():
            return
        
        # Nicht starten wenn bereits ein Poll laeuft
        if self._notification_poll_worker and self._notification_poll_worker.isRunning():
            return
        
        self._notification_poll_worker = NotificationPollWorker(
            self._messages_api, self._last_message_ts
        )
        self._notification_poll_worker.finished.connect(self._on_notification_poll_finished)
        self._notification_poll_worker.start()
    
    def _on_notification_poll_finished(self, summary: dict):
        """Callback wenn Notification-Poll abgeschlossen (Main-Thread)."""
        if not summary:
            return
        
        unread_chats = summary.get('unread_chats', 0)
        unread_system = summary.get('unread_system_messages', 0)
        
        # Badge aktualisieren
        total_unread = unread_chats + unread_system
        self._update_notification_badge(total_unread)
        
        # MessageCenterView aktualisieren
        if self._message_center_view:
            self._message_center_view.update_unread_count(unread_chats)
        
        # Toast bei neuer Chat-Nachricht
        latest = summary.get('latest_chat_message')
        if latest and unread_chats > self._prev_unread_chats:
            sender = latest.get('sender_name', '')
            preview = latest.get('preview', '')
            conv_id = latest.get('conversation_id', 0)
            
            # Kein Toast wenn User gerade in demselben Chat ist
            if not (self._chat_view and self._chat_view._current_conv_id == conv_id
                    and self._sidebar.isHidden()):
                self._toast_manager.show_info(
                    texts.MSG_CENTER_NEW_CHAT_MESSAGE.format(sender=sender),
                    action_text=texts.MSG_CENTER_OPEN_CHAT,
                    action_callback=lambda cid=conv_id: self._open_specific_chat(cid)
                )
            
            # Timestamp merken fuer Deduplizierung
            if latest.get('created_at'):
                self._last_message_ts = latest['created_at']
        
        self._prev_unread_chats = unread_chats
        self._prev_unread_system = unread_system
    
    def _update_notification_badge(self, count: int):
        """Aktualisiert den Badge auf dem Mitteilungszentrale-Button."""
        if count > 0:
            self._notification_badge.setText(str(min(count, 99)))
            self._notification_badge.show()
            # Position neu berechnen
            btn_w = self.btn_center.width()
            self._notification_badge.move(max(btn_w - 36, 120), 6)
        else:
            self._notification_badge.hide()
    
    def _refresh_badge_after_read(self):
        """Badge sofort aktualisieren nachdem Nachrichten gelesen wurden."""
        self._poll_notifications()
    
    def _open_specific_chat(self, conversation_id: int):
        """Oeffnet einen bestimmten Chat (z.B. von Toast-Klick)."""
        self._show_chat()
        if self._chat_view:
            self._chat_view.open_conversation(conversation_id)
    
    # ================================================================
    # Periodischer Update-Check
    # ================================================================
    
    def _check_for_updates(self):
        """Periodischer Update-Check (non-blocking, im Worker-Thread)."""
        if self._update_check_worker and self._update_check_worker.isRunning():
            return  # Bereits ein Check in Arbeit
        
        from main import APP_VERSION
        self._update_check_worker = UpdateCheckWorker(self.api_client, APP_VERSION)
        self._update_check_worker.update_available.connect(self._on_update_available)
        self._update_check_worker.start()
    
    def _on_update_available(self, update_info):
        """Wird aufgerufen wenn ein Update verfuegbar ist."""
        from services.update_service import UpdateService
        from ui.update_dialog import UpdateDialog
        
        update_service = UpdateService(self.api_client)
        
        if update_info.mandatory:
            # Pflicht-Update: Modaler Dialog
            dialog = UpdateDialog(update_info, update_service, mode='mandatory', parent=self)
            dialog.exec()
            # Nach Pflicht-Update: App beenden
            import sys
            sys.exit(0)
        else:
            # Optionales Update: Dezente Benachrichtigung via Dialog
            from PySide6.QtWidgets import QDialog as _QDialog
            dialog = UpdateDialog(update_info, update_service, mode='optional', parent=self)
            if dialog.exec() == _QDialog.DialogCode.Accepted:
                import sys
                sys.exit(0)
    
    # ================================================================
    # Globales Drag & Drop → Eingangsbox Upload
    # ================================================================

    def _has_outlook_data(self, mime_data) -> bool:
        """Prueft ob Outlook E-Mail-Daten im Drag & Drop enthalten sind."""
        for fmt in mime_data.formats():
            if 'FileGroupDescriptorW' in fmt:
                return True
        return False

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Akzeptiert Drag-Events mit Datei-URLs oder Outlook E-Mails."""
        if event.mimeData().hasUrls() or self._has_outlook_data(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Haelt den Drop-Indikator waehrend des Ziehens aktiv."""
        if event.mimeData().hasUrls() or self._has_outlook_data(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Verarbeitet den Drop: Dateien/Ordner/Outlook-Mails sammeln und hochladen."""
        mime = event.mimeData()
        has_urls = mime.hasUrls()
        has_outlook = self._has_outlook_data(mime)

        if not has_urls and not has_outlook:
            event.ignore()
            return

        # Permission pruefen
        user = self.auth_api.current_user
        if not user or not user.has_permission('documents_upload'):
            self._toast_manager.show_warning(texts.DROP_UPLOAD_NO_PERMISSION)
            event.ignore()
            return

        # Bereits ein Upload aktiv?
        if self._drop_upload_worker and self._drop_upload_worker.isRunning():
            event.ignore()
            return

        # Pfade sammeln (Explorer-Dateien und/oder Outlook-Mails)
        paths: List[str] = []

        if has_urls:
            for url in mime.urls():
                local = url.toLocalFile()
                if local:
                    paths.append(local)

        if has_outlook and not paths:
            # Outlook-Drop: E-Mails als temporaere .msg Dateien extrahieren
            outlook_files = self._extract_outlook_emails(mime)
            paths.extend(outlook_files)

        if not paths:
            event.ignore()
            return

        event.acceptProposedAction()

        # Dateien sammeln (Ordner rekursiv durchlaufen)
        file_paths = self._collect_files_from_paths(paths)

        if not file_paths:
            self._toast_manager.show_info(texts.DROP_UPLOAD_NO_FILES)
            return

        logger.info(f"Drag & Drop Upload: {len(file_paths)} Datei(en) aus {len(paths)} Element(en)")
        self._start_drop_upload(file_paths)

    def _cleanup_outlook_temp_dir(self, temp_dir: str):
        """Raeumt ein einzelnes Outlook-Temp-Verzeichnis sofort auf."""
        import shutil
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        if temp_dir in self._outlook_temp_dirs:
            self._outlook_temp_dirs.remove(temp_dir)

    def _extract_outlook_emails(self, mime_data) -> List[str]:
        """
        Extrahiert E-Mails aus Outlook Drag & Drop als temporaere .msg Dateien.
        
        Outlook liefert E-Mails nicht als Dateipfade, sondern im OLE-Format.
        Qt kann die OLE-Streams nicht korrekt lesen (FileContents liefert leere Daten).
        
        Daher: Zugriff auf Outlook per COM-Automation (pywin32).
        Die aktuell in Outlook ausgewaehlten E-Mails werden als .msg gespeichert.
        """
        import tempfile

        temp_dir = tempfile.mkdtemp(prefix="atlas_outlook_")
        self._outlook_temp_dirs.append(temp_dir)

        try:
            import win32com.client
            import pythoncom
        except ImportError:
            logger.error("pywin32 nicht installiert - Outlook Drag & Drop nicht verfuegbar")
            self._toast_manager.show_warning(texts.OUTLOOK_DROP_NO_PYWIN32)
            self._cleanup_outlook_temp_dir(temp_dir)
            return []

        try:
            # COM im aktuellen Thread initialisieren (fuer den Main-Thread)
            pythoncom.CoInitialize()

            # Aktive Outlook-Instanz holen (laeuft bereits, da User daraus zieht)
            outlook = win32com.client.GetActiveObject("Outlook.Application")
            explorer = outlook.ActiveExplorer()

            if not explorer or not explorer.Selection:
                logger.warning("Outlook-Drop: Keine E-Mail-Auswahl in Outlook gefunden")
                self._cleanup_outlook_temp_dir(temp_dir)
                return []

            selection = explorer.Selection
            count = selection.Count
            if count == 0:
                self._cleanup_outlook_temp_dir(temp_dir)
                return []

            logger.info(f"Outlook-Drop: {count} E-Mail(s) in Outlook ausgewaehlt")

            OL_MSG_FORMAT = 3  # olMSG
            temp_files: List[str] = []

            for i in range(1, count + 1):  # COM-Collections sind 1-basiert
                try:
                    item = selection.Item(i)
                    subject = getattr(item, 'Subject', f'email_{i}') or f'email_{i}'

                    # Dateiname bereinigen
                    filename = self._sanitize_outlook_filename(subject) + '.msg'
                    target_path = os.path.join(temp_dir, filename)

                    # Eindeutiger Pfad bei Namenskollision
                    if os.path.exists(target_path):
                        base, ext = os.path.splitext(target_path)
                        n = 2
                        while os.path.exists(f"{base}_{n}{ext}"):
                            n += 1
                        target_path = f"{base}_{n}{ext}"

                    item.SaveAs(target_path, OL_MSG_FORMAT)
                    temp_files.append(target_path)

                    size = os.path.getsize(target_path)
                    logger.info(f"Outlook E-Mail gespeichert: {filename} ({size} Bytes)")

                except Exception as e:
                    logger.warning(f"Outlook-Drop: E-Mail {i} konnte nicht gespeichert werden: {e}")
                    continue

            # Wenn keine Dateien extrahiert, temp_dir sofort aufraeumen
            if not temp_files:
                self._cleanup_outlook_temp_dir(temp_dir)

            return temp_files

        except Exception as e:
            logger.error(f"Outlook COM-Fehler: {e}")
            self._toast_manager.show_error(texts.OUTLOOK_DROP_COM_ERROR.format(error=str(e)))
            self._cleanup_outlook_temp_dir(temp_dir)
            return []

        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    @staticmethod
    def _sanitize_outlook_filename(subject: str) -> str:
        """Bereinigt einen Outlook-Betreff fuer die Verwendung als Dateiname."""
        for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t']:
            subject = subject.replace(ch, '_')
        # Mehrfache Unterstriche zusammenfassen
        while '__' in subject:
            subject = subject.replace('__', '_')
        subject = subject.strip(' ._')
        return subject[:200] or 'email'  # Max 200 Zeichen

    def _collect_files_from_paths(self, paths: List[str]) -> List[str]:
        """Sammelt alle Dateien aus Pfaden (Ordner werden rekursiv durchlaufen)."""
        file_paths: List[str] = []
        for p in paths:
            path = Path(p)
            if path.is_file():
                file_paths.append(str(path))
            elif path.is_dir():
                # Ordner rekursiv durchlaufen (alle Dateien, keine versteckten)
                for child in sorted(path.rglob('*')):
                    if child.is_file() and not child.name.startswith('.'):
                        file_paths.append(str(child))
        return file_paths

    def _start_drop_upload(self, file_paths: List[str]):
        """Startet den Upload der gesammelten Dateien in die Eingangsbox."""
        # Auto-Refresh pausieren falls Archiv geladen
        if self._archive_view and hasattr(self._archive_view, '_cache'):
            self._archive_view._cache.pause_auto_refresh()

        # Progress-Dialog
        self._drop_progress = QProgressDialog(
            texts.DROP_UPLOAD_SCANNING,
            texts.DROP_UPLOAD_CANCEL,
            0,
            len(file_paths),
            self
        )
        self._drop_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._drop_progress.setWindowTitle(texts.DROP_UPLOAD_TITLE)
        self._drop_progress.setMinimumDuration(0)
        self._drop_progress.show()

        self._drop_results = {'erfolge': [], 'fehler': [], 'doc_ids': [], 'duplikate': 0}

        # Worker starten
        self._drop_upload_worker = DropUploadWorker(self.api_client, file_paths)
        self._drop_upload_worker.progress.connect(self._on_drop_upload_progress)
        self._drop_upload_worker.file_finished.connect(self._on_drop_file_uploaded)
        self._drop_upload_worker.file_error.connect(self._on_drop_file_error)
        self._drop_upload_worker.all_finished.connect(self._on_drop_upload_finished)
        self._drop_upload_worker.start()

    def _on_drop_upload_progress(self, current: int, total: int, filename: str):
        """Aktualisiert den Progress-Dialog waehrend des Uploads."""
        if self._drop_progress and not self._drop_progress.wasCanceled():
            # Maximum dynamisch anpassen (ZIP/MSG koennen mehr Dateien liefern)
            if total != self._drop_progress.maximum():
                self._drop_progress.setMaximum(total)
            self._drop_progress.setValue(current)
            self._drop_progress.setLabelText(
                texts.DROP_UPLOAD_PROGRESS.format(current=current, total=total, filename=filename)
            )

    def _on_drop_file_uploaded(self, filename: str, doc):
        """Callback bei erfolgreichem Upload einer Datei."""
        self._drop_results['erfolge'].append(filename)
        if doc and hasattr(doc, 'id') and doc.id:
            self._drop_results['doc_ids'].append(doc.id)
        if doc and hasattr(doc, 'is_duplicate') and doc.is_duplicate:
            self._drop_results['duplikate'] += 1

    def _on_drop_file_error(self, filename: str, error: str):
        """Callback bei Upload-Fehler einer Datei."""
        self._drop_results['fehler'].append(f"{filename}: {error}")

    def _on_drop_upload_finished(self, erfolge: int, fehler: int):
        """Callback wenn alle Uploads abgeschlossen sind."""
        if self._drop_progress:
            self._drop_progress.close()
            self._drop_progress = None

        # Archiv-View aktualisieren falls geladen
        self._on_documents_uploaded()

        # Auto-Refresh wieder aktivieren
        if self._archive_view and hasattr(self._archive_view, '_cache'):
            self._archive_view._cache.resume_auto_refresh()

        # Outlook-Temp-Verzeichnisse aufraeumen
        if self._outlook_temp_dirs:
            import shutil
            for td in self._outlook_temp_dirs:
                try:
                    shutil.rmtree(td, ignore_errors=True)
                except Exception:
                    pass
            self._outlook_temp_dirs.clear()

        logger.info(f"Drag & Drop Upload fertig: {erfolge} Erfolg(e), {fehler} Fehler")

        # Duplikat-Toast anzeigen wenn Duplikate erkannt wurden
        dup_count = self._drop_results.get('duplikate', 0)
        if dup_count > 0:
            from i18n.de import DUPLICATE_DETECTED_TOAST
            self._toast_manager.show_warning(
                DUPLICATE_DETECTED_TOAST.format(count=dup_count)
            )

        # Erfolgs-/Fehler-Toast mit Undo-Option
        if erfolge > 0 and fehler == 0:
            self._toast_manager.show_success(
                texts.DROP_UPLOAD_SUCCESS.format(count=erfolge),
                action_text=texts.TOAST_UNDO,
                action_callback=self._on_drop_undo_clicked
            )
        elif erfolge > 0 and fehler > 0:
            self._toast_manager.show_warning(
                texts.DROP_UPLOAD_PARTIAL.format(erfolge=erfolge, fehler=fehler),
                action_text=texts.TOAST_UNDO,
                action_callback=self._on_drop_undo_clicked
            )
        elif fehler > 0:
            self._toast_manager.show_error(
                texts.DROP_UPLOAD_FAILED.format(count=fehler)
            )

    def _on_drop_undo_clicked(self):
        """Rückgängig: Hochgeladene Dokumente wieder entfernen (Bulk-API)."""
        doc_ids = self._drop_results.get('doc_ids', [])
        if not doc_ids:
            return

        from api.documents import DocumentsAPI
        docs_api = DocumentsAPI(self.api_client)

        deleted = docs_api.delete_documents(doc_ids)

        # Ergebnis-Toast (ohne Undo-Button)
        self._toast_manager.show_success(texts.DROP_UPLOAD_UNDONE.format(count=deleted))

        # IDs leeren damit kein doppeltes Undo moeglich
        self._drop_results['doc_ids'] = []

        # Archiv aktualisieren
        self._on_documents_uploaded()

        logger.info(f"Drag & Drop Undo: {deleted}/{len(doc_ids)} Dokument(e) entfernt")

    def resizeEvent(self, event):
        """Toasts bei Fenster-Resize neu positionieren."""
        super().resizeEvent(event)
        if hasattr(self, '_toast_manager'):
            self._toast_manager.reposition()

    def closeEvent(self, event):
        """Fenster schließen."""
        # Pruefen auf blockierende Operationen (KI-Verarbeitung, Kosten-Check, SmartScan, Provision-Import)
        blocking = []
        if self._archive_view and hasattr(self._archive_view, 'get_blocking_operations'):
            blocking.extend(self._archive_view.get_blocking_operations())
        if self._provision_view and hasattr(self._provision_view, 'get_blocking_operations'):
            blocking.extend(self._provision_view.get_blocking_operations())
        if blocking:
            from i18n import de as texts
            msg = texts.CLOSE_BLOCKED_TITLE + "\n\n" + "\n".join(f"- {b}" for b in blocking)
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_warning(msg)
            event.ignore()
            return

        # Prüfen auf ungespeicherte Änderungen im GDV-Editor
        if self._gdv_view and hasattr(self._gdv_view, 'has_unsaved_changes'):
            if self._gdv_view.has_unsaved_changes():
                reply = QMessageBox.question(
                    self,
                    "Ungespeicherte Änderungen",
                    "Es gibt ungespeicherte Änderungen im GDV-Editor.\nWirklich beenden?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
        
        # Worker-Threads aufräumen
        if self._bipro_view and hasattr(self._bipro_view, 'cleanup'):
            self._bipro_view.cleanup()
        
        # Update-Timer stoppen
        if hasattr(self, '_update_timer'):
            self._update_timer.stop()
        
        # Update-Worker aufraumen
        if self._update_check_worker and self._update_check_worker.isRunning():
            self._update_check_worker.quit()
            self._update_check_worker.wait(2000)
        
        # Drop-Upload-Worker aufraumen (BUG-0025 Fix: cancel() statt nur quit())
        if self._drop_upload_worker and self._drop_upload_worker.isRunning():
            self._drop_upload_worker.cancel()
            self._drop_upload_worker.wait(3000)
        
        event.accept()
