"""
Dialog: Freie Provision / Sonderzahlung anlegen oder bearbeiten.

Formular mit dynamischer Verteilungstabelle (Berater + Prozent).
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QDoubleSpinBox, QDateEdit, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QWidget, QMessageBox,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from typing import List, Optional

from domain.provision.entities import FreeCommission, Employee
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, ERROR, ERROR_LIGHT, SUCCESS,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)
from ui.provision.widgets import format_eur, get_secondary_button_style
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class FreeCommissionDialog(QDialog):
    """Dialog zum Anlegen/Bearbeiten einer Sonderzahlung."""

    def __init__(self, employees: list, fc: FreeCommission = None, parent=None):
        super().__init__(parent)
        self._employees = self._prepare_employees(employees)
        self._fc = fc
        self._is_edit = fc is not None and fc.id > 0

        title = texts.PM_FREE_DIALOG_TITLE_EDIT if self._is_edit else texts.PM_FREE_DIALOG_TITLE
        self.setWindowTitle(title)
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        self._setup_ui()
        if self._is_edit:
            self._populate_from_fc(fc)

    @staticmethod
    def _prepare_employees(employees) -> list:
        result = []
        for e in employees:
            if isinstance(e, dict):
                result.append(e)
            elif hasattr(e, 'id'):
                result.append({
                    'id': e.id,
                    'name': e.name,
                    'role': getattr(e, 'role', ''),
                    'is_active': getattr(e, 'is_active', True),
                })
            else:
                result.append(e)
        return [e for e in result if e.get('is_active', True)]

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_PRIMARY};
                font-family: {FONT_BODY};
            }}
            QLabel {{
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_900};
            }}
        """)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._datum_edit = QDateEdit()
        self._datum_edit.setCalendarPopup(True)
        self._datum_edit.setDate(QDate.currentDate())
        self._datum_edit.setDisplayFormat("dd.MM.yyyy")
        self._datum_edit.setStyleSheet(self._input_style())
        form.addRow(texts.PM_FREE_FIELD_DATUM, self._datum_edit)

        self._betrag_spin = QDoubleSpinBox()
        self._betrag_spin.setRange(0.01, 999999.99)
        self._betrag_spin.setDecimals(2)
        self._betrag_spin.setSuffix(" \u20ac")
        self._betrag_spin.setStyleSheet(self._input_style())
        self._betrag_spin.valueChanged.connect(self._on_betrag_changed)
        form.addRow(texts.PM_FREE_FIELD_BETRAG, self._betrag_spin)

        self._beschreibung_edit = QLineEdit()
        self._beschreibung_edit.setPlaceholderText(texts.PM_FREE_FIELD_BESCHREIBUNG)
        self._beschreibung_edit.setStyleSheet(self._input_style())
        form.addRow(texts.PM_FREE_FIELD_BESCHREIBUNG, self._beschreibung_edit)

        self._kostenstelle_edit = QLineEdit()
        self._kostenstelle_edit.setPlaceholderText(texts.PM_FREE_FIELD_KOSTENSTELLE)
        self._kostenstelle_edit.setStyleSheet(self._input_style())
        form.addRow(texts.PM_FREE_FIELD_KOSTENSTELLE, self._kostenstelle_edit)

        layout.addLayout(form)

        split_header = QHBoxLayout()
        split_title = QLabel(texts.PM_FREE_SPLIT_TITLE)
        split_title.setStyleSheet(
            f"font-size: 11pt; font-weight: 600; color: {PRIMARY_900}; font-family: {FONT_BODY};"
        )
        split_header.addWidget(split_title)
        split_header.addStretch()

        self._add_row_btn = QPushButton(f"  +  {texts.PM_FREE_SPLIT_ADD_ROW}")
        self._add_row_btn.setCursor(Qt.PointingHandCursor)
        self._add_row_btn.setStyleSheet(get_secondary_button_style())
        self._add_row_btn.clicked.connect(self._add_split_row)
        split_header.addWidget(self._add_row_btn)
        layout.addLayout(split_header)

        self._split_table = QTableWidget()
        self._split_table.setColumnCount(4)
        self._split_table.setHorizontalHeaderLabels([
            texts.PM_FREE_SPLIT_BERATER,
            texts.PM_FREE_SPLIT_PROZENT,
            texts.PM_FREE_SPLIT_EURO,
            '',
        ])
        self._split_table.verticalHeader().setVisible(False)
        self._split_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._split_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid {PRIMARY_500};
                border-radius: 4px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QHeaderView::section {{
                background-color: {BG_SECONDARY};
                color: {PRIMARY_900};
                padding: 6px 8px;
                border: none;
                border-bottom: 1px solid {PRIMARY_500};
                font-weight: 600;
                font-size: {FONT_SIZE_CAPTION};
            }}
        """)

        hh = self._split_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.resizeSection(1, 100)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.resizeSection(2, 120)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.resizeSection(3, 40)

        self._split_table.setMinimumHeight(140)
        layout.addWidget(self._split_table)

        sum_row = QHBoxLayout()
        sum_row.addStretch()
        self._sum_label = QLabel(f"{texts.PM_FREE_SPLIT_SUM_LABEL}: 0,00%")
        self._sum_label.setStyleSheet(
            f"font-size: {FONT_SIZE_BODY}; font-weight: 600; color: {PRIMARY_900}; font-family: {FONT_BODY};"
        )
        sum_row.addWidget(self._sum_label)
        layout.addLayout(sum_row)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {ERROR}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton(texts.PM_FREE_CANCEL)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(get_secondary_button_style())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._save_btn = QPushButton(texts.PM_FREE_SAVE)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {PRIMARY_500}; }}
            QPushButton:pressed {{ background-color: {PRIMARY_900}; }}
        """)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        layout.addLayout(btn_row)

        if not self._is_edit:
            self._add_split_row()

    def _input_style(self) -> str:
        return f"""
            QLineEdit, QDoubleSpinBox, QDateEdit {{
                background-color: white;
                color: {PRIMARY_900};
                border: 1.5px solid {PRIMARY_500};
                border-radius: 6px;
                padding: 6px 12px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                min-height: 28px;
            }}
            QLineEdit:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
                border-color: {ACCENT_500};
                border-width: 2px;
            }}
        """

    def _add_split_row(self):
        row = self._split_table.rowCount()
        self._split_table.insertRow(row)

        combo = QComboBox()
        combo.addItem("---", 0)
        for emp in self._employees:
            role_suffix = f" ({emp.get('role', '')})" if emp.get('role') else ''
            combo.addItem(f"{emp['name']}{role_suffix}", emp['id'])
        combo.setStyleSheet(f"""
            QComboBox {{
                border: none; background: transparent;
                padding: 2px 4px; font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
            }}
        """)
        self._split_table.setCellWidget(row, 0, combo)

        pct_spin = QDoubleSpinBox()
        pct_spin.setRange(0.01, 100.0)
        pct_spin.setDecimals(2)
        pct_spin.setSuffix(" %")
        pct_spin.setValue(0)
        pct_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: none; background: transparent;
                padding: 2px 4px; font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
            }}
        """)
        pct_spin.valueChanged.connect(self._update_sums)
        self._split_table.setCellWidget(row, 1, pct_spin)

        euro_item = QTableWidgetItem(format_eur(0))
        euro_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        euro_item.setFlags(euro_item.flags() & ~Qt.ItemIsEditable)
        self._split_table.setItem(row, 2, euro_item)

        remove_btn = QPushButton("\u2716")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setFixedSize(28, 28)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {ERROR}; border: none;
                font-size: 12pt;
            }}
            QPushButton:hover {{ background: {ERROR_LIGHT}; border-radius: 4px; }}
        """)
        remove_btn.clicked.connect(lambda _, r=row: self._remove_split_row(r))

        remove_container = QWidget()
        remove_layout = QHBoxLayout(remove_container)
        remove_layout.setContentsMargins(0, 0, 0, 0)
        remove_layout.setAlignment(Qt.AlignCenter)
        remove_layout.addWidget(remove_btn)
        self._split_table.setCellWidget(row, 3, remove_container)

        self._update_sums()

    def _remove_split_row(self, row: int):
        if self._split_table.rowCount() <= 1:
            return
        self._split_table.removeRow(row)
        self._reconnect_remove_buttons()
        self._update_sums()

    def _reconnect_remove_buttons(self):
        for r in range(self._split_table.rowCount()):
            container = self._split_table.cellWidget(r, 3)
            if container:
                btn_layout = container.layout()
                if btn_layout and btn_layout.count() > 0:
                    btn = btn_layout.itemAt(0).widget()
                    if btn:
                        try:
                            btn.clicked.disconnect()
                        except RuntimeError:
                            pass
                        btn.clicked.connect(lambda _, row=r: self._remove_split_row(row))

    def _on_betrag_changed(self, val):
        self._update_sums()

    def _update_sums(self):
        total_pct = 0.0
        gesamt = self._betrag_spin.value()

        for r in range(self._split_table.rowCount()):
            pct_spin = self._split_table.cellWidget(r, 1)
            if pct_spin:
                pct = pct_spin.value()
                total_pct += pct
                euro = round(gesamt * pct / 100, 2)
                item = self._split_table.item(r, 2)
                if item:
                    item.setText(format_eur(euro))

        formatted_pct = f"{total_pct:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self._sum_label.setText(f"{texts.PM_FREE_SPLIT_SUM_LABEL}: {formatted_pct}%")

        is_valid = abs(total_pct - 100) < 0.05
        color = SUCCESS if is_valid else ERROR
        self._sum_label.setStyleSheet(
            f"font-size: {FONT_SIZE_BODY}; font-weight: 600; color: {color}; font-family: {FONT_BODY};"
        )

    def _populate_from_fc(self, fc: FreeCommission):
        if fc.datum:
            parts = fc.datum[:10].split('-')
            if len(parts) == 3:
                self._datum_edit.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))

        self._betrag_spin.setValue(fc.gesamtbetrag)
        self._beschreibung_edit.setText(fc.beschreibung)
        self._kostenstelle_edit.setText(fc.kostenstelle or '')

        if fc.splits:
            for sp in fc.splits:
                self._add_split_row()
                row = self._split_table.rowCount() - 1
                combo = self._split_table.cellWidget(row, 0)
                if combo:
                    for i in range(combo.count()):
                        if combo.itemData(i) == sp.berater_id:
                            combo.setCurrentIndex(i)
                            break
                pct_spin = self._split_table.cellWidget(row, 1)
                if pct_spin:
                    pct_spin.setValue(sp.anteil_prozent)
        else:
            self._add_split_row()

        self._update_sums()

    def _validate(self) -> bool:
        self._error_label.setVisible(False)

        if not self._beschreibung_edit.text().strip():
            self._show_validation_error(texts.PM_FREE_VALIDATION_BESCHREIBUNG)
            return False

        if self._betrag_spin.value() <= 0:
            self._show_validation_error(texts.PM_FREE_VALIDATION_BETRAG)
            return False

        if self._split_table.rowCount() == 0:
            self._show_validation_error(texts.PM_FREE_VALIDATION_SPLITS)
            return False

        total_pct = 0.0
        for r in range(self._split_table.rowCount()):
            combo = self._split_table.cellWidget(r, 0)
            if combo and combo.currentData() == 0:
                self._show_validation_error(texts.PM_FREE_VALIDATION_BERATER_MISSING)
                return False
            pct_spin = self._split_table.cellWidget(r, 1)
            if pct_spin:
                total_pct += pct_spin.value()

        if abs(total_pct - 100) > 0.05:
            self._show_validation_error(
                texts.PM_FREE_SPLIT_SUM_ERROR.format(pct=f"{total_pct:.2f}")
            )
            return False

        return True

    def _show_validation_error(self, msg: str):
        self._error_label.setText(msg)
        self._error_label.setVisible(True)

    def _on_save(self):
        if not self._validate():
            return
        self.accept()

    def get_data(self) -> dict:
        date = self._datum_edit.date()
        datum = f"{date.year()}-{date.month():02d}-{date.day():02d}"

        splits = []
        for r in range(self._split_table.rowCount()):
            combo = self._split_table.cellWidget(r, 0)
            pct_spin = self._split_table.cellWidget(r, 1)
            if combo and pct_spin:
                berater_id = combo.currentData()
                if berater_id and berater_id > 0:
                    splits.append({
                        'berater_id': berater_id,
                        'anteil_prozent': round(pct_spin.value(), 2),
                    })

        return {
            'datum': datum,
            'gesamtbetrag': round(self._betrag_spin.value(), 2),
            'beschreibung': self._beschreibung_edit.text().strip(),
            'kostenstelle': self._kostenstelle_edit.text().strip() or None,
            'splits': splits,
        }
