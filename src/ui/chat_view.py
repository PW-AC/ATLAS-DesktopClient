"""
Chat-Vollbild-View (1:1 Nachrichten)

Wird angezeigt wenn 'Chats oeffnen' geklickt wird.
Hauptsidebar wird versteckt (wie bei Admin).

Layout:
- Links: Chat-Liste mit Conversations
- Rechts: Nachrichten-Verlauf + Eingabefeld
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFrame, QScrollArea, QSizePolicy, QSpacerItem, QListWidget,
    QListWidgetItem, QSplitter, QTextEdit, QDialog, QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal, QThread, Slot, QTimer
from PySide6.QtGui import QFont, QKeyEvent

from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_INVERSE, TEXT_DISABLED,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY,
    BORDER_DEFAULT, BORDER_FOCUS,
    SUCCESS, ERROR,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    FONT_WEIGHT_BOLD, FONT_WEIGHT_MEDIUM,
    SPACING_SM, SPACING_MD, SPACING_LG,
    RADIUS_MD, RADIUS_LG,
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER,
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Workers
# ============================================================================

class LoadConversationsWorker(QThread):
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, chat_api, parent=None):
        super().__init__(parent)
        self._api = chat_api
    
    def run(self):
        try:
            convs = self._api.get_conversations()
            self.finished.emit(convs)
        except Exception as e:
            self.error.emit(str(e))


class LoadChatMessagesWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, chat_api, conversation_id: int, parent=None):
        super().__init__(parent)
        self._api = chat_api
        self._conv_id = conversation_id
    
    def run(self):
        try:
            result = self._api.get_messages(self._conv_id, page=1, per_page=100)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ChatRefreshWorker(QThread):
    """Pollt aktiven Chat im Hintergrund (3s Intervall).
    
    Conversations werden nur alle 5 Zyklen (~15s) nachgeladen
    um API-Last zu reduzieren.
    """
    messages_updated = Signal(dict)       # Neue Nachrichten fuer aktuellen Chat
    conversations_updated = Signal(list)  # Aktualisierte Conversation-Liste
    
    def __init__(self, chat_api, conversation_id: int,
                 reload_conversations: bool = False,
                 mark_read: bool = False, parent=None):
        super().__init__(parent)
        self._api = chat_api
        self._conv_id = conversation_id
        self._reload_convs = reload_conversations
        self._mark_read = mark_read
    
    def run(self):
        try:
            # Nachrichten des aktuellen Chats laden (1 API-Call)
            if self._conv_id:
                result = self._api.get_messages(self._conv_id, page=1, per_page=100)
                self.messages_updated.emit(result)
                
                # Als gelesen markieren - nur wenn Flag gesetzt (1 API-Call)
                if self._mark_read:
                    try:
                        self._api.mark_as_read(self._conv_id)
                    except Exception:
                        pass
            
            # Conversations nur periodisch aktualisieren (1 API-Call, alle ~15s)
            if self._reload_convs:
                try:
                    convs = self._api.get_conversations()
                    self.conversations_updated.emit(convs)
                except Exception:
                    pass
        except Exception:
            pass  # Refresh-Fehler stillschweigend ignorieren


class SendMessageWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, chat_api, conversation_id: int, content: str, parent=None):
        super().__init__(parent)
        self._api = chat_api
        self._conv_id = conversation_id
        self._content = content
    
    def run(self):
        try:
            result = self._api.send_message(self._conv_id, self._content)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LoadUsersWorker(QThread):
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, chat_api, parent=None):
        super().__init__(parent)
        self._api = chat_api
    
    def run(self):
        try:
            users = self._api.get_available_users()
            self.finished.emit(users)
        except Exception as e:
            self.error.emit(str(e))


# ============================================================================
# Message Bubble Widget
# ============================================================================

class MessageBubble(QFrame):
    """Einzelne Chat-Nachricht als Bubble."""
    
    def __init__(self, msg: Dict, parent=None):
        super().__init__(parent)
        is_mine = msg.get('is_mine', False)
        self._setup_ui(msg, is_mine)
    
    def _setup_ui(self, msg: Dict, is_mine: bool):
        bg = ACCENT_100 if is_mine else BG_SECONDARY
        align = Qt.AlignmentFlag.AlignRight if is_mine else Qt.AlignmentFlag.AlignLeft
        
        self.setStyleSheet(f"""
            MessageBubble {{
                background-color: {bg};
                border-radius: {RADIUS_LG};
                padding: 8px 12px;
                margin: 2px {'4px 2px 48px' if is_mine else '48px 2px 4px'};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Content
        content = QLabel(msg.get('content', ''))
        content.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_BODY};
                background: transparent;
                border: none;
            }}
        """)
        content.setWordWrap(True)
        layout.addWidget(content)
        
        # Meta: Zeit + Lesestatus
        created = msg.get('created_at', '')
        try:
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            time_str = dt.strftime('%H:%M')
        except (ValueError, AttributeError):
            time_str = ''
        
        meta_parts = [time_str]
        if is_mine:
            if msg.get('is_read', False):
                meta_parts.append('✓✓')
            else:
                meta_parts.append('✓')
        
        meta = QLabel('  '.join(meta_parts))
        meta.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_CAPTION};
                background: transparent;
                border: none;
            }}
        """)
        meta.setAlignment(align)
        layout.addWidget(meta)


