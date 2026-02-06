"""
BiPRO-GDV Tool - Einstellungen Dialog

Minimaler Dialog für:
- Zertifikat-Verwaltung (Import, Liste, Löschen)

Design: ACENCIA Corporate Identity
"""

from typing import Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QLineEdit, QFormLayout,
    QGroupBox, QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from config.certificates import get_certificate_manager, CertificateInfo
from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, 
    TEXT_PRIMARY, TEXT_SECONDARY,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, WARNING, ERROR,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD, SPACING_SM, SPACING_MD,
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style
)

class CertificateListItem(QFrame):
    """Einzelnes Zertifikat in der Liste."""
    
    delete_requested = Signal(str)  # cert_id
    
    def __init__(self, cert: CertificateInfo, parent=None):
        super().__init__(parent)
        self.cert = cert
        self._setup_ui()
    
    def _setup_ui(self):
        self.setObjectName("certItem")
        self.setStyleSheet(f"""
            QFrame#certItem {{
                background-color: {PRIMARY_0};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 12px;
                margin-bottom: 8px;
            }}
            QFrame#certItem:hover {{
                border-color: {PRIMARY_500};
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Info-Bereich
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # Name + Status
        name_row = QHBoxLayout()
        name_label = QLabel(self.cert.name)
        name_label.setFont(QFont(FONT_BODY, 11))
        name_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: 500;")
        name_row.addWidget(name_label)
        
        # Status-Badge
        if self.cert.is_expired:
            status = QLabel(texts.CERT_EXPIRED)
            status.setStyleSheet(f"""
                background-color: {ERROR};
                color: white;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
        else:
            days = self.cert.days_until_expiry
            if days < 30:
                status = QLabel(f"{days} Tage")
                status.setStyleSheet(f"""
                    background-color: {WARNING};
                    color: white;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                """)
            else:
                status = QLabel(texts.CERT_VALID)
                status.setStyleSheet(f"""
                    background-color: {SUCCESS};
                    color: white;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                """)
        name_row.addWidget(status)
        name_row.addStretch()
        info_layout.addLayout(name_row)
        
        # Subject
        subject_label = QLabel(f"{texts.CERT_SUBJECT}: {self.cert.subject_cn}")
        subject_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        info_layout.addWidget(subject_label)
        
        # Gültigkeit
        valid_from = self._format_date(self.cert.valid_from)
        valid_until = self._format_date(self.cert.valid_until)
        validity_label = QLabel(f"{texts.CERT_VALID_UNTIL}: {valid_until}")
        validity_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        info_layout.addWidget(validity_label)
        
        layout.addLayout(info_layout, 1)
        
        # Löschen-Button
        delete_btn = QPushButton(texts.DELETE)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {ERROR};
                border-radius: {RADIUS_MD};
                padding: 6px 12px;
                color: {ERROR};
                font-size: {FONT_SIZE_CAPTION};
            }}
            QPushButton:hover {{
                background-color: {ERROR};
                color: white;
            }}
        """)
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.cert.id))
        layout.addWidget(delete_btn)
    
    def _format_date(self, iso_date: str) -> str:
        """Formatiert ISO-Datum zu deutschem Format."""
        try:
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return dt.strftime('%d.%m.%Y')
        except (ValueError, TypeError):
            return iso_date[:10] if iso_date else "-"


class CertificateImportDialog(QDialog):
    """Dialog zum Importieren eines Zertifikats."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(texts.CERT_IMPORT_TITLE)
        self.setMinimumWidth(450)
        self.setModal(True)
        
        self._selected_file = ""
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Titel
        title = QLabel(texts.CERT_IMPORT_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 14))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        layout.addWidget(title)
        
        # Beschreibung
        desc = QLabel(texts.CERT_IMPORT_DESC)
        desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(desc)
        
        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # Datei-Auswahl
        file_row = QHBoxLayout()
        self.file_label = QLabel(texts.CERT_FILE_SELECT)
        self.file_label.setStyleSheet(f"""
            background-color: {BG_SECONDARY};
            border: 1px solid {BORDER_DEFAULT};
            border-radius: {RADIUS_MD};
            padding: 8px 12px;
            color: {TEXT_SECONDARY};
        """)
        self.file_label.setMinimumWidth(250)
        file_row.addWidget(self.file_label, 1)
        
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(40)
        browse_btn.setStyleSheet(get_button_secondary_style())
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        
        form_layout.addRow(texts.CERT_FILE, file_row)
        
        # Passwort
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(texts.CERT_PASSWORD_PLACEHOLDER)
        self.password_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 8px 12px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT_500};
            }}
        """)
        form_layout.addRow(texts.CERT_PASSWORD, self.password_input)
        
        # Anzeigename
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(texts.CERT_NAME_PLACEHOLDER)
        self.name_input.setStyleSheet(self.password_input.styleSheet())
        form_layout.addRow(texts.CERT_NAME, self.name_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.setStyleSheet(get_button_secondary_style())
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.import_btn = QPushButton(texts.CERT_IMPORT)
        self.import_btn.setStyleSheet(get_button_primary_style())
        self.import_btn.clicked.connect(self.accept)
        self.import_btn.setEnabled(False)
        btn_layout.addWidget(self.import_btn)
        
        layout.addLayout(btn_layout)
    
    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            texts.CERT_FILE_SELECT,
            "",
            texts.CERT_FILE_FILTER
        )
        if file_path:
            self._selected_file = file_path
            self.file_label.setText(file_path.split('/')[-1].split('\\')[-1])
            self.file_label.setStyleSheet(f"""
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 8px 12px;
                color: {TEXT_PRIMARY};
            """)
            self.import_btn.setEnabled(True)
    
    def get_values(self) -> tuple:
        """Gibt (file_path, password, name) zurück."""
        return (
            self._selected_file,
            self.password_input.text(),
            self.name_input.text()
        )


class SettingsDialog(QDialog):
    """
    Einstellungen-Dialog.
    
    Minimal gehalten - nur Zertifikat-Verwaltung.
    """
    
    certificates_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(texts.SETTINGS_TITLE)
        self.setMinimumSize(550, 450)
        self.setModal(True)
        
        self.cert_manager = get_certificate_manager()
        self._setup_ui()
        self._refresh_certificates()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel(texts.SETTINGS_CERTIFICATES)
        header.setFont(QFont(FONT_HEADLINE, 16))
        header.setStyleSheet(f"color: {PRIMARY_900};")
        layout.addWidget(header)
        
        # Beschreibung
        desc = QLabel(texts.SETTINGS_CERTIFICATES_DESC)
        desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Zertifikats-Liste (scrollbar)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
        """)
        
        self.cert_container = QWidget()
        self.cert_layout = QVBoxLayout(self.cert_container)
        self.cert_layout.setContentsMargins(0, 0, 0, 0)
        self.cert_layout.setSpacing(8)
        self.cert_layout.addStretch()
        
        scroll.setWidget(self.cert_container)
        layout.addWidget(scroll, 1)
        
        # Keine Zertifikate Label
        self.no_certs_label = QLabel(texts.SETTINGS_NO_CERTIFICATES)
        self.no_certs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_certs_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            padding: 40px;
            font-style: italic;
        """)
        self.cert_layout.insertWidget(0, self.no_certs_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        import_btn = QPushButton(f"+ {texts.CERT_IMPORT}")
        import_btn.setStyleSheet(get_button_primary_style())
        import_btn.clicked.connect(self._import_certificate)
        btn_layout.addWidget(import_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton(texts.CLOSE)
        close_btn.setStyleSheet(get_button_secondary_style())
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _refresh_certificates(self):
        """Aktualisiert die Zertifikats-Liste."""
        # Alte Items entfernen (außer Stretch und no_certs_label)
        while self.cert_layout.count() > 2:
            item = self.cert_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        certs = self.cert_manager.list_certificates()
        
        if not certs:
            self.no_certs_label.show()
        else:
            self.no_certs_label.hide()
            for cert in certs:
                item = CertificateListItem(cert)
                item.delete_requested.connect(self._delete_certificate)
                # Vor dem Stretch einfügen
                self.cert_layout.insertWidget(self.cert_layout.count() - 1, item)
    
    def _import_certificate(self):
        """Öffnet den Import-Dialog."""
        dialog = CertificateImportDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            file_path, password, name = dialog.get_values()
            
            try:
                self.cert_manager.import_certificate(file_path, password, name)
                QMessageBox.information(
                    self,
                    texts.SUCCESS,
                    texts.CERT_IMPORT_SUCCESS
                )
                self._refresh_certificates()
                self.certificates_changed.emit()
            except ValueError as e:
                QMessageBox.warning(
                    self,
                    texts.ERROR,
                    str(e)
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    texts.ERROR,
                    f"{texts.CERT_IMPORT_ERROR}\n\n{e}"
                )
    
    def _delete_certificate(self, cert_id: str):
        """Löscht ein Zertifikat nach Bestätigung."""
        cert = self.cert_manager.get_certificate(cert_id)
        if not cert:
            return
        
        reply = QMessageBox.question(
            self,
            texts.CERT_DELETE_CONFIRM,
            texts.CERT_DELETE_CONFIRM_DESC.format(name=cert.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.cert_manager.delete_certificate(cert_id)
            self._refresh_certificates()
            self.certificates_changed.emit()
