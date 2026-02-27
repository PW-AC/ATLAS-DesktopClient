"""
Verteilschluessel & Rollen-Panel: Provisionsmodelle + Mitarbeiter merged.

Ersetzt: employees_panel.py
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QFrame, QPushButton, QDialog, QComboBox,
    QLineEdit, QFormLayout, QDialogButtonBox, QDoubleSpinBox,
    QTextEdit, QScrollArea, QSizePolicy, QMenu, QMessageBox,
    QDateEdit,
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QModelIndex, QDate,
)
from typing import List, Optional

from api.client import APIError
from api.provision import ProvisionAPI
from domain.provision.entities import Employee, CommissionModel
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    ERROR,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    ROLE_BADGE_COLORS, build_rich_tooltip, get_provision_table_style,
)
from ui.provision.widgets import (
    SectionHeader, PillBadgeDelegate, ProvisionLoadingOverlay,
    format_eur, get_secondary_button_style,
)
from ui.provision.workers import VerteilschluesselLoadWorker, SaveEmployeeWorker, SaveModelWorker
from ui.provision.models import DistEmployeeModel
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class VerteilschluesselPanel(QWidget):
    """Provisionsmodelle und Mitarbeiter mit Rollen.

    Implementiert IDistributionView fuer den DistributionPresenter.
    """

    navigate_to_panel = Signal(int)
    data_changed = Signal()

    def __init__(self, api: ProvisionAPI = None):
        super().__init__()
        self._api = api
        self._presenter = None
        self._worker = None
        self._save_worker = None
        self._models: List[CommissionModel] = []
        self._employees: List[Employee] = []
        self._toast_manager = None
        self._setup_ui()
        if api:
            QTimer.singleShot(100, self._load_data)

    @property
    def _backend(self):
        return self._presenter or self._api

    def set_presenter(self, presenter) -> None:
        """Verbindet dieses Panel mit dem DistributionPresenter."""
        self._presenter = presenter
        presenter.set_view(self)
        self._presenter.load_data()

    # ── IDistributionView ──

    def show_employees(self, employees: list) -> None:
        """View-Interface: Mitarbeiter anzeigen."""
        self._employees = employees
        self._emp_model.set_data(employees)

    def show_models(self, models: list) -> None:
        """View-Interface: Provisionsmodelle anzeigen."""
        self._models = models
        self._render_models()

    def show_loading(self, loading: bool) -> None:
        """View-Interface: Ladezustand."""
        overlay = getattr(self, '_loading_overlay', None)
        if overlay:
            overlay.setVisible(loading)

    def show_error(self, message: str) -> None:
        """View-Interface: Fehler anzeigen."""
        logger.error(f"Verteilschluessel-Fehler: {message}")

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Provisionsmodelle
        model_header = SectionHeader(
            texts.PROVISION_DIST_MODELS_TITLE,
            texts.PROVISION_DIST_MODELS_DESC,
        )
        add_model_btn = QPushButton(texts.PROVISION_DIST_MODEL_ADD)
        add_model_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 16px; font-weight: 500; }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        add_model_btn.clicked.connect(self._add_model)
        model_header.add_action(add_model_btn)
        layout.addWidget(model_header)

        self._models_container = QVBoxLayout()
        self._models_container.setSpacing(12)
        layout.addLayout(self._models_container)

        # Mitarbeiter
        emp_header = SectionHeader(
            texts.PROVISION_DIST_EMP_TITLE,
            texts.PROVISION_DIST_EMP_DESC,
        )
        add_emp_btn = QPushButton(texts.PROVISION_EMP_ADD)
        add_emp_btn.setStyleSheet(get_secondary_button_style())
        add_emp_btn.clicked.connect(self._add_employee)
        emp_header.add_action(add_emp_btn)
        layout.addWidget(emp_header)

        self._emp_model = DistEmployeeModel()
        self._emp_table = QTableView()
        self._emp_table.setModel(self._emp_model)
        self._emp_table.setAlternatingRowColors(True)
        self._emp_table.setSelectionBehavior(QTableView.SelectRows)
        self._emp_table.verticalHeader().setVisible(False)
        self._emp_table.verticalHeader().setDefaultSectionSize(52)
        self._emp_table.horizontalHeader().setStretchLastSection(True)
        self._emp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._emp_table.setStyleSheet(get_provision_table_style())
        self._emp_table.setMinimumHeight(300)
        self._emp_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._emp_table.customContextMenuRequested.connect(self._emp_context_menu)
        self._emp_table.doubleClicked.connect(self._on_emp_double_click)

        role_del = PillBadgeDelegate(ROLE_BADGE_COLORS, label_map={
            'consulter': texts.PROVISION_EMP_ROLE_CONSULTER,
            'teamleiter': texts.PROVISION_EMP_ROLE_TEAMLEITER,
            'backoffice': texts.PROVISION_EMP_ROLE_BACKOFFICE,
        })
        self._emp_table.setItemDelegateForColumn(1, role_del)
        self._role_del = role_del

        layout.addWidget(self._emp_table)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {ERROR}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._status)

        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._loading_overlay = ProvisionLoadingOverlay(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._loading_overlay.setGeometry(self.rect())

    def refresh(self):
        self._load_data()

    def _load_data(self):
        self._status.setText("")
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.setVisible(True)

        if self._presenter:
            self._presenter.load_data()
            return

        if self._worker and self._worker.isRunning():
            return
        self._worker = VerteilschluesselLoadWorker(self._api)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, models: List[CommissionModel], employees: List[Employee]):
        self._loading_overlay.setVisible(False)
        self._models = models
        self._employees = employees
        self._render_models()
        self._emp_model.set_data(employees)
        self._status.setText("")

    def _on_error(self, msg: str):
        self._loading_overlay.setVisible(False)
        self._status.setText(texts.PROVISION_DASH_ERROR)
        logger.error(f"Verteilschluessel-Ladefehler: {msg}")

    def _render_models(self):
        while self._models_container.count():
            item = self._models_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for model in self._models:
            if not model.is_active:
                continue
            card = QFrame()
            card.setStyleSheet(f"background: white; border: 1.5px solid #b0c4d8; border-radius: 8px;")
            card.setContextMenuPolicy(Qt.CustomContextMenu)
            _m = model
            card.customContextMenuRequested.connect(lambda pos, m=_m, c=card: self._model_context_menu(pos, m, c))
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 16, 20, 16)
            card_layout.setSpacing(8)

            name_lbl = QLabel(model.name)
            name_lbl.setStyleSheet(f"font-weight: 600; font-size: 12pt; color: {PRIMARY_900}; border: none;")
            card_layout.addWidget(name_lbl)

            if model.description:
                desc = QLabel(model.description)
                desc.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY}; border: none;")
                desc.setWordWrap(True)
                card_layout.addWidget(desc)

            rate = model.commission_rate
            ag = 100.0 - rate
            example_amount = 1000.0
            ag_amount = example_amount * ag / 100
            berater_brutto = example_amount * rate / 100
            tl_rate_val = model.tl_rate or 0.0
            if model.tl_basis == "gesamt_courtage":
                tl_amount = example_amount * tl_rate_val / 100
            else:
                tl_amount = berater_brutto * tl_rate_val / 100
            tl_amount = min(tl_amount, berater_brutto)
            berater_amount = berater_brutto - tl_amount

            rate_row = QHBoxLayout()
            for label, pct in [(texts.PROVISION_DIST_MODEL_COL_AG, ag),
                               (texts.PROVISION_DIST_MODEL_COL_BERATER, rate)]:
                item_lbl = QLabel(f"{label}: {pct:.0f}%")
                item_lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY}; border: none; font-weight: 500;")
                rate_row.addWidget(item_lbl)
            if model.tl_rate is not None and model.tl_rate > 0:
                basis_label = texts.PROVISION_EMP_DLG_TL_BASIS_GESAMT if model.tl_basis == "gesamt_courtage" else texts.PROVISION_EMP_DLG_TL_BASIS_BERATER
                tl_lbl = QLabel(f"TL: {model.tl_rate:.0f}% ({basis_label})")
                tl_lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY}; border: none; font-weight: 500;")
                rate_row.addWidget(tl_lbl)
            rate_row.addStretch()
            card_layout.addLayout(rate_row)

            example = QLabel(texts.PROVISION_DIST_MODEL_EXAMPLE.format(
                amount=format_eur(example_amount),
                ag=format_eur(ag_amount),
                berater=format_eur(berater_amount),
                tl=format_eur(tl_amount),
            ))
            example.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; border: none;")
            card_layout.addWidget(example)

            self._models_container.addWidget(card)

    def _add_model(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_DIST_MODEL_ADD)
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)

        name_edit = QLineEdit()
        form.addRow(texts.PROVISION_MODEL_COL_NAME + ":", name_edit)

        rate_spin = QDoubleSpinBox()
        rate_spin.setRange(0, 100)
        rate_spin.setDecimals(1)
        rate_spin.setSuffix("%")
        rate_spin.setValue(70.0)
        form.addRow(texts.PROVISION_DIST_MODEL_COL_BERATER + ":", rate_spin)

        tl_rate_spin = QDoubleSpinBox()
        tl_rate_spin.setRange(0, 100)
        tl_rate_spin.setDecimals(1)
        tl_rate_spin.setSuffix("%")
        tl_rate_spin.setSpecialValueText("\u2014")
        form.addRow(texts.PROVISION_MODEL_COL_TL_RATE + ":", tl_rate_spin)

        tl_basis_combo = QComboBox()
        tl_basis_combo.addItem(texts.PROVISION_EMP_DLG_TL_BASIS_BERATER, "berater_anteil")
        tl_basis_combo.addItem(texts.PROVISION_EMP_DLG_TL_BASIS_GESAMT, "gesamt_courtage")
        form.addRow(texts.PROVISION_MODEL_COL_TL_BASIS + ":", tl_basis_combo)

        desc_edit = QLineEdit()
        form.addRow(texts.PROVISION_MODEL_COL_DESC + ":", desc_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            if name:
                self._backend.create_model({
                    'name': name,
                    'commission_rate': rate_spin.value(),
                    'tl_rate': tl_rate_spin.value() if tl_rate_spin.value() > 0 else None,
                    'tl_basis': tl_basis_combo.currentData(),
                    'description': desc_edit.text().strip() or None,
                })
                self._load_data()

    def _get_model_map(self) -> dict:
        """Model-ID -> CommissionModel Lookup fuer Auto-Fill aller Felder."""
        return {m.id: m for m in self._models if m.is_active}

    def _add_employee(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_EMP_DLG_TITLE_ADD)
        dlg.setMinimumWidth(450)
        form = QFormLayout(dlg)

        name_edit = QLineEdit()
        form.addRow(texts.PROVISION_EMP_DLG_NAME, name_edit)

        role_combo = QComboBox()
        role_combo.addItem(texts.PROVISION_EMP_ROLE_CONSULTER, "consulter")
        role_combo.addItem(texts.PROVISION_EMP_ROLE_TEAMLEITER, "teamleiter")
        role_combo.addItem(texts.PROVISION_EMP_ROLE_BACKOFFICE, "backoffice")
        form.addRow(texts.PROVISION_EMP_DLG_ROLE, role_combo)

        model_combo = QComboBox()
        model_combo.addItem(texts.PROVISION_MODEL_NONE_SELECT, None)
        for m in self._models:
            if m.is_active:
                model_combo.addItem(f"{m.name} ({m.commission_rate:.0f}%)", m.id)
        form.addRow(texts.PROVISION_EMP_DLG_MODEL, model_combo)

        rate_spin = QDoubleSpinBox()
        rate_spin.setRange(0, 100)
        rate_spin.setDecimals(1)
        rate_spin.setSuffix("%")
        rate_spin.setValue(0.0)
        rate_spin.setSpecialValueText("\u2014")
        form.addRow(texts.PROVISION_DIST_EMP_COL_RATE + ":", rate_spin)

        tl_rate_spin = QDoubleSpinBox()
        tl_rate_spin.setRange(0, 100)
        tl_rate_spin.setDecimals(1)
        tl_rate_spin.setSuffix("%")
        tl_rate_spin.setSpecialValueText("\u2014")
        form.addRow(texts.PROVISION_DIST_EMP_COL_TL_RATE + ":", tl_rate_spin)

        tl_basis_combo = QComboBox()
        tl_basis_combo.addItem(texts.PROVISION_EMP_DLG_TL_BASIS_BERATER, "berater_anteil")
        tl_basis_combo.addItem(texts.PROVISION_EMP_DLG_TL_BASIS_GESAMT, "gesamt_courtage")
        form.addRow(texts.PROVISION_DIST_EMP_COL_TL_BASIS + ":", tl_basis_combo)

        model_map = self._get_model_map()

        def _on_model_changed():
            m = model_map.get(model_combo.currentData())
            if m:
                rate_spin.setValue(m.commission_rate)
                if m.tl_rate is not None:
                    tl_rate_spin.setValue(m.tl_rate)
                if m.tl_basis:
                    idx = 1 if m.tl_basis == "gesamt_courtage" else 0
                    tl_basis_combo.setCurrentIndex(idx)
            else:
                rate_spin.setValue(0.0)
                tl_rate_spin.setValue(0.0)

        model_combo.currentIndexChanged.connect(_on_model_changed)

        tl_combo = QComboBox()
        tl_combo.addItem("\u2014", None)
        for e in self._employees:
            if e.role == 'teamleiter' and e.is_active:
                tl_combo.addItem(e.name, e.id)
        form.addRow(texts.PROVISION_EMP_DLG_TEAMLEITER, tl_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            if name:
                model_id = model_combo.currentData()
                m = model_map.get(model_id)
                model_rate = m.commission_rate if m else 0.0
                rate_val = rate_spin.value()
                data = {
                    'name': name,
                    'role': role_combo.currentData(),
                    'commission_model_id': model_id,
                    'commission_rate_override': rate_val if rate_val > 0 and rate_val != model_rate else None,
                    'tl_override_rate': tl_rate_spin.value() if tl_rate_spin.value() > 0 else None,
                    'tl_override_basis': tl_basis_combo.currentData(),
                    'teamleiter_id': tl_combo.currentData(),
                }
                self._backend.create_employee(data)
                if self._toast_manager:
                    self._toast_manager.show_success(texts.PROVISION_TOAST_SAVED)
                self._load_data()

    # ── Employee context menu + edit/delete ──

    def _emp_context_menu(self, pos):
        idx = self._emp_table.indexAt(pos)
        if not idx.isValid():
            return
        emp = self._emp_model.get_item(idx.row())
        if not emp:
            return
        menu = QMenu(self)
        menu.addAction(texts.PROVISION_MENU_EDIT, lambda: self._edit_employee(emp))
        if emp.is_active:
            menu.addAction(texts.PROVISION_MENU_DEACTIVATE, lambda: self._deactivate_employee(emp))
        else:
            menu.addAction(texts.PROVISION_MENU_ACTIVATE, lambda: self._activate_employee(emp))
        menu.addAction(texts.PROVISION_MENU_DELETE, lambda: self._delete_employee(emp))
        menu.exec(self._emp_table.viewport().mapToGlobal(pos))

    def _on_emp_double_click(self, index: QModelIndex):
        emp = self._emp_model.get_item(index.row())
        if emp:
            self._edit_employee(emp)

    def _edit_employee(self, emp: Employee):
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_EMP_DLG_TITLE_EDIT)
        dlg.setMinimumWidth(450)
        form = QFormLayout(dlg)

        name_edit = QLineEdit(emp.name)
        form.addRow(texts.PROVISION_EMP_DLG_NAME, name_edit)

        role_combo = QComboBox()
        roles = [
            (texts.PROVISION_EMP_ROLE_CONSULTER, "consulter"),
            (texts.PROVISION_EMP_ROLE_TEAMLEITER, "teamleiter"),
            (texts.PROVISION_EMP_ROLE_BACKOFFICE, "backoffice"),
        ]
        for label, val in roles:
            role_combo.addItem(label, val)
        for i, (_, val) in enumerate(roles):
            if val == emp.role:
                role_combo.setCurrentIndex(i)
                break
        form.addRow(texts.PROVISION_EMP_DLG_ROLE, role_combo)

        model_combo = QComboBox()
        model_combo.addItem(texts.PROVISION_MODEL_NONE_SELECT, None)
        for m in self._models:
            if m.is_active:
                model_combo.addItem(f"{m.name} ({m.commission_rate:.0f}%)", m.id)
                if m.id == emp.commission_model_id:
                    model_combo.setCurrentIndex(model_combo.count() - 1)
        form.addRow(texts.PROVISION_EMP_DLG_MODEL, model_combo)

        rate_spin = QDoubleSpinBox()
        rate_spin.setRange(0, 100)
        rate_spin.setDecimals(1)
        rate_spin.setSuffix("%")
        current_rate = emp.commission_rate_override if emp.commission_rate_override else (emp.model_rate or 0.0)
        rate_spin.setValue(current_rate)
        rate_spin.setSpecialValueText("\u2014")
        form.addRow(texts.PROVISION_DIST_EMP_COL_RATE + ":", rate_spin)

        tl_rate_spin = QDoubleSpinBox()
        tl_rate_spin.setRange(0, 100)
        tl_rate_spin.setDecimals(1)
        tl_rate_spin.setSuffix("%")
        tl_rate_spin.setValue(emp.tl_override_rate or 0.0)
        tl_rate_spin.setSpecialValueText("\u2014")
        form.addRow(texts.PROVISION_DIST_EMP_COL_TL_RATE + ":", tl_rate_spin)

        tl_basis_combo = QComboBox()
        tl_basis_combo.addItem(texts.PROVISION_EMP_DLG_TL_BASIS_BERATER, "berater_anteil")
        tl_basis_combo.addItem(texts.PROVISION_EMP_DLG_TL_BASIS_GESAMT, "gesamt_courtage")
        if emp.tl_override_basis == "gesamt_courtage":
            tl_basis_combo.setCurrentIndex(1)
        form.addRow(texts.PROVISION_DIST_EMP_COL_TL_BASIS + ":", tl_basis_combo)

        model_map = self._get_model_map()

        def _on_model_changed():
            m = model_map.get(model_combo.currentData())
            if m:
                rate_spin.setValue(m.commission_rate)
                if m.tl_rate is not None:
                    tl_rate_spin.setValue(m.tl_rate)
                if m.tl_basis:
                    idx = 1 if m.tl_basis == "gesamt_courtage" else 0
                    tl_basis_combo.setCurrentIndex(idx)
            else:
                rate_spin.setValue(0.0)
                tl_rate_spin.setValue(0.0)

        model_combo.currentIndexChanged.connect(_on_model_changed)

        tl_combo = QComboBox()
        tl_combo.addItem("\u2014", None)
        for e in self._employees:
            if e.role == 'teamleiter' and e.is_active and e.id != emp.id:
                tl_combo.addItem(e.name, e.id)
                if e.id == emp.teamleiter_id:
                    tl_combo.setCurrentIndex(tl_combo.count() - 1)
        form.addRow(texts.PROVISION_EMP_DLG_TEAMLEITER, tl_combo)

        gueltig_ab = QDateEdit()
        gueltig_ab.setCalendarPopup(True)
        gueltig_ab.setDate(QDate.currentDate())
        gueltig_ab.setDisplayFormat("dd.MM.yyyy")
        gueltig_ab.setToolTip(texts.PROVISION_GUELTIG_AB_HINT)
        form.addRow(texts.PROVISION_GUELTIG_AB + ":", gueltig_ab)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            model_id = model_combo.currentData()
            m = model_map.get(model_id)
            model_rate = m.commission_rate if m else 0.0
            rate_val = rate_spin.value()
            override = rate_val if rate_val > 0 and rate_val != model_rate else None
            data = {
                'name': name_edit.text().strip() or emp.name,
                'role': role_combo.currentData(),
                'commission_model_id': model_id,
                'commission_rate_override': override,
                'tl_override_rate': tl_rate_spin.value() if tl_rate_spin.value() > 0 else None,
                'tl_override_basis': tl_basis_combo.currentData(),
                'teamleiter_id': tl_combo.currentData(),
                'gueltig_ab': gueltig_ab.date().toString("yyyy-MM-dd"),
            }
            self._save_worker = SaveEmployeeWorker(self._backend, emp.id, data)
            self._save_worker.finished.connect(self._on_save_finished)
            self._save_worker.error.connect(self._on_save_error)
            self._save_worker.start()

    def _deactivate_employee(self, emp: Employee):
        try:
            self._backend.delete_employee(emp.id, hard=False)
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_DEACTIVATED)
            self._load_data()
        except APIError:
            pass

    def _activate_employee(self, emp: Employee):
        try:
            success, _ = self._backend.update_employee(emp.id, {'is_active': True})
            if success and self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_ACTIVATED)
            self._load_data()
        except APIError:
            pass

    def _delete_employee(self, emp: Employee):
        answer = QMessageBox.question(
            self,
            texts.PROVISION_EMP_DELETE_CONFIRM_TITLE,
            texts.PROVISION_EMP_DELETE_CONFIRM.format(name=emp.name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self._backend.delete_employee(emp.id, hard=True)
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_DELETED)
            self._load_data()
        except APIError as e:
            error_msg = str(e)
            if '409' in error_msg:
                if self._toast_manager:
                    self._toast_manager.show_warning(texts.PROVISION_EMP_DELETE_HAS_REF)
            else:
                if self._toast_manager:
                    self._toast_manager.show_error(error_msg)

    # ── Model context menu + edit/delete ──

    def _model_context_menu(self, pos, model: CommissionModel, card: QFrame):
        menu = QMenu(self)
        menu.addAction(texts.PROVISION_MENU_EDIT, lambda: self._edit_model(model))
        menu.addAction(texts.PROVISION_MENU_DEACTIVATE, lambda: self._deactivate_model(model))
        menu.exec(card.mapToGlobal(pos))

    def _edit_model(self, model: CommissionModel):
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_MENU_EDIT)
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)

        name_edit = QLineEdit(model.name)
        form.addRow(texts.PROVISION_MODEL_COL_NAME + ":", name_edit)

        rate_spin = QDoubleSpinBox()
        rate_spin.setRange(0, 100)
        rate_spin.setDecimals(1)
        rate_spin.setSuffix("%")
        rate_spin.setValue(model.commission_rate)
        form.addRow(texts.PROVISION_DIST_MODEL_COL_BERATER + ":", rate_spin)

        tl_rate_spin = QDoubleSpinBox()
        tl_rate_spin.setRange(0, 100)
        tl_rate_spin.setDecimals(1)
        tl_rate_spin.setSuffix("%")
        tl_rate_spin.setValue(model.tl_rate or 0.0)
        tl_rate_spin.setSpecialValueText("\u2014")
        form.addRow(texts.PROVISION_MODEL_COL_TL_RATE + ":", tl_rate_spin)

        tl_basis_combo = QComboBox()
        tl_basis_combo.addItem(texts.PROVISION_EMP_DLG_TL_BASIS_BERATER, "berater_anteil")
        tl_basis_combo.addItem(texts.PROVISION_EMP_DLG_TL_BASIS_GESAMT, "gesamt_courtage")
        if model.tl_basis == "gesamt_courtage":
            tl_basis_combo.setCurrentIndex(1)
        form.addRow(texts.PROVISION_MODEL_COL_TL_BASIS + ":", tl_basis_combo)

        desc_edit = QLineEdit(model.description or "")
        form.addRow(texts.PROVISION_MODEL_COL_DESC + ":", desc_edit)

        gueltig_ab = QDateEdit()
        gueltig_ab.setCalendarPopup(True)
        gueltig_ab.setDate(QDate.currentDate())
        gueltig_ab.setDisplayFormat("dd.MM.yyyy")
        gueltig_ab.setToolTip(texts.PROVISION_GUELTIG_AB_HINT)
        form.addRow(texts.PROVISION_GUELTIG_AB + ":", gueltig_ab)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            data = {
                'name': name_edit.text().strip() or model.name,
                'commission_rate': rate_spin.value(),
                'tl_rate': tl_rate_spin.value() if tl_rate_spin.value() > 0 else None,
                'tl_basis': tl_basis_combo.currentData(),
                'description': desc_edit.text().strip() or None,
                'gueltig_ab': gueltig_ab.date().toString("yyyy-MM-dd"),
            }
            self._save_worker = SaveModelWorker(self._backend, model.id, data)
            self._save_worker.finished.connect(self._on_save_finished)
            self._save_worker.error.connect(self._on_save_error)
            self._save_worker.start()

    def _on_save_finished(self, success: bool, summary):
        if success:
            if summary:
                msg = texts.PROVISION_RECALC_TOAST.format(
                    splits=summary.splits_recalculated,
                    abrechnungen=summary.abrechnungen_regenerated,
                )
                if self._toast_manager:
                    self._toast_manager.show_success(msg)
                if summary.splits_recalculated > 0 or summary.abrechnungen_regenerated > 0:
                    self.data_changed.emit()
            else:
                if self._toast_manager:
                    self._toast_manager.show_success(texts.PROVISION_RECALC_TOAST_NO_CHANGES)
            self._load_data()

    def _on_save_error(self, error_msg: str):
        if self._toast_manager:
            self._toast_manager.show_error(error_msg)

    def _deactivate_model(self, model: CommissionModel):
        if self._backend.delete_model(model.id):
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_DEACTIVATED)
            self._load_data()
