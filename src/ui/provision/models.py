# -*- coding: utf-8 -*-
"""
QAbstractTableModel-Klassen fuer das Provisionsmanagement.

Extrahiert aus den Panel-Dateien fuer bessere Wartbarkeit.
Models nutzen i18n-Texte, Design-Tokens und format_eur aus widgets.
"""

import json

from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import QColor, QFont
from typing import List, Dict, Optional
from datetime import datetime

from domain.provision.entities import (
    Commission, Employee, Contract, VermittlerMapping,
    ContractSearchResult, BeraterAbrechnung, ImportBatch,
    DashboardSummary, PerformanceTeamMember, FreeCommission,
)
from ui.styles.tokens import (
    PRIMARY_500, SUCCESS, ERROR, WARNING,
    AMBER, BLUE_BRIGHT,
    ROLE_BADGE_COLORS, build_rich_tooltip,
)
from ui.provision.widgets import format_eur
from i18n import de as texts


# =============================================================================
# Helper-Funktionen (von Models aufgerufen)
# =============================================================================


def status_label(c) -> str:
    """Differenzierter Status-Text basierend auf match_status + berater_id."""
    if c.match_status in ('auto_matched', 'manual_matched', 'matched'):
        if c.berater_id:
            return texts.PROVISION_STATUS_ZUGEORDNET
        return texts.PROVISION_STATUS_VERTRAG_GEFUNDEN
    if c.match_status == 'unmatched':
        return texts.PROVISION_STATUS_OFFEN
    if c.match_status == 'ignored':
        return texts.PROVISION_STATUS_IGNORIERT
    if c.match_status == 'gesperrt':
        return texts.PROVISION_STATUS_GESPERRT
    return c.match_status


def status_pill_key(c) -> str:
    """Pill-Color-Key basierend auf match_status + berater_id."""
    if c.match_status in ('auto_matched', 'manual_matched', 'matched'):
        if c.berater_id:
            return 'zugeordnet'
        return 'vertrag_gefunden'
    if c.match_status == 'unmatched':
        return 'offen'
    if c.match_status == 'ignored':
        return 'ignoriert'
    if c.match_status == 'gesperrt':
        return 'gesperrt'
    return c.match_status


ART_LABELS = {
    'ap': texts.PROVISION_COMM_ART_AP,
    'bp': texts.PROVISION_COMM_ART_BP,
    'rueckbelastung': texts.PROVISION_COMM_ART_RUECK,
    'nullmeldung': texts.PROVISION_COMM_ART_NULL,
    'sonstige': texts.PROVISION_COMM_ART_SONSTIGE,
}


STATUS_LABELS = {
    'berechnet': texts.PROVISION_STATUS_ENTWURF,
    'geprueft': texts.PROVISION_STATUS_GEPRUEFT,
    'freigegeben': texts.PROVISION_STATUS_FREIGEGEBEN,
    'ausgezahlt': texts.PROVISION_STATUS_AUSGEZAHLT,
}


STATUS_PILL_MAP = {
    'berechnet': 'entwurf',
    'geprueft': 'geprueft',
    'freigegeben': 'freigegeben',
    'ausgezahlt': 'ausgezahlt',
}


def clearance_type(c) -> str:
    """Bestimmt den Klaerfall-Typ anhand von match_status und berater_id."""
    if c.match_status == 'unmatched':
        return texts.PROVISION_CLEAR_TYPE_NO_CONTRACT
    if c.match_status in ('auto_matched', 'manual_matched') and not c.berater_id:
        return texts.PROVISION_CLEAR_TYPE_NO_BERATER
    return texts.PROVISION_CLEAR_TYPE_NO_CONTRACT


def fmt_date(val: Optional[str]) -> str:
    if not val:
        return ''
    try:
        dt = datetime.strptime(val[:10], '%Y-%m-%d')
        return dt.strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        return val


def xempus_status_label(c: Contract) -> str:
    if c.provision_count and c.provision_count > 0:
        return texts.PROVISION_XEMPUS_STATUS_PAID
    if c.status == 'beantragt':
        return texts.PROVISION_XEMPUS_STATUS_APPLIED
    return texts.PROVISION_XEMPUS_STATUS_OPEN


def xempus_status_key(c: Contract) -> str:
    if c.provision_count and c.provision_count > 0:
        return 'zugeordnet'
    if c.status == 'beantragt':
        return 'beantragt'
    return 'offen'


# =============================================================================
# Dashboard
# =============================================================================


