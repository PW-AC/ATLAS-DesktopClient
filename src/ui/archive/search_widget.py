"""
ACENCIA ATLAS - ATLAS Index Volltextsuche

Extrahiert aus archive_boxes_view.py:
- SearchResultCard: Einzelne Ergebnis-Karte (Google-Stil)
- AtlasIndexWidget: Globale Volltextsuche ueber alle Dokumente
"""

from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QScrollArea, QPushButton, QCheckBox, QMenu
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from api.documents import SearchResult, BOX_DISPLAY_NAMES, BOX_COLORS
from utils.date_utils import format_date_german
from ui.archive.workers import SearchWorker
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, ACCENT_500,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    WARNING,
    FONT_HEADLINE, FONT_BODY, FONT_SIZE_BODY,
    RADIUS_MD,
    DOCUMENT_DISPLAY_COLORS
)

__all__ = ['SearchResultCard', 'AtlasIndexWidget']


class SearchResultCard(QFrame):
    """
    Einzelne Ergebnis-Karte im ATLAS Index (Google-Stil).
    
    Zeigt: Dateiname (fett), Meta-Zeile (Box|VU|Datum), Text-Snippet mit Highlighting.
    """
    clicked = Signal(object)         # SearchResult
    double_clicked = Signal(object)  # SearchResult
    context_menu_requested = Signal(object, object)  # SearchResult, QPoint
    
    # Box-Emojis fuer Meta-Zeile
    _BOX_EMOJIS = {
        'gdv': '📊', 'courtage': '💰', 'sach': '🏠', 'leben': '❤️',
        'kranken': '🏥', 'sonstige': '📁', 'roh': '📦', 'eingang': '📬',
        'verarbeitung': '📥', 'falsch': '⚠️'
    }
    
    def __init__(self, result: SearchResult, query: str, parent=None):
        super().__init__(parent)
        self.result = result
        self.query = query
        self._setup_ui()
    
    def _setup_ui(self):
        from html import escape
        from i18n.de import ATLAS_INDEX_RESULT_ARCHIVED, ATLAS_INDEX_NO_TEXT
        
        doc = self.result.document
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Hover-Effekt + Basis-Style
        border_color = BORDER_DEFAULT
        bg = BG_PRIMARY
        color_strip = ""
        if doc.display_color and doc.display_color in DOCUMENT_DISPLAY_COLORS:
            color_strip = f"border-left: 4px solid {doc.display_color};"
        
        self.setStyleSheet(f"""
            SearchResultCard {{
                background: {bg};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 10px 12px;
                {color_strip}
            }}
            SearchResultCard:hover {{
                background: {BG_SECONDARY};
                border-color: {PRIMARY_500};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Zeile 1: Dateiname (fett)
        filename_label = QLabel(f"📄 {escape(doc.original_filename)}")
        filename_label.setFont(QFont(FONT_BODY, int(FONT_SIZE_BODY.replace('pt', '').replace('px', '')), QFont.Weight.Bold))
        filename_label.setStyleSheet(f"color: {TEXT_PRIMARY}; border: none; background: transparent; padding: 0;")
        filename_label.setWordWrap(True)
        layout.addWidget(filename_label)
        
        # Zeile 2: Meta (Box | VU | Datum | Archiviert)
        box_emoji = self._BOX_EMOJIS.get(doc.box_type, '📁')
        box_name = BOX_DISPLAY_NAMES.get(doc.box_type, doc.box_type)
        box_color = BOX_COLORS.get(doc.box_type, TEXT_SECONDARY)
        
        meta_parts = [f'<span style="color:{box_color}; font-weight:600;">{box_emoji} {escape(box_name)}</span>']
        if doc.vu_name:
            meta_parts.append(escape(doc.vu_name))
        if doc.created_at:
            meta_parts.append(format_date_german(doc.created_at))
        if doc.is_archived:
            meta_parts.append(f'<span style="color:{WARNING};">{escape(ATLAS_INDEX_RESULT_ARCHIVED)}</span>')
        
        meta_label = QLabel(" &nbsp;|&nbsp; ".join(meta_parts))
        meta_label.setTextFormat(Qt.TextFormat.RichText)
        meta_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent; padding: 0;")
        layout.addWidget(meta_label)
        
        # Zeile 3: Text-Snippet mit Highlighting
        snippet_html = self._build_snippet(self.result.text_preview, self.query)
        if snippet_html:
            snippet_label = QLabel(snippet_html)
            snippet_label.setTextFormat(Qt.TextFormat.RichText)
            snippet_label.setWordWrap(True)
            snippet_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent; padding: 2px 0 0 0;")
            layout.addWidget(snippet_label)
        else:
            no_text_label = QLabel(f"<i>{escape(ATLAS_INDEX_NO_TEXT)}</i>")
            no_text_label.setTextFormat(Qt.TextFormat.RichText)
            no_text_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; border: none; background: transparent; padding: 2px 0 0 0;")
            layout.addWidget(no_text_label)
    
    @staticmethod
    def _build_snippet(text_preview: Optional[str], query: str) -> Optional[str]:
        """
        Baut ein kontextuelles Snippet mit dem ersten Treffer fett hervorgehoben.
        
        - Sucht case-insensitive nach dem vollen Suchbegriff, dann nach Einzelwoertern
        - Zeigt ~100 Zeichen davor + Treffer + ~200 Zeichen danach
        - Schneidet an Wortgrenzen ab
        - HTML-escaped, Treffer-Wort in <b>
        """
        from html import escape
        
        if not text_preview or not text_preview.strip():
            return None
        
        # Einzeiliger Text (Newlines -> Spaces)
        clean_text = ' '.join(text_preview.split())
        text_lower = clean_text.lower()
        
        # Treffer finden: Erst voller Suchbegriff, dann Einzelwoerter
        match_term = None
        pos = -1
        
        # 1. Versuch: Voller Suchbegriff
        query_lower = query.lower().strip()
        pos = text_lower.find(query_lower)
        if pos >= 0:
            match_term = query.strip()
        
        # 2. Versuch: Einzelne Woerter (laengstes zuerst, da aussagekraeftiger)
        if pos < 0:
            words = [w for w in query.split() if len(w) >= 3]
            words.sort(key=len, reverse=True)
            for word in words:
                word_pos = text_lower.find(word.lower())
                if word_pos >= 0:
                    pos = word_pos
                    match_term = word
                    break
        
        if pos >= 0 and match_term:
            match_len = len(match_term)
            # Kontext um den Treffer: ~100 vor, ~200 nach
            start = max(0, pos - 100)
            end = min(len(clean_text), pos + match_len + 200)
            
            # An Wortgrenzen ausrichten (nicht mitten im Wort abschneiden)
            if start > 0:
                space_pos = clean_text.find(' ', start)
                if space_pos != -1 and space_pos < pos:
                    start = space_pos + 1
            if end < len(clean_text):
                space_pos = clean_text.rfind(' ', pos + match_len, end + 30)
                if space_pos != -1:
                    end = space_pos
            
            snippet = clean_text[start:end]
            
            # Prefix/Suffix Ellipsis
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(clean_text) else ""
            
            # Treffer-Wort im Snippet hervorheben (nur erstes Vorkommen)
            snippet_lower = snippet.lower()
            match_pos = snippet_lower.find(match_term.lower())
            if match_pos >= 0:
                before = escape(snippet[:match_pos])
                matched = escape(snippet[match_pos:match_pos + match_len])
                after = escape(snippet[match_pos + match_len:])
                return f'{prefix}{before}<b style="color:{TEXT_PRIMARY};">{matched}</b>{after}{suffix}'
            
            return f'{prefix}{escape(snippet)}{suffix}'
        else:
            # Kein Treffer im Preview (nur Dateiname-Match) -> erste ~200 Zeichen
            snippet = clean_text[:200]
            if len(clean_text) > 200:
                # An Wortgrenze abschneiden
                space_pos = snippet.rfind(' ', 150)
                if space_pos != -1:
                    snippet = snippet[:space_pos]
                snippet += "..."
            return escape(snippet)
    
    def mouseDoubleClickEvent(self, event):
        """Doppelklick -> Vorschau oeffnen."""
        self.double_clicked.emit(self.result)
        event.accept()
    
    def mousePressEvent(self, event):
        """Einfacher Klick."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.result)
        event.accept()
    
    def contextMenuEvent(self, event):
        """Rechtsklick -> Kontextmenue."""
        self.context_menu_requested.emit(self.result, event.globalPos())
        event.accept()


class AtlasIndexWidget(QWidget):
    """
    ATLAS Index - Globale Volltextsuche ueber alle Dokumente.
    
    Virtuelle "Box" im Archiv, die server-seitige Suche mit FULLTEXT-Index
    auf document_ai_data.extracted_text nutzt. Snippet-basierte Ergebnisdarstellung.
    """
    # Signale fuer Interaktion mit dem ArchiveBoxesView
    preview_requested = Signal(object)       # Document -> Vorschau oeffnen
    show_in_box_requested = Signal(object)   # Document -> Zur Box wechseln
    download_requested = Signal(object)      # Document -> Download
    
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self._repo = repository
        self._search_worker: Optional[SearchWorker] = None
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(400)
        self._debounce_timer.timeout.connect(self._execute_search)
        self._current_query = ""
        self._result_cards: List[SearchResultCard] = []
        self._setup_ui()
    
    def _setup_ui(self):
        from i18n.de import (
            ATLAS_INDEX_TITLE, ATLAS_INDEX_SEARCH_PLACEHOLDER,
            ATLAS_INDEX_LIVE_SEARCH, ATLAS_INDEX_ENTER_QUERY
        )
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header: Titel
        title = QLabel(f"🔎 {ATLAS_INDEX_TITLE}")
        title.setFont(QFont(FONT_HEADLINE, 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)
        
        # Suchfeld
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(ATLAS_INDEX_SEARCH_PLACEHOLDER)
        self._search_input.setFont(QFont(FONT_BODY, 13))
        self._search_input.setMinimumHeight(38)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 6px 12px;
                font-size: 13px;
                background: {BG_PRIMARY};
                color: {TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {PRIMARY_500};
            }}
        """)
        self._search_input.textChanged.connect(self._on_text_changed)
        self._search_input.returnPressed.connect(self._on_enter_pressed)
        search_row.addWidget(self._search_input)
        
        # Such-Button (sichtbar wenn Live-Suche deaktiviert)
        from i18n.de import ATLAS_INDEX_SEARCH_BUTTON
        self._search_btn = QPushButton(ATLAS_INDEX_SEARCH_BUTTON)
        self._search_btn.setMinimumHeight(38)
        self._search_btn.setFont(QFont(FONT_BODY, 13))
        self._search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._search_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                padding: 6px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {PRIMARY_900};
            }}
            QPushButton:pressed {{
                background: {PRIMARY_900};
            }}
        """)
        self._search_btn.clicked.connect(self._on_enter_pressed)
        self._search_btn.setVisible(False)  # Anfangs versteckt (Live-Suche ist an)
        search_row.addWidget(self._search_btn)
        
        layout.addLayout(search_row)
        
        # Checkboxen: Suchoptionen
        from i18n.de import ATLAS_INDEX_INCLUDE_RAW, ATLAS_INDEX_SUBSTRING_SEARCH
        
        options_row = QHBoxLayout()
        options_row.setSpacing(16)
        
        self._live_search_cb = QCheckBox(ATLAS_INDEX_LIVE_SEARCH)
        self._live_search_cb.setChecked(True)
        self._live_search_cb.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._live_search_cb.toggled.connect(self._on_live_search_toggled)
        options_row.addWidget(self._live_search_cb)
        
        self._include_raw_cb = QCheckBox(ATLAS_INDEX_INCLUDE_RAW)
        self._include_raw_cb.setChecked(False)
        self._include_raw_cb.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._include_raw_cb.toggled.connect(self._on_option_changed)
        options_row.addWidget(self._include_raw_cb)
        
        self._substring_cb = QCheckBox(ATLAS_INDEX_SUBSTRING_SEARCH)
        self._substring_cb.setChecked(False)
        self._substring_cb.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._substring_cb.toggled.connect(self._on_option_changed)
        options_row.addWidget(self._substring_cb)
        
        options_row.addStretch()
        layout.addLayout(options_row)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER_DEFAULT};")
        layout.addWidget(sep)
        
        # Ergebnis-Zaehler / Status
        self._status_label = QLabel(ATLAS_INDEX_ENTER_QUERY)
        self._status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: 500;")
        layout.addWidget(self._status_label)
        
        # Ergebnis-Liste (scrollbar)
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """)
        
        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, 8, 0)
        self._results_layout.setSpacing(8)
        self._results_layout.addStretch()
        
        self._scroll_area.setWidget(self._results_container)
        layout.addWidget(self._scroll_area, 1)  # stretch=1 -> nimmt restlichen Platz
    
    def _on_text_changed(self, text: str):
        """Reagiert auf Texteingabe im Suchfeld."""
        from i18n.de import ATLAS_INDEX_MIN_CHARS, ATLAS_INDEX_ENTER_QUERY
        
        text = text.strip()
        if len(text) < 3:
            self._debounce_timer.stop()
            if len(text) == 0:
                self._status_label.setText(ATLAS_INDEX_ENTER_QUERY)
            else:
                self._status_label.setText(ATLAS_INDEX_MIN_CHARS)
            self._clear_results()
            return
        
        self._current_query = text
        
        if self._live_search_cb.isChecked():
            # Live-Suche: Debounce 400ms
            self._debounce_timer.start()
        # Wenn Live-Suche deaktiviert: nichts tun (warten auf Enter)
    
    def _on_live_search_toggled(self, checked: bool):
        """Live-Suche Checkbox geaendert -> Such-Button ein-/ausblenden."""
        self._search_btn.setVisible(not checked)
        if not checked:
            self._debounce_timer.stop()
    
    def _on_enter_pressed(self):
        """Enter oder Such-Button gedrueckt -> sofort suchen."""
        text = self._search_input.text().strip()
        if len(text) >= 3:
            self._current_query = text
            self._debounce_timer.stop()
            self._execute_search()
    
    def _on_option_changed(self, checked: bool):
        """Checkbox geaendert -> erneut suchen wenn Ergebnisse vorhanden."""
        if self._current_query and len(self._current_query) >= 3:
            self._execute_search()
    
    def _execute_search(self):
        """Fuehrt die Suche per SearchWorker aus."""
        from i18n.de import ATLAS_INDEX_SEARCHING
        
        query = self._current_query
        if len(query) < 3:
            return
        
        # Laufenden Worker abbrechen
        if self._search_worker is not None and self._search_worker.isRunning():
            try:
                self._search_worker.finished.disconnect(self._on_search_finished)
                self._search_worker.error.disconnect(self._on_search_error)
            except RuntimeError:
                pass
            self._search_worker = None
        
        self._status_label.setText(ATLAS_INDEX_SEARCHING)
        
        self._search_worker = SearchWorker(
            self._repo, query,
            include_raw=self._include_raw_cb.isChecked(),
            substring=self._substring_cb.isChecked()
        )
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()
    
    def _on_search_finished(self, results: List[SearchResult]):
        """Callback wenn Suchergebnisse vorliegen."""
        from i18n.de import ATLAS_INDEX_RESULTS_COUNT, ATLAS_INDEX_NO_RESULTS
        
        self._clear_results()
        
        if not results:
            self._status_label.setText(ATLAS_INDEX_NO_RESULTS)
            return
        
        self._status_label.setText(ATLAS_INDEX_RESULTS_COUNT.format(count=len(results)))
        
        for result in results:
            card = SearchResultCard(result, self._current_query)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.context_menu_requested.connect(self._on_card_context_menu)
            self._result_cards.append(card)
            # Vor dem Stretch einfuegen
            self._results_layout.insertWidget(self._results_layout.count() - 1, card)
    
    def _on_search_error(self, error_msg: str):
        """Callback bei Suchfehler."""
        self._clear_results()
        self._status_label.setText(f"Fehler: {error_msg}")
    
    def _clear_results(self):
        """Entfernt alle Ergebnis-Karten."""
        for card in self._result_cards:
            card.setParent(None)
            card.deleteLater()
        self._result_cards.clear()
    
    def _on_card_double_clicked(self, result: SearchResult):
        """Doppelklick auf Ergebnis-Karte -> Vorschau."""
        self.preview_requested.emit(result.document)
    
    def _on_card_context_menu(self, result: SearchResult, pos):
        """Rechtsklick auf Ergebnis-Karte -> Kontextmenue."""
        from i18n.de import (
            ATLAS_INDEX_PREVIEW, ATLAS_INDEX_DOWNLOAD, ATLAS_INDEX_SHOW_IN_BOX
        )
        
        menu = QMenu(self)
        
        preview_action = menu.addAction(f"👁 {ATLAS_INDEX_PREVIEW}")
        download_action = menu.addAction(f"💾 {ATLAS_INDEX_DOWNLOAD}")
        menu.addSeparator()
        box_name = BOX_DISPLAY_NAMES.get(result.document.box_type, result.document.box_type)
        show_in_box_action = menu.addAction(f"📂 {ATLAS_INDEX_SHOW_IN_BOX} ({box_name})")
        
        action = menu.exec(pos)
        if action == preview_action:
            self.preview_requested.emit(result.document)
        elif action == download_action:
            self.download_requested.emit(result.document)
        elif action == show_in_box_action:
            self.show_in_box_requested.emit(result.document)
    
    def focus_search(self):
        """Setzt Fokus auf das Suchfeld."""
        self._search_input.setFocus()
        self._search_input.selectAll()
    
    def cleanup(self):
        """Bereinigt laufende Worker."""
        self._debounce_timer.stop()
        if self._search_worker is not None and self._search_worker.isRunning():
            try:
                self._search_worker.finished.disconnect(self._on_search_finished)
                self._search_worker.error.disconnect(self._on_search_error)
            except RuntimeError:
                pass
            self._search_worker = None
