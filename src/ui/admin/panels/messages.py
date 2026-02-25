"""
ACENCIA ATLAS - Mitteilungen Panel (Admin)

Verwaltet System-/Admin-Mitteilungen und BiPRO-Handlungsaufforderungen.
"""

from typing import List, Dict
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QComboBox, QHeaderView, QAbstractItemView, QMessageBox, QTextEdit,
    QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from i18n import de as texts
from api.messages import MessagesAPI
from api.bipro_events import BiproEventsAPI
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_100, PRIMARY_0,
    ACCENT_500,
    FONT_HEADLINE,
    FONT_SIZE_BODY, RADIUS_MD,
)
from ui.admin.workers import AdminWriteWorker

logger = logging.getLogger(__name__)


class MessagesPanel(QWidget):
    """Admin-Mitteilungen verwalten (System + Admin + BiPRO-Events)."""

    def __init__(self, api_client, toast_manager, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._admin_messages_data: List[Dict] = []
        self._bipro_events_data: List[Dict] = []
        self._active_workers: list = []
        self._create_ui()

    def load_data(self):
        """Public entry point to load panel data."""
        self._load_admin_messages()
        self._load_bipro_events()

    def _create_ui(self):
        """Erstellt das Admin-Panel fuer Mitteilungen (System + Admin + BiPRO-Events)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(8)

        # ── Sektion 1: System-/Admin-Mitteilungen ──
        msg_section = QWidget()
        msg_layout = QVBoxLayout(msg_section)
        msg_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        title = QLabel(texts.ADMIN_MSG_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()

        new_msg_btn = QPushButton(f"+ {texts.ADMIN_MSG_NEW}")
        new_msg_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                padding: 8px 20px;
                font-size: {FONT_SIZE_BODY};
            }}
            QPushButton:hover {{
                background-color: #e8882e;
            }}
        """)
        new_msg_btn.clicked.connect(self._show_new_message_dialog)
        toolbar.addWidget(new_msg_btn)
        msg_layout.addLayout(toolbar)

        self._msg_table = QTableWidget()
        self._msg_table.setColumnCount(6)
        self._msg_table.setHorizontalHeaderLabels([
            texts.ADMIN_MSG_COL_DATE,
            texts.ADMIN_MSG_COL_TITLE,
            texts.ADMIN_MSG_COL_SEVERITY,
            texts.ADMIN_MSG_COL_SOURCE,
            texts.ADMIN_MSG_COL_SENDER,
            texts.ADMIN_MSG_COL_ACTIONS,
        ])
        self._msg_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._msg_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._msg_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._msg_table.verticalHeader().setVisible(False)
        self._msg_table.setAlternatingRowColors(True)
        self._msg_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                gridline-color: {PRIMARY_100};
                font-size: {FONT_SIZE_BODY};
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
        """)
        msg_layout.addWidget(self._msg_table)
        splitter.addWidget(msg_section)

        # ── Sektion 2: BiPRO-Handlungsaufforderungen ──
        bipro_section = QWidget()
        bipro_layout = QVBoxLayout(bipro_section)
        bipro_layout.setContentsMargins(0, 12, 0, 0)

        bipro_toolbar = QHBoxLayout()
        bipro_title = QLabel(texts.ADMIN_BIPRO_EVENTS_TITLE)
        bipro_title.setFont(QFont(FONT_HEADLINE, 16))
        bipro_title.setStyleSheet(f"color: {PRIMARY_900};")
        bipro_toolbar.addWidget(bipro_title)

        self._bipro_count_label = QLabel("")
        self._bipro_count_label.setStyleSheet(
            f"color: {PRIMARY_100}; font-size: {FONT_SIZE_BODY};"
        )
        bipro_toolbar.addWidget(self._bipro_count_label)

        bipro_toolbar.addStretch()

        delete_all_btn = QPushButton(texts.ADMIN_BIPRO_EVENTS_DELETE_ALL)
        delete_all_btn.setStyleSheet(f"""
            QPushButton {{
                color: #dc2626;
                background: transparent;
                border: 1px solid #dc2626;
                border-radius: {RADIUS_MD};
                padding: 6px 16px;
                font-size: {FONT_SIZE_BODY};
            }}
            QPushButton:hover {{
                background-color: #fee2e2;
            }}
        """)
        delete_all_btn.clicked.connect(self._delete_all_bipro_events)
        bipro_toolbar.addWidget(delete_all_btn)

        bipro_layout.addLayout(bipro_toolbar)

        self._bipro_table = QTableWidget()
        self._bipro_table.setColumnCount(7)
        self._bipro_table.setHorizontalHeaderLabels([
            texts.ADMIN_BIPRO_EVENTS_COL_DATE,
            texts.ADMIN_BIPRO_EVENTS_COL_VU,
            texts.ADMIN_BIPRO_EVENTS_COL_TYPE,
            texts.ADMIN_BIPRO_EVENTS_COL_VSNR,
            texts.ADMIN_BIPRO_EVENTS_COL_DESCRIPTION,
            texts.ADMIN_BIPRO_EVENTS_COL_READ,
            texts.ADMIN_BIPRO_EVENTS_COL_ACTIONS,
        ])
        self._bipro_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self._bipro_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._bipro_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._bipro_table.verticalHeader().setVisible(False)
        self._bipro_table.setAlternatingRowColors(True)
        self._bipro_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                gridline-color: {PRIMARY_100};
                font-size: {FONT_SIZE_BODY};
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
        """)
        bipro_layout.addWidget(self._bipro_table)
        splitter.addWidget(bipro_section)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def _load_admin_messages(self):
        """Laedt alle Mitteilungen fuer die Admin-Tabelle."""
        try:
            api = MessagesAPI(self._api_client)
            result = api.get_messages(page=1, per_page=100)
            self._admin_messages_data = result.get('data', [])
            self._populate_msg_table()
        except Exception as e:
            logger.error(f"Admin-Mitteilungen laden: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(texts.ADMIN_MSG_LOAD_ERROR)

    def _populate_msg_table(self):
        """Fuellt die Mitteilungen-Tabelle."""
        self._msg_table.setRowCount(len(self._admin_messages_data))

        severity_labels = {
            'info': texts.MSG_CENTER_SEVERITY_INFO,
            'warning': texts.MSG_CENTER_SEVERITY_WARNING,
            'error': texts.MSG_CENTER_SEVERITY_ERROR,
            'critical': texts.MSG_CENTER_SEVERITY_CRITICAL,
        }

        for row, msg in enumerate(self._admin_messages_data):
            # Datum
            created = msg.get('created_at', '')
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                date_str = dt.strftime('%d.%m.%Y %H:%M')
            except (ValueError, AttributeError):
                date_str = created
            self._msg_table.setItem(row, 0, QTableWidgetItem(date_str))

            # Titel
            self._msg_table.setItem(row, 1, QTableWidgetItem(msg.get('title', '')))

            # Severity
            sev = msg.get('severity', 'info')
            self._msg_table.setItem(row, 2, QTableWidgetItem(
                severity_labels.get(sev, sev)
            ))

            # Quelle
            self._msg_table.setItem(row, 3, QTableWidgetItem(msg.get('source', '')))

            # Absender
            self._msg_table.setItem(row, 4, QTableWidgetItem(msg.get('sender_name', '')))

            # Aktionen
            delete_btn = QPushButton(texts.ADMIN_MSG_DELETE)
            delete_btn.setStyleSheet(f"""
                QPushButton {{
                    color: #dc2626;
                    background: transparent;
                    border: 1px solid #dc2626;
                    border-radius: 4px;
                    padding: 3px 10px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: #fee2e2;
                }}
            """)
            msg_id = msg.get('id', 0)
            msg_title = msg.get('title', '')
            delete_btn.clicked.connect(
                lambda checked, mid=msg_id, mt=msg_title: self._delete_admin_message(mid, mt)
            )
            self._msg_table.setCellWidget(row, 5, delete_btn)

    def _show_new_message_dialog(self):
        """Zeigt den Dialog zum Erstellen einer neuen Mitteilung."""
        dialog = QDialog(self)
        dialog.setWindowTitle(texts.ADMIN_MSG_DIALOG_TITLE)
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet(f"background-color: {PRIMARY_0};")

        layout = QFormLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title_input = QLineEdit()
        title_input.setMaxLength(500)
        title_input.setPlaceholderText(texts.ADMIN_MSG_DIALOG_TITLE_LABEL)
        title_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 8px;
                font-size: {FONT_SIZE_BODY};
            }}
        """)
        layout.addRow(texts.ADMIN_MSG_DIALOG_TITLE_LABEL, title_input)

        desc_input = QTextEdit()
        desc_input.setMaximumHeight(100)
        desc_input.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 8px;
                font-size: {FONT_SIZE_BODY};
            }}
        """)
        layout.addRow(texts.ADMIN_MSG_DIALOG_DESC_LABEL, desc_input)

        severity_combo = QComboBox()
        severity_combo.addItem(texts.MSG_CENTER_SEVERITY_INFO, 'info')
        severity_combo.addItem(texts.MSG_CENTER_SEVERITY_WARNING, 'warning')
        severity_combo.addItem(texts.MSG_CENTER_SEVERITY_ERROR, 'error')
        severity_combo.addItem(texts.MSG_CENTER_SEVERITY_CRITICAL, 'critical')
        severity_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 6px 8px;
                font-size: {FONT_SIZE_BODY};
            }}
        """)
        layout.addRow(texts.ADMIN_MSG_DIALOG_SEVERITY_LABEL, severity_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            title_text = title_input.text().strip()
            if not title_text:
                return

            desc_text = desc_input.toPlainText().strip() or None
            severity = severity_combo.currentData()

            try:
                api = MessagesAPI(self._api_client)
                api.create_message(
                    title=title_text,
                    description=desc_text,
                    severity=severity
                )
                if self._toast_manager:
                    self._toast_manager.show_success(texts.ADMIN_MSG_CREATED)
                self._load_admin_messages()
            except Exception as e:
                logger.error(f"Mitteilung erstellen: {e}")
                if self._toast_manager:
                    self._toast_manager.show_error(texts.ADMIN_MSG_CREATE_ERROR)

    def _delete_admin_message(self, message_id: int, title: str):
        """Loescht eine Mitteilung nach Bestaetigung."""
        reply = QMessageBox.question(
            self,
            texts.ADMIN_MSG_DELETE,
            texts.ADMIN_MSG_DELETE_CONFIRM.format(title=title[:50]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            api = MessagesAPI(self._api_client)
            api.delete_message(message_id)
            if self._toast_manager:
                self._toast_manager.show_success(texts.ADMIN_MSG_DELETED)
            self._load_admin_messages()
        except Exception as e:
            logger.error(f"Mitteilung loeschen: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(texts.ADMIN_MSG_DELETE_ERROR)

    # ====================================================================
    # BiPRO-Events Verwaltung
    # ====================================================================

    def _load_bipro_events(self):
        """Laedt alle BiPRO-Events fuer die Admin-Tabelle."""
        try:
            api = BiproEventsAPI(self._api_client)
            result = api.get_events(page=1, per_page=500)
            self._bipro_events_data = result.get('data', [])
            self._populate_bipro_table()
        except Exception as e:
            logger.error(f"BiPRO-Events laden: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(texts.ADMIN_BIPRO_EVENTS_LOAD_ERROR)

    def _populate_bipro_table(self):
        """Fuellt die BiPRO-Events-Tabelle."""
        from datetime import datetime
        from PySide6.QtGui import QColor

        self._bipro_table.setRowCount(len(self._bipro_events_data))
        self._bipro_count_label.setText(f"({len(self._bipro_events_data)})")

        type_labels = getattr(texts, 'BIPRO_EVENT_TYPE_LABELS', {})

        for row, ev in enumerate(self._bipro_events_data):
            created = getattr(ev, 'created_at', '')
            try:
                dt = datetime.fromisoformat(str(created).replace('Z', '+00:00'))
                date_str = dt.strftime('%d.%m.%Y %H:%M')
            except (ValueError, AttributeError):
                date_str = str(created)
            self._bipro_table.setItem(row, 0, QTableWidgetItem(date_str))

            self._bipro_table.setItem(row, 1, QTableWidgetItem(
                getattr(ev, 'vu_name', '') or ''
            ))

            etype = getattr(ev, 'event_type', '')
            self._bipro_table.setItem(row, 2, QTableWidgetItem(
                type_labels.get(etype, etype)
            ))

            self._bipro_table.setItem(row, 3, QTableWidgetItem(
                getattr(ev, 'vsnr', '') or ''
            ))

            desc = getattr(ev, 'kurzbeschreibung', '') or getattr(ev, 'category_name', '') or ''
            self._bipro_table.setItem(row, 4, QTableWidgetItem(desc))

            is_read = getattr(ev, 'is_read', False)
            read_text = texts.ADMIN_BIPRO_EVENTS_READ_YES if is_read else texts.ADMIN_BIPRO_EVENTS_READ_NO
            read_item = QTableWidgetItem(read_text)
            if not is_read:
                read_item.setForeground(QColor('#dc2626'))
            self._bipro_table.setItem(row, 5, read_item)

            delete_btn = QPushButton(texts.ADMIN_BIPRO_EVENTS_DELETE)
            delete_btn.setStyleSheet(f"""
                QPushButton {{
                    color: #dc2626;
                    background: transparent;
                    border: 1px solid #dc2626;
                    border-radius: 4px;
                    padding: 3px 10px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: #fee2e2;
                }}
            """)
            event_id = getattr(ev, 'id', 0)
            delete_btn.clicked.connect(
                lambda checked, eid=event_id: self._delete_bipro_event(eid)
            )
            self._bipro_table.setCellWidget(row, 6, delete_btn)

    def _delete_bipro_event(self, event_id: int):
        """Loescht einen einzelnen BiPRO-Event."""
        reply = QMessageBox.question(
            self,
            texts.ADMIN_BIPRO_EVENTS_DELETE,
            texts.ADMIN_BIPRO_EVENTS_DELETE_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            api = BiproEventsAPI(self._api_client)
            if api.delete_event(event_id):
                if self._toast_manager:
                    self._toast_manager.show_success(texts.ADMIN_BIPRO_EVENTS_DELETED)
                self._load_bipro_events()
            else:
                if self._toast_manager:
                    self._toast_manager.show_error(texts.ADMIN_BIPRO_EVENTS_DELETE_ERROR)
        except Exception as e:
            logger.error(f"BiPRO-Event loeschen: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(texts.ADMIN_BIPRO_EVENTS_DELETE_ERROR)

    def _delete_all_bipro_events(self):
        """Loescht alle BiPRO-Events nach Bestaetigung."""
        count = len(self._bipro_events_data)
        if count == 0:
            return

        reply = QMessageBox.question(
            self,
            texts.ADMIN_BIPRO_EVENTS_DELETE_ALL,
            texts.ADMIN_BIPRO_EVENTS_DELETE_ALL_CONFIRM.format(count=count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            api = BiproEventsAPI(self._api_client)
            deleted = api.delete_all_events()
            if self._toast_manager:
                self._toast_manager.show_success(
                    texts.ADMIN_BIPRO_EVENTS_ALL_DELETED.format(count=deleted)
                )
            self._load_bipro_events()
        except Exception as e:
            logger.error(f"Alle BiPRO-Events loeschen: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(texts.ADMIN_BIPRO_EVENTS_DELETE_ERROR)
