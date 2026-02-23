"""
ACENCIA ATLAS - Sessions Panel

Standalone QWidget fuer die Session-Verwaltung im Admin-Bereich.
Extrahiert aus admin_view.py (Schritt 5 Refactoring).
"""

from typing import Optional, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QMessageBox, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont

from api.client import APIClient, APIError
from api.admin import AdminAPI
from i18n import de as texts

from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500,
    FONT_HEADLINE,
    RADIUS_MD,
)
from ui.admin.workers import LoadSessionsWorker


class SessionsPanel(QWidget):
    """Session-Verwaltung: Einsicht, Kill einzeln/alle, Auto-Refresh."""

    def __init__(self, api_client: APIClient, toast_manager,
                 admin_api: AdminAPI, **kwargs):
        super().__init__()
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._admin_api = admin_api
        self._sessions_data = []
        self._active_workers = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode zum Laden der Sessions."""
        self._load_sessions()

    def start_timer(self):
        """Startet den Auto-Refresh-Timer (30s)."""
        self._session_timer.start()

    def stop_timer(self):
        """Stoppt den Auto-Refresh-Timer."""
        self._session_timer.stop()

    # ----------------------------------------------------------------
    # UI
    # ----------------------------------------------------------------

    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Toolbar
        toolbar = QHBoxLayout()

        title = QLabel(texts.ADMIN_SESSIONS_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)

        toolbar.addStretch()

        # Filter: Nutzer
        self._sessions_filter_combo = QComboBox()
        self._sessions_filter_combo.setMinimumWidth(200)
        self._sessions_filter_combo.addItem(texts.ADMIN_SESSIONS_FILTER_ALL, None)
        self._sessions_filter_combo.currentIndexChanged.connect(self._load_sessions)
        toolbar.addWidget(self._sessions_filter_combo)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.setStyleSheet(f"border: 1px solid {PRIMARY_500}; border-radius: {RADIUS_MD}; color: {PRIMARY_500};")
        refresh_btn.clicked.connect(self._load_sessions)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        # Tabelle
        self._sessions_table = QTableWidget()
        self._sessions_table.setColumnCount(6)
        self._sessions_table.setHorizontalHeaderLabels([
            texts.ADMIN_COL_USER, texts.ADMIN_COL_IP, texts.ADMIN_COL_CLIENT,
            texts.ADMIN_COL_LAST_ACTIVE, texts.ADMIN_COL_CREATED, texts.ADMIN_COL_EXPIRES
        ])
        self._sessions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._sessions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._sessions_table.setAlternatingRowColors(True)
        self._sessions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._sessions_table.verticalHeader().setVisible(False)
        layout.addWidget(self._sessions_table)

        # Action-Buttons
        action_bar = QHBoxLayout()

        self._sessions_count_label = QLabel("")
        self._sessions_count_label.setStyleSheet(f"color: {PRIMARY_500};")
        action_bar.addWidget(self._sessions_count_label)
        action_bar.addStretch()

        self._btn_kill_session = QPushButton(texts.ADMIN_SESSIONS_KILL)
        self._btn_kill_session.setStyleSheet("color: #e74c3c;")
        self._btn_kill_session.clicked.connect(self._on_kill_session)
        action_bar.addWidget(self._btn_kill_session)

        self._btn_kill_all = QPushButton(texts.ADMIN_SESSIONS_KILL_ALL)
        self._btn_kill_all.setStyleSheet("color: #e74c3c;")
        self._btn_kill_all.clicked.connect(self._on_kill_all_sessions)
        action_bar.addWidget(self._btn_kill_all)

        layout.addLayout(action_bar)

        # Auto-Refresh Timer
        self._session_timer = QTimer()
        self._session_timer.setInterval(30000)  # 30 Sekunden
        self._session_timer.timeout.connect(self._load_sessions)

    # ----------------------------------------------------------------
    # Data loading
    # ----------------------------------------------------------------

    def _load_sessions(self):
        """Laedt Sessions."""
        user_id = self._sessions_filter_combo.currentData()
        worker = LoadSessionsWorker(self._admin_api, user_id)
        worker.finished.connect(self._on_sessions_loaded)
        worker.error.connect(lambda e: self._toast_manager.show_error(texts.ADMIN_SESSIONS_LOAD_ERROR.format(error=e)) if hasattr(self, '_toast_manager') else None)
        worker.finished.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        worker.error.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        self._active_workers.append(worker)
        worker.start()

    def _on_sessions_loaded(self, sessions: list):
        """Callback wenn Sessions geladen wurden."""
        self._sessions_data = sessions
        self._sessions_table.setRowCount(len(sessions))
        self._sessions_count_label.setText(f"{len(sessions)} Session(s)")

        for row, session in enumerate(sessions):
            self._sessions_table.setItem(row, 0, QTableWidgetItem(session.get('username', '')))
            self._sessions_table.setItem(row, 1, QTableWidgetItem(session.get('ip_address', '')))
            self._sessions_table.setItem(row, 2, QTableWidgetItem(session.get('user_agent_short', '')))

            last_active = session.get('last_activity_at', '-')
            if last_active and last_active != '-':
                last_active = last_active[:19].replace('T', ' ')
            self._sessions_table.setItem(row, 3, QTableWidgetItem(str(last_active)))

            created = session.get('created_at', '-')
            if created and created != '-':
                created = created[:19].replace('T', ' ')
            self._sessions_table.setItem(row, 4, QTableWidgetItem(str(created)))

            expires = session.get('expires_at', '-')
            if expires and expires != '-':
                expires = expires[:19].replace('T', ' ')
            self._sessions_table.setItem(row, 5, QTableWidgetItem(str(expires)))

        # User-Filter aktualisieren (nur einmalig)
        if self._sessions_filter_combo.count() <= 1:
            usernames = sorted(set(s.get('username', '') for s in sessions))
            for username in usernames:
                user_id = next((s.get('user_id') for s in sessions if s.get('username') == username), None)
                if user_id:
                    self._sessions_filter_combo.addItem(username, user_id)

    # ----------------------------------------------------------------
    # Actions
    # ----------------------------------------------------------------

    def _get_selected_session(self) -> Optional[Dict]:
        row = self._sessions_table.currentRow()
        if row < 0 or row >= len(self._sessions_data):
            return None
        return self._sessions_data[row]

    def _on_kill_session(self):
        session = self._get_selected_session()
        if not session:
            return
        reply = QMessageBox.question(self, texts.WARNING, texts.ADMIN_SESSIONS_KILL_CONFIRM,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._admin_api.kill_session(session['id'])
                self._toast_manager.show_success(texts.ADMIN_SESSIONS_KILLED)
                self._load_sessions()
            except APIError as e:
                self._toast_manager.show_error(str(e))

    def _on_kill_all_sessions(self):
        session = self._get_selected_session()
        if not session:
            return
        username = session.get('username', '')
        user_id = session.get('user_id')
        if not user_id:
            return
        reply = QMessageBox.question(self, texts.WARNING, texts.ADMIN_SESSIONS_KILL_ALL_CONFIRM.format(username=username),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._admin_api.kill_user_sessions(user_id)
                self._toast_manager.show_success(texts.ADMIN_SESSIONS_ALL_KILLED.format(count='?'))
                self._load_sessions()
            except APIError as e:
                self._toast_manager.show_error(str(e))
