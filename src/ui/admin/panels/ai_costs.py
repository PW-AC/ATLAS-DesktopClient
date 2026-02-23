"""
ACENCIA ATLAS - KI-Kosten Panel

Standalone QWidget fuer KI-Kosten-Tracking im Admin-Bereich.
Extrahiert aus admin_view.py (Schritt 5 Refactoring).
"""

import logging
from typing import Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QFrame, QFileDialog,
    QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from api.client import APIClient
from api.model_pricing import ModelPricingAPI
from i18n import de as texts

from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100,
    ACCENT_500, ACCENT_100,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
    get_button_secondary_style,
)
from ui.admin.workers import LoadCostDataWorker, AdminWriteWorker

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    'success': '#27ae60',
    'error': '#e74c3c',
    'denied': '#f39c12',
}


class AiCostsPanel(QWidget):
    """KI-Kosten: Statistiken, Verarbeitungshistorie, Request-Details, CSV-Export."""

    def __init__(self, api_client: APIClient, toast_manager,
                 model_pricing_api: ModelPricingAPI, **kwargs):
        super().__init__()
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._model_pricing_api = model_pricing_api
        self._active_workers = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode zum Laden der Kosten-Daten."""
        self._load_cost_data()

    # ----------------------------------------------------------------
    # UI
    # ----------------------------------------------------------------

    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --- Header mit Titel und Aktionen ---
        header_layout = QHBoxLayout()

        title = QLabel(texts.COSTS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900};
            font-weight: bold;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Zeitraum-Filter
        period_label = QLabel(texts.COSTS_PERIOD_LABEL)
        period_label.setStyleSheet(f"font-family: {FONT_BODY}; color: {PRIMARY_500};")
        header_layout.addWidget(period_label)

        self._costs_period_combo = QComboBox()
        self._costs_period_combo.addItem(texts.COSTS_PERIOD_ALL, "all")
        self._costs_period_combo.addItem(texts.COSTS_PERIOD_7D, "7d")
        self._costs_period_combo.addItem(texts.COSTS_PERIOD_30D, "30d")
        self._costs_period_combo.addItem(texts.COSTS_PERIOD_90D, "90d")
        self._costs_period_combo.setCurrentIndex(0)
        self._costs_period_combo.currentIndexChanged.connect(self._load_cost_data)
        self._costs_period_combo.setStyleSheet(f"font-family: {FONT_BODY};")
        header_layout.addWidget(self._costs_period_combo)

        # Aktualisieren-Button
        refresh_btn = QPushButton(texts.COSTS_REFRESH)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px;
                font-family: {FONT_BODY};
                background-color: {ACCENT_100};
                color: {PRIMARY_900};
                border: 1px solid {ACCENT_500};
                border-radius: {RADIUS_MD};
            }}
            QPushButton:hover {{
                background-color: {ACCENT_500};
                color: white;
            }}
        """)
        refresh_btn.clicked.connect(self._load_cost_data)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # --- Statistik-Karten ---
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_100};
                border: 1px solid {ACCENT_100};
                border-radius: {RADIUS_MD};
                padding: 16px;
            }}
        """)
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(24)

        # Statistik-Labels erstellen
        self._stat_labels = {}
        stat_items = [
            ('runs', texts.COSTS_TOTAL_RUNS, '0'),
            ('docs', texts.COSTS_TOTAL_DOCS, '0'),
            ('cost', texts.COSTS_TOTAL_COST, '$0.00'),
            ('avg_doc', texts.COSTS_AVG_COST_PER_DOC, '$0.00'),
            ('avg_run', texts.COSTS_AVG_COST_PER_RUN, '$0.00'),
            ('duration', texts.COSTS_TOTAL_DURATION, '0s'),
            ('rate', texts.COSTS_SUCCESS_RATE, '0%'),
        ]

        for key, label_text, default_val in stat_items:
            stat_widget = QVBoxLayout()

            value_label = QLabel(default_val)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet(f"""
                font-family: {FONT_HEADLINE};
                font-size: 18px;
                color: {PRIMARY_900};
                font-weight: bold;
                background: transparent;
                border: none;
            """)

            desc_label = QLabel(label_text)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setStyleSheet(f"""
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                color: {PRIMARY_500};
                background: transparent;
                border: none;
            """)

            stat_widget.addWidget(value_label)
            stat_widget.addWidget(desc_label)
            stats_layout.addLayout(stat_widget)

            self._stat_labels[key] = value_label

        layout.addWidget(stats_frame)

        # --- Historie-Tabelle ---
        history_label = QLabel(texts.COSTS_HISTORY_TITLE)
        history_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14px;
            color: {PRIMARY_900};
            font-weight: bold;
        """)
        layout.addWidget(history_label)

        self._costs_table = QTableWidget()
        self._costs_table.setColumnCount(8)
        self._costs_table.setHorizontalHeaderLabels([
            texts.COSTS_COL_DATE,
            texts.COSTS_COL_TOTAL_COST,
            texts.COSTS_COL_COST_PER_DOC,
            texts.COSTS_COL_DOC_COUNT,
            texts.COSTS_COL_SUCCESS,
            texts.COSTS_COL_FAILED,
            texts.COSTS_COL_DURATION,
            texts.COSTS_COL_USER,
        ])

        self._costs_table.setAlternatingRowColors(True)
        self._costs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._costs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._costs_table.verticalHeader().setVisible(False)
        self._costs_table.setStyleSheet(f"""
            QTableWidget {{
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                background-color: white;
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                gridline-color: {PRIMARY_100};
            }}
            QTableWidget::item {{
                padding: 6px 10px;
            }}
            QTableWidget::item:alternate {{
                background-color: #FAFAFA;
            }}
            QHeaderView::section {{
                background-color: {PRIMARY_100};
                color: {PRIMARY_900};
                font-weight: bold;
                padding: 8px 10px;
                border: none;
                border-bottom: 2px solid {ACCENT_500};
            }}
        """)

        header = self._costs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Datum
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)             # Kosten
        header.resizeSection(1, 80)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)             # $/Dok
        header.resizeSection(2, 95)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)             # Doks
        header.resizeSection(3, 55)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)             # OK
        header.resizeSection(4, 45)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)             # Fehler
        header.resizeSection(5, 65)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)             # Dauer
        header.resizeSection(6, 60)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)           # Nutzer

        layout.addWidget(self._costs_table, stretch=1)

        # Status-Label
        self._costs_status = QLabel("")
        self._costs_status.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
        """)
        layout.addWidget(self._costs_status)

        # --- Einzelne Requests (NEU) ---
        requests_header = QHBoxLayout()
        requests_label = QLabel(texts.AI_COSTS_REQUESTS_TITLE)
        requests_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14px;
            color: {PRIMARY_900};
            font-weight: bold;
        """)
        requests_header.addWidget(requests_label)
        requests_header.addStretch()

        export_btn = QPushButton(texts.AI_COSTS_REQUESTS_EXPORT)
        export_btn.setStyleSheet(get_button_secondary_style())
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self._export_ai_requests_csv)
        requests_header.addWidget(export_btn)
        layout.addLayout(requests_header)

        self._ai_requests_table = QTableWidget()
        self._ai_requests_table.setColumnCount(8)
        self._ai_requests_table.setHorizontalHeaderLabels([
            texts.AI_COSTS_REQUESTS_TIME, texts.AI_COSTS_REQUESTS_USER,
            texts.AI_COSTS_REQUESTS_PROVIDER, texts.AI_COSTS_REQUESTS_MODEL,
            texts.AI_COSTS_REQUESTS_PROMPT_TOKENS, texts.AI_COSTS_REQUESTS_COMPLETION_TOKENS,
            texts.AI_COSTS_REQUESTS_ESTIMATED, texts.AI_COSTS_REQUESTS_COST
        ])
        self._ai_requests_table.setAlternatingRowColors(True)
        self._ai_requests_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._ai_requests_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._ai_requests_table.verticalHeader().setVisible(False)
        self._ai_requests_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._ai_requests_table.setColumnWidth(0, 130)   # Zeit
        self._ai_requests_table.setColumnWidth(4, 110)   # Prompt Tokens
        self._ai_requests_table.setColumnWidth(5, 130)   # Completion Tokens
        self._ai_requests_table.setColumnWidth(6, 110)   # Geschaetzt
        self._ai_requests_table.setColumnWidth(7, 110)   # Echte Kosten
        layout.addWidget(self._ai_requests_table, stretch=1)

        self._ai_requests_status = QLabel("")
        self._ai_requests_status.setStyleSheet(f"font-size: {FONT_SIZE_CAPTION}; color: {PRIMARY_500};")
        layout.addWidget(self._ai_requests_status)

    # ----------------------------------------------------------------
    # Data loading
    # ----------------------------------------------------------------

    def _load_cost_data(self):
        """Laedt Kosten-Daten basierend auf dem Zeitraum-Filter."""
        from datetime import datetime, timedelta

        self._costs_status.setText(texts.LOADING)

        # Zeitraum bestimmen
        period = self._costs_period_combo.currentData()
        from_date = None
        to_date = None

        if period == '7d':
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        elif period == '30d':
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        elif period == '90d':
            from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        # 'all' -> kein Filter

        self._cost_worker = LoadCostDataWorker(
            self._api_client, from_date, to_date
        )
        self._cost_worker.finished.connect(self._on_cost_data_loaded)
        self._cost_worker.error.connect(self._on_cost_data_error)
        self._active_workers.append(self._cost_worker)
        self._cost_worker.start()

    def _on_cost_data_loaded(self, result: Dict):
        """Callback wenn Kosten-Daten geladen."""
        history = result.get('history', [])
        stats = result.get('stats', {})

        # Statistik-Karten aktualisieren
        self._update_cost_stats(stats)

        # Tabelle befuellen
        self._populate_cost_table(history)

        count = len(history)
        if count == 0:
            self._costs_status.setText(texts.COSTS_NO_DATA)
        else:
            self._costs_status.setText(f"{count} Verarbeitungslauf/-laeufe")

        # Einzelne Requests laden
        self._load_ai_requests()

    def _on_cost_data_error(self, error: str):
        """Callback bei Kosten-Daten Fehler."""
        self._costs_status.setText(texts.COSTS_LOAD_ERROR.format(error=error))
        logger.error(f"Kosten-Daten Fehler: {error}")

    def _update_cost_stats(self, stats: Dict):
        """Aktualisiert die Statistik-Karten."""
        if not stats:
            return

        self._stat_labels['runs'].setText(str(stats.get('total_runs', 0)))
        self._stat_labels['docs'].setText(str(stats.get('total_documents', 0)))

        total_cost = stats.get('total_cost_usd', 0)
        self._stat_labels['cost'].setText(f"${total_cost:.4f}")

        avg_doc = stats.get('avg_cost_per_document_usd', 0)
        self._stat_labels['avg_doc'].setText(f"${avg_doc:.6f}")

        avg_run = stats.get('avg_cost_per_run_usd', 0)
        self._stat_labels['avg_run'].setText(f"${avg_run:.4f}")

        duration_s = stats.get('total_duration_seconds', 0)
        if duration_s >= 60:
            minutes = int(duration_s // 60)
            seconds = int(duration_s % 60)
            self._stat_labels['duration'].setText(f"{minutes}m {seconds}s")
        else:
            self._stat_labels['duration'].setText(f"{duration_s:.1f}s")

        rate = stats.get('success_rate_percent', 0)
        self._stat_labels['rate'].setText(f"{rate:.1f}%")

        # Farbkodierung fuer Erfolgsrate
        if rate >= 95:
            color = STATUS_COLORS['success']
        elif rate >= 80:
            color = STATUS_COLORS['denied']
        else:
            color = STATUS_COLORS['error']

        self._stat_labels['rate'].setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 18px;
            color: {color};
            font-weight: bold;
            background: transparent;
            border: none;
        """)

    def _populate_cost_table(self, history: list):
        """Befuellt die Kosten-Tabelle."""
        self._costs_table.setRowCount(0)
        self._costs_table.setSortingEnabled(False)

        for entry in history:
            row = self._costs_table.rowCount()
            self._costs_table.insertRow(row)

            # Datum formatieren (YYYY-MM-DD HH:MM:SS -> DD.MM.YYYY HH:MM)
            date_str = entry.get('date', '')
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00') if 'Z' in date_str else date_str)
                formatted_date = dt.strftime('%d.%m.%Y %H:%M')
            except (ValueError, TypeError):
                formatted_date = date_str[:16] if date_str else '-'

            # Datum
            date_item = QTableWidgetItem(formatted_date)
            date_item.setData(Qt.ItemDataRole.UserRole, date_str)  # Fuer Sortierung
            self._costs_table.setItem(row, 0, date_item)

            # Gesamtkosten
            total_cost = entry.get('total_cost_usd', 0)
            cost_item = QTableWidgetItem(f"${total_cost:.4f}")
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cost_item.setData(Qt.ItemDataRole.UserRole, total_cost)
            self._costs_table.setItem(row, 1, cost_item)

            # Kosten pro Dokument
            cost_per_doc = entry.get('cost_per_document_usd', 0)
            cpd_item = QTableWidgetItem(f"${cost_per_doc:.6f}")
            cpd_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cpd_item.setData(Qt.ItemDataRole.UserRole, cost_per_doc)
            self._costs_table.setItem(row, 2, cpd_item)

            # Dokumente
            total_docs = entry.get('total_documents', 0)
            docs_item = QTableWidgetItem(str(total_docs))
            docs_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            docs_item.setData(Qt.ItemDataRole.UserRole, total_docs)
            self._costs_table.setItem(row, 3, docs_item)

            # Erfolgreich
            success = entry.get('successful_documents', 0)
            success_item = QTableWidgetItem(str(success))
            success_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            success_item.setForeground(QColor(STATUS_COLORS['success']))
            self._costs_table.setItem(row, 4, success_item)

            # Fehlgeschlagen
            failed = entry.get('failed_documents', 0)
            failed_item = QTableWidgetItem(str(failed))
            failed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if failed > 0:
                failed_item.setForeground(QColor(STATUS_COLORS['error']))
            self._costs_table.setItem(row, 5, failed_item)

            # Dauer
            duration_s = entry.get('duration_seconds', 0)
            if duration_s >= 60:
                minutes = int(duration_s // 60)
                seconds = int(duration_s % 60)
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{duration_s:.1f}s"
            duration_item = QTableWidgetItem(duration_str)
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            duration_item.setData(Qt.ItemDataRole.UserRole, duration_s)
            self._costs_table.setItem(row, 6, duration_item)

            # User
            user = entry.get('user', '-')
            self._costs_table.setItem(row, 7, QTableWidgetItem(user))

        self._costs_table.setSortingEnabled(True)

    # ----------------------------------------------------------------
    # AI Requests
    # ----------------------------------------------------------------

    def _load_ai_requests(self):
        """Laedt die einzelnen KI-Requests."""
        period = self._costs_period_combo.currentData() or 'all'

        def _do_load():
            return self._model_pricing_api.get_ai_requests(limit=200, period=period)

        worker = AdminWriteWorker(_do_load)
        worker.finished.connect(self._on_ai_requests_loaded)
        worker.error.connect(lambda e: (
            self._ai_requests_status.setText(texts.AI_COSTS_REQUESTS_LOAD_ERROR),
            logger.error(f"AI-Requests laden: {e}")
        ))
        self._active_workers.append(worker)
        worker.start()

    def _on_ai_requests_loaded(self, result):
        """Befuellt die AI-Requests Tabelle."""
        if not result:
            return
        requests = result if isinstance(result, list) else result.get('requests', [])
        table = self._ai_requests_table
        table.setRowCount(len(requests))

        for row, req in enumerate(requests):
            # Zeit
            created = req.get('created_at', '')
            try:
                from datetime import datetime as dt_cls
                dt = dt_cls.fromisoformat(created.replace('Z', '+00:00') if 'Z' in created else created)
                time_str = dt.strftime('%d.%m. %H:%M:%S')
            except (ValueError, TypeError):
                time_str = created[:19] if created else '-'
            table.setItem(row, 0, QTableWidgetItem(time_str))

            # User
            table.setItem(row, 1, QTableWidgetItem(req.get('username', '-')))

            # Provider
            table.setItem(row, 2, QTableWidgetItem(req.get('provider', '-')))

            # Modell
            table.setItem(row, 3, QTableWidgetItem(req.get('model', '-')))

            # Prompt Tokens
            pt = QTableWidgetItem(str(req.get('prompt_tokens', 0)))
            pt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 4, pt)

            # Completion Tokens
            ct = QTableWidgetItem(str(req.get('completion_tokens', 0)))
            ct.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 5, ct)

            # Geschaetzte Kosten
            est = req.get('estimated_cost_usd')
            est_str = f"${float(est):.6f}" if est is not None else "-"
            est_item = QTableWidgetItem(est_str)
            est_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 6, est_item)

            # Echte Kosten
            real = float(req.get('real_cost_usd', 0))
            real_item = QTableWidgetItem(f"${real:.6f}")
            real_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 7, real_item)

        total_count = len(requests)
        total_cost = sum(float(r.get('real_cost_usd', 0)) for r in requests)
        self._ai_requests_status.setText(
            texts.AI_COSTS_REQUESTS_TOTAL.format(count=total_count, cost=f"{total_cost:.4f}")
        )

    def _export_ai_requests_csv(self):
        """Exportiert die AI-Requests als CSV."""
        from ui.toast import ToastManager
        path, _ = QFileDialog.getSaveFileName(
            self, texts.AI_COSTS_REQUESTS_EXPORT, "ai_requests.csv", "CSV (*.csv)"
        )
        if not path:
            return

        try:
            table = self._ai_requests_table
            with open(path, 'w', encoding='utf-8-sig') as f:
                headers = []
                for col in range(table.columnCount()):
                    headers.append(table.horizontalHeaderItem(col).text())
                f.write(';'.join(headers) + '\n')

                for row in range(table.rowCount()):
                    cells = []
                    for col in range(table.columnCount()):
                        item = table.item(row, col)
                        cells.append(item.text() if item else '')
                    f.write(';'.join(cells) + '\n')

            ToastManager.instance().show_success(f"CSV exportiert: {path}")
        except Exception as e:
            ToastManager.instance().show_error(f"Export fehlgeschlagen: {e}")
