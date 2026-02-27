"""
ACENCIA ATLAS - BiPRO Datenabruf View

Ansicht für BiPRO-Verbindungen und Lieferungsabruf.

Design: ACENCIA Corporate Identity
"""

from typing import Optional, List
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QTextEdit, QProgressDialog, QFileDialog,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QCheckBox, QFrame, QProgressBar,
    QScrollArea, QGridLayout,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSettings
from PySide6.QtGui import QFont, QColor, QPainter, QShortcut, QKeySequence

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
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style,
    get_button_danger_style,
)


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


from bipro.workers import (
    FetchShipmentsWorker,
    DownloadShipmentWorker,
    AcknowledgeShipmentWorker,
    MailImportWorker,
    ParallelDownloadManager,
    PreviewAllShipmentsWorker,
)


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
            'download_events': 0,
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
            'download_events': 0,
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
            dl_events = self._stats.get('download_events', 0)
            if dl_events > 0:
                lines.append(f"🔔 {dl_events} Meldung(en) in Handlungsaufforderungen")
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
    # Signal wenn Navigation zum Archiv gewünscht
    request_archive_view = Signal()
    
    def __init__(self, api_client: APIClient, parent=None,
                 is_admin: bool = False, username: str = ""):
        super().__init__(parent)
        
        self.api_client = api_client
        self.vu_api = VUConnectionsAPI(api_client)
        self.docs_api = DocumentsAPI(api_client)
        self._is_admin = is_admin
        self._username = username
        
        # Cache-Service fuer VU-Verbindungen
        from services.data_cache import get_cache_service
        self._cache = get_cache_service(api_client)
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
        self._parallel_manager = None
        self._acknowledge_worker = None
        self._mail_import_worker = None
        self._mail_progress_toast = None
        self._preview_worker = None
        self._download_queue = []
        self._download_stats = {}
        
        # "Alle VUs abholen" State Machine
        self._all_vus_mode = False
        self._vu_queue: list = []
        self._all_vus_current_index = 0
        self._all_vus_total = 0
        self._all_vus_stats = {
            'vus_processed': 0, 'total_shipments': 0, 'total_docs': 0,
            'total_events': 0, 'vus_skipped': 0
        }
        
        # Unified Fetch State (VU + Mail parallel)
        self._unified_fetch_active = False
        self._unified_mail_done = False
        self._unified_vus_done = False
        self._unified_mail_docs = 0
        
        # View-Mode: Standard vs Admin
        self._admin_view_active = False
        
        # Preview-Cache
        self._preview_cache: list = []
        self._preview_cache_time: float = 0
        self._PREVIEW_CACHE_TTL = 180  # 3 Minuten
        self._last_manual_refresh_time: float = 0  # Rate-Limit: 30s Cooldown
        
        # Letzter Abruf / Letzte Quittierung (aus QSettings)
        self._last_fetch_info = self._load_fetch_info()
        self._last_ack_info = self._load_ack_info()
        
        # Liste aller aktiven Worker fuer sauberes Cleanup
        self._active_workers: list = []
        
        # Widget-Listen fuer View-Toggle
        self._admin_only_widgets: list = []
        self._standard_only_widgets: list = []
        
        self._setup_ui()
        
        # Progress-Overlay erstellen
        self._progress_overlay = BiPROProgressOverlay(self)
        self._progress_overlay.close_requested.connect(self._on_progress_overlay_closed)
        
        self._load_connections(force_refresh=False)
        
        # Auto-Preview starten
        self._start_preview_load()
    
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
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.quit()
            self._preview_worker.wait(1000)
    
    def closeEvent(self, event):
        """Wird aufgerufen wenn das Widget geschlossen wird."""
        self.cleanup()
        super().closeEvent(event)
    
    def resizeEvent(self, event):
        """Passt das Progress-Overlay und die Karten-Anordnung an die Fenstergroesse an."""
        super().resizeEvent(event)
        if hasattr(self, '_progress_overlay'):
            self._progress_overlay.setGeometry(self.rect())
        if hasattr(self, '_preview_cache') and self._preview_cache:
            self._render_preview_cards(self._preview_cache)
    
    def _on_progress_overlay_closed(self):
        """Callback wenn das Progress-Overlay geschlossen wird."""
        # Dokumenten-Liste aktualisieren
        self.documents_uploaded.emit()
    
    def _setup_ui(self):
        """UI aufbauen -- Standard-View (einfach) + Admin-View (technisch)."""
        from i18n.de import (
            BIPRO_HEADER, BIPRO_VIEW_TOGGLE_STANDARD, BIPRO_VIEW_TOGGLE_ADMIN,
            BIPRO_FETCH_ALL, BIPRO_FETCH_ALL_TOOLTIP, BIPRO_FETCH_ALL_LAST_INFO,
            BIPRO_MAIL_FETCH_TOOLTIP,
            BIPRO_FETCH_ONLY_MAIL, BIPRO_FETCH_ONLY_VU,
            BIPRO_SHOW_DETAILS, BIPRO_HIDE_DETAILS, BIPRO_GO_TO_ARCHIVE,
            BIPRO_ACK_BUTTON, BIPRO_ACK_LAST_INFO,
            BIPRO_PREVIEW_REFRESH, BIPRO_PREVIEW_LOADING, BIPRO_PREVIEW_EMPTY,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Header-Zeile: Titel + Refresh + Admin-Toggle ──
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        header = QLabel(BIPRO_HEADER)
        header.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {TEXT_PRIMARY};
            font-weight: 400;
        """)
        header_row.addWidget(header)

        self._refresh_btn = QPushButton(BIPRO_PREVIEW_REFRESH)
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.setStyleSheet(get_button_ghost_style())
        self._refresh_btn.setToolTip("Vorschau manuell aktualisieren (max. 1x / 30s)")
        self._refresh_btn.clicked.connect(self._on_manual_refresh)
        header_row.addWidget(self._refresh_btn)

        header_row.addStretch()

        self._admin_toggle = QPushButton(BIPRO_VIEW_TOGGLE_STANDARD)
        self._admin_toggle.setFixedHeight(28)
        self._admin_toggle.setCheckable(True)
        self._admin_toggle.setChecked(False)
        self._admin_toggle.setStyleSheet(f"""
            QPushButton {{
                background: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 4px;
                padding: 2px 12px;
                font-size: {FONT_SIZE_CAPTION};
                color: {TEXT_SECONDARY};
            }}
            QPushButton:checked {{
                background: {PRIMARY_900};
                color: white;
                border-color: {PRIMARY_900};
            }}
        """)
        self._admin_toggle.toggled.connect(self._toggle_view_mode)
        self._admin_toggle.setVisible(self._is_admin)
        header_row.addWidget(self._admin_toggle)

        layout.addLayout(header_row)

        # ==============================================================
        # STANDARD VIEW -- Aktions-Buttons, Quittieren, Vorschau-Karten
        # ==============================================================
        self._standard_container = QWidget()
        std_layout = QVBoxLayout(self._standard_container)
        std_layout.setContentsMargins(0, 0, 0, 0)
        std_layout.setSpacing(12)

        # ── Aktions-Buttons ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.fetch_all_vus_btn = QPushButton(BIPRO_FETCH_ALL)
        self.fetch_all_vus_btn.setFixedHeight(44)
        self.fetch_all_vus_btn.setStyleSheet(get_button_primary_style())
        self.fetch_all_vus_btn.setToolTip(BIPRO_FETCH_ALL_TOOLTIP)
        self.fetch_all_vus_btn.setShortcut("F5")
        self.fetch_all_vus_btn.clicked.connect(self._unified_fetch)
        action_bar.addWidget(self.fetch_all_vus_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {BORDER_DEFAULT};")
        action_bar.addWidget(sep)

        self.mail_fetch_btn = QPushButton(BIPRO_FETCH_ONLY_MAIL)
        self.mail_fetch_btn.setFixedHeight(30)
        self.mail_fetch_btn.setStyleSheet(get_button_secondary_style())
        self.mail_fetch_btn.setToolTip(BIPRO_MAIL_FETCH_TOOLTIP)
        self.mail_fetch_btn.clicked.connect(self._fetch_mails)
        action_bar.addWidget(self.mail_fetch_btn)

        self.fetch_single_vu_btn = QPushButton(BIPRO_FETCH_ONLY_VU)
        self.fetch_single_vu_btn.setFixedHeight(30)
        self.fetch_single_vu_btn.setStyleSheet(get_button_secondary_style())
        self.fetch_single_vu_btn.clicked.connect(self._fetch_selected_vu)
        action_bar.addWidget(self.fetch_single_vu_btn)

        action_bar.addStretch()

        self._ack_btn = QPushButton(BIPRO_ACK_BUTTON)
        self._ack_btn.setFixedHeight(36)
        self._ack_btn.setStyleSheet(get_button_danger_style())
        self._ack_btn.setToolTip(
            "Quittiert ALLE gelisteten Lieferungen bei allen Versicherern.\n"
            "ACHTUNG: Quittierte Lieferungen werden vom Server geloescht!"
        )
        self._ack_btn.clicked.connect(self._acknowledge_all_listed)
        action_bar.addWidget(self._ack_btn)

        std_layout.addLayout(action_bar)

        # ── Info-Zeile unter Buttons ──
        info_row = QHBoxLayout()
        info_row.setSpacing(24)

        self._fetch_info_label = QLabel()
        self._fetch_info_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_CAPTION};
            color: {TEXT_SECONDARY};
        """)
        info_row.addWidget(self._fetch_info_label)

        self._ack_info_label = QLabel()
        self._ack_info_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_CAPTION};
            color: {TEXT_SECONDARY};
        """)
        info_row.addWidget(self._ack_info_label)
        info_row.addStretch()
        std_layout.addLayout(info_row)

        self._update_fetch_info_label()
        self._update_ack_info_label()

        # ── Status-Karte (Abruf-Fortschritt) ──
        self._status_card = QFrame()
        self._status_card.setObjectName("statusCard")
        self._status_card.setStyleSheet(f"""
            QFrame#statusCard {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 10px;
                padding: 4px 12px;
            }}
            QFrame#statusCard QLabel {{
                border: none; background: transparent;
            }}
        """)
        status_card_layout = QVBoxLayout(self._status_card)
        status_card_layout.setContentsMargins(12, 6, 12, 6)
        status_card_layout.setSpacing(2)

        self._status_title_label = QLabel()
        self._status_title_label.setStyleSheet(f"""
            font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION};
            color: {TEXT_SECONDARY}; background: transparent; border: none;
        """)
        status_card_layout.addWidget(self._status_title_label)

        self._status_docs_label = QLabel()
        self._status_docs_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_BODY};
            color: {TEXT_PRIMARY}; font-weight: 600;
            background: transparent; border: none;
        """)
        status_card_layout.addWidget(self._status_docs_label)

        self._status_progress_bar = QProgressBar()
        self._status_progress_bar.setVisible(False)
        self._status_progress_bar.setTextVisible(True)
        self._status_progress_bar.setFormat("%p%")
        self._status_progress_bar.setFixedHeight(14)
        self._status_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {PRIMARY_0};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 4px; text-align: center;
                font-size: {FONT_SIZE_CAPTION};
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_500};
                border-radius: 3px;
            }}
        """)
        status_card_layout.addWidget(self._status_progress_bar)

        self._status_detail_label = QLabel()
        self._status_detail_label.setStyleSheet(f"""
            font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION};
            color: {TEXT_SECONDARY}; background: transparent; border: none;
        """)
        self._status_detail_label.setWordWrap(True)
        self._status_detail_label.setVisible(False)
        status_card_layout.addWidget(self._status_detail_label)

        status_action_row = QHBoxLayout()
        self._archive_link_btn = QPushButton(BIPRO_GO_TO_ARCHIVE)
        self._archive_link_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {ACCENT_500};
                border: none; font-weight: 600;
                font-size: {FONT_SIZE_BODY};
                text-decoration: underline; padding: 0;
            }}
            QPushButton:hover {{ color: {PRIMARY_900}; }}
        """)
        self._archive_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._archive_link_btn.setVisible(False)
        self._archive_link_btn.clicked.connect(self.request_archive_view.emit)
        status_action_row.addStretch()
        status_action_row.addWidget(self._archive_link_btn)
        status_card_layout.addLayout(status_action_row)

        self._status_card.setVisible(False)
        std_layout.addWidget(self._status_card)

        self._init_status_card()

        # ── Vorschau-Karten Bereich ──
        self._preview_header_label = QLabel(BIPRO_PREVIEW_LOADING)
        self._preview_header_label.setStyleSheet(f"""
            font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
            color: {TEXT_SECONDARY}; padding: 4px 0;
        """)
        std_layout.addWidget(self._preview_header_label)

        # Zusammenfassungs-Karte (pro VU aggregiert)
        self._preview_summary = QFrame()
        self._preview_summary.setObjectName("previewSummary")
        self._preview_summary.setStyleSheet(f"""
            QFrame#previewSummary {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 10px;
                padding: 12px 16px;
            }}
            QFrame#previewSummary QLabel {{
                border: none; background: transparent;
            }}
        """)
        self._preview_summary_layout = QVBoxLayout(self._preview_summary)
        self._preview_summary_layout.setContentsMargins(12, 8, 12, 8)
        self._preview_summary_layout.setSpacing(4)
        self._preview_summary.setVisible(False)
        std_layout.addWidget(self._preview_summary)

        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._preview_scroll.setMinimumHeight(120)

        self._preview_cards_widget = QWidget()
        self._preview_cards_layout = QGridLayout(self._preview_cards_widget)
        self._preview_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_cards_layout.setHorizontalSpacing(6)
        self._preview_cards_layout.setVerticalSpacing(6)
        self._preview_scroll.setWidget(self._preview_cards_widget)
        std_layout.addWidget(self._preview_scroll, 1)

        layout.addWidget(self._standard_container)

        # ==============================================================
        # ADMIN VIEW -- VU-Verwaltung, Shipment-Tabelle, Log
        # ==============================================================
        self._admin_container = QWidget()
        admin_layout = QVBoxLayout(self._admin_container)
        admin_layout.setContentsMargins(0, 0, 0, 0)
        admin_layout.setSpacing(8)

        # Splitter: VU-Liste links, Shipment-Details rechts
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # -- Linke Seite: Verbindungen --
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

        conn_buttons = QHBoxLayout()
        edit_btn = QPushButton("Bearbeiten")
        edit_btn.setStyleSheet(get_button_ghost_style())
        edit_btn.clicked.connect(self._edit_connection)
        conn_buttons.addWidget(edit_btn)
        show_pw_btn = QPushButton("Passwort")
        show_pw_btn.setStyleSheet(get_button_ghost_style())
        show_pw_btn.clicked.connect(self._show_password)
        conn_buttons.addWidget(show_pw_btn)
        delete_btn = QPushButton("Löschen")
        delete_btn.setStyleSheet(get_button_ghost_style())
        delete_btn.clicked.connect(self._delete_connection)
        conn_buttons.addWidget(delete_btn)
        conn_buttons.addStretch()
        left_layout.addLayout(conn_buttons)

        splitter.addWidget(left_widget)

        # -- Rechte Seite: Shipment-Tabelle + Details --
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self._details_toggle_btn = QPushButton(BIPRO_SHOW_DETAILS + "  \u25BE")
        self._details_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SECONDARY};
                border: none; font-size: {FONT_SIZE_BODY};
                text-align: left; padding: 4px 0;
            }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; }}
        """)
        self._details_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._details_toggle_btn.clicked.connect(self._toggle_details)
        right_layout.addWidget(self._details_toggle_btn)

        self._details_widget = QWidget()
        self._details_widget.setVisible(False)
        details_layout = QVBoxLayout(self._details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(6)

        details_toolbar = QHBoxLayout()
        self.download_btn = QPushButton("Ausgewaehlte herunterladen")
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet(get_button_ghost_style())
        self.download_btn.clicked.connect(self._download_selected)
        details_toolbar.addWidget(self.download_btn)
        self.download_all_btn = QPushButton("Alle herunterladen")
        self.download_all_btn.setEnabled(False)
        self.download_all_btn.setStyleSheet(get_button_ghost_style())
        self.download_all_btn.clicked.connect(self._download_all)
        details_toolbar.addWidget(self.download_all_btn)
        self.acknowledge_btn = QPushButton("Ausgewaehlte quittieren")
        self.acknowledge_btn.setToolTip(
            "Quittiert die ausgewaehlten Lieferungen beim Versicherer.\n"
            "ACHTUNG: Quittierte Lieferungen werden vom Server geloescht!"
        )
        self.acknowledge_btn.setEnabled(False)
        self.acknowledge_btn.setStyleSheet(get_button_ghost_style())
        self.acknowledge_btn.clicked.connect(self._acknowledge_selected)
        details_toolbar.addWidget(self.acknowledge_btn)
        details_toolbar.addStretch()
        details_layout.addLayout(details_toolbar)

        self.shipments_table = QTableWidget()
        self.shipments_table.setColumnCount(5)
        self.shipments_table.setHorizontalHeaderLabels([
            "ID", "Eingestellt", "Kategorie", "Verfuegbar bis", "Transfers"
        ])
        tbl_header = self.shipments_table.horizontalHeader()
        tbl_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tbl_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tbl_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tbl_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        tbl_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.shipments_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        details_layout.addWidget(self.shipments_table)

        right_layout.addWidget(self._details_widget)
        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([280, 720])

        admin_layout.addWidget(splitter)

        # Log-Bereich
        log_group = QGroupBox("Protokoll")
        log_inner = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_inner.addWidget(self.log_text)
        admin_layout.addWidget(log_group)

        self._admin_container.setVisible(False)
        layout.addWidget(self._admin_container)

        self._admin_only_widgets = [self._admin_container]
        self._standard_only_widgets = [self._standard_container]

        self._apply_view_mode()
    
    def _log(self, message: str):
        """Nachricht ins Log schreiben."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    # ── View Toggle ──

    def _toggle_view_mode(self, checked: bool):
        """Schaltet zwischen Standard- und Admin-Ansicht."""
        from i18n.de import BIPRO_VIEW_TOGGLE_STANDARD, BIPRO_VIEW_TOGGLE_ADMIN
        self._admin_view_active = checked
        self._admin_toggle.setText(
            BIPRO_VIEW_TOGGLE_ADMIN if checked else BIPRO_VIEW_TOGGLE_STANDARD
        )
        self._apply_view_mode()

    def _apply_view_mode(self):
        """Setzt Sichtbarkeit der UI-Sektionen je nach View-Mode."""
        admin = self._admin_view_active
        for w in self._standard_only_widgets:
            w.setVisible(not admin)
        for w in self._admin_only_widgets:
            w.setVisible(admin)

    # ── Fetch / Ack Info Labels ──

    def _load_fetch_info(self) -> dict:
        settings = QSettings("ACENCIA", "ATLAS")
        return {
            'timestamp': settings.value("bipro/last_fetch_timestamp", ""),
            'user': settings.value("bipro/last_fetch_user", ""),
        }

    def _save_fetch_info(self):
        ts = datetime.now().strftime("%d.%m.%Y %H:%M")
        settings = QSettings("ACENCIA", "ATLAS")
        settings.setValue("bipro/last_fetch_timestamp", ts)
        settings.setValue("bipro/last_fetch_user", self._username)
        self._last_fetch_info = {'timestamp': ts, 'user': self._username}
        self._update_fetch_info_label()

    def _load_ack_info(self) -> dict:
        settings = QSettings("ACENCIA", "ATLAS")
        return {
            'timestamp': settings.value("bipro/last_ack_timestamp", ""),
            'user': settings.value("bipro/last_ack_user", ""),
        }

    def _save_ack_info(self):
        ts = datetime.now().strftime("%d.%m.%Y %H:%M")
        settings = QSettings("ACENCIA", "ATLAS")
        settings.setValue("bipro/last_ack_timestamp", ts)
        settings.setValue("bipro/last_ack_user", self._username)
        self._last_ack_info = {'timestamp': ts, 'user': self._username}
        self._update_ack_info_label()

    def _update_fetch_info_label(self):
        from i18n.de import BIPRO_FETCH_ALL_LAST_INFO
        info = self._last_fetch_info
        if info.get('timestamp'):
            self._fetch_info_label.setText(
                BIPRO_FETCH_ALL_LAST_INFO.format(
                    timestamp=info['timestamp'], user=info.get('user', ''))
            )
        else:
            self._fetch_info_label.setText("")

    def _update_ack_info_label(self):
        from i18n.de import BIPRO_ACK_LAST_INFO
        info = self._last_ack_info
        if info.get('timestamp'):
            self._ack_info_label.setText(
                BIPRO_ACK_LAST_INFO.format(
                    timestamp=info['timestamp'], user=info.get('user', ''))
            )
        else:
            self._ack_info_label.setText("")

    # ── Preview-Karten ──

    def _start_preview_load(self, force: bool = False):
        """Laedt Lieferungs-Vorschau fuer alle VUs (komplett im Hintergrund).

        Args:
            force: True = Cache und Rate-Limit ignorieren (automatischer Aufruf).
                   Manueller Refresh hat ein eigenes 30s-Cooldown.
        """
        import time as _time

        if not force and self._preview_cache and \
                (_time.time() - self._preview_cache_time) < self._PREVIEW_CACHE_TTL:
            self._render_preview_cards(self._preview_cache)
            return

        if self._preview_worker and self._preview_worker.isRunning():
            return

        from i18n.de import BIPRO_PREVIEW_LOADING
        self._preview_header_label.setText(BIPRO_PREVIEW_LOADING)
        self._clear_preview_cards()

        active = [c for c in self._connections if c.is_active]
        if not active:
            from i18n.de import BIPRO_PREVIEW_EMPTY
            self._preview_header_label.setText(BIPRO_PREVIEW_EMPTY)
            return

        self._preview_worker = PreviewAllShipmentsWorker(
            connections=active,
            vu_api=self.vu_api,
            cert_config_loader=self._load_certificate_config,
        )
        self._preview_worker.finished.connect(self._on_preview_loaded)
        self._preview_worker.vu_error.connect(self._on_preview_vu_error)
        self._register_worker(self._preview_worker)
        self._preview_worker.start()

    def _get_credentials_for_connection(self, conn) -> 'Optional[VUCredentials]':
        """Holt Credentials fuer eine VU-Verbindung (ohne UI-Fehler).

        Wird nur fuer synchrone Aktionen verwendet (z.B. Quittierung),
        nicht fuer Preview (dort laueft alles im Worker-Thread).
        """
        if conn.auth_type == 'certificate':
            cert_config = self._load_certificate_config(conn.id)
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
            return self.vu_api.get_credentials(conn.id)
        except Exception:
            return None

    def _on_manual_refresh(self):
        """Manueller Refresh mit 30-Sekunden-Cooldown."""
        import time as _time
        now = _time.time()
        if (now - self._last_manual_refresh_time) < 30:
            remaining = int(30 - (now - self._last_manual_refresh_time))
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_info(
                    f"Bitte {remaining}s warten vor dem naechsten Aktualisieren."
                )
            return
        self._last_manual_refresh_time = now
        self._start_preview_load(force=True)

    def _on_preview_loaded(self, results: list):
        """Callback wenn PreviewAllShipmentsWorker fertig ist."""
        import time as _time
        self._preview_cache = results
        self._preview_cache_time = _time.time()
        self._render_preview_cards(results)

    def _on_preview_vu_error(self, vu_name: str, error_msg: str):
        from i18n.de import BIPRO_PREVIEW_ERROR
        logger.warning(BIPRO_PREVIEW_ERROR.format(vu_name=vu_name) + f": {error_msg}")

    def _clear_preview_cards(self):
        """Entfernt alle Karten aus dem Preview-Grid."""
        while self._preview_cards_layout.count():
            item = self._preview_cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render_preview_cards(self, results: list):
        """Baut Zusammenfassung + Vorschau-Karten aus den Preview-Ergebnissen."""
        from i18n.de import BIPRO_PREVIEW_COUNT, BIPRO_PREVIEW_EMPTY
        self._clear_preview_cards()
        self._clear_preview_summary()

        vu_stats: dict = {}
        cards = []
        for vu_name, shipments in results:
            if vu_name not in vu_stats:
                vu_stats[vu_name] = {'count': 0, 'categories': set()}
            for ship in shipments:
                vu_stats[vu_name]['count'] += 1
                if ship.category:
                    vu_stats[vu_name]['categories'].add(
                        get_category_short_name(ship.category) or ship.category
                    )
                cards.append((vu_name, ship))

        total_shipments = sum(v['count'] for v in vu_stats.values())

        if total_shipments == 0:
            self._preview_header_label.setText(BIPRO_PREVIEW_EMPTY)
            self._preview_summary.setVisible(False)
            return

        self._preview_header_label.setText(
            BIPRO_PREVIEW_COUNT.format(
                count=total_shipments, vu_count=len(vu_stats))
        )
        self._build_preview_summary(vu_stats, total_shipments)

        available_w = self._preview_scroll.viewport().width() or self.width() - 40
        cols = max(1, available_w // 180)
        for i, (vu_name, ship) in enumerate(cards):
            card = self._build_shipment_card(vu_name, ship)
            row, col = divmod(i, cols)
            self._preview_cards_layout.addWidget(card, row, col)

    def _clear_preview_summary(self):
        """Entfernt alle Widgets aus der Zusammenfassungs-Karte."""
        while self._preview_summary_layout.count():
            item = self._preview_summary_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _build_preview_summary(self, vu_stats: dict, total: int):
        """Baut die Zusammenfassungs-Karte oberhalb der Einzelkarten."""
        self._preview_summary.setVisible(True)

        title = QLabel(f"{total} Lieferung(en) verfuegbar")
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-weight: 600;
            font-size: {FONT_SIZE_BODY}; color: {TEXT_PRIMARY};
        """)
        self._preview_summary_layout.addWidget(title)

        for vu_name, stats in vu_stats.items():
            count = stats['count']
            cats = stats['categories']
            cat_text = ", ".join(sorted(cats)[:3])
            if len(cats) > 3:
                cat_text += f" (+{len(cats) - 3})"
            line_text = f"{vu_name}: {count} Lieferung(en)"
            if cat_text:
                line_text += f"  —  {cat_text}"
            line = QLabel(line_text)
            line.setStyleSheet(f"""
                font-size: {FONT_SIZE_CAPTION}; color: {TEXT_SECONDARY};
            """)
            self._preview_summary_layout.addWidget(line)

    def _build_shipment_card(self, vu_name: str, shipment) -> QFrame:
        """Erstellt eine einzelne Vorschau-Karte fuer eine Lieferung."""
        from i18n.de import (
            BIPRO_PREVIEW_CARD_CATEGORY, BIPRO_PREVIEW_CARD_DATE,
        )

        card = QFrame()
        card.setObjectName("shipmentCard")
        card.setMinimumWidth(160)
        card.setStyleSheet(f"""
            QFrame#shipmentCard {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 12px;
                padding: 10px;
            }}
            QFrame#shipmentCard:hover {{
                border-color: {ACCENT_500};
            }}
            QFrame#shipmentCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(3)

        cat_code = shipment.category or ""
        cat_icon = get_category_icon(cat_code) if cat_code else ""
        cat_name = get_category_short_name(cat_code) if cat_code else ""

        vu_label = QLabel(f"{cat_icon} {vu_name}")
        vu_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-weight: 600;
            font-size: {FONT_SIZE_BODY}; color: {TEXT_PRIMARY};
        """)
        card_layout.addWidget(vu_label)

        if cat_name:
            cat_label = QLabel(BIPRO_PREVIEW_CARD_CATEGORY.format(name=cat_name))
            cat_label.setStyleSheet(f"""
                font-size: {FONT_SIZE_CAPTION}; color: {TEXT_SECONDARY};
            """)
            card_layout.addWidget(cat_label)

        date_str = format_date_german(shipment.created_at) if shipment.created_at else ""
        if date_str:
            date_label = QLabel(BIPRO_PREVIEW_CARD_DATE.format(date=date_str))
            date_label.setStyleSheet(f"""
                font-size: {FONT_SIZE_CAPTION}; color: {TEXT_PRIMARY};
            """)
            card_layout.addWidget(date_label)

        return card

    # ── Acknowledge All Listed (Standard-View) ──

    def _acknowledge_all_listed(self):
        """Quittiert alle in der Vorschau gelisteten Lieferungen.

        Strategie: Parallele Batch-Quittierung (ein Worker pro VU mit allen
        Shipment-IDs). Falls einzelne IDs fehlschlagen, werden diese im
        sequentiellen Fallback nochmals einzeln versucht.
        """
        from i18n.de import (
            BIPRO_ACK_ALL_WARNING, BIPRO_ACK_SUCCESS,
            BIPRO_ACK_NO_SHIPMENTS, BIPRO_ACK_BUTTON,
        )

        if not self._preview_cache:
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_info(BIPRO_ACK_NO_SHIPMENTS)
            return

        total = sum(len(ships) for _, ships in self._preview_cache)
        if total == 0:
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_info(BIPRO_ACK_NO_SHIPMENTS)
            return

        reply = QMessageBox.warning(
            self, BIPRO_ACK_BUTTON,
            BIPRO_ACK_ALL_WARNING.format(count=total),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._ack_btn.setEnabled(False)

        vu_batches: list[tuple] = []
        for vu_name, shipments in self._preview_cache:
            if not shipments:
                continue
            conn = self._find_connection_by_name(vu_name)
            if not conn:
                continue
            creds = self._get_credentials_for_connection(conn)
            if not creds:
                continue
            ship_ids = [ship.shipment_id for ship in shipments]
            vu_batches.append((conn, creds, ship_ids))

        if not vu_batches:
            self._ack_btn.setEnabled(True)
            return

        self._ack_all_success = 0
        self._ack_all_total = sum(len(ids) for _, _, ids in vu_batches)
        self._ack_all_vus = set()

        self._acknowledge_all_parallel(vu_batches)

    # ── Parallele Batch-Quittierung ──

    def _acknowledge_all_parallel(self, vu_batches: list[tuple]):
        """Startet pro VU einen Worker mit allen Shipment-IDs (parallel).

        Jeder Worker holt nur einmal einen STS-Token und quittiert damit alle
        IDs seiner VU. Fehlgeschlagene IDs werden fuer den sequentiellen
        Fallback gesammelt.
        """
        import logging
        logger = logging.getLogger(__name__)

        self._ack_parallel_pending = len(vu_batches)
        self._ack_parallel_failed_queue: list[tuple] = []
        self._ack_parallel_workers: list = []

        for conn, creds, ship_ids in vu_batches:
            worker = AcknowledgeShipmentWorker(
                creds, ship_ids,
                sts_url=conn.get_effective_sts_url(),
                transfer_url=conn.get_effective_transfer_url(),
                consumer_id=conn.consumer_id or "",
            )
            vu_name = conn.vu_name
            worker.finished.connect(
                lambda ok, fail, vn=vu_name, c=conn, cr=creds:
                    self._on_ack_parallel_worker_done(vn, ok, fail, c, cr))
            self._register_worker(worker)
            self._ack_parallel_workers.append(worker)
            logger.info("Batch-Quittierung: %s gestartet (%d IDs)", vu_name, len(ship_ids))
            worker.start()

    def _on_ack_parallel_worker_done(self, vu_name: str, ok_ids: list,
                                      fail_ids: list, conn, creds):
        """Callback wenn ein paralleler VU-Worker fertig ist."""
        import logging
        logger = logging.getLogger(__name__)

        if ok_ids:
            self._ack_all_success += len(ok_ids)
            self._ack_all_vus.add(vu_name)

        if fail_ids:
            logger.warning("Batch-Quittierung %s: %d fehlgeschlagen, Fallback geplant",
                           vu_name, len(fail_ids))
            for ship_id in fail_ids:
                self._ack_parallel_failed_queue.append((conn, creds, ship_id))

        self._ack_parallel_pending -= 1
        if self._ack_parallel_pending <= 0:
            if self._ack_parallel_failed_queue:
                logger.info("Starte sequentiellen Fallback fuer %d fehlgeschlagene IDs",
                            len(self._ack_parallel_failed_queue))
                self._acknowledge_all_sequential(self._ack_parallel_failed_queue)
            else:
                self._on_ack_all_finished()

    # ── Sequentieller Fallback ──

    def _acknowledge_all_sequential(self, queue: list[tuple]):
        """Sequentieller Fallback: verarbeitet fehlgeschlagene IDs einzeln."""
        self._ack_all_queue = list(queue)
        self._process_next_ack_all()

    def _find_connection_by_name(self, vu_name: str):
        for conn in self._connections:
            if conn.vu_name == vu_name:
                return conn
        return None

    def _process_next_ack_all(self):
        """Verarbeitet die naechste Quittierung in der Queue (sequentieller Fallback)."""
        if not self._ack_all_queue:
            self._on_ack_all_finished()
            return

        conn, creds, ship_id = self._ack_all_queue.pop(0)
        worker = AcknowledgeShipmentWorker(
            creds, [ship_id],
            sts_url=conn.get_effective_sts_url(),
            transfer_url=conn.get_effective_transfer_url(),
            consumer_id=conn.consumer_id or "",
        )
        worker.finished.connect(lambda ok, fail: self._on_ack_all_item_done(
            conn.vu_name if not fail else "", len(fail) == 0))
        self._register_worker(worker)
        worker.start()
        self._acknowledge_worker = worker

    def _on_ack_all_item_done(self, vu_name: str, success: bool):
        if success:
            self._ack_all_success += 1
            if vu_name:
                self._ack_all_vus.add(vu_name)
        self._process_next_ack_all()

    def _on_ack_all_finished(self):
        from i18n.de import BIPRO_ACK_SUCCESS
        self._ack_btn.setEnabled(True)
        self._save_ack_info()
        self._preview_cache = []
        self._preview_cache_time = 0
        self._start_preview_load(force=True)
        if hasattr(self, '_toast_manager') and self._toast_manager:
            self._toast_manager.show_success(
                BIPRO_ACK_SUCCESS.format(
                    count=self._ack_all_success,
                    vu_count=len(self._ack_all_vus),
                )
            )

    # ── Status-Karte ──
    
    def _init_status_card(self):
        """Initialisiert die Status-Karte mit persistierten Daten."""
        from i18n.de import BIPRO_STATUS_LAST_FETCH, BIPRO_STATUS_LAST_DOCS, BIPRO_STATUS_NO_FETCH
        settings = QSettings("ACENCIA", "ATLAS")
        last_ts = settings.value("bipro/last_fetch_timestamp", "")
        last_docs = settings.value("bipro/last_fetch_docs", 0, type=int)
        
        if last_ts:
            self._status_title_label.setText(BIPRO_STATUS_LAST_FETCH.format(timestamp=last_ts))
            self._status_docs_label.setText(BIPRO_STATUS_LAST_DOCS.format(count=last_docs))
            self._archive_link_btn.setVisible(last_docs > 0)
        else:
            self._status_title_label.setText(BIPRO_STATUS_NO_FETCH)
            self._status_docs_label.setText("")
            self._archive_link_btn.setVisible(False)
    
    def _update_status_card_fetching(self):
        """Setzt Status-Karte in den Abruf-Modus."""
        from i18n.de import BIPRO_STATUS_FETCHING
        self._status_card.setVisible(True)
        self._status_title_label.setText(BIPRO_STATUS_FETCHING)
        self._status_docs_label.setText("")
        self._status_progress_bar.setValue(0)
        self._status_progress_bar.setVisible(True)
        self._status_detail_label.setVisible(True)
        self._status_detail_label.setText("")
        self._archive_link_btn.setVisible(False)
    
    def _update_status_card_progress(self, current: int, total: int, docs: int, detail_text: str = ""):
        """Aktualisiert die Status-Karte waehrend des Abrufs."""
        from i18n.de import BIPRO_STATUS_TOTAL
        if total > 0:
            pct = int((current / total) * 100)
            self._status_progress_bar.setValue(pct)
        self._status_docs_label.setText(BIPRO_STATUS_TOTAL.format(count=docs))
        if detail_text:
            self._status_detail_label.setText(detail_text)
    
    def _update_status_card_complete(self, total_docs: int):
        """Setzt Status-Karte in den Abschluss-Modus und persistiert."""
        from i18n.de import (
            BIPRO_STATUS_LAST_FETCH, BIPRO_STATUS_FETCH_SUCCESS, BIPRO_GO_TO_ARCHIVE
        )
        now_str = datetime.now().strftime("%d.%m.%Y \u2013 %H:%M")
        
        settings = QSettings("ACENCIA", "ATLAS")
        settings.setValue("bipro/last_fetch_timestamp", now_str)
        settings.setValue("bipro/last_fetch_docs", total_docs)
        
        self._status_card.setVisible(True)
        self._status_title_label.setText(BIPRO_STATUS_LAST_FETCH.format(timestamp=now_str))
        self._status_docs_label.setText(BIPRO_STATUS_FETCH_SUCCESS.format(count=total_docs))
        self._status_progress_bar.setVisible(False)
        self._status_detail_label.setVisible(False)
        self._archive_link_btn.setVisible(total_docs > 0)
        
        self._save_fetch_info()
        self._preview_cache = []
        self._preview_cache_time = 0
        
        if total_docs > 0 and hasattr(self, '_toast_manager') and self._toast_manager:
            from i18n.de import BIPRO_STATUS_FETCH_SUCCESS as msg
            self._toast_manager.show_success(
                msg.format(count=total_docs),
                action_text=BIPRO_GO_TO_ARCHIVE,
                action_callback=self.request_archive_view.emit
            )
    
    # ── Details Toggle ──
    
    def _toggle_details(self):
        """Klappt den Details-Bereich ein/aus."""
        from i18n.de import BIPRO_SHOW_DETAILS, BIPRO_HIDE_DETAILS
        visible = not self._details_widget.isVisible()
        self._details_widget.setVisible(visible)
        arrow = "\u25B4" if visible else "\u25BE"
        text = BIPRO_HIDE_DETAILS if visible else BIPRO_SHOW_DETAILS
        self._details_toggle_btn.setText(f"{text}  {arrow}")
    
    # ── Unified Fetch ──
    
    def _unified_fetch(self):
        """Startet den vereinheitlichten Abruf: Alle VUs + Mail-Import parallel."""
        if self._all_vus_mode:
            return
        
        self._unified_fetch_active = True
        self._unified_mail_done = False
        self._unified_vus_done = False
        self._unified_mail_docs = 0
        
        self._update_status_card_fetching()
        
        self._fetch_mails()
        self._fetch_all_vus()
    
    def _check_unified_complete(self):
        """Prueft ob beide Teile des Unified Fetch abgeschlossen sind."""
        if not getattr(self, '_unified_fetch_active', False):
            return
        if not self._unified_mail_done or not self._unified_vus_done:
            return
        
        total_docs = self._all_vus_stats.get('total_docs', 0) + self._unified_mail_docs
        self._update_status_card_complete(total_docs)
        self._unified_fetch_active = False
    
    def _fetch_selected_vu(self):
        """Ruft nur die aktuell ausgewaehlte VU-Verbindung ab."""
        current_item = self.connections_list.currentItem()
        if not current_item:
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_info("Bitte eine VU-Verbindung auswaehlen.")
            return
        self._on_connection_selected(current_item)
    
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
            'total_docs': 0, 'total_events': 0, 'vus_skipped': 0
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
        
        from bipro.workers import FetchShipmentsWorker
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
        self._download_stats = {'success': 0, 'failed': 0, 'docs': 0, 'events': 0, 'retries': 0}

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
                api_client=self.docs_api.client,
                parent=self
            )
            
            self._parallel_manager.progress_updated.connect(self._on_parallel_progress)
            self._parallel_manager.shipment_uploaded.connect(self._on_parallel_shipment_uploaded)
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
        events = stats.get('events', 0)
        
        self._all_vus_stats['vus_processed'] += 1
        self._all_vus_stats['total_shipments'] += success
        self._all_vus_stats['total_docs'] += docs
        self._all_vus_stats['total_events'] += events
        
        vu_log = BIPRO_FETCH_ALL_VU_DONE.format(
            vu_name=vu_name, success=success, docs=docs
        )
        if events > 0:
            vu_log += f", {events} Meldung(en)"
        self._log(vu_log)
        
        # Statistiken ans Overlay uebergeben
        self._progress_overlay._stats['download_success'] = stats.get('success', 0)
        self._progress_overlay._stats['download_failed'] = stats.get('failed', 0)
        self._progress_overlay._stats['download_docs'] = stats.get('docs', 0)
        self._progress_overlay._stats['download_events'] = events
        
        self._cleanup_parallel_manager()
        self._current_credentials = None
        
        QTimer.singleShot(200, self._process_next_vu)
    
    def _on_all_vus_download_error(self, error: str):
        """Callback bei Download-Fehler im 'Alle VUs' Modus."""
        vu_name = self._current_connection.vu_name if self._current_connection else "?"
        self._log(f"[{vu_name}] Download-Fehler: {error}")
        self._all_vus_stats['vus_processed'] += 1
        self._cleanup_parallel_manager()
        self._current_credentials = None
        # Weiter mit naechster VU
        QTimer.singleShot(200, self._process_next_vu)
    
    def _on_all_vus_finished(self):
        """Wird aufgerufen wenn alle VUs abgearbeitet sind."""
        from i18n.de import BIPRO_FETCH_ALL, BIPRO_FETCH_ALL_DONE
        
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.resume_auto_refresh()
        except Exception:
            pass
        
        stats = self._all_vus_stats
        all_vus_log = BIPRO_FETCH_ALL_DONE.format(
            total_vus=stats['vus_processed'],
            total_shipments=stats['total_shipments'],
            total_docs=stats['total_docs']
        )
        if stats.get('total_events', 0) > 0:
            all_vus_log = all_vus_log.rstrip(' =')
            all_vus_log += f", {stats['total_events']} Meldung(en) ==="
        self._log(all_vus_log)
        
        if stats['vus_skipped'] > 0:
            self._log(f"  Uebersprungen: {stats['vus_skipped']} VU(s)")
        
        self._all_vus_mode = False
        self.fetch_all_vus_btn.setEnabled(True)
        self.fetch_all_vus_btn.setText(BIPRO_FETCH_ALL)
        
        self._progress_overlay._stats['download_success'] = stats['total_shipments']
        self._progress_overlay._stats['download_docs'] = stats['total_docs']
        self._progress_overlay.show_completion(auto_close_seconds=10)
        
        self.documents_uploaded.emit()
        
        # Unified Fetch Koordinierung
        if self._unified_fetch_active:
            self._unified_vus_done = True
            self._check_unified_complete()
        else:
            self._update_status_card_complete(stats.get('total_docs', 0))
    
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
            if not self._unified_fetch_active:
                self._toast_manager.show_success(msg)
            self._log(msg)
            self.documents_uploaded.emit()
        else:
            if not self._unified_fetch_active:
                self._toast_manager.show_info(texts.BIPRO_MAIL_FETCH_NO_NEW)
            self._log(texts.BIPRO_MAIL_FETCH_NO_NEW)
        
        for err in stats.get('errors', []):
            self._log(f"  Fehler: {err}")
        
        # Unified Fetch Koordinierung
        if self._unified_fetch_active:
            self._unified_mail_done = True
            self._unified_mail_docs = imported
            self._check_unified_complete()
    
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
        self._download_stats = {'success': 0, 'failed': 0, 'docs': 0, 'events': 0, 'retries': 0}

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
            
            self._parallel_manager = ParallelDownloadManager(
                credentials=self._current_credentials,
                vu_name=self._current_connection.vu_name,
                shipments=shipment_infos,
                sts_url=self._current_connection.get_effective_sts_url(),
                transfer_url=self._current_connection.get_effective_transfer_url(),
                consumer_id=self._current_connection.consumer_id or "",
                max_workers=max_workers,
                api_client=self.docs_api.client,
                parent=self
            )
            
            self._parallel_manager.progress_updated.connect(self._on_parallel_progress)
            self._parallel_manager.shipment_uploaded.connect(self._on_parallel_shipment_uploaded)
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
        vu_name = self._current_connection.vu_name if self._current_connection else ""
        self._update_status_card_progress(current, total, docs_count, detail_text=vu_name)
    
    def _on_parallel_shipment_uploaded(self, shipment_id: str, doc_count: int,
                                        upload_errors: int):
        """Callback wenn eine Lieferung heruntergeladen und hochgeladen wurde.
        
        Uploads laufen im Worker-Thread, dieser Handler protokolliert nur.
        """
        if upload_errors > 0:
            self._log(f"    [WARN] Lieferung {shipment_id}: {upload_errors} Upload-Fehler")
    
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
        events = stats.get('events', 0)
        self._log(f"=== Alle Downloads abgeschlossen ===")
        summary_parts = [
            f"Erfolgreich: {stats.get('success', 0)}",
            f"Fehlgeschlagen: {stats.get('failed', 0)}",
            f"Dokumente: {stats.get('docs', 0)}",
        ]
        if events > 0:
            summary_parts.append(f"Meldungen: {events}")
        summary_parts.append(f"Retries: {stats.get('retries', 0)}")
        self._log(', '.join(summary_parts))
        
        # Fehlgeschlagene Lieferungen loggen
        failed_ids = stats.get('failed_ids', [])
        if failed_ids:
            self._log(f"  Fehlgeschlagene Lieferungen: {', '.join(failed_ids[:5])}" + 
                     (f" (+{len(failed_ids)-5} weitere)" if len(failed_ids) > 5 else ""))
        
        # Statistiken ans Overlay übergeben
        self._progress_overlay._stats['download_success'] = stats.get('success', 0)
        self._progress_overlay._stats['download_failed'] = stats.get('failed', 0)
        self._progress_overlay._stats['download_docs'] = stats.get('docs', 0)
        self._progress_overlay._stats['download_events'] = events
        self._progress_overlay._stats['download_retries'] = stats.get('retries', 0)
        
        self._progress_overlay.show_completion(auto_close_seconds=8)
        
        self._cleanup_parallel_manager()
    
    def _cleanup_parallel_manager(self):
        """Wartet auf QThread-Ende und gibt die Referenz frei."""
        if self._parallel_manager is not None:
            if self._parallel_manager.isRunning():
                self._parallel_manager.wait(5000)
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
        
        self._progress_overlay.setVisible(False)
        self._cleanup_parallel_manager()
        
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
        events = stats.get('events', 0)
        self._log(f"=== Alle Downloads abgeschlossen ===")
        seq_parts = [
            f"Erfolgreich: {stats['success']}",
            f"Fehlgeschlagen: {stats['failed']}",
            f"Dokumente: {stats['docs']}",
        ]
        if events > 0:
            seq_parts.append(f"Meldungen: {events}")
        self._log(', '.join(seq_parts))
        
        # Statistiken ans Overlay uebergeben
        self._progress_overlay._stats['download_success'] = stats['success']
        self._progress_overlay._stats['download_failed'] = stats['failed']
        self._progress_overlay._stats['download_docs'] = stats['docs']
        self._progress_overlay._stats['download_events'] = events
        
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
                        # Fruehe Text-Extraktion fuer Inhaltsduplikat-Erkennung
                        try:
                            from services.early_text_extract import extract_and_save_text
                            extract_and_save_text(self.docs_api, result.id, doc['filepath'], doc['filename'])
                        except Exception:
                            pass
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
        
        if successful:
            self._save_ack_info()
        
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
