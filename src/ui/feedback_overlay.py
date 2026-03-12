# -*- coding: utf-8 -*-
"""
Support-Feedback-Overlay – modales Enterprise-UI fuer Nutzer-Feedback.

Bietet drei Feedback-Typen (Feedback/Kritik, Feature-Wunsch, Problem/Fehler),
dynamische Formularerweiterung bei Bug-Meldungen, Screenshot-Upload und
Prioritaetswahl. Alle Texte kommen aus i18n/de.py, Styling aus Design-Tokens.

Das Overlay stellt ueber ``collect_payload()`` ein strukturiertes Dict bereit,
das spaeter direkt an die Support-API uebergeben werden kann.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QTextEdit, QScrollArea, QCheckBox,
    QGraphicsOpacityEffect, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor

from i18n import de as texts
import ui.styles.tokens as tok
from ui.widgets.screenshot_upload_widget import ScreenshotUploadWidget

logger = logging.getLogger(__name__)


# ======================================================================
# Payload dataclass
# ======================================================================

@dataclass
class FeedbackPayload:
    feedback_type: str = ""
    priority: str = "low"
    subject: str = ""
    content: str = ""
    reproduction_steps: str = ""
    include_logs: bool = False
    screenshot_path: Optional[str] = None


# ======================================================================
# Selectable type card
# ======================================================================

class _TypeCard(QFrame):
    """Klickbare Auswahlkarte fuer Feedback-Typ."""

    clicked = Signal()

    def __init__(self, icon: str, title: str, description: str, parent=None):
        super().__init__(parent)
        self._selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(88)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            f"font-size: 18pt; background: transparent; border: none;"
        )
        icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.TEXT_PRIMARY}; "
            f"background: transparent; border: none;"
        )
        title_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: 7pt; "
            f"color: {tok.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        desc_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(desc_lbl)

        self._apply_style()

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(f"""
                _TypeCard {{
                    background-color: {tok.BG_SECONDARY};
                    border: 2px solid {tok.ACCENT_500};
                    border-radius: {tok.RADIUS_XL};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                _TypeCard {{
                    background-color: {tok.BG_PRIMARY};
                    border: 2px solid {tok.BORDER_DEFAULT};
                    border-radius: {tok.RADIUS_XL};
                }}
                _TypeCard:hover {{
                    border-color: {tok.PRIMARY_500};
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ======================================================================
# Priority card (smaller)
# ======================================================================

class _PriorityCard(QFrame):
    """Kleine klickbare Karte fuer Prioritaetswahl."""

    clicked = Signal()

    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self._selected = False
        self._color = color
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        dot = QLabel("\u25CF")
        dot.setStyleSheet(
            f"font-size: 8pt; color: {color}; background: transparent; border: none;"
        )
        dot.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(dot)

        text = QLabel(label)
        text.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.TEXT_PRIMARY}; "
            f"background: transparent; border: none;"
        )
        text.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(text)

        self._apply_style()

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(f"""
                _PriorityCard {{
                    background-color: {tok.BG_SECONDARY};
                    border: 2px solid {self._color};
                    border-radius: {tok.RADIUS_LG};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                _PriorityCard {{
                    background-color: {tok.BG_PRIMARY};
                    border: 1px solid {tok.BORDER_DEFAULT};
                    border-radius: {tok.RADIUS_LG};
                }}
                _PriorityCard:hover {{
                    border-color: {tok.PRIMARY_500};
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ======================================================================
# Feedback Overlay
# ======================================================================

class FeedbackOverlay(QWidget):
    """Modales Feedback-Overlay mit halbtransparentem Backdrop."""

    close_requested = Signal()
    submit_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._selected_type: str | None = None
        self._selected_priority: str = "low"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 32, 48, 32)
        outer.setAlignment(Qt.AlignCenter)

        self._panel = QFrame()
        self._panel.setMinimumWidth(780)
        self._panel.setMaximumWidth(920)
        self._panel.setStyleSheet(f"""
            QFrame#feedbackPanel {{
                background-color: {tok.BG_PRIMARY};
                border-radius: 18px;
                border: 1px solid {tok.BORDER_DEFAULT};
            }}
        """)
        self._panel.setObjectName("feedbackPanel")

        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        panel_layout.addWidget(self._build_header())

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(
            f"color: {tok.BORDER_DEFAULT}; background: {tok.BORDER_DEFAULT}; "
            f"max-height: 1px; border: none;"
        )
        panel_layout.addWidget(div)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
        )
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._body_layout = QVBoxLayout(scroll_content)
        self._body_layout.setContentsMargins(32, 24, 32, 16)
        self._body_layout.setSpacing(20)

        self._build_type_selection()
        self._build_priority_selection()
        self._build_form_fields()
        self._build_bug_section()
        self._build_screenshot_section()
        self._body_layout.addStretch()

        scroll.setWidget(scroll_content)
        panel_layout.addWidget(scroll, 1)

        panel_layout.addWidget(self._build_footer())

        outer.addWidget(self._panel)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._anim = None

        self._update_submit_state()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(32, 24, 24, 16)
        layout.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        title = QLabel(texts.FEEDBACK_TITLE)
        title.setStyleSheet(
            f"font-family: {tok.FONT_HEADLINE}; font-size: {tok.FONT_SIZE_H2}; "
            f"font-weight: {tok.FONT_WEIGHT_BOLD}; color: {tok.TEXT_PRIMARY}; "
            f"background: transparent; border: none;"
        )
        text_col.addWidget(title)

        subtitle = QLabel(texts.FEEDBACK_SUBTITLE)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"color: {tok.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        text_col.addWidget(subtitle)

        layout.addLayout(text_col, 1)

        close_btn = QPushButton("\u2715")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 14pt; color: {tok.PRIMARY_500};
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background-color: {tok.PRIMARY_100}; color: {tok.PRIMARY_900};
            }}
        """)
        close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(close_btn, alignment=Qt.AlignTop)

        return header

    # ------------------------------------------------------------------
    # Type selection (3 cards)
    # ------------------------------------------------------------------

    def _build_type_selection(self):
        row = QHBoxLayout()
        row.setSpacing(12)

        self._type_cards: dict[str, _TypeCard] = {}

        specs = [
            ("feedback", "\U0001F4AC", texts.FEEDBACK_TYPE_FEEDBACK, texts.FEEDBACK_TYPE_FEEDBACK_DESC),
            ("feature", "\U0001F4A1", texts.FEEDBACK_TYPE_FEATURE, texts.FEEDBACK_TYPE_FEATURE_DESC),
            ("bug", "\u26A0\uFE0F", texts.FEEDBACK_TYPE_PROBLEM, texts.FEEDBACK_TYPE_PROBLEM_DESC),
        ]

        for type_id, icon, title, desc in specs:
            card = _TypeCard(icon, title, desc)
            card.clicked.connect(lambda tid=type_id: self._on_type_selected(tid))
            self._type_cards[type_id] = card
            row.addWidget(card)

        self._body_layout.addLayout(row)

    def _on_type_selected(self, type_id: str):
        self._selected_type = type_id
        for tid, card in self._type_cards.items():
            card.selected = (tid == type_id)

        is_bug = type_id == "bug"
        self._bug_section.setVisible(is_bug)
        self._priority_section.setVisible(True)

        if is_bug:
            self._logs_checkbox.setChecked(True)

        self._update_submit_state()

    # ------------------------------------------------------------------
    # Priority selection
    # ------------------------------------------------------------------

    def _build_priority_selection(self):
        self._priority_section = QWidget()
        self._priority_section.setStyleSheet("background: transparent;")
        self._priority_section.setVisible(False)

        layout = QVBoxLayout(self._priority_section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(texts.FEEDBACK_PRIORITY_LABEL)
        label.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.TEXT_PRIMARY};"
        )
        layout.addWidget(label)

        row = QHBoxLayout()
        row.setSpacing(10)

        self._priority_cards: dict[str, _PriorityCard] = {}
        specs = [
            ("low", texts.FEEDBACK_PRIORITY_LOW, tok.SUCCESS),
            ("medium", texts.FEEDBACK_PRIORITY_MEDIUM, tok.ACCENT_500),
            ("high", texts.FEEDBACK_PRIORITY_HIGH, tok.ERROR),
        ]

        for prio_id, prio_label, color in specs:
            card = _PriorityCard(prio_label, color)
            card.clicked.connect(lambda pid=prio_id: self._on_priority_selected(pid))
            self._priority_cards[prio_id] = card
            row.addWidget(card)

        self._priority_cards["low"].selected = True

        layout.addLayout(row)
        self._body_layout.addWidget(self._priority_section)

    def _on_priority_selected(self, prio_id: str):
        self._selected_priority = prio_id
        for pid, card in self._priority_cards.items():
            card.selected = (pid == prio_id)

    # ------------------------------------------------------------------
    # Form fields
    # ------------------------------------------------------------------

    def _build_form_fields(self):
        subject_label = QLabel(texts.FEEDBACK_SUBJECT_LABEL)
        subject_label.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.TEXT_PRIMARY};"
        )
        self._body_layout.addWidget(subject_label)

        self._subject_edit = QLineEdit()
        self._subject_edit.setPlaceholderText(texts.FEEDBACK_SUBJECT_PLACEHOLDER)
        self._subject_edit.setFixedHeight(40)
        self._body_layout.addWidget(self._subject_edit)

        content_row = QHBoxLayout()
        content_label = QLabel(texts.FEEDBACK_CONTENT_LABEL)
        content_label.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.TEXT_PRIMARY};"
        )
        content_row.addWidget(content_label)

        required_marker = QLabel("*")
        required_marker.setStyleSheet(
            f"font-size: {tok.FONT_SIZE_BODY}; color: {tok.ERROR}; "
            f"font-weight: bold;"
        )
        content_row.addWidget(required_marker)
        content_row.addStretch()
        self._body_layout.addLayout(content_row)

        self._content_edit = QTextEdit()
        self._content_edit.setPlaceholderText(texts.FEEDBACK_CONTENT_PLACEHOLDER)
        self._content_edit.setMinimumHeight(140)
        self._content_edit.setMaximumHeight(200)
        self._content_edit.textChanged.connect(self._update_submit_state)
        self._body_layout.addWidget(self._content_edit)

    # ------------------------------------------------------------------
    # Bug-specific section
    # ------------------------------------------------------------------

    def _build_bug_section(self):
        self._bug_section = QWidget()
        self._bug_section.setStyleSheet("background: transparent;")
        self._bug_section.setVisible(False)

        layout = QVBoxLayout(self._bug_section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        hint = QLabel(texts.FEEDBACK_REPRO_HINT)
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_CAPTION}; "
            f"color: {tok.TEXT_SECONDARY}; background-color: {tok.BG_SECONDARY}; "
            f"border-radius: {tok.RADIUS_MD}; padding: 8px 12px;"
        )
        layout.addWidget(hint)

        repro_label = QLabel(texts.FEEDBACK_REPRO_LABEL)
        repro_label.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.TEXT_PRIMARY};"
        )
        layout.addWidget(repro_label)

        self._repro_edit = QTextEdit()
        self._repro_edit.setPlaceholderText(texts.FEEDBACK_REPRO_PLACEHOLDER)
        self._repro_edit.setMinimumHeight(100)
        self._repro_edit.setMaximumHeight(140)
        layout.addWidget(self._repro_edit)

        self._logs_checkbox = QCheckBox(texts.FEEDBACK_LOGS_CHECKBOX)
        self._logs_checkbox.setChecked(True)
        layout.addWidget(self._logs_checkbox)

        logs_hint = QLabel(texts.FEEDBACK_LOGS_HINT)
        logs_hint.setWordWrap(True)
        logs_hint.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: 7pt; "
            f"color: {tok.TEXT_DISABLED}; padding-left: 24px;"
        )
        layout.addWidget(logs_hint)

        self._body_layout.addWidget(self._bug_section)

    # ------------------------------------------------------------------
    # Screenshot section
    # ------------------------------------------------------------------

    def _build_screenshot_section(self):
        self._screenshot_widget = ScreenshotUploadWidget()
        self._body_layout.addWidget(self._screenshot_widget)

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet(f"""
            QWidget {{
                background-color: {tok.BG_PRIMARY};
                border-top: 1px solid {tok.BORDER_DEFAULT};
                border-bottom-left-radius: 18px;
                border-bottom-right-radius: 18px;
            }}
        """)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(32, 16, 32, 20)
        layout.setSpacing(12)

        cancel_btn = QPushButton(texts.FEEDBACK_CANCEL)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {tok.PRIMARY_900};
                border-radius: {tok.RADIUS_MD}; padding: 0 20px;
                font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY};
                font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.PRIMARY_900};
            }}
            QPushButton:hover {{ background-color: {tok.PRIMARY_100}; }}
        """)
        cancel_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(cancel_btn)

        layout.addStretch()

        self._submit_btn = QPushButton(texts.FEEDBACK_SUBMIT)
        self._submit_btn.setCursor(Qt.PointingHandCursor)
        self._submit_btn.setFixedHeight(40)
        self._submit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {tok.ACCENT_500}; color: {tok.TEXT_INVERSE};
                border: none; border-radius: {tok.RADIUS_MD}; padding: 0 28px;
                font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY};
                font-weight: {tok.FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{ background-color: {tok.ACCENT_HOVER}; }}
            QPushButton:pressed {{ background-color: {tok.ACCENT_PRESSED}; }}
            QPushButton:disabled {{
                background-color: {tok.PRIMARY_100}; color: {tok.TEXT_DISABLED};
            }}
        """)
        self._submit_btn.clicked.connect(self._on_submit)
        layout.addWidget(self._submit_btn)

        return footer

    # ------------------------------------------------------------------
    # Validation & Submit
    # ------------------------------------------------------------------

    def _update_submit_state(self):
        has_type = self._selected_type is not None
        has_content = bool(self._content_edit.toPlainText().strip())
        self._submit_btn.setEnabled(has_type and has_content)

    def _on_submit(self):
        payload = self.collect_payload()
        if not payload:
            return
        self.submit_requested.emit(payload)

    def collect_payload(self) -> dict | None:
        """Sammelt alle Formulardaten als Dict.

        Gibt None zurueck, wenn die Pflichtfelder nicht ausgefuellt sind.
        """
        if not self._selected_type:
            return None
        content = self._content_edit.toPlainText().strip()
        if not content:
            return None

        return {
            "feedback_type": self._selected_type,
            "priority": self._selected_priority,
            "subject": self._subject_edit.text().strip(),
            "content": content,
            "reproduction_steps": (
                self._repro_edit.toPlainText().strip()
                if self._selected_type == "bug" else ""
            ),
            "include_logs": (
                self._logs_checkbox.isChecked()
                if self._selected_type == "bug" else False
            ),
            "screenshot_path": self._screenshot_widget.file_path,
        }

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def _ensure_opacity_effect(self):
        """Stellt sicher, dass der Opacity-Effekt existiert (C++ Objekt kann zerstoert worden sein)."""
        try:
            self._opacity.opacity()
        except (RuntimeError, AttributeError):
            self._opacity = QGraphicsOpacityEffect(self)
            self._opacity.setOpacity(0.0)
            self.setGraphicsEffect(self._opacity)

    def show_animated(self):
        self._ensure_opacity_effect()
        if hasattr(self, '_anim') and self._anim is not None:
            self._anim.stop()
        self._opacity.setOpacity(0.0)
        self.show()
        self.raise_()
        self.setFocus()
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(250)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def close_animated(self, callback=None):
        self._ensure_opacity_effect()
        if hasattr(self, '_anim') and self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(180)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.finished.connect(self.hide)
        if callback:
            self._anim.finished.connect(callback)
        self._anim.start()

    def reset(self):
        """Setzt das gesamte Overlay in den Ausgangszustand zurueck."""
        self._selected_type = None
        self._selected_priority = "low"
        for card in self._type_cards.values():
            card.selected = False
        for card in self._priority_cards.values():
            card.selected = False
        self._priority_cards["low"].selected = True
        self._priority_section.setVisible(False)
        self._bug_section.setVisible(False)
        self._subject_edit.clear()
        self._content_edit.clear()
        self._repro_edit.clear()
        self._logs_checkbox.setChecked(True)
        self._screenshot_widget.reset()
        self._update_submit_state()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 15, 30, 40))

    def mousePressEvent(self, event):
        if not self._panel.geometry().contains(event.pos()):
            self.close_requested.emit()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_requested.emit()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            focused = self.focusWidget()
            if not isinstance(focused, QTextEdit):
                self._on_submit()
        else:
            super().keyPressEvent(event)
