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
# ERWEITERTE SPEKTRUM-FARBEN (für Box-System, Charts, Status-Indikatoren)
# =============================================================================

AMBER        = "#f59e0b"   # Amber/Gold – Eingang, Duplikat-Warnung
ORANGE_WARM  = "#f97316"   # Warmes Orange – Verarbeitung
GREEN_EMERALD = "#10b981"  # Smaragdgrün – GDV-Box
INDIGO       = "#6366f1"   # Indigo – Courtage, Inhaltsduplikat
BLUE_BRIGHT  = "#3b82f6"   # Helles Blau – Sach-Versicherung
VIOLET       = "#8b5cf6"   # Violett – Leben-Versicherung, KI
CYAN         = "#06b6d4"   # Cyan – Kranken-Versicherung
SLATE        = "#64748b"   # Blaugrau – Sonstiges
STONE        = "#78716c"   # Steingrau – Roh/Archiv

# =============================================================================
# STATUS-FARBEN ERWEITERUNG (Quelltypen, KI, Duplikate, Critical)
# =============================================================================

STATUS_SCAN      = VIOLET           # Lila – Scan-Herkunft
STATUS_MAIL      = "#FF9800"        # Orange – Mail-Herkunft
STATUS_AI_ACTIVE = VIOLET           # Lila – KI-verarbeitet

DUPLICATE_FILE    = AMBER           # Amber – Datei-Duplikat
DUPLICATE_CONTENT = INDIGO          # Indigo – Inhaltsduplikat

NEUTRAL_BORDER    = "#999999"       # Neutrales Grau – Borders in Color-Pickern

CRITICAL          = "#7c2d12"       # Dunkles Braun-Rot – schwerwiegende Fehler
CRITICAL_LIGHT    = "#fef2f2"       # Sehr helles Rot-Weiß – Critical-Hintergrund

MAINTENANCE_CARD_BG = "#0d3259"     # Dunkles Blau – Maintenance-Overlay-Karten

# Tooltip
TOOLTIP_BG   = "#fffdf5"
TOOLTIP_TEXT  = "#1a1a1a"

# Tabellen (Provision-spezifisch, leicht bläulich)
TABLE_ALT_BG        = "#f5f8fb"
TABLE_BORDER        = "#b0c4d8"
TABLE_GRID          = "#d5dfe8"
TABLE_SELECTED_BG   = "#d0dfed"
TABLE_HOVER_BG      = "#edf2f7"
TABLE_HEADER_BG     = "#d0dcea"
TABLE_HEADER_BORDER = "#98b3cb"
TABLE_HEADER_HOVER  = "#bfcfdf"

# Accent-Interaktionszustände
ACCENT_HOVER   = "#e88a2d"
ACCENT_PRESSED = "#d97706"

# Subtile Borders (rgba, theme-aware)
BORDER_SUBTLE = "rgba(136, 169, 195, 0.15)"

# =============================================================================
# CHART-FARBEN (Matplotlib / Statistik-Views)
# =============================================================================

CHART_PALETTE = [
    PRIMARY_900, ACCENT_500, PRIMARY_500, SUCCESS, ERROR,
    INDIGO, CYAN, VIOLET, AMBER, SLATE,
]
CHART_BG_COLOR   = BG_PRIMARY   # "#ffffff"
CHART_TEXT_COLOR = PRIMARY_900  # "#001f3d"
CHART_GRID_COLOR = PRIMARY_100  # "#e3ebf2"

# =============================================================================
# BOX-FARBEN (Dokumentenarchiv) - Harmonisch mit CI
# =============================================================================

BOX_COLORS = {
    "eingang":      AMBER,
    "verarbeitung": ORANGE_WARM,
    "gdv":          GREEN_EMERALD,
    "courtage":     INDIGO,
    "sach":         BLUE_BRIGHT,
    "leben":        VIOLET,
    "kranken":      CYAN,
    "sonstige":     SLATE,
    "roh":          STONE,
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
    "consulter":          {"bg": "#dbeafe", "text": "#1e40af"},
    "teamleiter":         {"bg": "#fff3e0", "text": "#e65100"},
    "backoffice":         {"bg": "#f3f4f6", "text": "#374151"},
    "geschaeftsfuehrer":  {"bg": "#ede9fe", "text": "#5b21b6"},
}

ART_BADGE_COLORS = {
    "ap":              {"bg": "#dbeafe", "text": "#1e40af"},
    "bp":              {"bg": "#e0e7ff", "text": "#3730a3"},
    "rueckbelastung":  {"bg": "#fee2e2", "text": "#991b1b"},
    "nullmeldung":     {"bg": "#fef3c7", "text": "#92400e"},
    "sonstige":        {"bg": "#f3f4f6", "text": "#374151"},
}


