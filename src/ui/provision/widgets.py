# -*- coding: utf-8 -*-
"""
Wiederverwendbare UI-Bausteine fuer das Provisionsmanagement.

Alle Widgets folgen den ACENCIA Design-Tokens und den
visuellen Prinzipien des GF-Reworks (Pill-Badges, Donut-Charts,
FilterChips, KPI-Karten, etc.).
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QPushButton, QStyledItemDelegate, QStyle, QMenu,
    QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QRect, QSize, QModelIndex, QPoint, QPointF, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QFontMetrics

from ui.styles.tokens import (
    PRIMARY_0, PRIMARY_100, PRIMARY_500, PRIMARY_900,
    ACCENT_500, BG_PRIMARY, BG_SECONDARY, BG_TERTIARY,
    BORDER_DEFAULT, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    FONT_WEIGHT_MEDIUM, FONT_WEIGHT_BOLD,
    RADIUS_MD, RADIUS_LG, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    SUCCESS, ERROR, WARNING,
    PILL_COLORS, ROLE_BADGE_COLORS, ART_BADGE_COLORS,
)
from i18n import de as texts

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# 1. PillBadgeDelegate
# =============================================================================

class PillBadgeDelegate(QStyledItemDelegate):
    """Malt abgerundete Pill-Badges in Tabellenzellen.

    Farb-Mapping wird ueber ``color_map`` konfiguriert.
    Jeder Eintrag: ``{"bg": "#hex", "text": "#hex"}``.
    Zusaetzlich kann ``label_map`` interne Werte in GF-Sprache uebersetzen.
    """

    def __init__(self, color_map: dict, label_map: dict | None = None, parent=None):
        super().__init__(parent)
        self._color_map = color_map
        self._label_map = label_map or {}

    def paint(self, painter: QPainter, option, index: QModelIndex):
        raw_value = index.data(Qt.DisplayRole)
        if raw_value is None:
            return

        value = str(raw_value).strip()
        lookup_key = value.lower().replace(" ", "_")
        colors = self._color_map.get(lookup_key)

        if not colors:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor(PRIMARY_100))

        label = self._label_map.get(lookup_key, value)

        font = QFont()
        font.setFamily("Open Sans")
        font.setPointSize(9)
        font.setWeight(QFont.Medium)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(label)
        text_height = fm.height()

        pill_w = text_width + 24
        pill_h = text_height + 8
        pill_x = option.rect.x() + (option.rect.width() - pill_w) // 2
        pill_y = option.rect.y() + (option.rect.height() - pill_h) // 2
        pill_rect = QRect(pill_x, pill_y, pill_w, pill_h)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(colors["bg"]))
        painter.drawRoundedRect(pill_rect, pill_h // 2, pill_h // 2)

        painter.setPen(QColor(colors["text"]))
        painter.setFont(font)
        painter.drawText(pill_rect, Qt.AlignCenter, label)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 52)


# =============================================================================
# 2. DonutChartWidget
# =============================================================================

class DonutChartWidget(QWidget):
    """Ring-/Donut-Chart mit Prozentzahl in der Mitte."""

    def __init__(
        self,
        percent: float = 0.0,
        size: int = 120,
        thickness: int = 14,
        color_fill: str = SUCCESS,
        color_bg: str = PRIMARY_100,
        parent=None,
    ):
        super().__init__(parent)
        self._percent = percent
        self._size = size
        self._thickness = thickness
        self._color_fill = color_fill
        self._color_bg = color_bg
        self.setFixedSize(size, size)

    def set_percent(self, value: float):
        import math
        if math.isnan(value) or math.isinf(value):
            value = 0.0
        self._percent = max(0.0, min(100.0, value))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        margin = self._thickness // 2 + 2
        rect = QRect(margin, margin, self._size - 2 * margin, self._size - 2 * margin)

        bg_pen = QPen(QColor(self._color_bg), self._thickness)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        fill_pen = QPen(QColor(self._color_fill), self._thickness)
        fill_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(fill_pen)
        span = int(self._percent / 100.0 * 360 * 16)
        painter.drawArc(rect, 90 * 16, -span)

        painter.setPen(QColor(PRIMARY_900))
        font = QFont()
        font.setFamily("Open Sans")
        font.setPointSize(14)
        font.setWeight(QFont.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, f"{self._percent:.0f}%")

        painter.end()


# =============================================================================
# 3. FilterChipBar
# =============================================================================

class FilterChipBar(QWidget):
    """Horizontale Reihe von Toggle-Chips mit Zaehler."""

    filter_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._buttons: list[QPushButton] = []
        self._active_key = ""

    def set_chips(self, chips: list[tuple[str, str, int]]):
        """Setzt die Chips. Jeder Chip: (key, label, count)."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._buttons.clear()

        for key, label, count in chips:
            btn = QPushButton(f"{label} ({count})")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("chip_key", key)
            btn.clicked.connect(lambda checked, k=key: self._on_chip_clicked(k))
            self._buttons.append(btn)
            self._layout.addWidget(btn)

        self._layout.addStretch()
        self._apply_styles()

        if self._buttons:
            self._buttons[0].setChecked(True)
            self._active_key = self._buttons[0].property("chip_key")

    def _on_chip_clicked(self, key: str):
        self._active_key = key
        for btn in self._buttons:
            btn.setChecked(btn.property("chip_key") == key)
        self._apply_styles()
        self.filter_changed.emit(key)

    def _apply_styles(self):
        for btn in self._buttons:
            if btn.isChecked():
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ACCENT_500};
                        color: white;
                        border: 2px solid {ACCENT_500};
                        border-radius: 15px;
                        padding: 5px 16px;
                        font-family: {FONT_BODY};
                        font-size: {FONT_SIZE_BODY};
                        font-weight: 600;
                        min-height: 28px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: white;
                        color: {PRIMARY_900};
                        border: 1.5px solid {PRIMARY_500};
                        border-radius: 15px;
                        padding: 5px 16px;
                        font-family: {FONT_BODY};
                        font-size: {FONT_SIZE_BODY};
                        font-weight: 500;
                        min-height: 28px;
                    }}
                    QPushButton:hover {{
                        background-color: {PRIMARY_100};
                        border-color: {PRIMARY_900};
                    }}
                """)

    def active_key(self) -> str:
        return self._active_key


# =============================================================================
# 4. SectionHeader
# =============================================================================

class SectionHeader(QWidget):
    """Titel + Beschreibung fuer eine Sektion, optional mit Action-Button."""

    def __init__(self, title: str, description: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self._title = QLabel(title)
        self._title.setStyleSheet(
            f"font-size: 13pt; font-weight: 600; color: {PRIMARY_900}; font-family: {FONT_BODY};"
        )
        text_col.addWidget(self._title)

        if description:
            self._desc = QLabel(description)
            self._desc.setStyleSheet(
                f"font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500}; font-family: {FONT_BODY};"
            )
            self._desc.setWordWrap(True)
            text_col.addWidget(self._desc)
        else:
            self._desc = None

        layout.addLayout(text_col)
        layout.addStretch()
        self._action_area = QHBoxLayout()
        self._action_area.setSpacing(8)
        layout.addLayout(self._action_area)

    def add_action(self, button: QPushButton):
        self._action_area.addWidget(button)


# =============================================================================
# 5. ThreeDotMenuDelegate
# =============================================================================

class ThreeDotMenuDelegate(QStyledItemDelegate):
    """Malt ein Drei-Punkt-Icon und oeffnet bei Klick ein QMenu.

    ``menu_builder`` ist ein Callable das fuer einen gegebenen Model-Index
    ein QMenu zurueckgibt:  ``menu_builder(index: QModelIndex) -> QMenu``.
    """

    def __init__(self, menu_builder, parent=None):
        super().__init__(parent)
        self._menu_builder = menu_builder

    def paint(self, painter: QPainter, option, index: QModelIndex):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor(PRIMARY_100))

        cx = float(option.rect.center().x())
        cy = float(option.rect.center().y())
        dot_r = 3
        dot_gap = 8
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(PRIMARY_900))
        for dy in (-dot_gap, 0, dot_gap):
            painter.drawEllipse(QPointF(cx, cy + dy), dot_r, dot_r)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.MouseButtonRelease:
            menu = self._menu_builder(index)
            if menu:
                global_pos = option.widget.viewport().mapToGlobal(
                    QPoint(option.rect.right(), option.rect.center().y())
                )
                menu.exec(global_pos)
                return True
        return False

    def sizeHint(self, option, index):
        return QSize(48, 52)


# =============================================================================
# 6. KpiCard
# =============================================================================

class KpiCard(QFrame):
    """Weisse Karte mit farbiger Akzent-Leiste, CAPS-Titel, Wert, Subline.

    Kann optional einen Action-Button oder ein Widget (z.B. DonutChart) enthalten.
    """

    clicked = Signal()

    def __init__(
        self,
        title: str,
        accent_color: str = PRIMARY_900,
        parent=None,
    ):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.ArrowCursor)
        self.setStyleSheet(f"""
            KpiCard {{
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                border-top: 3px solid {accent_color};
            }}
        """)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(20, 16, 20, 16)
        self._main_layout.setSpacing(6)

        self._title_label = QLabel(title.upper())
        self._title_label.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; "
            f"font-family: {FONT_BODY}; letter-spacing: 0.5px;"
        )
        self._main_layout.addWidget(self._title_label)

        self._value_label = QLabel("")
        self._value_label.setStyleSheet(
            f"color: {PRIMARY_900}; font-size: 20pt; font-weight: 700; font-family: {FONT_BODY};"
        )
        self._main_layout.addWidget(self._value_label)

        self._subline_label = QLabel("")
        self._subline_label.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};"
        )
        self._subline_label.setWordWrap(True)
        self._main_layout.addWidget(self._subline_label)

        self._extra_layout = QVBoxLayout()
        self._extra_layout.setSpacing(4)
        self._main_layout.addLayout(self._extra_layout)

    def set_value(self, text: str):
        self._value_label.setText(text)

    def set_subline(self, text: str):
        self._subline_label.setText(text)

    def set_value_color(self, color: str):
        self._value_label.setStyleSheet(
            f"color: {color}; font-size: 20pt; font-weight: 700; font-family: {FONT_BODY};"
        )

    def add_extra_widget(self, widget: QWidget):
        self._extra_layout.addWidget(widget)

    def add_extra_label(self, text: str, color: str = PRIMARY_500):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {color}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};"
        )
        lbl.setWordWrap(True)
        self._extra_layout.addWidget(lbl)
        return lbl

    def add_action_button(self, text: str, callback=None) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        if callback:
            btn.clicked.connect(callback)
        self._extra_layout.addWidget(btn)
        return btn


# =============================================================================
# 7. PaginationBar
# =============================================================================

class PaginationBar(QWidget):
    """Seiten-Navigation: 'Zeige 1-50 von 276 Positionen'."""

    page_changed = Signal(int)

    def __init__(self, page_size: int = 50, parent=None):
        super().__init__(parent)
        self._page = 0
        self._total = 0
        self._page_size = page_size

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self._info_label = QLabel("")
        self._info_label.setStyleSheet(
            f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY}; font-family: {FONT_BODY};"
        )
        layout.addWidget(self._info_label)
        layout.addStretch()

        nav_btn_style = f"""
            QPushButton {{
                background-color: {PRIMARY_900};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: 600;
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: #0a3460;
            }}
            QPushButton:disabled {{
                background-color: #c8d3de;
                color: white;
            }}
        """

        self._prev_btn = QPushButton("<")
        self._prev_btn.setFixedSize(40, 34)
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setStyleSheet(nav_btn_style)
        self._prev_btn.clicked.connect(self._go_prev)
        layout.addWidget(self._prev_btn)

        self._page_label = QLabel("")
        self._page_label.setStyleSheet(
            f"color: {PRIMARY_900}; font-size: 11pt; font-weight: 700; "
            f"font-family: {FONT_BODY}; padding: 0 10px;"
        )
        layout.addWidget(self._page_label)

        self._next_btn = QPushButton(">")
        self._next_btn.setFixedSize(40, 34)
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setStyleSheet(nav_btn_style)
        self._next_btn.clicked.connect(self._go_next)
        layout.addWidget(self._next_btn)

    def set_total(self, total: int):
        self._total = total
        self._page = 0
        self._update_display()

    def _go_prev(self):
        if self._page > 0:
            self._page -= 1
            self._update_display()
            self.page_changed.emit(self._page)

    def _go_next(self):
        max_page = max(0, (self._total - 1) // self._page_size)
        if self._page < max_page:
            self._page += 1
            self._update_display()
            self.page_changed.emit(self._page)

    def _update_display(self):
        if self._total == 0:
            self._info_label.setText("")
            self._page_label.setText("")
            return
        start = self._page * self._page_size + 1
        end = min(start + self._page_size - 1, self._total)
        max_page = max(1, (self._total - 1) // self._page_size + 1)
        self._info_label.setText(
            texts.PROVISION_PAGINATION_SHOWING.format(start=start, end=end, total=self._total)
        )
        self._page_label.setText(f"{self._page + 1} / {max_page}")
        self._prev_btn.setEnabled(self._page > 0)
        self._next_btn.setEnabled(self._page < max_page - 1)

    @property
    def current_page(self) -> int:
        return self._page

    @property
    def page_size(self) -> int:
        return self._page_size


# =============================================================================
# 8. StatementCard
# =============================================================================

class StatementCard(QFrame):
    """Buchungszeilen-Aufschluesselung (Brutto / Abzuege / Netto)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            StatementCard {{
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(6)
        self._rows: list[QHBoxLayout] = []

    def clear_rows(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub = item.layout()
                while sub.count():
                    sub_item = sub.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()
        self._rows.clear()

    def add_line(self, label: str, amount: str, bold: bool = False, color: str = ""):
        row = QHBoxLayout()
        row.setSpacing(16)
        weight = "700" if bold else "400"
        size = "12pt" if bold else FONT_SIZE_BODY
        text_color = color or PRIMARY_900

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: {size}; font-weight: {weight}; color: {text_color}; font-family: {FONT_BODY};"
        )
        row.addWidget(lbl)
        row.addStretch()

        val = QLabel(amount)
        val.setStyleSheet(
            f"font-size: {size}; font-weight: {weight}; color: {text_color}; font-family: {FONT_BODY};"
        )
        row.addWidget(val)

        self._rows.append(row)
        self._layout.addLayout(row)

    def add_separator(self):
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {BORDER_DEFAULT}; border: none;")
        self._layout.addWidget(line)


# =============================================================================
# 9. ActivityFeedWidget
# =============================================================================

class ActivityFeedWidget(QWidget):
    """Scrollbare Activity-Feed-Liste mit farbigen Punkten."""

    COLORS = {
        "created":  SUCCESS,
        "changed":  "#3b82f6",
        "deleted":  ERROR,
        "import":   ACCENT_500,
        "matched":  SUCCESS,
        "status":   "#8b5cf6",
        "default":  PRIMARY_500,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._container = QWidget()
        self._feed_layout = QVBoxLayout(self._container)
        self._feed_layout.setContentsMargins(0, 0, 0, 0)
        self._feed_layout.setSpacing(8)
        self._feed_layout.addStretch()
        scroll.setWidget(self._container)
        outer.addWidget(scroll)

    def set_items(self, items: list[dict]):
        """Setzt die Feed-Eintraege. Jeder dict: {type, text, time}."""
        while self._feed_layout.count() > 1:
            item = self._feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for entry in items:
            color = self.COLORS.get(entry.get("type", ""), self.COLORS["default"])
            row = QHBoxLayout()
            row.setSpacing(8)

            dot = QLabel("\u25cf")
            dot.setStyleSheet(f"color: {color}; font-size: 8pt;")
            dot.setFixedWidth(14)
            row.addWidget(dot)

            text = QLabel(f"<span style='color:{PRIMARY_500};'>{entry.get('time', '')}</span> "
                          f"{entry.get('text', '')}")
            text.setStyleSheet(
                f"font-size: {FONT_SIZE_CAPTION}; color: {PRIMARY_900}; font-family: {FONT_BODY};"
            )
            text.setWordWrap(True)
            row.addWidget(text, 1)

            wrapper = QWidget()
            wrapper.setLayout(row)
            idx = max(0, self._feed_layout.count() - 1)
            self._feed_layout.insertWidget(idx, wrapper)


# =============================================================================
# 10. EUR-Formatierung Hilfsfunktion
# =============================================================================

def format_eur(value) -> str:
    """Formatiert einen numerischen Wert als EUR-String mit deutschem Format."""
    try:
        v = float(value)
        formatted = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted} \u20ac"
    except (ValueError, TypeError):
        return "0,00 \u20ac"


def get_secondary_button_style() -> str:
    """Styling fuer sekundaere Buttons mit sichtbarem Rahmen."""
    return f"""
        QPushButton {{
            background-color: white;
            color: {PRIMARY_900};
            border: 1.5px solid {PRIMARY_500};
            border-radius: 6px;
            padding: 7px 16px;
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {PRIMARY_100};
            border-color: {PRIMARY_900};
        }}
        QPushButton:pressed {{
            background-color: #c8d6e5;
        }}
        QPushButton:disabled {{
            color: #b0b0b0;
            border-color: #d0d0d0;
            background-color: #f5f5f5;
        }}
    """


def get_search_field_style() -> str:
    """Styling fuer Suchfelder mit sichtbarem Rahmen."""
    return f"""
        QLineEdit {{
            background-color: white;
            color: {PRIMARY_900};
            border: 1.5px solid {PRIMARY_500};
            border-radius: 6px;
            padding: 4px 12px;
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            min-height: 28px;
        }}
        QLineEdit:focus {{
            border-color: {ACCENT_500};
            border-width: 2px;
        }}
        QLineEdit::placeholder {{
            color: {PRIMARY_500};
        }}
    """


def get_combo_style() -> str:
    """Styling fuer ComboBoxen mit sichtbarem Rahmen."""
    return f"""
        QComboBox {{
            background-color: white;
            color: {PRIMARY_900};
            border: 1.5px solid {PRIMARY_500};
            border-radius: 6px;
            padding: 4px 12px;
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            min-height: 28px;
        }}
        QComboBox:hover {{
            border-color: {PRIMARY_900};
        }}
        QComboBox:focus {{
            border-color: {ACCENT_500};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background-color: white;
            border: 1.5px solid {PRIMARY_500};
            border-radius: 4px;
            selection-background-color: {PRIMARY_100};
        }}
    """


class ProvisionLoadingOverlay(QWidget):
    """Leichtes Loading-Overlay fuer Provision-Panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._dot_count = 0
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate)
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(texts.PROVISION_LOADING)
        self._label.setStyleSheet(
            f"font-size: 13pt; font-weight: 500; color: {PRIMARY_500}; "
            f"background: transparent;"
        )
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

    def showEvent(self, event):
        super().showEvent(event)
        self._dot_count = 0
        self._animation_timer.start(400)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._animation_timer.stop()

    def _animate(self):
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        self._label.setText(f"{texts.PROVISION_LOADING}{dots}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(255, 255, 255, 200))
        super().paintEvent(event)