# ============================================================================
# Conversation List Item
# ============================================================================

class ConversationItem(QFrame):
    """Einzelner Chat in der Chat-Liste."""
    clicked = Signal(int)  # conversation_id
    
    def __init__(self, conv: Dict, parent=None):
        super().__init__(parent)
        self._conv_id = conv.get('id', 0)
        self._selected = False
        self._setup_ui(conv)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def _setup_ui(self, conv: Dict):
        self.setFixedHeight(60)
        self._update_style(False)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        
        # Zeile 1: Name + Unread Badge
        top_row = QHBoxLayout()
        
        name = QLabel(conv.get('partner_name', ''))
        name.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_INVERSE};
                font-size: {FONT_SIZE_BODY};
                font-weight: {FONT_WEIGHT_BOLD};
                background: transparent;
                border: none;
            }}
        """)
        top_row.addWidget(name)
        top_row.addStretch()
        
        unread = conv.get('unread_count', 0)
        if unread > 0:
            badge = QLabel(str(unread))
            badge.setStyleSheet(f"""
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
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            top_row.addWidget(badge)
        
        layout.addLayout(top_row)
        
        # Zeile 2: Letzte Nachricht (Vorschau)
        last_msg = conv.get('last_message', '')
        if last_msg:
            preview = last_msg[:40] + ('...' if len(last_msg) > 40 else '')
            if conv.get('last_message_is_mine', False):
                preview = f"Du: {preview}"
            preview_label = QLabel(preview)
            preview_label.setStyleSheet(f"""
                QLabel {{
                    color: {PRIMARY_500};
                    font-size: {FONT_SIZE_CAPTION};
                    background: transparent;
                    border: none;
                }}
            """)
            layout.addWidget(preview_label)
    
    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style(selected)
    
    def _update_style(self, selected: bool):
        bg = SIDEBAR_HOVER if selected else 'transparent'
        border = f"border-left: 3px solid {ACCENT_500};" if selected else "border-left: 3px solid transparent;"
        self.setStyleSheet(f"""
            ConversationItem {{
                background-color: {bg};
                {border}
                border-top: none;
                border-right: none;
                border-bottom: none;
            }}
        """)
    
    def mousePressEvent(self, event):
        self.clicked.emit(self._conv_id)
        super().mousePressEvent(event)


# ============================================================================
# ChatView - Vollbild Chat
# ============================================================================