# =============================================================================
# TYPOGRAFIE - ACENCIA Fonts (OFFIZIELL)
# =============================================================================

# Font-Presets (umschaltbar ueber Einstellungen)
FONT_PRESETS = {
    "modern": {
        "headline": '"Libre Baskerville", "Tenor Sans", "Segoe UI", serif',
        "body": '"Zen Antique", "Open Sans", "Segoe UI", serif',
    },
    "classic": {
        "headline": '"Tenor Sans", "Segoe UI", -apple-system, sans-serif',
        "body": '"Open Sans", "Segoe UI", -apple-system, sans-serif',
    },
}

# Font-Familien (mit Fallbacks) - Standard: classic
FONT_HEADLINE = FONT_PRESETS["classic"]["headline"]
FONT_BODY = FONT_PRESETS["classic"]["body"]
FONT_MONO = '"Cascadia Code", "Consolas", monospace'


def apply_font_preset(preset_id: str):
    """Setzt FONT_HEADLINE und FONT_BODY gemaess dem gewaehlten Preset."""
    global FONT_HEADLINE, FONT_BODY
    preset = FONT_PRESETS.get(preset_id, FONT_PRESETS["classic"])
    FONT_HEADLINE = preset["headline"]
    FONT_BODY = preset["body"]


# =============================================================================
# DARK MODE
# =============================================================================

_LIGHT_COLORS = {
    "PRIMARY_900":  "#001f3d",
    "PRIMARY_500":  "#88a9c3",
    "PRIMARY_100":  "#e3ebf2",
    "PRIMARY_0":    "#ffffff",
    "ACCENT_500":   "#fa9939",
    "ACCENT_100":   "#f8dcbf",
    "TEXT_PRIMARY":     "#001f3d",
    "TEXT_SECONDARY":   "#88a9c3",
    "TEXT_DISABLED":    "#a0aec0",
    "TEXT_INVERSE":     "#ffffff",
    "BG_PRIMARY":       "#ffffff",
    "BG_SECONDARY":     "#e3ebf2",
    "BG_TERTIARY":      "#f8fafc",
    "BORDER_DEFAULT":   "#e3ebf2",
    "BORDER_STRONG":    "#88a9c3",
    "BORDER_FOCUS":     "#fa9939",
    "SIDEBAR_BG":       "#001f3d",
    "SIDEBAR_TEXT":     "#ffffff",
    "SIDEBAR_HOVER":    "rgba(136, 169, 195, 0.2)",
    "SHADOW_SM": "0 1px 2px rgba(0, 0, 0, 0.05)",
    "SHADOW_MD": "0 4px 6px rgba(0, 0, 0, 0.1)",
    "SHADOW_LG": "0 10px 15px rgba(0, 0, 0, 0.1)",
    "SUCCESS":       "#059669",
    "SUCCESS_LIGHT": "#d1fae5",
    "WARNING_LIGHT": "#f8dcbf",
    "ERROR":         "#dc2626",
    "ERROR_LIGHT":   "#fee2e2",
    "INFO_LIGHT":    "#e3ebf2",
    "CHART_BG":      "#ffffff",
    "CHART_TEXT":    "#001f3d",
    "CHART_GRID":    "#e3ebf2",
    "TOOLTIP_BG":    "#fffdf5",
    "TOOLTIP_TEXT":  "#1a1a1a",
    "TABLE_ALT_BG":        "#f5f8fb",
    "TABLE_BORDER":        "#b0c4d8",
    "TABLE_GRID":          "#d5dfe8",
    "TABLE_SELECTED_BG":   "#d0dfed",
    "TABLE_HOVER_BG":      "#edf2f7",
    "TABLE_HEADER_BG":     "#d0dcea",
    "TABLE_HEADER_BORDER": "#98b3cb",
    "TABLE_HEADER_HOVER":  "#bfcfdf",
    "ACCENT_HOVER":   "#e88a2d",
    "ACCENT_PRESSED": "#d97706",
    "BORDER_SUBTLE":  "rgba(136, 169, 195, 0.15)",
}

