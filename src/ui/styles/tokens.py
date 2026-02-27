# -*- coding: utf-8 -*-
"""
ACENCIA Design Tokens

Offizielle Farben, Typografie und Spacing gemäß ACENCIA Corporate Design.
Quelle: Firmendesign/Farben.txt und Firmendesign/Fonts.txt

WICHTIG: Diese Datei ist die Single Source of Truth für alle visuellen Konstanten.
Änderungen hier wirken sich auf die gesamte Anwendung aus.
"""

# =============================================================================
# ACENCIA PRIMÄRFARBEN (Blau-Palette) - OFFIZIELL
# =============================================================================

PRIMARY_900 = "#001f3d"   # Dunkles Blau - Sidebar, Titel, Primärtext
PRIMARY_500 = "#88a9c3"   # Helles Blau - Sekundärtext, Icons, Info
PRIMARY_100 = "#e3ebf2"   # Sehr helles Blau - Hover, Backgrounds, Borders
PRIMARY_0 = "#ffffff"     # Weiß - Content-Hintergrund

# =============================================================================
# ACENCIA SEKUNDÄRFARBEN (Orange) - OFFIZIELL - SPARSAM VERWENDEN!
# =============================================================================

ACCENT_500 = "#fa9939"    # Volles Orange - Primäre CTAs, Active States
ACCENT_100 = "#f8dcbf"    # Helles Orange - Badges, dezente Highlights

# =============================================================================
# ABGELEITETE FARBEN (für UI-Konsistenz)
# =============================================================================

# Text
TEXT_PRIMARY = PRIMARY_900
TEXT_SECONDARY = PRIMARY_500
TEXT_DISABLED = "#a0aec0"
TEXT_INVERSE = PRIMARY_0

# Hintergründe
BG_PRIMARY = PRIMARY_0
BG_SECONDARY = PRIMARY_100
BG_TERTIARY = "#f8fafc"

# Borders
BORDER_DEFAULT = PRIMARY_100
BORDER_STRONG = PRIMARY_500
BORDER_FOCUS = ACCENT_500

# Sidebar (Dunkel)
SIDEBAR_BG = PRIMARY_900
SIDEBAR_TEXT = PRIMARY_0
SIDEBAR_HOVER = "rgba(136, 169, 195, 0.2)"  # primary-500 @ 20%
SIDEBAR_ACTIVE_BORDER = ACCENT_500

# =============================================================================
# STATUS-FARBEN (nicht im CI, aber notwendig für UX)
# =============================================================================

SUCCESS = "#059669"       # Grün - Erfolg, Aktiv
SUCCESS_500 = SUCCESS
SUCCESS_LIGHT = "#d1fae5"
WARNING = ACCENT_500      # Orange - Warnung (= ACENCIA Orange)
WARNING_500 = WARNING
WARNING_LIGHT = ACCENT_100
ERROR = "#dc2626"         # Rot - Fehler
ERROR_500 = ERROR
ERROR_LIGHT = "#fee2e2"
DANGER_500 = ERROR        # Alias fuer Settings-Panel
INFO = PRIMARY_500        # Hellblau - Information (= ACENCIA Hellblau)
INFO_500 = INFO
INFO_LIGHT = PRIMARY_100

# =============================================================================
# BOX-FARBEN (Dokumentenarchiv) - Harmonisch mit CI
# =============================================================================

BOX_COLORS = {
    "eingang": "#f59e0b",       # Amber - Attention
    "verarbeitung": "#f97316",  # Orange - In Progress
    "gdv": "#10b981",           # Grün - Primäre Daten
    "courtage": "#6366f1",      # Indigo - Finanzdaten
    "sach": "#3b82f6",          # Blau - Versicherungstyp
    "leben": "#8b5cf6",         # Violett - Versicherungstyp
    "kranken": "#06b6d4",       # Cyan - Versicherungstyp
    "sonstige": "#64748b",      # Grau - Neutral
    "roh": "#78716c",           # Steingrau - Archiv/System
}

