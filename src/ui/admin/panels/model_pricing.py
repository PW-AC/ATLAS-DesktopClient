"""
ACENCIA ATLAS - Admin Panel: Modell-Preise

Extrahiert aus admin_view.py (Zeilen 4128-4382).
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QDateEdit,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor

from api.client import APIClient
from i18n import de as texts
from ui.styles.tokens import (
    TEXT_SECONDARY,
    FONT_HEADLINE,
    FONT_SIZE_CAPTION,
    get_button_primary_style, get_button_ghost_style,
)
from ui.admin.workers import AdminWriteWorker

logger = logging.getLogger(__name__)

SPACING_MD = 16
SPACING_LG = 24

STATUS_COLORS = {
    'success': '#27ae60',
    'error': '#e74c3c',
    'denied': '#f39c12',
}


class ModelPricingPanel(QWidget):
    """Admin-Panel fuer Modell-Preise (Kostenberechnung pro Modell)."""

    def __init__(self, api_client: APIClient, toast_manager, model_pricing_api, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._model_pricing_api = model_pricing_api
        self._active_workers: list = []
        self._pricing_data = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode zum Laden der Daten."""
        self._load_model_pricing()

    def _create_ui(self):
        """Erstellt das Modell-Preise-Panel."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_MD)

        # Header
        header = QHBoxLayout()
        title = QLabel(texts.MODEL_PRICING_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton(texts.MODEL_PRICING_ADD)
        add_btn.setStyleSheet(get_button_primary_style())
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._show_add_pricing_dialog)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Hint
        hint_label = QLabel(texts.MODEL_PRICING_HINT)
        hint_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}; padding: 4px 0;")
        hint_label.setOpenExternalLinks(True)
        layout.addWidget(hint_label)

        # Tabelle
        self._pricing_table = QTableWidget()
        self._pricing_table.setColumnCount(7)
        self._pricing_table.setHorizontalHeaderLabels([
            texts.MODEL_PRICING_PROVIDER, texts.MODEL_PRICING_MODEL,
            texts.MODEL_PRICING_INPUT, texts.MODEL_PRICING_OUTPUT,
            texts.MODEL_PRICING_VALID_FROM, texts.MODEL_PRICING_IS_ACTIVE,
            texts.MODEL_PRICING_ACTIONS
        ])
        self._pricing_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._pricing_table.setColumnWidth(6, 220)
        self._pricing_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._pricing_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._pricing_table.verticalHeader().setVisible(False)
        self._pricing_table.setAlternatingRowColors(True)
        layout.addWidget(self._pricing_table)

    def _load_model_pricing(self):
        """Laedt alle Modell-Preise vom Server."""
        def _do_load():
            return self._model_pricing_api.list_prices_admin()

        worker = AdminWriteWorker(_do_load)
        worker.finished.connect(self._on_pricing_loaded)
        worker.error.connect(lambda e: self._show_toast_error(f"Modell-Preise laden: {e}"))
        self._active_workers.append(worker)
        worker.start()

    def _on_pricing_loaded(self, prices):
        """Aktualisiert die Preise-Tabelle."""
        self._pricing_data = prices if prices else []
        table = self._pricing_table
        table.setRowCount(len(self._pricing_data))

        for row, p in enumerate(self._pricing_data):
            type_label = texts.AI_PROVIDER_OPENROUTER if p.provider == 'openrouter' else texts.AI_PROVIDER_OPENAI
            table.setItem(row, 0, QTableWidgetItem(type_label))
            table.setItem(row, 1, QTableWidgetItem(p.model_name))
            table.setItem(row, 2, QTableWidgetItem(f"${p.input_price_per_million:.4f}"))
            table.setItem(row, 3, QTableWidgetItem(f"${p.output_price_per_million:.4f}"))
            table.setItem(row, 4, QTableWidgetItem(p.valid_from))

            active_text = texts.AI_PROVIDER_ACTIVE if p.is_active else texts.AI_PROVIDER_INACTIVE
            active_item = QTableWidgetItem(active_text)
            if p.is_active:
                active_item.setForeground(QColor(STATUS_COLORS['success']))
            else:
                active_item.setForeground(QColor(STATUS_COLORS['error']))
            table.setItem(row, 5, active_item)

            # Aktions-Buttons
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            edit_btn = QPushButton(texts.MODEL_PRICING_EDIT)
            edit_btn.setStyleSheet(get_button_ghost_style())
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setFixedHeight(28)
            edit_btn.clicked.connect(lambda _, pid=p.id: self._show_edit_pricing_dialog(pid))
            actions_layout.addWidget(edit_btn)

            if p.is_active:
                deact_btn = QPushButton(texts.MODEL_PRICING_DEACTIVATE)
                deact_btn.setStyleSheet(get_button_ghost_style())
                deact_btn.setCursor(Qt.PointingHandCursor)
                deact_btn.setFixedHeight(28)
                deact_btn.clicked.connect(lambda _, pid=p.id, pmodel=p.model_name: self._deactivate_pricing(pid, pmodel))
                actions_layout.addWidget(deact_btn)

            table.setCellWidget(row, 6, actions)

        table.resizeRowsToContents()

    def _show_add_pricing_dialog(self):
        """Dialog zum Anlegen eines neuen Modell-Preises."""
        dialog = QDialog(self)
        dialog.setWindowTitle(texts.MODEL_PRICING_DIALOG_TITLE_NEW)
        dialog.setMinimumWidth(450)
        form = QFormLayout(dialog)

        provider_combo = QComboBox()
        provider_combo.addItem(texts.AI_PROVIDER_OPENROUTER, "openrouter")
        provider_combo.addItem(texts.AI_PROVIDER_OPENAI, "openai")
        form.addRow(texts.MODEL_PRICING_PROVIDER + ":", provider_combo)

        model_edit = QLineEdit()
        model_edit.setPlaceholderText("z.B. gpt-4o oder openai/gpt-4o")
        form.addRow(texts.MODEL_PRICING_MODEL + ":", model_edit)

        input_spin = QLineEdit()
        input_spin.setPlaceholderText("z.B. 2.50")
        form.addRow(texts.MODEL_PRICING_INPUT + ":", input_spin)

        output_spin = QLineEdit()
        output_spin.setPlaceholderText("z.B. 10.00")
        form.addRow(texts.MODEL_PRICING_OUTPUT + ":", output_spin)

        date_edit = QDateEdit()
        date_edit.setDate(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        form.addRow(texts.MODEL_PRICING_VALID_FROM + ":", date_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            from ui.toast import ToastManager
            provider = provider_combo.currentData()
            model_name = model_edit.text().strip()
            try:
                input_price = float(input_spin.text().replace(',', '.'))
                output_price = float(output_spin.text().replace(',', '.'))
            except ValueError:
                ToastManager.instance().show_error("Ungueltige Preiseingabe")
                return
            valid_from = date_edit.date().toString("yyyy-MM-dd")

            if not model_name:
                return

            def _do_create():
                return self._model_pricing_api.create_price(
                    provider, model_name, input_price, output_price, valid_from
                )

            worker = AdminWriteWorker(_do_create)
            worker.finished.connect(lambda _: (
                ToastManager.instance().show_success(texts.MODEL_PRICING_CREATED.format(model=model_name)),
                self._load_model_pricing()
            ))
            worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
            self._active_workers.append(worker)
            worker.start()

    def _show_edit_pricing_dialog(self, price_id: int):
        """Dialog zum Bearbeiten eines Modell-Preises."""
        price = None
        for p in self._pricing_data:
            if p.id == price_id:
                price = p
                break
        if not price:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(texts.MODEL_PRICING_DIALOG_TITLE_EDIT)
        dialog.setMinimumWidth(450)
        form = QFormLayout(dialog)

        model_edit = QLineEdit(price.model_name)
        form.addRow(texts.MODEL_PRICING_MODEL + ":", model_edit)

        input_edit = QLineEdit(str(price.input_price_per_million))
        form.addRow(texts.MODEL_PRICING_INPUT + ":", input_edit)

        output_edit = QLineEdit(str(price.output_price_per_million))
        form.addRow(texts.MODEL_PRICING_OUTPUT + ":", output_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            from ui.toast import ToastManager
            data = {}
            new_model = model_edit.text().strip()
            if new_model and new_model != price.model_name:
                data['model_name'] = new_model
            try:
                new_input = float(input_edit.text().replace(',', '.'))
                if new_input != price.input_price_per_million:
                    data['input_price_per_million'] = new_input
                new_output = float(output_edit.text().replace(',', '.'))
                if new_output != price.output_price_per_million:
                    data['output_price_per_million'] = new_output
            except ValueError:
                ToastManager.instance().show_error("Ungueltige Preiseingabe")
                return

            if not data:
                return

            def _do_update():
                return self._model_pricing_api.update_price(price_id, **data)

            worker = AdminWriteWorker(_do_update)
            worker.finished.connect(lambda _: (
                ToastManager.instance().show_success(texts.MODEL_PRICING_UPDATED),
                self._load_model_pricing()
            ))
            worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
            self._active_workers.append(worker)
            worker.start()

    def _deactivate_pricing(self, price_id: int, model_name: str):
        """Modell-Preis deaktivieren nach Bestaetigung."""
        from ui.toast import ToastManager
        reply = QMessageBox.question(
            self, texts.MODEL_PRICING_DEACTIVATE,
            texts.MODEL_PRICING_CONFIRM_DELETE.format(model=model_name),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        def _do_deactivate():
            return self._model_pricing_api.delete_price(price_id)

        worker = AdminWriteWorker(_do_deactivate)
        worker.finished.connect(lambda _: (
            ToastManager.instance().show_success(texts.MODEL_PRICING_DEACTIVATED),
            self._load_model_pricing()
        ))
        worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
        self._active_workers.append(worker)
        worker.start()

    def _show_toast_error(self, msg: str):
        """Zeigt eine Fehler-Toast-Benachrichtigung."""
        from ui.toast import ToastManager
        ToastManager.instance().show_error(msg)