_DARK_COLORS = {
    "PRIMARY_900":  "#c9d8e6",
    "PRIMARY_500":  "#6a8eab",
    "PRIMARY_100":  "#1e2d3d",
    "PRIMARY_0":    "#0d1117",
    "ACCENT_500":   "#fa9939",
    "ACCENT_100":   "#5c3a15",
    "TEXT_PRIMARY":     "#e6edf3",
    "TEXT_SECONDARY":   "#8b949e",
    "TEXT_DISABLED":    "#484f58",
    "TEXT_INVERSE":     "#0d1117",
    "BG_PRIMARY":       "#0d1117",
    "BG_SECONDARY":     "#161b22",
    "BG_TERTIARY":      "#010409",
    "BORDER_DEFAULT":   "#30363d",
    "BORDER_STRONG":    "#484f58",
    "BORDER_FOCUS":     "#fa9939",
    "SIDEBAR_BG":       "#010409",
    "SIDEBAR_TEXT":     "#e6edf3",
    "SIDEBAR_HOVER":    "rgba(110, 118, 129, 0.25)",
    "SHADOW_SM": "0 1px 3px rgba(0, 0, 0, 0.3)",
    "SHADOW_MD": "0 4px 8px rgba(0, 0, 0, 0.4)",
    "SHADOW_LG": "0 10px 20px rgba(0, 0, 0, 0.5)",
    "SUCCESS":       "#3fb950",
    "SUCCESS_LIGHT": "#0f2d16",
    "WARNING_LIGHT": "#3d2004",
    "ERROR":         "#f85149",
    "ERROR_LIGHT":   "#3d0c0c",
    "INFO_LIGHT":    "#0d2744",
    "CHART_BG":      "#0d1117",
    "CHART_TEXT":    "#e6edf3",
    "CHART_GRID":    "#30363d",
    "TOOLTIP_BG":    "#21262d",
    "TOOLTIP_TEXT":  "#e6edf3",
    "TABLE_ALT_BG":        "#161b22",
    "TABLE_BORDER":        "#30363d",
    "TABLE_GRID":          "#21262d",
    "TABLE_SELECTED_BG":   "#1c3a5c",
    "TABLE_HOVER_BG":      "#1c2533",
    "TABLE_HEADER_BG":     "#1c2332",
    "TABLE_HEADER_BORDER": "#344b63",
    "TABLE_HEADER_HOVER":  "#243040",
    "ACCENT_HOVER":   "#e88a2d",
    "ACCENT_PRESSED": "#d97706",
    "BORDER_SUBTLE":  "rgba(110, 118, 129, 0.15)",
}

_CURRENT_THEME = "light"


def get_current_theme() -> str:
    """Gibt das aktuell aktive Theme zurueck ('light' oder 'dark')."""
    return _CURRENT_THEME


