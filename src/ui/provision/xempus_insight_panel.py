"""
Xempus Insight Panel: Tabbed-Ansicht mit Arbeitgeber-TreeView,
Statistik-Dashboard, Import-Management und Status-Mapping.

Ersetzt den alten xempus_panel.py mit einer vollstaendigen
Verwaltungsoberflaeche fuer Xempus-Daten.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QSplitter, QFrame, QScrollArea, QTabWidget,
    QLineEdit, QPushButton, QSizePolicy, QFileDialog,
    QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QAbstractItemView, QLayout, QLayoutItem,
)
from PySide6.QtCore import (
    Qt, Signal, QSortFilterProxyModel, QTimer, QModelIndex,
    QRect, QSize, QPoint,
)
from PySide6.QtGui import QColor, QPainter, QPen, QBrush

from typing import List, Optional, Dict

from api.provision import ProvisionAPI
from api.xempus import XempusAPI
from api.client import APIError
from domain.xempus_models import (
    XempusEmployer, XempusTariff, XempusSubsidy, XempusEmployee,
    XempusConsultation, XempusImportBatch, XempusStatusMapping,
    XempusStats, XempusDiff,
)
from services.xempus_parser import parse_xempus_complete, prepare_sheets_for_upload
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    TEXT_DISABLED, TEXT_SECONDARY,
    INDIGO, BLUE_BRIGHT,
    FONT_BODY, FONT_HEADLINE, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
    PILL_COLORS, get_provision_table_style, build_rich_tooltip,
)
from ui.provision.widgets import (
    PillBadgeDelegate, DonutChartWidget, FilterChipBar, SectionHeader,
    KpiCard, ProvisionLoadingOverlay,
    format_eur, get_search_field_style, get_secondary_button_style,
)
from ui.provision.workers import (
    EmployerLoadWorker, EmployerDetailWorker,
    EmployeePageLoadWorker, EmployeeDetailWorker,
    XempusStatsLoadWorker,
    XempusBatchesLoadWorker, XempusImportWorker, XempusDiffLoadWorker,
    StatusMappingLoadWorker,
)
from ui.provision.models import (
    EmployerTableModel, XempusBatchTableModel, StatusMappingModel, fmt_date,
)
from ui.provision.dialogs import DiffDialog
from infrastructure.threading.worker_utils import run_worker, detach_worker
from i18n import de as texts
import logging
import warnings

logger = logging.getLogger(__name__)


# =============================================================================
# Flow Layout
# =============================================================================


class _FlowLayout(QLayout):
    """Layout that wraps items horizontally, flowing to the next row when full."""

    def __init__(self, parent=None, h_spacing=12, v_spacing=10):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), apply_geometry=False)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, apply_geometry=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, apply_geometry: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        row_height = 0

        for item in self._items:
            item_size = item.sizeHint()
            if x + item_size.width() > effective.right() + 1 and row_height > 0:
                x = effective.x()
                y += row_height + self._v_spacing
                row_height = 0
            if apply_geometry:
                item.setGeometry(QRect(QPoint(x, y), item_size))
            x += item_size.width() + self._h_spacing
            row_height = max(row_height, item_size.height())

        total_height = y + row_height - rect.y() + m.bottom()
        if apply_geometry and self.parentWidget():
            self.parentWidget().setMinimumHeight(total_height)
        return total_height


# =============================================================================
# Tabs
# =============================================================================


class _EmployerCard(QFrame):
    """Einzelne Arbeitgeber-Karte im Telefonbuch-Stil."""

    clicked = Signal(str)
    double_clicked = Signal(str)

    _BASE_STYLE = f"""
        _EmployerCard {{
            background-color: white;
            border: 1px solid {BORDER_DEFAULT};
            border-radius: 8px;
        }}
        _EmployerCard:hover {{
            border-color: {PRIMARY_500};
            background-color: {BG_TERTIARY};
        }}
    """

    def __init__(self, employer: 'XempusEmployer', parent=None):
        super().__init__(parent)
        self._employer = employer
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(300, 100)
        self._selected = False
        self.setStyleSheet(self._BASE_STYLE)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        initial = self._employer.name[0].upper() if self._employer.name else "?"
        avatar = QLabel(initial)
        avatar.setFixedSize(48, 48)
        avatar.setAlignment(Qt.AlignCenter)
        hue = sum(ord(c) for c in self._employer.id) % 360
        avatar_bg = f"hsl({hue}, 35%, 88%)"
        avatar_fg = f"hsl({hue}, 45%, 35%)"
        avatar.setStyleSheet(f"""
            QLabel {{
                background-color: {avatar_bg};
                color: {avatar_fg};
                border-radius: 24px;
                font-size: 16pt;
                font-weight: 700;
                font-family: {FONT_BODY};
            }}
        """)
        layout.addWidget(avatar)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)

        name_lbl = QLabel(self._employer.name or "–")
        name_lbl.setStyleSheet(f"""
            font-weight: 600; font-size: {FONT_SIZE_BODY};
            color: {PRIMARY_900}; font-family: {FONT_BODY};
        """)
        name_lbl.setWordWrap(True)
        info_col.addWidget(name_lbl)

        city_parts = [p for p in [self._employer.plz, self._employer.city] if p]
        city_text = " ".join(city_parts) if city_parts else texts.XEMPUS_EMPLOYER_CARD_NO_CITY
        city_lbl = QLabel(city_text)
        city_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};")
        info_col.addWidget(city_lbl)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        emp_count = self._employer.employee_count
        if emp_count == 1:
            emp_text = texts.XEMPUS_EMPLOYER_CARD_EMPLOYEE_SINGULAR
        else:
            emp_text = texts.XEMPUS_EMPLOYER_CARD_EMPLOYEES.format(count=emp_count)
        emp_lbl = QLabel(emp_text)
        emp_lbl.setStyleSheet(f"""
            color: {ACCENT_500}; font-size: {FONT_SIZE_CAPTION};
            font-weight: 600; font-family: {FONT_BODY};
        """)
        meta_row.addWidget(emp_lbl)

        status_text = texts.XEMPUS_EMPLOYER_CARD_ACTIVE if self._employer.is_active else texts.XEMPUS_EMPLOYER_CARD_INACTIVE
        status_color = SUCCESS if self._employer.is_active else ERROR
        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet(f"""
            color: {status_color}; font-size: {FONT_SIZE_CAPTION};
            font-family: {FONT_BODY};
        """)
        meta_row.addWidget(status_lbl)
        meta_row.addStretch()

        info_col.addLayout(meta_row)
        layout.addLayout(info_col, 1)

    def set_selected(self, selected: bool):
        if self._selected != selected:
            self._selected = selected
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._selected:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(ACCENT_500), 2)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(BG_SECONDARY)))
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
            painter.end()

    def mousePressEvent(self, event):
        self.clicked.emit(self._employer.id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self._employer.id)
        super().mouseDoubleClickEvent(event)

    @property
    def employer(self) -> 'XempusEmployer':
        return self._employer


class _EmployersTab(QWidget):
    """Arbeitgeber als Card-Grid im Telefonbuch-Stil mit Detail-Panel."""

    employer_double_clicked = Signal(str)

    def __init__(self, xempus_api: XempusAPI, parent=None):
        super().__init__(parent)
        self._api = xempus_api
        self._worker = None
        self._stats_worker = None
        self._detail_worker = None
        self._current_employer_id = None
        self._selected_card_id: Optional[str] = None
        self._all_employers: List[XempusEmployer] = []
        self._cards: Dict[str, _EmployerCard] = {}
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText(texts.XEMPUS_EMPLOYER_SEARCH)
        self._search.setStyleSheet(get_search_field_style())
        self._search.setFixedWidth(280)
        self._search.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search)
        toolbar.addStretch()
        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        toolbar.addWidget(self._count_label)
        root.addLayout(toolbar)

        self._kpi_row = QHBoxLayout()
        self._kpi_row.setSpacing(10)
        self._kpi_cards: Dict[str, QFrame] = {}
        for key, label, accent, tip in [
            ('total', texts.XEMPUS_EMPLOYER_KPI_TOTAL, PRIMARY_900, texts.XEMPUS_EMPLOYER_KPI_TOTAL_TIP),
            ('active', texts.XEMPUS_EMPLOYER_KPI_ACTIVE, SUCCESS, texts.XEMPUS_EMPLOYER_KPI_ACTIVE_TIP),
            ('employees', texts.XEMPUS_EMPLOYER_KPI_EMPLOYEES_TOTAL, INDIGO, texts.XEMPUS_EMPLOYER_KPI_EMPLOYEES_TOTAL_TIP),
            ('avg_emp', texts.XEMPUS_EMPLOYER_KPI_AVG_EMPLOYEES, ACCENT_500, texts.XEMPUS_EMPLOYER_KPI_AVG_EMPLOYEES_TIP),
            ('cities', texts.XEMPUS_EMPLOYER_KPI_CITIES, PRIMARY_500, texts.XEMPUS_EMPLOYER_KPI_CITIES_TIP),
            ('consultations', texts.XEMPUS_EMPLOYER_KPI_CONSULTATIONS, BLUE_BRIGHT, texts.XEMPUS_EMPLOYER_KPI_CONSULTATIONS_TIP),
            ('conversion', texts.XEMPUS_EMPLOYER_KPI_CONVERSION, SUCCESS, texts.XEMPUS_EMPLOYER_KPI_CONVERSION_TIP),
        ]:
            card = self._make_kpi_card(label, "–", accent)
            card.setToolTip(build_rich_tooltip(tip))
            self._kpi_cards[key] = card
            self._kpi_row.addWidget(card)
        kpi_widget = QWidget()
        kpi_widget.setLayout(self._kpi_row)
        root.addWidget(kpi_widget)

        status_row_wrapper = QHBoxLayout()
        status_row_wrapper.setSpacing(8)
        status_title = QLabel(texts.XEMPUS_EMPLOYER_STATUS_TITLE)
        status_title.setStyleSheet(f"""
            font-weight: 600; font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_900}; font-family: {FONT_BODY};
        """)
        status_row_wrapper.addWidget(status_title)
        self._status_chips_layout = QHBoxLayout()
        self._status_chips_layout.setSpacing(6)
        status_row_wrapper.addLayout(self._status_chips_layout)
        status_row_wrapper.addStretch()
        root.addLayout(status_row_wrapper)

        self._splitter = QSplitter(Qt.Horizontal)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._scroll_container = QWidget()
        self._scroll_container.setStyleSheet("background: transparent;")
        self._grid_layout = QVBoxLayout(self._scroll_container)
        self._grid_layout.setContentsMargins(4, 4, 4, 4)
        self._grid_layout.setSpacing(12)
        self._grid_layout.addStretch()
        self._scroll.setWidget(self._scroll_container)
        self._splitter.addWidget(self._scroll)

        self._detail_frame = QFrame()
        self._detail_frame.setFixedWidth(380)
        self._detail_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border-left: 1px solid {BORDER_DEFAULT};
            }}
        """)
        self._detail_layout = QVBoxLayout(self._detail_frame)
        self._detail_layout.setContentsMargins(16, 16, 16, 16)
        self._detail_layout.setSpacing(8)
        placeholder = QLabel(texts.XEMPUS_EMPLOYER_DETAIL_TITLE)
        placeholder.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY};")
        placeholder.setAlignment(Qt.AlignCenter)
        self._detail_layout.addWidget(placeholder)
        self._detail_layout.addStretch()
        self._splitter.addWidget(self._detail_frame)

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        root.addWidget(self._splitter, 1)

        self._loading = ProvisionLoadingOverlay(self)
        self._loading.hide()

    def refresh(self):
        detach_worker(self._worker)
        detach_worker(self._stats_worker)
        self._loading.show()
        self._worker = EmployerLoadWorker(self._api)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()
        self._stats_worker = XempusStatsLoadWorker(self._api)
        self._stats_worker.finished.connect(self._on_stats_loaded)
        self._stats_worker.error.connect(lambda m: logger.error(f"Stats: {m}"))
        self._stats_worker.start()

    @staticmethod
    def _make_kpi_card(label: str, value: str, accent: str = "") -> QFrame:
        card = QFrame()
        border_top = f"border-top: 3px solid {accent};" if accent else ""
        card.setStyleSheet(f"""
            QFrame#xempusKpiCard {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                {border_top}
            }}
        """)
        card.setObjectName("xempusKpiCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        val_lbl = QLabel(str(value))
        val_lbl.setObjectName("kpiValue")
        val_lbl.setStyleSheet(f"""
            font-size: 18pt; font-weight: 700; color: {PRIMARY_900};
            font-family: {FONT_HEADLINE}; background: transparent; border: none;
        """)
        val_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(val_lbl)
        cap_lbl = QLabel(label)
        cap_lbl.setStyleSheet(f"""
            font-size: {FONT_SIZE_CAPTION}; color: {TEXT_SECONDARY};
            font-family: {FONT_BODY}; background: transparent; border: none;
        """)
        cap_lbl.setAlignment(Qt.AlignCenter)
        cap_lbl.setWordWrap(True)
        lay.addWidget(cap_lbl)
        return card

    def _update_kpi_stats(self, employers: List[XempusEmployer]):
        total = len(employers)
        active = sum(1 for e in employers if e.is_active)
        total_emp = sum(e.employee_count for e in employers)
        avg_emp = round(total_emp / total, 1) if total > 0 else 0
        cities = len({e.city for e in employers if e.city})

        for key, val in [
            ('total', str(total)),
            ('active', str(active)),
            ('employees', str(total_emp)),
            ('avg_emp', str(avg_emp)),
            ('cities', str(cities)),
        ]:
            self._set_kpi_value(key, val)

    def _set_kpi_value(self, key: str, value: str):
        card = self._kpi_cards.get(key)
        if card:
            val_lbl = card.findChild(QLabel, "kpiValue")
            if val_lbl:
                val_lbl.setText(value)

    def _on_stats_loaded(self, stats: XempusStats):
        self._set_kpi_value('consultations', str(stats.total_consultations))
        self._set_kpi_value('conversion', f"{stats.abschluss_quote:.1f}%")
        self._update_status_chips(stats.status_distribution)

    def _update_status_chips(self, distribution: list):
        while self._status_chips_layout.count():
            item = self._status_chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        status_colors = {
            'converted': SUCCESS, 'open': WARNING, 'applied': BLUE_BRIGHT,
            'rejected': ERROR, 'not_desired': TEXT_DISABLED, 'other': PRIMARY_500,
        }
        for entry in distribution:
            cat = entry.get('category', 'other')
            count = int(entry.get('count', 0))
            label_text = entry.get('display_label', cat)
            color = entry.get('color', status_colors.get(cat, PRIMARY_500))

            chip = QLabel(f"  {label_text}: {count}  ")
            chip.setStyleSheet(f"""
                background-color: {color}20;
                color: {color};
                border: 1px solid {color}40;
                border-radius: 10px;
                padding: 3px 8px;
                font-size: {FONT_SIZE_CAPTION};
                font-weight: 500;
                font-family: {FONT_BODY};
            """)
            self._status_chips_layout.addWidget(chip)

    def _on_loaded(self, employers: list):
        self._loading.hide()
        self._all_employers = employers
        self._count_label.setText(texts.XEMPUS_EMPLOYER_COUNT.format(count=len(employers)))
        self._update_kpi_stats(employers)
        self._build_card_grid(employers)

    def _on_error(self, msg: str):
        self._loading.hide()
        logger.error(f"Employer load error: {msg}")

    def _build_card_grid(self, employers: List[XempusEmployer]):
        self._cards.clear()
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        sorted_employers = sorted(employers, key=lambda e: (e.name or "").upper())

        grouped: Dict[str, List[XempusEmployer]] = {}
        for emp in sorted_employers:
            letter = (emp.name or "?")[0].upper()
            if not letter.isalpha():
                letter = "#"
            grouped.setdefault(letter, []).append(emp)

        for letter in sorted(grouped.keys()):
            section_header = QLabel(letter)
            section_header.setStyleSheet(f"""
                font-size: 14pt; font-weight: 700; color: {PRIMARY_900};
                font-family: {FONT_BODY}; padding: 8px 4px 4px 4px;
                border-bottom: 2px solid {ACCENT_500};
            """)
            section_header.setFixedHeight(40)
            self._grid_layout.addWidget(section_header)

            flow = _FlowLayout(h_spacing=12, v_spacing=10)
            for emp in grouped[letter]:
                card = _EmployerCard(emp)
                card.clicked.connect(self._on_card_clicked)
                card.double_clicked.connect(self.employer_double_clicked)
                self._cards[emp.id] = card
                flow.addWidget(card)

            flow_container = QWidget()
            flow_container.setLayout(flow)
            self._grid_layout.addWidget(flow_container)

        self._grid_layout.addStretch()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                _EmployersTab._clear_layout(item.layout())

    def _on_search(self, text: str):
        self._pending_filter = text
        self._search_timer.stop()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                self._search_timer.timeout.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._search_timer.timeout.connect(self._apply_filter)
        self._search_timer.start()

    def _apply_filter(self):
        text = self._pending_filter.lower().strip()
        if not text:
            self._build_card_grid(self._all_employers)
            return
        filtered = [
            e for e in self._all_employers
            if text in (e.name or "").lower()
            or text in (e.city or "").lower()
            or text in (e.plz or "").lower()
            or text in (e.id or "").lower()
        ]
        self._build_card_grid(filtered)
        self._count_label.setText(texts.XEMPUS_EMPLOYER_COUNT.format(count=len(filtered)))

    def _on_card_clicked(self, employer_id: str):
        if self._selected_card_id and self._selected_card_id in self._cards:
            self._cards[self._selected_card_id].set_selected(False)
        self._selected_card_id = employer_id
        if employer_id in self._cards:
            self._cards[employer_id].set_selected(True)
        self._load_detail(employer_id)

    def _load_detail(self, employer_id: str):
        self._current_employer_id = employer_id
        detach_worker(self._detail_worker)
        self._detail_worker = EmployerDetailWorker(self._api, employer_id)
        self._detail_worker.finished.connect(
            lambda d, eid=employer_id: self._show_detail(d, eid))
        self._detail_worker.error.connect(lambda msg: logger.error(f"Detail: {msg}"))
        self._detail_worker.start()

    def _show_detail(self, detail: Optional[Dict], employer_id: str = None):
        if employer_id and employer_id != self._current_employer_id:
            return
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        if not detail:
            return

        employer: XempusEmployer = detail['employer']
        tariffs: list = detail.get('tariffs', [])
        subsidies: list = detail.get('subsidies', [])

        title = QLabel(employer.name)
        title.setStyleSheet(f"font-weight: 700; font-size: 12pt; color: {PRIMARY_900};")
        title.setWordWrap(True)
        self._detail_layout.addWidget(title)

        fields = [
            (texts.XEMPUS_EMPLOYER_DETAIL_ID, employer.id),
            (texts.XEMPUS_EMPLOYER_DETAIL_ADDRESS,
             ', '.join(p for p in [employer.street, f"{employer.plz} {employer.city}".strip()] if p)),
            (texts.XEMPUS_EMPLOYER_COL_EMPLOYEES, str(employer.employee_count)),
        ]
        for label_text, value in fields:
            if not value:
                continue
            row = QHBoxLayout()
            lbl = QLabel(f"{label_text}:")
            lbl.setFixedWidth(100)
            lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
            val = QLabel(str(value))
            val.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY};")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            self._detail_layout.addLayout(row)

        if tariffs:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
            self._detail_layout.addWidget(sep)

            tariff_title = QLabel(texts.XEMPUS_EMPLOYER_DETAIL_TARIFFS)
            tariff_title.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {PRIMARY_900};")
            self._detail_layout.addWidget(tariff_title)

            for t in tariffs[:10]:
                info = f"{t.versicherer or ''} – {t.tarif or ''}"
                lbl = QLabel(info.strip(' –'))
                lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_CAPTION}; padding: 1px 0;")
                lbl.setWordWrap(True)
                self._detail_layout.addWidget(lbl)

        if subsidies:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
            self._detail_layout.addWidget(sep)

            sub_title = QLabel(texts.XEMPUS_EMPLOYER_DETAIL_SUBSIDIES)
            sub_title.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {PRIMARY_900};")
            self._detail_layout.addWidget(sub_title)

            for s in subsidies[:10]:
                info = s.bezeichnung or '–'
                if s.fester_zuschuss is not None:
                    info += f"  ({format_eur(s.fester_zuschuss)})"
                lbl = QLabel(info)
                lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_CAPTION}; padding: 1px 0;")
                lbl.setWordWrap(True)
                self._detail_layout.addWidget(lbl)

        self._detail_layout.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.resize(self.size())


