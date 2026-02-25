# -*- coding: utf-8 -*-
"""
Dialog-Klassen fuer das Provisionsmanagement.

Extrahiert aus den Panel-Dateien fuer bessere Wartbarkeit.
MatchContractDialog wird von mehreren Panels verwendet.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QFrame, QPushButton, QLineEdit,
    QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from typing import Optional

from api.provision import ProvisionAPI, Commission, ContractSearchResult
from api.client import APIError
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    get_provision_table_style,
)
from ui.provision.widgets import (
    PillBadgeDelegate, format_eur,
    get_search_field_style, get_secondary_button_style,
)
from ui.provision.workers import MatchSearchWorker
from ui.provision.models import SuggestionsModel
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MatchContractDialog
# =============================================================================

MATCH_REASON_LABELS = {
    'vsnr_exact': texts.PROVISION_MATCH_DLG_SCORE_VSNR_EXACT,
    'vsnr_alt': texts.PROVISION_MATCH_DLG_SCORE_VSNR_ALT,
    'name_exact': texts.PROVISION_MATCH_DLG_SCORE_NAME_EXACT,
    'name_partial': texts.PROVISION_MATCH_DLG_SCORE_NAME_PARTIAL,
}

MATCH_SCORE_COLORS = {
    100: {"bg": "#dcfce7", "text": "#166534"},
    90: {"bg": "#dbeafe", "text": "#1e40af"},
    70: {"bg": "#fef9c3", "text": "#854d0e"},
    40: {"bg": "#fee2e2", "text": "#991b1b"},
}


class MatchContractDialog(QDialog):
    """Dialog fuer manuelle Vertragszuordnung mit Multi-Level-Matching."""

    def __init__(self, api: ProvisionAPI, commission: Commission, parent=None):
        super().__init__(parent)
        self._api = api
        self._comm = commission
        self._worker: Optional[MatchSearchWorker] = None
        self._selected_contract: Optional[ContractSearchResult] = None
        self.setWindowTitle(texts.PROVISION_MATCH_DLG_TITLE)
        self.setMinimumSize(780, 550)
        self._setup_ui()
        QTimer.singleShot(100, self._auto_search)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        orig_frame = QFrame()
        orig_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        orig_layout = QVBoxLayout(orig_frame)
        orig_layout.setSpacing(6)

        orig_title = QLabel(texts.PROVISION_MATCH_DLG_ORIGINAL)
        orig_title.setStyleSheet(f"font-weight: 600; color: {PRIMARY_900}; border: none;")
        orig_layout.addWidget(orig_title)

        details = QHBoxLayout()
        for label, value in [
            (texts.PROVISION_POS_COL_VU, self._comm.versicherer or self._comm.vu_name or "\u2014"),
            (texts.PROVISION_POS_COL_VSNR, self._comm.vsnr or "\u2014"),
            (texts.PROVISION_POS_COL_KUNDE, self._comm.versicherungsnehmer or "\u2014"),
            (texts.PROVISION_POS_COL_BETRAG, format_eur(self._comm.betrag)),
            (texts.PROVISION_POS_COL_XEMPUS_BERATER, self._comm.xempus_berater_name or "\u2014"),
        ]:
            item = QLabel(f"<b>{label}:</b> {value}")
            item.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_CAPTION}; border: none;")
            details.addWidget(item)
        details.addStretch()
        orig_layout.addLayout(details)

        source_lbl = QLabel(f"{texts.PROVISION_POS_COL_SOURCE}: {self._comm.source_label}")
        source_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; border: none;")
        orig_layout.addWidget(source_lbl)

        layout.addWidget(orig_frame)

        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(texts.PROVISION_MATCH_DLG_SEARCH)
        self._search_edit.setFixedHeight(34)
        self._search_edit.setStyleSheet(get_search_field_style())
        self._search_edit.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_edit)

        search_btn = QPushButton(texts.PROVISION_MATCH_DLG_SEARCH_BTN)
        search_btn.setFixedHeight(34)
        search_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 4px 16px; font-weight: 500; }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        search_btn.clicked.connect(self._do_search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        self._results_title = QLabel(texts.PROVISION_MATCH_DLG_RESULTS)
        self._results_title.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
        layout.addWidget(self._results_title)

        self._suggestions_model = SuggestionsModel()
        self._table = QTableView()
        self._table.setModel(self._suggestions_model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(42)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setStyleSheet(get_provision_table_style())
        self._table.setMinimumHeight(200)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)

        score_delegate = PillBadgeDelegate(
            {str(k): v for k, v in MATCH_SCORE_COLORS.items()},
        )
        self._table.setItemDelegateForColumn(SuggestionsModel.COL_SCORE, score_delegate)

        reason_delegate = PillBadgeDelegate({
            'vsnr_exact': {"bg": "#dcfce7", "text": "#166534"},
            'vsnr_alt': {"bg": "#dbeafe", "text": "#1e40af"},
            'name_exact': {"bg": "#fef9c3", "text": "#854d0e"},
            'name_partial': {"bg": "#fee2e2", "text": "#991b1b"},
        }, label_map={
            'vsnr_exact': texts.PROVISION_MATCH_DLG_SCORE_VSNR_EXACT,
            'vsnr_alt': texts.PROVISION_MATCH_DLG_SCORE_VSNR_ALT,
            'name_exact': texts.PROVISION_MATCH_DLG_SCORE_NAME_EXACT,
            'name_partial': texts.PROVISION_MATCH_DLG_SCORE_NAME_PARTIAL,
        })
        self._table.setItemDelegateForColumn(SuggestionsModel.COL_REASON, reason_delegate)

        layout.addWidget(self._table, 1)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._assign_btn = QPushButton(texts.PROVISION_MATCH_DLG_ASSIGN)
        self._assign_btn.setEnabled(False)
        self._assign_btn.setFixedHeight(36)
        self._assign_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 24px; font-weight: 600; }}
            QPushButton:hover {{ background-color: #e88a2d; }}
            QPushButton:disabled {{ background-color: {BORDER_DEFAULT}; color: {PRIMARY_500}; }}
        """)
        self._assign_btn.clicked.connect(self._do_assign)
        btn_row.addWidget(self._assign_btn)

        cancel_btn = QPushButton(texts.PROVISION_MATCH_DLG_CANCEL)
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(get_secondary_button_style())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _auto_search(self):
        """Automatische Server-Suche beim Oeffnen."""
        self._status_label.setText(texts.PROVISION_MATCH_DLG_LOADING)
        self._suggestions_model.set_data([])
        self._run_search(q=None)

    def _do_search(self):
        q = self._search_edit.text().strip()
        self._status_label.setText(texts.PROVISION_MATCH_DLG_LOADING)
        self._suggestions_model.set_data([])
        self._run_search(q=q if q else None)

    def _run_search(self, q: str = None):
        if self._worker and self._worker.isRunning():
            return
        self._worker = MatchSearchWorker(self._api, self._comm.id, q=q)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_search_error)
        self._worker.start()

    def _on_results(self, suggestions: list, commission: dict):
        results = []
        for s in suggestions:
            if isinstance(s, ContractSearchResult):
                results.append(s)
            elif isinstance(s, dict):
                results.append(ContractSearchResult.from_dict(s))
            else:
                results.append(s)
        self._suggestions_model.set_data(results)
        if results:
            count = len(results)
            self._status_label.setText(
                texts.PROVISION_MATCH_RESULTS_COUNT.format(count=count)
            )
        else:
            self._status_label.setText(texts.PROVISION_MATCH_DLG_NO_RESULTS)

    def _on_search_error(self, msg: str):
        self._status_label.setText(f"{texts.PROVISION_ERROR_PREFIX}: {msg}")
        logger.error(f"Match-Suche fehlgeschlagen: {msg}")

    def _on_selection(self, selected, deselected):
        indexes = self._table.selectionModel().selectedRows()
        if indexes:
            item = self._suggestions_model.get_item(indexes[0].row())
            self._selected_contract = item
            self._assign_btn.setEnabled(item is not None)
        else:
            self._selected_contract = None
            self._assign_btn.setEnabled(False)

    def _do_assign(self):
        if not self._selected_contract:
            return
        contract = self._selected_contract.contract
        force = bool(self._comm.contract_id)

        if force:
            reply = QMessageBox.question(
                self,
                texts.PROVISION_MATCH_DLG_REASSIGN,
                texts.PROVISION_MATCH_DLG_FORCE,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        try:
            self._api.assign_contract(
                commission_id=self._comm.id,
                contract_id=contract.id,
                force_override=force,
            )
            self.accept()
        except APIError as e:
            self._status_label.setText(
                texts.PROVISION_TOAST_ASSIGN_CONFLICT.format(msg=str(e))
            )
            self._status_label.setStyleSheet(f"color: {ERROR}; font-size: {FONT_SIZE_CAPTION};")


# =============================================================================
# DiffDialog (Xempus Snapshot-Vergleich)
# =============================================================================

try:
    from domain.xempus_models import XempusDiff
except ImportError:
    XempusDiff = object


class DiffDialog(QDialog):
    """Snapshot-Vergleichs-Dialog."""

    def __init__(self, diff, parent=None):
        super().__init__(parent)
        self.setWindowTitle(texts.XEMPUS_DIFF_TITLE)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        if diff.previous_batch_id is None:
            lbl = QLabel(texts.XEMPUS_DIFF_NO_PREVIOUS)
            lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY};")
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)
        else:
            for entity_name, entity_data in [
                (texts.XEMPUS_DIFF_EMPLOYERS, diff.employers),
                (texts.XEMPUS_DIFF_EMPLOYEES, diff.employees),
                (texts.XEMPUS_DIFF_CONSULTATIONS, diff.consultations),
            ]:
                if not entity_data:
                    continue
                new = int(entity_data.get('new', 0))
                removed = int(entity_data.get('removed', 0))
                changed = int(entity_data.get('changed', 0))

                section = QLabel(entity_name)
                section.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
                layout.addWidget(section)

                summary = QLabel(texts.XEMPUS_DIFF_SUMMARY.format(
                    new=new, removed=removed, changed=changed))
                summary.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY};")
                layout.addWidget(summary)

                chips_row = QHBoxLayout()
                for label_text, count, color in [
                    (texts.XEMPUS_DIFF_NEW, new, SUCCESS),
                    (texts.XEMPUS_DIFF_REMOVED, removed, ERROR),
                    (texts.XEMPUS_DIFF_CHANGED, changed, WARNING),
                ]:
                    if count > 0:
                        chip = QLabel(f"  {label_text}: {count}  ")
                        chip.setStyleSheet(f"""
                            background-color: {color}20; color: {color};
                            border: 1px solid {color}40; border-radius: 10px;
                            padding: 3px 8px; font-size: {FONT_SIZE_CAPTION};
                        """)
                        chips_row.addWidget(chip)
                chips_row.addStretch()
                layout.addLayout(chips_row)

        layout.addStretch()

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