# =============================================================================
# DOKUMENTEN-FARBMARKIERUNGEN (blasse, nicht grelle Toene)
# =============================================================================

DOCUMENT_DISPLAY_COLORS = {
    'green':  '#c8e6c9',   # Blasses Gruen
    'red':    '#ffcdd2',   # Blasses Rot
    'blue':   '#bbdefb',   # Blasses Blau
    'orange': '#ffe0b2',   # Blasses Orange
    'purple': '#e1bee7',   # Blasses Lila
    'pink':   '#f8bbd0',   # Blasses Pink
    'cyan':   '#b2ebf2',   # Blasses Tuerkis
    'yellow': '#fff9c4',   # Blasses Gelb
}

# =============================================================================
# PILL-BADGE FARBEN (Provisionsmanagement Status-Badges)
# =============================================================================

PILL_COLORS = {
    "zugeordnet":        {"bg": "#d1fae5", "text": "#065f46"},
    "vertrag_gefunden":  {"bg": "#fef3c7", "text": "#92400e"},
    "offen":             {"bg": "#fff3e0", "text": "#e65100"},
    "nicht_zugeordnet":  {"bg": "#fff3e0", "text": "#e65100"},
    "gesperrt":    {"bg": "#fee2e2", "text": "#991b1b"},
    "entwurf":     {"bg": "#f3f4f6", "text": "#374151"},
    "geprueft":    {"bg": "#dbeafe", "text": "#1e40af"},
    "freigegeben": {"bg": "#d1fae5", "text": "#065f46"},
    "ausgezahlt":  {"bg": "#c8e6c9", "text": "#1b5e20"},
    "ignoriert":   {"bg": "#f3f4f6", "text": "#6b7280"},
    "in_pruefung": {"bg": "#fef3c7", "text": "#92400e"},
    "abgeschlossen": {"bg": "#d1fae5", "text": "#065f46"},
}

ROLE_BADGE_COLORS = {
    "consulter":   {"bg": "#dbeafe", "text": "#1e40af"},
    "teamleiter":  {"bg": "#fff3e0", "text": "#e65100"},
    "backoffice":  {"bg": "#f3f4f6", "text": "#374151"},
}

ART_BADGE_COLORS = {
    "ap":              {"bg": "#dbeafe", "text": "#1e40af"},
    "bp":              {"bg": "#e0e7ff", "text": "#3730a3"},
    "rueckbelastung":  {"bg": "#fee2e2", "text": "#991b1b"},
    "nullmeldung":     {"bg": "#fef3c7", "text": "#92400e"},
    "sonstige":        {"bg": "#f3f4f6", "text": "#374151"},
}

VU_BADGE_COLORS = {
    "Allianz":   {"bg": "#dbeafe", "text": "#1e40af"},
    "SwissLife": {"bg": "#dcfce7", "text": "#166534"},
    "VB":        {"bg": "#fff7ed", "text": "#c2410c"},
}

# =============================================================================
# TYPOGRAFIE - ACENCIA Fonts (OFFIZIELL)
# =============================================================================

# Font-Familien (mit Fallbacks)
FONT_HEADLINE = '"Tenor Sans", "Segoe UI", -apple-system, sans-serif'
FONT_BODY = '"Open Sans", "Segoe UI", -apple-system, sans-serif'
FONT_MONO = '"Cascadia Code", "Consolas", monospace'

# Font-Groessen (pt statt px: verhindert QFont::setPointSize(-1) Warnungen)
# Qt-Stylesheets mit px setzen pixelSize, pointSize() liefert dann -1.
# Mit pt bleibt pointSize() immer gueltig.
FONT_SIZE_H1 = "15pt"
FONT_SIZE_H2 = "12pt"
FONT_SIZE_H3 = "11pt"
FONT_SIZE_BODY = "10pt"
FONT_SIZE_CAPTION = "8pt"
FONT_SIZE_MONO = "9pt"