class _EmployeeCard(QFrame):
    """Einzelne Mitarbeiter-Karte im Telefonbuch-Stil."""

    clicked = Signal(str)

    _BASE_STYLE = f"""
        _EmployeeCard {{
            background-color: white;
            border: 1px solid {BORDER_DEFAULT};
            border-radius: 8px;
        }}
        _EmployeeCard:hover {{
            border-color: {PRIMARY_500};
            background-color: {BG_TERTIARY};
        }}
    """

    def __init__(self, employee: 'XempusEmployee', parent=None):
        super().__init__(parent)
        self._employee = employee
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(300, 100)
        self._selected = False
        self.setStyleSheet(self._BASE_STYLE)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        initials = ""
        if self._employee.vorname:
            initials += self._employee.vorname[0].upper()
        if self._employee.name:
            initials += self._employee.name[0].upper()
        if not initials:
            initials = "?"

        avatar = QLabel(initials)
        avatar.setFixedSize(44, 44)
        avatar.setAlignment(Qt.AlignCenter)
        hue = sum(ord(c) for c in self._employee.id) % 360
        avatar_bg = f"hsl({hue}, 35%, 88%)"
        avatar_fg = f"hsl({hue}, 45%, 35%)"
        avatar.setStyleSheet(f"""
            QLabel {{
                background-color: {avatar_bg};
                color: {avatar_fg};
                border-radius: 22px;
                font-size: 13pt;
                font-weight: 700;
                font-family: {FONT_BODY};
            }}
        """)
        layout.addWidget(avatar)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        full_name = self._employee.full_name or "–"
        name_lbl = QLabel(full_name)
        name_lbl.setStyleSheet(f"""
            font-weight: 600; font-size: {FONT_SIZE_BODY};
            color: {PRIMARY_900}; font-family: {FONT_BODY};
        """)
        name_lbl.setWordWrap(True)
        info_col.addWidget(name_lbl)

        employer_text = self._employee.employer_name or texts.XEMPUS_EMPLOYEE_CARD_NO_EMPLOYER
        employer_lbl = QLabel(employer_text)
        employer_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};")
        info_col.addWidget(employer_lbl)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        status_text = self._employee.status_label or self._employee.beratungsstatus or texts.XEMPUS_EMPLOYEE_CARD_NO_STATUS
        status_color = self._employee.status_color or PRIMARY_500
        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet(f"""
            color: {status_color}; font-size: {FONT_SIZE_CAPTION};
            font-weight: 500; font-family: {FONT_BODY};
        """)
        meta_row.addWidget(status_lbl)

        if self._employee.personalnummer:
            pnr_lbl = QLabel(f"#{self._employee.personalnummer}")
            pnr_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};")
            meta_row.addWidget(pnr_lbl)

        meta_row.addStretch()
        info_col.addLayout(meta_row)
        layout.addLayout(info_col, 1)

    def set_selected(self, selected: bool):
        if self._selected != selected:
            self._selected = selected
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._selected:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(ACCENT_500), 2)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(BG_SECONDARY)))
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
            painter.end()

    def mousePressEvent(self, event):
        self.clicked.emit(self._employee.id)
        super().mousePressEvent(event)

    @property
    def employee(self) -> 'XempusEmployee':
        return self._employee