class ChatView(QWidget):
    """
    Vollbild-Chat-Ansicht.
    
    Signals:
        back_requested: Zurueck zur Mitteilungszentrale
    """
    back_requested = Signal()
    
    def __init__(self, chat_api, parent=None):
        super().__init__(parent)
        self._chat_api = chat_api
        self._conversations: List[Dict] = []
        self._current_conv_id: Optional[int] = None
        self._current_conv_items: Dict[int, ConversationItem] = {}
        self._messages: List[Dict] = []
        self._conv_worker = None
        self._msg_worker = None
        self._send_worker = None
        self._users_worker = None
        self._refresh_worker = None
        
        # Auto-Refresh Timer (3s Polling wenn Chat aktiv)
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._auto_refresh_poll)
        self._last_known_msg_count = 0
        self._refresh_cycle_count = 0
        self._has_unread_to_mark = True  # Beim ersten Oeffnen mark_as_read
        
        self._setup_ui()
    
    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Linke Sidebar: Chat-Liste ===
        left_panel = QFrame()
        left_panel.setFixedWidth(280)
        left_panel.setStyleSheet(f"""
            QFrame {{
                background-color: {SIDEBAR_BG};
                border: none;
            }}
        """)
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Zurueck-Button
        back_btn = QPushButton(f"  ←  {texts.CHAT_BACK}")
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_INVERSE};
                border: none;
                border-bottom: 1px solid {PRIMARY_500};
                padding: 12px 16px;
                text-align: left;
                font-size: {FONT_SIZE_BODY};
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
            }}
        """)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_requested.emit)
        left_layout.addWidget(back_btn)
        
        # Chat-Titel
        chat_title = QLabel(f"  {texts.CHAT_TITLE}")
        chat_title.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_INVERSE};
                font-size: {FONT_SIZE_H3};
                font-weight: {FONT_WEIGHT_BOLD};
                padding: 12px 16px 8px 16px;
            }}
        """)
        left_layout.addWidget(chat_title)
        
        # Conversations Scroll
        self._conv_scroll = QScrollArea()
        self._conv_scroll.setWidgetResizable(True)
        self._conv_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._conv_scroll.setStyleSheet("background: transparent; border: none;")
        
        self._conv_container = QWidget()
        self._conv_layout = QVBoxLayout(self._conv_container)
        self._conv_layout.setContentsMargins(0, 0, 0, 0)
        self._conv_layout.setSpacing(0)
        self._conv_layout.addStretch()
        
        self._conv_scroll.setWidget(self._conv_container)
        left_layout.addWidget(self._conv_scroll, 1)
        
        # Neuer Chat Button
        new_chat_btn = QPushButton(f"  +  {texts.CHAT_NEW}")
        new_chat_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ACCENT_500};
                border: none;
                border-top: 1px solid {PRIMARY_500};
                padding: 12px 16px;
                text-align: left;
                font-size: {FONT_SIZE_BODY};
                font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
            }}
        """)
        new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_chat_btn.clicked.connect(self._new_chat)
        left_layout.addWidget(new_chat_btn)
        
        main_layout.addWidget(left_panel)
        
        # === Rechte Seite: Chat-Verlauf ===
        right_panel = QFrame()
        right_panel.setStyleSheet(f"background-color: {BG_PRIMARY}; border: none;")
        
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Chat-Header
        self._chat_header = QLabel("")
        self._chat_header.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_H2};
                font-weight: {FONT_WEIGHT_BOLD};
                padding: 12px 20px;
                border-bottom: 1px solid {BORDER_DEFAULT};
                background-color: {BG_TERTIARY};
            }}
        """)
        right_layout.addWidget(self._chat_header)
        
        # Messages Scroll
        self._msg_scroll = QScrollArea()
        self._msg_scroll.setWidgetResizable(True)
        self._msg_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._msg_scroll.setStyleSheet(f"background-color: {BG_PRIMARY}; border: none;")
        
        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(16, 8, 16, 8)
        self._msg_layout.setSpacing(4)
        self._msg_layout.addStretch()
        
        self._msg_scroll.setWidget(self._msg_container)
        right_layout.addWidget(self._msg_scroll, 1)
        
        # Platzhalter wenn kein Chat ausgewaehlt
        self._no_chat_label = QLabel(texts.CHAT_NO_CONVERSATIONS)
        self._no_chat_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_H3};
                padding: 40px;
            }}
        """)
        self._no_chat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Input Area
        self._input_frame = QFrame()
        self._input_frame.setStyleSheet(f"""
            QFrame {{
                border-top: 1px solid {BORDER_DEFAULT};
                background-color: {BG_TERTIARY};
            }}
        """)
        input_layout = QHBoxLayout(self._input_frame)
        input_layout.setContentsMargins(16, 8, 16, 8)
        input_layout.setSpacing(8)
        
        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText(texts.CHAT_PLACEHOLDER)
        self._input_field.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 8px 12px;
                font-size: {FONT_SIZE_BODY};
                background-color: {BG_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {BORDER_FOCUS};
            }}
        """)
        self._input_field.setMaxLength(2000)
        self._input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self._input_field, 1)
        
        self._send_btn = QPushButton(texts.CHAT_SEND)
        self._send_btn.setStyleSheet(get_button_primary_style())
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self._send_btn)
        
        right_layout.addWidget(self._input_frame)
        self._input_frame.setVisible(False)  # Erst sichtbar wenn Chat ausgewaehlt
        
        main_layout.addWidget(right_panel, 1)
    
    def refresh(self):
        """Conversations neu laden."""
        self._load_conversations()
    
    # ====================================================================
    # Auto-Refresh (1s Polling wenn Chat aktiv)
    # ====================================================================
    
    def start_auto_refresh(self):
        """Startet 3s-Polling fuer Echtzeit-Nachrichten und Lesestatus."""
        self._last_known_msg_count = len(self._messages)
        self._refresh_cycle_count = 0
        self._auto_refresh_timer.start(3000)  # 3 Sekunden
    
    def stop_auto_refresh(self):
        """Stoppt das Polling."""
        self._auto_refresh_timer.stop()
    
    def _auto_refresh_poll(self):
        """Wird alle 3s aufgerufen - pollt Nachrichten (+ Conversations alle 15s)."""
        if not self._current_conv_id:
            return
        # Nicht starten wenn bereits ein Refresh laeuft
        if self._refresh_worker and self._refresh_worker.isRunning():
            return
        
        # Conversations nur alle 5 Zyklen nachladen (~15s)
        self._refresh_cycle_count += 1
        reload_convs = (self._refresh_cycle_count % 5 == 0)
        
        # mark_as_read nur wenn beim letzten Zyklus ungelesene erkannt wurden
        needs_mark_read = getattr(self, '_has_unread_to_mark', False)
        
        self._refresh_worker = ChatRefreshWorker(
            self._chat_api, self._current_conv_id,
            reload_conversations=reload_convs,
            mark_read=needs_mark_read, parent=self
        )
        self._refresh_worker.messages_updated.connect(self._on_refresh_messages)
        if reload_convs:
            self._refresh_worker.conversations_updated.connect(self._on_refresh_conversations)
        self._refresh_worker.start()
    
    @Slot(dict)
    def _on_refresh_messages(self, result: dict):
        """Aktualisiert Nachrichten wenn sich etwas geaendert hat."""
        new_messages = result.get('data', [])
        
        # Pruefen ob sich etwas geaendert hat (Anzahl oder Lesestatus)
        has_changes = False
        has_unread = False
        
        if len(new_messages) != len(self._messages):
            has_changes = True
        else:
            # Lesestatus-Aenderungen erkennen (z.B. Gegenueber hat gelesen)
            for old, new in zip(self._messages, new_messages):
                if old.get('is_read') != new.get('is_read'):
                    has_changes = True
                    break
                if old.get('read_at') != new.get('read_at'):
                    has_changes = True
                    break
        
        # Ungelesene Nachrichten vom Gegenueber erkennen
        for msg in new_messages:
            if not msg.get('is_mine') and not msg.get('read_at'):
                has_unread = True
                break
        
        # mark_as_read nur bei ungelesenen - nicht-blockierend im naechsten Worker-Zyklus
        self._has_unread_to_mark = has_unread
        
        if has_changes:
            old_count = len(self._messages)
            self._messages = new_messages
            self._populate_messages()
            
            # Nur nach unten scrollen wenn neue Nachrichten dazukamen
            if len(new_messages) > old_count:
                QTimer.singleShot(50, self._scroll_to_bottom)
    
    @Slot(list)
    def _on_refresh_conversations(self, conversations: list):
        """Aktualisiert die Conversation-Liste (unread-Badges anderer Chats)."""
        if conversations != self._conversations:
            self._conversations = conversations
            self._populate_conversations()
    
    # ====================================================================
    # Conversations laden
    # ====================================================================
    
    def _load_conversations(self):
        if self._conv_worker and self._conv_worker.isRunning():
            return
        self._conv_worker = LoadConversationsWorker(self._chat_api, self)
        self._conv_worker.finished.connect(self._on_conversations_loaded)
        self._conv_worker.error.connect(lambda e: logger.error(f"Chats laden: {e}"))
        self._conv_worker.start()
    
    @Slot(list)
    def _on_conversations_loaded(self, conversations: list):
        self._conversations = conversations
        self._populate_conversations()
    
    def _populate_conversations(self):
        # Alte Items entfernen (ausser Stretch)
        while self._conv_layout.count() > 1:
            item = self._conv_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._current_conv_items.clear()
        
        if not self._conversations:
            label = QLabel(f"  {texts.CHAT_NO_CONVERSATIONS}")
            label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY}; padding: 16px;")
            self._conv_layout.insertWidget(0, label)
            return
        
        for i, conv in enumerate(self._conversations):
            item = ConversationItem(conv)
            item.clicked.connect(self._on_conversation_clicked)
            self._current_conv_items[conv['id']] = item
            self._conv_layout.insertWidget(i, item)
            
            # Aktuell ausgewaehlten Chat markieren
            if self._current_conv_id and conv['id'] == self._current_conv_id:
                item.set_selected(True)
    
    @Slot(int)
    def _on_conversation_clicked(self, conv_id: int):
        # Alte Auswahl deselektieren
        for cid, item in self._current_conv_items.items():
            item.set_selected(cid == conv_id)
        
        self._current_conv_id = conv_id
        
        # Partner-Name finden
        for conv in self._conversations:
            if conv['id'] == conv_id:
                self._chat_header.setText(conv.get('partner_name', ''))
                break
        
        self._input_frame.setVisible(True)
        self._input_field.setFocus()
        
        # Nachrichten laden
        self._load_messages(conv_id)
        
        # Als gelesen markieren
        try:
            self._chat_api.mark_as_read(conv_id)
        except Exception:
            pass
    
    # ====================================================================
    # Nachrichten laden
    # ====================================================================
    
    def _load_messages(self, conv_id: int):
        if self._msg_worker and self._msg_worker.isRunning():
            return
        self._msg_worker = LoadChatMessagesWorker(self._chat_api, conv_id, self)
        self._msg_worker.finished.connect(self._on_messages_loaded)
        self._msg_worker.error.connect(lambda e: logger.error(f"Nachrichten laden: {e}"))
        self._msg_worker.start()
    
    @Slot(dict)
    def _on_messages_loaded(self, result: dict):
        self._messages = result.get('data', [])
        self._last_known_msg_count = len(self._messages)
        self._populate_messages()
    
    def _populate_messages(self):
        # Alte Bubbles entfernen (ausser Stretch)
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self._messages:
            label = QLabel(texts.CHAT_NO_MESSAGES)
            label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY}; padding: 20px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._msg_layout.insertWidget(0, label)
        else:
            for i, msg in enumerate(self._messages):
                bubble = MessageBubble(msg)
                self._msg_layout.insertWidget(i, bubble)
        
        # Nach unten scrollen
        QTimer.singleShot(50, self._scroll_to_bottom)
    
    def _scroll_to_bottom(self):
        vbar = self._msg_scroll.verticalScrollBar()
        vbar.setValue(vbar.maximum())
    
    # ====================================================================
    # Nachricht senden
    # ====================================================================
    
    def _send_message(self):
        if not self._current_conv_id:
            return
        
        content = self._input_field.text().strip()
        if not content:
            return
        
        if len(content) > 2000:
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_warning(texts.CHAT_MESSAGE_TOO_LONG)
            return
        
        self._input_field.clear()
        self._send_btn.setEnabled(False)
        
        self._send_worker = SendMessageWorker(
            self._chat_api, self._current_conv_id, content, self
        )
        self._send_worker.finished.connect(self._on_message_sent)
        self._send_worker.error.connect(self._on_send_error)
        self._send_worker.start()
    
    @Slot(dict)
    def _on_message_sent(self, msg: dict):
        self._send_btn.setEnabled(True)
        # Nachricht lokal anfuegen
        msg['is_mine'] = True
        msg['is_read'] = False
        self._messages.append(msg)
        
        # Neue Bubble hinzufuegen
        bubble = MessageBubble(msg)
        idx = self._msg_layout.count() - 1  # Vor dem Stretch
        self._msg_layout.insertWidget(idx, bubble)
        
        QTimer.singleShot(50, self._scroll_to_bottom)
    
    @Slot(str)
    def _on_send_error(self, error: str):
        self._send_btn.setEnabled(True)
        logger.error(f"Nachricht senden fehlgeschlagen: {error}")
        if hasattr(self, '_toast_manager') and self._toast_manager:
            self._toast_manager.show_error(texts.CHAT_SEND_ERROR)
    
    # ====================================================================
    # Neuer Chat
    # ====================================================================
    
    def _new_chat(self):
        """Zeigt verfuegbare Nutzer und erstellt einen neuen Chat."""
        if self._users_worker and self._users_worker.isRunning():
            return
        self._users_worker = LoadUsersWorker(self._chat_api, self)
        self._users_worker.finished.connect(self._on_users_loaded)
        self._users_worker.error.connect(lambda e: logger.error(f"User laden: {e}"))
        self._users_worker.start()
    
    @Slot(list)
    def _on_users_loaded(self, users: list):
        if not users:
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_info(texts.CHAT_NO_USERS)
            return
        
        # Dialog mit Nutzer-Auswahl
        dialog = QDialog(self)
        dialog.setWindowTitle(texts.CHAT_SELECT_USER_TITLE)
        dialog.setMinimumWidth(300)
        dialog.setStyleSheet(f"background-color: {BG_PRIMARY};")
        
        layout = QVBoxLayout(dialog)
        
        label = QLabel(texts.CHAT_SELECT_USER)
        label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: {FONT_SIZE_H3}; font-weight: {FONT_WEIGHT_BOLD};")
        layout.addWidget(label)
        
        user_list = QListWidget()
        user_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                font-size: {FONT_SIZE_BODY};
            }}
            QListWidget::item {{
                padding: 8px 12px;
            }}
            QListWidget::item:selected {{
                background-color: {PRIMARY_100};
                color: {TEXT_PRIMARY};
            }}
        """)
        
        for user in users:
            item = QListWidgetItem(user.get('username', ''))
            item.setData(Qt.ItemDataRole.UserRole, user.get('id'))
            user_list.addItem(item)
        
        layout.addWidget(user_list)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = user_list.currentItem()
            if selected:
                target_id = selected.data(Qt.ItemDataRole.UserRole)
                self._create_conversation(target_id, selected.text())
    
    def _create_conversation(self, target_user_id: int, username: str):
        """Erstellt eine neue Conversation."""
        try:
            result = self._chat_api.create_conversation(target_user_id)
            conv_id = result.get('id')
            if conv_id:
                if hasattr(self, '_toast_manager') and self._toast_manager:
                    self._toast_manager.show_success(
                        texts.CHAT_CREATED.format(name=username)
                    )
                # Conversations neu laden und den neuen Chat auswaehlen
                self._current_conv_id = conv_id
                self._load_conversations()
                # Nach kurzer Verzoegerung den Chat oeffnen
                QTimer.singleShot(500, lambda: self._on_conversation_clicked(conv_id))
        except Exception as e:
            logger.error(f"Chat erstellen fehlgeschlagen: {e}")
    
    def open_conversation(self, conversation_id: int):
        """Oeffnet einen bestimmten Chat (z.B. von Toast aus)."""
        self._current_conv_id = conversation_id
        self._load_conversations()
        QTimer.singleShot(500, lambda: self._on_conversation_clicked(conversation_id))