# Font-Weights
FONT_WEIGHT_NORMAL = "400"
FONT_WEIGHT_MEDIUM = "500"
FONT_WEIGHT_BOLD = "600"

# =============================================================================
# SPACING-SYSTEM
# =============================================================================

SPACING_XS = "4px"    # Icon-Padding
SPACING_SM = "8px"    # Kompakte Elemente
SPACING_MD = "16px"   # Standard
SPACING_LG = "24px"   # Section-Trennung
SPACING_XL = "32px"   # Bereichs-Trennung

# =============================================================================
# BORDER-RADIUS
# =============================================================================

RADIUS_SM = "4px"
RADIUS_MD = "6px"
RADIUS_LG = "8px"

# =============================================================================
# SHADOWS
# =============================================================================

SHADOW_SM = "0 1px 2px rgba(0, 0, 0, 0.05)"
SHADOW_MD = "0 4px 6px rgba(0, 0, 0, 0.1)"
SHADOW_LG = "0 10px 15px rgba(0, 0, 0, 0.1)"

# =============================================================================
# LAYOUT-KONSTANTEN
# =============================================================================

SIDEBAR_WIDTH = "220px"
SIDEBAR_WIDTH_INT = 220

CONTENT_MIN_WIDTH = "800px"
CONTENT_MIN_WIDTH_INT = 800

SPLITTER_MIN_LEFT = 200
SPLITTER_MIN_RIGHT = 400

# =============================================================================
# TRANSITION
# =============================================================================

TRANSITION_FAST = "150ms"
TRANSITION_NORMAL = "250ms"

# =============================================================================
# RICH-TOOLTIP BUILDER
# =============================================================================

def build_rich_tooltip(
    definition: str,
    berechnung: str = "",
    quelle: str = "",
    hinweis: str = "",
) -> str:
    """Baut einen standardisierten Rich-Tooltip im HTML-Format.

    Jeder Tooltip folgt dem 4-Felder-Template:
      - Definition:  Was bedeutet dieses Feld?
      - Berechnung:  Wie entsteht der Wert?
      - Quelle:      Woher kommen die Daten?
      - Hinweis:     Typische Ursachen bei Abweichungen
    """
    parts = [f"<b>{definition}</b>"]
    if berechnung:
        parts.append(f"<br/><span style='color:{PRIMARY_500};'>Berechnung:</span> {berechnung}")
    if quelle:
        parts.append(f"<br/><span style='color:{PRIMARY_500};'>Quelle:</span> {quelle}")
    if hinweis:
        parts.append(f"<br/><span style='color:{ACCENT_500};'>Hinweis:</span> {hinweis}")
    return "".join(parts)


# =============================================================================
# PROVISION TABLE STYLE (erhoehte Zeilenhoehe fuer GF-Lesbarkeit)
# =============================================================================

def get_provision_table_style() -> str:
    """Tabellen-Styling fuer Provisionsmanagement: grosszuegige Zeilen, gut lesbar."""
    return f"""
        QTableView {{
            background-color: {BG_PRIMARY};
            alternate-background-color: #f5f8fb;
            border: 1.5px solid #b0c4d8;
            border-radius: {RADIUS_LG};
            gridline-color: #d5dfe8;
            font-family: {FONT_BODY};
            font-size: 11pt;
            selection-background-color: {PRIMARY_100};
            selection-color: {TEXT_PRIMARY};
        }}
        QTableView::item {{
            padding: 12px 14px;
            border-bottom: 1px solid #d5dfe8;
        }}
        QTableView::item:selected {{
            background-color: #d0dfed;
            color: {TEXT_PRIMARY};
        }}
        QTableView::item:hover {{
            background-color: #edf2f7;
        }}
        QHeaderView::section {{
            background-color: #d0dcea;
            color: {PRIMARY_900};
            padding: 12px 14px;
            border: none;
            border-bottom: 2px solid #98b3cb;
            font-weight: {FONT_WEIGHT_BOLD};
            font-family: {FONT_BODY};
            font-size: 10pt;
        }}
        QHeaderView::section:hover {{
            background-color: #bfcfdf;
        }}
    """


