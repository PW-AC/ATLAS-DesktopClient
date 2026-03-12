"""
ContactCompanyView - Firmenverwaltung im Contact-Modul.

Zeigt Firmen als Karten in einer scrollbaren Liste.
Klick auf eine Firma zeigt deren Mitarbeiter.
Neue Firma per Dialog (mit Berechtigung contact.companies).
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QDialog, QFormLayout, QLineEdit,
    QMenu, QMessageBox, QStackedWidget,
)
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QAction, QCursor

from contact.api_client import ContactApiClient
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, FONT_BODY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_H2,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT, RADIUS_MD,
    get_button_primary_style, get_button_secondary_style,
)
from i18n import de as texts

logger = logging.getLogger(__name__)


class _CompanyLoadWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, api: ContactApiClient):
        super().__init__()
        self._api = api

    def run(self):
        try:
            self.finished.emit(self._api.list_companies())
        except Exception as e:
            logger.error("Firmen laden fehlgeschlagen: %s", e)
            self.error.emit(str(e))


class _CompanyDetailWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: ContactApiClient, company_id: int):
        super().__init__()
        self._api = api
        self._cid = company_id

    def run(self):
        try:
            self.finished.emit(self._api.get_company(self._cid))
        except Exception as e:
            logger.error("Firmendetail laden fehlgeschlagen: %s", e)
            self.error.emit(str(e))


class _CompanyCreateWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: ContactApiClient, data: dict):
        super().__init__()
        self._api = api
        self._data = data

    def run(self):
        try:
            self.finished.emit(self._api.create_company(self._data))
        except Exception as e:
            logger.error("Firma erstellen fehlgeschlagen: %s", e)
            self.error.emit(str(e))


class _CompanyCard(QFrame):
    clicked = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, company: dict, has_delete: bool = False, parent=None):
        super().__init__(parent)
        self._company = company
        self._company_id = company.get("id", 0)
        self._has_delete = has_delete
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(280)
        self.setMinimumHeight(100)
        self.setObjectName("company_card")
        self.setStyleSheet(f"""
            QFrame#company_card {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
            }}
            QFrame#company_card:hover {{
                border-color: {ACCENT_500};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        name = self._company.get("name", "") or "-"
        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            font-family: {FONT_BODY}; font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900}; font-weight: 600;
        """)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        phone = self._company.get("phone_central", "") or ""
        if phone:
            phone_label = QLabel(f"{texts.CONTACT_COMPANY_PHONE_CENTRAL}: {phone}")
            phone_label.setStyleSheet(f"""
                font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            """)
            layout.addWidget(phone_label)

        email = self._company.get("email_domain", "") or ""
        if email:
            email_label = QLabel(f"{texts.CONTACT_COMPANY_EMAIL_DOMAIN}: {email}")
            email_label.setStyleSheet(f"""
                font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            """)
            layout.addWidget(email_label)

        count = self._company.get("contact_count", 0)
        count_label = QLabel(f"{count} {texts.CONTACT_COMPANY_CONTACT_COUNT}")
        count_label.setStyleSheet(f"""
            font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
        """)
        layout.addWidget(count_label)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._company_id:
            self.clicked.emit(self._company_id)
        super().mouseReleaseEvent(event)

    def _show_context_menu(self, pos):
        if not self._has_delete or not self._company_id:
            return
        menu = QMenu(self)
        delete_action = QAction(texts.CONTACT_COMPANY_DELETE, self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self._company_id))
        menu.addAction(delete_action)
        menu.exec(self.mapToGlobal(pos))


class _EmployeeRow(QFrame):
    clicked = Signal(int)

    def __init__(self, contact: dict, parent=None):
        super().__init__(parent)
        self._contact_id = contact.get("contact_id", 0)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setObjectName("employee_row")
        self.setStyleSheet(f"""
            QFrame#employee_row {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 6px;
                padding: 8px 12px;
            }}
            QFrame#employee_row:hover {{
                border-color: {ACCENT_500};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        display = contact.get("display_name") or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "-"
        name_lbl = QLabel(display)
        name_lbl.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900}; font-weight: 600;")
        layout.addWidget(name_lbl)

        role = contact.get("role", "")
        if role:
            role_lbl = QLabel(role)
            role_lbl.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; color: {PRIMARY_500};")
            layout.addWidget(role_lbl)

        layout.addStretch()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._contact_id:
            self.clicked.emit(self._contact_id)
        super().mouseReleaseEvent(event)


