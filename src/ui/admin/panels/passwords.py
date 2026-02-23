"""
ACENCIA ATLAS - Admin Panel: Passwoerter-Verwaltung

Extrahiert aus admin_view.py (Zeilen 2523-2893).
"""

from typing import List, Dict

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from api.client import APIClient, APIError
from api.passwords import PasswordsAPI
from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100,
    ACCENT_500, ACCENT_100,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2, FONT_SIZE_CAPTION,
    RADIUS_MD, RADIUS_SM,
)
from ui.admin.workers import AdminWriteWorker
from ui.admin.dialogs import PasswordDialog

logger = logging.getLogger(__name__)


class PasswordsPanel(QWidget):
    """Admin-Panel fuer PDF/ZIP Passwort-Verwaltung."""

    def __init__(self, api_client: APIClient, toast_manager, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._passwords_api = PasswordsAPI(api_client)
        self._pw_data: List[Dict] = []
        self._pw_show_values: bool = False
        self._active_workers: List = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode zum Laden der Daten."""
        self._load_passwords()

    def _create_ui(self):
        """Erstellt den Passwoerter-Tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --- Header mit Titel und Aktionen ---
        header_layout = QHBoxLayout()

        title = QLabel(texts.PASSWORDS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900};
            font-weight: bold;
        """)
        header_layout.addWidget(title)

        subtitle = QLabel(texts.PASSWORDS_SUBTITLE)
        subtitle.setStyleSheet(f"font-family: {FONT_BODY}; color: {PRIMARY_500}; margin-left: 12px;")
        header_layout.addWidget(subtitle)

        header_layout.addStretch()

        # Filter: Typ
        type_label = QLabel(texts.PASSWORD_TYPE)
        type_label.setStyleSheet(f"font-family: {FONT_BODY}; color: {PRIMARY_500};")
        header_layout.addWidget(type_label)

        self._pw_type_filter = QComboBox()
        self._pw_type_filter.addItem(texts.PASSWORDS_ALL, "all")
        self._pw_type_filter.addItem(texts.PASSWORDS_PDF, "pdf")
        self._pw_type_filter.addItem(texts.PASSWORDS_ZIP, "zip")
        self._pw_type_filter.setStyleSheet(f"font-family: {FONT_BODY};")
        self._pw_type_filter.currentIndexChanged.connect(self._apply_passwords_filter)
        header_layout.addWidget(self._pw_type_filter)

        # Hinzufuegen Button
        add_btn = QPushButton(f"+ {texts.PASSWORD_ADD}")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px;
                font-family: {FONT_BODY};
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #e88a2d;
            }}
        """)
        add_btn.clicked.connect(self._add_password)
        header_layout.addWidget(add_btn)

        # Aktualisieren Button
        refresh_btn = QPushButton(texts.COSTS_REFRESH)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px;
                font-family: {FONT_BODY};
                background-color: {ACCENT_100};
                color: {PRIMARY_900};
                border: 1px solid {ACCENT_500};
                border-radius: {RADIUS_MD};
            }}
            QPushButton:hover {{
                background-color: {ACCENT_500};
                color: white;
            }}
        """)
        refresh_btn.clicked.connect(self._load_passwords)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # --- Passwoerter-Tabelle ---
        self._pw_table = QTableWidget()
        self._pw_table.setColumnCount(6)
        self._pw_table.setHorizontalHeaderLabels([
            texts.PASSWORD_TYPE,
            texts.PASSWORD_VALUE,
            texts.PASSWORD_DESCRIPTION,
            texts.PASSWORD_CREATED_AT,
            texts.PASSWORD_IS_ACTIVE,
            ""  # Aktionen
        ])
        self._pw_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._pw_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._pw_table.setAlternatingRowColors(True)
        self._pw_table.verticalHeader().setVisible(False)
        self._pw_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Spaltenbreiten
        header = self._pw_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 60)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 140)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 60)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 420)

        self._pw_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_SM};
                font-family: {FONT_BODY};
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
            QHeaderView::section {{
                background-color: {PRIMARY_100};
                padding: 8px;
                border: none;
                font-family: {FONT_BODY};
                font-weight: bold;
                color: {PRIMARY_900};
            }}
        """)

        layout.addWidget(self._pw_table)

    def _load_passwords(self):
        """Laedt alle Passwoerter vom Server."""
        try:
            pw_type = self._pw_type_filter.currentData()
            if pw_type == "all":
                self._pw_data = self._passwords_api.get_all_passwords()
            else:
                self._pw_data = self._passwords_api.get_all_passwords(pw_type)
            self._populate_pw_table()
        except APIError as e:
            logger.error(f"Fehler beim Laden der Passwoerter: {e}")
            self._toast_manager.show_error(texts.PASSWORD_ERROR_LOAD.format(error=str(e)))

    def _apply_passwords_filter(self):
        """Wendet den Typ-Filter an."""
        self._load_passwords()

    def _populate_pw_table(self):
        """Fuellt die Passwoerter-Tabelle."""
        self._pw_table.setRowCount(len(self._pw_data))
        self._pw_table.verticalHeader().setDefaultSectionSize(48)

        for row, pw in enumerate(self._pw_data):
            # Typ
            type_item = QTableWidgetItem(
                texts.PASSWORD_TYPE_PDF if pw.get('password_type') == 'pdf' else texts.PASSWORD_TYPE_ZIP
            )
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_bg = QColor('#e8f5e9') if pw.get('password_type') == 'pdf' else QColor('#e3f2fd')
            type_item.setBackground(type_bg)
            self._pw_table.setItem(row, 0, type_item)

            # Passwort-Wert (maskiert oder angezeigt)
            value = pw.get('password_value', '')
            display_value = value if self._pw_show_values else '*' * min(len(value), 12)
            value_item = QTableWidgetItem(display_value)
            value_item.setFont(QFont("Consolas", 10))
            self._pw_table.setItem(row, 1, value_item)

            # Beschreibung
            desc_item = QTableWidgetItem(pw.get('description') or '-')
            self._pw_table.setItem(row, 2, desc_item)

            # Erstellt am
            created = pw.get('created_at', '')
            if created:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created)
                    created = dt.strftime('%d.%m.%Y %H:%M')
                except Exception:
                    pass
            created_item = QTableWidgetItem(created)
            created_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._pw_table.setItem(row, 3, created_item)

            # Aktiv
            active = pw.get('is_active')
            active_text = "Ja" if active and str(active) == '1' else "Nein"
            active_item = QTableWidgetItem(active_text)
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if not (active and str(active) == '1'):
                active_item.setForeground(QColor('#e74c3c'))
            else:
                active_item.setForeground(QColor('#27ae60'))
            self._pw_table.setItem(row, 4, active_item)

            # Aktionen-Buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            # Anzeigen/Verbergen Toggle
            toggle_btn = QPushButton(texts.PASSWORD_SHOW if not self._pw_show_values else texts.PASSWORD_HIDE)
            toggle_btn.setFixedHeight(26)
            toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 2px 8px;
                    font-family: {FONT_BODY};
                    font-size: {FONT_SIZE_CAPTION};
                    background-color: {PRIMARY_100};
                    color: {PRIMARY_900};
                    border: none;
                    border-radius: {RADIUS_SM};
                }}
                QPushButton:hover {{ background-color: {PRIMARY_500}; color: white; }}
            """)
            toggle_btn.clicked.connect(self._toggle_pw_visibility)
            actions_layout.addWidget(toggle_btn)

            # Bearbeiten
            edit_btn = QPushButton(texts.PASSWORD_EDIT)
            edit_btn.setFixedHeight(26)
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 2px 8px;
                    font-family: {FONT_BODY};
                    font-size: {FONT_SIZE_CAPTION};
                    background-color: {ACCENT_100};
                    color: {PRIMARY_900};
                    border: none;
                    border-radius: {RADIUS_SM};
                }}
                QPushButton:hover {{ background-color: {ACCENT_500}; color: white; }}
            """)
            pw_id = pw.get('id')
            edit_btn.clicked.connect(lambda checked=False, pid=pw_id: self._edit_password(pid))
            actions_layout.addWidget(edit_btn)

            # Loeschen/Reaktivieren
            is_active = active and str(active) == '1'
            if is_active:
                del_btn = QPushButton(texts.PASSWORD_DELETE)
                del_btn.setFixedHeight(26)
                del_btn.setStyleSheet(f"""
                    QPushButton {{
                        padding: 2px 8px;
                        font-family: {FONT_BODY};
                        font-size: {FONT_SIZE_CAPTION};
                        background-color: #ffebee;
                        color: #c62828;
                        border: none;
                        border-radius: {RADIUS_SM};
                    }}
                    QPushButton:hover {{ background-color: #e74c3c; color: white; }}
                """)
                del_btn.clicked.connect(lambda checked=False, pid=pw_id: self._delete_password(pid))
                actions_layout.addWidget(del_btn)
            else:
                react_btn = QPushButton(texts.PASSWORD_REACTIVATE)
                react_btn.setFixedHeight(26)
                react_btn.setStyleSheet(f"""
                    QPushButton {{
                        padding: 2px 8px;
                        font-family: {FONT_BODY};
                        font-size: {FONT_SIZE_CAPTION};
                        background-color: #e8f5e9;
                        color: #2e7d32;
                        border: none;
                        border-radius: {RADIUS_SM};
                    }}
                    QPushButton:hover {{ background-color: #27ae60; color: white; }}
                """)
                react_btn.clicked.connect(lambda checked=False, pid=pw_id: self._reactivate_password(pid))
                actions_layout.addWidget(react_btn)

            self._pw_table.setCellWidget(row, 5, actions_widget)

    def _toggle_pw_visibility(self):
        """Schaltet die Sichtbarkeit der Passwort-Werte um."""
        self._pw_show_values = not self._pw_show_values
        self._populate_pw_table()

    def _add_password(self):
        """Oeffnet Dialog zum Hinzufuegen eines neuen Passworts."""
        dialog = PasswordDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            try:
                self._passwords_api.create_password(
                    data['password_type'],
                    data['password_value'],
                    data.get('description', '')
                )
                from services.pdf_unlock import clear_password_cache
                clear_password_cache()
                self._load_passwords()
            except APIError as e:
                self._toast_manager.show_error(texts.PASSWORD_ERROR_SAVE.format(error=str(e)))

    def _edit_password(self, password_id: int):
        """Oeffnet Dialog zum Bearbeiten eines Passworts."""
        pw_data = None
        for pw in self._pw_data:
            if pw.get('id') == password_id:
                pw_data = pw
                break

        if not pw_data:
            return

        dialog = PasswordDialog(self, pw_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            try:
                self._passwords_api.update_password(
                    password_id,
                    password_value=data.get('password_value'),
                    description=data.get('description')
                )
                from services.pdf_unlock import clear_password_cache
                clear_password_cache()
                self._load_passwords()
            except APIError as e:
                self._toast_manager.show_error(texts.PASSWORD_ERROR_SAVE.format(error=str(e)))

    def _delete_password(self, password_id: int):
        """Deaktiviert ein Passwort (Soft-Delete)."""
        pw_data = None
        for pw in self._pw_data:
            if pw.get('id') == password_id:
                pw_data = pw
                break

        if not pw_data:
            return

        reply = QMessageBox.question(
            self,
            texts.PASSWORD_CONFIRM_DELETE_TITLE,
            texts.PASSWORD_CONFIRM_DELETE.format(value=pw_data.get('password_value', '???')),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._passwords_api.delete_password(password_id)
                from services.pdf_unlock import clear_password_cache
                clear_password_cache()
                self._load_passwords()
            except APIError as e:
                self._toast_manager.show_error(texts.PASSWORD_ERROR_SAVE.format(error=str(e)))

    def _reactivate_password(self, password_id: int):
        """Reaktiviert ein deaktiviertes Passwort."""
        try:
            self._passwords_api.update_password(password_id, is_active=True)
            from services.pdf_unlock import clear_password_cache
            clear_password_cache()
            self._load_passwords()
        except APIError as e:
            self._toast_manager.show_error(texts.PASSWORD_ERROR_SAVE.format(error=str(e)))
