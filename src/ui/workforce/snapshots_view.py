"""
ACENCIA ATLAS - Workforce Snapshots View

Snapshot-Vergleich: Snapshots auflisten, zwei auswaehlen, Diff anzeigen,
Loeschen einzelner Snapshots.
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
    QFrame, QAbstractItemView, QMessageBox, QScrollArea,
    QGridLayout,
)
from PySide6.QtCore import Qt, QRunnable, QObject, Signal, QThreadPool

from workforce.api_client import WorkforceApiClient
from ui.workforce.utils import format_date_de
from ui.styles.tokens import (
    PRIMARY_900, ACCENT_500, ACCENT_100,
    FONT_HEADLINE, FONT_BODY, FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, BORDER_DEFAULT, RADIUS_MD, RADIUS_SM,
    SUCCESS, SUCCESS_LIGHT, ERROR, ERROR_LIGHT, WARNING, WARNING_LIGHT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    FONT_WEIGHT_BOLD, FONT_WEIGHT_MEDIUM,
)
from i18n import de as texts

logger = logging.getLogger(__name__)


class _SnapshotDiffSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)


class _SnapshotDiffWorker(QRunnable):
    """Worker fuer Snapshot-Vergleich (laed beide Snapshots und berechnet Diff)."""

    def __init__(self, wf_api: WorkforceApiClient, snap_id_a: int, snap_id_b: int):
        super().__init__()
        self.signals = _SnapshotDiffSignals()
        self._api = wf_api
        self._snap_id_a = snap_id_a
        self._snap_id_b = snap_id_b

    @staticmethod
    def _extract_person_info(core: dict) -> dict:
        vorname = core.get('Vorname', '')
        nachname = core.get('Name', '') or core.get('Nachname', '')
        return {
            'name': f"{vorname} {nachname}".strip(),
            'geburtsdatum': core.get('Geburtsdatum', ''),
            'personalnummer': core.get('Personalnummer', ''),
        }

    def run(self):
        try:
            snap_a = self._api.get_snapshot(self._snap_id_a)
            snap_b = self._api.get_snapshot(self._snap_id_b)

            data_a = snap_a.get('data', {})
            data_b = snap_b.get('data', {})
            pids_a = set(data_a.keys())
            pids_b = set(data_b.keys())

            added = pids_b - pids_a
            removed = pids_a - pids_b
            common = pids_a & pids_b

            changed = {}
            for pid in common:
                core_a = data_a[pid].get('core', {})
                core_b = data_b[pid].get('core', {})
                all_keys = set(core_a.keys()) | set(core_b.keys())
                field_changes = {}
                for key in all_keys:
                    val_a = core_a.get(key, '')
                    val_b = core_b.get(key, '')
                    if str(val_a) != str(val_b):
                        field_changes[key] = {'old': val_a, 'new': val_b}
                if field_changes:
                    changed[pid] = {
                        **self._extract_person_info(core_b),
                        'fields': field_changes,
                    }

            added_details = []
            for pid in added:
                core = data_b[pid].get('core', {})
                added_details.append({'pid': pid, **self._extract_person_info(core)})

            removed_details = []
            for pid in removed:
                core = data_a[pid].get('core', {})
                removed_details.append({'pid': pid, **self._extract_person_info(core)})

            self.signals.finished.emit({
                'snap_a': snap_a, 'snap_b': snap_b,
                'added': added_details, 'removed': removed_details,
                'changed': changed,
            })
        except Exception as e:
            logger.error(f"Snapshot-Diff Fehler: {e}", exc_info=True)
            self.signals.error.emit(str(e))


class SnapshotsView(QWidget):
    """Snapshot-Vergleich: Liste, Auswahl, Diff-Ansicht, Loeschen."""

    def __init__(self, wf_api: WorkforceApiClient):
        super().__init__()
        self._wf_api = wf_api
        self._toast_manager = None
        self._thread_pool = QThreadPool.globalInstance()
        self._employers: list[dict] = []
        self._snapshots: list[dict] = []
        self._selected_a: int | None = None
        self._selected_b: int | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel(texts.WF_SNAPSHOTS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900}; font-weight: bold;
        """)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        emp_label = QLabel(texts.WF_EMPLOYER_SELECT)
        emp_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-family: {FONT_BODY};")
        toolbar.addWidget(emp_label)

        self._employer_combo = QComboBox()
        self._employer_combo.setMinimumWidth(220)
        self._employer_combo.currentIndexChanged.connect(self._on_employer_changed)
        toolbar.addWidget(self._employer_combo)

        toolbar.addStretch()

        refresh_btn = QPushButton(texts.WF_REFRESH)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 4px 12px; font-family: {FONT_BODY};
                background-color: {ACCENT_100}; color: {PRIMARY_900};
                border: 1px solid {ACCENT_500}; border-radius: {RADIUS_SM};
            }}
            QPushButton:hover {{ background-color: {ACCENT_500}; color: white; }}
        """)
        refresh_btn.clicked.connect(self._load_snapshots)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        selection_frame = QFrame()
        selection_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
            }}
        """)
        sel_layout = QHBoxLayout(selection_frame)
        sel_layout.setContentsMargins(16, 12, 16, 12)
        sel_layout.setSpacing(16)

        snap_a_section = QVBoxLayout()
        snap_a_label = QLabel(texts.WF_SNAPSHOT_A_LABEL)
        snap_a_label.setStyleSheet(f"font-weight: bold; color: {TEXT_PRIMARY};")
        snap_a_section.addWidget(snap_a_label)
        self._snap_a_combo = QComboBox()
        self._snap_a_combo.setMinimumWidth(200)
        snap_a_section.addWidget(self._snap_a_combo)
        sel_layout.addLayout(snap_a_section)

        vs_label = QLabel(texts.WF_SNAPSHOT_VS)
        vs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vs_label.setStyleSheet(f"color: {ACCENT_500}; font-weight: bold; font-size: 14pt;")
        sel_layout.addWidget(vs_label)

        snap_b_section = QVBoxLayout()
        snap_b_label = QLabel(texts.WF_SNAPSHOT_B_LABEL)
        snap_b_label.setStyleSheet(f"font-weight: bold; color: {TEXT_PRIMARY};")
        snap_b_section.addWidget(snap_b_label)
        self._snap_b_combo = QComboBox()
        self._snap_b_combo.setMinimumWidth(200)
        snap_b_section.addWidget(self._snap_b_combo)
        sel_layout.addLayout(snap_b_section)

        self._compare_btn = QPushButton(texts.WF_SNAPSHOT_COMPARE_BTN)
        self._compare_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._compare_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 20px; font-family: {FONT_BODY};
                background-color: {ACCENT_500}; color: white;
                border: none; border-radius: {RADIUS_MD}; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
            QPushButton:disabled {{ background-color: {BG_SECONDARY}; color: {TEXT_DISABLED}; }}
        """)
        self._compare_btn.clicked.connect(self._on_compare)
        sel_layout.addWidget(self._compare_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        layout.addWidget(selection_frame)

        self._snapshot_table = QTableWidget()
        self._snapshot_table.setColumnCount(4)
        self._snapshot_table.setHorizontalHeaderLabels([
            texts.WF_COL_SNAPSHOT_DATE, texts.WF_COL_EMPLOYEE_COUNT,
            texts.WF_COL_SNAPSHOT_ID, texts.WF_COL_ACTIONS,
        ])
        self._snapshot_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._snapshot_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._snapshot_table.setAlternatingRowColors(True)
        self._snapshot_table.verticalHeader().setVisible(False)
        self._snapshot_table.verticalHeader().setDefaultSectionSize(44)
        self._snapshot_table.setMaximumHeight(250)

        h = self._snapshot_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._snapshot_table.setColumnWidth(3, 160)

        layout.addWidget(self._snapshot_table)

        self._diff_frame = QFrame()
        self._diff_frame.setVisible(False)
        diff_outer = QVBoxLayout(self._diff_frame)
        diff_outer.setContentsMargins(0, 0, 0, 0)
        diff_outer.setSpacing(12)

        self._diff_header = QLabel("")
        self._diff_header.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: 11pt;
            color: {PRIMARY_900}; font-weight: bold;
        """)
        diff_outer.addWidget(self._diff_header)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        self._added_badge = self._create_badge(SUCCESS, SUCCESS_LIGHT)
        summary_row.addWidget(self._added_badge)
        self._removed_badge = self._create_badge(ERROR, ERROR_LIGHT)
        summary_row.addWidget(self._removed_badge)
        self._changed_badge = self._create_badge(WARNING, WARNING_LIGHT)
        summary_row.addWidget(self._changed_badge)
        summary_row.addStretch()
        diff_outer.addLayout(summary_row)

        self._no_changes_label = QLabel(texts.WF_DIFF_NO_CHANGES)
        self._no_changes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_changes_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY}; font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY}; padding: 24px;
        """)
        self._no_changes_label.setVisible(False)
        diff_outer.addWidget(self._no_changes_label)

        self._diff_scroll = QScrollArea()
        self._diff_scroll.setWidgetResizable(True)
        self._diff_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._diff_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._diff_scroll_content = QWidget()
        self._diff_scroll_content.setStyleSheet("background: transparent;")
        self._diff_cards_layout = QVBoxLayout(self._diff_scroll_content)
        self._diff_cards_layout.setContentsMargins(0, 0, 8, 0)
        self._diff_cards_layout.setSpacing(10)
        self._diff_cards_layout.addStretch()
        self._diff_scroll.setWidget(self._diff_scroll_content)
        diff_outer.addWidget(self._diff_scroll)

        layout.addWidget(self._diff_frame, 1)

    def _create_badge(self, color: str, bg_light: str = "") -> QLabel:
        bg = bg_light if bg_light else color
        text_color = color if bg_light else "white"
        badge = QLabel("")
        badge.setStyleSheet(f"""
            background-color: {bg}; color: {text_color};
            padding: 5px 14px; border-radius: 12px;
            font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION};
            font-weight: {FONT_WEIGHT_BOLD};
            border: 1px solid {color};
        """)
        return badge

    # ── Data ───────────────────────────────────────────────────

    def refresh(self):
        self._load_employers()

    def _load_employers(self):
        try:
            self._employers = self._wf_api.get_employers()
            current_data = self._employer_combo.currentData()
            self._employer_combo.blockSignals(True)
            self._employer_combo.clear()
            if not self._employers:
                self._employer_combo.addItem(texts.WF_NO_EMPLOYERS, None)
            else:
                for emp in self._employers:
                    self._employer_combo.addItem(emp.get('name', '?'), emp.get('id'))
                if current_data:
                    idx = next(
                        (i for i, e in enumerate(self._employers) if e.get('id') == current_data), 0
                    )
                    self._employer_combo.setCurrentIndex(idx)
            self._employer_combo.blockSignals(False)
            self._load_snapshots()
        except Exception as e:
            logger.error(f"Arbeitgeber laden: {e}")

    def _on_employer_changed(self):
        self._diff_frame.setVisible(False)
        self._load_snapshots()

    def _load_snapshots(self):
        employer_id = self._employer_combo.currentData()
        if not employer_id:
            self._snapshots = []
            self._snapshot_table.setRowCount(0)
            self._update_snap_combos()
            return
        try:
            self._snapshots = self._wf_api.get_snapshots(employer_id)
            self._populate_snapshot_table()
            self._update_snap_combos()
        except Exception as e:
            logger.error(f"Snapshots laden: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(texts.WF_SNAPSHOTS_LOAD_ERROR.format(error=str(e)))

    def _populate_snapshot_table(self):
        self._snapshot_table.setSortingEnabled(False)
        self._snapshot_table.setRowCount(len(self._snapshots))

        for row, snap in enumerate(self._snapshots):
            ts = format_date_de(snap.get('snapshot_ts', '-'))
            self._snapshot_table.setItem(row, 0, QTableWidgetItem(ts))

            count = snap.get('employee_count', 0)
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._snapshot_table.setItem(row, 1, count_item)

            id_item = QTableWidgetItem(str(snap.get('id', '')))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._snapshot_table.setItem(row, 2, id_item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)

            del_btn = QPushButton(texts.DELETE)
            del_btn.setFixedHeight(26)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color: #e74c3c;
                    border: 1px solid #e74c3c; border-radius: {RADIUS_SM};
                    padding: 2px 10px; font-family: {FONT_BODY}; font-size: 12px;
                }}
                QPushButton:hover {{ background-color: #e74c3c; color: white; }}
            """)
            del_btn.clicked.connect(lambda checked, s=snap: self._on_delete_snapshot(s))
            actions_layout.addWidget(del_btn)
            actions_layout.addStretch()

            self._snapshot_table.setCellWidget(row, 3, actions_widget)

        self._snapshot_table.setSortingEnabled(True)

    def _update_snap_combos(self):
        self._snap_a_combo.clear()
        self._snap_b_combo.clear()
        for snap in self._snapshots:
            ts = format_date_de(snap.get('snapshot_ts', '-'))
            count = snap.get('employee_count', 0)
            label = f"{ts}  ({count} MA)"
            self._snap_a_combo.addItem(label, snap.get('id'))
            self._snap_b_combo.addItem(label, snap.get('id'))
        if len(self._snapshots) >= 2:
            self._snap_a_combo.setCurrentIndex(1)
            self._snap_b_combo.setCurrentIndex(0)
        self._compare_btn.setEnabled(len(self._snapshots) >= 2)

    # ── Compare ────────────────────────────────────────────────

    def _on_compare(self):
        snap_id_a = self._snap_a_combo.currentData()
        snap_id_b = self._snap_b_combo.currentData()
        if not snap_id_a or not snap_id_b:
            return
        if snap_id_a == snap_id_b:
            if self._toast_manager:
                self._toast_manager.show_warning(texts.WF_SNAPSHOT_SAME_WARNING)
            return

        self._compare_btn.setEnabled(False)
        worker = _SnapshotDiffWorker(self._wf_api, snap_id_a, snap_id_b)
        worker.signals.finished.connect(self._on_diff_done)
        worker.signals.error.connect(self._on_diff_error)
        self._thread_pool.start(worker)

    def _on_diff_done(self, result: dict):
        self._compare_btn.setEnabled(True)
        self._diff_frame.setVisible(True)

        added = result.get('added', [])
        removed = result.get('removed', [])
        changed = result.get('changed', {})

        snap_a = result.get('snap_a', {})
        snap_b = result.get('snap_b', {})
        ts_a = format_date_de(snap_a.get('snapshot_ts', '?'))
        ts_b = format_date_de(snap_b.get('snapshot_ts', '?'))
        self._diff_header.setText(texts.WF_SNAPSHOT_DIFF_HEADER.format(ts_a=ts_a, ts_b=ts_b))

        self._added_badge.setText(texts.WF_DIFF_ADDED_BADGE.format(count=len(added)))
        self._removed_badge.setText(texts.WF_DIFF_REMOVED_BADGE.format(count=len(removed)))
        self._changed_badge.setText(texts.WF_DIFF_CHANGED_BADGE.format(count=len(changed)))

        self._clear_diff_cards()

        total = len(added) + len(removed) + len(changed)
        self._no_changes_label.setVisible(total == 0)
        self._diff_scroll.setVisible(total > 0)

        for person in added:
            card = self._build_person_card(
                person_info=person,
                category=texts.WF_DIFF_EMPLOYEE_CARD_ADDED,
                accent_color=SUCCESS,
                accent_bg=SUCCESS_LIGHT,
                subtitle=texts.WF_DIFF_CATEGORY_ADDED,
            )
            self._diff_cards_layout.insertWidget(
                self._diff_cards_layout.count() - 1, card
            )

        for person in removed:
            card = self._build_person_card(
                person_info=person,
                category=texts.WF_DIFF_EMPLOYEE_CARD_REMOVED,
                accent_color=ERROR,
                accent_bg=ERROR_LIGHT,
                subtitle=texts.WF_DIFF_CATEGORY_REMOVED,
            )
            self._diff_cards_layout.insertWidget(
                self._diff_cards_layout.count() - 1, card
            )

        for pid, info in changed.items():
            fields = info.get('fields', {})
            subtitle = texts.WF_DIFF_EMPLOYEE_CARD_FIELDS_CHANGED.format(count=len(fields))
            card = self._build_person_card(
                person_info=info,
                category=texts.WF_DIFF_CATEGORY_CHANGED,
                accent_color=WARNING,
                accent_bg=WARNING_LIGHT,
                subtitle=subtitle,
                field_changes=fields,
            )
            self._diff_cards_layout.insertWidget(
                self._diff_cards_layout.count() - 1, card
            )

    def _clear_diff_cards(self):
        while self._diff_cards_layout.count() > 1:
            item = self._diff_cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _build_person_card(
        self, person_info: dict, category: str, accent_color: str,
        accent_bg: str, subtitle: str, field_changes: dict | None = None,
    ) -> QFrame:
        name = person_info.get('name', person_info.get('pid', '?'))
        geburtsdatum = format_date_de(person_info.get('geburtsdatum', '')) if person_info.get('geburtsdatum') else ''
        personalnummer = person_info.get('personalnummer', '')

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame#diffCard {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-left: 4px solid {accent_color};
                border-radius: {RADIUS_MD};
            }}
            QFrame#diffCard:hover {{
                border-color: {accent_color};
            }}
        """)
        card.setObjectName("diffCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_BODY};
            color: {TEXT_PRIMARY}; font-weight: {FONT_WEIGHT_BOLD};
            background: transparent; border: none;
        """)
        top_row.addWidget(name_label)

        top_row.addStretch()

        cat_badge = QLabel(category)
        cat_badge.setStyleSheet(f"""
            background-color: {accent_bg}; color: {accent_color};
            padding: 3px 10px; border-radius: 10px;
            font-family: {FONT_BODY}; font-size: {FONT_SIZE_CAPTION};
            font-weight: {FONT_WEIGHT_BOLD}; border: none;
        """)
        top_row.addWidget(cat_badge)

        card_layout.addLayout(top_row)

        meta_parts = []
        if geburtsdatum:
            meta_parts.append(f"{texts.WF_DIFF_LABEL_BIRTHDAY} {geburtsdatum}")
        if personalnummer:
            meta_parts.append(f"{texts.WF_DIFF_LABEL_PERSONNEL_NR} {personalnummer}")

        detail_row = QHBoxLayout()
        detail_row.setSpacing(16)

        if meta_parts:
            meta_style = f"""
                color: {TEXT_SECONDARY}; font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION}; background: transparent; border: none;
            """
            for part in meta_parts:
                ml = QLabel(part)
                ml.setStyleSheet(meta_style)
                detail_row.addWidget(ml)

        detail_row.addStretch()

        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY}; font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION}; background: transparent; border: none;
        """)
        detail_row.addWidget(sub_label)

        card_layout.addLayout(detail_row)

        if field_changes:
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setStyleSheet(f"background-color: {BORDER_DEFAULT}; border: none; max-height: 1px;")
            card_layout.addWidget(separator)

            grid = QGridLayout()
            grid.setContentsMargins(0, 4, 0, 0)
            grid.setSpacing(0)
            grid.setColumnStretch(0, 2)
            grid.setColumnStretch(1, 3)
            grid.setColumnStretch(2, 0)
            grid.setColumnStretch(3, 3)

            hdr_style = f"""
                color: {TEXT_SECONDARY}; font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION}; font-weight: {FONT_WEIGHT_BOLD};
                padding: 4px 8px; background-color: {BG_SECONDARY};
                border: none;
            """
            for col, text in enumerate([
                texts.WF_DIFF_COL_FIELD, texts.WF_DIFF_COL_OLD,
                "", texts.WF_DIFF_COL_NEW,
            ]):
                h = QLabel(text)
                h.setStyleSheet(hdr_style)
                grid.addWidget(h, 0, col)

            arrow_hdr = QLabel("")
            arrow_hdr.setFixedWidth(28)
            arrow_hdr.setStyleSheet(hdr_style)
            grid.addWidget(arrow_hdr, 0, 2)

            for row_idx, (field, vals) in enumerate(field_changes.items(), start=1):
                old_raw = vals.get('old', '')
                new_raw = vals.get('new', '')
                old_val = format_date_de(str(old_raw)) if old_raw != '' else '-'
                new_val = format_date_de(str(new_raw)) if new_raw != '' else '-'

                bg = "transparent" if row_idx % 2 == 0 else BG_TERTIARY
                cell_base = f"""
                    font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
                    padding: 6px 8px; background-color: {bg}; border: none;
                """

                field_label = QLabel(field)
                field_label.setStyleSheet(f"""
                    {cell_base} color: {TEXT_PRIMARY};
                    font-weight: {FONT_WEIGHT_MEDIUM};
                """)
                grid.addWidget(field_label, row_idx, 0)

                old_label = QLabel(old_val)
                old_label.setWordWrap(True)
                old_label.setStyleSheet(f"""
                    {cell_base} color: {ERROR};
                """)
                grid.addWidget(old_label, row_idx, 1)

                arrow = QLabel(texts.WF_DIFF_FIELD_ARROW)
                arrow.setFixedWidth(28)
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setStyleSheet(f"""
                    {cell_base} color: {TEXT_SECONDARY};
                """)
                grid.addWidget(arrow, row_idx, 2)

                new_label = QLabel(new_val)
                new_label.setWordWrap(True)
                new_label.setStyleSheet(f"""
                    {cell_base} color: {SUCCESS}; font-weight: {FONT_WEIGHT_BOLD};
                """)
                grid.addWidget(new_label, row_idx, 3)

            card_layout.addLayout(grid)

        return card

    def _on_diff_error(self, error: str):
        self._compare_btn.setEnabled(True)
        logger.error(f"Snapshot-Diff: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(texts.WF_SNAPSHOT_DIFF_ERROR.format(error=error))

    # ── Delete ─────────────────────────────────────────────────

    def _on_delete_snapshot(self, snapshot: dict):
        snap_id = snapshot.get('id')
        ts = format_date_de(snapshot.get('snapshot_ts', '?'))

        reply = QMessageBox.question(
            self, texts.WARNING,
            texts.WF_SNAPSHOT_DELETE_CONFIRM.format(date=ts),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._wf_api.delete_snapshot(snap_id)
            if self._toast_manager:
                self._toast_manager.show_success(texts.WF_SNAPSHOT_DELETED)
            self._load_snapshots()
        except Exception as e:
            logger.error(f"Snapshot loeschen: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(str(e))