# =============================================================================
# STYLESHEET-HELPER FUNKTIONEN
# =============================================================================

def get_button_primary_style() -> str:
    """Primärer Button-Style (Orange) - nur für Haupt-CTAs."""
    return f"""
        QPushButton {{
            background-color: {ACCENT_500};
            color: {TEXT_INVERSE};
            border: none;
            border-radius: {RADIUS_MD};
            padding: {SPACING_SM} {SPACING_MD};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}
        QPushButton:hover {{
            background-color: #e88a2d;
        }}
        QPushButton:pressed {{
            background-color: #d97706;
        }}
        QPushButton:disabled {{
            background-color: {PRIMARY_100};
            color: {TEXT_DISABLED};
        }}
    """

def get_button_secondary_style() -> str:
    """Sekundärer Button-Style (Dunkelblau Border)."""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {PRIMARY_900};
            border: 1px solid {PRIMARY_900};
            border-radius: {RADIUS_MD};
            padding: {SPACING_SM} {SPACING_MD};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}
        QPushButton:hover {{
            background-color: {PRIMARY_100};
        }}
        QPushButton:pressed {{
            background-color: {PRIMARY_500};
            color: {TEXT_INVERSE};
        }}
        QPushButton:disabled {{
            border-color: {PRIMARY_100};
            color: {TEXT_DISABLED};
        }}
    """

def get_button_ghost_style() -> str:
    """Ghost Button-Style (transparent, für Toolbars)."""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {TEXT_PRIMARY};
            border: none;
            border-radius: {RADIUS_MD};
            padding: {SPACING_SM} {SPACING_MD};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
        }}
        QPushButton:hover {{
            background-color: {PRIMARY_100};
        }}
        QPushButton:pressed {{
            background-color: {PRIMARY_500};
            color: {TEXT_INVERSE};
        }}
        QPushButton:disabled {{
            color: {TEXT_DISABLED};
        }}
    """