class BeraterRankingModel(QAbstractTableModel):
    COLUMNS = [
        texts.PROVISION_DASH_COL_NAME,
        texts.PROVISION_DASH_COL_ROLE,
        texts.PROVISION_DASH_COL_BRUTTO,
        texts.PROVISION_DASH_COL_TL_ABZUG,
        texts.PROVISION_DASH_COL_NETTO,
        texts.PROVISION_DASH_COL_AG,
        texts.PROVISION_DASH_COL_RUECK,
    ]

    TOOLTIPS = [
        texts.PROVISION_TIP_COL_BERATER,
        "",
        build_rich_tooltip(
            texts.PROVISION_TIP_COL_BETRAG,
            quelle=texts.PROVISION_DASH_TOTAL_TIP_SRC,
        ),
        build_rich_tooltip(
            texts.PROVISION_TIP_COL_TL_ANTEIL,
        ),
        build_rich_tooltip(
            texts.PROVISION_TIP_NETTO_DEF,
            berechnung=texts.PROVISION_TIP_NETTO_CALC,
        ),
        build_rich_tooltip(
            texts.PROVISION_TIP_COL_AG_ANTEIL,
        ),
        build_rich_tooltip(
            texts.PROVISION_TIP_RUECK_DEF,
        ),
    ]

    def __init__(self):
        super().__init__()
        self._data: List[Dict] = []

    def set_data(self, data: List[Dict]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.COLUMNS[section]
            if role == Qt.ToolTipRole and section < len(self.TOOLTIPS):
                return self.TOOLTIPS[section] or None
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return row.get('name', '')
            elif col == 1:
                r = row.get('role', '')
                return {
                    'consulter': texts.PROVISION_EMP_ROLE_CONSULTER,
                    'teamleiter': texts.PROVISION_EMP_ROLE_TEAMLEITER,
                    'backoffice': texts.PROVISION_EMP_ROLE_BACKOFFICE,
                }.get(r, r)
            elif col == 2:
                return format_eur(row.get('brutto', 0))
            elif col == 3:
                return format_eur(row.get('tl_abzug', 0))
            elif col == 4:
                return format_eur(row.get('berater_netto', 0))
            elif col == 5:
                return format_eur(row.get('ag_anteil', 0))
            elif col == 6:
                return format_eur(row.get('rueckbelastung', 0))

        if role == Qt.ForegroundRole:
            if col == 6:
                val = float(row.get('rueckbelastung', 0))
                if val < 0:
                    return QColor(ERROR)
            if col == 3:
                val = float(row.get('tl_abzug', 0))
                if val < 0:
                    return QColor(ERROR)

        if role == Qt.TextAlignmentRole and col >= 2:
            return Qt.AlignRight | Qt.AlignVCenter

        return None


# =============================================================================
# Erfolgsauswertung / Performance
# =============================================================================


class FuehrungskraftModel(QAbstractTableModel):
    """Team-Tabelle im Fuehrungskraft-Tab der Erfolgsauswertung."""

    COLUMNS = [
        texts.PM_PERF_TEAM_COL_NAME,
        texts.PM_PERF_TEAM_COL_BRUTTO_MONAT,
        texts.PM_PERF_TEAM_COL_NETTO_MONAT,
        texts.PM_PERF_TEAM_COL_BRUTTO_YTD,
        texts.PM_PERF_TEAM_COL_NETTO_YTD,
        texts.PM_PERF_TEAM_COL_STORNOQUOTE,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[PerformanceTeamMember] = []
        self._display_cache: List[List[str]] = []

    def set_data(self, data: List[PerformanceTeamMember]):
        self.beginResetModel()
        self._data = data
        self._display_cache = []
        for m in data:
            self._display_cache.append([
                m.name,
                format_eur(m.brutto_monat),
                format_eur(m.netto_monat),
                format_eur(m.brutto_ytd),
                format_eur(m.netto_ytd),
                f"{m.stornoquote_betrag:.1f} %",
            ])
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        col = index.column()
        if role == Qt.DisplayRole:
            return self._display_cache[index.row()][col]
        if role == Qt.TextAlignmentRole and col >= 1:
            return Qt.AlignRight | Qt.AlignVCenter
        return None


# =============================================================================
# Abrechnungslaeufe (VU-Import Batches)
# =============================================================================


class VuBatchesModel(QAbstractTableModel):
    COLUMNS = [
        texts.PROVISION_RUN_COL_VU,
        texts.PROVISION_RUN_COL_ZEITRAUM,
        texts.PROVISION_RUN_COL_IMPORT_DATE,
        texts.PROVISION_RUN_COL_TOTAL,
        texts.PROVISION_RUN_COL_MATCHED,
        texts.PROVISION_RUN_COL_CLEARANCE,
        texts.PROVISION_RUN_COL_STATUS,
    ]

    TOOLTIPS = [
        texts.PROVISION_TIP_COL_VERSICHERER,
        "",
        "",
        "",
        "",
        "",
        build_rich_tooltip(
            "Aktueller Pruefstatus des Abrechnungslaufs",
            hinweis=f"Entwurf: {texts.PROVISION_RUN_STATUS_ENTWURF_TIP}; "
                    f"In Pruefung: {texts.PROVISION_RUN_STATUS_PRUEFUNG_TIP}; "
                    f"Abgeschlossen: {texts.PROVISION_RUN_STATUS_DONE_TIP}",
        ),
    ]

    def __init__(self):
        super().__init__()
        self._data: List[ImportBatch] = []

    def set_data(self, data: List[ImportBatch]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.COLUMNS[section]
            if role == Qt.ToolTipRole and section < len(self.TOOLTIPS):
                return self.TOOLTIPS[section] or None
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        b = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return b.vu_name or b.source_type
            elif col == 1:
                return b.sheet_name or ""
            elif col == 2:
                d = b.created_at or ""
                if len(d) >= 10:
                    try:
                        dt = datetime.strptime(d[:10], "%Y-%m-%d")
                        return dt.strftime("%d.%m.%Y")
                    except ValueError:
                        pass
                return d
            elif col == 3:
                return str(b.total_rows)
            elif col == 4:
                return str(b.matched_rows)
            elif col == 5:
                clearance = b.total_rows - b.matched_rows - b.skipped_rows
                return str(max(0, clearance))
            elif col == 6:
                if b.matched_rows == b.total_rows:
                    return texts.PROVISION_RUN_STATUS_DONE
                elif b.matched_rows > 0:
                    return texts.PROVISION_RUN_STATUS_PRUEFUNG
                return texts.PROVISION_RUN_STATUS_ENTWURF

        if role == Qt.TextAlignmentRole and col in (3, 4, 5):
            return Qt.AlignRight | Qt.AlignVCenter

        return None


# =============================================================================
# Provisionspositionen
# =============================================================================


def build_positions_cache(data: List[Commission]):
    """Baut Display- und Tooltip-Caches fuer PositionsModel. Thread-safe (keine Qt-Calls)."""
    display: List[List[str]] = []
    tooltips: List[Dict[int, str]] = []
    ncols = 11
    COL_DATUM, COL_VU, COL_VSNR, COL_KUNDE = 0, 1, 2, 3
    COL_BETRAG, COL_BUCHUNGSART, COL_XEMPUS_BERATER, COL_BERATER = 4, 5, 6, 7
    COL_STATUS, COL_BERATER_ANTEIL, COL_MENU = 8, 9, 10

    for c in data:
        row = [''] * ncols
        tips: Dict[int, str] = {}

        d = c.auszahlungsdatum or ""
        if len(d) >= 10:
            try:
                dt = datetime.strptime(d[:10], "%Y-%m-%d")
                row[COL_DATUM] = dt.strftime("%d.%m.%Y")
            except ValueError:
                row[COL_DATUM] = d
        else:
            row[COL_DATUM] = d

        row[COL_VU] = c.vu_name or c.versicherer or ""
        row[COL_VSNR] = c.vsnr or ""
        row[COL_KUNDE] = c.versicherungsnehmer or ""

        label = format_eur(c.effective_amount)
        if c.is_overridden:
            label += " *"
        row[COL_BETRAG] = label
        if c.is_overridden:
            tips[COL_BETRAG] = texts.PM_OVERRIDE_TOOLTIP.format(
                original=format_eur(c.betrag),
                settled=format_eur(c.amount_settled),
            )

        row[COL_BUCHUNGSART] = c.buchungsart_raw or ART_LABELS.get(c.art, c.art)
        row[COL_XEMPUS_BERATER] = c.xempus_berater_name or "\u2014"
        row[COL_BERATER] = c.berater_name or "\u2014"
        row[COL_STATUS] = status_label(c)
        row[COL_BERATER_ANTEIL] = format_eur(c.berater_anteil) if c.berater_anteil is not None else ""
        row[COL_MENU] = "\U0001f4dd" if c.has_note else ""
        if c.has_note:
            snippet = (c.note[:80] + "...") if len(c.note or '') > 80 else (c.note or '')
            tips[COL_MENU] = snippet

        display.append(row)
        tooltips.append(tips)

    return display, tooltips


class PositionsModel(QAbstractTableModel):
    COL_DATUM = 0
    COL_VU = 1
    COL_VSNR = 2
    COL_KUNDE = 3
    COL_BETRAG = 4
    COL_BUCHUNGSART = 5
    COL_XEMPUS_BERATER = 6
    COL_BERATER = 7
    COL_STATUS = 8
    COL_BERATER_ANTEIL = 9
    COL_MENU = 10

    COLUMNS = [
        texts.PROVISION_POS_COL_DATUM,
        texts.PROVISION_POS_COL_VU,
        texts.PROVISION_POS_COL_VSNR,
        texts.PROVISION_POS_COL_KUNDE,
        texts.PROVISION_POS_COL_BETRAG,
        texts.PROVISION_POS_COL_BUCHUNGSART,
        texts.PROVISION_POS_COL_XEMPUS_BERATER,
        texts.PROVISION_POS_COL_BERATER,
        texts.PROVISION_POS_COL_STATUS,
        texts.PROVISION_POS_COL_BERATER_ANTEIL,
        "",
    ]

    TOOLTIPS = [
        texts.PROVISION_TIP_COL_DATUM,
        texts.PROVISION_TIP_COL_VERSICHERER,
        texts.PROVISION_TIP_COL_VSNR,
        texts.PROVISION_TIP_COL_KUNDE,
        build_rich_tooltip(texts.PROVISION_TIP_COL_BETRAG),
        texts.PROVISION_TIP_COL_BUCHUNGSART,
        texts.PROVISION_TIP_COL_XEMPUS_BERATER,
        texts.PROVISION_TIP_COL_BERATER,
        build_rich_tooltip(
            texts.PROVISION_TIP_COL_STATUS,
            hinweis=texts.PROVISION_TIP_STATUS_HINT,
        ),
        build_rich_tooltip(texts.PROVISION_TIP_COL_BERATER_ANTEIL),
        "",
    ]

    def __init__(self):
        super().__init__()
        self._data: List[Commission] = []
        self._display_cache: List[List[str]] = []
        self._tooltip_cache: List[Dict[int, str]] = []

    def set_data(self, data: List[Commission]):
        self.beginResetModel()
        self._data = data
        self._display_cache, self._tooltip_cache = build_positions_cache(data)
        self.endResetModel()

    def set_data_with_cache(self, data: List[Commission],
                            display_cache: List[List[str]],
                            tooltip_cache: List[Dict[int, str]]):
        """Setzt Daten mit vorberechneten Caches (O(1) auf Main-Thread)."""
        self.beginResetModel()
        self._data = data
        self._display_cache = display_cache
        self._tooltip_cache = tooltip_cache
        self.endResetModel()

    def get_commission(self, row: int) -> Optional[Commission]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.COLUMNS[section]
            if role == Qt.ToolTipRole and section < len(self.TOOLTIPS):
                return self.TOOLTIPS[section] or None
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole:
            return self._display_cache[row][col]

        if role == Qt.ToolTipRole:
            return self._tooltip_cache[row].get(col)

        c = self._data[row]

        if role == Qt.TextAlignmentRole:
            if col in (self.COL_BETRAG, self.COL_BERATER_ANTEIL):
                return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            if col == self.COL_BETRAG:
                if c.is_overridden:
                    return QColor(AMBER)
                if c.effective_amount < 0:
                    return QColor(ERROR)

        if role == Qt.FontRole:
            if col == self.COL_BETRAG and c.is_overridden:
                f = QFont()
                f.setItalic(True)
                return f

        if role == Qt.UserRole:
            return c

        if role == Qt.UserRole + 1:
            return getattr(c, 'is_relevant', True)

        return None


class PositionsFilterProxy(QSortFilterProxyModel):
    """Proxy mit globalem Freitext-Filter und pro-Spalte Column-Filtern.

    global_filter  – durchsucht ALLE Spalten (OR); mindestens eine muss matchen.
    column_filters – Dict[col_index, text]; JEDE gesetzte Spalte muss matchen (AND).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._global_filter: str = ""
        self._column_filters: Dict[int, str] = {}
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def set_global_filter(self, text: str) -> None:
        self._global_filter = text.strip().lower()
        self.invalidateFilter()

    def set_column_filter(self, column: int, text: str) -> None:
        cleaned = text.strip().lower()
        if cleaned:
            self._column_filters[column] = cleaned
        else:
            self._column_filters.pop(column, None)
        self.invalidateFilter()

    def clear_all_filters(self) -> None:
        self._global_filter = ""
        self._column_filters.clear()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return True

        if self._global_filter:
            found = False
            for col in range(model.columnCount()):
                idx = model.index(source_row, col, source_parent)
                val = model.data(idx, Qt.DisplayRole)
                if val is not None and self._global_filter in str(val).lower():
                    found = True
                    break
            if not found:
                return False

        for col, text in self._column_filters.items():
            idx = model.index(source_row, col, source_parent)
            val = model.data(idx, Qt.DisplayRole)
            if val is None or text not in str(val).lower():
                return False

        return True


# =============================================================================
# Zuordnung & Klaerfaelle
# =============================================================================


class UnmatchedModel(QAbstractTableModel):
    COL_VU = 0
    COL_VSNR = 1
    COL_KUNDE = 2
    COL_BETRAG = 3
    COL_XEMPUS_BERATER = 4
    COL_SOURCE = 5
    COL_PROBLEM = 6

    COLUMNS = [
        texts.PROVISION_POS_COL_VU,
        texts.PROVISION_POS_COL_VSNR,
        texts.PROVISION_POS_COL_KUNDE,
        texts.PROVISION_POS_COL_BETRAG,
        texts.PROVISION_POS_COL_XEMPUS_BERATER,
        texts.PROVISION_POS_COL_SOURCE,
        texts.PROVISION_CLEAR_PROBLEM,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[Commission] = []

    def set_data(self, data: List[Commission]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_item(self, row: int) -> Optional[Commission]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        c = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_VU:
                return c.versicherer or c.vu_name or ""
            elif col == self.COL_VSNR:
                return c.vsnr or ""
            elif col == self.COL_KUNDE:
                return c.versicherungsnehmer or ""
            elif col == self.COL_BETRAG:
                return format_eur(c.betrag)
            elif col == self.COL_XEMPUS_BERATER:
                return c.xempus_berater_name or "\u2014"
            elif col == self.COL_SOURCE:
                return c.source_label
            elif col == self.COL_PROBLEM:
                return clearance_type(c)

        if role == Qt.TextAlignmentRole and col == self.COL_BETRAG:
            return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.ForegroundRole and col == self.COL_BETRAG:
            if c.betrag < 0:
                return QColor(ERROR)

        if role == Qt.UserRole:
            return c

        return None


class MappingsModel(QAbstractTableModel):
    COLUMNS = [
        texts.PROVISION_MAP_COL_VU_NAME,
        texts.PROVISION_MAP_COL_BERATER,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[VermittlerMapping] = []

    def set_data(self, data: List[VermittlerMapping]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_item(self, row: int) -> Optional[VermittlerMapping]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        m = self._data[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return m.vermittler_name
            elif col == 1:
                return m.berater_name or f"ID {m.berater_id}"
        return None


class SuggestionsModel(QAbstractTableModel):
    COL_SCORE = 0
    COL_VSNR = 1
    COL_KUNDE = 2
    COL_VU = 3
    COL_SPARTE = 4
    COL_BERATER = 5
    COL_REASON = 6

    COLUMNS = [
        texts.PROVISION_MATCH_DLG_SCORE_LABEL,
        texts.PROVISION_POS_COL_VSNR,
        texts.PROVISION_POS_COL_KUNDE,
        texts.PROVISION_POS_COL_VU,
        texts.PROVISION_MATCH_DLG_COL_SPARTE,
        texts.PROVISION_POS_COL_BERATER,
        texts.PROVISION_MATCH_DLG_COL_REASON,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[ContractSearchResult] = []

    def set_data(self, data: List[ContractSearchResult]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_item(self, row: int) -> Optional[ContractSearchResult]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._data[index.row()]
        ct = item.contract
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_SCORE:
                return str(item.match_score)
            elif col == self.COL_VSNR:
                return ct.vsnr or "\u2014"
            elif col == self.COL_KUNDE:
                return ct.versicherungsnehmer or ""
            elif col == self.COL_VU:
                return ct.versicherer or ""
            elif col == self.COL_SPARTE:
                return ct.sparte or ""
            elif col == self.COL_BERATER:
                return ct.berater_name or "\u2014"
            elif col == self.COL_REASON:
                return item.match_reason or ''

        if role == Qt.TextAlignmentRole and col == self.COL_SCORE:
            return Qt.AlignCenter

        return None


# =============================================================================
# Verteilschluessel & Rollen
# =============================================================================


class DistEmployeeModel(QAbstractTableModel):
    COL_NAME = 0
    COL_ROLE = 1
    COL_MODEL = 2
    COL_RATE = 3
    COL_TL_RATE = 4
    COL_TL_BASIS = 5
    COL_TEAM = 6
    COL_ACTIVE = 7
    COL_USER = 8

    COLUMNS = [
        texts.PROVISION_DIST_EMP_COL_NAME,
        texts.PROVISION_DIST_EMP_COL_ROLE,
        texts.PROVISION_DIST_EMP_COL_MODEL,
        texts.PROVISION_DIST_EMP_COL_RATE,
        texts.PROVISION_DIST_EMP_COL_TL_RATE,
        texts.PROVISION_DIST_EMP_COL_TL_BASIS,
        texts.PROVISION_DIST_EMP_COL_TEAM,
        texts.PROVISION_DIST_EMP_COL_ACTIVE,
        texts.PM_EMP_USER_COL_HEADER,
    ]

    TOOLTIPS = [
        "",
        "",
        texts.PROVISION_DIST_EMP_TIP_MODEL,
        build_rich_tooltip(
            texts.PROVISION_DIST_EMP_TIP_RATE_DEF,
            berechnung=texts.PROVISION_DIST_EMP_TIP_RATE_CALC,
        ),
        build_rich_tooltip(
            texts.PROVISION_DIST_EMP_TIP_TL_RATE_DEF,
            berechnung=texts.PROVISION_DIST_EMP_TIP_TL_RATE_CALC,
        ),
        texts.PROVISION_DIST_EMP_COL_TL_BASIS_TIP,
        "",
        "",
        "",
    ]

    def __init__(self):
        super().__init__()
        self._data: List[Employee] = []

    def set_data(self, data: List[Employee]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_item(self, row: int) -> Optional[Employee]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.COLUMNS[section]
            if role == Qt.ToolTipRole and section < len(self.TOOLTIPS):
                return self.TOOLTIPS[section] or None
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_NAME:
                return e.name
            elif col == self.COL_ROLE:
                return {
                    'consulter': texts.PROVISION_EMP_ROLE_CONSULTER,
                    'teamleiter': texts.PROVISION_EMP_ROLE_TEAMLEITER,
                    'backoffice': texts.PROVISION_EMP_ROLE_BACKOFFICE,
                }.get(e.role, e.role)
            elif col == self.COL_MODEL:
                return e.model_name or "\u2014"
            elif col == self.COL_RATE:
                return f"{e.effective_rate:.1f}%"
            elif col == self.COL_TL_RATE:
                return f"{e.tl_override_rate:.1f}%" if e.tl_override_rate else "\u2014"
            elif col == self.COL_TL_BASIS:
                basis_labels = {
                    'berater_anteil': texts.PROVISION_EMP_DLG_TL_BASIS_BERATER,
                    'gesamt_courtage': texts.PROVISION_EMP_DLG_TL_BASIS_GESAMT,
                }
                return basis_labels.get(e.tl_override_basis, e.tl_override_basis)
            elif col == self.COL_TEAM:
                return e.teamleiter_name or "\u2014"
            elif col == self.COL_ACTIVE:
                return "\u2713" if e.is_active else "\u2717"
            elif col == self.COL_USER:
                if e.has_user:
                    return e.user_email or e.user_username or "\u2713"
                return "\u2014"

        if role == Qt.ToolTipRole and col == self.COL_USER:
            if e.has_user:
                if e.user_email:
                    return texts.PM_EMP_USER_LINKED.format(
                        username=e.user_username or '?', email=e.user_email)
                return texts.PM_EMP_USER_LINKED_NO_EMAIL.format(
                    username=e.user_username or '?')
            return texts.PM_EMP_USER_NONE

        if role == Qt.TextAlignmentRole:
            if col in (self.COL_RATE, self.COL_TL_RATE):
                return Qt.AlignRight | Qt.AlignVCenter
            if col in (self.COL_ACTIVE, self.COL_USER):
                return Qt.AlignCenter

        if role == Qt.ForegroundRole and col == self.COL_USER:
            from PySide6.QtGui import QColor
            if e.has_user:
                return QColor(SUCCESS)
            return QColor(PRIMARY_500)

        return None


# =============================================================================
# Auszahlungen & Reports
# =============================================================================


class AuszahlungenModel(QAbstractTableModel):
    COL_NAME = 0
    COL_ROLE = 1
    COL_BRUTTO = 2
    COL_TL = 3
    COL_NETTO = 4
    COL_RUECK = 5
    COL_KORREKTUR = 6
    COL_VU_ABZUG = 7
    COL_AUSZAHLUNG = 8
    COL_POS = 9
    COL_STATUS = 10
    COL_VERSION = 11
    COL_EMAIL = 12
    COL_MENU = 13

    COLUMNS = [
        texts.PROVISION_PAY_COL_BERATER,
        texts.PROVISION_PAY_COL_ROLE,
        texts.PROVISION_PAY_COL_BRUTTO,
        texts.PROVISION_PAY_COL_TL,
        texts.PROVISION_PAY_COL_NETTO,
        texts.PROVISION_PAY_COL_RUECK,
        texts.PM_PAY_COL_KORREKTUR,
        texts.PM_PAY_COL_VU_ABZUG,
        texts.PROVISION_PAY_COL_AUSZAHLUNG,
        texts.PROVISION_PAY_COL_POSITIONS,
        texts.PROVISION_PAY_COL_STATUS,
        texts.PROVISION_PAY_COL_VERSION,
        texts.PM_STMT_EMAIL_COL_HEADER,
        "",
    ]

    _RIGHT_COLS = None

    def __init__(self):
        super().__init__()
        self._data: List[BeraterAbrechnung] = []
        self._display_cache: List[List[str]] = []
        self._tooltip_cache: List[Dict[int, str]] = []
        if AuszahlungenModel._RIGHT_COLS is None:
            AuszahlungenModel._RIGHT_COLS = {
                self.COL_BRUTTO, self.COL_TL, self.COL_NETTO, self.COL_RUECK,
                self.COL_KORREKTUR, self.COL_VU_ABZUG, self.COL_AUSZAHLUNG,
                self.COL_POS, self.COL_VERSION,
            }

    def set_data(self, data: List[BeraterAbrechnung]):
        self.beginResetModel()
        self._data = data
        self._build_cache()
        self.endResetModel()

    def _build_cache(self):
        display: List[List[str]] = []
        tooltips: List[Dict[int, str]] = []
        role_map = {
            'consulter': texts.PROVISION_EMP_ROLE_CONSULTER,
            'teamleiter': texts.PROVISION_EMP_ROLE_TEAMLEITER,
            'backoffice': texts.PROVISION_EMP_ROLE_BACKOFFICE,
        }
        ncols = len(self.COLUMNS)
        for a in self._data:
            row = [''] * ncols
            tips: Dict[int, str] = {}

            row[self.COL_NAME] = a.berater_name
            row[self.COL_ROLE] = role_map.get(a.berater_role, a.berater_role)
            row[self.COL_BRUTTO] = format_eur(a.brutto_provision)
            row[self.COL_TL] = format_eur(a.tl_abzug)
            row[self.COL_NETTO] = format_eur(a.netto_provision)
            row[self.COL_RUECK] = format_eur(a.rueckbelastungen)
            row[self.COL_KORREKTUR] = format_eur(a.korrektur_vormonat) if a.has_korrektur else ""
            row[self.COL_VU_ABZUG] = format_eur(a.vu_abzug_summe) if a.vu_abzug_summe > 0 else ""
            row[self.COL_AUSZAHLUNG] = format_eur(a.auszahlung)
            row[self.COL_POS] = str(a.anzahl_provisionen)
            row[self.COL_STATUS] = STATUS_LABELS.get(a.status, a.status)
            row[self.COL_VERSION] = str(a.revision)

            if a.email_status == 'sent':
                row[self.COL_EMAIL] = texts.PM_STMT_EMAIL_STATUS_SENT
            elif a.email_status == 'failed':
                row[self.COL_EMAIL] = texts.PM_STMT_EMAIL_STATUS_FAILED
            elif not a.has_email:
                row[self.COL_EMAIL] = texts.PM_STMT_EMAIL_NO_ADDR

            if a.email_status == 'sent' and a.email_sent_at:
                tips[self.COL_EMAIL] = texts.PM_STMT_EMAIL_TOOLTIP_SENT.format(date=a.email_sent_at)
            elif a.email_status == 'failed' and a.email_error:
                tips[self.COL_EMAIL] = texts.PM_STMT_EMAIL_TOOLTIP_FAILED.format(error=a.email_error)
            elif not a.has_email:
                tips[self.COL_EMAIL] = texts.PM_STMT_EMAIL_TOOLTIP_NO_ADDR

            if a.has_korrektur and a.korrektur_details:
                try:
                    details = json.loads(a.korrektur_details)
                    lines = [texts.PM_KORREKTUR_TOOLTIP_HEADER]
                    for k in details:
                        lines.append(texts.PM_KORREKTUR_TOOLTIP_LINE.format(
                            monat=k.get('source_abrechnungsmonat', '?'),
                            diff=format_eur(float(k.get('differenz_netto', 0))),
                        ))
                    tips[self.COL_KORREKTUR] = '\n'.join(lines)
                except Exception:
                    pass

            if a.vu_abzug_summe > 0:
                tips[self.COL_VU_ABZUG] = texts.PM_PAY_VU_ABZUG_TOOLTIP

            display.append(row)
            tooltips.append(tips)

        self._display_cache = display
        self._tooltip_cache = tooltips

    def get_item(self, row: int) -> Optional[BeraterAbrechnung]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole:
            return self._display_cache[row][col]

        if role == Qt.ToolTipRole:
            return self._tooltip_cache[row].get(col)

        if role == Qt.TextAlignmentRole and col in self._RIGHT_COLS:
            return Qt.AlignRight | Qt.AlignVCenter

        a = self._data[row]

        if role == Qt.ForegroundRole:
            if col == self.COL_RUECK and a.rueckbelastungen < 0:
                return QColor(ERROR)
            if col == self.COL_TL and a.tl_abzug < 0:
                return QColor(ERROR)
            if col == self.COL_KORREKTUR and a.has_korrektur:
                return QColor(WARNING)
            if col == self.COL_EMAIL:
                if a.email_status == 'sent':
                    return QColor(SUCCESS)
                elif a.email_status == 'failed':
                    return QColor(ERROR)
                elif not a.has_email:
                    return QColor(PRIMARY_500)

        if role == Qt.FontRole and col == self.COL_KORREKTUR and a.has_korrektur:
            font = QFont()
            font.setItalic(True)
            return font

        return None


# =============================================================================
# Freie Provisionen / Sonderzahlungen
# =============================================================================


class FreeCommissionModel(QAbstractTableModel):
    """Tabellen-Model fuer die Freien Provisionen (Sonderzahlungen)."""

    COL_DATUM = 0
    COL_BETRAG = 1
    COL_BESCHREIBUNG = 2
    COL_KOSTENSTELLE = 3
    COL_VERTEILUNG = 4
    COL_ERSTELLT_VON = 5

    COLUMNS = [
        texts.PM_FREE_COL_DATUM,
        texts.PM_FREE_COL_BETRAG,
        texts.PM_FREE_COL_BESCHREIBUNG,
        texts.PM_FREE_COL_KOSTENSTELLE,
        texts.PM_FREE_COL_VERTEILUNG,
        texts.PM_FREE_COL_ERSTELLT_VON,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[FreeCommission] = []
        self._display_cache: List[List[str]] = []

    def set_data(self, data: List[FreeCommission]):
        self.beginResetModel()
        self._data = data
        self._display_cache = []
        for fc in data:
            self._display_cache.append([
                fc.datum[:10] if fc.datum else '',
                format_eur(fc.gesamtbetrag),
                fc.beschreibung,
                fc.kostenstelle or '',
                fc.verteilung_text or '',
                fc.created_by_name or '',
            ])
        self.endResetModel()

    def get_item(self, row: int) -> Optional[FreeCommission]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        col = index.column()
        if role == Qt.DisplayRole:
            return self._display_cache[index.row()][col]
        if role == Qt.TextAlignmentRole and col == self.COL_BETRAG:
            return Qt.AlignRight | Qt.AlignVCenter
        if role == Qt.UserRole:
            return self._data[index.row()]
        return None


# =============================================================================
# Xempus-Beratungen (xempus_panel)
# =============================================================================


class XempusContractsModel(QAbstractTableModel):
    COL_BEGINN = 0
    COL_VSNR = 1
    COL_PERSON = 2
    COL_VU = 3
    COL_SPARTE = 4
    COL_BEITRAG = 5
    COL_BERATER = 6
    COL_PROV_SUMME = 7
    COL_STATUS = 8

    COLUMNS = [
        texts.PROVISION_XEMPUS_COL_BEGINN,
        texts.PROVISION_XEMPUS_COL_VSNR,
        texts.PROVISION_XEMPUS_COL_PERSON,
        texts.PROVISION_XEMPUS_COL_VU,
        texts.PROVISION_XEMPUS_COL_SPARTE,
        texts.PROVISION_XEMPUS_COL_BEITRAG,
        texts.PROVISION_XEMPUS_COL_BERATER,
        texts.PROVISION_XEMPUS_COL_PROV_SUMME,
        texts.PROVISION_XEMPUS_COL_STATUS,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[Contract] = []
        self._emp_map: dict = {}

    def set_data(self, data: List[Contract], employees: List[Employee] = None):
        self.beginResetModel()
        self._data = data
        if employees:
            self._emp_map = {e.id: e.name for e in employees}
        self.endResetModel()

    def get_contract(self, row: int) -> Optional[Contract]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        c = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_BEGINN:
                if c.beginn:
                    try:
                        dt = datetime.strptime(c.beginn[:10], '%Y-%m-%d')
                        return dt.strftime('%d.%m.%Y')
                    except (ValueError, TypeError):
                        return c.beginn or ''
                return ''
            if col == self.COL_VSNR:
                return c.vsnr or ''
            if col == self.COL_PERSON:
                return c.versicherungsnehmer or ''
            if col == self.COL_VU:
                return c.versicherer or ''
            if col == self.COL_SPARTE:
                return c.sparte or ''
            if col == self.COL_BEITRAG:
                return format_eur(c.beitrag) if c.beitrag else ''
            if col == self.COL_BERATER:
                if c.berater_id and c.berater_id in self._emp_map:
                    return self._emp_map[c.berater_id]
                return c.berater_name or ''
            if col == self.COL_PROV_SUMME:
                return format_eur(c.provision_summe) if c.provision_summe else ''
            if col == self.COL_STATUS:
                return xempus_status_label(c)

        if role == Qt.UserRole:
            if col == self.COL_STATUS:
                return xempus_status_key(c)

        if role == Qt.TextAlignmentRole:
            if col in (self.COL_BEITRAG, self.COL_PROV_SUMME):
                return int(Qt.AlignRight | Qt.AlignVCenter)

        if role == Qt.ForegroundRole:
            if col == self.COL_STATUS:
                key = xempus_status_key(c)
                colors = {'zugeordnet': SUCCESS, 'offen': WARNING, 'beantragt': BLUE_BRIGHT}
                color = colors.get(key, PRIMARY_500)
                return QColor(color)

        return None


# =============================================================================
# Xempus Insight (xempus_insight_panel)
# =============================================================================


try:
    from domain.xempus_models import (
        XempusEmployer, XempusImportBatch, XempusStatusMapping,
    )
except ImportError:
    XempusEmployer = object
    XempusImportBatch = object
    XempusStatusMapping = object


class EmployerTableModel(QAbstractTableModel):
    COL_NAME = 0
    COL_CITY = 1
    COL_EMPLOYEES = 2
    COL_STATUS = 3

    COLUMNS = [
        texts.XEMPUS_EMPLOYER_COL_NAME,
        texts.XEMPUS_EMPLOYER_COL_CITY,
        texts.XEMPUS_EMPLOYER_COL_EMPLOYEES,
        texts.XEMPUS_EMPLOYER_COL_STATUS,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[XempusEmployer] = []

    def set_data(self, data: List[XempusEmployer]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_employer(self, row: int) -> Optional[XempusEmployer]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_NAME:
                return e.name
            if col == self.COL_CITY:
                parts = [e.plz, e.city]
                return ' '.join(p for p in parts if p) or ''
            if col == self.COL_EMPLOYEES:
                return str(e.employee_count)
            if col == self.COL_STATUS:
                return texts.XEMPUS_EMPLOYER_ACTIVE if e.is_active else texts.XEMPUS_EMPLOYER_INACTIVE

        if role == Qt.UserRole:
            if col == self.COL_STATUS:
                return 'aktiv' if e.is_active else 'inaktiv'

        if role == Qt.TextAlignmentRole:
            if col == self.COL_EMPLOYEES:
                return int(Qt.AlignRight | Qt.AlignVCenter)

        return None


class XempusBatchTableModel(QAbstractTableModel):
    COL_DATE = 0
    COL_FILE = 1
    COL_RECORDS = 2
    COL_PHASE = 3
    COL_ACTIVE = 4

    COLUMNS = [
        texts.XEMPUS_IMPORT_BATCH_COL_DATE,
        texts.XEMPUS_IMPORT_BATCH_COL_FILE,
        texts.XEMPUS_IMPORT_BATCH_COL_RECORDS,
        texts.XEMPUS_IMPORT_BATCH_COL_PHASE,
        texts.XEMPUS_IMPORT_BATCH_COL_ACTIVE,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[XempusImportBatch] = []

    def set_data(self, data: List[XempusImportBatch]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_batch(self, row: int) -> Optional[XempusImportBatch]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        b = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_DATE:
                return fmt_date(b.imported_at)
            if col == self.COL_FILE:
                return b.filename
            if col == self.COL_RECORDS:
                if b.record_counts:
                    total = sum(b.record_counts.values()) if isinstance(b.record_counts, dict) else 0
                    return str(total)
                return '\u2013'
            if col == self.COL_PHASE:
                return b.import_phase
            if col == self.COL_ACTIVE:
                return '\u2713' if b.is_active_snapshot else ''

        if role == Qt.UserRole:
            if col == self.COL_PHASE:
                return b.import_phase

        if role == Qt.ForegroundRole:
            if col == self.COL_ACTIVE and b.is_active_snapshot:
                return QColor(SUCCESS)

        if role == Qt.TextAlignmentRole:
            if col in (self.COL_RECORDS, self.COL_ACTIVE):
                return int(Qt.AlignCenter)

        return None


class StatusMappingModel(QAbstractTableModel):
    COL_TEXT = 0
    COL_CATEGORY = 1
    COL_DISPLAY = 2
    COL_COLOR = 3

    COLUMNS = [
        texts.XEMPUS_STATUS_MAP_COL_TEXT,
        texts.XEMPUS_STATUS_MAP_COL_CATEGORY,
        texts.XEMPUS_STATUS_MAP_COL_DISPLAY,
        texts.XEMPUS_STATUS_MAP_COL_COLOR,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[XempusStatusMapping] = []

    def set_data(self, data: List[XempusStatusMapping]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_mapping(self, row: int) -> Optional[XempusStatusMapping]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        m = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_TEXT:
                return m.raw_status
            if col == self.COL_CATEGORY:
                return m.category
            if col == self.COL_DISPLAY:
                return m.display_label or m.raw_status
            if col == self.COL_COLOR:
                return ''

        if role == Qt.BackgroundRole:
            if col == self.COL_COLOR:
                return QColor(m.color)

        return None
