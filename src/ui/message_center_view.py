"""
Mitteilungszentrale - Dashboard View

Zeigt drei Kacheln:
1. System- & Admin-Mitteilungen (grosse Kachel)
2. Aktuelles Release (kleine Kachel)
3. Nachrichten / Chats (kleine Kachel mit Button)
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QFont

from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_INVERSE,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY,
    BORDER_DEFAULT,
    SUCCESS, SUCCESS_LIGHT, WARNING, WARNING_LIGHT,
    ERROR, ERROR_LIGHT, INFO, INFO_LIGHT,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    FONT_WEIGHT_BOLD, FONT_WEIGHT_MEDIUM,
    SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    RADIUS_MD, RADIUS_LG, SHADOW_MD,
    get_button_primary_style, get_button_secondary_style,
)

logger = logging.getLogger(__name__)

# Severity → Farben
SEVERITY_COLORS = {
    'info': (INFO, INFO_LIGHT),
    'warning': (WARNING, WARNING_LIGHT),
    'error': (ERROR, ERROR_LIGHT),
    'critical': ('#7c2d12', '#fef2f2'),
}

SEVERITY_LABELS = {
    'info': texts.MSG_CENTER_SEVERITY_INFO,
    'warning': texts.MSG_CENTER_SEVERITY_WARNING,
    'error': texts.MSG_CENTER_SEVERITY_ERROR,
    'critical': texts.MSG_CENTER_SEVERITY_CRITICAL,
}


# ============================================================================
# Worker: Mitteilungen laden
# ============================================================================

class LoadMessagesWorker(QThread):
    """Laedt Mitteilungen im Hintergrund."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, messages_api, parent=None):
        super().__init__(parent)
        self._api = messages_api
    
    def run(self):
        try:
            result = self._api.get_messages(page=1, per_page=50)
            messages = result.get('data', [])
            self.finished.emit(messages)
        except Exception as e:
            self.error.emit(str(e))


