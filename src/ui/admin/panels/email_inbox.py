"""
ACENCIA ATLAS - E-Mail-Posteingang Panel

Extrahiert aus admin_view.py (Lines 5106-5379).
"""

from typing import List, Dict
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QDialog, QTextEdit, QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction

from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, TEXT_SECONDARY,
    FONT_HEADLINE,
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style,
)
from ui.admin.workers import ImapPollWorker, AdminWriteWorker

logger = logging.getLogger(__name__)


class EmailInboxPanel(QWidget):
    """E-Mail-Posteingang (IMAP-Import)."""

    def __init__(self, api_client, toast_manager, email_accounts_api, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._email_accounts_api = email_accounts_api
        self._inbox_data: List[Dict] = []
        self._inbox_page = 1
        self._active_workers: list = []
        self._imap_poll_worker = None
        self._ea_data: List[Dict] = []
        self._smartscan_api = None
        self._create_ui()

    def set_smartscan_api(self, smartscan_api):
        """Sets the SmartScan API (needed for IMAP poll account lookup)."""
        self._smartscan_api = smartscan_api

    def set_ea_data(self, ea_data: List[Dict]):
        """Sets cached email accounts data from the EmailAccountsPanel."""
        self._ea_data = ea_data

    def load_data(self):
        """Public entry point to load panel data."""
        self._load_email_inbox()

    def _create_ui(self):
        """Erstellt den E-Mail-Posteingang-Tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel(texts.EMAIL_INBOX_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)

        self._inbox_last_poll = QLabel("")
        self._inbox_last_poll.setStyleSheet(f"color: {TEXT_SECONDARY};")
        toolbar.addWidget(self._inbox_last_poll)
        toolbar.addStretch()

        # Status-Filter
        self._inbox_filter = QComboBox()
        self._inbox_filter.addItem(texts.EMAIL_INBOX_FILTER_ALL, "")
        self._inbox_filter.addItem(texts.EMAIL_INBOX_FILTER_NEW, "new")
        self._inbox_filter.addItem(texts.EMAIL_INBOX_FILTER_PROCESSED, "processed")
        self._inbox_filter.addItem(texts.EMAIL_INBOX_FILTER_IGNORED, "ignored")
        self._inbox_filter.currentIndexChanged.connect(lambda: self._load_email_inbox())
        toolbar.addWidget(self._inbox_filter)

        poll_btn = QPushButton(texts.EMAIL_INBOX_POLL)
        poll_btn.setStyleSheet(get_button_primary_style())
        poll_btn.clicked.connect(self._poll_email_inbox)
        toolbar.addWidget(poll_btn)

        layout.addLayout(toolbar)

        # Tabelle
        self._inbox_table = QTableWidget()
        self._inbox_table.setColumnCount(6)
        self._inbox_table.setHorizontalHeaderLabels([
            texts.EMAIL_INBOX_DATE, texts.EMAIL_INBOX_FROM,
            texts.EMAIL_INBOX_SUBJECT, texts.EMAIL_INBOX_ATTACHMENTS,
            texts.EMAIL_INBOX_STATUS, ""
        ])
        self._inbox_table.horizontalHeader().setStretchLastSection(True)
        self._inbox_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._inbox_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._inbox_table.verticalHeader().setVisible(False)
        self._inbox_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._inbox_table.customContextMenuRequested.connect(self._show_inbox_context_menu)
        layout.addWidget(self._inbox_table)

    def _load_email_inbox(self):
        """Laedt E-Mail-Posteingang."""
        try:
            status_filter = self._inbox_filter.currentData()
            result = self._email_accounts_api.get_inbox(
                page=self._inbox_page, limit=50, status=status_filter or None
            )
            self._inbox_data = result.get('mails', []) if isinstance(result, dict) else []
            self._populate_inbox_table()
        except Exception as e:
            logger.error(f"Fehler beim Laden des Posteingangs: {e}")

    def _populate_inbox_table(self):
        """Fuellt die Posteingang-Tabelle."""
        status_labels = {
            'new': texts.EMAIL_INBOX_STATUS_NEW,
            'processed': texts.EMAIL_INBOX_STATUS_PROCESSED,
            'ignored': texts.EMAIL_INBOX_STATUS_IGNORED,
        }

        self._inbox_table.setRowCount(len(self._inbox_data))
        for row, mail in enumerate(self._inbox_data):
            received = mail.get('received_at', '')
            if received and 'T' in str(received):
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(received).replace('Z', '+00:00'))
                    received = dt.strftime('%d.%m.%Y %H:%M')
                except Exception:
                    pass

            self._inbox_table.setItem(row, 0, QTableWidgetItem(str(received)))

            from_str = mail.get('from_name', '') or mail.get('from_address', '')
            self._inbox_table.setItem(row, 1, QTableWidgetItem(from_str))
            self._inbox_table.setItem(row, 2, QTableWidgetItem(mail.get('subject', '')))
            self._inbox_table.setItem(row, 3, QTableWidgetItem(str(mail.get('attachment_count', 0))))
            self._inbox_table.setItem(row, 4, QTableWidgetItem(
                status_labels.get(mail.get('processing_status', ''), mail.get('processing_status', ''))
            ))

            detail_btn = QPushButton(texts.EMAIL_INBOX_DETAILS)
            detail_btn.setStyleSheet(get_button_ghost_style())
            detail_btn.clicked.connect(lambda checked, r=row: self._show_inbox_detail(r))
            self._inbox_table.setCellWidget(row, 5, detail_btn)

        self._inbox_table.resizeColumnsToContents()

    def _poll_email_inbox(self):
        """IMAP-Postfach im Hintergrund abrufen (verhindert UI-Freeze)."""
        if self._imap_poll_worker and self._imap_poll_worker.isRunning():
            self._toast_manager.show_info(texts.EMAIL_INBOX_POLL_RUNNING)
            return

        acc_id = None

        # 1. Versuche imap_poll_account_id aus SmartScan-Einstellungen
        if self._smartscan_api:
            try:
                settings = self._smartscan_api.get_settings()
                if settings:
                    raw_id = settings.get('imap_poll_account_id')
                    if raw_id is not None and str(raw_id).strip():
                        acc_id = int(raw_id)
            except Exception as e:
                logger.debug(f"SmartScan-Settings Fehler (ignoriert): {e}")

        # 2. Fallback: Erstes E-Mail-Konto mit IMAP-Host verwenden
        if not acc_id and self._ea_data:
            for acc in self._ea_data:
                imap_host = acc.get('imap_host', '').strip() if acc.get('imap_host') else ''
                is_active = acc.get('is_active')
                if imap_host and (is_active == 1 or is_active == '1' or is_active is True):
                    acc_id = int(acc['id'])
                    break

        # 3. Noch kein Konto? Konten nachladen und erneut suchen
        if not acc_id:
            try:
                accounts = self._email_accounts_api.get_accounts()
                for acc in accounts:
                    imap_host = acc.get('imap_host', '').strip() if acc.get('imap_host') else ''
                    is_active = acc.get('is_active')
                    if imap_host and (is_active == 1 or is_active == '1' or is_active is True):
                        acc_id = int(acc['id'])
                        break
            except Exception:
                pass

        if not acc_id:
            self._toast_manager.show_warning(texts.EMAIL_INBOX_NO_IMAP_ACCOUNT)
            return

        logger.info(f"IMAP-Poll gestartet fuer Konto-ID {acc_id}")

        self._toast_manager.show_info(texts.EMAIL_INBOX_POLL_RUNNING)
        self._imap_poll_worker = ImapPollWorker(self._email_accounts_api, acc_id)
        self._imap_poll_worker.finished.connect(self._on_imap_poll_finished)
        self._imap_poll_worker.error.connect(self._on_imap_poll_error)
        self._active_workers.append(self._imap_poll_worker)
        self._imap_poll_worker.start()

    def _on_imap_poll_finished(self, result: dict):
        """Callback wenn IMAP-Poll abgeschlossen."""
        new_mails = result.get('new_mails', 0)
        new_atts = result.get('new_attachments', 0)

        if new_mails > 0:
            self._toast_manager.show_success(texts.EMAIL_INBOX_POLL_SUCCESS.format(
                new_mails=new_mails, new_attachments=new_atts))
        else:
            self._toast_manager.show_info(texts.EMAIL_INBOX_POLL_NO_NEW)

        self._load_email_inbox()

    def _on_imap_poll_error(self, error: str):
        """Callback wenn IMAP-Poll fehlgeschlagen."""
        self._toast_manager.show_error(texts.EMAIL_INBOX_POLL_ERROR.format(error=error))

    def _show_inbox_context_menu(self, position):
        """Kontextmenue fuer Posteingang-Tabelle."""
        row = self._inbox_table.rowAt(position.y())
        if row < 0 or row >= len(self._inbox_data):
            return

        mail = self._inbox_data[row]
        menu = QMenu(self)

        if mail.get('has_attachments') and mail.get('processing_status') == 'new':
            import_action = QAction(texts.EMAIL_INBOX_IMPORT, self)
            import_action.triggered.connect(lambda: self._import_inbox_attachments(row))
            menu.addAction(import_action)

        ignore_action = QAction(texts.EMAIL_INBOX_IGNORE, self)
        ignore_action.triggered.connect(lambda: self._ignore_inbox_mail(row))
        menu.addAction(ignore_action)

        detail_action = QAction(texts.EMAIL_INBOX_DETAILS, self)
        detail_action.triggered.connect(lambda: self._show_inbox_detail(row))
        menu.addAction(detail_action)

        menu.exec(self._inbox_table.viewport().mapToGlobal(position))

    def _show_inbox_detail(self, row: int):
        """Zeigt Mail-Details an."""
        if row < 0 or row >= len(self._inbox_data):
            return
        mail = self._inbox_data[row]
        try:
            detail = self._email_accounts_api.get_inbox_mail(mail['id'])
            if not detail:
                return

            dialog = QDialog(self)
            dialog.setWindowTitle(f"Mail: {detail.get('subject', '')}")
            dialog.setMinimumSize(600, 400)
            layout = QVBoxLayout(dialog)

            # Header
            header_text = f"Von: {detail.get('from_name', '')} <{detail.get('from_address', '')}>\n"
            header_text += f"Betreff: {detail.get('subject', '')}\n"
            header_text += f"Datum: {detail.get('received_at', '')}"
            header_label = QLabel(header_text)
            header_label.setWordWrap(True)
            layout.addWidget(header_label)

            # Body
            body = detail.get('body_preview', '')
            if body:
                body_edit = QTextEdit()
                body_edit.setPlainText(body)
                body_edit.setReadOnly(True)
                body_edit.setMaximumHeight(150)
                layout.addWidget(body_edit)

            # Anhaenge
            attachments = detail.get('attachments', [])
            if attachments:
                att_label = QLabel(f"Anhaenge ({len(attachments)}):")
                att_label.setFont(QFont(FONT_HEADLINE, 12))
                layout.addWidget(att_label)

                att_table = QTableWidget()
                att_table.setRowCount(len(attachments))
                att_table.setColumnCount(4)
                att_table.setHorizontalHeaderLabels(["Dateiname", "Groesse", "MIME", "Status"])
                att_table.horizontalHeader().setStretchLastSection(True)
                for i, att in enumerate(attachments):
                    att_table.setItem(i, 0, QTableWidgetItem(att.get('filename', '')))
                    size_bytes = att.get('file_size_bytes', 0)
                    size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes else "?"
                    att_table.setItem(i, 1, QTableWidgetItem(size_str))
                    att_table.setItem(i, 2, QTableWidgetItem(att.get('mime_type', '')))
                    att_table.setItem(i, 3, QTableWidgetItem(att.get('import_status', '')))
                layout.addWidget(att_table)

            close_btn = QPushButton("Schliessen")
            close_btn.setStyleSheet(get_button_secondary_style())
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

            dialog.exec()
        except Exception as e:
            logger.error(f"Fehler beim Laden der Mail-Details: {e}")

    def _import_inbox_attachments(self, row: int):
        """Importiert Anhaenge einer Mail (Stub - wird vom ImapImportWorker erledigt)."""
        self._toast_manager.show_info(
            "Der Import wird ueber den IMAP-Import-Worker ausgefuehrt. "
            "Verwenden Sie den 'Postfach abrufen' Button.")

    def _ignore_inbox_mail(self, row: int):
        """Markiert eine Mail als ignoriert."""
        if row < 0 or row >= len(self._inbox_data):
            return
        # TODO: API-Call zum Ignorieren
        self._load_email_inbox()
