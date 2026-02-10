# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Toast-Benachrichtigungssystem

Zentrales, nicht-blockierendes Benachrichtigungssystem.
Ersetzt alle modalen QMessageBox-Dialoge fuer Info/Erfolg/Warnung/Fehler.

Verwendung:
    toast_manager = ToastManager(parent_widget)
    toast_manager.show_success("Einstellungen gespeichert")
    toast_manager.show_error("Verbindung fehlgeschlagen", action_text="Erneut", action_callback=retry)
    toast_manager.show_warning("Dokument bereits vorhanden")
    toast_manager.show_info("3 Dateien hochgeladen", action_text="Rueckgaengig", action_callback=undo)

REGELN (siehe docs/ui/UX_RULES.md):
    - KEINE modalen Dialoge fuer Info/Erfolg/Warnung/nicht-kritische Fehler
    - Toasts erscheinen oben rechts, gestapelt
    - Hover pausiert Auto-Dismiss
    - Optionaler Action-Button (Undo, Retry etc.)
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect, QProgressBar
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal, QPoint
from PySide6.QtGui import QFont

from ui.styles.tokens import (
    SUCCESS, SUCCESS_LIGHT,
    ERROR, ERROR_LIGHT,
    WARNING, WARNING_LIGHT,
    INFO, INFO_LIGHT,
    TEXT_PRIMARY, TEXT_INVERSE,
    FONT_BODY, FONT_SIZE_BODY,
    RADIUS_MD, SHADOW_MD,
)
from i18n import de as texts


# =============================================================================
# TOAST-KONFIGURATION
# =============================================================================

TOAST_WIDTH = 400
TOAST_MIN_HEIGHT = 52
TOAST_MARGIN_TOP = 16
TOAST_MARGIN_RIGHT = 16
TOAST_SPACING = 8

# Dauer in Millisekunden
DURATION_SUCCESS = 4000
DURATION_ERROR = 8000
DURATION_WARNING = 6000
DURATION_INFO = 5000

# Animation
SLIDE_IN_DURATION = 300
FADE_OUT_DURATION = 250

# Toast-Typen mit Styling
TOAST_STYLES = {
    "success": {
        "bg": SUCCESS,
        "bg_light": SUCCESS_LIGHT,
        "border": SUCCESS,
        "icon": "\u2714",  # ✔
        "text_color": TEXT_INVERSE,
        "duration": DURATION_SUCCESS,
    },
    "error": {
        "bg": ERROR,
        "bg_light": ERROR_LIGHT,
        "border": ERROR,
        "icon": "\u2716",  # ✖
        "text_color": TEXT_INVERSE,
        "duration": DURATION_ERROR,
    },
    "warning": {
        "bg": WARNING,
        "bg_light": WARNING_LIGHT,
        "border": WARNING,
        "icon": "\u26a0",  # ⚠
        "text_color": TEXT_INVERSE,
        "duration": DURATION_WARNING,
    },
    "info": {
        "bg": INFO,
        "bg_light": INFO_LIGHT,
        "border": INFO,
        "icon": "\u2139",  # ℹ
        "text_color": TEXT_INVERSE,
        "duration": DURATION_INFO,
    },
}


# =============================================================================
# TOAST WIDGET
# =============================================================================

