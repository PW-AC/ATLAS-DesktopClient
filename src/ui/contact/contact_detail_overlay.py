# -*- coding: utf-8 -*-
"""
Contact Detail Overlay - Modales Vollbild-Overlay fuer Kontaktdetails.

Alle Sektionen untereinander in einem scrollbaren Panel.
Speichern-Button immer sichtbar am unteren Rand.
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QFormLayout, QLineEdit, QDateEdit, QComboBox,
    QTextEdit, QScrollArea, QGraphicsOpacityEffect,
    QDialog, QDialogButtonBox, QSizePolicy, QMenu, QApplication,
    QListWidget, QListWidgetItem, QRadioButton, QButtonGroup, QGridLayout,
)
from PySide6.QtCore import Signal, Qt, QPropertyAnimation, QEasingCurve, QThread, QDate, QTimer
from PySide6.QtGui import QColor, QPainter, QAction

from contact.api_client import ContactApiClient
from api.auth import AuthAPI
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, FONT_BODY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_H2,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT, RADIUS_MD,
    PRIMARY_0, PRIMARY_100, FONT_WEIGHT_BOLD,
    ERROR, SUCCESS, TEXT_INVERSE, WARNING_LIGHT,
    get_button_primary_style, get_button_secondary_style,
)
from i18n import de as texts
from ui.contact.contact_card_widget import (
    _format_date, _format_datetime, _get_all_phones, _phone_for_teams,
    call_with_teams, copy_phone_to_clipboard,
)

logger = logging.getLogger(__name__)

_SECTION_STYLE = (
    f"font-family: {FONT_BODY}; font-size: 11pt; font-weight: {FONT_WEIGHT_BOLD}; "
    f"color: {PRIMARY_900}; background: transparent; border: none; padding-top: 12px;"
)
_ROW_STYLE = (
    f"background-color: {BG_PRIMARY}; border: 1px solid {BORDER_DEFAULT}; "
    f"border-radius: 6px; padding: 6px 10px;"
)
_LBL_STYLE = (
    f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
    f"color: {PRIMARY_900}; border: none; background: transparent;"
)


class _LoadWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: ContactApiClient, cid: int):
        super().__init__()
        self._api, self._cid = api, cid

    def run(self):
        try:
            self.finished.emit(self._api.get_contact(self._cid))
        except Exception as e:
            self.error.emit(str(e))


class _MergeSearchWorker(QThread):
    finished = Signal(list)

    def __init__(self, api: ContactApiClient, query: str, exclude_id: int):
        super().__init__()
        self._api = api
        self._query = query
        self._exclude = exclude_id

    def run(self):
        try:
            data = self._api.search(self._query, limit=15)
            contacts = [c for c in data.get('contacts', []) if c.get('id') != self._exclude]
            self.finished.emit(contacts)
        except Exception:
            self.finished.emit([])


_MERGE_FIELD_LABELS = {
    'first_name': texts.CONTACT_FIRST_NAME,
    'last_name': texts.CONTACT_LAST_NAME,
    'date_of_birth': texts.CONTACT_DATE_OF_BIRTH,
    'personnel_number': texts.CONTACT_PERSONNEL_NUMBER,
    'contact_type': texts.CONTACT_TYPE,
}


class MergeConflictDialog(QDialog):

    def __init__(self, api: ContactApiClient, source: dict, target: dict, parent=None):
        super().__init__(parent)
        self._api = api
        self._source = source
        self._target = target
        self._groups: dict[str, QButtonGroup] = {}
        self._result: dict | None = None
        self.setWindowTitle(texts.CONTACT_MERGE_CONFIRM_TITLE)
        self.setMinimumWidth(560)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        stamm_fields = ['first_name', 'last_name', 'date_of_birth', 'personnel_number', 'contact_type']
        conflicts = []
        auto_fill = []
        for f in stamm_fields:
            sv = self._source.get(f) or ''
            tv = self._target.get(f) or ''
            if sv and tv and str(sv).strip() != str(tv).strip():
                conflicts.append(f)
            elif sv and not tv:
                auto_fill.append(f)

        if conflicts:
            hdr = QLabel(texts.CONTACT_MERGE_CONFLICT_HEADER)
            hdr.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; font-weight: bold; color: {PRIMARY_900};")
            hdr.setWordWrap(True)
            root.addWidget(hdr)

            grid = QGridLayout()
            grid.setSpacing(6)
            grid.addWidget(QLabel(""), 0, 0)
            lbl_src = QLabel(texts.CONTACT_MERGE_KEEP_SOURCE)
            lbl_src.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; font-weight: bold;")
            grid.addWidget(lbl_src, 0, 1)
            lbl_tgt = QLabel(texts.CONTACT_MERGE_KEEP_TARGET)
            lbl_tgt.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; font-weight: bold;")
            grid.addWidget(lbl_tgt, 0, 2)

            for row_idx, field in enumerate(conflicts, start=1):
                sv = str(self._source.get(field) or '')
                tv = str(self._target.get(field) or '')
                label = _MERGE_FIELD_LABELS.get(field, field)
                lbl = QLabel(label)
                lbl.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900};")
                grid.addWidget(lbl, row_idx, 0)
                rb_src = QRadioButton(sv)
                rb_tgt = QRadioButton(tv)
                rb_tgt.setChecked(True)
                group = QButtonGroup(self)
                group.addButton(rb_src, 0)
                group.addButton(rb_tgt, 1)
                self._groups[field] = group
                grid.addWidget(rb_src, row_idx, 1)
                grid.addWidget(rb_tgt, row_idx, 2)

            root.addLayout(grid)

        if auto_fill:
            info_fill = QLabel(texts.CONTACT_MERGE_TRANSFER_INFO + " " + ", ".join(
                _MERGE_FIELD_LABELS.get(f, f) for f in auto_fill
            ))
            info_fill.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; color: {PRIMARY_500};")
            info_fill.setWordWrap(True)
            root.addWidget(info_fill)

        transfer_parts = []
        _add = lambda items, label: transfer_parts.append(f"{len(items)} {label}") if items else None
        _add(self._source.get('phones', []), texts.CONTACT_MERGE_PHONES)
        _add(self._source.get('emails', []), texts.CONTACT_MERGE_EMAILS)
        _add(self._source.get('notes', []), texts.CONTACT_MERGE_NOTES)
        _add(self._source.get('calls', []), texts.CONTACT_MERGE_CALLS)
        _add(self._source.get('custom_values', []), texts.CONTACT_MERGE_CUSTOM)
        _add(self._source.get('companies', []), texts.CONTACT_MERGE_COMPANIES)
        if transfer_parts:
            transfer_lbl = QLabel(texts.CONTACT_MERGE_TRANSFER_INFO + "\n" + ", ".join(transfer_parts))
            transfer_lbl.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900};")
            transfer_lbl.setWordWrap(True)
            root.addWidget(transfer_lbl)

        warn = QLabel(f"\u26A0  {texts.CONTACT_MERGE_DELETE_INFO}")
        warn.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {ERROR}; font-weight: bold;")
        warn.setWordWrap(True)
        root.addWidget(warn)

        bb = QDialogButtonBox()
        self._merge_btn = bb.addButton(texts.CONTACT_MERGE_BTN, QDialogButtonBox.ButtonRole.AcceptRole)
        self._merge_btn.setStyleSheet(get_button_primary_style())
        self._merge_btn.setCursor(Qt.PointingHandCursor)
        bb.addButton(QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def get_resolutions(self) -> dict:
        result = {}
        stamm_fields = ['first_name', 'last_name', 'date_of_birth', 'personnel_number', 'contact_type']
        for f in stamm_fields:
            sv = self._source.get(f) or ''
            tv = self._target.get(f) or ''
            if f in self._groups:
                result[f] = 'source' if self._groups[f].checkedId() == 0 else 'target'
            elif sv and not tv:
                result[f] = 'source'
        return result


class ContactDetailOverlay(QWidget):
    contact_updated = Signal()
    close_requested = Signal()

    def __init__(self, contact_api: ContactApiClient, auth_api: AuthAPI, parent=None):
        super().__init__(parent)
        self._api = contact_api
        self._auth = auth_api
        self._cid: int | None = None
        self._data: dict = {}
        self._is_new = False
        self._worker = None
        self._anim = None
        self._open_call_dialog_pending = False

        self.setVisible(False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        self._panels_row = QHBoxLayout()
        self._panels_row.setSpacing(12)
        self._panels_row.setAlignment(Qt.AlignCenter)

        self._panel = QFrame()
        self._panel.setObjectName("cdPanel")
        self._panel.setMinimumSize(680, 500)
        self._panel.setMaximumSize(760, 900)
        self._panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._panel.setStyleSheet(f"""
            QFrame#cdPanel {{
                background-color: {PRIMARY_0};
                border-radius: {RADIUS_MD};
                border: 1px solid {BORDER_DEFAULT};
            }}
        """)

        pl = QVBoxLayout(self._panel)
        pl.setContentsMargins(28, 20, 28, 16)
        pl.setSpacing(0)

        # ── Header ──
        hdr = QHBoxLayout()
        self._name_lbl = QLabel()
        self._name_lbl.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_H2}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; "
            f"background: transparent; border: none;"
        )
        self._name_lbl.setWordWrap(True)
        hdr.addWidget(self._name_lbl, 1)

        self._fav_btn = QPushButton("\u2606")
        self._fav_btn.setCursor(Qt.PointingHandCursor)
        self._fav_btn.setFixedSize(44, 44)
        self._fav_btn.setMinimumSize(44, 44)
        self._fav_btn.setStyleSheet(
            f"QPushButton {{ background-color: {PRIMARY_100}; border: 1px solid {BORDER_DEFAULT}; "
            f"border-radius: 22px; font-size: 22pt; color: {PRIMARY_500}; min-width: 44px; min-height: 44px; }} "
            f"QPushButton:hover {{ background-color: {PRIMARY_100}; color: {ACCENT_500}; border-color: {ACCENT_500}; }}"
        )
        self._fav_btn.clicked.connect(self._toggle_favorite)
        hdr.addWidget(self._fav_btn)

        self._call_btn = QPushButton(texts.CONTACT_CALL_TEAMS)
        self._call_btn.setStyleSheet(get_button_primary_style())
        self._call_btn.setCursor(Qt.PointingHandCursor)
        self._call_btn.clicked.connect(self._on_call_clicked)
        hdr.addWidget(self._call_btn)

        self._copy_btn = QPushButton(texts.CONTACT_COPY_NUMBER)
        self._copy_btn.setStyleSheet(get_button_secondary_style())
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.clicked.connect(self._on_copy_clicked)
        hdr.addWidget(self._copy_btn)

        close_btn = QPushButton("\u2715")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(44, 44)
        close_btn.setMinimumSize(44, 44)
        close_btn.setStyleSheet(
            f"QPushButton {{ background-color: {PRIMARY_100}; border: 1px solid {BORDER_DEFAULT}; "
            f"border-radius: 22px; font-size: 20pt; font-weight: bold; "
            f"color: {PRIMARY_900}; min-width: 44px; min-height: 44px; }} "
            f"QPushButton:hover {{ background-color: {PRIMARY_100}; color: {ACCENT_500}; border-color: {ACCENT_500}; }}"
        )
        close_btn.clicked.connect(self._close)
        hdr.addWidget(close_btn)
        pl.addLayout(hdr)
        pl.addSpacing(8)

        # ── Scrollbarer Inhalt ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._cl = QVBoxLayout(self._scroll_content)
        self._cl.setContentsMargins(0, 0, 12, 0)
        self._cl.setSpacing(6)

        # ── Dubletten-Merge-Banner ──
        self._merge_frame = QFrame()
        self._merge_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {WARNING_LIGHT}; border: 1px solid {ACCENT_500};
                border-radius: 6px; padding: 10px;
            }}
        """)
        mfl = QVBoxLayout(self._merge_frame)
        mfl.setContentsMargins(8, 6, 8, 6)
        mfl.setSpacing(6)
        merge_lbl = QLabel(texts.CONTACT_MERGE_LABEL)
        merge_lbl.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900}; border: none; background: transparent;")
        merge_lbl.setWordWrap(True)
        mfl.addWidget(merge_lbl)

        merge_search_row = QHBoxLayout()
        merge_search_row.setSpacing(8)
        self._merge_search = QLineEdit()
        self._merge_search.setPlaceholderText(texts.CONTACT_MERGE_SEARCH_PLACEHOLDER)
        merge_search_row.addWidget(self._merge_search, 1)
        self._merge_btn = QPushButton(texts.CONTACT_MERGE_BTN)
        self._merge_btn.setStyleSheet(get_button_primary_style())
        self._merge_btn.setCursor(Qt.PointingHandCursor)
        self._merge_btn.setEnabled(False)
        self._merge_btn.clicked.connect(self._on_merge_clicked)
        merge_search_row.addWidget(self._merge_btn)
        mfl.addLayout(merge_search_row)

        self._merge_results = QListWidget()
        self._merge_results.setMaximumHeight(150)
        self._merge_results.setVisible(False)
        self._merge_results.setStyleSheet(f"""
            QListWidget {{
                background-color: {BG_PRIMARY}; border: 1px solid {BORDER_DEFAULT};
                border-radius: 4px; font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
            }}
            QListWidget::item {{
                padding: 6px 8px;
            }}
            QListWidget::item:selected {{
                background-color: {PRIMARY_100}; color: {PRIMARY_900};
            }}
        """)
        self._merge_results.itemClicked.connect(self._on_merge_item_selected)
        mfl.addWidget(self._merge_results)

        self._merge_selected_lbl = QLabel()
        self._merge_selected_lbl.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500}; border: none; background: transparent;")
        self._merge_selected_lbl.setVisible(False)
        mfl.addWidget(self._merge_selected_lbl)

        self._merge_frame.setVisible(False)
        self._merge_target_id: int | None = None
        self._merge_search_worker = None
        self._merge_search_timer = QTimer()
        self._merge_search_timer.setSingleShot(True)
        self._merge_search_timer.setInterval(400)
        self._merge_search_timer.timeout.connect(self._do_merge_search)
        self._merge_search.textChanged.connect(self._on_merge_search_changed)

        self._cl.addWidget(self._merge_frame)

        # Sektion: Stammdaten
        self._cl.addWidget(self._heading(texts.CONTACT_DETAIL_TAB_DATA))
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._edit_fn = QLineEdit()
        self._edit_fn.setPlaceholderText(texts.CONTACT_FIRST_NAME)
        form.addRow(texts.CONTACT_FIRST_NAME + ":", self._edit_fn)
        self._edit_ln = QLineEdit()
        self._edit_ln.setPlaceholderText(texts.CONTACT_LAST_NAME)
        form.addRow(texts.CONTACT_LAST_NAME + ":", self._edit_ln)
        self._edit_dob = QDateEdit()
        self._edit_dob.setCalendarPopup(True)
        self._edit_dob.setDisplayFormat("dd.MM.yyyy")
        form.addRow(texts.CONTACT_DATE_OF_BIRTH + ":", self._edit_dob)
        self._edit_pnr = QLineEdit()
        self._edit_pnr.setPlaceholderText(texts.CONTACT_PERSONNEL_NUMBER)
        form.addRow(texts.CONTACT_PERSONNEL_NUMBER + ":", self._edit_pnr)
        self._combo_type = QComboBox()
        self._combo_type.addItem(texts.CONTACT_TYPE_PERSON, "person")
        self._combo_type.addItem(texts.CONTACT_TYPE_EMPLOYEE, "employee")
        self._combo_type.addItem(texts.CONTACT_TYPE_ASP, "asp")
        self._combo_type.addItem(texts.CONTACT_TYPE_TEMPORARY, "temporary")
        self._combo_type.addItem(texts.CONTACT_TYPE_OTHER, "other")
        self._combo_type.addItem(texts.CONTACT_TYPE_CUSTOM, "__custom__")
        self._combo_type.currentIndexChanged.connect(self._on_type_changed)
        self._edit_type_custom = QLineEdit()
        self._edit_type_custom.setPlaceholderText(texts.CONTACT_TYPE)
        self._edit_type_custom.setVisible(False)
        form.addRow(texts.CONTACT_TYPE + ":", self._combo_type)
        form.addRow("", self._edit_type_custom)
        self._combo_company = QComboBox()
        self._combo_company.addItem(texts.CONTACT_COMPANY_NONE, 0)
        form.addRow(texts.CONTACT_COMPANY_FIELD + ":", self._combo_company)
        self._cl.addLayout(form)
        self._companies_loaded = False

        # Sektion: Telefonnummern
        self._cl.addWidget(self._heading(texts.CONTACT_DETAIL_TAB_PHONES))
        self._phones_box = QVBoxLayout()
        self._phones_box.setSpacing(4)
        self._cl.addLayout(self._phones_box)
        self._add_phone_btn = self._action_btn(texts.CONTACT_PHONE_ADD, self._add_phone)
        self._cl.addWidget(self._add_phone_btn)

        # Sektion: E-Mails
        self._cl.addWidget(self._heading(texts.CONTACT_DETAIL_TAB_EMAILS))
        self._emails_box = QVBoxLayout()
        self._emails_box.setSpacing(4)
        self._cl.addLayout(self._emails_box)
        self._add_email_btn = self._action_btn(texts.CONTACT_EMAIL_ADD, self._add_email)
        self._cl.addWidget(self._add_email_btn)

        # Sektion: Weitere Felder
        self._cl.addWidget(self._heading(texts.CONTACT_DETAIL_TAB_CUSTOM))
        self._custom_box = QVBoxLayout()
        self._custom_box.setSpacing(4)
        self._cl.addLayout(self._custom_box)
        self._add_custom_btn = self._action_btn(texts.CONTACT_CUSTOM_FIELD_ADD, self._add_custom_field)
        self._cl.addWidget(self._add_custom_btn)

        # Sektion: Gespraechsjournal
        self._cl.addWidget(self._heading(texts.CONTACT_DETAIL_TAB_CALLS))
        self._calls_box = QVBoxLayout()
        self._calls_box.setSpacing(4)
        self._cl.addLayout(self._calls_box)
        self._cl.addWidget(self._action_btn(texts.CONTACT_CALL_NEW, self._open_call_dialog, primary=True))

        # Sektion: Notizen
        self._cl.addWidget(self._heading(texts.CONTACT_DETAIL_TAB_NOTES))
        self._notes_box = QVBoxLayout()
        self._notes_box.setSpacing(4)
        self._cl.addLayout(self._notes_box)
        self._cl.addWidget(self._action_btn(texts.CONTACT_NOTE_NEW, self._add_note, primary=True))

        self._cl.addStretch()
        scroll.setWidget(self._scroll_content)
        pl.addWidget(scroll, 1)

        # ── Speichern-Button (immer sichtbar) ──
        pl.addSpacing(8)
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        self._save_btn = QPushButton(texts.SAVE)
        self._save_btn.setStyleSheet(get_button_primary_style())
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setMinimumWidth(140)
        self._save_btn.setMinimumHeight(36)
        self._save_btn.clicked.connect(self._save_stammdaten)
        btn_bar.addWidget(self._save_btn)
        pl.addLayout(btn_bar)

        self._panels_row.addWidget(self._panel)

        # ── Rueckruf-Seitenpanel ──
        self._cb_panel = QFrame()
        self._cb_panel.setObjectName("cdCbPanel")
        self._cb_panel.setFixedWidth(260)
        self._cb_panel.setMaximumHeight(900)
        self._cb_panel.setStyleSheet(f"""
            QFrame#cdCbPanel {{
                background-color: {PRIMARY_0};
                border-radius: {RADIUS_MD};
                border: 1px solid {ERROR};
            }}
        """)
        cb_layout = QVBoxLayout(self._cb_panel)
        cb_layout.setContentsMargins(16, 16, 16, 16)
        cb_layout.setSpacing(8)
        cb_title = QLabel(f"\U0001F514 {texts.CONTACT_CALLBACK_OPEN}")
        cb_title.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: 11pt; font-weight: {FONT_WEIGHT_BOLD}; "
            f"color: {ERROR}; background: transparent; border: none;"
        )
        cb_layout.addWidget(cb_title)
        self._cb_scroll = QScrollArea()
        self._cb_scroll.setWidgetResizable(True)
        self._cb_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._cb_scroll.setStyleSheet("background: transparent; border: none;")
        self._cb_content = QWidget()
        self._cb_content.setStyleSheet("background: transparent;")
        self._cb_box = QVBoxLayout(self._cb_content)
        self._cb_box.setContentsMargins(0, 0, 0, 0)
        self._cb_box.setSpacing(6)
        self._cb_scroll.setWidget(self._cb_content)
        cb_layout.addWidget(self._cb_scroll)
        self._cb_panel.setVisible(False)

        self._panels_row.addWidget(self._cb_panel)

        outer_wrapper = QWidget()
        outer_wrapper.setStyleSheet("background: transparent;")
        outer_wrapper.setLayout(self._panels_row)
        outer.addWidget(outer_wrapper)

    # ── Helpers ──

    def _heading(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(_SECTION_STYLE)
        return lbl

    def _action_btn(self, text: str, handler, primary: bool = False) -> QPushButton:
        btn = QPushButton(f"  +  {text}")
        btn.setStyleSheet(get_button_primary_style() if primary else get_button_secondary_style())
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMaximumWidth(300)
        btn.clicked.connect(handler)
        return btn

    @property
    def _can_edit(self) -> bool:
        user = self._auth.current_user if self._auth else None
        return bool(user and user.has_permission('contact.edit'))

    def _row(self, text: str, on_edit=None, on_copy=None, on_delete=None) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"QFrame {{ {_ROW_STYLE} }}")
        f.setContextMenuPolicy(Qt.CustomContextMenu)
        can_edit = self._can_edit

        def _ctx(pos, _edit=on_edit, _copy=on_copy, _del=on_delete):
            menu = QMenu(f)
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {BG_PRIMARY};
                    border: 1px solid {BORDER_DEFAULT};
                    border-radius: 6px;
                    padding: 4px;
                }}
                QMenu::item {{
                    padding: 6px 20px;
                    border-radius: 4px;
                    font-family: {FONT_BODY};
                    font-size: {FONT_SIZE_BODY};
                    color: {PRIMARY_900};
                }}
                QMenu::item:selected {{
                    background-color: {PRIMARY_100};
                }}
            """)
            if _copy:
                a = QAction(texts.CONTACT_ROW_COPY, f)
                a.triggered.connect(_copy)
                menu.addAction(a)
            if _edit and can_edit:
                a = QAction(texts.CONTACT_ROW_EDIT, f)
                a.triggered.connect(_edit)
                menu.addAction(a)
            if _del and can_edit:
                a = QAction(texts.CONTACT_ROW_DELETE, f)
                a.triggered.connect(_del)
                menu.addAction(a)
            if not menu.isEmpty():
                menu.exec(f.mapToGlobal(pos))

        f.customContextMenuRequested.connect(_ctx)
        r = QHBoxLayout(f)
        r.setContentsMargins(4, 2, 4, 2)
        r.setSpacing(8)
        lbl = QLabel(text)
        lbl.setStyleSheet(_LBL_STYLE)
        lbl.setWordWrap(True)
        r.addWidget(lbl, 1)
        return f

    def _clear_box(self, box):
        while box.count():
            item = box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_box(item.layout())

    # ── Show / Close ──

    def show_contact(self, contact_id: int, open_call_dialog_immediately: bool = False):
        self._cid = contact_id
        self._is_new = False
        self._open_call_dialog_pending = open_call_dialog_immediately
        self._worker = _LoadWorker(self._api, contact_id)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def show_new_contact(self, prefill_phone: str = '', prefill_name: str = '',
                         open_call_dialog_immediately: bool = False):
        self._open_call_dialog_pending = open_call_dialog_immediately
        fn, ln = '', ''
        if prefill_name:
            parts = prefill_name.strip().split(' ', 1)
            fn, ln = parts[0], parts[1] if len(parts) > 1 else ''
        try:
            d = {'first_name': fn or None, 'last_name': ln or None, 'contact_type': 'person'}
            if prefill_phone:
                d['phones'] = [{'phone_raw': prefill_phone, 'phone_type': 'mobile', 'is_preferred': 1}]
            res = self._api.create_contact(d)
            nid = res.get('id')
            if nid:
                self._is_new = True
                self.contact_updated.emit()
                self.show_contact(nid, open_call_dialog_immediately=self._open_call_dialog_pending)
        except Exception as e:
            self._open_call_dialog_pending = False
            logger.error("Kontakt anlegen: %s", e)

    def _on_loaded(self, data: dict):
        self._data = data
        self._fill()
        self._fade_in()
        if self._open_call_dialog_pending:
            self._open_call_dialog_pending = False
            QTimer.singleShot(150, self._open_call_dialog)

    def _on_loaded_silent(self, data: dict):
        self._data = data
        self._fill(include_stammdaten=False)
        self.contact_updated.emit()

    def _on_error(self, msg: str):
        logger.error("Kontakt laden: %s", msg)

    def _fade_in(self):
        if self.parent():
            self.resize(self.parent().size())
            self.move(0, 0)
        self.setVisible(True)
        self.raise_()
        self.setFocus()
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def _close(self):
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(150)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.finished.connect(self._on_fade_out)
        self._anim.start()

    def _on_fade_out(self):
        self.setVisible(False)
        self.close_requested.emit()

    # ── Populate ──

    def _fill(self, include_stammdaten: bool = True):
        d = self._data
        can_edit = self._can_edit
        self._add_phone_btn.setVisible(can_edit)
        self._add_email_btn.setVisible(can_edit)
        self._add_custom_btn.setVisible(can_edit)
        self._save_btn.setVisible(can_edit)
        self._edit_fn.setReadOnly(not can_edit)
        self._edit_ln.setReadOnly(not can_edit)
        self._edit_pnr.setReadOnly(not can_edit)
        self._edit_dob.setEnabled(can_edit)
        self._combo_type.setEnabled(can_edit)
        self._edit_type_custom.setReadOnly(not can_edit)
        self._combo_company.setEnabled(can_edit)
        self._merge_frame.setVisible(bool(self._cid and can_edit))
        self._merge_target_id = None
        self._merge_selected_lbl.setVisible(False)
        self._merge_btn.setEnabled(False)
        self._merge_search.clear()
        self._merge_results.setVisible(False)
        self._fill_header()
        if include_stammdaten:
            self._fill_stammdaten()
        self._fill_phones()
        self._fill_emails()
        self._fill_custom()
        self._fill_calls()
        self._fill_notes()
        self._fill_callbacks()

    def _fill_header(self):
        d = self._data
        name = d.get('display_name') or f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() or texts.CONTACT_NEW
        self._name_lbl.setText(name)
        self._fav_btn.setVisible(self._cid is not None)
        is_fav = d.get('is_favorite', False)
        self._fav_btn.setText("\u2605" if is_fav else "\u2606")
        c = ACCENT_500 if is_fav else PRIMARY_500
        self._fav_btn.setStyleSheet(
            f"QPushButton {{ background-color: {PRIMARY_100}; border: 1px solid {BORDER_DEFAULT}; "
            f"border-radius: 22px; font-size: 22pt; color: {c}; min-width: 44px; min-height: 44px; }} "
            f"QPushButton:hover {{ background-color: {PRIMARY_100}; color: {ACCENT_500}; border-color: {ACCENT_500}; }}"
        )
        has_phones = bool(_get_all_phones(d))
        self._call_btn.setVisible(has_phones)
        self._copy_btn.setVisible(has_phones)

    def _fill_stammdaten(self):
        d = self._data
        self._edit_fn.setText(d.get('first_name') or '')
        self._edit_ln.setText(d.get('last_name') or '')
        dob = d.get('date_of_birth')
        if dob:
            p = str(dob)[:10].split('-')
            if len(p) == 3:
                self._edit_dob.setDate(QDate(int(p[0]), int(p[1]), int(p[2])))
        else:
            self._edit_dob.setDate(QDate(1900, 1, 1))
        self._edit_pnr.setText(str(d.get('personnel_number') or ''))
        ct = d.get('contact_type', 'person')
        idx = self._combo_type.findData(ct)
        if idx >= 0:
            self._combo_type.setCurrentIndex(idx)
            self._edit_type_custom.setVisible(False)
        else:
            custom_idx = self._combo_type.findData("__custom__")
            self._combo_type.setCurrentIndex(custom_idx)
            self._edit_type_custom.setText(ct)
            self._edit_type_custom.setVisible(True)
        self._fill_company_combo()

    def _fill_company_combo(self):
        if not self._companies_loaded:
            self._combo_company.blockSignals(True)
            self._combo_company.clear()
            self._combo_company.addItem(texts.CONTACT_COMPANY_NONE, 0)
            try:
                for c in self._api.list_companies():
                    self._combo_company.addItem(c.get('name', ''), c.get('id', 0))
            except Exception:
                pass
            self._companies_loaded = True
            self._combo_company.blockSignals(False)
        links = self._data.get('companies', [])
        current_id = links[0].get('company_id', 0) if links else 0
        idx = self._combo_company.findData(current_id)
        self._combo_company.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_type_changed(self, index: int):
        is_custom = self._combo_type.currentData() == "__custom__"
        self._edit_type_custom.setVisible(is_custom)
        if is_custom:
            self._edit_type_custom.setFocus()

    def _fill_phones(self):
        self._clear_box(self._phones_box)
        for p in self._data.get('phones', []):
            raw = p.get('phone_raw', '')
            pt = p.get('phone_type', '')
            pref = "\u2605 " if p.get('is_preferred') else ""
            lbl = p.get('label', '')
            txt = f"{pref}{pt}: {raw}" + (f" ({lbl})" if lbl else "")
            pid = p.get('id')
            del_fn = (lambda chk=False, i=pid: self._del_phone(i)) if pid else None
            edit_fn = (lambda chk=False, entry=p: self._edit_phone(entry)) if pid else None
            copy_fn = (lambda chk=False, n=raw: QApplication.clipboard().setText(n))
            self._phones_box.addWidget(self._row(txt, on_edit=edit_fn, on_copy=copy_fn, on_delete=del_fn))

    def _fill_emails(self):
        self._clear_box(self._emails_box)
        for e in self._data.get('emails', []):
            addr = e.get('email', '')
            et = e.get('email_type', '')
            pref = "\u2605 " if e.get('is_preferred') else ""
            txt = f"{pref}{et}: {addr}"
            eid = e.get('id')
            del_fn = (lambda chk=False, i=eid: self._del_email(i)) if eid else None
            edit_fn = (lambda chk=False, entry=e: self._edit_email(entry)) if eid else None
            copy_fn = (lambda chk=False, a=addr: QApplication.clipboard().setText(a))
            self._emails_box.addWidget(self._row(txt, on_edit=edit_fn, on_copy=copy_fn, on_delete=del_fn))

    def _fill_custom(self):
        self._clear_box(self._custom_box)
        for cv in self._data.get('custom_values', []):
            n, v = cv.get('field_name', ''), cv.get('field_value', '')
            cvid = cv.get('id')
            del_fn = (lambda chk=False, i=cvid: self._del_custom(i)) if cvid else None
            edit_fn = (lambda chk=False, entry=cv: self._edit_custom(entry)) if cvid else None
            copy_fn = (lambda chk=False, val=v: QApplication.clipboard().setText(val))
            self._custom_box.addWidget(self._row(f"{n}: {v}", on_edit=edit_fn, on_copy=copy_fn, on_delete=del_fn))

    def _fill_calls(self):
        self._clear_box(self._calls_box)
        calls = sorted(self._data.get('calls', []), key=lambda x: x.get('created_at', ''), reverse=True)
        for c in calls:
            dt = _format_datetime(c.get('created_at'))
            subj = c.get('subject', '') or ''
            by = c.get('created_by', '')
            d = "\u2190" if c.get('direction') == 'inbound' else "\u2192"
            cb_at = _format_datetime(c.get('callback_at')) if c.get('callback_needed') and c.get('status') == 'open' else ""
            cb = f" \U0001F514 {cb_at}" if cb_at else ""
            txt = f"{dt}  {d}  {subj}" + (f"  ({by})" if by else "") + cb
            note = c.get('note', '')
            if note:
                txt += f"\n{note[:120]}"
            copy_fn = (lambda chk=False, t=txt: QApplication.clipboard().setText(t))
            self._calls_box.addWidget(self._row(txt, on_copy=copy_fn))

    def _fill_notes(self):
        self._clear_box(self._notes_box)
        for n in self._data.get('notes', []):
            body = (n.get('content', '') or '')[:200]
            vis = n.get('visibility', 'shared')
            badge = "\U0001F512 " if vis == 'private' else ""
            by = n.get('created_by', '')
            dt = _format_datetime(n.get('created_at'))
            txt = f"{badge}{dt} ({by}): {body}"
            nid = n.get('id')
            del_fn = (lambda chk=False, i=nid: self._del_note(i)) if nid else None
            copy_fn = (lambda chk=False, b=body: QApplication.clipboard().setText(b))
            self._notes_box.addWidget(self._row(txt, on_copy=copy_fn, on_delete=del_fn))

    def _fill_callbacks(self):
        self._clear_box(self._cb_box)
        open_cbs = [
            c for c in self._data.get('calls', [])
            if isinstance(c, dict) and c.get('callback_needed') and c.get('status') == 'open'
        ]
        self._cb_panel.setVisible(len(open_cbs) > 0)
        for c in sorted(open_cbs, key=lambda x: x.get('callback_at') or x.get('created_at') or '', reverse=False):
            subj = c.get('subject', '') or ''
            cb_at = _format_datetime(c.get('callback_at')) if c.get('callback_at') else _format_datetime(c.get('created_at'))
            by = c.get('created_by', '')
            txt = f"{cb_at}\n{subj}" + (f" ({by})" if by else "")

            f = QFrame()
            f.setStyleSheet(f"QFrame {{ {_ROW_STYLE} }}")
            r = QVBoxLayout(f)
            r.setContentsMargins(6, 4, 6, 4)
            r.setSpacing(4)
            lbl = QLabel(txt)
            lbl.setStyleSheet(
                f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
                f"color: {ERROR}; border: none; background: transparent;"
            )
            lbl.setWordWrap(True)
            r.addWidget(lbl)
            cid = c.get('id')
            done_btn = QPushButton(f"\u2714 {texts.CONTACT_CALLBACK_MARK_DONE}")
            done_btn.setCursor(Qt.PointingHandCursor)
            done_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1px solid {SUCCESS}; "
                f"border-radius: 4px; padding: 4px 8px; color: {SUCCESS}; "
                f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; }} "
                f"QPushButton:hover {{ background: {SUCCESS}; color: {TEXT_INVERSE}; }}"
            )
            done_btn.clicked.connect(lambda chk=False, i=cid: self._mark_done(i))
            r.addWidget(done_btn)
            self._cb_box.addWidget(f)
        self._cb_box.addStretch()

    def _mark_done(self, call_id: int):
        try:
            self._api.update_call(call_id, {'status': 'done', 'callback_needed': 0})
            self._reload()
            self.contact_updated.emit()
        except Exception as e:
            logger.error("Rueckruf erledigen: %s", e)

    # ── Actions ──

    def _save_stammdaten(self):
        d = {
            'first_name': self._edit_fn.text().strip(),
            'last_name': self._edit_ln.text().strip(),
            'personnel_number': self._edit_pnr.text().strip(),
            'contact_type': (self._edit_type_custom.text().strip() if self._combo_type.currentData() == "__custom__" else self._combo_type.currentData()) or 'person',
        }
        dob = self._edit_dob.date()
        if dob.year() > 1900:
            d['date_of_birth'] = dob.toString('yyyy-MM-dd')
        try:
            if self._cid:
                self._api.update_contact(self._cid, d)
            else:
                ph = self._data.get('phones', [])
                if ph:
                    d['phones'] = [{'phone_raw': p['phone_raw'], 'phone_type': p.get('phone_type', 'other'),
                                    'is_preferred': p.get('is_preferred', 0)} for p in ph if p.get('phone_raw')]
                res = self._api.create_contact(d)
                nid = res.get('id')
                if nid:
                    self._cid = nid
                    self._is_new = False
            if self._cid:
                self._sync_company_link()
            self.contact_updated.emit()
            self._close()
        except Exception as e:
            logger.error("Speichern: %s", e)

    def _sync_company_link(self):
        selected_company_id = self._combo_company.currentData() or 0
        links = self._data.get('companies', [])
        current_link = links[0] if links else None
        current_company_id = current_link.get('company_id', 0) if current_link else 0
        if selected_company_id == current_company_id:
            return
        try:
            if current_link:
                self._api.unlink_company(current_link['link_id'])
            if selected_company_id:
                self._api.link_company(self._cid, selected_company_id)
        except Exception as e:
            logger.error("Firmen-Verknuepfung: %s", e)

    def _on_call_clicked(self):
        phones = _get_all_phones(self._data)
        if not phones:
            return
        if len(phones) == 1:
            call_with_teams(_phone_for_teams(phones[0][0]))
        else:
            menu = QMenu(self)
            for raw, ptype in phones:
                teams_number = _phone_for_teams(raw)
                action = QAction(f"{ptype}: {raw}", self)
                action.triggered.connect(lambda _, n=teams_number: call_with_teams(n))
                menu.addAction(action)
            menu.exec(self._call_btn.mapToGlobal(self._call_btn.rect().bottomLeft()))

    def _on_copy_clicked(self):
        phones = _get_all_phones(self._data)
        if not phones:
            return
        if len(phones) == 1:
            copy_phone_to_clipboard(_phone_for_teams(phones[0][0]))
        else:
            menu = QMenu(self)
            for raw, ptype in phones:
                teams_number = _phone_for_teams(raw)
                action = QAction(f"{ptype}: {raw}", self)
                action.triggered.connect(lambda _, n=teams_number: copy_phone_to_clipboard(n))
                menu.addAction(action)
            menu.exec(self._copy_btn.mapToGlobal(self._copy_btn.rect().bottomLeft()))

    def _toggle_favorite(self):
        if not self._cid:
            return
        try:
            if self._data.get('is_favorite'):
                self._api.remove_favorite(self._cid)
                self._data['is_favorite'] = False
            else:
                self._api.set_favorite(self._cid)
                self._data['is_favorite'] = True
            self._fill(include_stammdaten=False)
            self.contact_updated.emit()
        except Exception:
            pass

    def _add_phone(self):
        if not self._cid:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.CONTACT_PHONE_ADD)
        dlg.setMinimumWidth(380)
        f = QFormLayout(dlg)
        f.setSpacing(10)
        pe = QLineEdit()
        pe.setPlaceholderText("+49 171 1234567")
        f.addRow(texts.CONTACT_DETAIL_TAB_PHONES + ":", pe)
        tc = QComboBox()
        for l, v in [(texts.CONTACT_PHONE_TYPE_MOBILE, 'mobile'), (texts.CONTACT_PHONE_TYPE_LANDLINE, 'landline'),
                     (texts.CONTACT_PHONE_TYPE_BUSINESS, 'business_direct'), (texts.CONTACT_PHONE_TYPE_CENTRAL, 'central'),
                     (texts.CONTACT_PHONE_TYPE_WHATSAPP, 'whatsapp'), (texts.CONTACT_PHONE_TYPE_OTHER, 'other')]:
            tc.addItem(l, v)
        f.addRow(texts.CONTACT_TYPE + ":", tc)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted and pe.text().strip():
            try:
                self._api.add_phone(self._cid, {'phone_raw': pe.text().strip(), 'phone_type': tc.currentData()})
                self._reload()
                self.contact_updated.emit()
            except Exception as e:
                logger.error("Telefon: %s", e)

    def _edit_phone(self, entry: dict):
        pid = entry.get('id')
        if not pid:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.CONTACT_PHONE_EDIT)
        dlg.setMinimumWidth(380)
        f = QFormLayout(dlg)
        f.setSpacing(10)
        pe = QLineEdit(entry.get('phone_raw', ''))
        f.addRow(texts.CONTACT_DETAIL_TAB_PHONES + ":", pe)
        tc = QComboBox()
        for label, val in [(texts.CONTACT_PHONE_TYPE_MOBILE, 'mobile'), (texts.CONTACT_PHONE_TYPE_LANDLINE, 'landline'),
                           (texts.CONTACT_PHONE_TYPE_BUSINESS, 'business_direct'), (texts.CONTACT_PHONE_TYPE_CENTRAL, 'central'),
                           (texts.CONTACT_PHONE_TYPE_WHATSAPP, 'whatsapp'), (texts.CONTACT_PHONE_TYPE_OTHER, 'other')]:
            tc.addItem(label, val)
        idx = tc.findData(entry.get('phone_type', 'other'))
        if idx >= 0:
            tc.setCurrentIndex(idx)
        f.addRow(texts.CONTACT_TYPE + ":", tc)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted and pe.text().strip():
            try:
                self._api.update_phone(pid, {'phone_raw': pe.text().strip(), 'phone_type': tc.currentData()})
                self._reload()
                self.contact_updated.emit()
            except Exception as e:
                logger.error("Telefon bearbeiten: %s", e)

    def _del_phone(self, pid):
        try:
            self._api.delete_phone(pid)
            self._reload()
            self.contact_updated.emit()
        except Exception:
            pass

    def _add_email(self):
        if not self._cid:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.CONTACT_EMAIL_ADD)
        dlg.setMinimumWidth(380)
        f = QFormLayout(dlg)
        f.setSpacing(10)
        ee = QLineEdit()
        ee.setPlaceholderText("name@beispiel.de")
        f.addRow(texts.CONTACT_DETAIL_TAB_EMAILS + ":", ee)
        tc = QComboBox()
        tc.addItem(texts.CONTACT_NOTE_VISIBILITY_PRIVATE, "personal")
        tc.addItem(texts.CONTACT_PHONE_TYPE_BUSINESS, "business")
        tc.addItem(texts.CONTACT_PHONE_TYPE_OTHER, "other")
        f.addRow(texts.CONTACT_TYPE + ":", tc)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted and ee.text().strip():
            try:
                self._api.add_email(self._cid, {'email': ee.text().strip(), 'email_type': tc.currentData()})
                self._reload()
                self.contact_updated.emit()
            except Exception as e:
                logger.error("E-Mail: %s", e)

    def _edit_email(self, entry: dict):
        eid = entry.get('id')
        if not eid:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.CONTACT_EMAIL_EDIT)
        dlg.setMinimumWidth(380)
        f = QFormLayout(dlg)
        f.setSpacing(10)
        ee = QLineEdit(entry.get('email', ''))
        f.addRow(texts.CONTACT_DETAIL_TAB_EMAILS + ":", ee)
        tc = QComboBox()
        tc.addItem(texts.CONTACT_NOTE_VISIBILITY_PRIVATE, "personal")
        tc.addItem(texts.CONTACT_PHONE_TYPE_BUSINESS, "business")
        tc.addItem(texts.CONTACT_PHONE_TYPE_OTHER, "other")
        idx = tc.findData(entry.get('email_type', 'other'))
        if idx >= 0:
            tc.setCurrentIndex(idx)
        f.addRow(texts.CONTACT_TYPE + ":", tc)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted and ee.text().strip():
            try:
                self._api.update_email(eid, {'email': ee.text().strip(), 'email_type': tc.currentData()})
                self._reload()
                self.contact_updated.emit()
            except Exception as e:
                logger.error("E-Mail bearbeiten: %s", e)

    def _del_email(self, eid):
        try:
            self._api.delete_email(eid)
            self._reload()
            self.contact_updated.emit()
        except Exception:
            pass

    def _add_custom_field(self):
        if not self._cid:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.CONTACT_CUSTOM_FIELD_ADD)
        dlg.setMinimumWidth(380)
        f = QFormLayout(dlg)
        f.setSpacing(10)
        ne = QLineEdit()
        ne.setPlaceholderText(texts.CONTACT_CUSTOM_FIELD_NAME)
        f.addRow(texts.CONTACT_CUSTOM_FIELD_NAME + ":", ne)
        ve = QLineEdit()
        ve.setPlaceholderText(texts.CONTACT_CUSTOM_FIELD_VALUE)
        f.addRow(texts.CONTACT_CUSTOM_FIELD_VALUE + ":", ve)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted and ne.text().strip():
            try:
                self._api.add_custom_value(self._cid, ne.text().strip(), ve.text().strip())
                self._reload()
                self.contact_updated.emit()
            except Exception as e:
                logger.error("Feld: %s", e)

    def _edit_custom(self, entry: dict):
        cvid = entry.get('id')
        if not cvid:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.CONTACT_CUSTOM_EDIT)
        dlg.setMinimumWidth(380)
        f = QFormLayout(dlg)
        f.setSpacing(10)
        ne = QLineEdit(entry.get('field_name', ''))
        f.addRow(texts.CONTACT_CUSTOM_FIELD_NAME + ":", ne)
        ve = QLineEdit(entry.get('field_value', ''))
        f.addRow(texts.CONTACT_CUSTOM_FIELD_VALUE + ":", ve)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted and ne.text().strip():
            try:
                self._api.update_custom_value(cvid, {
                    'field_name': ne.text().strip(),
                    'field_value': ve.text().strip(),
                })
                self._reload()
                self.contact_updated.emit()
            except Exception as e:
                logger.error("Feld bearbeiten: %s", e)

    def _del_custom(self, cid):
        try:
            self._api.delete_custom_value(cid)
            self._reload()
            self.contact_updated.emit()
        except Exception:
            pass

    def _open_call_dialog(self):
        if not self._cid:
            return
        from ui.contact.contact_call_dialog import ContactCallDialog
        dlg = ContactCallDialog(self._api, self._cid, self, contact_data=self._data)
        dlg.call_saved.connect(self._on_call_saved)
        dlg.exec()

    def _on_call_saved(self):
        self._reload()
        self.contact_updated.emit()

    def _add_note(self):
        if not self._cid:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.CONTACT_NOTE_NEW)
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)
        ce = QTextEdit()
        ce.setPlaceholderText(texts.CONTACT_CALL_NOTE)
        ce.setMinimumHeight(100)
        lay.addWidget(ce)
        vc = QComboBox()
        vc.addItem(texts.CONTACT_NOTE_VISIBILITY_SHARED, "shared")
        vc.addItem(texts.CONTACT_NOTE_VISIBILITY_PRIVATE, "private")
        lay.addWidget(vc)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted and ce.toPlainText().strip():
            try:
                self._api.create_note(self._cid, {'content': ce.toPlainText().strip(), 'visibility': vc.currentData()})
                self._reload()
                self.contact_updated.emit()
            except Exception as e:
                logger.error("Notiz: %s", e)

    def _del_note(self, nid):
        try:
            self._api.delete_note(nid)
            self._reload()
            self.contact_updated.emit()
        except Exception:
            pass

    def _reload(self):
        if not self._cid:
            return
        self._worker = _LoadWorker(self._api, self._cid)
        self._worker.finished.connect(self._on_loaded_silent)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    # ── Merge (Dubletten zusammenfuehren) ──

    def _on_merge_search_changed(self, text: str):
        self._merge_search_timer.stop()
        if len(text.strip()) < 2:
            self._merge_results.setVisible(False)
            return
        self._merge_search_timer.start()

    def _do_merge_search(self):
        q = self._merge_search.text().strip()
        if len(q) < 2 or not self._cid:
            return
        self._merge_search_worker = _MergeSearchWorker(self._api, q, self._cid)
        self._merge_search_worker.finished.connect(self._on_merge_search_results)
        self._merge_search_worker.start()

    def _on_merge_search_results(self, contacts: list):
        self._merge_results.clear()
        if not contacts:
            item = QListWidgetItem(texts.CONTACT_MERGE_NO_RESULTS)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self._merge_results.addItem(item)
            self._merge_results.setVisible(True)
            return
        for c in contacts:
            name = c.get('display_name') or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            phone = c.get('phone', '')
            display = f"{name}" + (f"  ({phone})" if phone else "")
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, c.get('id'))
            item.setData(Qt.UserRole + 1, name)
            self._merge_results.addItem(item)
        self._merge_results.setVisible(True)

    def _on_merge_item_selected(self, item: QListWidgetItem):
        cid = item.data(Qt.UserRole)
        name = item.data(Qt.UserRole + 1)
        if not cid:
            return
        self._merge_target_id = cid
        self._merge_selected_lbl.setText(f"\u2192  {name} (#{cid})")
        self._merge_selected_lbl.setVisible(True)
        self._merge_results.setVisible(False)
        self._merge_search.clear()
        self._merge_btn.setEnabled(True)

    def _on_merge_clicked(self):
        if not self._cid or not self._merge_target_id:
            return
        try:
            source_data = self._api.get_contact(self._cid)
            target_data = self._api.get_contact(self._merge_target_id)
        except Exception as e:
            logger.error("Merge-Daten laden: %s", e)
            return

        dlg = MergeConflictDialog(self._api, source_data, target_data, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        resolutions = dlg.get_resolutions()
        try:
            self._api.merge_contacts(self._merge_target_id, self._cid, resolutions)
            self._merge_target_id = None
            self._merge_selected_lbl.setVisible(False)
            self._merge_btn.setEnabled(False)
            self.contact_updated.emit()
            self._close()
        except Exception as e:
            logger.error("Merge ausfuehren: %s", e)

    # ── Events ──

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 15, 30, 100))

    def resizeEvent(self, event):
        if self.parent():
            self.resize(self.parent().size())
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        in_main = self._panel.geometry().contains(event.pos())
        in_cb = self._cb_panel.isVisible() and self._cb_panel.geometry().contains(event.pos())
        if not in_main and not in_cb:
            self._close()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._close()
        else:
            super().keyPressEvent(event)
