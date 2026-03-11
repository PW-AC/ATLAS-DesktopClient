"""
Provisions-Einstellungen Panel.

Allgemeine PM-Einstellungen (Default-Vermittler) und Gefahrenzone (Reset).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QProgressBar, QSizePolicy, QComboBox,
    QDoubleSpinBox, QCheckBox,
)
from PySide6.QtCore import Signal, Qt, QTimer, QThread

from api.provision import ProvisionAPI
from infrastructure.cache.provision_cache import ProvisionCache
from ui.styles.tokens import (
    PRIMARY_0, PRIMARY_500, PRIMARY_900, ACCENT_500,
    FONT_BODY, FONT_HEADLINE, FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    DANGER_500, SUCCESS_500,
    ERROR, ERROR_LIGHT, BORDER_DEFAULT, BLUE_BRIGHT, INFO_LIGHT,
)
from i18n import de as texts

import logging

logger = logging.getLogger(__name__)


class _SettingsLoadWorker(QThread):
    """Laedt PM-Settings und Mitarbeiterliste parallel."""
    finished = Signal(dict, list)
    error = Signal(str)

    def __init__(self, api):
        super().__init__()
        self._api = api

    def run(self):
        try:
            settings = self._api.get_pm_settings()
            employees = self._api.get_employees()
            self.finished.emit(settings, employees)
        except Exception as e:
            self.error.emit(str(e))


class _SettingsSaveWorker(QThread):
    """Speichert PM-Settings."""
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, api, settings: dict):
        super().__init__()
        self._api = api
        self._settings = settings

    def run(self):
        try:
            ok = self._api.update_pm_settings(self._settings)
            self.finished.emit(ok)
        except Exception as e:
            self.error.emit(str(e))


class _ResetWorker(QThread):
    """Worker fuer den Datenbank-Reset (async)."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api

    def run(self):
        try:
            result = self._api.reset_provision_data()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ResetConfirmDialog(QDialog):
    """Bestaetigungsdialog mit 3-Sekunden-Countdown."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(texts.PROVISION_SETTINGS_RESET_CONFIRM_TITLE)
        self.setFixedSize(480, 320)
        self.setModal(True)

        self._countdown = 3
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        icon_lbl = QLabel("\u26A0\uFE0F")
        icon_lbl.setStyleSheet("font-size: 48pt;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        title = QLabel(texts.PROVISION_SETTINGS_RESET_CONFIRM_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            font-weight: 700;
            color: {DANGER_500};
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(texts.PROVISION_SETTINGS_RESET_CONFIRM_DESC)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {PRIMARY_500};
            line-height: 1.5;
        """)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()

        self._countdown_lbl = QLabel(texts.PROVISION_SETTINGS_RESET_COUNTDOWN.format(seconds=self._countdown))
        self._countdown_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {ACCENT_500};
            font-weight: 600;
        """)
        self._countdown_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._countdown_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self._cancel_btn = QPushButton(texts.PROVISION_SETTINGS_RESET_CANCEL)
        self._cancel_btn.setMinimumHeight(44)
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_0};
                border: 1px solid {PRIMARY_500};
                border-radius: 6px;
                padding: 10px 24px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            }}
            QPushButton:hover {{
                background-color: rgba(0,0,0,0.05);
            }}
        """)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._confirm_btn = QPushButton(texts.PROVISION_SETTINGS_RESET_CONFIRM_BTN.format(seconds=self._countdown))
        self._confirm_btn.setMinimumHeight(44)
        self._confirm_btn.setCursor(Qt.PointingHandCursor)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER_500};
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: 600;
                color: white;
            }}
            QPushButton:hover {{
                background-color: {ERROR};
            }}
            QPushButton:disabled {{
                background-color: {ERROR_LIGHT};
                color: {ERROR_LIGHT};
            }}
        """)
        self._confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._confirm_btn)

        layout.addLayout(btn_row)

    def showEvent(self, event):
        super().showEvent(event)
        self._countdown = 3
        self._update_ui()
        self._timer.start(1000)

    def _tick(self):
        self._countdown -= 1
        self._update_ui()
        if self._countdown <= 0:
            self._timer.stop()
            self._confirm_btn.setEnabled(True)
            self._confirm_btn.setText(texts.PROVISION_SETTINGS_RESET_CONFIRM_NOW)
            self._countdown_lbl.setText(texts.PROVISION_SETTINGS_RESET_READY)

    def _update_ui(self):
        if self._countdown > 0:
            self._countdown_lbl.setText(texts.PROVISION_SETTINGS_RESET_COUNTDOWN.format(seconds=self._countdown))
            self._confirm_btn.setText(texts.PROVISION_SETTINGS_RESET_CONFIRM_BTN.format(seconds=self._countdown))


class SettingsPanel(QWidget):
    """Einstellungen-Panel: Default-Vermittler + Gefahrenzone."""

    data_changed = Signal()

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api
        self._presenter = None
        self._toast_manager = None
        self._reset_worker = None
        self._settings_load_worker = None
        self._settings_save_worker = None
        self._employees = []
        self._current_default_berater_id = None
        self._initial_load_done = False
        self._setup_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_load_done:
            self._initial_load_done = True
            self._load_settings()

    @property
    def _backend(self):
        return self._presenter or self._api

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel(texts.PROVISION_SETTINGS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            font-weight: 700;
            color: {PRIMARY_900};
        """)
        layout.addWidget(title)

        # ── Allgemeine Einstellungen ──
        self._build_general_settings(layout)

        # ── Split-Engine Einstellungen ──
        self._build_split_settings(layout)

        layout.addStretch()

        danger_frame = QFrame()
        danger_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {ERROR_LIGHT};
                border: 2px solid {DANGER_500};
                border-radius: 12px;
            }}
        """)

        danger_layout = QVBoxLayout(danger_frame)
        danger_layout.setContentsMargins(24, 24, 24, 24)
        danger_layout.setSpacing(16)

        danger_title = QLabel(f"\u26A0\uFE0F  {texts.PROVISION_SETTINGS_DANGER_ZONE}")
        danger_title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14pt;
            font-weight: 700;
            color: {DANGER_500};
        """)
        danger_layout.addWidget(danger_title)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {DANGER_500}; opacity: 0.3;")
        danger_layout.addWidget(sep)

        reset_row = QHBoxLayout()
        reset_row.setSpacing(16)

        reset_info = QVBoxLayout()
        reset_info.setSpacing(4)

        reset_title = QLabel(texts.PROVISION_SETTINGS_RESET_TITLE)
        reset_title.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: 600;
            color: {PRIMARY_900};
        """)
        reset_info.addWidget(reset_title)

        reset_desc = QLabel(texts.PROVISION_SETTINGS_RESET_DESC)
        reset_desc.setWordWrap(True)
        reset_desc.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
            line-height: 1.4;
        """)
        reset_info.addWidget(reset_desc)

        deleted_lbl = QLabel(texts.PROVISION_SETTINGS_RESET_DELETED)
        deleted_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {DANGER_500};
            margin-top: 8px;
        """)
        reset_info.addWidget(deleted_lbl)

        kept_lbl = QLabel(texts.PROVISION_SETTINGS_RESET_KEPT)
        kept_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {SUCCESS_500};
        """)
        reset_info.addWidget(kept_lbl)

        reset_row.addLayout(reset_info, 1)

        self._reset_btn = QPushButton(texts.PROVISION_SETTINGS_RESET_BTN)
        self._reset_btn.setMinimumSize(180, 48)
        self._reset_btn.setCursor(Qt.PointingHandCursor)
        self._reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER_500};
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: 700;
                color: white;
            }}
            QPushButton:hover {{
                background-color: {ERROR};
            }}
            QPushButton:pressed {{
                background-color: {ERROR};
            }}
            QPushButton:disabled {{
                background-color: {ERROR_LIGHT};
            }}
        """)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        reset_row.addWidget(self._reset_btn, 0, Qt.AlignTop)

        danger_layout.addLayout(reset_row)
        layout.addWidget(danger_frame)

        layout.addStretch()

    # ── General Settings ──

    def _build_general_settings(self, parent_layout: QVBoxLayout):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_0};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 12px;
            }}
        """)

        fl = QVBoxLayout(frame)
        fl.setContentsMargins(24, 24, 24, 24)
        fl.setSpacing(16)

        section_title = QLabel(texts.PM_SETTINGS_SECTION_GENERAL)
        section_title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14pt;
            font-weight: 700;
            color: {PRIMARY_900};
        """)
        fl.addWidget(section_title)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: {BORDER_DEFAULT};")
        fl.addWidget(sep)

        row = QHBoxLayout()
        row.setSpacing(16)

        info_col = QVBoxLayout()
        info_col.setSpacing(4)

        lbl = QLabel(texts.PM_SETTINGS_DEFAULT_BERATER)
        lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: 600;
            color: {PRIMARY_900};
        """)
        info_col.addWidget(lbl)

        hint = QLabel(texts.PM_SETTINGS_DEFAULT_BERATER_HINT)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
            line-height: 1.4;
        """)
        info_col.addWidget(hint)

        row.addLayout(info_col, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        self._berater_combo = QComboBox()
        self._berater_combo.setMinimumWidth(260)
        self._berater_combo.setMinimumHeight(40)
        self._berater_combo.setStyleSheet(f"""
            QComboBox {{
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                padding: 6px 12px;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 6px;
                background-color: white;
                color: {PRIMARY_900};
            }}
            QComboBox:hover {{
                border-color: {ACCENT_500};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
        """)
        self._berater_combo.addItem(texts.PM_SETTINGS_DEFAULT_BERATER_NONE, None)
        right_col.addWidget(self._berater_combo)

        self._save_settings_btn = QPushButton(texts.PM_SETTINGS_SAVE_BTN)
        self._save_settings_btn.setMinimumHeight(40)
        self._save_settings_btn.setCursor(Qt.PointingHandCursor)
        self._save_settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: 600;
                color: white;
            }}
            QPushButton:hover {{
                background-color: {BLUE_BRIGHT};
            }}
            QPushButton:disabled {{
                background-color: {INFO_LIGHT};
            }}
        """)
        self._save_settings_btn.clicked.connect(self._on_save_settings)
        right_col.addWidget(self._save_settings_btn)

        row.addLayout(right_col)
        fl.addLayout(row)

        parent_layout.addWidget(frame)

    # ── Split-Engine Settings ──

    def _build_split_settings(self, parent_layout: QVBoxLayout):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_0};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 12px;
            }}
        """)

        fl = QVBoxLayout(frame)
        fl.setContentsMargins(24, 24, 24, 24)
        fl.setSpacing(16)

        section_title = QLabel(texts.PM_SETTINGS_SECTION_SPLIT)
        section_title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14pt;
            font-weight: 700;
            color: {PRIMARY_900};
        """)
        fl.addWidget(section_title)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: {BORDER_DEFAULT};")
        fl.addWidget(sep)

        formula_lbl = QLabel(texts.PM_SETTINGS_FACTOR_FORMULA)
        formula_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {ACCENT_500};
            font-weight: 600;
            padding: 8px 12px;
            background-color: {INFO_LIGHT};
            border-radius: 6px;
        """)
        fl.addWidget(formula_lbl)

        factors_row = QHBoxLayout()
        factors_row.setSpacing(24)

        f1_col = QVBoxLayout()
        f1_col.setSpacing(4)
        f1_lbl = QLabel(texts.PM_SETTINGS_FACTOR_1)
        f1_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: 600;
            color: {PRIMARY_900};
        """)
        f1_col.addWidget(f1_lbl)
        f1_hint = QLabel(texts.PM_SETTINGS_FACTOR_1_HINT)
        f1_hint.setWordWrap(True)
        f1_hint.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
        """)
        f1_col.addWidget(f1_hint)
        self._factor1_spin = QDoubleSpinBox()
        self._factor1_spin.setRange(0.01, 1.00)
        self._factor1_spin.setDecimals(2)
        self._factor1_spin.setSingleStep(0.05)
        self._factor1_spin.setValue(0.80)
        self._factor1_spin.setMinimumHeight(40)
        self._factor1_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                padding: 6px 12px;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 6px;
                background-color: white;
                color: {PRIMARY_900};
            }}
            QDoubleSpinBox:hover {{ border-color: {ACCENT_500}; }}
        """)
        f1_col.addWidget(self._factor1_spin)
        factors_row.addLayout(f1_col)

        f2_col = QVBoxLayout()
        f2_col.setSpacing(4)
        f2_lbl = QLabel(texts.PM_SETTINGS_FACTOR_2)
        f2_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: 600;
            color: {PRIMARY_900};
        """)
        f2_col.addWidget(f2_lbl)
        f2_hint = QLabel(texts.PM_SETTINGS_FACTOR_2_HINT)
        f2_hint.setWordWrap(True)
        f2_hint.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
        """)
        f2_col.addWidget(f2_hint)
        self._factor2_spin = QDoubleSpinBox()
        self._factor2_spin.setRange(0.01, 1.00)
        self._factor2_spin.setDecimals(2)
        self._factor2_spin.setSingleStep(0.05)
        self._factor2_spin.setValue(0.90)
        self._factor2_spin.setMinimumHeight(40)
        self._factor2_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                padding: 6px 12px;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 6px;
                background-color: white;
                color: {PRIMARY_900};
            }}
            QDoubleSpinBox:hover {{ border-color: {ACCENT_500}; }}
        """)
        f2_col.addWidget(self._factor2_spin)
        factors_row.addLayout(f2_col)

        fl.addLayout(factors_row)

        tl_sep = QFrame()
        tl_sep.setFixedHeight(1)
        tl_sep.setStyleSheet("background-color: {BORDER_DEFAULT};")
        fl.addWidget(tl_sep)

        tl_row = QHBoxLayout()
        tl_row.setSpacing(16)

        tl_info = QVBoxLayout()
        tl_info.setSpacing(4)
        tl_lbl = QLabel(texts.PM_SETTINGS_NO_TL_TO_COMPANY)
        tl_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: 600;
            color: {PRIMARY_900};
        """)
        tl_info.addWidget(tl_lbl)
        tl_hint = QLabel(texts.PM_SETTINGS_NO_TL_TO_COMPANY_HINT)
        tl_hint.setWordWrap(True)
        tl_hint.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
            line-height: 1.4;
        """)
        tl_info.addWidget(tl_hint)
        tl_row.addLayout(tl_info, 1)

        self._no_tl_checkbox = QCheckBox()
        self._no_tl_checkbox.setChecked(True)
        self._no_tl_checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 22px;
                height: 22px;
            }}
        """)
        tl_row.addWidget(self._no_tl_checkbox, 0, Qt.AlignTop)

        fl.addLayout(tl_row)

        parent_layout.addWidget(frame)

    def _load_settings(self):
        if self._settings_load_worker and self._settings_load_worker.isRunning():
            return
        self._save_settings_btn.setEnabled(False)
        self._settings_load_worker = _SettingsLoadWorker(self._backend)
        self._settings_load_worker.finished.connect(self._on_settings_loaded)
        self._settings_load_worker.error.connect(self._on_settings_load_error)
        self._settings_load_worker.start()

    def _on_settings_loaded(self, settings: dict, employees: list):
        self._employees = employees
        self._berater_combo.clear()
        self._berater_combo.addItem(texts.PM_SETTINGS_DEFAULT_BERATER_NONE, None)

        for emp in sorted(employees, key=lambda e: e.name):
            if emp.is_active:
                self._berater_combo.addItem(emp.name, emp.id)

        current_id = settings.get('xempus_default_berater_id')
        self._current_default_berater_id = int(current_id) if current_id else None

        if self._current_default_berater_id:
            for i in range(self._berater_combo.count()):
                if self._berater_combo.itemData(i) == self._current_default_berater_id:
                    self._berater_combo.setCurrentIndex(i)
                    break

        f1 = settings.get('split_factor_1')
        if f1:
            self._factor1_spin.setValue(float(f1))
        f2 = settings.get('split_factor_2')
        if f2:
            self._factor2_spin.setValue(float(f2))

        no_tl = settings.get('no_tl_alloc_to_company', '1')
        self._no_tl_checkbox.setChecked(no_tl != '0')

        self._save_settings_btn.setEnabled(True)

    def _on_settings_load_error(self, error: str):
        logger.error(f"Settings laden fehlgeschlagen: {error}")
        self._save_settings_btn.setEnabled(True)

    def _on_save_settings(self):
        selected_id = self._berater_combo.currentData()
        value = str(selected_id) if selected_id else ''

        payload = {
            'xempus_default_berater_id': value,
            'split_factor_1': str(self._factor1_spin.value()),
            'split_factor_2': str(self._factor2_spin.value()),
            'no_tl_alloc_to_company': '1' if self._no_tl_checkbox.isChecked() else '0',
        }

        self._save_settings_btn.setEnabled(False)
        self._settings_save_worker = _SettingsSaveWorker(
            self._backend, payload)
        self._settings_save_worker.finished.connect(self._on_settings_saved)
        self._settings_save_worker.error.connect(self._on_settings_save_error)
        self._settings_save_worker.start()

    def _on_settings_saved(self, ok: bool):
        self._save_settings_btn.setEnabled(True)
        if ok:
            self._current_default_berater_id = self._berater_combo.currentData()
            if self._toast_manager:
                self._toast_manager.show_success(texts.PM_SETTINGS_SAVED)
        else:
            if self._toast_manager:
                self._toast_manager.show_error(texts.PM_SETTINGS_SAVE_ERROR)

    def _on_settings_save_error(self, error: str):
        self._save_settings_btn.setEnabled(True)
        logger.error(f"Settings speichern fehlgeschlagen: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(texts.PM_SETTINGS_SAVE_ERROR)

    # ── Reset (Gefahrenzone) ──

    def _on_reset_clicked(self):
        dialog = ResetConfirmDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._execute_reset()

    def _execute_reset(self):
        self._reset_btn.setEnabled(False)
        self._reset_btn.setText(texts.PROVISION_SETTINGS_RESET_RUNNING)

        self._reset_worker = _ResetWorker(self._backend)
        self._reset_worker.finished.connect(self._on_reset_finished)
        self._reset_worker.error.connect(self._on_reset_error)
        self._reset_worker.start()

    def _on_reset_finished(self, result: dict):
        self._reset_btn.setEnabled(True)
        self._reset_btn.setText(texts.PROVISION_SETTINGS_RESET_BTN)

        ProvisionCache.instance().invalidate_all()

        deleted = result.get('deleted', {})
        msg = texts.PROVISION_SETTINGS_RESET_SUCCESS.format(
            commissions=deleted.get('pm_commissions', 0),
            contracts=deleted.get('pm_contracts', 0),
            batches=deleted.get('pm_import_batches', 0),
        )
        if self._toast_manager:
            self._toast_manager.show_success(msg)
        logger.info(f"Provision-Reset erfolgreich: {result}")
        self.data_changed.emit()

    def _on_reset_error(self, error: str):
        self._reset_btn.setEnabled(True)
        self._reset_btn.setText(texts.PROVISION_SETTINGS_RESET_BTN)

        if self._toast_manager:
            self._toast_manager.show_error(texts.PROVISION_SETTINGS_RESET_ERROR.format(error=error))
        logger.error(f"Provision-Reset Fehler: {error}")

    def refresh(self):
        self._load_settings()
