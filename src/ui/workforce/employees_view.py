"""
ACENCIA ATLAS - Workforce Employees View

Mitarbeiter-Uebersicht mit Arbeitgeber-Auswahl, Suche, Statusfilter,
Lazy-Load (Infinite Scroll) und Sync-Funktion.
Rechtsklick-Kontextmenue zeigt alle verfuegbaren Daten gruppiert an.
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QHeaderView,
    QFrame, QAbstractItemView, QSplitter, QScrollArea,
    QDialog, QGridLayout, QMenu, QFormLayout,
)
from PySide6.QtCore import Qt, QThreadPool, QTimer, QRunnable, QObject, Signal
from PySide6.QtGui import QFont, QColor, QAction, QGuiApplication

from workforce.api_client import WorkforceApiClient
from workforce.workers import SyncWorker
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, ACCENT_100,
    FONT_HEADLINE, FONT_BODY, FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT, RADIUS_MD, RADIUS_SM,
    SUCCESS, ERROR, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED, TEXT_INVERSE,
    get_button_primary_style, get_button_secondary_style, get_input_style,
    get_dialog_style,
)
from i18n import de as texts

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Detail-Fetch Worker
# ═══════════════════════════════════════════════════════════════

class _FetchDetailSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)


class _FetchDetailWorker(QRunnable):
    """Laedt details_json fuer einen einzelnen Mitarbeiter."""

    def __init__(self, wf_api: WorkforceApiClient, employer_id: int, employee_id: int):
        super().__init__()
        self.signals = _FetchDetailSignals()
        self._api = wf_api
        self._employer_id = employer_id
        self._employee_id = employee_id

    def run(self):
        try:
            result = self._api.get_employee(self._employer_id, self._employee_id)
            self.signals.finished.emit(result)
        except Exception as e:
            logger.error(f"Mitarbeiter-Detail laden fehlgeschlagen: {e}")
            self.signals.error.emit(str(e))


# ═══════════════════════════════════════════════════════════════
# Klickbarer Wert (Kopieren in Zwischenablage)
# ═══════════════════════════════════════════════════════════════

class _ClickableValue(QLabel):
    """QLabel das bei Linksklick den Wert in die Zwischenablage kopiert."""

    def __init__(self, value: str, field_label: str, toast_manager=None, parent=None):
        display = value if value and value != 'None' else '-'
        super().__init__(display, parent)
        self._value = value or ''
        self._field_label = field_label
        self._toast_manager = toast_manager
        if self._value and self._value != '-':
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._value and self._value != '-':
            QGuiApplication.clipboard().setText(self._value)
            if self._toast_manager:
                self._toast_manager.show_success(
                    texts.WF_VALUE_COPIED.format(label=self._field_label)
                )
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════
# Detail-Dialog (Kontextmenue -> "Alle Details anzeigen")
# ═══════════════════════════════════════════════════════════════

class EmployeeDetailDialog(QDialog):
    """
    Zeigt ALLE verfuegbaren Mitarbeiterdaten gruppiert an.
    Layout orientiert sich am Original-HR-Tool mit Karten-Grid.
    """

    def __init__(self, parent, employee_full: dict, toast_manager=None):
        super().__init__(parent)
        self._emp = employee_full
        self._toast_manager = toast_manager
        self._details_json = employee_full.get('details_json') or {}
        self._groups = self._details_json.get('details') or {}

        first = self._details_json.get('firstName') or employee_full.get('first_name', '')
        last = self._details_json.get('lastName') or employee_full.get('last_name', '')
        self._name = f"{first} {last}".strip()
        self._position = (
            self._details_json.get('position')
            or employee_full.get('position', '')
        )

        self.setWindowTitle(f"{texts.WF_EMPLOYEE_DETAILS_TITLE} – {self._name}")
        self.setMinimumSize(800, 500)
        self.resize(900, 620)
        self.setStyleSheet(get_dialog_style())
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(self._name)
        name_lbl.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: 18pt;
            color: {PRIMARY_900}; font-weight: bold;
            padding: 24px 28px 0px 28px;
        """)
        outer.addWidget(name_lbl)

        if self._position:
            pos_lbl = QLabel(self._position)
            pos_lbl.setStyleSheet(f"""
                color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};
                padding: 0px 28px 12px 28px;
            """)
            outer.addWidget(pos_lbl)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
        outer.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(24, 20, 24, 24)
        grid.setSpacing(16)

        if self._groups:
            col = 0
            row_idx = 0
            max_cols = 4
            for group_name, fields in self._groups.items():
                if not fields:
                    continue
                card = self._build_group_card(group_name, fields)
                grid.addWidget(card, row_idx, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row_idx += 1

            self._add_db_meta_card(grid, row_idx, col)
        else:
            self._build_fallback_view(grid)

        grid.setRowStretch(grid.rowCount(), 1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        close_row = QHBoxLayout()
        close_row.setContentsMargins(24, 8, 24, 16)
        close_row.addStretch()
        close_btn = QPushButton(texts.CLOSE if hasattr(texts, 'CLOSE') else "Schliessen")
        close_btn.setStyleSheet(get_button_secondary_style())
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        outer.addLayout(close_row)

    def _build_group_card(self, title: str, fields: list) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header = QLabel(title)
        header.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: 11pt;
            color: {PRIMARY_900}; font-weight: bold;
            border: none; padding: 0;
        """)
        layout.addWidget(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_DEFAULT}; border: none;")
        layout.addWidget(sep)

        for field in fields:
            label_text = field.get('label', '?')
            value = field.get('value', '')
            if value is None or value == '':
                continue

            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10pt; border: none; padding: 0;")
            lbl.setMinimumWidth(100)
            row.addWidget(lbl)

            val = _ClickableValue(str(value), label_text, self._toast_manager)
            val.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 10pt; font-weight: 500; border: none; padding: 0;")
            val.setWordWrap(True)
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(val, 1)

            layout.addLayout(row)

        layout.addStretch()
        return card

    def _add_db_meta_card(self, grid: QGridLayout, row_idx: int, col: int):
        """Karte mit DB-Metadaten (ID, Provider-PID, Hash, Sync-Datum)."""
        meta_fields = []
        if self._emp.get('id'):
            meta_fields.append({'label': 'DB-ID', 'value': self._emp['id']})
        if self._emp.get('provider_pid'):
            meta_fields.append({'label': 'Provider-ID', 'value': self._emp['provider_pid']})
        if self._emp.get('data_hash'):
            meta_fields.append({'label': 'Daten-Hash', 'value': self._emp['data_hash'][:16] + '...'})
        if self._emp.get('last_synced_at'):
            meta_fields.append({'label': 'Letzte Sync', 'value': self._emp['last_synced_at']})
        if self._emp.get('created_at'):
            meta_fields.append({'label': 'Erstellt', 'value': self._emp['created_at']})

        if meta_fields:
            card = self._build_group_card("Systeminformationen (ATLAS)", meta_fields)
            grid.addWidget(card, row_idx, col)

    def _build_fallback_view(self, grid: QGridLayout):
        """Fallback wenn kein details_json vorhanden ist."""
        flat_fields = []
        skip_keys = {'details_json', 'details', 'data_hash'}
        source = self._details_json if self._details_json else self._emp
        for key, value in source.items():
            if key in skip_keys or value is None or value == '' or isinstance(value, (dict, list)):
                continue
            flat_fields.append({'label': key, 'value': value})

        if flat_fields:
            card = self._build_group_card(texts.WF_EMPLOYEE_DETAILS_TITLE, flat_fields)
            grid.addWidget(card, 0, 0, 1, 2)
        else:
            lbl = QLabel(texts.WF_EMPLOYEE_NO_DETAILS)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};")
            grid.addWidget(lbl, 0, 0)


# ═══════════════════════════════════════════════════════════════
# Employees View (Hauptansicht)
# ═══════════════════════════════════════════════════════════════

class EmployeesView(QWidget):
    """Mitarbeiter-Liste mit Sync, Suche, Filter und Lazy-Load."""

    PAGE_SIZE = 50

    def __init__(self, wf_api: WorkforceApiClient, thread_pool: QThreadPool):
        super().__init__()
        self._wf_api = wf_api
        self._thread_pool = thread_pool
        self._toast_manager = None
        self._employers: list[dict] = []
        self._current_page = 1
        self._total_pages = 1
        self._total_count = 0
        self._is_loading = False
        self._syncing = False
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._search_timer.timeout.connect(self._load_employees_reset)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel(texts.WF_EMPLOYEES_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900}; font-weight: bold;
        """)
        header.addWidget(title)
        header.addStretch()

        self._sync_btn = QPushButton(texts.WF_SYNC_BTN)
        self._sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sync_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px; font-family: {FONT_BODY};
                background-color: {ACCENT_500}; color: white;
                border: none; border-radius: {RADIUS_MD}; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
            QPushButton:disabled {{ background-color: {BG_SECONDARY}; color: {TEXT_DISABLED}; }}
        """)
        self._sync_btn.clicked.connect(self._on_sync)
        header.addWidget(self._sync_btn)

        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        emp_label = QLabel(texts.WF_EMPLOYER_SELECT)
        emp_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-family: {FONT_BODY};")
        toolbar.addWidget(emp_label)

        self._employer_combo = QComboBox()
        self._employer_combo.setMinimumWidth(220)
        self._employer_combo.currentIndexChanged.connect(self._on_employer_changed)
        toolbar.addWidget(self._employer_combo)

        toolbar.addSpacing(16)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(texts.WF_EMPLOYEES_SEARCH_PLACEHOLDER)
        self._search_input.setMinimumWidth(200)
        self._search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search_input)

        status_label = QLabel(texts.WF_EMPLOYEES_STATUS_FILTER)
        status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-family: {FONT_BODY};")
        toolbar.addWidget(status_label)

        self._status_combo = QComboBox()
        self._status_combo.addItem(texts.WF_FILTER_ALL, "all")
        self._status_combo.addItem(texts.WF_FILTER_ACTIVE, "active")
        self._status_combo.addItem(texts.WF_FILTER_INACTIVE, "inactive")
        self._status_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._status_combo)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            texts.WF_COL_FIRST_NAME, texts.WF_COL_LAST_NAME,
            texts.WF_COL_EMAIL, texts.WF_COL_DEPARTMENT,
            texts.WF_COL_POSITION, texts.WF_COL_STATUS,
        ])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(36)

        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.currentCellChanged.connect(self._on_row_selected)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)

        vbar = self._table.verticalScrollBar()
        vbar.valueChanged.connect(self._on_scroll_changed)

        table_layout.addWidget(self._table, 1)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        table_layout.addWidget(self._count_label)

        self._splitter.addWidget(table_container)

        self._detail_panel = QScrollArea()
        self._detail_panel.setWidgetResizable(True)
        self._detail_panel.setMinimumWidth(280)
        self._detail_content = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_content)
        self._detail_layout.setContentsMargins(16, 16, 16, 16)
        self._detail_layout.setSpacing(8)
        self._detail_placeholder = QLabel(texts.WF_EMPLOYEES_SELECT_ROW)
        self._detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_placeholder.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};")
        self._detail_layout.addWidget(self._detail_placeholder)
        self._detail_layout.addStretch()
        self._detail_panel.setWidget(self._detail_content)
        self._splitter.addWidget(self._detail_panel)

        self._splitter.setSizes([700, 300])
        layout.addWidget(self._splitter, 1)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(f"color: {ACCENT_500}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._progress_label)

    # ── Data Loading ────────────────────────────────────────────

    def refresh(self):
        self._load_employers()

    def _load_employers(self):
        try:
            self._employers = self._wf_api.get_employers()
            current_data = self._employer_combo.currentData()
            self._employer_combo.blockSignals(True)
            self._employer_combo.clear()
            if not self._employers:
                self._employer_combo.addItem(texts.WF_NO_EMPLOYERS, None)
            else:
                for emp in self._employers:
                    self._employer_combo.addItem(emp.get('name', '?'), emp.get('id'))
                if current_data:
                    idx = next(
                        (i for i, e in enumerate(self._employers) if e.get('id') == current_data), 0
                    )
                    self._employer_combo.setCurrentIndex(idx)
            self._employer_combo.blockSignals(False)
            self._load_employees_reset()
        except Exception as e:
            logger.error(f"Arbeitgeber laden: {e}")

    def _on_employer_changed(self):
        self._load_employees_reset()

    def _on_search_changed(self):
        self._search_timer.start()

    def _on_filter_changed(self):
        self._load_employees_reset()

    def _load_employees_reset(self):
        """Tabelle leeren und ab Seite 1 neu laden."""
        self._current_page = 1
        self._total_pages = 1
        self._total_count = 0
        self._table.setRowCount(0)
        self._load_employees_page()

    def _load_employees_page(self):
        """Aktuelle Seite laden und an Tabelle anhaengen."""
        employer_id = self._employer_combo.currentData()
        if not employer_id or self._is_loading:
            return

        self._is_loading = True
        status_val = self._status_combo.currentData()
        status_param = status_val if status_val != 'all' else None
        search = self._search_input.text().strip() or None

        try:
            result = self._wf_api.get_employees(
                employer_id, page=self._current_page,
                per_page=self.PAGE_SIZE, status=status_param, search=search,
            )
            employees = result.get('employees', [])
            pagination = result.get('pagination', {})
            self._total_pages = pagination.get('pages', 1)
            self._total_count = pagination.get('total', 0)

            self._append_rows(employees)
            self._count_label.setText(
                texts.WF_EMPLOYEES_COUNT.format(count=self._total_count)
            )
        except Exception as e:
            logger.error(f"Mitarbeiter laden: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(texts.WF_EMPLOYEES_LOAD_ERROR.format(error=str(e)))
        finally:
            self._is_loading = False

    def _append_rows(self, employees: list):
        """Zeilen an bestehende Tabelle anhaengen (Lazy Load)."""
        self._table.setSortingEnabled(False)
        start_row = self._table.rowCount()
        self._table.setRowCount(start_row + len(employees))

        for i, emp in enumerate(employees):
            row = start_row + i

            self._table.setItem(row, 0, QTableWidgetItem(emp.get('first_name', '')))
            self._table.setItem(row, 1, QTableWidgetItem(emp.get('last_name', '')))
            self._table.setItem(row, 2, QTableWidgetItem(emp.get('email', '')))
            self._table.setItem(row, 3, QTableWidgetItem(emp.get('department', '')))
            self._table.setItem(row, 4, QTableWidgetItem(emp.get('position', '')))

            status = emp.get('status', 'active')
            status_item = QTableWidgetItem(f"● {status}")
            color = SUCCESS if status == 'active' else TEXT_DISABLED
            status_item.setForeground(QColor(color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 5, status_item)

            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, emp)

        self._table.setSortingEnabled(True)

    # ── Lazy Load (Infinite Scroll) ────────────────────────────

    def _on_scroll_changed(self, value: int):
        vbar = self._table.verticalScrollBar()
        if vbar.maximum() == 0:
            return
        if value >= vbar.maximum() - 20 and not self._is_loading:
            if self._current_page < self._total_pages:
                self._current_page += 1
                self._load_employees_page()

    # ── Detail Panel (rechte Seite) ────────────────────────────

    def _on_row_selected(self, row: int, _col: int, _prev_row: int, _prev_col: int):
        if row < 0 or row >= self._table.rowCount():
            return
        item = self._table.item(row, 0)
        if not item:
            return
        emp = item.data(Qt.ItemDataRole.UserRole)
        if not emp:
            return

        self._show_detail_basic(emp)

        employer_id = self._employer_combo.currentData()
        employee_id = emp.get('id')
        if employer_id and employee_id:
            worker = _FetchDetailWorker(self._wf_api, employer_id, employee_id)
            worker.signals.finished.connect(self._on_detail_panel_loaded)
            worker.signals.error.connect(lambda e: logger.error(f"Detail-Panel laden: {e}"))
            self._thread_pool.start(worker)

    def _show_detail_basic(self, emp: dict):
        """Sofort die Basisdaten anzeigen (aus der Liste)."""
        self._clear_detail_layout()

        name_lbl = QLabel(f"{emp.get('first_name', '')} {emp.get('last_name', '')}")
        name_lbl.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: 13pt;
            color: {PRIMARY_900}; font-weight: bold;
        """)
        self._detail_layout.addWidget(name_lbl)

        if emp.get('position'):
            pos_lbl = QLabel(emp['position'])
            pos_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};")
            self._detail_layout.addWidget(pos_lbl)

        loading = QLabel(texts.WF_EMPLOYEE_LOADING_DETAILS)
        loading.setStyleSheet(f"color: {ACCENT_500}; font-size: {FONT_SIZE_CAPTION}; padding-top: 8px;")
        self._detail_layout.addWidget(loading)
        self._detail_layout.addStretch()

    def _on_detail_panel_loaded(self, employee_full: dict):
        """Vollstaendige Daten im rechten Panel anzeigen."""
        self._clear_detail_layout()

        details_json = employee_full.get('details_json') or {}
        groups = details_json.get('details') or {}

        first = details_json.get('firstName') or employee_full.get('first_name', '')
        last = details_json.get('lastName') or employee_full.get('last_name', '')
        position = details_json.get('position') or employee_full.get('position', '')

        name_lbl = QLabel(f"{first} {last}".strip())
        name_lbl.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: 13pt;
            color: {PRIMARY_900}; font-weight: bold;
        """)
        self._detail_layout.addWidget(name_lbl)

        if position:
            pos_lbl = QLabel(position)
            pos_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};")
            self._detail_layout.addWidget(pos_lbl)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
        self._detail_layout.addWidget(sep)

        if groups:
            for group_name, fields in groups.items():
                if not fields:
                    continue
                self._add_detail_group(group_name, fields)
        else:
            self._add_detail_fallback(employee_full)

        self._add_detail_meta(employee_full)
        self._detail_layout.addStretch()

    def _add_detail_group(self, title: str, fields: list):
        """Eine Gruppe mit Titel und Feldern im Detail-Panel."""
        header = QLabel(title)
        header.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: 10pt;
            color: {PRIMARY_900}; font-weight: bold;
            padding-top: 10px;
        """)
        self._detail_layout.addWidget(header)

        for field in fields:
            label_text = field.get('label', '?')
            value = field.get('value', '')
            if value is None or value == '':
                continue
            self._add_detail_row(label_text, str(value))

    def _add_detail_fallback(self, emp: dict):
        """Fallback: Flache Felder aus der DB anzeigen."""
        fallback_fields = [
            (texts.WF_DETAIL_EMAIL, emp.get('email')),
            (texts.WF_DETAIL_DEPARTMENT, emp.get('department')),
            (texts.WF_DETAIL_POSITION, emp.get('position')),
            (texts.WF_DETAIL_STATUS, emp.get('status')),
            (texts.WF_DETAIL_PERSON_ID, emp.get('provider_pid')),
            (texts.WF_DETAIL_JOIN_DATE, emp.get('join_date')),
            (texts.WF_DETAIL_LEAVE_DATE, emp.get('leave_date')),
        ]
        for label_text, value in fallback_fields:
            if value:
                self._add_detail_row(label_text, str(value))

    def _add_detail_meta(self, emp: dict):
        """ATLAS-Metadaten am Ende des Panels."""
        meta = []
        if emp.get('provider_pid'):
            meta.append((texts.WF_DETAIL_PERSON_ID, emp['provider_pid']))
        if emp.get('last_synced_at'):
            meta.append((texts.WF_DETAIL_LAST_SYNCED, emp['last_synced_at']))
        if not meta:
            return

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_DEFAULT}; margin-top: 8px;")
        self._detail_layout.addWidget(sep)

        for label_text, value in meta:
            self._add_detail_row(label_text, str(value))

    def _add_detail_row(self, label_text: str, value: str):
        """Einzelne Label/Value-Zeile im Detail-Panel."""
        row_widget = QWidget()
        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 3, 0, 3)
        row_layout.setSpacing(1)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        row_layout.addWidget(lbl)

        val = _ClickableValue(value, label_text, self._toast_manager)
        val.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: {FONT_SIZE_BODY};")
        val.setWordWrap(True)
        row_layout.addWidget(val)

        self._detail_layout.addWidget(row_widget)

    def _clear_detail_layout(self):
        while self._detail_layout.count():
            child = self._detail_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    # ── Kontextmenue (Rechtsklick) ─────────────────────────────

    def _on_context_menu(self, position):
        item = self._table.itemAt(position)
        if not item:
            return
        row = item.row()
        first_item = self._table.item(row, 0)
        if not first_item:
            return
        emp = first_item.data(Qt.ItemDataRole.UserRole)
        if not emp:
            return

        menu = QMenu(self)
        details_action = QAction(texts.WF_EMPLOYEE_ALL_DETAILS, self)
        details_action.triggered.connect(lambda: self._show_full_details(emp))
        menu.addAction(details_action)
        menu.exec(self._table.viewport().mapToGlobal(position))

    def _show_full_details(self, emp_basic: dict):
        """Laedt details_json vom Server und oeffnet den Detail-Dialog."""
        employer_id = self._employer_combo.currentData()
        employee_id = emp_basic.get('id')
        if not employer_id or not employee_id:
            return

        self._progress_label.setText(texts.WF_EMPLOYEE_LOADING_DETAILS)

        worker = _FetchDetailWorker(self._wf_api, employer_id, employee_id)
        worker.signals.finished.connect(self._on_detail_loaded)
        worker.signals.error.connect(self._on_detail_error)
        self._thread_pool.start(worker)

    def _on_detail_loaded(self, employee_full: dict):
        self._progress_label.setText("")
        dialog = EmployeeDetailDialog(self, employee_full, self._toast_manager)
        dialog.exec()

    def _on_detail_error(self, error: str):
        self._progress_label.setText("")
        logger.error(f"Detail-Laden fehlgeschlagen: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(error)

    # ── Sync ───────────────────────────────────────────────────

    def _on_sync(self):
        employer_id = self._employer_combo.currentData()
        if not employer_id or self._syncing:
            return

        self._syncing = True
        self._sync_btn.setEnabled(False)
        self._progress_label.setText(texts.WF_SYNC_RUNNING)

        worker = SyncWorker(self._wf_api, employer_id)
        worker.signals.finished.connect(self._on_sync_done)
        worker.signals.error.connect(self._on_sync_error)
        worker.signals.progress.connect(self._on_sync_progress)
        self._thread_pool.start(worker)

    def _on_sync_progress(self, msg: str):
        self._progress_label.setText(msg)

    def _on_sync_done(self, result: dict):
        self._syncing = False
        self._sync_btn.setEnabled(True)
        self._progress_label.setText("")
        synced = result.get('employee_count', result.get('synced_count', 0))
        if self._toast_manager:
            self._toast_manager.show_success(
                texts.WF_SYNC_SUCCESS.format(count=synced)
            )
        self._load_employees_reset()

    def _on_sync_error(self, error: str):
        self._syncing = False
        self._sync_btn.setEnabled(True)
        self._progress_label.setText("")
        logger.error(f"Sync fehlgeschlagen: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(texts.WF_SYNC_ERROR.format(error=error))
