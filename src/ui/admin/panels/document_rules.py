"""
ACENCIA ATLAS - Admin Panel: Dokumenten-Regeln

Extrahiert aus admin_view.py (Zeilen 2982-3228).
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QGroupBox,
    QPushButton, QScrollArea,
)
from PySide6.QtGui import QFont

from api.client import APIClient
from api.document_rules import DocumentRulesAPI, DocumentRulesSettings
from i18n import de as texts
from ui.styles.tokens import ACCENT_500
from ui.admin.workers import AdminWriteWorker

logger = logging.getLogger(__name__)


class DocumentRulesPanel(QWidget):
    """Admin-Panel fuer Dokumenten-Regeln (Duplikate, leere Seiten)."""

    def __init__(self, api_client: APIClient, toast_manager, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._active_workers: list = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode zum Laden der Daten."""
        self._load_document_rules()

    def _create_ui(self):
        """Erstellt das Dokumenten-Regeln Panel mit 4 Regel-Sektionen."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Titel
        title = QLabel(texts.DOC_RULES_TITLE)
        title.setFont(QFont("Open Sans", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(texts.DOC_RULES_DESCRIPTION)
        desc.setFont(QFont("Open Sans", 10))
        desc.setStyleSheet(f"color: #64748b;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Scroll-Bereich fuer die 4 Sektionen
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(16)

        # Farb-Optionen fuer Dropdowns
        color_items = [
            ('green', texts.DOC_RULES_COLOR_GREEN),
            ('red', texts.DOC_RULES_COLOR_RED),
            ('blue', texts.DOC_RULES_COLOR_BLUE),
            ('orange', texts.DOC_RULES_COLOR_ORANGE),
            ('purple', texts.DOC_RULES_COLOR_PURPLE),
            ('pink', texts.DOC_RULES_COLOR_PINK),
            ('cyan', texts.DOC_RULES_COLOR_CYAN),
            ('yellow', texts.DOC_RULES_COLOR_YELLOW),
        ]

        def create_rule_section(title_text: str, desc_text: str,
                                action_items: list, color_items_list: list):
            """Erstellt eine Regel-Sektion mit Aktion-Dropdown + Farb-Dropdown."""
            group = QGroupBox(title_text)
            group.setFont(QFont("Open Sans", 11, QFont.Weight.DemiBold))
            group.setStyleSheet(f"""
                QGroupBox {{
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding: 16px 12px 12px 12px;
                    background: white;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 6px;
                }}
            """)
            g_layout = QVBoxLayout(group)
            g_layout.setSpacing(8)

            desc_label = QLabel(desc_text)
            desc_label.setFont(QFont("Open Sans", 9))
            desc_label.setStyleSheet("color: #64748b; border: none;")
            desc_label.setWordWrap(True)
            g_layout.addWidget(desc_label)

            # Aktion
            action_row = QHBoxLayout()
            action_label = QLabel(texts.DOC_RULES_ACTION_LABEL)
            action_label.setFixedWidth(80)
            action_label.setStyleSheet("border: none;")
            action_combo = QComboBox()
            for value, display in action_items:
                action_combo.addItem(display, value)
            action_combo.setMinimumWidth(250)
            action_row.addWidget(action_label)
            action_row.addWidget(action_combo)
            action_row.addStretch()
            g_layout.addLayout(action_row)

            # Farbe (initial versteckt)
            color_row = QHBoxLayout()
            color_label = QLabel(texts.DOC_RULES_COLOR_LABEL)
            color_label.setFixedWidth(80)
            color_label.setStyleSheet("border: none;")
            color_combo = QComboBox()
            for value, display in color_items_list:
                color_combo.addItem(display, value)
            color_combo.setMinimumWidth(250)
            color_row.addWidget(color_label)
            color_row.addWidget(color_combo)
            color_row.addStretch()

            color_container = QWidget()
            color_container.setLayout(color_row)
            color_container.setStyleSheet("border: none;")
            color_container.setVisible(False)
            g_layout.addWidget(color_container)

            def on_action_changed(idx):
                val = action_combo.itemData(idx)
                needs_color = val in ('color_both', 'color_new', 'color_file')
                color_container.setVisible(needs_color)

            action_combo.currentIndexChanged.connect(on_action_changed)

            return group, action_combo, color_combo, color_container

        # 1. Datei-Duplikate
        dup_actions = [
            ('none', texts.DOC_RULES_ACTION_NONE),
            ('color_both', texts.DOC_RULES_ACTION_COLOR_BOTH),
            ('color_new', texts.DOC_RULES_ACTION_COLOR_NEW),
            ('delete_new', texts.DOC_RULES_ACTION_DELETE_NEW),
            ('delete_old', texts.DOC_RULES_ACTION_DELETE_OLD),
        ]

        grp1, self._dr_file_dup_action, self._dr_file_dup_color, _ = create_rule_section(
            texts.DOC_RULES_FILE_DUP_TITLE, texts.DOC_RULES_FILE_DUP_DESC,
            dup_actions, color_items)
        scroll_layout.addWidget(grp1)

        # 2. Inhaltsduplikate
        grp2, self._dr_content_dup_action, self._dr_content_dup_color, _ = create_rule_section(
            texts.DOC_RULES_CONTENT_DUP_TITLE, texts.DOC_RULES_CONTENT_DUP_DESC,
            dup_actions, color_items)
        scroll_layout.addWidget(grp2)

        # 3. Teilweise leere Seiten
        partial_actions = [
            ('none', texts.DOC_RULES_ACTION_NONE),
            ('remove_pages', texts.DOC_RULES_ACTION_REMOVE_PAGES),
            ('color_file', texts.DOC_RULES_ACTION_COLOR_FILE),
        ]

        grp3, self._dr_partial_empty_action, self._dr_partial_empty_color, _ = create_rule_section(
            texts.DOC_RULES_PARTIAL_EMPTY_TITLE, texts.DOC_RULES_PARTIAL_EMPTY_DESC,
            partial_actions, color_items)
        scroll_layout.addWidget(grp3)

        # 4. Komplett leere Dateien
        full_actions = [
            ('none', texts.DOC_RULES_ACTION_NONE),
            ('delete', texts.DOC_RULES_ACTION_DELETE),
            ('color_file', texts.DOC_RULES_ACTION_COLOR_FILE),
        ]

        grp4, self._dr_full_empty_action, self._dr_full_empty_color, _ = create_rule_section(
            texts.DOC_RULES_FULL_EMPTY_TITLE, texts.DOC_RULES_FULL_EMPTY_DESC,
            full_actions, color_items)
        scroll_layout.addWidget(grp4)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Speichern-Button
        save_btn = QPushButton(texts.DOC_RULES_SAVE)
        save_btn.setMinimumHeight(36)
        save_btn.setMaximumWidth(200)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #e67e22; }}
        """)
        save_btn.clicked.connect(self._save_document_rules)
        layout.addWidget(save_btn)

        # Status-Label
        self._dr_status = QLabel("")
        self._dr_status.setVisible(False)
        self._dr_status.setWordWrap(True)
        layout.addWidget(self._dr_status)

    def _load_document_rules(self):
        """Laedt die Dokumenten-Regeln vom Server und setzt die UI-Werte."""
        try:
            api = DocumentRulesAPI(self._api_client)
            settings = api.get_rules()

            self._set_combo_by_data(self._dr_file_dup_action, settings.file_dup_action)
            self._set_combo_by_data(self._dr_file_dup_color, settings.file_dup_color or 'green')
            self._set_combo_by_data(self._dr_content_dup_action, settings.content_dup_action)
            self._set_combo_by_data(self._dr_content_dup_color, settings.content_dup_color or 'green')
            self._set_combo_by_data(self._dr_partial_empty_action, settings.partial_empty_action)
            self._set_combo_by_data(self._dr_partial_empty_color, settings.partial_empty_color or 'orange')
            self._set_combo_by_data(self._dr_full_empty_action, settings.full_empty_action)
            self._set_combo_by_data(self._dr_full_empty_color, settings.full_empty_color or 'red')
        except Exception as e:
            logger.error(f"Dokumenten-Regeln laden fehlgeschlagen: {e}")
            self._dr_status.setText(texts.DOC_RULES_LOAD_ERROR)
            self._dr_status.setStyleSheet(
                "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;")
            self._dr_status.setVisible(True)

    def _set_combo_by_data(self, combo: QComboBox, value: str):
        """Setzt eine QComboBox auf den Eintrag mit dem gegebenen Data-Wert."""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _save_document_rules(self):
        """Speichert die Dokumenten-Regeln auf dem Server."""
        settings = DocumentRulesSettings(
            file_dup_action=self._dr_file_dup_action.currentData() or 'none',
            file_dup_color=self._dr_file_dup_color.currentData() if self._dr_file_dup_action.currentData() in ('color_both', 'color_new') else None,
            content_dup_action=self._dr_content_dup_action.currentData() or 'none',
            content_dup_color=self._dr_content_dup_color.currentData() if self._dr_content_dup_action.currentData() in ('color_both', 'color_new') else None,
            partial_empty_action=self._dr_partial_empty_action.currentData() or 'none',
            partial_empty_color=self._dr_partial_empty_color.currentData() if self._dr_partial_empty_action.currentData() == 'color_file' else None,
            full_empty_action=self._dr_full_empty_action.currentData() or 'none',
            full_empty_color=self._dr_full_empty_color.currentData() if self._dr_full_empty_action.currentData() == 'color_file' else None,
        )

        try:
            api = DocumentRulesAPI(self._api_client)
            success = api.save_rules(settings)
            if success:
                self._dr_status.setText(texts.DOC_RULES_SAVE_SUCCESS)
                self._dr_status.setStyleSheet(
                    "color: #059669; background: #ecfdf5; padding: 6px 12px; border-radius: 4px;")
            else:
                self._dr_status.setText(texts.DOC_RULES_SAVE_ERROR.format(error="Server-Fehler"))
                self._dr_status.setStyleSheet(
                    "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;")
        except Exception as e:
            self._dr_status.setText(texts.DOC_RULES_SAVE_ERROR.format(error=str(e)))
            self._dr_status.setStyleSheet(
                "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;")
        self._dr_status.setVisible(True)
