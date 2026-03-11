"""
Workforce Triggers View - Trigger-Verwaltung und Ausfuehrungslog.

Zeigt alle konfigurierten Trigger an, erlaubt CRUD-Operationen,
Ein-/Ausschalten und zeigt das Ausfuehrungsprotokoll.
"""

import json
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit,
    QHeaderView, QDialog, QFormLayout, QFrame, QCheckBox,
    QTextEdit, QTabWidget, QSpinBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from workforce.api_client import WorkforceApiClient
from ui.workforce.utils import format_date_de
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, FONT_BODY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_H2,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT, RADIUS_MD,
    SUCCESS, ERROR,
    get_button_primary_style, get_button_secondary_style,
    get_button_danger_style, get_dialog_style, get_input_style,
)
from i18n import de as texts

logger = logging.getLogger(__name__)

_EVENTS = [
    ('employee_joined', 'WF_TRIGGER_EVT_JOINED'),
    ('employee_left', 'WF_TRIGGER_EVT_LEFT'),
    ('employee_changed', 'WF_TRIGGER_EVT_CHANGED'),
    ('status_changed', 'WF_TRIGGER_EVT_STATUS'),
    ('sync_completed', 'WF_TRIGGER_EVT_SYNC'),
]

_ACTION_TYPES = [
    ('email', 'WF_TRIGGER_ACT_EMAIL'),
    ('webhook', 'WF_TRIGGER_ACT_WEBHOOK'),
    ('log', 'WF_TRIGGER_ACT_LOG'),
]