class LoadReleasesWorker(QThread):
    """Laedt Releases im Hintergrund."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, releases_api, parent=None):
        super().__init__(parent)
        self._api = releases_api
    
    def run(self):
        try:
            releases = self._api.get_public_releases()
            self.finished.emit(releases)
        except Exception:
            self.finished.emit([])


# ============================================================================
# Message Card Widget
# ============================================================================

class MessageCard(QFrame):
    """Einzelne Mitteilung als Card."""
    
    def __init__(self, message: Dict, parent=None):
        super().__init__(parent)
        self._setup_ui(message)
    
    def _setup_ui(self, msg: Dict):
        severity = msg.get('severity', 'info')
        fg_color, bg_color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS['info'])
        is_read = msg.get('is_read', False)
        
        self.setStyleSheet(f"""
            MessageCard {{
                background-color: {bg_color if not is_read else BG_TERTIARY};
                border: 1px solid {BORDER_DEFAULT};
                border-left: 4px solid {fg_color};
                border-radius: {RADIUS_MD};
                padding: {SPACING_SM};
                margin-bottom: 4px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        # Zeile 1: Severity-Badge + Titel
        top_row = QHBoxLayout()
        
        badge = QLabel(SEVERITY_LABELS.get(severity, severity))
        badge.setStyleSheet(f"""
            QLabel {{
                background-color: {fg_color};
                color: {TEXT_INVERSE};
                border-radius: 3px;
                padding: 1px 6px;
                font-size: {FONT_SIZE_CAPTION};
                font-weight: {FONT_WEIGHT_BOLD};
            }}
        """)
        badge.setFixedHeight(18)
        top_row.addWidget(badge)
        
        title = QLabel(msg.get('title', ''))
        title.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_BODY};
                font-weight: {FONT_WEIGHT_BOLD};
                background: transparent;
                border: none;
            }}
        """)
        title.setWordWrap(True)
        top_row.addWidget(title, 1)
        layout.addLayout(top_row)
        
        # Zeile 2: Beschreibung (optional)
        desc = msg.get('description', '')
        if desc:
            desc_label = QLabel(desc)
            desc_label.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_SECONDARY};
                    font-size: {FONT_SIZE_CAPTION};
                    background: transparent;
                    border: none;
                }}
            """)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Zeile 3: Meta (Sender + Datum)
        meta_row = QHBoxLayout()
        
        sender = msg.get('sender_name', '')
        created = msg.get('created_at', '')
        try:
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            date_str = dt.strftime('%d.%m.%Y %H:%M')
        except (ValueError, AttributeError):
            date_str = created
        
        meta_text = texts.MSG_CENTER_FROM.format(sender=sender) + f"  ·  {date_str}"
        meta = QLabel(meta_text)
        meta.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_CAPTION};
                background: transparent;
                border: none;
            }}
        """)
        meta_row.addWidget(meta)
        meta_row.addStretch()
        layout.addLayout(meta_row)


# ============================================================================
# MessageCenterView - Haupt-Dashboard
# ============================================================================

class MessageCenterView(QWidget):
    """
    Mitteilungszentrale Dashboard.
    
    Signals:
        open_chats_requested: Emitted wenn 'Chats oeffnen' geklickt wird
    """
    open_chats_requested = Signal()
    
    def __init__(self, api_client, releases_api=None, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._releases_api = releases_api
        self._messages_api = None
        self._toast_manager = None
        self._messages: List[Dict] = []
        self._releases: List[Dict] = []
        self._show_all_messages = False
        self._show_all_releases = False
        self._load_worker = None
        self._releases_worker = None
        
        self._setup_ui()
    
    def set_messages_api(self, messages_api):
        """Setzt die Messages API (lazy, nach Login)."""
        self._messages_api = messages_api
    
    def set_releases_api(self, releases_api):
        """Setzt die Releases API."""
        self._releases_api = releases_api
    
    def refresh(self):
        """Laedt Mitteilungen und Releases neu."""
        self._load_messages()
        self._load_releases()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)
        
        # === Header ===
        header = QLabel(texts.MSG_CENTER_TITLE)
        header.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-family: {FONT_HEADLINE};
                font-size: {FONT_SIZE_H1};
                font-weight: {FONT_WEIGHT_BOLD};
            }}
        """)
        main_layout.addWidget(header)
        
        # === Scroll Area fuer Kacheln ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {BG_PRIMARY}; border: none;")
        
        scroll_content = QWidget()
        self._content_layout = QVBoxLayout(scroll_content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)
        
        # --- Kachel 1: System & Admin Mitteilungen (gross) ---
        self._messages_card = self._create_messages_card()
        self._content_layout.addWidget(self._messages_card)
        
        # --- Untere Reihe: Release + Nachrichten ---
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)
        
        self._release_card = self._create_release_card()
        bottom_row.addWidget(self._release_card, 1)
        
        self._chats_card = self._create_chats_card()
        bottom_row.addWidget(self._chats_card, 1)
        
        self._content_layout.addLayout(bottom_row)
        self._content_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)
    
    # ====================================================================
    # Kachel: System & Admin Mitteilungen
    # ====================================================================
    
    def _create_messages_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("messagesCard")
        card.setStyleSheet(f"""
            QFrame#messagesCard {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_LG};
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Header
        header_row = QHBoxLayout()
        title = QLabel(texts.MSG_CENTER_SYSTEM_ADMIN_TITLE)
        title.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_H2};
                font-weight: {FONT_WEIGHT_BOLD};
            }}
        """)
        header_row.addWidget(title)
        header_row.addStretch()
        
        self._msg_toggle_btn = QPushButton(texts.MSG_CENTER_SHOW_ALL)
        self._msg_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                color: {ACCENT_500};
                background: transparent;
                border: none;
                font-size: {FONT_SIZE_CAPTION};
                font-weight: {FONT_WEIGHT_MEDIUM};
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        self._msg_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._msg_toggle_btn.clicked.connect(self._toggle_show_all_messages)
        header_row.addWidget(self._msg_toggle_btn)
        layout.addLayout(header_row)
        
        # Messages Container
        self._messages_container = QVBoxLayout()
        self._messages_container.setSpacing(4)
        layout.addLayout(self._messages_container)
        
        # Loading / Empty Label
        self._msg_status_label = QLabel(texts.MSG_CENTER_LOADING)
        self._msg_status_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_BODY};
                padding: 16px;
            }}
        """)
        self._msg_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._messages_container.addWidget(self._msg_status_label)
        
        return card
    
    def _populate_messages(self):
        """Fuellt die Mitteilungs-Kachel mit Daten."""
        # Alte Widgets entfernen
        while self._messages_container.count():
            item = self._messages_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self._messages:
            label = QLabel(texts.MSG_CENTER_NO_MESSAGES)
            label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY}; padding: 16px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._messages_container.addWidget(label)
            self._msg_toggle_btn.setVisible(False)
            return
        
        # Anzeige: 3 oder alle
        count = len(self._messages) if self._show_all_messages else min(3, len(self._messages))
        for msg in self._messages[:count]:
            card = MessageCard(msg)
            self._messages_container.addWidget(card)
        
        self._msg_toggle_btn.setVisible(len(self._messages) > 3)
        self._msg_toggle_btn.setText(
            texts.MSG_CENTER_SHOW_LESS if self._show_all_messages else texts.MSG_CENTER_SHOW_ALL
        )
    
    def _toggle_show_all_messages(self):
        self._show_all_messages = not self._show_all_messages
        self._populate_messages()
    
    # ====================================================================
    # Kachel: Aktuelles Release
    # ====================================================================
    
    def _create_release_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("releaseCard")
        card.setStyleSheet(f"""
            QFrame#releaseCard {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_LG};
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Header
        title = QLabel(texts.MSG_CENTER_CURRENT_RELEASE)
        title.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_H3};
                font-weight: {FONT_WEIGHT_BOLD};
            }}
        """)
        layout.addWidget(title)
        
        # Release Content Container
        self._release_container = QVBoxLayout()
        self._release_container.setSpacing(4)
        layout.addLayout(self._release_container)
        
        self._release_status_label = QLabel(texts.MSG_CENTER_LOADING)
        self._release_status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};")
        self._release_container.addWidget(self._release_status_label)
        
        # "Alle Releases" Button
        self._release_toggle_btn = QPushButton(texts.MSG_CENTER_ALL_RELEASES)
        self._release_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                color: {ACCENT_500};
                background: transparent;
                border: none;
                font-size: {FONT_SIZE_CAPTION};
                font-weight: {FONT_WEIGHT_MEDIUM};
                padding: 4px 0px;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        self._release_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._release_toggle_btn.clicked.connect(self._toggle_show_all_releases)
        self._release_toggle_btn.setVisible(False)
        layout.addWidget(self._release_toggle_btn)
        
        layout.addStretch()
        return card
    
    def _populate_releases(self):
        """Fuellt die Release-Kachel mit Daten."""
        while self._release_container.count():
            item = self._release_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self._releases:
            label = QLabel(texts.MSG_CENTER_NO_RELEASES)
            label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};")
            self._release_container.addWidget(label)
            self._release_toggle_btn.setVisible(False)
            return
        
        # Aktuelles Release (oder alle)
        count = len(self._releases) if self._show_all_releases else 1
        for i, rel in enumerate(self._releases[:count]):
            version = rel.get('version', '?')
            notes = rel.get('release_notes', '')
            released = rel.get('released_at', '')
            status = rel.get('status', '')
            
            try:
                dt = datetime.fromisoformat(released.replace('Z', '+00:00'))
                date_str = dt.strftime('%d.%m.%Y')
            except (ValueError, AttributeError):
                date_str = released
            
            # Version Label
            ver_label = QLabel(f"v{version}" + (f"  ·  {date_str}" if date_str else ''))
            ver_label.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_PRIMARY};
                    font-size: {FONT_SIZE_BODY};
                    font-weight: {FONT_WEIGHT_BOLD};
                }}
            """)
            self._release_container.addWidget(ver_label)
            
            # Release Notes (gekuerzt)
            if notes:
                max_len = 500 if self._show_all_releases else 150
                display_notes = notes[:max_len] + ('...' if len(notes) > max_len else '')
                notes_label = QLabel(display_notes)
                notes_label.setStyleSheet(f"""
                    QLabel {{
                        color: {TEXT_SECONDARY};
                        font-size: {FONT_SIZE_CAPTION};
                    }}
                """)
                notes_label.setWordWrap(True)
                self._release_container.addWidget(notes_label)
            
            # Separator zwischen Releases
            if i < count - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet(f"color: {BORDER_DEFAULT};")
                self._release_container.addWidget(sep)
        
        self._release_toggle_btn.setVisible(len(self._releases) > 1)
        self._release_toggle_btn.setText(
            texts.MSG_CENTER_BACK_TO_OVERVIEW if self._show_all_releases else texts.MSG_CENTER_ALL_RELEASES
        )
    
    def _toggle_show_all_releases(self):
        self._show_all_releases = not self._show_all_releases
        self._populate_releases()
    
    # ====================================================================
    # Kachel: Nachrichten / Chats
    # ====================================================================
    
    def _create_chats_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("chatsCard")
        card.setStyleSheet(f"""
            QFrame#chatsCard {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_LG};
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Header
        title = QLabel(texts.MSG_CENTER_CHATS_TITLE)
        title.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_H3};
                font-weight: {FONT_WEIGHT_BOLD};
            }}
        """)
        layout.addWidget(title)
        
        # Unread-Info
        self._chat_info_label = QLabel(texts.MSG_CENTER_NO_UNREAD)
        self._chat_info_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_BODY};
            }}
        """)
        layout.addWidget(self._chat_info_label)
        
        layout.addStretch()
        
        # "Chats oeffnen" Button
        open_btn = QPushButton(texts.MSG_CENTER_OPEN_CHATS)
        open_btn.setStyleSheet(get_button_primary_style())
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self.open_chats_requested.emit)
        layout.addWidget(open_btn)
        
        return card
    
    def update_unread_count(self, unread_chats: int):
        """Aktualisiert die Unread-Anzeige in der Chat-Kachel."""
        if unread_chats > 0:
            self._chat_info_label.setText(
                texts.MSG_CENTER_UNREAD_CHATS.format(count=unread_chats)
            )
            self._chat_info_label.setStyleSheet(f"""
                QLabel {{
                    color: {ACCENT_500};
                    font-size: {FONT_SIZE_BODY};
                    font-weight: {FONT_WEIGHT_BOLD};
                }}
            """)
        else:
            self._chat_info_label.setText(texts.MSG_CENTER_NO_UNREAD)
            self._chat_info_label.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_SECONDARY};
                    font-size: {FONT_SIZE_BODY};
                }}
            """)
    
    # ====================================================================
    # Daten laden
    # ====================================================================
    
    def _load_messages(self):
        if not self._messages_api:
            return
        if self._load_worker and self._load_worker.isRunning():
            return
        
        self._load_worker = LoadMessagesWorker(self._messages_api, self)
        self._load_worker.finished.connect(self._on_messages_loaded)
        self._load_worker.error.connect(self._on_messages_error)
        self._load_worker.start()
    
    @Slot(list)
    def _on_messages_loaded(self, messages: list):
        self._messages = messages
        self._populate_messages()
        
        # Ungelesene als gelesen markieren
        unread_ids = [m['id'] for m in messages if not m.get('is_read', True)]
        if unread_ids and self._messages_api:
            try:
                self._messages_api.mark_as_read(unread_ids)
            except Exception:
                pass
    
    @Slot(str)
    def _on_messages_error(self, error: str):
        logger.error(f"Mitteilungen laden fehlgeschlagen: {error}")
    
    def _load_releases(self):
        if not self._releases_api:
            return
        if self._releases_worker and self._releases_worker.isRunning():
            return
        
        self._releases_worker = LoadReleasesWorker(self._releases_api, self)
        self._releases_worker.finished.connect(self._on_releases_loaded)
        self._releases_worker.error.connect(lambda e: None)
        self._releases_worker.start()
    
    @Slot(list)
    def _on_releases_loaded(self, releases: list):
        self._releases = releases
        self._populate_releases()