class ToastWidget(QFrame):
    """
    Einzelne Toast-Benachrichtigung.
    
    Nicht direkt verwenden - wird von ToastManager erstellt.
    """
    
    closed = Signal(object)  # Emitted when toast is dismissed (sends self)
    
    def __init__(self, toast_type: str, message: str, 
                 action_text: str = None, action_callback: callable = None,
                 duration_ms: int = None, parent=None):
        super().__init__(parent)
        
        self._toast_type = toast_type
        self._action_callback = action_callback
        self._hover_paused = False
        self._is_closing = False
        
        style = TOAST_STYLES.get(toast_type, TOAST_STYLES["info"])
        
        # Duration
        self._duration_ms = duration_ms or style["duration"]
        
        # Frame konfigurieren
        self.setObjectName("toastWidget")
        self.setFixedWidth(TOAST_WIDTH)
        self.setMinimumHeight(TOAST_MIN_HEIGHT)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # Styling
        bg_color = style["bg"]
        text_color = style["text_color"]
        
        self.setStyleSheet(f"""
            QFrame#toastWidget {{
                background-color: {bg_color};
                border-radius: 8px;
                border: none;
            }}
        """)
        
        # Shadow via Drop-Shadow wuerde QGraphicsDropShadowEffect brauchen
        # Stattdessen nutzen wir einen dezenten Border
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        
        # Icon
        icon_label = QLabel(style["icon"])
        icon_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        icon_label.setFixedWidth(22)
        layout.addWidget(icon_label)
        
        # Text
        self._text_label = QLabel(message)
        self._text_label.setWordWrap(True)
        self._text_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-family: {FONT_BODY};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self._text_label, 1)
        
        # Action-Button (optional)
        if action_text and action_callback:
            self._action_btn = QPushButton(action_text)
            self._action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(255, 255, 255, 0.2);
                    color: {text_color};
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    font-family: {FONT_BODY};
                    font-size: 12px;
                    font-weight: 600;
                    padding: 4px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: rgba(255, 255, 255, 0.35);
                }}
            """)
            self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._action_btn.clicked.connect(self._on_action_clicked)
            layout.addWidget(self._action_btn)
        
        # Schliessen-Button (X)
        close_btn = QPushButton("\u2715")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: rgba(255, 255, 255, 0.6);
                border: none;
                font-size: 14px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                color: {text_color};
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
            }}
        """)
        close_btn.setFixedWidth(24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn)
        
        # Opacity fuer Fade-Out
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        
        # Auto-Dismiss Timer
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._fade_out)
        
    def start_dismiss_timer(self):
        """Startet den Auto-Dismiss-Timer."""
        self._dismiss_timer.start(self._duration_ms)
    
    def _on_action_clicked(self):
        """Action-Button geklickt."""
        if self._action_callback:
            try:
                self._action_callback()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Toast-Action fehlgeschlagen: {e}")
        self._dismiss()
    
    def _fade_out(self):
        """Fade-Out-Animation starten."""
        if self._is_closing:
            return
        self._is_closing = True
        
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(FADE_OUT_DURATION)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(self._on_fade_finished)
        self._fade_anim.start()
    
    def _on_fade_finished(self):
        """Nach Fade-Out: Toast entfernen."""
        self.closed.emit(self)
        self.deleteLater()
    
    def _dismiss(self):
        """Toast sofort schliessen (mit Fade)."""
        self._dismiss_timer.stop()
        self._fade_out()
    
    def enterEvent(self, event):
        """Hover: Timer pausieren."""
        super().enterEvent(event)
        if self._dismiss_timer.isActive():
            self._remaining_time = self._dismiss_timer.remainingTime()
            self._dismiss_timer.stop()
            self._hover_paused = True
    
    def leaveEvent(self, event):
        """Hover Ende: Timer fortsetzen."""
        super().leaveEvent(event)
        if self._hover_paused and not self._is_closing:
            remaining = getattr(self, '_remaining_time', self._duration_ms)
            self._dismiss_timer.start(max(remaining, 1000))
            self._hover_paused = False


# =============================================================================
# PROGRESS TOAST WIDGET
# =============================================================================

