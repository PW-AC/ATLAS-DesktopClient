"""
Contact Card Widget - QFrame-basierte Karte zur Darstellung eines Kontakts.

Zeigt Anzeigename, Geburtsdatum, Telefon, Tags und Mini-Historie.
"""

import urllib.parse

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QSizePolicy, QMenu, QApplication, QPushButton,
)
from PySide6.QtCore import Signal, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices

from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_H2,
    BG_PRIMARY, BORDER_DEFAULT, RADIUS_XL, FONT_WEIGHT_BOLD,
    INFO_LIGHT, VIOLET, BLUE_BRIGHT, ERROR_LIGHT, ERROR,
    WARNING_LIGHT, TEXT_DISABLED, SUCCESS, TEXT_INVERSE,
)
from i18n import de as texts

_CONTACT_TYPE_STYLE = {
    'person': {
        'bg': INFO_LIGHT, 'accent': VIOLET,
        'icon': texts.CONTACT_CARD_ICON_PERSON, 'badge': texts.CONTACT_TYPE_PERSON,
    },
    'employee': {
        'bg': INFO_LIGHT, 'accent': BLUE_BRIGHT,
        'icon': texts.CONTACT_CARD_ICON_EMPLOYEE, 'badge': texts.CONTACT_TYPE_EMPLOYEE,
    },
    'asp': {
        'bg': ERROR_LIGHT, 'accent': ERROR,
        'icon': texts.CONTACT_CARD_ICON_ASP, 'badge': texts.CONTACT_TYPE_ASP,
    },
    'temporary': {
        'bg': WARNING_LIGHT, 'accent': ACCENT_500,
        'icon': texts.CONTACT_CARD_ICON_TEMPORARY, 'badge': texts.CONTACT_TYPE_TEMPORARY,
    },
}
_DEFAULT_TYPE_STYLE = {
    'bg': BG_PRIMARY, 'accent': TEXT_DISABLED,
    'icon': texts.CONTACT_CARD_ICON_OTHER, 'badge': texts.CONTACT_TYPE_OTHER,
}


def _format_display_name(contact: dict) -> str:
    """Baut den Anzeigenamen aus first_name und last_name."""
    first = contact.get('first_name', '') or ''
    last = contact.get('last_name', '') or ''
    display = contact.get('display_name', '').strip()
    if display:
        return display
    return f"{first} {last}".strip() or "-"


def _get_primary_phone(contact: dict) -> str:
    """Liefert die bevorzugte oder erste Telefonnummer."""
    phones = _get_all_phones(contact)
    if phones:
        return phones[0][0]  # (raw, type_key) -> raw
    return contact.get('phone', '') or ''


def _get_all_phones(contact: dict) -> list[tuple[str, str]]:
    """Liefert alle Telefonnummern als [(phone_raw, phone_type), ...], bevorzugte zuerst."""
    phones = contact.get('phones') or contact.get('phone_numbers') or []
    if not isinstance(phones, list) or not phones:
        single = (contact.get('phone', '') or '').strip()
        return [(single, 'other')] if single else []
    result = []
    for p in sorted(phones, key=lambda x: (0 if (isinstance(x, dict) and x.get('is_preferred')) else 1)):
        if not isinstance(p, dict):
            continue
        raw = (p.get('phone_raw', '') or p.get('phone', '') or '').strip()
        if raw:
            result.append((raw, p.get('phone_type', 'other')))
    return result


_PHONE_TYPE_LABELS = {
    'mobile': texts.CONTACT_PHONE_TYPE_MOBILE,
    'landline': texts.CONTACT_PHONE_TYPE_LANDLINE,
    'business_direct': texts.CONTACT_PHONE_TYPE_BUSINESS,
    'central': texts.CONTACT_PHONE_TYPE_CENTRAL,
    'whatsapp': texts.CONTACT_PHONE_TYPE_WHATSAPP,
    'other': texts.CONTACT_PHONE_TYPE_OTHER,
}