class _CreateCompanyDialog(QDialog):

    def __init__(self, parent=None, prefill_name: str = ''):
        super().__init__(parent)
        self._prefill_name = prefill_name
        self.setWindowTitle(texts.CONTACT_COMPANY_NEW)
        self.setMinimumWidth(360)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._name_input = QLineEdit(self._prefill_name)
        self._name_input.setPlaceholderText(texts.CONTACT_COMPANY_NAME)
        form.addRow(texts.CONTACT_COMPANY_NAME, self._name_input)

        self._phone_input = QLineEdit()
        self._phone_input.setPlaceholderText(texts.CONTACT_COMPANY_PHONE_CENTRAL)
        form.addRow(texts.CONTACT_COMPANY_PHONE_CENTRAL, self._phone_input)

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText(texts.CONTACT_COMPANY_EMAIL_DOMAIN)
        form.addRow(texts.CONTACT_COMPANY_EMAIL_DOMAIN, self._email_input)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.setStyleSheet(get_button_secondary_style())
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        save_btn = QPushButton(texts.SAVE)
        save_btn.setStyleSheet(get_button_primary_style())
        save_btn.clicked.connect(self.accept)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def get_data(self) -> dict:
        return {
            "name": self._name_input.text().strip(),
            "phone_central": self._phone_input.text().strip() or None,
            "email_domain": self._email_input.text().strip() or None,
        }