def apply_theme(theme: str) -> None:
    """Aktiviert 'light' oder 'dark' Theme und aktualisiert alle Modul-Variablen."""
    global _CURRENT_THEME
    global PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0
    global ACCENT_500, ACCENT_100
    global TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED, TEXT_INVERSE
    global BG_PRIMARY, BG_SECONDARY, BG_TERTIARY
    global BORDER_DEFAULT, BORDER_STRONG, BORDER_FOCUS
    global SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER, SIDEBAR_ACTIVE_BORDER
    global SHADOW_SM, SHADOW_MD, SHADOW_LG
    global SUCCESS, SUCCESS_500, SUCCESS_LIGHT
    global WARNING, WARNING_500, WARNING_LIGHT
    global ERROR, ERROR_500, ERROR_LIGHT, DANGER_500
    global INFO, INFO_500, INFO_LIGHT
    global CHART_BG_COLOR, CHART_TEXT_COLOR, CHART_GRID_COLOR
    global TOOLTIP_BG, TOOLTIP_TEXT
    global TABLE_ALT_BG, TABLE_BORDER, TABLE_GRID
    global TABLE_SELECTED_BG, TABLE_HOVER_BG
    global TABLE_HEADER_BG, TABLE_HEADER_BORDER, TABLE_HEADER_HOVER
    global ACCENT_HOVER, ACCENT_PRESSED
    global BORDER_SUBTLE

    _CURRENT_THEME = theme
    c = _DARK_COLORS if theme == "dark" else _LIGHT_COLORS

    PRIMARY_900 = c["PRIMARY_900"]
    PRIMARY_500 = c["PRIMARY_500"]
    PRIMARY_100 = c["PRIMARY_100"]
    PRIMARY_0   = c["PRIMARY_0"]
    ACCENT_500  = c["ACCENT_500"]
    ACCENT_100  = c["ACCENT_100"]

    TEXT_PRIMARY   = c["TEXT_PRIMARY"]
    TEXT_SECONDARY = c["TEXT_SECONDARY"]
    TEXT_DISABLED  = c["TEXT_DISABLED"]
    TEXT_INVERSE   = c["TEXT_INVERSE"]

    BG_PRIMARY   = c["BG_PRIMARY"]
    BG_SECONDARY = c["BG_SECONDARY"]
    BG_TERTIARY  = c["BG_TERTIARY"]

    BORDER_DEFAULT = c["BORDER_DEFAULT"]
    BORDER_STRONG  = c["BORDER_STRONG"]
    BORDER_FOCUS   = c["BORDER_FOCUS"]

    SIDEBAR_BG    = c["SIDEBAR_BG"]
    SIDEBAR_TEXT   = c["SIDEBAR_TEXT"]
    SIDEBAR_HOVER  = c["SIDEBAR_HOVER"]

    SHADOW_SM = c["SHADOW_SM"]
    SHADOW_MD = c["SHADOW_MD"]
    SHADOW_LG = c["SHADOW_LG"]

    SUCCESS       = c["SUCCESS"]
    SUCCESS_500   = SUCCESS
    SUCCESS_LIGHT = c["SUCCESS_LIGHT"]
    WARNING       = ACCENT_500
    WARNING_500   = WARNING
    WARNING_LIGHT = c["WARNING_LIGHT"]
    ERROR         = c["ERROR"]
    ERROR_500     = ERROR
    ERROR_LIGHT   = c["ERROR_LIGHT"]
    DANGER_500    = ERROR
    INFO          = PRIMARY_500
    INFO_500      = INFO
    INFO_LIGHT    = c["INFO_LIGHT"]

    CHART_BG_COLOR   = c["CHART_BG"]
    CHART_TEXT_COLOR  = c["CHART_TEXT"]
    CHART_GRID_COLOR = c["CHART_GRID"]

    SIDEBAR_ACTIVE_BORDER = ACCENT_500

    TOOLTIP_BG   = c["TOOLTIP_BG"]
    TOOLTIP_TEXT  = c["TOOLTIP_TEXT"]

    TABLE_ALT_BG        = c["TABLE_ALT_BG"]
    TABLE_BORDER        = c["TABLE_BORDER"]
    TABLE_GRID          = c["TABLE_GRID"]
    TABLE_SELECTED_BG   = c["TABLE_SELECTED_BG"]
    TABLE_HOVER_BG      = c["TABLE_HOVER_BG"]
    TABLE_HEADER_BG     = c["TABLE_HEADER_BG"]
    TABLE_HEADER_BORDER = c["TABLE_HEADER_BORDER"]
    TABLE_HEADER_HOVER  = c["TABLE_HEADER_HOVER"]

    ACCENT_HOVER   = c["ACCENT_HOVER"]
    ACCENT_PRESSED = c["ACCENT_PRESSED"]

    BORDER_SUBTLE = c["BORDER_SUBTLE"]


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
RADIUS_XL = "12px"

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
    """Tabellen-Styling fuer Provisionsmanagement: kompakte Zeilen, gut lesbar."""
    return f"""
        QTableView {{
            background-color: {BG_PRIMARY};
            alternate-background-color: {TABLE_ALT_BG};
            border: 1.5px solid {TABLE_BORDER};
            border-radius: {RADIUS_LG};
            gridline-color: {TABLE_GRID};
            font-family: {FONT_BODY};
            font-size: 9.5pt;
            selection-background-color: {PRIMARY_100};
            selection-color: {TEXT_PRIMARY};
        }}
        QTableView::item {{
            padding: 6px 10px;
            border-bottom: 1px solid {TABLE_GRID};
        }}
        QTableView::item:selected {{
            background-color: {TABLE_SELECTED_BG};
            color: {TEXT_PRIMARY};
        }}
        QTableView::item:hover {{
            background-color: {TABLE_HOVER_BG};
        }}
        QHeaderView::section {{
            background-color: {TABLE_HEADER_BG};
            color: {PRIMARY_900};
            padding: 7px 10px;
            border: none;
            border-bottom: 2px solid {TABLE_HEADER_BORDER};
            font-weight: {FONT_WEIGHT_BOLD};
            font-family: {FONT_BODY};
            font-size: 9pt;
        }}
        QHeaderView::section:hover {{
            background-color: {TABLE_HEADER_HOVER};
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
            background-color: {ACCENT_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {ACCENT_PRESSED};
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
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {TEXT_PRIMARY};
        }}
        
        QMenu::item {{
            padding: 8px 24px;
            border-radius: {RADIUS_SM};
            background-color: transparent;
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
            background-color: {TOOLTIP_BG};
            color: {TOOLTIP_TEXT};
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
            padding: 4px;
            outline: none;
        }}
        
        QComboBox QAbstractItemView::item {{
            padding: 6px 12px;
            border-radius: {RADIUS_SM};
            color: {TEXT_PRIMARY};
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
        }}
        
        QComboBox QAbstractItemView::item:selected {{
            background-color: {PRIMARY_100};
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