def get_button_danger_style() -> str:
    """Danger Button-Style (Rot Border) - für destruktive Aktionen."""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {ERROR};
            border: 1px solid {ERROR};
            border-radius: {RADIUS_MD};
            padding: {SPACING_SM} {SPACING_MD};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}
        QPushButton:hover {{
            background-color: {ERROR_LIGHT};
        }}
        QPushButton:pressed {{
            background-color: {ERROR};
            color: {TEXT_INVERSE};
        }}
        QPushButton:disabled {{
            border-color: {PRIMARY_100};
            color: {TEXT_DISABLED};
        }}
    """

def get_table_style() -> str:
    """Einheitliches Tabellen-Styling."""
    return f"""
        QTableWidget {{
            background-color: {BG_PRIMARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            gridline-color: {BORDER_DEFAULT};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
        }}
        QTableWidget::item {{
            padding: {SPACING_SM};
            border-bottom: 1px solid {BORDER_DEFAULT};
        }}
        QTableWidget::item:selected {{
            background-color: {PRIMARY_100};
            color: {TEXT_PRIMARY};
        }}
        QTableWidget::item:hover {{
            background-color: {BG_TERTIARY};
        }}
        QHeaderView::section {{
            background-color: {BG_SECONDARY};
            color: {TEXT_PRIMARY};
            padding: {SPACING_SM} {SPACING_MD};
            border: none;
            border-bottom: 2px solid {BORDER_DEFAULT};
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}
    """

def get_input_style() -> str:
    """Einheitliches Input-Styling."""
    return f"""
        QLineEdit, QTextEdit, QComboBox {{
            background-color: {BG_PRIMARY};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            padding: {SPACING_SM};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border-color: {ACCENT_500};
            outline: none;
        }}
        QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
            background-color: {BG_SECONDARY};
            color: {TEXT_DISABLED};
        }}
    """

def get_sidebar_style() -> str:
    """Sidebar-Styling (dunkler Hintergrund)."""
    return f"""
        QFrame#sidebar {{
            background-color: {SIDEBAR_BG};
            border: none;
        }}
        QFrame#sidebar QLabel {{
            color: {SIDEBAR_TEXT};
            font-family: {FONT_BODY};
        }}
        QFrame#sidebar QLabel#sidebarTitle {{
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
        }}
    """

def get_dialog_style() -> str:
    """Einheitliches Dialog-Styling."""
    return f"""
        QDialog {{
            background-color: {BG_PRIMARY};
        }}
        QDialog QLabel {{
            color: {TEXT_PRIMARY};
            font-family: {FONT_BODY};
        }}
        QDialog QLabel#dialogTitle {{
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {TEXT_PRIMARY};
            padding-bottom: {SPACING_MD};
        }}
    """


# =============================================================================
# KOMPLETTES STYLESHEET (für QApplication)
# =============================================================================

def get_application_stylesheet() -> str:
    """
    Generiert das komplette Stylesheet für die Anwendung.
    Wird in src/main.py verwendet: app.setStyleSheet(get_application_stylesheet())
    """
    return f"""
        /* ================================================================== */
        /* GLOBALE STYLES                                                     */
        /* ================================================================== */
        
        * {{
            font-family: {FONT_BODY};
        }}
        
        QMainWindow {{
            background-color: {BG_PRIMARY};
        }}
        
        QWidget {{
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {TEXT_PRIMARY};
        }}
        
        /* ================================================================== */
        /* MENUBAR                                                            */
        /* ================================================================== */
        
        QMenuBar {{
            background-color: {BG_SECONDARY};
            border-bottom: 1px solid {BORDER_DEFAULT};
            padding: 2px;
        }}
        
        QMenuBar::item {{
            padding: 6px 12px;
            background: transparent;
        }}
        
        QMenuBar::item:selected {{
            background-color: {PRIMARY_100};
            border-radius: {RADIUS_SM};
        }}
        
        QMenu {{
            background-color: {BG_PRIMARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            padding: 4px;
        }}
        
        QMenu::item {{
            padding: 8px 24px;
            border-radius: {RADIUS_SM};
        }}
        
        QMenu::item:selected {{
            background-color: {PRIMARY_100};
        }}
        
        QMenu::separator {{
            height: 1px;
            background-color: {BORDER_DEFAULT};
            margin: 4px 8px;
        }}
        
        /* ================================================================== */
        /* STATUSBAR                                                          */
        /* ================================================================== */
        
        QStatusBar {{
            background-color: {BG_SECONDARY};
            border-top: 1px solid {BORDER_DEFAULT};
            color: {TEXT_SECONDARY};
            font-size: {FONT_SIZE_CAPTION};
        }}
        
        /* ================================================================== */
        /* SCROLLBARS                                                         */
        /* ================================================================== */
        
        QScrollBar:vertical {{
            background-color: {BG_SECONDARY};
            width: 12px;
            border-radius: 6px;
            margin: 2px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {PRIMARY_500};
            border-radius: 5px;
            min-height: 30px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {PRIMARY_900};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QScrollBar:horizontal {{
            background-color: {BG_SECONDARY};
            height: 12px;
            border-radius: 6px;
            margin: 2px;
        }}
        
        QScrollBar::handle:horizontal {{
            background-color: {PRIMARY_500};
            border-radius: 5px;
            min-width: 30px;
        }}
        
        QScrollBar::handle:horizontal:hover {{
            background-color: {PRIMARY_900};
        }}
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        
        /* ================================================================== */
        /* SPLITTER                                                           */
        /* ================================================================== */
        
        QSplitter::handle {{
            background-color: {BORDER_DEFAULT};
        }}
        
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        
        QSplitter::handle:vertical {{
            height: 2px;
        }}
        
        QSplitter::handle:hover {{
            background-color: {PRIMARY_500};
        }}
        
        /* ================================================================== */
        /* TABWIDGET                                                          */
        /* ================================================================== */
        
        QTabWidget::pane {{
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            background-color: {BG_PRIMARY};
        }}
        
        QTabBar::tab {{
            background-color: {BG_SECONDARY};
            color: {TEXT_SECONDARY};
            padding: 8px 16px;
            border: none;
            border-bottom: 2px solid transparent;
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
        }}
        
        QTabBar::tab:selected {{
            color: {TEXT_PRIMARY};
            border-bottom-color: {ACCENT_500};
            background-color: {BG_PRIMARY};
        }}
        
        QTabBar::tab:hover:!selected {{
            background-color: {PRIMARY_100};
        }}
        
        /* ================================================================== */
        /* TOOLTIPS                                                           */
        /* ================================================================== */
        
        QToolTip {{
            background-color: #fffdf5;
            color: #1a1a1a;
            border: 1px solid {ACCENT_500};
            border-radius: {RADIUS_SM};
            padding: 8px 12px;
            font-size: {FONT_SIZE_BODY};
            font-weight: 500;
        }}
        
        /* ================================================================== */
        /* GROUPBOX                                                           */
        /* ================================================================== */
        
        QGroupBox {{
            font-family: {FONT_BODY};
            font-weight: {FONT_WEIGHT_MEDIUM};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            margin-top: 12px;
            padding-top: 8px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            color: {TEXT_PRIMARY};
        }}
        
        /* ================================================================== */
        /* CHECKBOX & RADIOBUTTON                                             */
        /* ================================================================== */
        
        QCheckBox, QRadioButton {{
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {TEXT_PRIMARY};
            spacing: 8px;
        }}
        
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 16px;
            height: 16px;
        }}
        
        QCheckBox::indicator:unchecked {{
            border: 2px solid {BORDER_STRONG};
            border-radius: 3px;
            background-color: {BG_PRIMARY};
        }}
        
        QCheckBox::indicator:checked {{
            border: 2px solid {ACCENT_500};
            border-radius: 3px;
            background-color: {ACCENT_500};
        }}
        
        QRadioButton::indicator:unchecked {{
            border: 2px solid {BORDER_STRONG};
            border-radius: 8px;
            background-color: {BG_PRIMARY};
        }}
        
        QRadioButton::indicator:checked {{
            border: 2px solid {ACCENT_500};
            border-radius: 8px;
            background-color: {ACCENT_500};
        }}
        
        /* ================================================================== */
        /* PROGRESSBAR                                                        */
        /* ================================================================== */
        
        QProgressBar {{
            border: none;
            border-radius: {RADIUS_SM};
            background-color: {BG_SECONDARY};
            text-align: center;
            font-size: {FONT_SIZE_CAPTION};
            color: {TEXT_PRIMARY};
        }}
        
        QProgressBar::chunk {{
            background-color: {ACCENT_500};
            border-radius: {RADIUS_SM};
        }}
        
        /* ================================================================== */
        /* INPUTS                                                             */
        /* ================================================================== */
        
        QLineEdit {{
            background-color: {BG_PRIMARY};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            padding: 8px 12px;
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            selection-background-color: {PRIMARY_100};
        }}
        
        QLineEdit:focus {{
            border-color: {ACCENT_500};
        }}
        
        QLineEdit:disabled {{
            background-color: {BG_SECONDARY};
            color: {TEXT_DISABLED};
        }}
        
        QTextEdit {{
            background-color: {BG_PRIMARY};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            padding: 8px;
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            selection-background-color: {PRIMARY_100};
        }}
        
        QTextEdit:focus {{
            border-color: {ACCENT_500};
        }}
        
        QComboBox {{
            background-color: {BG_PRIMARY};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            padding: 8px 12px;
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
        }}
        
        QComboBox:focus {{
            border-color: {ACCENT_500};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {BG_PRIMARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            selection-background-color: {PRIMARY_100};
        }}
        
        /* ================================================================== */
        /* TABLES                                                             */
        /* ================================================================== */
        
        QTableWidget, QTableView {{
            background-color: {BG_PRIMARY};
            alternate-background-color: {BG_TERTIARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            gridline-color: {BORDER_DEFAULT};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            selection-background-color: {PRIMARY_100};
            selection-color: {TEXT_PRIMARY};
        }}
        
        QTableWidget::item, QTableView::item {{
            padding: 8px;
            border-bottom: 1px solid {BORDER_DEFAULT};
        }}
        
        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {PRIMARY_100};
            color: {TEXT_PRIMARY};
        }}
        
        QTableWidget::item:hover, QTableView::item:hover {{
            background-color: {BG_SECONDARY};
        }}
        
        QHeaderView::section {{
            background-color: {BG_SECONDARY};
            color: {TEXT_PRIMARY};
            padding: 10px 12px;
            border: none;
            border-bottom: 2px solid {BORDER_DEFAULT};
            font-weight: {FONT_WEIGHT_MEDIUM};
            font-family: {FONT_BODY};
        }}
        
        QHeaderView::section:hover {{
            background-color: {PRIMARY_100};
        }}
        
        /* ================================================================== */
        /* TREE WIDGET                                                        */
        /* ================================================================== */
        
        QTreeWidget, QTreeView {{
            background-color: {BG_PRIMARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            selection-background-color: {PRIMARY_100};
        }}
        
        QTreeWidget::item, QTreeView::item {{
            padding: 6px 8px;
            border-radius: {RADIUS_SM};
        }}
        
        QTreeWidget::item:selected, QTreeView::item:selected {{
            background-color: {PRIMARY_100};
            color: {TEXT_PRIMARY};
        }}
        
        QTreeWidget::item:hover, QTreeView::item:hover {{
            background-color: {BG_SECONDARY};
        }}
        
        /* ================================================================== */
        /* LIST WIDGET                                                        */
        /* ================================================================== */
        
        QListWidget, QListView {{
            background-color: {BG_PRIMARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            selection-background-color: {PRIMARY_100};
        }}
        
        QListWidget::item, QListView::item {{
            padding: 8px 12px;
            border-bottom: 1px solid {BORDER_DEFAULT};
        }}
        
        QListWidget::item:selected, QListView::item:selected {{
            background-color: {PRIMARY_100};
            color: {TEXT_PRIMARY};
        }}
        
        QListWidget::item:hover, QListView::item:hover {{
            background-color: {BG_SECONDARY};
        }}
        
        /* ================================================================== */
        /* BUTTONS (Default - Secondary Style)                                */
        /* ================================================================== */
        
        QPushButton {{
            background-color: transparent;
            color: {PRIMARY_900};
            border: 1px solid {PRIMARY_900};
            border-radius: {RADIUS_MD};
            padding: 8px 16px;
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}
        
        QPushButton:hover {{
            background-color: {PRIMARY_100};
        }}
        
        QPushButton:pressed {{
            background-color: {PRIMARY_500};
            color: {TEXT_INVERSE};
        }}
        
        QPushButton:disabled {{
            border-color: {BORDER_DEFAULT};
            color: {TEXT_DISABLED};
        }}
        
        /* ================================================================== */
        /* DIALOG                                                             */
        /* ================================================================== */
        
        QDialog {{
            background-color: {BG_PRIMARY};
        }}
        
        QMessageBox {{
            background-color: {BG_PRIMARY};
        }}
        
        QMessageBox QLabel {{
            color: {TEXT_PRIMARY};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
        }}
    """


# =============================================================================
# ERROR DIALOG HELPER
# =============================================================================

def show_error_dialog(parent, title: str, cause: str, actions: list = None, 
                      retry_callback=None) -> bool:
    """
    Zeigt einen strukturierten Fehler-Dialog im ACENCIA Design.
    
    Args:
        parent: Parent-Widget
        title: Kurzer Fehlertitel
        cause: Technische Ursache des Fehlers
        actions: Liste von Handlungsvorschlägen (Strings)
        retry_callback: Optional - Funktion die bei "Erneut versuchen" aufgerufen wird
    
    Returns:
        True wenn "Erneut versuchen" geklickt wurde, sonst False
    
    Beispiel:
        show_error_dialog(
            self,
            "Verbindung zum Server fehlgeschlagen",
            "Server antwortet nicht (Timeout nach 30s)",
            [
                "Internetverbindung prüfen",
                "Server-Status unter status.acencia.info prüfen"
            ],
            retry_callback=self._retry_connection
        )
    """
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
    from PySide6.QtCore import Qt
    
    dialog = QDialog(parent)
    dialog.setWindowTitle("Fehler")
    dialog.setMinimumWidth(450)
    dialog.setStyleSheet(f"""
        QDialog {{
            background-color: {BG_PRIMARY};
        }}
        QLabel {{
            color: {TEXT_PRIMARY};
            font-family: {FONT_BODY};
        }}
    """)
    
    layout = QVBoxLayout(dialog)
    layout.setSpacing(16)
    layout.setContentsMargins(24, 24, 24, 24)
    
    # Titel mit Warnsymbol
    title_label = QLabel(f"⚠ {title}")
    title_label.setStyleSheet(f"""
        font-family: {FONT_HEADLINE};
        font-size: 12pt;
        color: {ERROR};
        font-weight: 500;
    """)
    layout.addWidget(title_label)
    
    # Ursache
    cause_container = QVBoxLayout()
    cause_header = QLabel("Ursache:")
    cause_header.setStyleSheet(f"""
        font-size: {FONT_SIZE_CAPTION};
        color: {TEXT_SECONDARY};
        font-weight: 500;
    """)
    cause_container.addWidget(cause_header)
    
    cause_text = QLabel(cause)
    cause_text.setWordWrap(True)
    cause_text.setStyleSheet(f"""
        font-size: {FONT_SIZE_BODY};
        color: {TEXT_PRIMARY};
        padding-left: 8px;
    """)
    cause_container.addWidget(cause_text)
    layout.addLayout(cause_container)
    
    # Handlungsvorschläge
    if actions:
        actions_container = QVBoxLayout()
        actions_header = QLabel("Mögliche Handlungen:")
        actions_header.setStyleSheet(f"""
            font-size: {FONT_SIZE_CAPTION};
            color: {TEXT_SECONDARY};
            font-weight: 500;
        """)
        actions_container.addWidget(actions_header)
        
        for action in actions:
            action_label = QLabel(f"• {action}")
            action_label.setStyleSheet(f"""
                font-size: {FONT_SIZE_BODY};
                color: {TEXT_PRIMARY};
                padding-left: 8px;
            """)
            actions_container.addWidget(action_label)
        
        layout.addLayout(actions_container)
    
    # Buttons
    button_layout = QHBoxLayout()
    button_layout.addStretch()
    
    close_btn = QPushButton("Schließen")
    close_btn.setStyleSheet(get_button_secondary_style())
    close_btn.clicked.connect(dialog.reject)
    button_layout.addWidget(close_btn)
    
    retry_clicked = [False]  # Mutable für Closure
    
    if retry_callback:
        retry_btn = QPushButton("Erneut versuchen")
        retry_btn.setStyleSheet(get_button_primary_style())
        def on_retry():
            retry_clicked[0] = True
            dialog.accept()
            retry_callback()
        retry_btn.clicked.connect(on_retry)
        button_layout.addWidget(retry_btn)
    
    layout.addLayout(button_layout)
    
    dialog.exec()
    return retry_clicked[0]


# show_success_toast() wurde entfernt (v1.0.7).
# Verwende stattdessen ToastManager aus ui.toast:
#   from ui.toast import ToastManager
#   toast_manager.show_success("Nachricht")
# Siehe docs/ui/UX_RULES.md
