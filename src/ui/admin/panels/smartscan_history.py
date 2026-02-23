"""
ACENCIA ATLAS - SmartScan-Historie Panel

Extrahiert aus admin_view.py (Lines 4883-5100).
"""

from typing import List, Dict
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QHeaderView, QDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, ACCENT_500,
    FONT_HEADLINE,
    get_button_secondary_style,
)
from ui.admin.workers import AdminWriteWorker

logger = logging.getLogger(__name__)


class SmartScanHistoryPanel(QWidget):
    """SmartScan Versandhistorie."""

    def __init__(self, api_client, toast_manager, smartscan_api, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._smartscan_api = smartscan_api
        self._ss_hist_data: List[Dict] = []
        self._active_workers: list = []
        self._create_ui()

    def load_data(self):
        """Public entry point to load panel data."""
        self._load_smartscan_history()

    def _create_ui(self):
        """Erstellt den SmartScan-Historie-Tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel(texts.SMARTSCAN_HISTORY_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()

        # Zeitraum-Filter
        self._ss_hist_filter = QComboBox()
        self._ss_hist_filter.addItem(texts.SMARTSCAN_HISTORY_FILTER_ALL, "all")
        self._ss_hist_filter.addItem(texts.SMARTSCAN_HISTORY_FILTER_7D, "7")
        self._ss_hist_filter.addItem(texts.SMARTSCAN_HISTORY_FILTER_30D, "30")
        self._ss_hist_filter.addItem(texts.SMARTSCAN_HISTORY_FILTER_90D, "90")
        self._ss_hist_filter.currentIndexChanged.connect(lambda: self._load_smartscan_history())
        toolbar.addWidget(self._ss_hist_filter)

        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.setStyleSheet(get_button_secondary_style())
        refresh_btn.clicked.connect(self._load_smartscan_history)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        # Tabelle
        self._ss_hist_table = QTableWidget()
        self._ss_hist_table.setColumnCount(9)
        self._ss_hist_table.setHorizontalHeaderLabels([
            texts.SMARTSCAN_HISTORY_DATE, texts.SMARTSCAN_HISTORY_USER,
            texts.SMARTSCAN_HISTORY_MODE, texts.SMARTSCAN_HISTORY_DOCUMENTS,
            texts.SMARTSCAN_HISTORY_SENT, texts.SMARTSCAN_HISTORY_FAILED,
            texts.SMARTSCAN_HISTORY_ARCHIVED, texts.SMARTSCAN_HISTORY_STATUS,
            texts.SMARTSCAN_HISTORY_DETAILS
        ])
        ss_hist_header = self._ss_hist_table.horizontalHeader()
        ss_hist_header.setStretchLastSection(True)
        for col in range(8):
            ss_hist_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._ss_hist_table.setColumnWidth(8, 120)
        self._ss_hist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._ss_hist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._ss_hist_table.verticalHeader().setVisible(False)
        self._ss_hist_table.verticalHeader().setDefaultSectionSize(40)
        layout.addWidget(self._ss_hist_table)

    def _load_smartscan_history(self):
        """Laedt SmartScan-Historie."""
        try:
            jobs = self._smartscan_api.get_jobs(limit=100)
            self._ss_hist_data = jobs
            self._populate_smartscan_history()
        except Exception as e:
            logger.error(f"Fehler beim Laden der SmartScan-Historie: {e}")

    def _populate_smartscan_history(self):
        """Fuellt die SmartScan-Historie-Tabelle."""
        status_labels = {
            'queued': texts.SMARTSCAN_STATUS_QUEUED,
            'sending': texts.SMARTSCAN_STATUS_SENDING,
            'sent': texts.SMARTSCAN_STATUS_SENT,
            'partial': texts.SMARTSCAN_STATUS_PARTIAL,
            'failed': texts.SMARTSCAN_STATUS_FAILED,
        }
        mode_labels = {
            'single': texts.SMARTSCAN_MODE_SINGLE.split('(')[0].strip(),
            'batch': texts.SMARTSCAN_MODE_BATCH.split('(')[0].strip(),
        }

        self._ss_hist_table.setRowCount(len(self._ss_hist_data))
        for row, job in enumerate(self._ss_hist_data):
            created = job.get('created_at', '')
            if created:
                try:
                    from datetime import datetime
                    dt_str = created.replace('T', ' ').replace('Z', '')
                    if '+' in dt_str:
                        dt_str = dt_str[:dt_str.index('+')]
                    dt = datetime.strptime(dt_str.strip(), '%Y-%m-%d %H:%M:%S')
                    created = dt.strftime('%d.%m.%Y %H:%M')
                except Exception:
                    pass

            total_items = int(job.get('total_items', 0) or 0)
            processed = int(job.get('processed_items', 0) or 0)
            sent = int(job.get('sent_emails', 0) or 0)
            failed = int(job.get('failed_emails', 0) or 0)

            self._ss_hist_table.setItem(row, 0, QTableWidgetItem(created))
            self._ss_hist_table.setItem(row, 1, QTableWidgetItem(job.get('username', '')))
            self._ss_hist_table.setItem(row, 2, QTableWidgetItem(
                mode_labels.get(job.get('mode', ''), job.get('mode', ''))
            ))
            self._ss_hist_table.setItem(row, 3, QTableWidgetItem(str(total_items)))
            self._ss_hist_table.setItem(row, 4, QTableWidgetItem(str(sent)))
            self._ss_hist_table.setItem(row, 5, QTableWidgetItem(str(failed)))
            self._ss_hist_table.setItem(row, 6, QTableWidgetItem(
                "Ja" if processed > 0 else "-"
            ))
            self._ss_hist_table.setItem(row, 7, QTableWidgetItem(
                status_labels.get(job.get('status', ''), job.get('status', ''))
            ))

            detail_btn = QPushButton(texts.SMARTSCAN_HISTORY_DETAILS)
            detail_btn.setFixedHeight(28)
            detail_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {ACCENT_500};
                    border: 1px solid {ACCENT_500};
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background: {ACCENT_500};
                    color: white;
                }}
            """)
            detail_btn.clicked.connect(lambda checked, r=row: self._show_smartscan_job_details(r))
            self._ss_hist_table.setCellWidget(row, 8, detail_btn)

        self._ss_hist_table.resizeColumnsToContents()

    def _show_smartscan_job_details(self, row: int):
        """Zeigt Job-Details an."""
        if row < 0 or row >= len(self._ss_hist_data):
            return
        job = self._ss_hist_data[row]
        try:
            details = self._smartscan_api.get_job_details(job['id'])
            if not details:
                return

            dialog = QDialog(self)
            dialog.setWindowTitle(texts.SMARTSCAN_DETAIL_TITLE)
            dialog.setMinimumSize(700, 500)
            layout = QVBoxLayout(dialog)

            # Items-Tabelle
            items_label = QLabel(texts.SMARTSCAN_DETAIL_DOCUMENTS)
            items_label.setFont(QFont(FONT_HEADLINE, 14))
            layout.addWidget(items_label)

            items_table = QTableWidget()
            items = details.get('items', [])
            items_table.setRowCount(len(items))
            items_table.setColumnCount(3)
            items_table.setHorizontalHeaderLabels([
                texts.SMARTSCAN_DETAIL_DOC_NAME,
                texts.SMARTSCAN_DETAIL_DOC_STATUS,
                texts.SMARTSCAN_DETAIL_DOC_ERROR
            ])
            items_table.horizontalHeader().setStretchLastSection(True)
            items_table.verticalHeader().setDefaultSectionSize(34)
            for i, item in enumerate(items):
                items_table.setItem(i, 0, QTableWidgetItem(item.get('original_filename', '') or ''))
                items_table.setItem(i, 1, QTableWidgetItem(item.get('status', '')))
                items_table.setItem(i, 2, QTableWidgetItem(item.get('error_message', '') or ''))
            items_table.resizeColumnsToContents()
            layout.addWidget(items_table)

            # Emails-Tabelle
            emails_label = QLabel(texts.SMARTSCAN_DETAIL_EMAILS)
            emails_label.setFont(QFont(FONT_HEADLINE, 14))
            layout.addWidget(emails_label)

            emails_table = QTableWidget()
            emails = details.get('emails', [])
            emails_table.setRowCount(len(emails))
            emails_table.setColumnCount(4)
            emails_table.setHorizontalHeaderLabels([
                texts.SMARTSCAN_DETAIL_EMAIL_SUBJECT,
                texts.SMARTSCAN_DETAIL_EMAIL_ATTACHMENTS,
                texts.SMARTSCAN_DETAIL_EMAIL_MESSAGE_ID,
                texts.SMARTSCAN_DETAIL_EMAIL_SENT_AT
            ])
            emails_table.horizontalHeader().setStretchLastSection(True)
            emails_table.verticalHeader().setDefaultSectionSize(34)
            for i, email in enumerate(emails):
                emails_table.setItem(i, 0, QTableWidgetItem(email.get('subject', '') or ''))
                emails_table.setItem(i, 1, QTableWidgetItem(str(email.get('attachment_count', 0))))
                emails_table.setItem(i, 2, QTableWidgetItem(email.get('message_id', '') or ''))
                created = email.get('created_at', '') or ''
                if created:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(created.replace('T', ' ')[:19], '%Y-%m-%d %H:%M:%S')
                        created = dt.strftime('%d.%m.%Y %H:%M')
                    except Exception:
                        pass
                emails_table.setItem(i, 3, QTableWidgetItem(created))
            emails_table.resizeColumnsToContents()
            layout.addWidget(emails_table)

            close_btn = QPushButton("Schliessen")
            close_btn.setStyleSheet(get_button_secondary_style())
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

            dialog.exec()
        except Exception as e:
            logger.error(f"Fehler beim Laden der Job-Details: {e}")
