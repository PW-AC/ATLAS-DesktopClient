# -*- coding: utf-8 -*-
"""
QAbstractTableModel-Klassen fuer das Provisionsmanagement.

Extrahiert aus den Panel-Dateien fuer bessere Wartbarkeit.
Models nutzen i18n-Texte, Design-Tokens und format_eur aus widgets.
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor
from typing import List, Dict, Optional
from datetime import datetime

from domain.provision.entities import (
    Commission, Employee, Contract, VermittlerMapping,
    ContractSearchResult, BeraterAbrechnung, ImportBatch,
    DashboardSummary,
)
from ui.styles.tokens import (
    PRIMARY_500, SUCCESS, ERROR, WARNING,
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


VU_BADGE_COLORS = {
    'Allianz': '#003781',
    'SwissLife': '#E30613',
    'VB': '#009640',
    'Xempus': '#5b8def',
}


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
    COL_SOURCE = 10
    COL_MENU = 11

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
        texts.PROVISION_POS_COL_SOURCE,
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
        texts.PROVISION_TIP_COL_SOURCE,
        "",
    ]

    def __init__(self):
        super().__init__()
        self._data: List[Commission] = []

    def set_data(self, data: List[Commission]):
        self.beginResetModel()
        self._data = data
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
        c = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_VU:
                return c.vu_name or c.versicherer or ""
            elif col == self.COL_DATUM:
                d = c.auszahlungsdatum or ""
                if len(d) >= 10:
                    try:
                        dt = datetime.strptime(d[:10], "%Y-%m-%d")
                        return dt.strftime("%d.%m.%Y")
                    except ValueError:
                        pass
                return d
            elif col == self.COL_KUNDE:
                return c.versicherungsnehmer or ""
            elif col == self.COL_VSNR:
                return c.vsnr or ""
            elif col == self.COL_BETRAG:
                return format_eur(c.betrag)
            elif col == self.COL_BUCHUNGSART:
                return c.buchungsart_raw or ART_LABELS.get(c.art, c.art)
            elif col == self.COL_BERATER_ANTEIL:
                return format_eur(c.berater_anteil) if c.berater_anteil is not None else ""
            elif col == self.COL_STATUS:
                return status_label(c)
            elif col == self.COL_BERATER:
                return c.berater_name or "\u2014"
            elif col == self.COL_XEMPUS_BERATER:
                return c.xempus_berater_name or "\u2014"
            elif col == self.COL_SOURCE:
                return c.source_label
            elif col == self.COL_MENU:
                return ""

        if role == Qt.TextAlignmentRole:
            if col in (self.COL_BETRAG, self.COL_BERATER_ANTEIL):
                return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            if col == self.COL_BETRAG and c.betrag < 0:
                return QColor(ERROR)
            if col == self.COL_VU:
                vu = c.vu_name or c.versicherer or ''
                color = VU_BADGE_COLORS.get(vu)
                if color:
                    return QColor(color)

        if role == Qt.UserRole:
            return c

        if role == Qt.UserRole + 1:
            return getattr(c, 'is_relevant', True)

        return None


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
    COLUMNS = [
        texts.PROVISION_DIST_EMP_COL_NAME,
        texts.PROVISION_DIST_EMP_COL_ROLE,
        texts.PROVISION_DIST_EMP_COL_MODEL,
        texts.PROVISION_DIST_EMP_COL_RATE,
        texts.PROVISION_DIST_EMP_COL_TL_RATE,
        texts.PROVISION_DIST_EMP_COL_TL_BASIS,
        texts.PROVISION_DIST_EMP_COL_TEAM,
        texts.PROVISION_DIST_EMP_COL_ACTIVE,
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
            if col == 0:
                return e.name
            elif col == 1:
                return {
                    'consulter': texts.PROVISION_EMP_ROLE_CONSULTER,
                    'teamleiter': texts.PROVISION_EMP_ROLE_TEAMLEITER,
                    'backoffice': texts.PROVISION_EMP_ROLE_BACKOFFICE,
                }.get(e.role, e.role)
            elif col == 2:
                return e.model_name or "\u2014"
            elif col == 3:
                return f"{e.effective_rate:.1f}%"
            elif col == 4:
                return f"{e.tl_override_rate:.1f}%" if e.tl_override_rate else "\u2014"
            elif col == 5:
                basis_labels = {
                    'berater_anteil': texts.PROVISION_EMP_DLG_TL_BASIS_BERATER,
                    'gesamt_courtage': texts.PROVISION_EMP_DLG_TL_BASIS_GESAMT,
                }
                return basis_labels.get(e.tl_override_basis, e.tl_override_basis)
            elif col == 6:
                return e.teamleiter_name or "\u2014"
            elif col == 7:
                return "\u2713" if e.is_active else "\u2717"

        if role == Qt.TextAlignmentRole:
            if col in (3, 4):
                return Qt.AlignRight | Qt.AlignVCenter
            if col == 7:
                return Qt.AlignCenter

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
    COL_AUSZAHLUNG = 6
    COL_POS = 7
    COL_STATUS = 8
    COL_VERSION = 9
    COL_MENU = 10

    COLUMNS = [
        texts.PROVISION_PAY_COL_BERATER,
        texts.PROVISION_PAY_COL_ROLE,
        texts.PROVISION_PAY_COL_BRUTTO,
        texts.PROVISION_PAY_COL_TL,
        texts.PROVISION_PAY_COL_NETTO,
        texts.PROVISION_PAY_COL_RUECK,
        texts.PROVISION_PAY_COL_AUSZAHLUNG,
        texts.PROVISION_PAY_COL_POSITIONS,
        texts.PROVISION_PAY_COL_STATUS,
        texts.PROVISION_PAY_COL_VERSION,
        "",
    ]

    def __init__(self):
        super().__init__()
        self._data: List[BeraterAbrechnung] = []

    def set_data(self, data: List[BeraterAbrechnung]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

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
        a = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_NAME:
                return a.berater_name
            elif col == self.COL_ROLE:
                return {
                    'consulter': texts.PROVISION_EMP_ROLE_CONSULTER,
                    'teamleiter': texts.PROVISION_EMP_ROLE_TEAMLEITER,
                    'backoffice': texts.PROVISION_EMP_ROLE_BACKOFFICE,
                }.get(a.berater_role, a.berater_role)
            elif col == self.COL_BRUTTO:
                return format_eur(a.brutto_provision)
            elif col == self.COL_TL:
                return format_eur(a.tl_abzug)
            elif col == self.COL_NETTO:
                return format_eur(a.netto_provision)
            elif col == self.COL_RUECK:
                return format_eur(a.rueckbelastungen)
            elif col == self.COL_AUSZAHLUNG:
                return format_eur(a.auszahlung)
            elif col == self.COL_POS:
                return str(a.anzahl_provisionen)
            elif col == self.COL_STATUS:
                return STATUS_LABELS.get(a.status, a.status)
            elif col == self.COL_VERSION:
                return str(a.revision)
            elif col == self.COL_MENU:
                return ""

        if role == Qt.TextAlignmentRole and col in (2, 3, 4, 5, 6, 7, 9):
            return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            if col == self.COL_RUECK and a.rueckbelastungen < 0:
                return QColor(ERROR)
            if col == self.COL_TL and a.tl_abzug < 0:
                return QColor(ERROR)

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
                colors = {'zugeordnet': SUCCESS, 'offen': WARNING, 'beantragt': '#5b8def'}
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
