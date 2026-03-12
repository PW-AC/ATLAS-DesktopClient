"""
ContactsView - Hauptansicht Kontakt-Karten-Grid mit Live-Suche.

Zeigt Kontakte als Karten-Grid, gefiltert nach filter_mode.
QThread fuer API-Calls, QTimer-Debounce fuer Suche.
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea,
    QGridLayout, QLabel, QPushButton, QFrame, QMessageBox,
)
from PySide6.QtCore import Signal, Qt, QTimer, QThread

from contact.api_client import ContactApiClient
from api.auth import AuthAPI
from ui.contact.contact_card_widget import ContactCard
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT, RADIUS_MD,
    get_button_primary_style, get_button_secondary_style,
)
from i18n import de as texts

logger = logging.getLogger(__name__)


class _ContactLoadWorker(QThread):
    """Laedt Kontakte basierend auf filter_mode."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: ContactApiClient, filter_mode: str):
        super().__init__()
        self._api = api
        self._filter_mode = filter_mode

    def run(self):
        try:
            if self._filter_mode == 'all':
                result = self._api.list_contacts()
            elif self._filter_mode == 'favorites':
                items = self._api.get_favorites()
                result = {'contacts': items, 'pagination': {}}
            elif self._filter_mode == 'recent_viewed':
                items = self._api.get_recent('viewed')
                result = {'contacts': items, 'pagination': {}}
            elif self._filter_mode == 'recent_called':
                items = self._api.get_recent('called')
                result = {'contacts': items, 'pagination': {}}
            elif self._filter_mode == 'callbacks':
                items = self._api.get_callbacks()
                result = {'contacts': self._callbacks_to_contacts(items), 'pagination': {}}
            else:
                result = {'contacts': [], 'pagination': {}}
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Kontakte laden fehlgeschlagen: {e}")
            self.error.emit(str(e))

    def _callbacks_to_contacts(self, callbacks: list) -> list:
        """Wandelt Callback-Liste in kontakt-aehnliche Dicts um."""
        out = []
        seen_ids = set()
        for cb in callbacks or []:
            if not isinstance(cb, dict):
                continue
            cid = cb.get('contact_id')
            if not cid or cid in seen_ids:
                continue
            seen_ids.add(cid)
            out.append({
                'id': cid,
                'display_name': cb.get('contact_name', ''),
                'first_name': cb.get('first_name', ''),
                'last_name': cb.get('last_name', ''),
                'phone': '',
                'open_callbacks': 1,
                'last_call_at': cb.get('callback_at') or cb.get('created_at'),
            })
        return out