class _EmployeesTab(QWidget):
    """Mitarbeiter als Card-Grid mit Lazy-Loading und Arbeitgeber-Filter."""

    BATCH_SIZE = 48

    def __init__(self, xempus_api: XempusAPI, parent=None):
        super().__init__(parent)
        self._api = xempus_api
        self._worker = None
        self._employer_worker = None
        self._detail_worker = None
        self._current_employee_id = None
        self._current_page = 1
        self._total_pages = 1
        self._total_count = 0
        self._loading_more = False
        self._pending_employer_filter: Optional[str] = None
        self._selected_card_id: Optional[str] = None
        self._pending_employees: list = []
        self._cards: Dict[str, _EmployeeCard] = {}
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText(texts.XEMPUS_EMPLOYEE_SEARCH)
        self._search.setStyleSheet(get_search_field_style())
        self._search.setFixedWidth(280)
        self._search.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search)

        self._employer_filter = QComboBox()
        self._employer_filter.setFixedWidth(240)
        self._employer_filter.addItem(texts.XEMPUS_EMPLOYEE_FILTER_ALL, "")
        self._employer_filter.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._employer_filter)

        toolbar.addStretch()
        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        toolbar.addWidget(self._count_label)
        root.addLayout(toolbar)

        self._splitter = QSplitter(Qt.Horizontal)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._flow = _FlowLayout(self._scroll_content, h_spacing=12, v_spacing=10)
        self._flow.setContentsMargins(4, 4, 4, 4)
        self._scroll.setWidget(self._scroll_content)
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self._splitter.addWidget(self._scroll)

        self._detail_frame = QFrame()
        self._detail_frame.setFixedWidth(380)
        self._detail_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border-left: 1px solid {BORDER_DEFAULT};
            }}
        """)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._detail_inner = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_inner)
        self._detail_layout.setContentsMargins(16, 16, 16, 16)
        self._detail_layout.setSpacing(8)
        placeholder = QLabel(texts.XEMPUS_EMPLOYEE_DETAIL_TITLE)
        placeholder.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY};")
        placeholder.setAlignment(Qt.AlignCenter)
        self._detail_layout.addWidget(placeholder)
        self._detail_layout.addStretch()
        detail_scroll.setWidget(self._detail_inner)
        frame_layout = QVBoxLayout(self._detail_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.addWidget(detail_scroll)
        self._splitter.addWidget(self._detail_frame)

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        root.addWidget(self._splitter, 1)

        self._loading = ProvisionLoadingOverlay(self)
        self._loading.hide()

    def refresh(self):
        self._reset_and_load()
        self._load_employers()

    def filter_by_employer(self, employer_id: str):
        """Setzt den Arbeitgeber-Filter auf die gegebene ID und laedt neu."""
        idx = self._employer_filter.findData(employer_id)
        if idx >= 0:
            self._employer_filter.setCurrentIndex(idx)
        else:
            self._pending_employer_filter = employer_id

    def _reset_and_load(self):
        self._current_page = 1
        self._total_pages = 1
        self._total_count = 0
        self._clear_grid()
        self._load_page()

    def _load_employers(self):
        detach_worker(self._employer_worker)
        self._employer_worker = EmployerLoadWorker(self._api)
        self._employer_worker.finished.connect(self._on_employers_loaded)
        self._employer_worker.error.connect(lambda m: logger.error(f"Employer list: {m}"))
        self._employer_worker.start()

    def _load_page(self):
        if self._loading_more:
            return
        detach_worker(self._worker)
        self._loading_more = True
        if self._current_page == 1:
            self._loading.show()
        employer_id = self._employer_filter.currentData() or None
        q = self._search.text().strip() or None
        self._worker = EmployeePageLoadWorker(
            self._api, page=self._current_page, per_page=self.BATCH_SIZE,
            employer_id=employer_id, q=q)
        self._worker.finished.connect(self._on_page_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_employers_loaded(self, employers: list):
        restore_id = self._pending_employer_filter or self._employer_filter.currentData()
        self._pending_employer_filter = None
        self._employer_filter.blockSignals(True)
        self._employer_filter.clear()
        self._employer_filter.addItem(texts.XEMPUS_EMPLOYEE_FILTER_ALL, "")
        for emp in sorted(employers, key=lambda e: (e.name or "").upper()):
            self._employer_filter.addItem(emp.name, emp.id)
        if restore_id:
            idx = self._employer_filter.findData(restore_id)
            if idx >= 0:
                self._employer_filter.setCurrentIndex(idx)
        self._employer_filter.blockSignals(False)
        if restore_id and self._employer_filter.currentData() == restore_id:
            self._reset_and_load()

    def _on_page_loaded(self, employees: list, pagination: dict):
        self._loading.hide()
        self._loading_more = False
        self._total_count = int(pagination.get('total', 0))
        self._total_pages = int(pagination.get('total_pages', 1))
        self._current_page = int(pagination.get('page', self._current_page))
        self._count_label.setText(texts.XEMPUS_EMPLOYEE_COUNT.format(count=self._total_count))

        if self._current_page == 1 and not employees:
            self._clear_grid()
            empty_lbl = QLabel(texts.XEMPUS_EMPLOYEE_EMPTY)
            empty_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY}; padding: 32px;")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self._flow.addWidget(empty_lbl)
            return

        self._append_cards(employees)

    def _on_error(self, msg: str):
        self._loading.hide()
        self._loading_more = False
        logger.error(f"Employee load error: {msg}")
        self._count_label.setText(f"Fehler: {msg}")

    def _on_filter_changed(self, _index: int):
        self._reset_and_load()

    def _on_search(self, text: str):
        self._search_timer.stop()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                self._search_timer.timeout.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._search_timer.timeout.connect(self._reset_and_load)
        self._search_timer.start()

    def _on_scroll(self, value: int):
        sb = self._scroll.verticalScrollBar()
        if sb.maximum() == 0:
            return
        if value >= sb.maximum() - 100:
            if not self._loading_more and self._current_page < self._total_pages:
                self._current_page += 1
                self._load_page()

    def _clear_grid(self):
        self._selected_card_id = None
        self._pending_employees = []
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._cards.clear()

    _CARD_BATCH_SIZE = 12

    def _append_cards(self, employees: List[XempusEmployee]):
        self._pending_employees = list(employees)
        self._drain_card_batch()

    def _drain_card_batch(self):
        if not self._pending_employees:
            QTimer.singleShot(50, self._check_fill_viewport)
            return
        batch = self._pending_employees[:self._CARD_BATCH_SIZE]
        self._pending_employees = self._pending_employees[self._CARD_BATCH_SIZE:]
        for emp in batch:
            card = _EmployeeCard(emp)
            card.clicked.connect(self._on_card_clicked)
            self._cards[emp.id] = card
            self._flow.addWidget(card)
        if self._pending_employees:
            QTimer.singleShot(0, self._drain_card_batch)

    def _check_fill_viewport(self):
        sb = self._scroll.verticalScrollBar()
        if sb.maximum() <= 0 and self._current_page < self._total_pages and not self._loading_more:
            self._current_page += 1
            self._load_page()

    def _on_card_clicked(self, employee_id: str):
        if self._selected_card_id and self._selected_card_id in self._cards:
            self._cards[self._selected_card_id].set_selected(False)
        self._selected_card_id = employee_id
        if employee_id in self._cards:
            self._cards[employee_id].set_selected(True)
        self._load_detail(employee_id)

    def _load_detail(self, employee_id: str):
        self._current_employee_id = employee_id
        detach_worker(self._detail_worker)
        self._detail_worker = EmployeeDetailWorker(self._api, employee_id)
        self._detail_worker.finished.connect(
            lambda d, eid=employee_id: self._show_detail(d, eid))
        self._detail_worker.error.connect(lambda msg: logger.error(f"Employee detail: {msg}"))
        self._detail_worker.start()

    def _show_detail(self, detail: Optional[Dict], employee_id: str = None):
        if employee_id and employee_id != self._current_employee_id:
            return
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        if not detail:
            return

        employee: XempusEmployee = detail['employee']
        consultations: list = detail.get('consultations', [])

        title = QLabel(employee.full_name)
        title.setStyleSheet(f"font-weight: 700; font-size: 12pt; color: {PRIMARY_900};")
        title.setWordWrap(True)
        self._detail_layout.addWidget(title)

        if employee.status_label or employee.beratungsstatus:
            status_text = employee.status_label or employee.beratungsstatus
            status_color = employee.status_color or ACCENT_500
            status_chip = QLabel(f"  {status_text}  ")
            status_chip.setStyleSheet(f"""
                background-color: {status_color}20;
                color: {status_color};
                border: 1px solid {status_color}40;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: {FONT_SIZE_CAPTION};
                font-weight: 500;
            """)
            self._detail_layout.addWidget(status_chip)

        fields = [
            (texts.XEMPUS_EMPLOYEE_DETAIL_ID, employee.id),
            (texts.XEMPUS_EMPLOYEE_DETAIL_EMPLOYER, employee.employer_name),
            (texts.XEMPUS_EMPLOYEE_DETAIL_PERSONNEL_NR, employee.personalnummer),
            (texts.XEMPUS_EMPLOYEE_DETAIL_ADDRESS,
             ', '.join(p for p in [employee.street, f"{employee.plz or ''} {employee.city or ''}".strip()] if p)),
            (texts.XEMPUS_EMPLOYEE_DETAIL_PHONE, employee.telefon),
            (texts.XEMPUS_EMPLOYEE_DETAIL_MOBILE, employee.mobiltelefon),
            (texts.XEMPUS_EMPLOYEE_DETAIL_EMAIL, employee.email),
            (texts.XEMPUS_EMPLOYEE_DETAIL_BIRTHDAY, fmt_date(employee.geburtsdatum)),
            (texts.XEMPUS_EMPLOYEE_DETAIL_ENTRY, fmt_date(employee.diensteintritt)),
            (texts.XEMPUS_EMPLOYEE_DETAIL_SALARY,
             format_eur(employee.bruttolohn) if employee.bruttolohn is not None else None),
            (texts.XEMPUS_EMPLOYEE_DETAIL_TAX_CLASS, employee.steuerklasse),
            (texts.XEMPUS_EMPLOYEE_DETAIL_INSURANCE, employee.krankenversicherung),
            (texts.XEMPUS_EMPLOYEE_DETAIL_POSITION, employee.berufsstellung),
            (texts.XEMPUS_EMPLOYEE_DETAIL_JOB_TITLE, employee.berufsbezeichnung),
        ]
        for label_text, value in fields:
            if not value:
                continue
            row = QHBoxLayout()
            lbl = QLabel(f"{label_text}:")
            lbl.setFixedWidth(110)
            lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
            val = QLabel(str(value))
            val.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY};")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            self._detail_layout.addLayout(row)

        if consultations:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
            self._detail_layout.addWidget(sep)

            cons_title = QLabel(f"{texts.XEMPUS_EMPLOYEE_DETAIL_CONSULTATIONS} ({len(consultations)})")
            cons_title.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {PRIMARY_900};")
            self._detail_layout.addWidget(cons_title)

            for c in consultations[:15]:
                c_status = c.status_label or c.status or "–"
                c_color = c.status_color or PRIMARY_500
                c_date = fmt_date(c.beratungsdatum) or "–"
                c_insurer = c.versicherer or ""
                c_tarif = c.tarif or ""
                info_parts = [p for p in [c_date, c_insurer, c_tarif] if p and p != "–"]
                info_line = " · ".join(info_parts)

                c_frame = QFrame()
                c_frame.setStyleSheet(f"""
                    QFrame {{
                        border-left: 3px solid {c_color};
                        padding: 2px 0 2px 8px;
                        margin: 1px 0;
                    }}
                """)
                c_lay = QVBoxLayout(c_frame)
                c_lay.setContentsMargins(8, 4, 4, 4)
                c_lay.setSpacing(1)
                c_status_lbl = QLabel(c_status)
                c_status_lbl.setStyleSheet(f"color: {c_color}; font-size: {FONT_SIZE_CAPTION}; font-weight: 600;")
                c_lay.addWidget(c_status_lbl)
                if info_line:
                    c_info_lbl = QLabel(info_line)
                    c_info_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
                    c_info_lbl.setWordWrap(True)
                    c_lay.addWidget(c_info_lbl)
                if c.gesamtbeitrag is not None:
                    c_amount = QLabel(format_eur(c.gesamtbeitrag))
                    c_amount.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_CAPTION}; font-weight: 500;")
                    c_lay.addWidget(c_amount)
                self._detail_layout.addWidget(c_frame)

        self._detail_layout.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.resize(self.size())


class _ImportTab(QWidget):
    """Import-Panel mit Datei-Upload und Batch-Historie."""

    import_completed = Signal()

    def __init__(self, xempus_api: XempusAPI, parent=None):
        super().__init__(parent)
        self._api = xempus_api
        self._import_worker = None
        self._batches_worker = None
        self._diff_worker = None
        self._toast_manager = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(12)

        import_frame = QFrame()
        import_frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 8px;
                border-top: 3px solid {ACCENT_500};
            }}
        """)
        import_layout = QVBoxLayout(import_frame)
        import_layout.setContentsMargins(20, 16, 20, 16)
        import_layout.setSpacing(8)

        title = QLabel(texts.XEMPUS_IMPORT_TITLE)
        title.setStyleSheet(f"font-weight: 700; font-size: 12pt; color: {PRIMARY_900};")
        import_layout.addWidget(title)

        desc = QLabel(texts.XEMPUS_IMPORT_DESC)
        desc.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        import_layout.addWidget(desc)

        btn_row = QHBoxLayout()
        self._import_btn = QPushButton(texts.XEMPUS_IMPORT_SELECT_FILE)
        self._import_btn.setStyleSheet(get_secondary_button_style())
        self._import_btn.setCursor(Qt.PointingHandCursor)
        self._import_btn.clicked.connect(self._select_file)
        btn_row.addWidget(self._import_btn)

        self._progress_label = QLabel()
        self._progress_label.setStyleSheet(f"color: {ACCENT_500}; font-size: {FONT_SIZE_CAPTION};")
        btn_row.addWidget(self._progress_label)
        btn_row.addStretch()
        import_layout.addLayout(btn_row)

        root.addWidget(import_frame)

        history_title = QLabel(texts.XEMPUS_IMPORT_BATCH_HISTORY)
        history_title.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
        root.addWidget(history_title)

        self._batch_model = XempusBatchTableModel()
        self._batch_table = QTableView()
        self._batch_table.setModel(self._batch_model)
        self._batch_table.setSelectionBehavior(QTableView.SelectRows)
        self._batch_table.setSelectionMode(QTableView.SingleSelection)
        self._batch_table.setAlternatingRowColors(True)
        self._batch_table.setSortingEnabled(True)
        self._batch_table.setStyleSheet(get_provision_table_style())
        self._batch_table.verticalHeader().setVisible(False)
        self._batch_table.horizontalHeader().setStretchLastSection(True)
        phase_colors = {
            'raw_ingest': {'bg': '#fff3e0', 'text': '#e65100'},
            'normalize': {'bg': '#e3f2fd', 'text': '#1565c0'},
            'snapshot_update': {'bg': '#e8f5e9', 'text': '#2e7d32'},
            'complete': {'bg': '#e8f5e9', 'text': '#1b5e20'},
        }
        self._batch_table.setItemDelegateForColumn(
            XempusBatchTableModel.COL_PHASE,
            PillBadgeDelegate(phase_colors, parent=self._batch_table)
        )
        self._batch_table.doubleClicked.connect(self._on_batch_double_click)
        root.addWidget(self._batch_table, 1)

        self._loading = ProvisionLoadingOverlay(self)
        self._loading.hide()

    def refresh(self):
        detach_worker(self._batches_worker)
        self._batches_worker = XempusBatchesLoadWorker(self._api)
        self._batches_worker.finished.connect(self._on_batches_loaded)
        self._batches_worker.error.connect(lambda m: logger.error(f"Batches: {m}"))
        self._batches_worker.start()

    def _on_batches_loaded(self, batches: list):
        self._batch_model.set_data(batches)
        if self._batch_table.model().rowCount() > 0:
            self._batch_table.resizeColumnsToContents()

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, texts.XEMPUS_IMPORT_SELECT_FILE,
            "", "Excel (*.xlsx)")
        if not path:
            return
        self._start_import(path)

    def _start_import(self, filepath: str):
        if self._import_worker and self._import_worker.isRunning():
            return

        import os
        self._pending_filename = os.path.basename(filepath)

        self._progress_label.setText(texts.XEMPUS_IMPORT_RUNNING)
        self._import_btn.setEnabled(False)

        run_worker(
            self,
            lambda w, fp=filepath: self._parse_file(fp),
            self._on_parse_complete,
            on_error=self._on_parse_error,
        )

    @staticmethod
    def _parse_file(filepath: str):
        result = parse_xempus_complete(filepath)
        return prepare_sheets_for_upload(result)

    def _on_parse_complete(self, sheets):
        if not sheets:
            self._progress_label.setText(texts.XEMPUS_IMPORT_ERROR.format(error="Keine Daten"))
            self._import_btn.setEnabled(True)
            return

        self._import_worker = XempusImportWorker(self._api, self._pending_filename, sheets)
        self._import_worker.phase_changed.connect(self._on_phase_changed)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.error.connect(self._on_import_error)
        self._import_worker.start()

    def _on_parse_error(self, error_msg):
        self._progress_label.setText(texts.XEMPUS_IMPORT_ERROR.format(error=error_msg))
        self._import_btn.setEnabled(True)

    def _on_phase_changed(self, phase: int, desc: str):
        self._progress_label.setText(texts.XEMPUS_IMPORT_PROGRESS.format(phase=phase, desc=desc))

    def _on_import_finished(self, result):
        self._import_btn.setEnabled(True)
        rc = result.get('record_counts', {}) if isinstance(result, dict) else {}
        employers = rc.get('employers', 0)
        employees = rc.get('employees', 0)
        consultations = rc.get('consultations', 0)

        sync = result.get('sync', {}) if isinstance(result, dict) else {}
        match = result.get('match', {}) if isinstance(result, dict) else {}
        synced = sync.get('synced', 0)
        matched = match.get('matched', 0)

        msg = texts.XEMPUS_IMPORT_SUCCESS.format(
            employers=employers, employees=employees, consultations=consultations)
        if synced or matched:
            msg += '\n' + texts.XEMPUS_SYNC_RESULT.format(synced=synced, matched=matched)
        self._progress_label.setText(msg)
        self.refresh()
        self.import_completed.emit()

    def _on_import_error(self, msg: str):
        self._import_btn.setEnabled(True)
        self._progress_label.setText(texts.XEMPUS_IMPORT_ERROR.format(error=msg))
        logger.error(f"Xempus import error: {msg}")

    def _on_batch_double_click(self, index: QModelIndex):
        batch = self._batch_model.get_batch(index.row())
        if not batch or batch.import_phase != 'complete':
            return
        self._show_diff(batch.id)

    def _show_diff(self, batch_id: int):
        detach_worker(self._diff_worker)
        self._diff_worker = XempusDiffLoadWorker(self._api, batch_id)
        self._diff_worker.finished.connect(self._show_diff_dialog)
        self._diff_worker.error.connect(lambda m: logger.error(f"Diff: {m}"))
        self._diff_worker.start()

    def _show_diff_dialog(self, diff: Optional[XempusDiff]):
        if not diff:
            return
        dlg = DiffDialog(diff, self)
        dlg.exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.resize(self.size())