class _TriggerLoadThread(QThread):
    """Laedt Trigger-Daten im Hintergrund."""
    finished = Signal(object)  # list; object verhindert Shiboken copy-convert Fehler
    error = Signal(str)

    def __init__(self, api: WorkforceApiClient):
        super().__init__()
        self._api = api

    def run(self):
        try:
            result = self._api.get_triggers()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _TriggerSaveThread(QThread):
    """Speichert oder erstellt einen Trigger."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: WorkforceApiClient, data: dict, trigger_id: int = None):
        super().__init__()
        self._api = api
        self._data = data
        self._trigger_id = trigger_id

    def run(self):
        try:
            if self._trigger_id:
                result = self._api.update_trigger(self._trigger_id, self._data)
            else:
                result = self._api.create_trigger(self._data)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _TriggerDeleteThread(QThread):
    """Loescht einen Trigger."""
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, api: WorkforceApiClient, trigger_id: int):
        super().__init__()
        self._api = api
        self._trigger_id = trigger_id

    def run(self):
        try:
            ok = self._api.delete_trigger(self._trigger_id)
            self.finished.emit(ok)
        except Exception as e:
            self.error.emit(str(e))


class _TriggerToggleThread(QThread):
    """Aktiviert/deaktiviert einen Trigger."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: WorkforceApiClient, trigger_id: int):
        super().__init__()
        self._api = api
        self._trigger_id = trigger_id

    def run(self):
        try:
            result = self._api.toggle_trigger(self._trigger_id)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _RunsLoadThread(QThread):
    """Laedt Trigger-Runs."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: WorkforceApiClient, page: int = 1, trigger_id: int = None,
                 employer_id: int = None, status: str = None):
        super().__init__()
        self._api = api
        self._page = page
        self._trigger_id = trigger_id
        self._employer_id = employer_id
        self._status = status

    def run(self):
        try:
            result = self._api.get_trigger_runs(
                page=self._page, trigger_id=self._trigger_id,
                employer_id=self._employer_id, status=self._status,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _TriggerDialog(QDialog):
    """Dialog zum Erstellen/Bearbeiten eines Triggers."""

    def __init__(self, parent=None, trigger: dict = None):
        super().__init__(parent)
        self._trigger = trigger or {}
        self.setWindowTitle(
            texts.WF_TRIGGERS_EDIT if trigger else texts.WF_TRIGGERS_CREATE
        )
        self.setMinimumWidth(520)
        self.setStyleSheet(get_dialog_style())
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_input = QLineEdit(self._trigger.get('name', ''))
        self._name_input.setPlaceholderText(texts.WF_TRIGGERS_NAME_PLACEHOLDER)
        form.addRow(texts.WF_TRIGGERS_NAME, self._name_input)

        self._event_combo = QComboBox()
        for event_key, text_attr in _EVENTS:
            self._event_combo.addItem(getattr(texts, text_attr, event_key), event_key)
        if self._trigger.get('event'):
            idx = self._event_combo.findData(self._trigger['event'])
            if idx >= 0:
                self._event_combo.setCurrentIndex(idx)
        form.addRow(texts.WF_TRIGGERS_EVENT, self._event_combo)

        self._action_combo = QComboBox()
        for act_key, text_attr in _ACTION_TYPES:
            self._action_combo.addItem(getattr(texts, text_attr, act_key), act_key)
        if self._trigger.get('action_type'):
            idx = self._action_combo.findData(self._trigger['action_type'])
            if idx >= 0:
                self._action_combo.setCurrentIndex(idx)
        form.addRow(texts.WF_TRIGGERS_ACTION_TYPE, self._action_combo)

        self._logic_combo = QComboBox()
        self._logic_combo.addItem("AND", "AND")
        self._logic_combo.addItem("OR", "OR")
        if self._trigger.get('condition_logic') == 'OR':
            self._logic_combo.setCurrentIndex(1)
        form.addRow(texts.WF_TRIGGERS_CONDITION_LOGIC, self._logic_combo)

        self._conditions_edit = QTextEdit()
        self._conditions_edit.setMaximumHeight(100)
        self._conditions_edit.setPlaceholderText(texts.WF_TRIGGERS_CONDITIONS_PLACEHOLDER)
        conditions = self._trigger.get('conditions')
        if conditions:
            if isinstance(conditions, list):
                self._conditions_edit.setPlainText(json.dumps(conditions, indent=2, ensure_ascii=False))
            else:
                self._conditions_edit.setPlainText(str(conditions))
        form.addRow(texts.WF_TRIGGERS_CONDITIONS, self._conditions_edit)

        self._config_edit = QTextEdit()
        self._config_edit.setMaximumHeight(120)
        self._config_edit.setPlaceholderText(texts.WF_TRIGGERS_CONFIG_PLACEHOLDER)
        config = self._trigger.get('action_config')
        if config:
            if isinstance(config, dict):
                self._config_edit.setPlainText(json.dumps(config, indent=2, ensure_ascii=False))
            else:
                self._config_edit.setPlainText(str(config))
        form.addRow(texts.WF_TRIGGERS_ACTION_CONFIG, self._config_edit)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.setStyleSheet(get_button_secondary_style())
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        save_btn = QPushButton(texts.SAVE)
        save_btn.setStyleSheet(get_button_primary_style())
        save_btn.clicked.connect(self._validate_and_accept)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _validate_and_accept(self):
        if not self._name_input.text().strip():
            if hasattr(self.parent(), '_toast_manager') and self.parent()._toast_manager:
                self.parent()._toast_manager.show_warning(texts.WF_TRIGGERS_NAME_REQUIRED)
            return

        cond_text = self._conditions_edit.toPlainText().strip()
        conditions = []
        if cond_text:
            try:
                conditions = json.loads(cond_text)
            except json.JSONDecodeError:
                if hasattr(self.parent(), '_toast_manager') and self.parent()._toast_manager:
                    self.parent()._toast_manager.show_warning(texts.WF_TRIGGERS_INVALID_JSON)
                return

        config_text = self._config_edit.toPlainText().strip()
        action_config = {}
        if config_text:
            try:
                action_config = json.loads(config_text)
            except json.JSONDecodeError:
                if hasattr(self.parent(), '_toast_manager') and self.parent()._toast_manager:
                    self.parent()._toast_manager.show_warning(texts.WF_TRIGGERS_INVALID_CONFIG)
                return

        self.accept()

    def get_data(self) -> dict:
        cond_text = self._conditions_edit.toPlainText().strip()
        conditions = json.loads(cond_text) if cond_text else []
        config_text = self._config_edit.toPlainText().strip()
        action_config = json.loads(config_text) if config_text else {}

        return {
            'name': self._name_input.text().strip(),
            'event': self._event_combo.currentData(),
            'action_type': self._action_combo.currentData(),
            'condition_logic': self._logic_combo.currentData(),
            'conditions': conditions,
            'action_config': action_config,
        }


class TriggersView(QWidget):
    """Trigger-Verwaltung mit Tabelle und Ausfuehrungslog."""

    def __init__(self, wf_api: WorkforceApiClient):
        super().__init__()
        self._wf_api = wf_api
        self._toast_manager = None
        self._triggers: list[dict] = []
        self._load_thread = None
        self._runs_thread = None
        self._action_thread = None

        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._triggers_tab = QWidget()
        self._tabs.addTab(self._triggers_tab, texts.WF_TRIGGERS_TAB_LIST)
        self._setup_triggers_tab()

        self._runs_tab = QWidget()
        self._tabs.addTab(self._runs_tab, texts.WF_TRIGGERS_TAB_RUNS)
        self._setup_runs_tab()

        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _setup_triggers_tab(self):
        layout = QVBoxLayout(self._triggers_tab)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(texts.WF_TRIGGERS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_BODY}; font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900}; font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()

        create_btn = QPushButton(texts.WF_TRIGGERS_CREATE)
        create_btn.setStyleSheet(get_button_primary_style())
        create_btn.setCursor(Qt.PointingHandCursor)
        create_btn.clicked.connect(self._open_create_dialog)
        header.addWidget(create_btn)
        layout.addLayout(header)

        self._triggers_table = QTableWidget(0, 6)
        self._triggers_table.setHorizontalHeaderLabels([
            texts.WF_TRIGGERS_COL_NAME,
            texts.WF_TRIGGERS_COL_EVENT,
            texts.WF_TRIGGERS_COL_ACTION,
            texts.WF_TRIGGERS_COL_ENABLED,
            texts.WF_TRIGGERS_COL_LAST_RUN,
            texts.WF_TRIGGERS_COL_ACTIONS,
        ])
        self._triggers_table.horizontalHeader().setStretchLastSection(True)
        self._triggers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._triggers_table.verticalHeader().setVisible(False)
        self._triggers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._triggers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._triggers_table.setAlternatingRowColors(True)
        layout.addWidget(self._triggers_table, 1)

    def _setup_runs_tab(self):
        layout = QVBoxLayout(self._runs_tab)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        filters = QHBoxLayout()
        filters.setSpacing(8)

        filters.addWidget(QLabel(texts.WF_TRIGGERS_FILTER_TRIGGER))
        self._filter_trigger = QComboBox()
        self._filter_trigger.setMinimumWidth(180)
        self._filter_trigger.addItem(texts.WF_TRIGGERS_FILTER_ALL, None)
        filters.addWidget(self._filter_trigger)

        filters.addWidget(QLabel(texts.WF_TRIGGERS_FILTER_STATUS))
        self._filter_status = QComboBox()
        self._filter_status.addItem(texts.WF_TRIGGERS_FILTER_ALL, None)
        self._filter_status.addItem(texts.WF_TRIGGERS_STATUS_SUCCESS, "success")
        self._filter_status.addItem(texts.WF_TRIGGERS_STATUS_ERROR, "error")
        self._filter_status.addItem(texts.WF_TRIGGERS_STATUS_SKIPPED, "skipped")
        filters.addWidget(self._filter_status)

        filters.addStretch()
        filter_btn = QPushButton(texts.WF_TRIGGERS_FILTER_APPLY)
        filter_btn.setStyleSheet(get_button_secondary_style())
        filter_btn.setCursor(Qt.PointingHandCursor)
        filter_btn.clicked.connect(self._load_runs)
        filters.addWidget(filter_btn)
        layout.addLayout(filters)

        self._runs_table = QTableWidget(0, 7)
        self._runs_table.setHorizontalHeaderLabels([
            texts.WF_TRIGGERS_RUN_TRIGGER,
            texts.WF_TRIGGERS_RUN_EVENT,
            texts.WF_TRIGGERS_RUN_EMPLOYEE,
            texts.WF_TRIGGERS_RUN_ACTION,
            texts.WF_TRIGGERS_RUN_STATUS,
            texts.WF_TRIGGERS_RUN_TIME,
            texts.WF_TRIGGERS_RUN_BY,
        ])
        self._runs_table.horizontalHeader().setStretchLastSection(True)
        self._runs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._runs_table.verticalHeader().setVisible(False)
        self._runs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._runs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._runs_table.setAlternatingRowColors(True)
        layout.addWidget(self._runs_table, 1)

        pag = QHBoxLayout()
        pag.addStretch()
        self._runs_page_label = QLabel(texts.WF_TRIGGERS_PAGE.format(page=1))
        self._runs_page_label.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};"
        )
        pag.addWidget(self._runs_page_label)
        self._prev_btn = QPushButton(texts.WF_TRIGGERS_PREV)
        self._prev_btn.setStyleSheet(get_button_secondary_style())
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._prev_page)
        pag.addWidget(self._prev_btn)
        self._next_btn = QPushButton(texts.WF_TRIGGERS_NEXT)
        self._next_btn.setStyleSheet(get_button_secondary_style())
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._next_page)
        pag.addWidget(self._next_btn)
        layout.addLayout(pag)

        self._runs_current_page = 1
        self._runs_total_pages = 1

    def _on_tab_changed(self, index: int):
        if index == 1:
            self._load_runs()

    def _load_triggers(self):
        if self._load_thread and self._load_thread.isRunning():
            return
        thread = _TriggerLoadThread(self._wf_api)
        thread.finished.connect(self._on_triggers_loaded)
        thread.error.connect(self._on_load_error)
        self._load_thread = thread
        thread.start()

    def _on_triggers_loaded(self, triggers: list):
        self._triggers = triggers
        self._render_triggers_table()
        self._update_filter_combos()

    def _on_load_error(self, error: str):
        logger.error(f"Trigger-Ladefehler: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(f"{texts.WF_TRIGGERS_LOAD_ERROR}: {error}")

    def _render_triggers_table(self):
        self._triggers_table.setRowCount(len(self._triggers))
        for row, trig in enumerate(self._triggers):
            self._triggers_table.setItem(row, 0, QTableWidgetItem(trig.get('name', '')))
            self._triggers_table.setItem(row, 1, QTableWidgetItem(trig.get('event', '')))
            self._triggers_table.setItem(row, 2, QTableWidgetItem(trig.get('action_type', '')))

            enabled = trig.get('enabled', False)
            status_item = QTableWidgetItem(
                texts.WF_TRIGGERS_ENABLED if enabled else texts.WF_TRIGGERS_DISABLED
            )
            status_item.setForeground(
                Qt.GlobalColor.darkGreen if enabled else Qt.GlobalColor.darkRed
            )
            self._triggers_table.setItem(row, 3, status_item)

            self._triggers_table.setItem(
                row, 4, QTableWidgetItem(trig.get('last_execution', '-'))
            )

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            toggle_btn = QPushButton(
                texts.WF_TRIGGERS_DISABLE if enabled else texts.WF_TRIGGERS_ENABLE
            )
            toggle_btn.setStyleSheet(get_button_secondary_style())
            toggle_btn.setFixedHeight(28)
            toggle_btn.setCursor(Qt.PointingHandCursor)
            tid = trig.get('id')
            toggle_btn.clicked.connect(lambda _, t=tid: self._toggle_trigger(t))
            actions_layout.addWidget(toggle_btn)

            edit_btn = QPushButton(texts.EDIT)
            edit_btn.setStyleSheet(get_button_secondary_style())
            edit_btn.setFixedHeight(28)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.clicked.connect(lambda _, t=trig: self._open_edit_dialog(t))
            actions_layout.addWidget(edit_btn)

            del_btn = QPushButton(texts.DELETE)
            del_btn.setStyleSheet(get_button_danger_style())
            del_btn.setFixedHeight(28)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.clicked.connect(lambda _, t=tid: self._delete_trigger(t))
            actions_layout.addWidget(del_btn)

            self._triggers_table.setCellWidget(row, 5, actions_widget)
            self._triggers_table.setRowHeight(row, 44)

    def _update_filter_combos(self):
        self._filter_trigger.clear()
        self._filter_trigger.addItem(texts.WF_TRIGGERS_FILTER_ALL, None)
        for trig in self._triggers:
            self._filter_trigger.addItem(trig.get('name', '?'), trig.get('id'))

    def _open_create_dialog(self):
        dlg = _TriggerDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            thread = _TriggerSaveThread(self._wf_api, data)
            thread.finished.connect(self._on_trigger_saved)
            thread.error.connect(self._on_save_error)
            self._action_thread = thread
            thread.start()

    def _open_edit_dialog(self, trigger: dict):
        dlg = _TriggerDialog(self, trigger)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            thread = _TriggerSaveThread(self._wf_api, data, trigger.get('id'))
            thread.finished.connect(self._on_trigger_saved)
            thread.error.connect(self._on_save_error)
            self._action_thread = thread
            thread.start()

    def _on_trigger_saved(self, _result: dict):
        if self._toast_manager:
            self._toast_manager.show_success(texts.WF_TRIGGERS_SAVED)
        self._load_triggers()

    def _on_save_error(self, error: str):
        logger.error(f"Trigger-Speicherfehler: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(f"{texts.WF_TRIGGERS_SAVE_ERROR}: {error}")

    def _toggle_trigger(self, trigger_id: int):
        thread = _TriggerToggleThread(self._wf_api, trigger_id)
        thread.finished.connect(lambda _: self._load_triggers())
        thread.error.connect(self._on_load_error)
        self._action_thread = thread
        thread.start()

    def _delete_trigger(self, trigger_id: int):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, texts.WF_TRIGGERS_DELETE_TITLE, texts.WF_TRIGGERS_DELETE_CONFIRM,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        thread = _TriggerDeleteThread(self._wf_api, trigger_id)
        thread.finished.connect(self._on_trigger_deleted)
        thread.error.connect(self._on_load_error)
        self._action_thread = thread
        thread.start()

    def _on_trigger_deleted(self, success: bool):
        if success and self._toast_manager:
            self._toast_manager.show_success(texts.WF_TRIGGERS_DELETED)
        self._load_triggers()

    def _load_runs(self):
        if self._runs_thread and self._runs_thread.isRunning():
            return
        trigger_id = self._filter_trigger.currentData()
        status = self._filter_status.currentData()
        thread = _RunsLoadThread(
            self._wf_api, page=self._runs_current_page,
            trigger_id=trigger_id, status=status,
        )
        thread.finished.connect(self._on_runs_loaded)
        thread.error.connect(self._on_load_error)
        self._runs_thread = thread
        thread.start()

    def _on_runs_loaded(self, result: dict):
        runs = result.get('runs', [])
        pagination = result.get('pagination', {})
        self._runs_current_page = pagination.get('current_page', 1)
        self._runs_total_pages = pagination.get('total_pages', 1)

        self._runs_page_label.setText(
            texts.WF_TRIGGERS_PAGE.format(page=self._runs_current_page)
        )
        self._prev_btn.setEnabled(self._runs_current_page > 1)
        self._next_btn.setEnabled(self._runs_current_page < self._runs_total_pages)

        self._runs_table.setRowCount(len(runs))
        for row, run in enumerate(runs):
            self._runs_table.setItem(row, 0, QTableWidgetItem(run.get('trigger_name', '-')))
            self._runs_table.setItem(row, 1, QTableWidgetItem(run.get('event', '')))
            self._runs_table.setItem(row, 2, QTableWidgetItem(run.get('employee_name', '-')))
            self._runs_table.setItem(row, 3, QTableWidgetItem(run.get('action_type', '')))

            status_text = run.get('status', '')
            status_item = QTableWidgetItem(status_text)
            if status_text == 'success':
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status_text == 'error':
                status_item.setForeground(Qt.GlobalColor.red)
            self._runs_table.setItem(row, 4, status_item)

            self._runs_table.setItem(row, 5, QTableWidgetItem(format_date_de(run.get('created_at', '') or '')))
            self._runs_table.setItem(row, 6, QTableWidgetItem(run.get('executed_by', '')))

    def _prev_page(self):
        if self._runs_current_page > 1:
            self._runs_current_page -= 1
            self._load_runs()

    def _next_page(self):
        if self._runs_current_page < self._runs_total_pages:
            self._runs_current_page += 1
            self._load_runs()

    def refresh(self):
        self._load_triggers()
        if self._tabs.currentIndex() == 1:
            self._runs_current_page = 1
            self._load_runs()
