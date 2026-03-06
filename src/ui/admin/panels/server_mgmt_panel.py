"""
ACENCIA ATLAS - Server-Management Panel (Super-Admin)

Tabs: Verbindungen | Fail2Ban | Firewall | Services | Server
"""

import logging
from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QHeaderView, QAbstractItemView, QMessageBox, QProgressBar,
    QLineEdit, QPlainTextEdit,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from api.client import APIClient, APIError
from api.server_management import ServerManagementAPI
from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_0,
    ACCENT_500, SUCCESS, WARNING, ERROR,
    FONT_HEADLINE, FONT_BODY, FONT_MONO,
    FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
    get_button_primary_style, get_button_secondary_style,
)

logger = logging.getLogger(__name__)


class _ApiWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, func, *args, parent=None):
        super().__init__(parent)
        self._func = func
        self._args = args

    def run(self):
        try:
            result = self._func(*self._args)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ServerMgmtPanel(QWidget):
    """Server-Management mit Tabs (nur fuer super_admin)."""

    def __init__(self, api_client: APIClient, toast_manager=None, **kwargs):
        super().__init__()
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._server_api = ServerManagementAPI(api_client)
        self._workers: list = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(texts.SRVMGMT_TITLE)
        title.setStyleSheet(f"font-family: {FONT_HEADLINE}; font-size: 18pt; color: {PRIMARY_900}; font-weight: 700;")
        layout.addWidget(title)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._conn_tab = self._build_connections_tab()
        self._tabs.addTab(self._conn_tab, texts.SRVMGMT_TAB_CONNECTIONS)

        self._f2b_tab = self._build_fail2ban_tab()
        self._tabs.addTab(self._f2b_tab, texts.SRVMGMT_TAB_FAIL2BAN)

        self._fw_tab = self._build_firewall_tab()
        self._tabs.addTab(self._fw_tab, texts.SRVMGMT_TAB_FIREWALL)

        self._svc_tab = self._build_services_tab()
        self._tabs.addTab(self._svc_tab, texts.SRVMGMT_TAB_SERVICES)

        self._sys_tab = self._build_system_tab()
        self._tabs.addTab(self._sys_tab, texts.SRVMGMT_TAB_SYSTEM)

        self._console_tab = self._build_console_tab()
        self._tabs.addTab(self._console_tab, texts.SRVMGMT_TAB_CONSOLE)

    def load_data(self):
        idx = self._tabs.currentIndex()
        loaders = [
            self._load_connections,
            self._load_fail2ban,
            self._load_firewall,
            self._load_services,
            self._load_system,
        ]
        if 0 <= idx < len(loaders):
            loaders[idx]()

    def _run(self, func, callback, err_msg="Fehler"):
        w = _ApiWorker(func, parent=self)
        w.finished.connect(callback)
        w.error.connect(lambda e: self._toast_manager.show_error(f"{err_msg}: {e}") if self._toast_manager else None)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    # === Connections ===

    def _build_connections_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        refresh = QPushButton(texts.SRVMGMT_REFRESH)
        refresh.clicked.connect(self._load_connections)
        toolbar.addWidget(refresh)
        lay.addLayout(toolbar)

        self._conn_table = QTableWidget()
        self._conn_table.setColumnCount(5)
        self._conn_table.setHorizontalHeaderLabels([
            "Status", "Lokal", "Remote", "Prozess (PID)", ""
        ])
        self._conn_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._conn_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self._conn_table.setColumnWidth(4, 120)
        self._conn_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._conn_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._conn_table.setAlternatingRowColors(True)
        lay.addWidget(self._conn_table)
        return w

    def _load_connections(self):
        self._run(self._server_api.get_connections, self._on_connections_loaded, texts.SRVMGMT_CONN_ERROR)

    def _on_connections_loaded(self, conns):
        if not isinstance(conns, list):
            conns = []
        self._conn_data = conns
        self._conn_table.setRowCount(len(conns))
        for row, c in enumerate(conns):
            self._conn_table.setItem(row, 0, QTableWidgetItem(c.get('state', '')))
            self._conn_table.setItem(row, 1, QTableWidgetItem(c.get('local_addr', '')))
            self._conn_table.setItem(row, 2, QTableWidgetItem(c.get('remote_addr', '')))
            pid = c.get('pid')
            proc = c.get('process', '')
            self._conn_table.setItem(row, 3, QTableWidgetItem(f"{proc} ({pid})" if pid else proc))

            if pid and 'sshd' in proc:
                kill_btn = QPushButton(texts.SRVMGMT_CONN_KILL)
                kill_btn.setStyleSheet(f"color: {ERROR}; font-weight: 600;")
                kill_btn.clicked.connect(lambda _, p=pid: self._kill_connection(p))
                self._conn_table.setCellWidget(row, 4, kill_btn)

    def _kill_connection(self, pid: int):
        reply = QMessageBox.question(
            self, texts.WARNING,
            texts.SRVMGMT_CONN_KILL_CONFIRM.format(pid=pid),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._server_api.kill_connection(pid)
                if self._toast_manager:
                    self._toast_manager.show_success(texts.SRVMGMT_CONN_KILLED.format(pid=pid))
                self._load_connections()
            except APIError as e:
                if self._toast_manager:
                    self._toast_manager.show_error(str(e))

    # === Fail2Ban ===

    def _build_fail2ban_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        refresh = QPushButton(texts.SRVMGMT_REFRESH)
        refresh.clicked.connect(self._load_fail2ban)
        toolbar.addWidget(refresh)
        lay.addLayout(toolbar)

        self._f2b_table = QTableWidget()
        self._f2b_table.setColumnCount(5)
        self._f2b_table.setHorizontalHeaderLabels([
            "Jail", "IP", texts.SRVMGMT_F2B_BANNED, texts.SRVMGMT_F2B_TOTAL, ""
        ])
        self._f2b_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._f2b_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self._f2b_table.setColumnWidth(4, 120)
        self._f2b_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._f2b_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._f2b_table.setAlternatingRowColors(True)
        lay.addWidget(self._f2b_table)
        return w

    def _load_fail2ban(self):
        self._run(self._server_api.get_fail2ban_status, self._on_f2b_loaded, texts.SRVMGMT_F2B_ERROR)

    def _on_f2b_loaded(self, jails):
        if not isinstance(jails, list):
            jails = []
        rows = []
        for jail in jails:
            name = jail.get('name', '')
            banned_ips = jail.get('banned_ips', [])
            total = jail.get('total_banned', 0)
            current = jail.get('currently_banned', 0)
            if banned_ips:
                for bip in banned_ips:
                    rows.append((name, bip.get('ip', ''), current, total, name))
            else:
                rows.append((name, '-', current, total, None))

        self._f2b_table.setRowCount(len(rows))
        for row, (jail_name, ip, current, total, unban_jail) in enumerate(rows):
            self._f2b_table.setItem(row, 0, QTableWidgetItem(jail_name))
            self._f2b_table.setItem(row, 1, QTableWidgetItem(ip))
            self._f2b_table.setItem(row, 2, QTableWidgetItem(str(current)))
            self._f2b_table.setItem(row, 3, QTableWidgetItem(str(total)))
            if unban_jail and ip != '-':
                btn = QPushButton(texts.SRVMGMT_F2B_UNBAN)
                btn.clicked.connect(lambda _, i=ip, j=unban_jail: self._unban_ip(i, j))
                self._f2b_table.setCellWidget(row, 4, btn)

    def _unban_ip(self, ip: str, jail: str):
        try:
            self._server_api.unban_ip(ip, jail)
            if self._toast_manager:
                self._toast_manager.show_success(texts.SRVMGMT_F2B_UNBANNED.format(ip=ip, jail=jail))
            self._load_fail2ban()
        except APIError as e:
            if self._toast_manager:
                self._toast_manager.show_error(str(e))

    # === Firewall ===

    def _build_firewall_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)

        toolbar = QHBoxLayout()
        self._fw_status_label = QLabel()
        toolbar.addWidget(self._fw_status_label)
        toolbar.addStretch()

        reload_btn = QPushButton(texts.SRVMGMT_FW_RELOAD)
        reload_btn.setStyleSheet(f"color: {WARNING}; font-weight: 600;")
        reload_btn.clicked.connect(self._reload_firewall)
        toolbar.addWidget(reload_btn)

        refresh = QPushButton(texts.SRVMGMT_REFRESH)
        refresh.clicked.connect(self._load_firewall)
        toolbar.addWidget(refresh)
        lay.addLayout(toolbar)

        self._fw_table = QTableWidget()
        self._fw_table.setColumnCount(4)
        self._fw_table.setHorizontalHeaderLabels(["#", "Ziel", "Aktion", "Von"])
        self._fw_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._fw_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._fw_table.setAlternatingRowColors(True)
        lay.addWidget(self._fw_table)
        return w

    def _load_firewall(self):
        self._run(self._server_api.get_firewall_status, self._on_fw_loaded, texts.SRVMGMT_FW_ERROR)

    def _on_fw_loaded(self, data):
        if not isinstance(data, dict):
            data = {}
        status = data.get('status', 'unknown')
        self._fw_status_label.setText(f"UFW: {status}")
        self._fw_status_label.setStyleSheet(
            f"font-weight: 700; color: {SUCCESS if status == 'active' else ERROR};"
        )
        rules = data.get('rules', [])
        self._fw_table.setRowCount(len(rules))
        for row, r in enumerate(rules):
            self._fw_table.setItem(row, 0, QTableWidgetItem(str(r.get('number', ''))))
            self._fw_table.setItem(row, 1, QTableWidgetItem(r.get('to', '')))
            self._fw_table.setItem(row, 2, QTableWidgetItem(r.get('action', '')))
            self._fw_table.setItem(row, 3, QTableWidgetItem(r.get('from', '')))

    def _reload_firewall(self):
        reply = QMessageBox.question(
            self, texts.WARNING, texts.SRVMGMT_FW_RELOAD_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._server_api.reload_firewall()
                if self._toast_manager:
                    self._toast_manager.show_success(texts.SRVMGMT_FW_RELOADED)
                self._load_firewall()
            except APIError as e:
                if self._toast_manager:
                    self._toast_manager.show_error(str(e))

    # === Services ===

    def _build_services_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        refresh = QPushButton(texts.SRVMGMT_REFRESH)
        refresh.clicked.connect(self._load_services)
        toolbar.addWidget(refresh)
        lay.addLayout(toolbar)

        self._svc_table = QTableWidget()
        self._svc_table.setColumnCount(4)
        self._svc_table.setHorizontalHeaderLabels([
            "Service", "Status", texts.SRVMGMT_SVC_SINCE, ""
        ])
        self._svc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._svc_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self._svc_table.setColumnWidth(3, 120)
        self._svc_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._svc_table.setAlternatingRowColors(True)
        lay.addWidget(self._svc_table)
        return w

    def _load_services(self):
        self._run(self._server_api.get_services, self._on_svc_loaded, texts.SRVMGMT_SVC_ERROR)

    def _on_svc_loaded(self, services):
        if not isinstance(services, list):
            services = []
        self._svc_table.setRowCount(len(services))
        restartable = ['nginx', 'php8.3-fpm', 'mysql', 'fail2ban', 'ssh']
        for row, s in enumerate(services):
            self._svc_table.setItem(row, 0, QTableWidgetItem(s.get('name', '')))
            status = s.get('status', 'unknown')
            item = QTableWidgetItem(status)
            if status == 'active':
                item.setForeground(QColor(SUCCESS))
            elif status == 'failed':
                item.setForeground(QColor(ERROR))
            else:
                item.setForeground(QColor(WARNING))
            self._svc_table.setItem(row, 1, item)
            self._svc_table.setItem(row, 2, QTableWidgetItem(s.get('active_since', '-') or '-'))

            if s.get('name') in restartable:
                btn = QPushButton(texts.SRVMGMT_SVC_RESTART)
                btn.clicked.connect(lambda _, name=s['name']: self._restart_service(name))
                self._svc_table.setCellWidget(row, 3, btn)

    def _restart_service(self, name: str):
        reply = QMessageBox.question(
            self, texts.WARNING,
            texts.SRVMGMT_SVC_RESTART_CONFIRM.format(service=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._server_api.restart_service(name)
                if self._toast_manager:
                    self._toast_manager.show_success(texts.SRVMGMT_SVC_RESTARTED.format(service=name))
                self._load_services()
            except APIError as e:
                if self._toast_manager:
                    self._toast_manager.show_error(str(e))

    # === System ===

    def _build_system_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.addStretch()

        reboot_btn = QPushButton(texts.SRVMGMT_REBOOT)
        reboot_btn.setStyleSheet(f"background: {ERROR}; color: white; font-weight: 700; border: none; border-radius: {RADIUS_MD}; padding: 8px 20px;")
        reboot_btn.clicked.connect(self._reboot_server)
        toolbar.addWidget(reboot_btn)

        refresh = QPushButton(texts.SRVMGMT_REFRESH)
        refresh.clicked.connect(self._load_system)
        toolbar.addWidget(refresh)
        lay.addLayout(toolbar)

        self._sys_info_label = QLabel()
        self._sys_info_label.setStyleSheet(f"font-family: {FONT_MONO}; font-size: {FONT_SIZE_BODY}; padding: 12px; background: {PRIMARY_0}; border-radius: {RADIUS_MD};")
        self._sys_info_label.setWordWrap(True)
        self._sys_info_label.setTextFormat(Qt.RichText)
        lay.addWidget(self._sys_info_label)
        lay.addStretch()
        return w

    def _load_system(self):
        self._run(self._server_api.get_system_info, self._on_sys_loaded, texts.SRVMGMT_SYS_ERROR)

    def _on_sys_loaded(self, data):
        if not isinstance(data, dict):
            data = {}
        cpu = data.get('cpu', {})
        mem = data.get('memory', {})
        disk = data.get('disk', {})
        uptime = data.get('uptime', {})

        html = f"""
        <b>Uptime:</b> {uptime.get('human', '-')}<br><br>
        <b>CPU:</b> {cpu.get('usage_percent', 0)}% (Load: {cpu.get('load_1m', 0)} / {cpu.get('load_5m', 0)} / {cpu.get('load_15m', 0)}, {cpu.get('cores', 0)} Kerne)<br>
        <b>RAM:</b> {mem.get('used_mb', 0)} / {mem.get('total_mb', 0)} MB ({mem.get('usage_percent', 0)}%)<br>
        <b>Disk:</b> {disk.get('used_gb', 0)} / {disk.get('total_gb', 0)} GB ({disk.get('usage_percent', 0)}%)
        """
        self._sys_info_label.setText(html)

    # === Console ===

    def _build_console_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)

        warn = QLabel(texts.SRVMGMT_CONSOLE_WARNING)
        warn.setStyleSheet(f"color: {ERROR}; font-weight: 700; padding: 8px 0;")
        warn.setWordWrap(True)
        lay.addWidget(warn)

        self._console_output = QPlainTextEdit()
        self._console_output.setReadOnly(True)
        self._console_output.setStyleSheet(f"""
            QPlainTextEdit {{
                background: #0d1117; color: #c9d1d9;
                font-family: {FONT_MONO}; font-size: 13px;
                border: 1px solid #30363d; border-radius: {RADIUS_MD};
                padding: 12px;
            }}
        """)
        self._console_output.setPlainText("root@atlas:~# ")
        lay.addWidget(self._console_output, stretch=1)

        input_row = QHBoxLayout()
        prompt = QLabel("root@atlas:~#")
        prompt.setStyleSheet(f"font-family: {FONT_MONO}; font-weight: 700; color: {SUCCESS};")
        input_row.addWidget(prompt)

        self._console_input = QLineEdit()
        self._console_input.setStyleSheet(f"""
            QLineEdit {{
                background: #0d1117; color: #c9d1d9;
                font-family: {FONT_MONO}; font-size: 13px;
                border: 1px solid #30363d; border-radius: {RADIUS_MD};
                padding: 8px;
            }}
        """)
        self._console_input.setPlaceholderText(texts.SRVMGMT_CONSOLE_PLACEHOLDER)
        self._console_input.returnPressed.connect(self._exec_command)
        input_row.addWidget(self._console_input, stretch=1)

        exec_btn = QPushButton(texts.SRVMGMT_CONSOLE_EXEC)
        exec_btn.setStyleSheet(f"background: {ACCENT_500}; color: white; font-weight: 700; border: none; border-radius: {RADIUS_MD}; padding: 8px 16px;")
        exec_btn.clicked.connect(self._exec_command)
        input_row.addWidget(exec_btn)

        lay.addLayout(input_row)
        return w

    def _exec_command(self):
        cmd = self._console_input.text().strip()
        if not cmd:
            return
        self._console_input.clear()
        self._console_output.appendPlainText(f"$ {cmd}")
        self._console_input.setEnabled(False)

        def on_result(data):
            if isinstance(data, dict):
                output = data.get('output', '')
                duration = data.get('duration_ms', 0)
                if output:
                    self._console_output.appendPlainText(output)
                self._console_output.appendPlainText(f"[{duration}ms]\nroot@atlas:~# ")
            else:
                self._console_output.appendPlainText(str(data))
                self._console_output.appendPlainText("root@atlas:~# ")
            self._console_input.setEnabled(True)
            self._console_input.setFocus()

        def on_error(err):
            self._console_output.appendPlainText(f"FEHLER: {err}")
            self._console_output.appendPlainText("root@atlas:~# ")
            self._console_input.setEnabled(True)
            self._console_input.setFocus()

        w = _ApiWorker(self._server_api.exec_command, cmd, parent=self)
        w.finished.connect(on_result)
        w.error.connect(on_error)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _reboot_server(self):
        reply = QMessageBox.warning(
            self, texts.SRVMGMT_REBOOT,
            texts.SRVMGMT_REBOOT_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            reply2 = QMessageBox.critical(
                self, texts.SRVMGMT_REBOOT,
                texts.SRVMGMT_REBOOT_CONFIRM_2,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply2 == QMessageBox.StandardButton.Yes:
                try:
                    self._server_api.reboot_server()
                    if self._toast_manager:
                        self._toast_manager.show_success(texts.SRVMGMT_REBOOTING)
                except APIError as e:
                    if self._toast_manager:
                        self._toast_manager.show_error(str(e))