class _StatusMappingTab(QWidget):
    """Status-Mapping-Verwaltung."""

    def __init__(self, xempus_api: XempusAPI, parent=None):
        super().__init__(parent)
        self._api = xempus_api
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        title = QLabel(texts.XEMPUS_STATUS_MAP_TITLE)
        title.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()

        desc = QLabel(texts.XEMPUS_STATUS_MAP_DESC)
        desc.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        toolbar.addWidget(desc)
        root.addLayout(toolbar)

        self._sm_model = StatusMappingModel()
        self._sm_table = QTableView()
        self._sm_table.setModel(self._sm_model)
        self._sm_table.setSelectionBehavior(QTableView.SelectRows)
        self._sm_table.setSelectionMode(QTableView.SingleSelection)
        self._sm_table.setAlternatingRowColors(True)
        self._sm_table.setStyleSheet(get_provision_table_style())
        self._sm_table.verticalHeader().setVisible(False)
        self._sm_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self._sm_table, 1)

        self._loading = ProvisionLoadingOverlay(self)
        self._loading.hide()

    def refresh(self):
        detach_worker(self._worker)
        self._loading.show()
        self._worker = StatusMappingLoadWorker(self._api)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, mappings: list):
        self._loading.hide()
        self._sm_model.set_data(mappings)
        if self._sm_table.model().rowCount() > 0:
            self._sm_table.resizeColumnsToContents()

    def _on_error(self, msg: str):
        self._loading.hide()
        logger.error(f"Status mapping load error: {msg}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.resize(self.size())


# =============================================================================
# Diff Dialog
# =============================================================================


# =============================================================================
# Main Panel
# =============================================================================


class XempusInsightPanel(QWidget):
    """Xempus Insight Engine: Tabbed-Panel mit Arbeitgebern, Mitarbeitern, Import, Status-Mapping."""

    navigate_to_panel = Signal(int)

    def __init__(self, provision_api: ProvisionAPI):
        super().__init__()
        self._provision_api = provision_api
        self._xempus_api = XempusAPI(provision_api.client)
        self._tabs_initialized = set()
        self._toast_manager = None
        self._setup_ui()
        QTimer.singleShot(100, self._init_first_tab)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        header = SectionHeader(texts.XEMPUS_NAV_TITLE)
        root.addWidget(header)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 4px;
                background-color: {BG_PRIMARY};
            }}
            QTabBar::tab {{
                padding: 8px 16px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {PRIMARY_900};
                border-bottom: 2px solid {ACCENT_500};
                font-weight: 600;
            }}
            QTabBar::tab:hover {{
                color: {PRIMARY_900};
                background-color: {BG_SECONDARY};
            }}
        """)

        self._employers_tab = _EmployersTab(self._xempus_api)
        self._employers_tab.employer_double_clicked.connect(self._on_employer_double_clicked)
        self._tabs.addTab(self._employers_tab, texts.XEMPUS_TAB_EMPLOYERS)

        self._employees_tab = _EmployeesTab(self._xempus_api)
        self._tabs.addTab(self._employees_tab, texts.XEMPUS_TAB_EMPLOYEES)

        self._import_tab = _ImportTab(self._xempus_api)
        self._import_tab.import_completed.connect(self._on_import_completed)
        self._tabs.addTab(self._import_tab, texts.XEMPUS_TAB_IMPORT)

        self._status_map_tab = _StatusMappingTab(self._xempus_api)
        self._tabs.addTab(self._status_map_tab, texts.XEMPUS_TAB_STATUS_MAP)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs, 1)

    def _init_first_tab(self):
        self._ensure_tab_loaded(0)

    def _on_tab_changed(self, index: int):
        self._ensure_tab_loaded(index)

    def _ensure_tab_loaded(self, index: int):
        if index in self._tabs_initialized:
            return
        self._tabs_initialized.add(index)
        tab = self._tabs.widget(index)
        if hasattr(tab, 'refresh'):
            tab.refresh()

    def _on_employer_double_clicked(self, employer_id: str):
        employee_tab_index = self._tabs.indexOf(self._employees_tab)
        self._tabs_initialized.add(employee_tab_index)
        self._employees_tab.refresh()
        self._tabs.setCurrentIndex(employee_tab_index)
        self._employees_tab.filter_by_employer(employer_id)

    def _on_import_completed(self):
        self._tabs_initialized.discard(0)
        self._tabs_initialized.discard(1)
        if self._tabs.currentIndex() == 0:
            self._employers_tab.refresh()
        elif self._tabs.currentIndex() == 1:
            self._employees_tab.refresh()

    def refresh(self):
        """Alle geladenen Tabs neu laden."""
        for idx in list(self._tabs_initialized):
            tab = self._tabs.widget(idx)
            if hasattr(tab, 'refresh'):
                tab.refresh()
