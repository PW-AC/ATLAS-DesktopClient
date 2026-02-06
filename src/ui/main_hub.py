"""
BiPRO-GDV Tool - Hauptfenster (Hub)

Modernes Hauptfenster mit Sidebar-Navigation und Bereichen:
- BiPRO Datenabruf
- Dokumentenarchiv  
- GDV Editor

Design: ACENCIA Corporate Identity
- Dunkle Sidebar (#001f3d)
- Orange Akzente (#fa9939)
"""

from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QMessageBox, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap

from api.client import APIClient
from api.auth import AuthAPI

# ACENCIA Design Tokens
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100,
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD, SPACING_SM, SPACING_MD, SPACING_LG,
    SIDEBAR_WIDTH_INT
)


class NavButton(QPushButton):
    """
    Navigations-Button für die dunkle Sidebar.
    ACENCIA Design: Weiß auf dunkelblau, Orange bei aktiv.
    """
    
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.setText(f"  {icon}  {text}")
        self.setCheckable(True)
        self.setMinimumHeight(48)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
                padding: 12px 16px;
                text-align: left;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {SIDEBAR_TEXT};
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
            }}
            QPushButton:checked {{
                background-color: {SIDEBAR_HOVER};
                border-left: 3px solid {ACCENT_500};
                color: {SIDEBAR_TEXT};
                font-weight: 500;
            }}
        """)


class MainHub(QMainWindow):
    """
    Hauptfenster der BiPRO-GDV Anwendung.
    
    Enthält:
    - Sidebar mit Navigation
    - Stacked Widget für die verschiedenen Bereiche
    """
    
    def __init__(self, api_client: APIClient, auth_api: AuthAPI):
        super().__init__()
        
        self.api_client = api_client
        self.auth_api = auth_api
        
        # Lazy-loaded Views
        self._bipro_view = None
        self._archive_view = None
        self._gdv_view = None
        
        # Fenstertitel
        username = auth_api.current_user.username if auth_api.current_user else "Unbekannt"
        self.setWindowTitle(f"BiPRO-GDV Tool - {username}")
        self.setMinimumSize(1400, 900)
        
        self._setup_ui()
        
        # Standardmäßig BiPRO-Bereich anzeigen
        self._show_bipro()
    
    def _setup_ui(self):
        """UI aufbauen mit ACENCIA Corporate Design."""
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Sidebar (Dunkel - ACENCIA Design) ===
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH_INT)
        sidebar.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {SIDEBAR_BG};
                border: none;
            }}
        """)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(4)
        
        # Logo/Titel Container
        logo_container = QWidget()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(20, 0, 20, 16)
        logo_layout.setSpacing(4)
        
        # Titel (ACENCIA Style)
        title = QLabel("BiPRO-GDV Tool")
        title.setFont(QFont("Tenor Sans", 16))
        title.setStyleSheet(f"""
            color: {SIDEBAR_TEXT};
            font-family: {FONT_HEADLINE};
            padding: 0;
        """)
        logo_layout.addWidget(title)
        
        # Untertitel
        subtitle = QLabel("ACENCIA GmbH")
        subtitle.setStyleSheet(f"""
            color: {PRIMARY_500};
            font-size: {FONT_SIZE_CAPTION};
            padding: 0;
        """)
        logo_layout.addWidget(subtitle)
        
        sidebar_layout.addWidget(logo_container)
        
        # Benutzer-Info
        if self.auth_api.current_user:
            user_container = QWidget()
            user_layout = QHBoxLayout(user_container)
            user_layout.setContentsMargins(20, 8, 20, 16)
            
            user_label = QLabel(f"● {self.auth_api.current_user.username}")
            user_label.setStyleSheet(f"""
                color: {PRIMARY_500};
                font-size: {FONT_SIZE_CAPTION};
            """)
            user_layout.addWidget(user_label)
            user_layout.addStretch()
            sidebar_layout.addWidget(user_container)
        
        # Navigation Label
        nav_label = QLabel("BEREICHE")
        nav_label.setStyleSheet(f"""
            color: {PRIMARY_500};
            font-size: {FONT_SIZE_CAPTION};
            padding: 16px 20px 8px 20px;
            letter-spacing: 1px;
        """)
        sidebar_layout.addWidget(nav_label)
        
        # BiPRO Button
        self.btn_bipro = NavButton("🔄", "BiPRO Datenabruf")
        self.btn_bipro.clicked.connect(self._show_bipro)
        sidebar_layout.addWidget(self.btn_bipro)
        
        # Archiv Button
        self.btn_archive = NavButton("📁", "Dokumentenarchiv")
        self.btn_archive.clicked.connect(self._show_archive)
        sidebar_layout.addWidget(self.btn_archive)
        
        # GDV Editor Button
        self.btn_gdv = NavButton("📄", "GDV Editor")
        self.btn_gdv.clicked.connect(self._show_gdv)
        sidebar_layout.addWidget(self.btn_gdv)
        
        # Spacer
        sidebar_layout.addStretch()
        
        # System Label
        settings_label = QLabel("SYSTEM")
        settings_label.setStyleSheet(f"""
            color: {PRIMARY_500};
            font-size: {FONT_SIZE_CAPTION};
            padding: 16px 20px 8px 20px;
            letter-spacing: 1px;
        """)
        sidebar_layout.addWidget(settings_label)
        
        # VU-Verbindungen
        self.btn_connections = NavButton("⚙️", "VU-Verbindungen")
        self.btn_connections.clicked.connect(self._show_connections)
        sidebar_layout.addWidget(self.btn_connections)
        
        # Einstellungen (Zertifikate etc.)
        self.btn_settings = NavButton("🔧", "Einstellungen")
        self.btn_settings.clicked.connect(self._show_settings)
        sidebar_layout.addWidget(self.btn_settings)
        
        # Abmelden Button (auf dunklem Hintergrund)
        logout_container = QWidget()
        logout_layout = QVBoxLayout(logout_container)
        logout_layout.setContentsMargins(16, 16, 16, 0)
        
        logout_btn = QPushButton("Abmelden")
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {PRIMARY_500};
                border-radius: {RADIUS_MD};
                padding: 10px 16px;
                color: {PRIMARY_500};
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
            }}
            QPushButton:hover {{
                background-color: rgba(136, 169, 195, 0.15);
                border-color: {SIDEBAR_TEXT};
                color: {SIDEBAR_TEXT};
            }}
        """)
        logout_btn.clicked.connect(self._on_logout)
        logout_layout.addWidget(logout_btn)
        sidebar_layout.addWidget(logout_container)
        
        main_layout.addWidget(sidebar)
        
        # === Content Area ===
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background-color: {PRIMARY_0};")
        main_layout.addWidget(self.content_stack)
        
        # Placeholder-Widgets (werden bei Bedarf ersetzt)
        self._placeholder_bipro = self._create_placeholder("BiPRO Datenabruf", "Wird geladen...")
        self._placeholder_archive = self._create_placeholder("Dokumentenarchiv", "Wird geladen...")
        self._placeholder_gdv = self._create_placeholder("GDV Editor", "Wird geladen...")
        self._placeholder_connections = self._create_placeholder("VU-Verbindungen", "Wird geladen...")
        
        self.content_stack.addWidget(self._placeholder_bipro)      # Index 0
        self.content_stack.addWidget(self._placeholder_archive)    # Index 1
        self.content_stack.addWidget(self._placeholder_gdv)        # Index 2
        self.content_stack.addWidget(self._placeholder_connections) # Index 3
    
    def _create_placeholder(self, title: str, subtitle: str) -> QWidget:
        """Erstellt ein Placeholder-Widget im ACENCIA Design."""
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {PRIMARY_0};")
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Tenor Sans", 20))
        title_label.setStyleSheet(f"""
            color: {PRIMARY_900};
            font-family: {FONT_HEADLINE};
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet(f"color: {PRIMARY_500};")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_label)
        
        return widget
    
    def _update_nav_buttons(self, active_btn: NavButton):
        """Aktualisiert die Navigation-Buttons."""
        for btn in [self.btn_bipro, self.btn_archive, self.btn_gdv, self.btn_connections, self.btn_settings]:
            btn.setChecked(btn == active_btn)
    
    def _show_bipro(self):
        """Zeigt den BiPRO-Bereich."""
        self._update_nav_buttons(self.btn_bipro)
        
        if self._bipro_view is None:
            from ui.bipro_view import BiPROView
            self._bipro_view = BiPROView(self.api_client)
            self._bipro_view.documents_uploaded.connect(self._on_documents_uploaded)
            
            # Placeholder ersetzen
            self.content_stack.removeWidget(self._placeholder_bipro)
            self.content_stack.insertWidget(0, self._bipro_view)
        
        self.content_stack.setCurrentIndex(0)
    
    def _show_archive(self):
        """Zeigt das Dokumentenarchiv mit Box-System."""
        self._update_nav_buttons(self.btn_archive)
        
        if self._archive_view is None:
            # Neue Box-basierte Archiv-Ansicht verwenden
            from ui.archive_boxes_view import ArchiveBoxesView
            self._archive_view = ArchiveBoxesView(self.api_client)
            self._archive_view.open_gdv_requested.connect(self._on_open_gdv_from_archive)
            
            # Placeholder ersetzen
            self.content_stack.removeWidget(self._placeholder_archive)
            self.content_stack.insertWidget(1, self._archive_view)
        
        self.content_stack.setCurrentIndex(1)
    
    def _show_gdv(self):
        """Zeigt den GDV-Editor."""
        self._update_nav_buttons(self.btn_gdv)
        
        if self._gdv_view is None:
            from ui.gdv_editor_view import GDVEditorView
            self._gdv_view = GDVEditorView(self.api_client)
            
            # Placeholder ersetzen
            self.content_stack.removeWidget(self._placeholder_gdv)
            self.content_stack.insertWidget(2, self._gdv_view)
        
        self.content_stack.setCurrentIndex(2)
    
    def _show_connections(self):
        """Zeigt die VU-Verbindungsverwaltung."""
        self._update_nav_buttons(self.btn_connections)
        
        # Für jetzt: BiPRO-View hat die Verbindungsverwaltung integriert
        # Später: Eigene Ansicht
        QMessageBox.information(
            self,
            "VU-Verbindungen",
            "Die VU-Verbindungen können im BiPRO Datenabruf-Bereich verwaltet werden.\n\n"
            "(Eigene Ansicht kommt in einer späteren Version)"
        )
        self._show_bipro()
    
    def _show_settings(self):
        """Öffnet den Einstellungen-Dialog."""
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()
    
    def _on_documents_uploaded(self):
        """Callback wenn neue Dokumente hochgeladen wurden."""
        # Archiv-View aktualisieren falls geladen
        if self._archive_view:
            # ArchiveBoxesView verwendet _refresh_all()
            if hasattr(self._archive_view, '_refresh_all'):
                self._archive_view._refresh_all()
            elif hasattr(self._archive_view, 'refresh_documents'):
                self._archive_view.refresh_documents()
    
    def _on_open_gdv_from_archive(self, doc_id: int, filename: str):
        """Öffnet eine GDV-Datei aus dem Archiv im Editor."""
        # Zum GDV-Editor wechseln
        self._show_gdv()
        
        # Datei laden
        if self._gdv_view:
            self._gdv_view.load_from_server(doc_id, filename)
    
    def _on_logout(self):
        """Benutzer abmelden."""
        reply = QMessageBox.question(
            self,
            "Abmelden",
            "Wirklich abmelden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.auth_api.logout()
            self.close()
    
    def closeEvent(self, event):
        """Fenster schließen."""
        # Prüfen auf ungespeicherte Änderungen im GDV-Editor
        if self._gdv_view and hasattr(self._gdv_view, 'has_unsaved_changes'):
            if self._gdv_view.has_unsaved_changes():
                reply = QMessageBox.question(
                    self,
                    "Ungespeicherte Änderungen",
                    "Es gibt ungespeicherte Änderungen im GDV-Editor.\nWirklich beenden?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
        
        # Worker-Threads aufräumen
        if self._bipro_view and hasattr(self._bipro_view, 'cleanup'):
            self._bipro_view.cleanup()
        
        event.accept()