class ContactCompanyView(QWidget):
    contact_selected = Signal(int)

    def __init__(self, contact_api: ContactApiClient, auth_api=None, parent=None):
        super().__init__(parent)
        self._contact_api = contact_api
        self._auth_api = auth_api
        self._toast_manager = None
        self._load_worker = None
        self._detail_worker = None
        self._create_worker = None
        self._setup_ui()

    def _has_create_permission(self) -> bool:
        if not self._auth_api:
            return True
        user = self._auth_api.current_user
        if not user:
            return False
        return user.has_permission("contact.companies") or user.is_module_admin("contact")

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._list_page = self._build_list_page()
        self._stack.addWidget(self._list_page)

        self._detail_page = self._build_detail_page()
        self._stack.addWidget(self._detail_page)

        self.refresh()

    # ── Page 0: Firmenliste ──

    def _build_list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title = QLabel(texts.CONTACT_NAV_COMPANIES)
        title.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_H2}; color: {PRIMARY_900}; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        if self._has_create_permission():
            new_btn = QPushButton(texts.CONTACT_COMPANY_NEW)
            new_btn.setStyleSheet(get_button_primary_style())
            new_btn.setCursor(Qt.PointingHandCursor)
            new_btn.clicked.connect(lambda: self._on_create_company())
            header.addWidget(new_btn)

        layout.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setAlignment(Qt.AlignTop)

        self._scroll.setWidget(self._cards_container)
        layout.addWidget(self._scroll)

        self._loading_label = QLabel(texts.CONTACT_COMPANY_LOADING)
        self._loading_label.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500};")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._cards_layout.addWidget(self._loading_label)

        return page

    # ── Page 1: Firmendetail mit Mitarbeitern ──

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        back_btn = QPushButton(texts.CONTACT_COMPANY_BACK)
        back_btn.setStyleSheet(get_button_secondary_style())
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        self._detail_name = QLabel()
        self._detail_name.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_H2}; color: {PRIMARY_900}; font-weight: 600;")
        layout.addWidget(self._detail_name)

        self._detail_info = QLabel()
        self._detail_info.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500};")
        self._detail_info.setWordWrap(True)
        layout.addWidget(self._detail_info)

        emp_label = QLabel(texts.CONTACT_COMPANY_EMPLOYEES)
        emp_label.setStyleSheet(f"font-family: {FONT_BODY}; font-size: 11pt; color: {PRIMARY_900}; font-weight: 600; padding-top: 8px;")
        layout.addWidget(emp_label)

        self._emp_scroll = QScrollArea()
        self._emp_scroll.setWidgetResizable(True)
        self._emp_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._emp_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._emp_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._emp_container = QWidget()
        self._emp_layout = QVBoxLayout(self._emp_container)
        self._emp_layout.setContentsMargins(0, 0, 0, 0)
        self._emp_layout.setSpacing(8)
        self._emp_layout.setAlignment(Qt.AlignTop)
        self._emp_scroll.setWidget(self._emp_container)
        layout.addWidget(self._emp_scroll)

        return page

    # ── Firmenliste laden ──

    def refresh(self):
        if self._load_worker and self._load_worker.isRunning():
            return
        self._loading_label.setVisible(True)
        self._load_worker = _CompanyLoadWorker(self._contact_api)
        self._load_worker.finished.connect(self._on_company_loaded)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.start()

    def _on_company_loaded(self, companies: list):
        self._loading_label.setVisible(False)

        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w and w != self._loading_label:
                w.deleteLater()

        if not companies:
            empty = QLabel(texts.CONTACT_COMPANY_EMPTY)
            empty.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500};")
            empty.setAlignment(Qt.AlignCenter)
            self._cards_layout.addWidget(empty)
            self._cards_layout.addWidget(self._loading_label)
            self._loading_label.setVisible(False)
            return

        has_delete = self._has_create_permission()
        for company in companies:
            card = _CompanyCard(company, has_delete=has_delete)
            card.clicked.connect(self._on_company_clicked)
            card.delete_requested.connect(self._on_delete_requested)
            self._cards_layout.addWidget(card)

        self._cards_layout.addWidget(self._loading_label)
        self._loading_label.setVisible(False)

    def _on_load_error(self, error: str):
        self._loading_label.setVisible(False)
        self._loading_label.setText(f"{texts.CONTACT_COMPANY_LOADING}: {error}")
        self._loading_label.setVisible(True)
        logger.error("Firmen laden: %s", error)
        if self._toast_manager:
            self._toast_manager.show_error(error)

    # ── Firmendetail laden ──

    def _on_company_clicked(self, company_id: int):
        if self._detail_worker and self._detail_worker.isRunning():
            return
        self._detail_worker = _CompanyDetailWorker(self._contact_api, company_id)
        self._detail_worker.finished.connect(self._on_detail_loaded)
        self._detail_worker.error.connect(self._on_detail_error)
        self._detail_worker.start()

    def _on_detail_loaded(self, data: dict):
        self._detail_name.setText(data.get("name", "-"))

        info_parts = []
        phone = data.get("phone_central", "")
        if phone:
            info_parts.append(f"{texts.CONTACT_COMPANY_PHONE_CENTRAL}: {phone}")
        email = data.get("email_domain", "")
        if email:
            info_parts.append(f"{texts.CONTACT_COMPANY_EMAIL_DOMAIN}: {email}")
        self._detail_info.setText("  |  ".join(info_parts) if info_parts else "")
        self._detail_info.setVisible(bool(info_parts))

        while self._emp_layout.count():
            item = self._emp_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        contacts = data.get("contacts", [])
        if not contacts:
            empty = QLabel(texts.CONTACT_COMPANY_NO_EMPLOYEES)
            empty.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500};")
            empty.setAlignment(Qt.AlignCenter)
            self._emp_layout.addWidget(empty)
        else:
            for c in contacts:
                row = _EmployeeRow(c)
                row.clicked.connect(self.contact_selected.emit)
                self._emp_layout.addWidget(row)

        self._stack.setCurrentIndex(1)

    def _on_detail_error(self, error: str):
        logger.error("Firmendetail: %s", error)
        if self._toast_manager:
            self._toast_manager.show_error(error)

    # ── Firma erstellen ──

    def open_create_dialog(self, prefill_name: str = ''):
        self._on_create_company(prefill_name)

    def _on_create_company(self, prefill_name: str = ''):
        dialog = _CreateCompanyDialog(self, prefill_name=prefill_name)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data["name"]:
            if self._toast_manager:
                self._toast_manager.show_warning(texts.CONTACT_COMPANY_NAME_REQUIRED)
            return
        if self._create_worker and self._create_worker.isRunning():
            return
        self._create_worker = _CompanyCreateWorker(self._contact_api, data)
        self._create_worker.finished.connect(self._on_company_created)
        self._create_worker.error.connect(self._on_create_error)
        self._create_worker.start()

    def _on_company_created(self, _result: dict):
        if self._toast_manager:
            self._toast_manager.show_success(texts.CONTACT_COMPANY_SAVED)
        self.refresh()

    def _on_create_error(self, error: str):
        logger.error("Firma erstellen: %s", error)
        if self._toast_manager:
            self._toast_manager.show_error(error)

    # ── Firma loeschen ──

    def _on_delete_requested(self, company_id: int):
        reply = QMessageBox.question(
            self, texts.CONTACT_COMPANY_DELETE, texts.CONTACT_COMPANY_DELETE_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._contact_api.delete_company(company_id)
            if self._toast_manager:
                self._toast_manager.show_success(texts.CONTACT_COMPANY_DELETED)
            self.refresh()
        except Exception as e:
            logger.error("Firma loeschen fehlgeschlagen: %s", e)
            if self._toast_manager:
                self._toast_manager.show_error(str(e))
