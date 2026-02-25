"""
Mitteilungszentrale - Dashboard View

Zeigt vier Kacheln:
1a. System- & Admin-Mitteilungen (links oben)
1b. Handlungsaufforderungen - Aus BiPRO (rechts oben)
2. Aktuelles Release (links unten)
3. Nachrichten / Chats (rechts unten)
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


class LoadBiproEventsWorker(QThread):
    """Laedt BiPRO-Events im Hintergrund."""
    finished = Signal(list)

    def __init__(self, bipro_events_api, parent=None):
        super().__init__(parent)
        self._api = bipro_events_api

    def run(self):
        try:
            result = self._api.get_events(page=1, per_page=200)
            self.finished.emit(result.get('data', []))
        except Exception:
            self.finished.emit([])


class MarkBiproEventReadWorker(QThread):
    """Markiert BiPRO-Events als gelesen im Hintergrund."""
    finished = Signal(bool, int)  # success, updated_count
    error = Signal(str)

    def __init__(self, bipro_events_api, event_ids: list, mark_all: bool = False, parent=None):
        super().__init__(parent)
        self._api = bipro_events_api
        self._event_ids = event_ids
        self._mark_all = mark_all

    def run(self):
        try:
            if self._mark_all:
                updated = self._api.mark_all_read() or 0
            else:
                result = self._api.mark_as_read(self._event_ids)
                updated = result.get('updated', len(self._event_ids)) if isinstance(result, dict) else len(self._event_ids)
            self.finished.emit(True, updated)
        except Exception as e:
            self.error.emit(str(e))


# ============================================================================
# Event-Type Farben + Labels
# ============================================================================

EVENT_TYPE_COLORS = {
    'gdv_announced': ('#d97706', '#fffbeb'),
    'contract_xml': (INFO, INFO_LIGHT),
    'status_message': ('#6b7280', '#f9fafb'),
    'document_xml': ('#8b5cf6', '#f5f3ff'),
}


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
# BiPRO Event Card Widget
# ============================================================================

class BiproEventCard(QFrame):
    """Einzelner BiPRO-Event als Card mit Metadaten."""
    mark_read = Signal(int)

    def __init__(self, event, parent=None):
        super().__init__(parent)
        self._event = event
        self._setup_ui(event)

    def _setup_ui(self, ev):
        et = getattr(ev, 'event_type', '') if hasattr(ev, 'event_type') else ev.get('event_type', '')
        is_read = getattr(ev, 'is_read', False) if hasattr(ev, 'is_read') else ev.get('is_read', False)
        fg_color, bg_color = EVENT_TYPE_COLORS.get(et, EVENT_TYPE_COLORS['document_xml'])

        self.setStyleSheet(f"""
            BiproEventCard {{
                background-color: {bg_color if not is_read else BG_TERTIARY};
                border: 1px solid {BORDER_DEFAULT};
                border-left: 4px solid {fg_color};
                border-radius: {RADIUS_MD};
                padding: {SPACING_SM};
                margin-bottom: 4px;
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        top_row = QHBoxLayout()

        type_label_text = texts.BIPRO_EVENT_TYPE_LABELS.get(et, et)
        badge = QLabel(type_label_text)
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

        vu_name = _ev_get(ev, 'vu_name', '')
        kurz = _ev_get(ev, 'kurzbeschreibung', '') or _ev_get(ev, 'freitext', '')
        title_text = f"{vu_name}" + (f" — {kurz}" if kurz else '')
        title = QLabel(title_text)
        fw = FONT_WEIGHT_BOLD if not is_read else FONT_WEIGHT_MEDIUM
        title.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_BODY};
                font-weight: {fw};
                background: transparent; border: none;
            }}
        """)
        title.setWordWrap(True)
        top_row.addWidget(title, 1)

        if not is_read:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {ACCENT_500}; font-size: 10px; background: transparent; border: none;")
            top_row.addWidget(dot)

        layout.addLayout(top_row)

        meta_parts = []
        vsnr = _ev_get(ev, 'vsnr', '')
        sparte = _ev_get(ev, 'sparte', '')
        if vsnr:
            meta_parts.append(f"{texts.BIPRO_EVENT_VSNR}: {vsnr}")
        if sparte:
            meta_parts.append(f"{texts.BIPRO_EVENT_SPARTE}: {sparte}")

        created = _ev_get(ev, 'created_at', '')
        try:
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            meta_parts.append(dt.strftime('%d.%m.%Y %H:%M'))
        except (ValueError, AttributeError):
            if created:
                meta_parts.append(created)

        if meta_parts:
            meta_label = QLabel('  |  '.join(meta_parts))
            meta_label.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_SECONDARY};
                    font-size: {FONT_SIZE_CAPTION};
                    background: transparent; border: none;
                }}
            """)
            layout.addWidget(meta_label)

        vn_name = _ev_get(ev, 'vn_name', '')
        if vn_name:
            vn_label = QLabel(vn_name)
            vn_label.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_SECONDARY};
                    font-size: {FONT_SIZE_CAPTION};
                    font-style: italic;
                    background: transparent; border: none;
                }}
            """)
            layout.addWidget(vn_label)

        ref_file = _ev_get(ev, 'referenced_filename', '')
        if ref_file:
            known_ext = any(ref_file.lower().endswith(ext)
                           for ext in ('.pdf', '.gdv', '.csv', '.xlsx', '.zip', '.txt'))
            if known_ext:
                file_label = QLabel(f"\U0001F4CE {ref_file}")
                file_label.setStyleSheet(f"""
                    QLabel {{
                        color: {TEXT_SECONDARY};
                        font-size: {FONT_SIZE_CAPTION};
                        font-style: italic;
                        background: transparent; border: none;
                    }}
                """)
                layout.addWidget(file_label)

    def mousePressEvent(self, event):
        ev_id = _ev_get(self._event, 'id', 0)
        if ev_id:
            self.mark_read.emit(int(ev_id))
        super().mousePressEvent(event)


def _ev_get(ev, key, default=''):
    """Zugriff auf BiproEvent (Dataclass oder Dict)."""
    if hasattr(ev, key):
        return getattr(ev, key) or default
    if isinstance(ev, dict):
        return ev.get(key) or default
    return default


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
        self._bipro_events_api = None
        self._toast_manager = None
        self._messages: List[Dict] = []
        self._releases: List[Dict] = []
        self._bipro_events = []
        self._show_all_releases = False
        self._load_worker = None
        self._releases_worker = None
        self._bipro_events_worker = None
        self._mark_read_worker = None
        
        self._setup_ui()
    
    def set_messages_api(self, messages_api):
        """Setzt die Messages API (lazy, nach Login)."""
        self._messages_api = messages_api
    
    def set_releases_api(self, releases_api):
        """Setzt die Releases API."""
        self._releases_api = releases_api

    def set_bipro_events_api(self, bipro_events_api):
        """Setzt die BiPRO-Events API (lazy, nach Login)."""
        self._bipro_events_api = bipro_events_api
    
    def refresh(self):
        """Laedt Mitteilungen, Releases und BiPRO-Events neu."""
        self._load_messages()
        self._load_releases()
        self._load_bipro_events()
    
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
        
        # --- Obere Reihe: System-Mitteilungen + BiPRO-Events ---
        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        self._messages_card = self._create_messages_card()
        top_row.addWidget(self._messages_card, 1)
        self._bipro_events_card = self._create_bipro_events_card()
        top_row.addWidget(self._bipro_events_card, 1)
        self._content_layout.addLayout(top_row)

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
        layout.addLayout(header_row)
        
        msg_scroll = QScrollArea()
        msg_scroll.setWidgetResizable(True)
        msg_scroll.setFrameShape(QFrame.Shape.NoFrame)
        msg_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        msg_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                width: 6px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_DEFAULT};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self._messages_container = QVBoxLayout(scroll_widget)
        self._messages_container.setContentsMargins(0, 0, 0, 0)
        self._messages_container.setSpacing(4)
        
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

        msg_scroll.setWidget(scroll_widget)
        layout.addWidget(msg_scroll, 1)
        
        return card
    
    def _populate_messages(self):
        """Fuellt die Mitteilungs-Kachel mit Daten."""
        while self._messages_container.count():
            item = self._messages_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self._messages:
            label = QLabel(texts.MSG_CENTER_NO_MESSAGES)
            label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY}; padding: 16px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._messages_container.addWidget(label)
            return
        
        for msg in self._messages:
            card = MessageCard(msg)
            self._messages_container.addWidget(card)
    
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
    # Kachel: Handlungsaufforderungen - Aus BiPRO
    # ====================================================================

    def _create_bipro_events_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("biproEventsCard")
        card.setStyleSheet(f"""
            QFrame#biproEventsCard {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_LG};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        title = QLabel(texts.BIPRO_EVENT_TITLE)
        title.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_H2};
                font-weight: {FONT_WEIGHT_BOLD};
            }}
        """)
        header_row.addWidget(title)

        self._bipro_event_badge = QLabel("")
        self._bipro_event_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {ACCENT_500};
                color: {TEXT_INVERSE};
                border-radius: 9px;
                padding: 1px 6px;
                font-size: {FONT_SIZE_CAPTION};
                font-weight: {FONT_WEIGHT_BOLD};
                min-width: 18px;
            }}
        """)
        self._bipro_event_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bipro_event_badge.setFixedHeight(18)
        self._bipro_event_badge.setVisible(False)
        header_row.addWidget(self._bipro_event_badge)

        header_row.addStretch()

        self._mark_all_read_btn = QPushButton(texts.BIPRO_EVENT_MARK_ALL_READ)
        self._mark_all_read_btn.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_SECONDARY};
                background: transparent;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 4px;
                padding: 3px 10px;
                font-size: {FONT_SIZE_CAPTION};
            }}
            QPushButton:hover {{
                background-color: {BG_SECONDARY};
                color: {TEXT_PRIMARY};
            }}
        """)
        self._mark_all_read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mark_all_read_btn.setVisible(False)
        self._mark_all_read_btn.clicked.connect(self._mark_all_bipro_events_read)
        header_row.addWidget(self._mark_all_read_btn)

        layout.addLayout(header_row)

        subtitle = QLabel(texts.BIPRO_EVENT_SUBTITLE)
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_CAPTION};
            }}
        """)
        layout.addWidget(subtitle)

        bipro_scroll = QScrollArea()
        bipro_scroll.setWidgetResizable(True)
        bipro_scroll.setFrameShape(QFrame.Shape.NoFrame)
        bipro_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bipro_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                width: 6px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_DEFAULT};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self._bipro_events_container = QVBoxLayout(scroll_widget)
        self._bipro_events_container.setContentsMargins(0, 0, 0, 0)
        self._bipro_events_container.setSpacing(4)

        self._bipro_status_label = QLabel(texts.BIPRO_EVENT_NO_EVENTS)
        self._bipro_status_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_BODY};
                padding: 16px;
            }}
        """)
        self._bipro_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bipro_events_container.addWidget(self._bipro_status_label)

        bipro_scroll.setWidget(scroll_widget)
        layout.addWidget(bipro_scroll, 1)

        return card

    def _populate_bipro_events(self):
        """Fuellt die BiPRO-Events-Kachel mit Daten."""
        while self._bipro_events_container.count():
            item = self._bipro_events_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._bipro_events:
            label = QLabel(texts.BIPRO_EVENT_NO_EVENTS)
            label.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY}; padding: 16px;"
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._bipro_events_container.addWidget(label)
            self._bipro_event_badge.setVisible(False)
            self._mark_all_read_btn.setVisible(False)
            return

        for ev in self._bipro_events:
            card = BiproEventCard(ev)
            card.mark_read.connect(self._on_bipro_event_clicked)
            self._bipro_events_container.addWidget(card)

        unread = sum(1 for e in self._bipro_events if not _ev_get(e, 'is_read', False))
        if unread > 0:
            self._bipro_event_badge.setText(str(unread))
            self._bipro_event_badge.setVisible(True)
            self._mark_all_read_btn.setVisible(True)
        else:
            self._bipro_event_badge.setVisible(False)
            self._mark_all_read_btn.setVisible(False)

    @Slot(int)
    def _on_bipro_event_clicked(self, event_id: int):
        """Markiert einen BiPRO-Event als gelesen (async via Worker)."""
        if not self._bipro_events_api:
            return
        if self._mark_read_worker and self._mark_read_worker.isRunning():
            return

        for ev in self._bipro_events:
            if _ev_get(ev, 'id', 0) == event_id:
                if hasattr(ev, 'is_read'):
                    ev.is_read = True
                elif isinstance(ev, dict):
                    ev['is_read'] = True
        self._populate_bipro_events()

        self._mark_read_worker = MarkBiproEventReadWorker(
            self._bipro_events_api, [event_id], mark_all=False, parent=self
        )
        self._mark_read_worker.error.connect(
            lambda msg: logger.warning(f"mark_as_read fehlgeschlagen: {msg}")
        )
        self._mark_read_worker.start()

    def _mark_all_bipro_events_read(self):
        """Markiert alle BiPRO-Events als gelesen (async via Worker)."""
        if not self._bipro_events_api:
            return
        if self._mark_read_worker and self._mark_read_worker.isRunning():
            return

        unread = sum(1 for e in self._bipro_events if not _ev_get(e, 'is_read', False))
        if unread == 0:
            if self._toast_manager:
                self._toast_manager.show_info(texts.BIPRO_EVENT_MARK_ALL_READ_NONE)
            return

        for ev in self._bipro_events:
            if hasattr(ev, 'is_read'):
                ev.is_read = True
            elif isinstance(ev, dict):
                ev['is_read'] = True
        self._populate_bipro_events()

        self._mark_read_worker = MarkBiproEventReadWorker(
            self._bipro_events_api, [], mark_all=True, parent=self
        )
        self._mark_read_worker.finished.connect(self._on_mark_all_read_finished)
        self._mark_read_worker.error.connect(
            lambda msg: logger.warning(f"Alle als gelesen markieren fehlgeschlagen: {msg}")
        )
        self._mark_read_worker.start()

    @Slot(bool, int)
    def _on_mark_all_read_finished(self, success: bool, updated: int):
        """Callback nach erfolgreichem Markieren aller Events als gelesen."""
        if success and self._toast_manager:
            self._toast_manager.show_success(
                texts.BIPRO_EVENT_MARK_ALL_READ_SUCCESS.format(count=updated)
            )

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

    def _load_bipro_events(self):
        if not self._bipro_events_api:
            return
        if self._bipro_events_worker and self._bipro_events_worker.isRunning():
            return
        self._bipro_events_worker = LoadBiproEventsWorker(self._bipro_events_api, self)
        self._bipro_events_worker.finished.connect(self._on_bipro_events_loaded)
        self._bipro_events_worker.start()

    @Slot(list)
    def _on_bipro_events_loaded(self, events: list):
        self._bipro_events = events
        self._populate_bipro_events()