class ProgressToastWidget(QFrame):
    """
    Toast mit Fortschrittsbalken fuer lang laufende Operationen.
    
    Schliesst sich NICHT automatisch - muss manuell via dismiss() geschlossen werden.
    Nicht direkt verwenden - wird von ToastManager.show_progress() erstellt.
    """
    
    closed = Signal(object)  # Emitted when toast is dismissed (sends self)
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        
        self._is_closing = False
        
        # Frame konfigurieren
        self.setObjectName("progressToastWidget")
        self.setFixedWidth(TOAST_WIDTH)
        self.setMinimumHeight(TOAST_MIN_HEIGHT)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        
        bg_color = INFO
        text_color = TEXT_INVERSE
        
        self.setStyleSheet(f"""
            QFrame#progressToastWidget {{
                background-color: {bg_color};
                border-radius: 8px;
                border: none;
            }}
        """)
        
        # Haupt-Layout (vertikal: Text + Progress)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(6)
        
        # Obere Zeile: Icon + Text + X
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        
        icon_label = QLabel("\u2709")  # Briefumschlag
        icon_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        icon_label.setFixedWidth(22)
        top_row.addWidget(icon_label)
        
        self._text_label = QLabel(title)
        self._text_label.setWordWrap(True)
        self._text_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-family: {FONT_BODY};
                font-size: 13px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        top_row.addWidget(self._text_label, 1)
        
        outer.addLayout(top_row)
        
        # Status-Text (detail)
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.85);
                font-family: {FONT_BODY};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)
        outer.addWidget(self._status_label)
        
        # Progress Bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: rgba(255, 255, 255, 0.85);
                border-radius: 3px;
            }}
        """)
        outer.addWidget(self._progress_bar)
        
        # Opacity fuer Fade-Out
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
    
    def start_dismiss_timer(self):
        """Progress-Toasts haben keinen Auto-Dismiss-Timer."""
        pass
    
    def set_status(self, text: str):
        """Status-Text unter dem Titel aktualisieren."""
        self._status_label.setText(text)
    
    def set_progress(self, current: int, total: int):
        """Fortschritt aktualisieren (0 bis total)."""
        if total > 0:
            pct = int((current / total) * 100)
            self._progress_bar.setValue(min(pct, 100))
        else:
            self._progress_bar.setValue(0)
    
    def set_title(self, text: str):
        """Titel aktualisieren."""
        self._text_label.setText(text)
    
    def dismiss(self):
        """Toast manuell schliessen (mit Fade-Out)."""
        self._fade_out()
    
    def _fade_out(self):
        """Fade-Out-Animation starten."""
        if self._is_closing:
            return
        self._is_closing = True
        
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(FADE_OUT_DURATION)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(self._on_fade_finished)
        self._fade_anim.start()
    
    def _on_fade_finished(self):
        """Nach Fade-Out: Toast entfernen."""
        self.closed.emit(self)
        self.deleteLater()


# =============================================================================
# TOAST MANAGER
# =============================================================================

class ToastManager:
    """
    Zentraler Toast-Manager fuer ein Hauptfenster.
    
    Verwaltet alle aktiven Toasts, positioniert sie gestapelt oben rechts,
    und raeumt geschlossene Toasts auf.
    
    Verwendung:
        self._toast_manager = ToastManager(self)  # In MainHub.__init__
        self._toast_manager.show_success("Gespeichert")
        self._toast_manager.show_error("Fehlgeschlagen", action_text="Erneut", action_callback=fn)
    """
    
    def __init__(self, parent_widget):
        """
        Args:
            parent_widget: Das Hauptfenster (QWidget), in dem Toasts angezeigt werden.
        """
        self._parent = parent_widget
        self._active_toasts: list[ToastWidget] = []
    
    def show_success(self, message: str, action_text: str = None,
                     action_callback: callable = None, duration_ms: int = None):
        """Erfolgs-Toast (gruen) anzeigen."""
        self._show("success", message, action_text, action_callback, duration_ms)
    
    def show_error(self, message: str, action_text: str = None,
                   action_callback: callable = None, duration_ms: int = None):
        """Fehler-Toast (rot) anzeigen."""
        self._show("error", message, action_text, action_callback, duration_ms)
    
    def show_warning(self, message: str, action_text: str = None,
                     action_callback: callable = None, duration_ms: int = None):
        """Warn-Toast (orange) anzeigen."""
        self._show("warning", message, action_text, action_callback, duration_ms)
    
    def show_info(self, message: str, action_text: str = None,
                  action_callback: callable = None, duration_ms: int = None):
        """Info-Toast (blau) anzeigen."""
        self._show("info", message, action_text, action_callback, duration_ms)
    
    def show_progress(self, title: str) -> ProgressToastWidget:
        """
        Erstellt einen Progress-Toast mit Fortschrittsbalken.
        
        Schliesst sich NICHT automatisch - Aufrufer muss dismiss() aufrufen.
        
        Returns:
            ProgressToastWidget mit set_status(), set_progress(), dismiss()
        """
        toast = ProgressToastWidget(title=title, parent=self._parent)
        toast.closed.connect(self._on_toast_closed)
        
        self._active_toasts.append(toast)
        self._reposition_all()
        
        toast.setVisible(True)
        toast.raise_()
        return toast
    
    def _show(self, toast_type: str, message: str,
              action_text: str = None, action_callback: callable = None,
              duration_ms: int = None):
        """Erstellt und zeigt einen Toast."""
        toast = ToastWidget(
            toast_type=toast_type,
            message=message,
            action_text=action_text,
            action_callback=action_callback,
            duration_ms=duration_ms,
            parent=self._parent,
        )
        toast.closed.connect(self._on_toast_closed)
        
        self._active_toasts.append(toast)
        self._reposition_all()
        
        toast.setVisible(True)
        toast.raise_()
        toast.start_dismiss_timer()
    
    def _on_toast_closed(self, toast: ToastWidget):
        """Callback wenn ein Toast geschlossen wird."""
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)
        self._reposition_all()
    
    def _reposition_all(self):
        """Alle aktiven Toasts oben rechts gestapelt positionieren."""
        if not self._parent:
            return
        
        parent_rect = self._parent.rect()
        x = parent_rect.width() - TOAST_WIDTH - TOAST_MARGIN_RIGHT
        y = TOAST_MARGIN_TOP
        
        for toast in self._active_toasts:
            toast.move(x, y)
            toast.adjustSize()
            y += toast.height() + TOAST_SPACING
    
    def clear_all(self):
        """Alle aktiven Toasts sofort entfernen."""
        for toast in list(self._active_toasts):
            # ProgressToastWidget hat keinen _dismiss_timer (BUG-0001 Fix)
            if hasattr(toast, '_dismiss_timer'):
                toast._dismiss_timer.stop()
            toast.setVisible(False)
            toast.deleteLater()
        self._active_toasts.clear()
    
    def reposition(self):
        """
        Toasts neu positionieren (z.B. nach Fenster-Resize aufrufen).
        """
        self._reposition_all()
