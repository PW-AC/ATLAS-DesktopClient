"""
ACENCIA ATLAS - Aktivitaetslog Panel

Standalone QWidget fuer das Aktivitaetslog im Admin-Bereich.
Extrahiert aus admin_view.py (Schritt 5 Refactoring).
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QLineEdit, QDateEdit,
    QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor

from api.client import APIClient
from api.admin import AdminAPI
from i18n import de as texts

from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500,
    ACCENT_500,
    FONT_HEADLINE,
    RADIUS_MD,
)
from ui.admin.workers import LoadActivityWorker

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    'success': '#27ae60',
    'error': '#e74c3c',
    'denied': '#f39c12',
}

CATEGORY_NAMES = {
    'auth': texts.ACTIVITY_CAT_AUTH,
    'document': texts.ACTIVITY_CAT_DOCUMENT,
    'bipro': texts.ACTIVITY_CAT_BIPRO,
    'vu_connection': texts.ACTIVITY_CAT_VU_CONNECTION,
    'gdv': texts.ACTIVITY_CAT_GDV,
    'admin': texts.ACTIVITY_CAT_ADMIN,
    'system': texts.ACTIVITY_CAT_SYSTEM,
    'ai': texts.ACTIVITY_CAT_AI,
}


class ActivityLogPanel(QWidget):
    """Aktivitaetslog: Filter, Pagination, farbkodierte Status."""

    def __init__(self, api_client: APIClient, toast_manager,
                 admin_api: AdminAPI, **kwargs):
        super().__init__()
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._admin_api = admin_api
        self._activity_page = 1
        self._activity_per_page = 50
        self._active_workers = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode: Setzt Seite zurueck und laedt."""
        self._activity_page = 1
        self._load_activity()

    # ----------------------------------------------------------------
    # UI
    # ----------------------------------------------------------------

    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Toolbar
        toolbar = QHBoxLayout()

        title = QLabel(texts.ADMIN_ACTIVITY_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.setStyleSheet(f"border: 1px solid {PRIMARY_500}; border-radius: {RADIUS_MD}; color: {PRIMARY_500};")
        refresh_btn.clicked.connect(self._load_activity)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        # Filter-Leiste
        filter_bar = QHBoxLayout()

        # Kategorie
        filter_bar.addWidget(QLabel(texts.ADMIN_ACTIVITY_FILTER_CATEGORY + ":"))
        self._activity_category_combo = QComboBox()
        self._activity_category_combo.setMinimumWidth(150)
        self._activity_category_combo.addItem(texts.ADMIN_ACTIVITY_FILTER_ALL, '')
        for cat_key, cat_name in CATEGORY_NAMES.items():
            self._activity_category_combo.addItem(cat_name, cat_key)
        filter_bar.addWidget(self._activity_category_combo)

        # Status
        filter_bar.addWidget(QLabel(texts.ADMIN_ACTIVITY_FILTER_STATUS + ":"))
        self._activity_status_combo = QComboBox()
        self._activity_status_combo.addItem(texts.ADMIN_ACTIVITY_FILTER_ALL, '')
        self._activity_status_combo.addItem(texts.ACTIVITY_STATUS_SUCCESS, 'success')
        self._activity_status_combo.addItem(texts.ACTIVITY_STATUS_ERROR, 'error')
        self._activity_status_combo.addItem(texts.ACTIVITY_STATUS_DENIED, 'denied')
        filter_bar.addWidget(self._activity_status_combo)

        # Von/Bis
        filter_bar.addWidget(QLabel(texts.ADMIN_ACTIVITY_FILTER_FROM + ":"))
        self._activity_from_date = QDateEdit()
        self._activity_from_date.setCalendarPopup(True)
        self._activity_from_date.setDate(QDate.currentDate().addDays(-7))
        self._activity_from_date.setDisplayFormat("dd.MM.yyyy")
        filter_bar.addWidget(self._activity_from_date)

        filter_bar.addWidget(QLabel(texts.ADMIN_ACTIVITY_FILTER_TO + ":"))
        self._activity_to_date = QDateEdit()
        self._activity_to_date.setCalendarPopup(True)
        self._activity_to_date.setDate(QDate.currentDate())
        self._activity_to_date.setDisplayFormat("dd.MM.yyyy")
        filter_bar.addWidget(self._activity_to_date)

        # Suche
        self._activity_search = QLineEdit()
        self._activity_search.setPlaceholderText(texts.ADMIN_ACTIVITY_FILTER_SEARCH)
        self._activity_search.setMinimumWidth(180)
        self._activity_search.returnPressed.connect(self._load_activity)
        filter_bar.addWidget(self._activity_search)

        # Filter-Button
        filter_btn = QPushButton(texts.ADMIN_ACTIVITY_FILTER_SEARCH.replace('...', ''))
        filter_btn.setStyleSheet(f"background-color: {ACCENT_500}; color: white; border: none; border-radius: {RADIUS_MD}; padding: 6px 16px;")
        filter_btn.clicked.connect(self._load_activity)
        filter_bar.addWidget(filter_btn)

        layout.addLayout(filter_bar)

        # Tabelle
        self._activity_table = QTableWidget()
        self._activity_table.setColumnCount(7)
        self._activity_table.setHorizontalHeaderLabels([
            texts.ADMIN_COL_TIMESTAMP, texts.ADMIN_COL_USER, texts.ADMIN_COL_CATEGORY,
            texts.ADMIN_COL_ACTION, texts.ADMIN_COL_DESCRIPTION, texts.ADMIN_COL_IP,
            texts.ADMIN_COL_STATUS
        ])
        self._activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._activity_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._activity_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._activity_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._activity_table.setAlternatingRowColors(True)
        self._activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._activity_table.verticalHeader().setVisible(False)
        layout.addWidget(self._activity_table)

        # Pagination
        pagination_bar = QHBoxLayout()

        self._activity_total_label = QLabel("")
        self._activity_total_label.setStyleSheet(f"color: {PRIMARY_500};")
        pagination_bar.addWidget(self._activity_total_label)
        pagination_bar.addStretch()

        self._btn_prev_page = QPushButton("← Vorherige")
        self._btn_prev_page.setEnabled(False)
        self._btn_prev_page.clicked.connect(self._activity_prev_page)
        pagination_bar.addWidget(self._btn_prev_page)

        self._activity_page_label = QLabel("")
        pagination_bar.addWidget(self._activity_page_label)

        self._btn_next_page = QPushButton("Naechste →")
        self._btn_next_page.setEnabled(False)
        self._btn_next_page.clicked.connect(self._activity_next_page)
        pagination_bar.addWidget(self._btn_next_page)

        layout.addLayout(pagination_bar)

    # ----------------------------------------------------------------
    # Data loading
    # ----------------------------------------------------------------

    def _load_activity(self):
        """Laedt Aktivitaetslog mit aktuellen Filtern."""
        filters = {
            'page': self._activity_page,
            'per_page': self._activity_per_page,
        }

        category = self._activity_category_combo.currentData()
        if category:
            filters['action_category'] = category

        status = self._activity_status_combo.currentData()
        if status:
            filters['status'] = status

        from_date = self._activity_from_date.date().toString('yyyy-MM-dd')
        filters['from_date'] = from_date

        to_date = self._activity_to_date.date().toString('yyyy-MM-dd')
        filters['to_date'] = to_date

        search = self._activity_search.text().strip()
        if search:
            filters['search'] = search

        worker = LoadActivityWorker(self._admin_api, filters)
        worker.finished.connect(self._on_activity_loaded)
        worker.error.connect(lambda e: self._toast_manager.show_error(texts.ADMIN_ACTIVITY_LOAD_ERROR.format(error=e)) if hasattr(self, '_toast_manager') else None)
        worker.finished.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        worker.error.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        self._active_workers.append(worker)
        worker.start()

    def _on_activity_loaded(self, result: dict):
        """Callback wenn Log geladen wurde."""
        items = result.get('items', [])
        total = result.get('total', 0)
        page = result.get('page', 1)
        total_pages = result.get('total_pages', 0)

        self._activity_table.setRowCount(len(items))

        for row, item in enumerate(items):
            # Zeitpunkt
            ts = item.get('created_at', '-')
            if ts and ts != '-':
                ts = ts[:19].replace('T', ' ')
            self._activity_table.setItem(row, 0, QTableWidgetItem(str(ts)))

            # Nutzer
            self._activity_table.setItem(row, 1, QTableWidgetItem(item.get('username', '-')))

            # Kategorie
            cat_key = item.get('action_category', '')
            cat_name = CATEGORY_NAMES.get(cat_key, cat_key)
            self._activity_table.setItem(row, 2, QTableWidgetItem(cat_name))

            # Aktion
            self._activity_table.setItem(row, 3, QTableWidgetItem(item.get('action', '')))

            # Beschreibung
            self._activity_table.setItem(row, 4, QTableWidgetItem(item.get('description', '')))

            # IP
            self._activity_table.setItem(row, 5, QTableWidgetItem(item.get('ip_address', '')))

            # Status (farbkodiert)
            status = item.get('status', 'success')
            status_text = {
                'success': texts.ACTIVITY_STATUS_SUCCESS,
                'error': texts.ACTIVITY_STATUS_ERROR,
                'denied': texts.ACTIVITY_STATUS_DENIED
            }.get(status, status)
            status_item = QTableWidgetItem(status_text)
            color = STATUS_COLORS.get(status, PRIMARY_500)
            status_item.setForeground(QColor(color))
            self._activity_table.setItem(row, 6, status_item)

        # Pagination aktualisieren
        self._activity_total_label.setText(texts.ADMIN_ACTIVITY_TOTAL.format(total=total))
        self._activity_page_label.setText(texts.ADMIN_ACTIVITY_PAGE.format(page=page, total_pages=max(total_pages, 1)))
        self._btn_prev_page.setEnabled(page > 1)
        self._btn_next_page.setEnabled(page < total_pages)

    # ----------------------------------------------------------------
    # Pagination
    # ----------------------------------------------------------------

    def _activity_prev_page(self):
        if self._activity_page > 1:
            self._activity_page -= 1
            self._load_activity()

    def _activity_next_page(self):
        self._activity_page += 1
        self._load_activity()