class _ContactSearchWorker(QThread):
    """Fuehrt Kontaktsuche aus."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: ContactApiClient, query: str):
        super().__init__()
        self._api = api
        self._query = query

    def run(self):
        try:
            result = self._api.search(self._query)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Kontaktsuche fehlgeschlagen: {e}")
            self.error.emit(str(e))


class ContactsView(QWidget):
    """Hauptansicht Kontakt-Karten-Grid mit Live-Suche."""

    contact_selected = Signal(int)
    create_person_requested = Signal(str)
    create_company_requested = Signal(str)
    create_temp_note_requested = Signal(str)
    quick_call_note_requested = Signal()

    def __init__(self, contact_api: ContactApiClient, auth_api: AuthAPI, filter_mode: str = 'all', parent=None):
        super().__init__(parent)
        self._contact_api = contact_api
        self._auth_api = auth_api
        self._filter_mode = filter_mode
        self._load_worker = None
        self._search_worker = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._search_timer.timeout.connect(self._execute_search)
        self._current_contacts: list = []
        self._last_search_query = ''
        self._setup_ui()
        QTimer.singleShot(0, self.refresh)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(texts.CONTACT_SEARCH_PLACEHOLDER)
        self._search_input.setMinimumHeight(36)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 8px 12px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
            }}
            QLineEdit:focus {{
                border-color: {ACCENT_500};
            }}
        """)
        self._search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_input)

        action_bar = QHBoxLayout()
        user = self._auth_api.current_user if self._auth_api else None
        has_edit = user and user.has_permission('contact.edit')
        self._new_contact_btn = QPushButton(texts.CONTACT_NEW)
        self._new_contact_btn.setStyleSheet(get_button_primary_style())
        self._new_contact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_contact_btn.setVisible(has_edit)
        self._new_contact_btn.clicked.connect(self._on_new_contact)
        action_bar.addWidget(self._new_contact_btn)
        if self._filter_mode == 'all':
            self._quick_note_btn = QPushButton(texts.CONTACT_QUICK_CALL_NOTE)
            self._quick_note_btn.setStyleSheet(get_button_secondary_style())
            self._quick_note_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._quick_note_btn.setVisible(has_edit)
            self._quick_note_btn.clicked.connect(self._on_quick_call_note)
            action_bar.addWidget(self._quick_note_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """)
        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._scroll.setWidget(self._grid_container)
        layout.addWidget(self._scroll)

        self._no_results_widget = QFrame()
        self._no_results_widget.setVisible(False)
        self._no_results_widget.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 24px;
            }}
        """)
        no_layout = QVBoxLayout(self._no_results_widget)
        no_layout.setSpacing(16)
        self._no_results_label = QLabel()
        self._no_results_label.setWordWrap(True)
        self._no_results_label.setStyleSheet(f"""
            color: {PRIMARY_900}; font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
        """)
        no_layout.addWidget(self._no_results_label)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        self._btn_person = QPushButton(texts.CONTACT_NO_RESULTS_CREATE_PERSON)
        self._btn_person.setStyleSheet(get_button_primary_style())
        self._btn_person.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_person.clicked.connect(self._on_create_person)
        self._btn_company = QPushButton(texts.CONTACT_NO_RESULTS_CREATE_COMPANY)
        self._btn_company.setStyleSheet(get_button_primary_style())
        self._btn_company.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_company.clicked.connect(self._on_create_company)
        self._btn_temp_note = QPushButton(texts.CONTACT_NO_RESULTS_TEMP_NOTE)
        self._btn_temp_note.setStyleSheet(get_button_primary_style())
        self._btn_temp_note.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_temp_note.clicked.connect(self._on_create_temp_note)
        btn_layout.addWidget(self._btn_person)
        btn_layout.addWidget(self._btn_company)
        btn_layout.addWidget(self._btn_temp_note)
        btn_layout.addStretch()
        no_layout.addLayout(btn_layout)
        layout.addWidget(self._no_results_widget)

    def _on_search_changed(self):
        self._search_timer.stop()
        query = self._search_input.text().strip()
        if len(query) >= 2:
            self._search_timer.start()
        elif len(query) == 0:
            self.refresh()

    def _execute_search(self):
        query = self._search_input.text().strip()
        if len(query) < 2:
            self.refresh()
            return
        if self._search_worker and self._search_worker.isRunning():
            return
        self._search_worker = _ContactSearchWorker(self._contact_api, query)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_search_finished(self, result: dict):
        contacts = result.get('contacts', [])
        self._render_contacts(contacts, is_search=True)

    def _on_search_error(self, error: str):
        logger.error(f"Kontaktsuche: {error}")
        self._render_contacts([])

    def _on_load_finished(self, result: dict):
        contacts = result.get('contacts', [])
        self._render_contacts(contacts)

    def _on_load_error(self, error: str):
        logger.error(f"Kontakte laden: {error}")
        self._render_contacts([])

    def _render_contacts(self, contacts: list, is_search: bool = False):
        seen_ids = set()
        unique = []
        for c in contacts:
            if not isinstance(c, dict):
                continue
            cid = c.get('id')
            if cid and cid in seen_ids:
                continue
            if cid:
                seen_ids.add(cid)
            unique.append(c)

        self._current_contacts = unique
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not unique:
            self._grid_container.setVisible(False)
            self._no_results_widget.setVisible(True)
            query = self._search_input.text().strip() if is_search else ''
            self._no_results_label.setText(
                texts.CONTACT_NO_RESULTS_FOR_QUERY.format(query=query) if query
                else texts.CONTACT_NO_RESULTS
            )
            self._last_search_query = query
            return

        self._grid_container.setVisible(True)
        self._no_results_widget.setVisible(False)
        cols = max(1, self._scroll.viewport().width() // 296)
        for i, contact in enumerate(unique):
            card = ContactCard(contact)
            card.clicked.connect(self.contact_selected.emit)
            card.delete_requested.connect(self._on_delete_requested)
            row, col = divmod(i, cols)
            self._grid_layout.addWidget(card, row, col)

    def _on_new_contact(self):
        self.contact_selected.emit(0)

    def _on_quick_call_note(self):
        self.quick_call_note_requested.emit()

    def _on_create_person(self):
        query = getattr(self, '_last_search_query', '') or self._search_input.text().strip()
        self.create_person_requested.emit(query)

    def _on_create_company(self):
        query = getattr(self, '_last_search_query', '') or self._search_input.text().strip()
        self.create_company_requested.emit(query)

    def _on_create_temp_note(self):
        query = getattr(self, '_last_search_query', '') or self._search_input.text().strip()
        self.create_temp_note_requested.emit(query)

    def _on_delete_requested(self, contact_id: int):
        reply = QMessageBox.question(
            self, texts.CONTACT_DELETE, texts.CONTACT_DELETE_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._contact_api.delete_contact(contact_id)
            self.refresh()
        except Exception as e:
            logger.error("Kontakt loeschen fehlgeschlagen: %s", e)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._current_contacts:
            self._render_contacts(self._current_contacts)

    def refresh(self):
        query = self._search_input.text().strip()
        if len(query) >= 2:
            self._execute_search()
            return
        if self._load_worker and self._load_worker.isRunning():
            return
        self._load_worker = _ContactLoadWorker(self._contact_api, self._filter_mode)
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.start()
