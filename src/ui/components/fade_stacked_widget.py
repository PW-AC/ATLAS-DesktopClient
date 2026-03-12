# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Animated Stacked Widget mit Fade-Through-Transition

Drop-in-Replacement fuer QStackedWidget. Beim View-Wechsel wird ein
Overlay ueber den Stack geblendet (fade to black/transparent), dann
der View gewechselt und das Overlay wieder ausgeblendet.

Dieser Ansatz vermeidet QGraphicsOpacityEffect auf den Child-Widgets,
da diese bereits eigene Effects fuer Sidebar-Animationen nutzen koennen
(Qt erlaubt nur einen QGraphicsEffect pro Widget).

Die Animation kann per set_animated(False) deaktiviert werden.
"""

import logging
from typing import Optional

from PySide6.QtWidgets import QStackedWidget, QWidget
from PySide6.QtCore import (
    QPropertyAnimation, QEasingCurve, Signal, Qt, Property,
)
from PySide6.QtGui import QPainter, QColor

logger = logging.getLogger(__name__)

_DEFAULT_FADE_OUT_MS = 100
_DEFAULT_FADE_IN_MS = 150


class _FadeOverlay(QWidget):
    """Halbtransparentes Overlay fuer Fade-Through-Transitions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()

    def get_opacity(self) -> float:
        return self._opacity

    def set_opacity(self, value: float):
        self._opacity = value
        self.update()

    opacity = Property(float, get_opacity, set_opacity)

    def paintEvent(self, event):
        if self._opacity <= 0.001:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        alpha = int(self._opacity * 255)
        painter.fillRect(self.rect(), QColor(255, 255, 255, alpha))
        painter.end()


class FadeStackedWidget(QStackedWidget):
    """QStackedWidget mit optionalem Fade-Through beim View-Wechsel.

    Nutzt ein Overlay statt QGraphicsOpacityEffect, um Konflikte mit
    bestehenden Effects auf Child-Widgets zu vermeiden.
    """

    transition_finished = Signal()
    view_switched = Signal()

    def __init__(self, parent=None, fade_out_ms: int = _DEFAULT_FADE_OUT_MS,
                 fade_in_ms: int = _DEFAULT_FADE_IN_MS):
        super().__init__(parent)
        self._fade_out_ms = fade_out_ms
        self._fade_in_ms = fade_in_ms
        self._animated = True
        self._transitioning = False
        self._pending_index: Optional[int] = None
        self._fade_anim: Optional[QPropertyAnimation] = None

        self._overlay = _FadeOverlay(self)
        self._overlay.setGeometry(self.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())

    def set_animated(self, enabled: bool):
        """Aktiviert oder deaktiviert die Fade-Animation."""
        self._animated = enabled

    @property
    def is_transitioning(self) -> bool:
        return self._transitioning

    def setCurrentIndex(self, index: int):
        if index == self.currentIndex():
            return

        if not self._animated or self.count() == 0:
            self._do_hard_switch(index)
            return

        if self._transitioning:
            self._abort_transition()
            self._do_hard_switch(index)
            return

        self._start_fade_out(index)

    def setCurrentWidget(self, widget):
        idx = self.indexOf(widget)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def _do_hard_switch(self, index: int):
        """Sofortiger Wechsel ohne Animation."""
        self._overlay.hide()
        super().setCurrentIndex(index)
        self.view_switched.emit()
        self.transition_finished.emit()

    def _start_fade_out(self, target_index: int):
        """Phase 1: Overlay einblenden (verdeckt aktuellen View)."""
        self._transitioning = True
        self._pending_index = target_index

        self._overlay.set_opacity(0.0)
        self._overlay.setGeometry(self.rect())
        self._overlay.show()
        self._overlay.raise_()

        self._fade_anim = QPropertyAnimation(self._overlay, b"opacity", self)
        self._fade_anim.setDuration(self._fade_out_ms)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.InCubic)
        self._fade_anim.finished.connect(self._on_fade_out_done)
        self._fade_anim.start()

    def _on_fade_out_done(self):
        """Phase 2: View wechseln (hinter dem Overlay) und Overlay ausblenden.

        Emittiert view_switched sofort nach dem Switch, damit Downstream-
        Animationen (z.B. ModuleSidebar-Enter) parallel zum Fade-In starten.
        """
        target = self._pending_index
        self._pending_index = None

        if target is None or target < 0 or target >= self.count():
            self._overlay.hide()
            self._transitioning = False
            self.transition_finished.emit()
            return

        super().setCurrentIndex(target)
        self.view_switched.emit()

        self._fade_anim = QPropertyAnimation(self._overlay, b"opacity", self)
        self._fade_anim.setDuration(self._fade_in_ms)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.finished.connect(self._on_fade_in_done)
        self._fade_anim.start()

    def _on_fade_in_done(self):
        """Phase 3: Overlay verstecken, Aufraeuemen."""
        self._overlay.hide()
        self._overlay.set_opacity(0.0)
        self._fade_anim = None
        self._transitioning = False
        self.transition_finished.emit()

    def _abort_transition(self):
        """Bricht eine laufende Transition sauber ab."""
        if self._fade_anim is not None:
            self._fade_anim.stop()
            try:
                self._fade_anim.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._fade_anim = None
        self._overlay.hide()
        self._overlay.set_opacity(0.0)
        self._pending_index = None
        self._transitioning = False