def _phone_for_teams(phone: str, default_country: str = '+49') -> str:
    """Formatiert Nummer fuer Teams: E.164 ohne Leerzeichen (+49123456789)."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit() or c == '+')
    if not digits:
        return ''
    if digits.startswith('+'):
        return '+' + ''.join(c for c in digits[1:] if c.isdigit())
    if digits.startswith('00'):
        return '+' + ''.join(c for c in digits[2:] if c.isdigit())
    if digits.startswith('0'):
        return default_country + ''.join(c for c in digits[1:] if c.isdigit())
    # Bereits mit Laendervorwahl (z.B. 491756955231): nur + davorsetzen
    if digits.startswith('49') and len(digits) >= 11:
        return '+' + digits
    # International (z.B. 4312345678): + davorsetzen
    if len(digits) >= 10:
        return '+' + digits
    return default_country + digits


def call_with_teams(number: str) -> None:
    """Startet einen Teams-PSTN-Anruf fuer die uebergebene E.164-Nummer."""
    if not number:
        return
    users_value = f"4:{number}"
    uri = f"https://teams.microsoft.com/l/call/0/0?users={urllib.parse.quote(users_value, safe='')}"
    QDesktopServices.openUrl(QUrl(uri))


def copy_phone_to_clipboard(number: str) -> None:
    """Kopiert eine Telefonnummer in die Zwischenablage."""
    if number:
        QApplication.clipboard().setText(number)


def _format_date(value) -> str:
    """Formatiert ein ISO-Datum (yyyy-MM-dd) ins deutsche Format (dd.MM.yyyy)."""
    if not value:
        return ''
    s = str(value).strip()
    if len(s) >= 10 and s[4] == '-':
        return f"{s[8:10]}.{s[5:7]}.{s[:4]}"
    return s


def _format_datetime(value) -> str:
    """Formatiert ein ISO-Datetime ins deutsche Format (dd.MM.yyyy HH:mm)."""
    if not value:
        return ''
    s = str(value).strip().replace('T', ' ')
    if len(s) >= 16 and s[4] == '-':
        return f"{s[8:10]}.{s[5:7]}.{s[:4]} {s[11:16]}"
    return s


class ContactCard(QFrame):
    """Karten-Widget fuer einen Kontakt in der Grid-Ansicht."""

    clicked = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, contact: dict, parent=None):
        super().__init__(parent)
        self._contact = contact
        self._contact_id = contact.get('id', 0)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._setup_ui()

    def _setup_ui(self):
        ct = self._contact.get('contact_type', 'person') or 'person'
        ts = _CONTACT_TYPE_STYLE.get(ct, _DEFAULT_TYPE_STYLE)

        self.setFixedWidth(280)
        self.setMinimumHeight(95)
        self.setMaximumHeight(170)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        self.setObjectName("contact_card")
        self.setStyleSheet(f"""
            QFrame#contact_card {{
                background-color: {ts['bg']};
                border: 1px solid {BORDER_DEFAULT};
                border-left: 4px solid {ts['accent']};
                border-radius: {RADIUS_XL};
            }}
            QFrame#contact_card:hover {{
                border-color: {ACCENT_500};
                border-left: 4px solid {ts['accent']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)

        type_icon = QLabel(ts['icon'])
        type_icon.setStyleSheet("font-size: 18pt; padding: 0; margin: 0;")
        header.addWidget(type_icon, 0, Qt.AlignTop)

        name_lbl = QLabel(_format_display_name(self._contact))
        name_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_H2};
            font-weight: 600;
            color: {PRIMARY_900};
        """)
        name_lbl.setWordWrap(True)
        header.addWidget(name_lbl, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        right_col.setContentsMargins(0, 0, 0, 0)

        companies = self._contact.get('companies') or []
        company_name = companies[0].get('company_name', '') if companies else ''
        if company_name:
            company_lbl = QLabel(company_name)
            company_lbl.setStyleSheet(f"""
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                color: {PRIMARY_500};
            """)
            company_lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
            right_col.addWidget(company_lbl)

        if self._contact.get('is_favorite'):
            star = QLabel("\u2605")
            star.setStyleSheet(f"color: {ACCENT_500}; font-size: 14pt;")
            star.setAlignment(Qt.AlignRight)
            right_col.addWidget(star)

        right_col.addStretch()
        header.addLayout(right_col)
        layout.addLayout(header)

        badge = QLabel(ts['badge'])
        badge.setStyleSheet(f"""
            background-color: {ts['accent']};
            color: {TEXT_INVERSE};
            padding: 1px 8px;
            border-radius: 4px;
            font-size: {FONT_SIZE_CAPTION};
            font-family: {FONT_BODY};
            font-weight: 600;
        """)
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout.addWidget(badge)

        dob = self._contact.get('date_of_birth') or self._contact.get('birth_date')
        if dob:
            dob_lbl = QLabel(_format_date(dob))
            dob_lbl.setStyleSheet(f"""
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                color: {PRIMARY_500};
            """)
            layout.addWidget(dob_lbl)

        phone = _get_primary_phone(self._contact)
        if phone:
            phone_row = QHBoxLayout()
            phone_row.setSpacing(6)
            phone_lbl = QLabel(phone)
            phone_lbl.setStyleSheet(f"""
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            """)
            phone_row.addWidget(phone_lbl, 1)

            call_btn = QPushButton("\U0001F4DE")
            call_btn.setToolTip(texts.CONTACT_CALL_TEAMS)
            call_btn.setFixedSize(28, 28)
            call_btn.setCursor(Qt.PointingHandCursor)
            call_btn.setStyleSheet(
                f"QPushButton {{ background-color: {SUCCESS}; border: none; border-radius: 14px; "
                f"font-size: 13pt; color: {TEXT_INVERSE}; padding: 0; }} "
                f"QPushButton:hover {{ background-color: {SUCCESS}; }}"
            )
            teams_number = _phone_for_teams(phone)
            call_btn.clicked.connect(lambda _, n=teams_number: call_with_teams(n))
            phone_row.addWidget(call_btn, 0, Qt.AlignVCenter)
            layout.addLayout(phone_row)

        tags = self._contact.get('tags') or []
        if tags:
            tags_row = QHBoxLayout()
            tags_row.setSpacing(4)
            for tag in tags[:5]:
                tag_name = (tag.get('tag_name') or tag.get('name') or tag) if isinstance(tag, dict) else str(tag)
                tag_color = tag.get('color', ACCENT_500) if isinstance(tag, dict) else ACCENT_500
                chip = QLabel(str(tag_name))
                chip.setStyleSheet(f"""
                    background-color: {tag_color};
                    color: white;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: {FONT_SIZE_CAPTION};
                    font-family: {FONT_BODY};
                """)
                tags_row.addWidget(chip)
            tags_row.addStretch()
            layout.addLayout(tags_row)

        layout.addSpacing(4)

        last_call_at = self._contact.get('last_call_at')
        last_call_by = self._contact.get('last_call_by')
        open_callbacks = self._contact.get('open_callbacks', 0)
        if isinstance(open_callbacks, bool):
            open_callbacks = 1 if open_callbacks else 0

        if last_call_at or last_call_by:
            history_parts = []
            if last_call_at:
                history_parts.append(f"{texts.CONTACT_CARD_LAST_CONTACT}: {_format_date(last_call_at)}")
            if last_call_by:
                history_parts.append(f"{texts.CONTACT_CARD_SPOKEN_BY}: {last_call_by}")
            history_lbl = QLabel("\n".join(history_parts))
            history_lbl.setStyleSheet(f"""
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                color: {PRIMARY_500};
            """)
            history_lbl.setWordWrap(True)
            layout.addWidget(history_lbl)

        if open_callbacks and open_callbacks > 0:
            cb_lbl = QLabel(f"\U0001F514 {texts.CONTACT_CARD_OPEN_CALLBACK} ({open_callbacks})")
            cb_lbl.setStyleSheet(f"""
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: {FONT_WEIGHT_BOLD};
                color: {ERROR};
            """)
            cb_lbl.setWordWrap(True)
            layout.addWidget(cb_lbl)

        layout.addStretch()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._contact_id)
        super().mouseReleaseEvent(event)

    def _show_context_menu(self, pos):
        if not self._contact_id:
            return
        menu = QMenu(self)
        phones = _get_all_phones(self._contact)
        if phones:
            if len(phones) == 1:
                raw, ptype = phones[0]
                teams_number = _phone_for_teams(raw)
                call_action = QAction(texts.CONTACT_CALL_TEAMS, self)
                call_action.triggered.connect(lambda: self._call_with_teams(teams_number))
                menu.addAction(call_action)
                copy_action = QAction(texts.CONTACT_COPY_NUMBER, self)
                copy_action.triggered.connect(lambda: self._copy_number(teams_number))
                menu.addAction(copy_action)
            else:
                call_sub = menu.addMenu(texts.CONTACT_CALL_TEAMS)
                copy_sub = menu.addMenu(texts.CONTACT_COPY_NUMBER)
                for raw, ptype in phones:
                    teams_number = _phone_for_teams(raw)
                    label = _PHONE_TYPE_LABELS.get(ptype, ptype)
                    call_a = QAction(label, self)
                    call_a.triggered.connect(lambda _, n=teams_number: self._call_with_teams(n))
                    call_sub.addAction(call_a)
                    copy_a = QAction(label, self)
                    copy_a.triggered.connect(lambda _, n=teams_number: self._copy_number(n))
                    copy_sub.addAction(copy_a)
        delete_action = QAction(texts.CONTACT_DELETE, self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self._contact_id))
        menu.addAction(delete_action)
        menu.exec(self.mapToGlobal(pos))

    def _copy_number(self, number: str):
        copy_phone_to_clipboard(number)

    def _call_with_teams(self, number: str):
        call_with_teams(number)
