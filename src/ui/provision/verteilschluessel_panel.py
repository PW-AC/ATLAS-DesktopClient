"""
Verteilschluessel & Rollen-Panel: Provisionsmodelle + Mitarbeiter merged.

Ersetzt: employees_panel.py
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QFrame, QPushButton, QDialog, QComboBox,
    QLineEdit, QFormLayout, QDialogButtonBox, QDoubleSpinBox,
    QTextEdit, QScrollArea, QSizePolicy, QMenu, QMessageBox,
    QDateEdit, QGroupBox, QCheckBox,
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QModelIndex, QDate,
)
from typing import List, Optional

from api.client import APIClient
from api.admin import AdminAPI
from api.provision import ProvisionAPI
from domain.provision.entities import Employee, CommissionModel
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500, ACCENT_HOVER,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    ERROR, SUCCESS, INFO_LIGHT, TABLE_BORDER,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    ROLE_BADGE_COLORS, build_rich_tooltip, get_provision_table_style,
)
from ui.provision.widgets import (
    SectionHeader, PillBadgeDelegate, ProvisionLoadingOverlay,
    format_eur, get_secondary_button_style,
)
from ui.provision.workers import VerteilschluesselLoadWorker, SaveEmployeeWorker, SaveModelWorker
from ui.provision.models import DistEmployeeModel
from infrastructure.threading.worker_utils import run_worker
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class VerteilschluesselPanel(QWidget):
    """Provisionsmodelle und Mitarbeiter mit Rollen.

    Implementiert IDistributionView fuer den DistributionPresenter.
    """

    navigate_to_panel = Signal(int)
    data_changed = Signal()

    def __init__(self, api: ProvisionAPI = None, api_client: APIClient = None):
        super().__init__()
        self._api = api
        self._admin_api = AdminAPI(api_client) if api_client else None
        self._presenter = None
        self._worker = None
        self._save_worker = None
        self._models: List[CommissionModel] = []
        self._employees: List[Employee] = []
        self._toast_manager = None
        self._split_factors = (0.8, 0.9)
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

        # Formel-Banner
        self._formula_frame = QFrame()
        self._formula_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {INFO_LIGHT};
                border: 1.5px solid {ACCENT_500};
                border-radius: 10px;
            }}
        """)
        formula_layout = QVBoxLayout(self._formula_frame)
        formula_layout.setContentsMargins(20, 16, 20, 16)
        formula_layout.setSpacing(6)

        formula_title = QLabel(texts.PROVISION_FORMULA_BANNER)
        formula_title.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: 700;
            color: {ACCENT_500};
            border: none;
        """)
        formula_layout.addWidget(formula_title)

        self._formula_lines = QLabel()
        self._formula_lines.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {PRIMARY_900};
            border: none;
            line-height: 1.6;
        """)
        formula_layout.addWidget(self._formula_lines)

        self._formula_source = QLabel(texts.PROVISION_FORMULA_SOURCE)
        self._formula_source.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
            border: none;
            font-style: italic;
        """)
        formula_layout.addWidget(self._formula_source)

        self._update_formula_banner(0.8, 0.9)
        layout.addWidget(self._formula_frame)

        # Provisionsmodelle
        model_header = SectionHeader(
            texts.PROVISION_DIST_MODELS_TITLE,
            texts.PROVISION_DIST_MODELS_DESC,
        )
        add_model_btn = QPushButton(texts.PROVISION_DIST_MODEL_ADD)
        add_model_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 16px; font-weight: 500; }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
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
            'geschaeftsfuehrer': texts.PROVISION_EMP_ROLE_GESCHAEFTSFUEHRER,
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

    def _update_formula_banner(self, f1: float, f2: float):
        lines = (
            texts.PROVISION_FORMULA_CONS.format(f1=f1, f2=f2)
            + "\n" + texts.PROVISION_FORMULA_TL
            + "\n" + texts.PROVISION_FORMULA_FIRMA
        )
        self._formula_lines.setText(lines)

    def _on_loaded(self, models: List[CommissionModel], employees: List[Employee], settings=None):
        self._loading_overlay.setVisible(False)
        self._models = models
        self._employees = employees
        if settings:
            f1 = float(settings.get('split_factor_1', '0.8'))
            f2 = float(settings.get('split_factor_2', '0.9'))
            self._split_factors = (f1, f2)
            self._update_formula_banner(f1, f2)
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

        f1, f2 = self._split_factors

        for model in self._models:
            if not model.is_active:
                continue
            card = QFrame()
            card.setStyleSheet(f"background: {BG_PRIMARY}; border: 1.5px solid {TABLE_BORDER}; border-radius: 8px;")
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

            base_rate = model.commission_rate
            tl_rate_val = model.tl_rate or 0.0
            uses_factors = model.apply_split_factors

            example_amount = 1000.0
            if uses_factors:
                eff_rate = round(base_rate * f1 * f2, 2)
                berater_amount = round(example_amount * f1 * f2 * base_rate / 100, 2)
                rate_text = texts.PROVISION_FORMULA_EFF_RATE.format(
                    base_rate=f"{base_rate:.1f}", f1=f1, f2=f2, eff_rate=f"{eff_rate:.1f}")
            else:
                eff_rate = base_rate
                berater_amount = round(example_amount * base_rate / 100, 2)
                rate_text = f"{texts.PROVISION_DIST_MODEL_COL_BERATER}: {base_rate:.1f}%"
            tl_amount = round(example_amount * tl_rate_val / 100, 2)
            ag_amount = round(example_amount - berater_amount - tl_amount, 2)

            rate_lbl = QLabel(rate_text)
            rate_lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY}; border: none; font-weight: 500;")
            card_layout.addWidget(rate_lbl)

            if tl_rate_val > 0:
                tl_lbl = QLabel(texts.PROVISION_FORMULA_TL_FIXED.format(
                    tl_rate=f"{tl_rate_val:.1f}",
                ))
                tl_lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY}; border: none; font-weight: 500;")
                card_layout.addWidget(tl_lbl)

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

        factors_cb = QCheckBox(texts.PM_SETTINGS_FACTOR_FORMULA)
        factors_cb.setChecked(True)
        form.addRow(texts.PM_SETTINGS_SECTION_SPLIT + ":", factors_cb)

        desc_edit = QLineEdit()
        form.addRow(texts.PROVISION_MODEL_COL_DESC + ":", desc_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            if name:
                data = {
                    'name': name,
                    'commission_rate': rate_spin.value(),
                    'tl_rate': tl_rate_spin.value() if tl_rate_spin.value() > 0 else None,
                    'tl_basis': 'gesamt_courtage',
                    'apply_split_factors': 1 if factors_cb.isChecked() else 0,
                    'description': desc_edit.text().strip() or None,
                }
                run_worker(
                    self,
                    lambda w, d=data: self._backend.create_model(d),
                    lambda _: self._load_data(),
                )

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
        role_combo.addItem(texts.PROVISION_EMP_ROLE_GESCHAEFTSFUEHRER, "geschaeftsfuehrer")
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

        tl_basis_lbl = QLabel(texts.PM_SETTINGS_TL_BASIS_FIXED)
        tl_basis_lbl.setEnabled(False)
        form.addRow(texts.PROVISION_DIST_EMP_COL_TL_BASIS + ":", tl_basis_lbl)

        model_map = self._get_model_map()

        def _on_model_changed():
            m = model_map.get(model_combo.currentData())
            if m:
                rate_spin.setValue(m.commission_rate)
                if m.tl_rate is not None:
                    tl_rate_spin.setValue(m.tl_rate)
            else:
                rate_spin.setValue(0.0)
                tl_rate_spin.setValue(0.0)

        model_combo.currentIndexChanged.connect(_on_model_changed)

        tl_combo = QComboBox()
        tl_combo.addItem("\u2014", None)
        for e in self._employees:
            if e.role in ('teamleiter', 'geschaeftsfuehrer') and e.is_active:
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
                    'tl_override_basis': 'gesamt_courtage',
                    'teamleiter_id': tl_combo.currentData(),
                }
                run_worker(
                    self,
                    lambda w, d=data: self._backend.create_employee(d),
                    self._on_employee_created,
                )

    def _on_employee_created(self, result):
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
            (texts.PROVISION_EMP_ROLE_GESCHAEFTSFUEHRER, "geschaeftsfuehrer"),
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

        tl_basis_lbl = QLabel(texts.PM_SETTINGS_TL_BASIS_FIXED)
        tl_basis_lbl.setEnabled(False)
        form.addRow(texts.PROVISION_DIST_EMP_COL_TL_BASIS + ":", tl_basis_lbl)

        model_map = self._get_model_map()

        def _on_model_changed():
            m = model_map.get(model_combo.currentData())
            if m:
                rate_spin.setValue(m.commission_rate)
                if m.tl_rate is not None:
                    tl_rate_spin.setValue(m.tl_rate)
            else:
                rate_spin.setValue(0.0)
                tl_rate_spin.setValue(0.0)

        model_combo.currentIndexChanged.connect(_on_model_changed)

        tl_combo = QComboBox()
        tl_combo.addItem("\u2014", None)
        for e in self._employees:
            if e.role in ('teamleiter', 'geschaeftsfuehrer') and e.is_active and e.id != emp.id:
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

        user_section = self._build_user_account_section(dlg, emp)
        form.addRow(user_section)

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
                'tl_override_basis': 'gesamt_courtage',
                'teamleiter_id': tl_combo.currentData(),
                'gueltig_ab': gueltig_ab.date().toString("yyyy-MM-dd"),
            }
            pending_user_id = user_section.property('pending_user_id')
            if pending_user_id is not None:
                data['user_id'] = pending_user_id
            self.show_loading(True)
            self._save_worker = SaveEmployeeWorker(self._backend, emp.id, data)
            self._save_worker.finished.connect(self._on_save_finished)
            self._save_worker.error.connect(self._on_save_error)
            self._save_worker.start()

    # ── Nutzerkonto-Abschnitt im Edit-Dialog ──

    def _build_user_account_section(self, parent_dlg: QDialog, emp: Employee) -> QGroupBox:
        """Baut den Nutzerkonto-Abschnitt fuer den Employee-Edit-Dialog."""
        group = QGroupBox(texts.PM_EMP_USER_SECTION)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        group.setProperty('pending_user_id', None)

        if emp.has_user:
            self._build_user_linked_view(layout, parent_dlg, group, emp)
        else:
            self._build_user_unlinked_view(layout, parent_dlg, group, emp)

        return group

    def _build_user_linked_view(self, layout: QVBoxLayout, parent_dlg: QDialog,
                                group: QGroupBox, emp: Employee):
        email_display = emp.user_email or ''
        if email_display:
            info_text = texts.PM_EMP_USER_LINKED.format(
                username=emp.user_username or '?', email=email_display)
        else:
            info_text = texts.PM_EMP_USER_LINKED_NO_EMAIL.format(
                username=emp.user_username or '?')

        info_label = QLabel(info_text)
        info_label.setStyleSheet(f"color: {SUCCESS}; font-size: {FONT_SIZE_BODY};")
        layout.addWidget(info_label)

        unlink_btn = QPushButton(texts.PM_EMP_USER_UNLINK)
        unlink_btn.setStyleSheet(get_secondary_button_style())
        unlink_btn.clicked.connect(
            lambda: self._on_unlink_user(group, layout, parent_dlg, emp))
        layout.addWidget(unlink_btn)

    def _on_unlink_user(self, group: QGroupBox, layout: QVBoxLayout,
                        parent_dlg: QDialog, emp: Employee):
        reply = QMessageBox.question(
            parent_dlg,
            texts.PM_EMP_USER_SECTION,
            texts.PM_EMP_USER_UNLINK_CONFIRM,
        )
        if reply == QMessageBox.Yes:
            group.setProperty('pending_user_id', 0)
            self._clear_layout(layout)
            done_label = QLabel(texts.PM_EMP_USER_UNLINK_SUCCESS)
            done_label.setStyleSheet(f"color: {PRIMARY_500}; font-style: italic;")
            layout.addWidget(done_label)

    def _build_user_unlinked_view(self, layout: QVBoxLayout, parent_dlg: QDialog,
                                  group: QGroupBox, emp: Employee):
        info_label = QLabel(texts.PM_EMP_USER_NONE)
        info_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY};")
        layout.addWidget(info_label)

        btn_row = QHBoxLayout()
        link_btn = QPushButton(texts.PM_EMP_USER_LINK_EXISTING)
        link_btn.setStyleSheet(get_secondary_button_style())
        link_btn.clicked.connect(
            lambda: self._on_link_existing_user(group, layout, parent_dlg))
        btn_row.addWidget(link_btn)

        create_btn = QPushButton(texts.PM_EMP_USER_CREATE_NEW)
        create_btn.setStyleSheet(get_secondary_button_style())
        create_btn.clicked.connect(
            lambda: self._on_create_new_user(group, layout, parent_dlg, emp))
        btn_row.addWidget(create_btn)

        if not self._admin_api:
            link_btn.setEnabled(False)
            link_btn.setToolTip("AdminAPI nicht verfuegbar")
            create_btn.setEnabled(False)
            create_btn.setToolTip("AdminAPI nicht verfuegbar")

        layout.addLayout(btn_row)

    def _on_link_existing_user(self, group: QGroupBox, layout: QVBoxLayout,
                               parent_dlg: QDialog):
        if not self._admin_api:
            return
        run_worker(
            self,
            lambda w: self._admin_api.get_users(),
            lambda users, g=group, l=layout: self._populate_user_combo(g, l, users),
            on_error=lambda msg: self._on_link_user_error(msg),
        )

    def _on_link_user_error(self, msg):
        logger.error(f"Fehler beim Laden der Nutzer: {msg}")
        if self._toast_manager:
            self._toast_manager.show_error(msg)

    def _populate_user_combo(self, group: QGroupBox, layout: QVBoxLayout, users):
        linked_ids = {e.user_id for e in self._employees if e.user_id}
        available = [u for u in users if u.get('id') not in linked_ids
                     and u.get('is_active', True)]

        if not available:
            if self._toast_manager:
                self._toast_manager.show_info(texts.PM_EMP_USER_NONE)
            return

        self._clear_layout(layout)
        select_label = QLabel(texts.PM_EMP_USER_LINK_EXISTING)
        select_label.setStyleSheet(f"font-weight: bold; font-size: {FONT_SIZE_BODY};")
        layout.addWidget(select_label)

        combo = QComboBox()
        combo.addItem(texts.PM_EMP_USER_SELECT, None)
        for u in available:
            display = u.get('username', '')
            email = u.get('email', '')
            if email:
                display += f" ({email})"
            combo.addItem(display, u.get('id'))
        layout.addWidget(combo)

        def _on_selected():
            uid = combo.currentData()
            if uid:
                group.setProperty('pending_user_id', uid)

        combo.currentIndexChanged.connect(_on_selected)

    def _on_create_new_user(self, group: QGroupBox, layout: QVBoxLayout,
                            parent_dlg: QDialog, emp: Employee):
        if not self._admin_api:
            return

        self._clear_layout(layout)
        create_label = QLabel(texts.PM_EMP_USER_CREATE_NEW)
        create_label.setStyleSheet(f"font-weight: bold; font-size: {FONT_SIZE_BODY};")
        layout.addWidget(create_label)

        create_form = QFormLayout()
        create_form.setSpacing(6)

        suggested_username = emp.name.lower().replace(' ', '.').replace('ue', 'ue').replace('ae', 'ae').replace('oe', 'oe')
        username_edit = QLineEdit(suggested_username)
        username_edit.setPlaceholderText(texts.PM_EMP_USER_USERNAME)
        create_form.addRow(texts.PM_EMP_USER_USERNAME + ":", username_edit)

        email_edit = QLineEdit()
        email_edit.setPlaceholderText(texts.PM_EMP_USER_EMAIL)
        create_form.addRow(texts.PM_EMP_USER_EMAIL + ":", email_edit)

        password_edit = QLineEdit()
        password_edit.setPlaceholderText(texts.PM_EMP_USER_PASSWORD)
        password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        create_form.addRow(texts.PM_EMP_USER_PASSWORD + ":", password_edit)

        layout.addLayout(create_form)

        perm_group_box = QGroupBox(texts.PM_EMP_USER_PERMISSIONS)
        perm_layout = QVBoxLayout(perm_group_box)
        perm_layout.setSpacing(4)
        perm_checkboxes = {}
        for perm_key, perm_name in texts.PERMISSION_NAMES.items():
            cb = QCheckBox(perm_name)
            cb.setChecked(False)
            perm_checkboxes[perm_key] = cb
            perm_layout.addWidget(cb)
        layout.addWidget(perm_group_box)

        confirm_btn = QPushButton(texts.PM_EMP_USER_CREATE_NEW)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)

        status_label = QLabel()
        layout.addWidget(status_label)

        def _do_create():
            uname = username_edit.text().strip()
            if len(uname) < 3:
                status_label.setText(texts.PM_EMP_USER_NAME_TOO_SHORT)
                status_label.setStyleSheet(f"color: {ERROR};")
                return
            pw = password_edit.text()
            if len(pw) < 8:
                status_label.setText(texts.PM_EMP_USER_PW_TOO_SHORT)
                status_label.setStyleSheet(f"color: {ERROR};")
                return
            email = email_edit.text().strip()
            perms = [k for k, cb in perm_checkboxes.items() if cb.isChecked()]
            confirm_btn.setEnabled(False)
            status_label.setText(texts.PM_EMP_USER_CREATE_NEW + "...")
            status_label.setStyleSheet(f"color: {PRIMARY_500};")

            run_worker(
                self,
                lambda w: self._admin_api.create_user(
                    username=uname, password=pw, email=email,
                    account_type='user', permissions=perms,
                ),
                lambda new_user: _on_user_created(new_user),
                on_error=lambda msg: _on_user_create_error(msg),
            )

        def _on_user_created(new_user):
            new_user_id = new_user.get('id') if new_user else None
            if new_user_id:
                group.setProperty('pending_user_id', new_user_id)
                status_label.setText(texts.PM_EMP_USER_CREATE_SUCCESS)
                status_label.setStyleSheet(f"color: {SUCCESS};")
                confirm_btn.setEnabled(False)
                username_edit.setReadOnly(True)
                email_edit.setReadOnly(True)
                password_edit.setReadOnly(True)
                for cb in perm_checkboxes.values():
                    cb.setEnabled(False)
            else:
                status_label.setText(texts.PM_EMP_USER_CREATE_ERROR.format(
                    error="Keine User-ID erhalten"))
                status_label.setStyleSheet(f"color: {ERROR};")
                confirm_btn.setEnabled(True)

        def _on_user_create_error(msg):
            status_label.setText(texts.PM_EMP_USER_CREATE_ERROR.format(error=msg))
            status_label.setStyleSheet(f"color: {ERROR};")
            confirm_btn.setEnabled(True)

        confirm_btn.clicked.connect(_do_create)
        layout.addWidget(confirm_btn)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                VerteilschluesselPanel._clear_sub_layout(item.layout())

    @staticmethod
    def _clear_sub_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                VerteilschluesselPanel._clear_sub_layout(item.layout())

    def _deactivate_employee(self, emp: Employee):
        run_worker(
            self,
            lambda w, eid=emp.id: self._backend.delete_employee(eid, hard=False),
            lambda _: self._on_emp_deactivated(),
        )

    def _on_emp_deactivated(self):
        if self._toast_manager:
            self._toast_manager.show_success(texts.PROVISION_TOAST_DEACTIVATED)
        self._load_data()

    def _activate_employee(self, emp: Employee):
        run_worker(
            self,
            lambda w, eid=emp.id: self._backend.update_employee(eid, {'is_active': True}),
            self._on_emp_activated,
        )

    def _on_emp_activated(self, result):
        success = result[0] if isinstance(result, tuple) else result
        if success and self._toast_manager:
            self._toast_manager.show_success(texts.PROVISION_TOAST_ACTIVATED)
        self._load_data()

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
        run_worker(
            self,
            lambda w, eid=emp.id: self._backend.delete_employee(eid, hard=True),
            lambda _: self._on_emp_hard_deleted(),
            on_error=self._on_emp_delete_error,
        )

    def _on_emp_hard_deleted(self):
        if self._toast_manager:
            self._toast_manager.show_success(texts.PROVISION_TOAST_DELETED)
        self._load_data()

    def _on_emp_delete_error(self, error_msg):
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

        factors_cb = QCheckBox(texts.PM_SETTINGS_FACTOR_FORMULA)
        factors_cb.setChecked(model.apply_split_factors)
        form.addRow(texts.PM_SETTINGS_SECTION_SPLIT + ":", factors_cb)

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
                'tl_basis': 'gesamt_courtage',
                'apply_split_factors': 1 if factors_cb.isChecked() else 0,
                'description': desc_edit.text().strip() or None,
                'gueltig_ab': gueltig_ab.date().toString("yyyy-MM-dd"),
            }
            self.show_loading(True)
            self._save_worker = SaveModelWorker(self._backend, model.id, data)
            self._save_worker.finished.connect(self._on_save_finished)
            self._save_worker.error.connect(self._on_save_error)
            self._save_worker.start()

    def _on_save_finished(self, success: bool, summary):
        self.show_loading(False)
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
        self.show_loading(False)
        if self._toast_manager:
            self._toast_manager.show_error(error_msg)

    def _deactivate_model(self, model: CommissionModel):
        run_worker(
            self,
            lambda w, mid=model.id: self._backend.delete_model(mid),
            self._on_model_deactivated,
        )

    def _on_model_deactivated(self, success):
        if success:
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_DEACTIVATED)
            self._load_data()
