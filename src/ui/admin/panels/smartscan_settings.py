"""
ACENCIA ATLAS - SmartScan-Einstellungen Panel

Extrahiert aus admin_view.py (Lines 4593-4877).
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QRadioButton, QButtonGroup, QPushButton, QLabel, QTextEdit,
    QSpinBox, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, TEXT_SECONDARY,
    FONT_HEADLINE, FONT_SIZE_CAPTION,
    get_button_primary_style,
    DOCUMENT_DISPLAY_COLORS,
)
from ui.admin.workers import AdminWriteWorker

logger = logging.getLogger(__name__)


class SmartScanSettingsPanel(QWidget):
    """SmartScan-Einstellungen (Versand + IMAP-Import)."""

    def __init__(self, api_client, toast_manager, smartscan_api, email_accounts_api, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._smartscan_api = smartscan_api
        self._email_accounts_api = email_accounts_api
        self._active_workers: list = []
        self._create_ui()

    def load_data(self):
        """Public entry point to load panel data."""
        self._load_smartscan_settings()

    def _create_ui(self):
        """Erstellt den SmartScan-Einstellungen-Tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # === Versand-Sektion ===
        title = QLabel(texts.SMARTSCAN_SETTINGS_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        # SmartScan aktiviert
        self._ss_enabled = QCheckBox(texts.SMARTSCAN_ENABLED)
        form.addRow("", self._ss_enabled)

        # E-Mail-Konto
        self._ss_email_account = QComboBox()
        form.addRow(texts.SMARTSCAN_EMAIL_ACCOUNT, self._ss_email_account)

        # Zieladresse
        self._ss_target = QLineEdit()
        self._ss_target.setPlaceholderText("scan@scs-smartscan.de")
        form.addRow(texts.SMARTSCAN_TARGET_ADDRESS, self._ss_target)

        # Betreff-Vorlage
        self._ss_subject = QLineEdit()
        self._ss_subject.setPlaceholderText("SmartScan - {box} - {date}")
        subject_help = QLabel(texts.SMARTSCAN_SUBJECT_HELP)
        subject_help.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        form.addRow(texts.SMARTSCAN_SUBJECT_TEMPLATE, self._ss_subject)
        form.addRow("", subject_help)

        # Body-Vorlage
        self._ss_body = QTextEdit()
        self._ss_body.setMaximumHeight(100)
        self._ss_body.setPlaceholderText("Smart!Scan Versand - {count} Dokument(e)")
        form.addRow(texts.SMARTSCAN_BODY_TEMPLATE, self._ss_body)

        # Versandmodus
        mode_group = QButtonGroup(content)
        self._ss_mode_single = QRadioButton(texts.SMARTSCAN_MODE_SINGLE)
        self._ss_mode_batch = QRadioButton(texts.SMARTSCAN_MODE_BATCH)
        mode_group.addButton(self._ss_mode_single)
        mode_group.addButton(self._ss_mode_batch)
        self._ss_mode_single.setChecked(True)
        mode_widget = QWidget()
        mode_layout = QVBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(self._ss_mode_single)
        mode_layout.addWidget(self._ss_mode_batch)
        form.addRow(texts.SMARTSCAN_SEND_MODE, mode_widget)

        # Batch-Limits
        self._ss_max_attachments = QSpinBox()
        self._ss_max_attachments.setRange(1, 100)
        self._ss_max_attachments.setValue(20)
        form.addRow(texts.SMARTSCAN_BATCH_MAX_ATTACHMENTS, self._ss_max_attachments)

        self._ss_max_mb = QSpinBox()
        self._ss_max_mb.setRange(1, 100)
        self._ss_max_mb.setValue(25)
        form.addRow(texts.SMARTSCAN_BATCH_MAX_MB, self._ss_max_mb)

        # Post-Send Aktionen
        self._ss_archive = QCheckBox(texts.SMARTSCAN_ARCHIVE_AFTER_SEND)
        form.addRow("", self._ss_archive)

        recolor_widget = QWidget()
        recolor_layout = QHBoxLayout(recolor_widget)
        recolor_layout.setContentsMargins(0, 0, 0, 0)
        self._ss_recolor = QCheckBox(texts.SMARTSCAN_RECOLOR_AFTER_SEND)
        recolor_layout.addWidget(self._ss_recolor)
        self._ss_recolor_combo = QComboBox()
        for key, hex_color in DOCUMENT_DISPLAY_COLORS.items():
            self._ss_recolor_combo.addItem(key.capitalize(), key)
        recolor_layout.addWidget(self._ss_recolor_combo)
        recolor_layout.addStretch()
        form.addRow("", recolor_widget)

        layout.addLayout(form)

        # === IMAP-Import Sektion ===
        layout.addSpacing(20)
        imap_title = QLabel(texts.SMARTSCAN_IMAP_SECTION)
        imap_title.setFont(QFont(FONT_HEADLINE, 16))
        imap_title.setStyleSheet(f"color: {PRIMARY_900};")
        layout.addWidget(imap_title)

        imap_form = QFormLayout()
        imap_form.setSpacing(10)

        self._ss_imap_auto = QCheckBox(texts.SMARTSCAN_IMAP_AUTO_IMPORT)
        imap_form.addRow("", self._ss_imap_auto)

        self._ss_imap_account = QComboBox()
        imap_form.addRow(texts.SMARTSCAN_IMAP_ACCOUNT, self._ss_imap_account)

        # Filter-Modus
        filter_group = QButtonGroup(content)
        self._ss_imap_filter_all = QRadioButton(texts.SMARTSCAN_IMAP_FILTER_ALL)
        self._ss_imap_filter_keyword = QRadioButton(texts.SMARTSCAN_IMAP_FILTER_KEYWORD)
        filter_group.addButton(self._ss_imap_filter_all)
        filter_group.addButton(self._ss_imap_filter_keyword)
        self._ss_imap_filter_all.setChecked(True)
        filter_widget = QWidget()
        filter_layout = QVBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(self._ss_imap_filter_all)
        filter_layout.addWidget(self._ss_imap_filter_keyword)
        imap_form.addRow(texts.SMARTSCAN_IMAP_FILTER_MODE, filter_widget)

        self._ss_imap_keyword = QLineEdit()
        self._ss_imap_keyword.setText("ATLASabruf")
        imap_form.addRow(texts.SMARTSCAN_IMAP_KEYWORD, self._ss_imap_keyword)

        # Absender-Filter
        sender_group = QButtonGroup(content)
        self._ss_imap_sender_all = QRadioButton(texts.SMARTSCAN_IMAP_SENDER_ALL)
        self._ss_imap_sender_whitelist = QRadioButton(texts.SMARTSCAN_IMAP_SENDER_WHITELIST)
        sender_group.addButton(self._ss_imap_sender_all)
        sender_group.addButton(self._ss_imap_sender_whitelist)
        self._ss_imap_sender_all.setChecked(True)
        sender_widget = QWidget()
        sender_layout = QVBoxLayout(sender_widget)
        sender_layout.setContentsMargins(0, 0, 0, 0)
        sender_layout.addWidget(self._ss_imap_sender_all)
        sender_layout.addWidget(self._ss_imap_sender_whitelist)
        imap_form.addRow(texts.SMARTSCAN_IMAP_SENDER_MODE, sender_widget)

        self._ss_imap_senders = QTextEdit()
        self._ss_imap_senders.setMaximumHeight(80)
        self._ss_imap_senders.setPlaceholderText("info@example.com\nscanner@firma.de")
        imap_form.addRow(texts.SMARTSCAN_IMAP_ALLOWED_SENDERS, self._ss_imap_senders)

        # Info-Text
        info_label = QLabel(texts.SMARTSCAN_IMAP_INFO)
        info_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        info_label.setWordWrap(True)
        imap_form.addRow("", info_label)

        layout.addLayout(imap_form)

        # Speichern-Button
        layout.addSpacing(20)
        save_btn = QPushButton(texts.SMARTSCAN_SETTINGS_SAVED.split('.')[0])
        save_btn.setText("Einstellungen speichern")
        save_btn.setStyleSheet(get_button_primary_style())
        save_btn.clicked.connect(self._save_smartscan_settings)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _load_smartscan_settings(self):
        """Laedt SmartScan-Einstellungen vom Server."""
        try:
            # E-Mail-Konten fuer Dropdowns laden
            accounts = self._email_accounts_api.get_accounts()
            self._ss_email_account.clear()
            self._ss_imap_account.clear()
            self._ss_email_account.addItem("-- Kein Konto --", None)
            self._ss_imap_account.addItem("-- Kein Konto --", None)
            for acc in accounts:
                label = f"{acc.get('account_name', acc.get('name', ''))} ({acc.get('from_address', '')})"
                acc_id_int = int(acc['id']) if acc.get('id') is not None else None
                self._ss_email_account.addItem(label, acc_id_int)
                self._ss_imap_account.addItem(label, acc_id_int)

            # Einstellungen laden
            settings = self._smartscan_api.get_settings()
            if not settings:
                return

            self._ss_enabled.setChecked(bool(int(settings.get('enabled', 0))))

            # E-Mail-Konto auswaehlen
            acc_id = settings.get('email_account_id')
            if acc_id is not None:
                acc_id = int(acc_id)
                idx = self._ss_email_account.findData(acc_id)
                if idx >= 0:
                    self._ss_email_account.setCurrentIndex(idx)

            self._ss_target.setText(settings.get('target_address', '') or '')
            self._ss_subject.setText(settings.get('subject_template', '') or '')
            self._ss_body.setPlainText(settings.get('body_template', '') or '')

            if settings.get('send_mode_default') == 'batch':
                self._ss_mode_batch.setChecked(True)
            else:
                self._ss_mode_single.setChecked(True)

            self._ss_max_attachments.setValue(int(settings.get('batch_max_attachments', 20) or 20))
            self._ss_max_mb.setValue(int(settings.get('batch_max_total_mb', 25) or 25))
            self._ss_archive.setChecked(bool(int(settings.get('archive_after_send', 0) or 0)))
            self._ss_recolor.setChecked(bool(int(settings.get('recolor_after_send', 0) or 0)))

            color = settings.get('recolor_color')
            if color:
                idx = self._ss_recolor_combo.findData(color)
                if idx >= 0:
                    self._ss_recolor_combo.setCurrentIndex(idx)

            # IMAP Settings
            self._ss_imap_auto.setChecked(bool(int(settings.get('imap_auto_import', 0) or 0)))

            imap_acc_id = settings.get('imap_poll_account_id')
            if imap_acc_id is not None:
                imap_acc_id = int(imap_acc_id)
                idx = self._ss_imap_account.findData(imap_acc_id)
                if idx >= 0:
                    self._ss_imap_account.setCurrentIndex(idx)

            if settings.get('imap_filter_mode') == 'keyword':
                self._ss_imap_filter_keyword.setChecked(True)
            else:
                self._ss_imap_filter_all.setChecked(True)

            self._ss_imap_keyword.setText(settings.get('imap_filter_keyword', 'ATLASabruf') or 'ATLASabruf')

            if settings.get('imap_sender_mode') == 'whitelist':
                self._ss_imap_sender_whitelist.setChecked(True)
            else:
                self._ss_imap_sender_all.setChecked(True)

            senders = settings.get('imap_allowed_senders', '')
            if senders:
                self._ss_imap_senders.setPlainText(senders.replace(',', '\n'))

        except Exception as e:
            logger.error(f"Fehler beim Laden der SmartScan-Einstellungen: {e}")

    def _save_smartscan_settings(self):
        """Speichert SmartScan-Einstellungen."""
        data = {
            'enabled': 1 if self._ss_enabled.isChecked() else 0,
            'email_account_id': self._ss_email_account.currentData(),
            'target_address': self._ss_target.text().strip(),
            'subject_template': self._ss_subject.text().strip(),
            'body_template': self._ss_body.toPlainText().strip(),
            'send_mode_default': 'batch' if self._ss_mode_batch.isChecked() else 'single',
            'batch_max_attachments': self._ss_max_attachments.value(),
            'batch_max_total_mb': self._ss_max_mb.value(),
            'archive_after_send': 1 if self._ss_archive.isChecked() else 0,
            'recolor_after_send': 1 if self._ss_recolor.isChecked() else 0,
            'recolor_color': self._ss_recolor_combo.currentData() if self._ss_recolor.isChecked() else None,
            'imap_auto_import': 1 if self._ss_imap_auto.isChecked() else 0,
            'imap_poll_account_id': self._ss_imap_account.currentData(),
            'imap_filter_mode': 'keyword' if self._ss_imap_filter_keyword.isChecked() else 'all',
            'imap_filter_keyword': self._ss_imap_keyword.text().strip(),
            'imap_sender_mode': 'whitelist' if self._ss_imap_sender_whitelist.isChecked() else 'all',
            'imap_allowed_senders': ','.join(
                line.strip() for line in self._ss_imap_senders.toPlainText().split('\n') if line.strip()
            ),
        }
        try:
            result = self._smartscan_api.update_settings(data)
            if result is not None:
                self._toast_manager.show_success(texts.SMARTSCAN_SETTINGS_SAVED)
            else:
                self._toast_manager.show_error(texts.SMARTSCAN_SETTINGS_ERROR.format(error="Keine Antwort vom Server"))
        except Exception as e:
            self._toast_manager.show_error(texts.SMARTSCAN_SETTINGS_ERROR.format(error=str(e)))
