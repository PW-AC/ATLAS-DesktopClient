# -*- coding: utf-8 -*-
"""
Dialog-Klassen fuer das Provisionsmanagement.

Extrahiert aus den Panel-Dateien fuer bessere Wartbarkeit.
MatchContractDialog wird von mehreren Panels verwendet.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QFrame, QPushButton, QLineEdit,
    QDialogButtonBox, QMessageBox, QTextEdit, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, QTimer
from typing import Optional

from api.provision import ProvisionAPI, Commission, ContractSearchResult
from api.client import APIError
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, ACCENT_HOVER,
    BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, SUCCESS_LIGHT, ERROR, ERROR_LIGHT, WARNING, WARNING_LIGHT,
    INFO_LIGHT, BLUE_BRIGHT, AMBER,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    get_provision_table_style,
)
from ui.provision.widgets import (
    PillBadgeDelegate, format_eur,
    get_search_field_style, get_secondary_button_style,
)
from ui.provision.workers import MatchSearchWorker
from ui.provision.models import SuggestionsModel
from infrastructure.threading.worker_utils import run_worker, detach_worker
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
    100: {"bg": SUCCESS_LIGHT, "text": SUCCESS},
    90: {"bg": INFO_LIGHT, "text": BLUE_BRIGHT},
    70: {"bg": WARNING_LIGHT, "text": AMBER},
    40: {"bg": ERROR_LIGHT, "text": ERROR},
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
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
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
            'vsnr_exact': {"bg": SUCCESS_LIGHT, "text": SUCCESS},
            'vsnr_alt': {"bg": INFO_LIGHT, "text": BLUE_BRIGHT},
            'name_exact': {"bg": WARNING_LIGHT, "text": AMBER},
            'name_partial': {"bg": ERROR_LIGHT, "text": ERROR},
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
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
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
            detach_worker(self._worker)
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

        self._assign_btn.setEnabled(False)
        self._status_label.setText(texts.PROVISION_MATCH_DLG_LOADING)
        run_worker(
            self,
            lambda w, cid=self._comm.id, ctid=contract.id, f=force: (
                self._api.assign_contract(
                    commission_id=cid, contract_id=ctid, force_override=f)
            ),
            lambda _: self.accept(),
            on_error=self._on_assign_error,
        )

    def _on_assign_error(self, error_msg):
        self._assign_btn.setEnabled(True)
        self._status_label.setText(
            texts.PROVISION_TOAST_ASSIGN_CONFLICT.format(msg=error_msg)
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


# =============================================================================
# OverrideDialog (Betragskorrektur)
# =============================================================================


class OverrideDialog(QDialog):
    """Dialog zum Setzen einer Betragskorrektur fuer die Abrechnung."""

    def __init__(self, commission: Commission, parent=None):
        super().__init__(parent)
        self._comm = commission
        self._amount: Optional[float] = None
        self._reason: Optional[str] = None
        self.setWindowTitle(texts.PM_OVERRIDE_TITLE)
        self.setMinimumWidth(420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(6)

        orig_label = QLabel(
            f"<b>{texts.PM_OVERRIDE_ORIGINAL}:</b> {format_eur(self._comm.betrag)}"
        )
        orig_label.setStyleSheet(f"color: {PRIMARY_900}; border: none;")
        info_layout.addWidget(orig_label)

        context = QLabel(
            f"{self._comm.versicherer or ''} | {self._comm.vsnr} | {self._comm.versicherungsnehmer or ''}"
        )
        context.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; border: none;"
        )
        info_layout.addWidget(context)
        layout.addWidget(info_frame)

        amount_label = QLabel(texts.PM_OVERRIDE_AMOUNT)
        amount_label.setStyleSheet(f"font-weight: 600; color: {PRIMARY_900};")
        layout.addWidget(amount_label)

        self._amount_spin = QDoubleSpinBox()
        self._amount_spin.setRange(-9999999.99, 9999999.99)
        self._amount_spin.setDecimals(2)
        self._amount_spin.setSuffix(" \u20ac")
        self._amount_spin.setFixedHeight(36)
        current = self._comm.amount_settled if self._comm.is_overridden else self._comm.betrag
        self._amount_spin.setValue(current)
        self._amount_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 1px solid {BORDER_DEFAULT}; border-radius: 6px;
                padding: 4px 8px; font-size: {FONT_SIZE_BODY};
            }}
            QDoubleSpinBox:focus {{ border-color: {ACCENT_500}; }}
        """)
        layout.addWidget(self._amount_spin)

        reason_label = QLabel(texts.PM_OVERRIDE_REASON)
        reason_label.setStyleSheet(f"font-weight: 600; color: {PRIMARY_900};")
        layout.addWidget(reason_label)

        self._reason_edit = QTextEdit()
        self._reason_edit.setPlaceholderText(texts.PM_OVERRIDE_REASON_PLACEHOLDER)
        self._reason_edit.setMaximumHeight(80)
        self._reason_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {BORDER_DEFAULT}; border-radius: 6px;
                padding: 6px; font-size: {FONT_SIZE_BODY};
            }}
            QTextEdit:focus {{ border-color: {ACCENT_500}; }}
        """)
        if self._comm.amount_override_reason:
            self._reason_edit.setPlainText(self._comm.amount_override_reason)
        layout.addWidget(self._reason_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_btn = QPushButton(texts.PM_OVERRIDE_SET)
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 24px; font-weight: 600; }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton(texts.PROVISION_MATCH_DLG_CANCEL)
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(get_secondary_button_style())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _on_save(self):
        self._amount = round(self._amount_spin.value(), 2)
        self._reason = self._reason_edit.toPlainText().strip() or None
        self.accept()

    @property
    def amount(self) -> Optional[float]:
        return self._amount

    @property
    def reason(self) -> Optional[str]:
        return self._reason


# =============================================================================
# NoteDialog (Notiz bearbeiten)
# =============================================================================


class NoteDialog(QDialog):
    """Dialog zum Bearbeiten einer Provisions-Notiz."""

    def __init__(self, commission: Commission, parent=None):
        super().__init__(parent)
        self._comm = commission
        self._note_text: Optional[str] = None
        self.setWindowTitle(texts.PM_NOTE_TITLE)
        self.setMinimumWidth(420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        context = QLabel(
            f"{self._comm.versicherer or ''} | {self._comm.vsnr} | "
            f"{format_eur(self._comm.betrag)}"
        )
        context.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(context)

        self._note_edit = QTextEdit()
        self._note_edit.setPlaceholderText(texts.PM_NOTE_PLACEHOLDER)
        self._note_edit.setMinimumHeight(120)
        self._note_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {BORDER_DEFAULT}; border-radius: 6px;
                padding: 8px; font-size: {FONT_SIZE_BODY};
            }}
            QTextEdit:focus {{ border-color: {ACCENT_500}; }}
        """)
        if self._comm.note:
            self._note_edit.setPlainText(self._comm.note)
        layout.addWidget(self._note_edit)

        if self._comm.note_updater_name and self._comm.note_updated_at:
            meta = QLabel(texts.PM_NOTE_UPDATED_BY.format(
                name=self._comm.note_updater_name,
                date=self._comm.note_updated_at,
            ))
            meta.setStyleSheet(
                f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-style: italic;"
            )
            layout.addWidget(meta)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_btn = QPushButton(texts.PM_NOTE_SAVE)
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 24px; font-weight: 600; }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton(texts.PROVISION_MATCH_DLG_CANCEL)
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(get_secondary_button_style())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _on_save(self):
        self._note_text = self._note_edit.toPlainText().strip()
        self.accept()

    @property
    def note(self) -> Optional[str]:
        return self._note_text
