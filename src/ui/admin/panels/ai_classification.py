"""
ACENCIA ATLAS - Admin Panel: KI-Klassifikation

Extrahiert aus admin_view.py (Zeilen 3234-3839).
"""

from typing import List, Dict

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QPushButton, QFrame, QScrollArea, QSpinBox, QPlainTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from api.client import APIClient
from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100, SUCCESS, TEXT_SECONDARY,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD, RADIUS_SM,
    get_button_primary_style, get_button_secondary_style,
)
from ui.admin.workers import AdminWriteWorker

SPACING_SM = 8
SPACING_MD = 16

logger = logging.getLogger(__name__)

# STATUS_COLORS used for s2_disabled_info
STATUS_COLORS = {
    'success': '#27ae60',
    'error': '#e74c3c',
    'denied': '#f39c12',
}


class AiClassificationPanel(QWidget):
    """Admin-Panel fuer KI-Klassifikation (Pipeline + Prompt-Editor)."""

    def __init__(self, api_client: APIClient, toast_manager,
                 processing_settings_api, ai_providers_api, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._processing_settings_api = processing_settings_api
        self._ai_providers_api = ai_providers_api
        self._active_workers: list = []
        self._current_ai_settings = None
        self._ai_s1_versions: List[Dict] = []
        self._ai_s2_versions: List[Dict] = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode zum Laden der Daten."""
        self._load_ai_classification_settings()

    def _create_ui(self):
        """Erstellt das KI-Klassifikation Panel mit Pipeline-Visualisierung + Prompt-Editor."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(SPACING_MD)

        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel(texts.PROCESSING_AI_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._btn_ai_save = QPushButton(texts.PROCESSING_AI_SAVE)
        self._btn_ai_save.setStyleSheet(get_button_primary_style())
        self._btn_ai_save.setCursor(Qt.PointingHandCursor)
        self._btn_ai_save.clicked.connect(self._save_ai_classification_settings)
        toolbar.addWidget(self._btn_ai_save)

        layout.addLayout(toolbar)

        subtitle = QLabel(texts.PROCESSING_AI_SUBTITLE)
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Provider-Info-Banner
        self._ai_provider_banner = QLabel(texts.AI_CLASSIFICATION_NO_PROVIDER)
        self._ai_provider_banner.setWordWrap(True)
        self._ai_provider_banner.setStyleSheet(f"""
            QLabel {{
                background-color: {ACCENT_100};
                border: 1px solid {ACCENT_500};
                border-radius: {RADIUS_SM};
                padding: 8px 12px;
                color: {PRIMARY_900};
                font-size: {FONT_SIZE_BODY};
            }}
        """)
        layout.addWidget(self._ai_provider_banner)

        # Scrollbarer Inhalt
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(SPACING_MD)

        # ---- Bereich A: Statische Pipeline-Visualisierung ----
        pipeline_group = QFrame()
        pipeline_group.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 16px;
            }}
        """)
        pipeline_layout = QVBoxLayout(pipeline_group)
        pipeline_layout.setSpacing(SPACING_SM)

        pipeline_title = QLabel(texts.PROCESSING_AI_PIPELINE_TITLE)
        pipeline_title.setFont(QFont(FONT_HEADLINE, 14))
        pipeline_title.setStyleSheet(f"color: {PRIMARY_900}; background: transparent;")
        pipeline_layout.addWidget(pipeline_title)

        # Pipeline-Schritte als Flow-Karten
        steps = [
            (texts.PROCESSING_AI_STEP_XML, texts.PROCESSING_AI_STEP_XML_DESC, "Roh-Archiv"),
            (texts.PROCESSING_AI_STEP_GDV_BIPRO, texts.PROCESSING_AI_STEP_GDV_BIPRO_DESC, "GDV-Box"),
            (texts.PROCESSING_AI_STEP_GDV_EXT, texts.PROCESSING_AI_STEP_GDV_EXT_DESC, "GDV-Box"),
            (texts.PROCESSING_AI_STEP_PDF_VALIDATE, texts.PROCESSING_AI_STEP_PDF_VALIDATE_DESC, None),
            (texts.PROCESSING_AI_STEP_COURTAGE, texts.PROCESSING_AI_STEP_COURTAGE_DESC, "Courtage-Box"),
        ]

        for step_title, step_desc, target in steps:
            step_frame = QFrame()
            step_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {PRIMARY_0};
                    border: 1px solid {PRIMARY_500};
                    border-radius: {RADIUS_SM};
                    padding: 8px 12px;
                }}
            """)
            step_row = QHBoxLayout(step_frame)
            step_row.setContentsMargins(8, 4, 8, 4)

            step_lbl = QLabel(f"<b>{step_title}</b>")
            step_lbl.setStyleSheet(f"color: {PRIMARY_900}; background: transparent; border: none;")
            step_row.addWidget(step_lbl)

            desc_lbl = QLabel(step_desc)
            desc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent; border: none;")
            step_row.addWidget(desc_lbl)
            step_row.addStretch()

            if target:
                target_lbl = QLabel(f"→ {target}")
                target_lbl.setStyleSheet(f"color: {ACCENT_500}; font-weight: bold; background: transparent; border: none;")
                step_row.addWidget(target_lbl)

            pipeline_layout.addWidget(step_frame)

        # Uebergangs-Pfeil
        transition = QLabel(f"▼  {texts.PROCESSING_AI_STEP_KI_TRANSITION} → {texts.PROCESSING_AI_ARROW_LABEL}")
        transition.setAlignment(Qt.AlignCenter)
        transition.setStyleSheet(f"color: {ACCENT_500}; font-size: 14px; font-weight: bold; padding: 8px; background: transparent;")
        pipeline_layout.addWidget(transition)

        scroll_layout.addWidget(pipeline_group)

        # ---- Bereich B: Stufe 1 ----
        stage1_group = QFrame()
        stage1_group.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_0};
                border: 2px solid {ACCENT_500};
                border-radius: {RADIUS_MD};
                padding: 16px;
            }}
        """)
        stage1_layout = QVBoxLayout(stage1_group)
        stage1_layout.setSpacing(SPACING_SM)

        s1_header = QHBoxLayout()
        s1_title = QLabel(texts.PROCESSING_AI_STAGE1_TITLE)
        s1_title.setFont(QFont(FONT_HEADLINE, 14))
        s1_title.setStyleSheet(f"color: {PRIMARY_900}; border: none;")
        s1_header.addWidget(s1_title)
        s1_header.addStretch()
        s1_badge = QLabel(texts.PROCESSING_AI_STAGE1_ALWAYS_ACTIVE)
        s1_badge.setStyleSheet(f"color: {SUCCESS}; font-size: {FONT_SIZE_CAPTION}; border: none;")
        s1_header.addWidget(s1_badge)
        stage1_layout.addLayout(s1_header)

        s1_desc = QLabel(texts.PROCESSING_AI_STAGE1_DESC)
        s1_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; border: none;")
        stage1_layout.addWidget(s1_desc)

        # Model + Max Tokens
        s1_row = QHBoxLayout()
        s1_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_MODEL))
        self._ai_s1_model = QComboBox()
        self._ai_s1_model.setMinimumWidth(250)
        self._ai_s1_model.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        s1_row.addWidget(self._ai_s1_model)
        s1_row.addSpacing(20)
        s1_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_MAX_TOKENS))
        self._ai_s1_max_tokens = QSpinBox()
        self._ai_s1_max_tokens.setRange(50, 4096)
        self._ai_s1_max_tokens.setValue(150)
        self._ai_s1_max_tokens.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        s1_row.addWidget(self._ai_s1_max_tokens)
        s1_row.addStretch()
        stage1_layout.addLayout(s1_row)

        # Version Dropdown + Save As
        s1_version_row = QHBoxLayout()
        s1_version_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_VERSION))
        self._ai_s1_version = QComboBox()
        self._ai_s1_version.setMinimumWidth(300)
        self._ai_s1_version.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        self._ai_s1_version.currentIndexChanged.connect(self._on_s1_version_changed)
        s1_version_row.addWidget(self._ai_s1_version)
        self._btn_s1_save_version = QPushButton(texts.PROCESSING_AI_VERSION_SAVE_AS)
        self._btn_s1_save_version.setStyleSheet(get_button_secondary_style())
        self._btn_s1_save_version.setCursor(Qt.PointingHandCursor)
        self._btn_s1_save_version.clicked.connect(lambda: self._save_prompt_version('stage1'))
        s1_version_row.addWidget(self._btn_s1_save_version)
        s1_version_row.addStretch()
        stage1_layout.addLayout(s1_version_row)

        # Prompt Editor
        prompt_label = QLabel(texts.PROCESSING_AI_STAGE_PROMPT)
        prompt_label.setStyleSheet("border: none;")
        stage1_layout.addWidget(prompt_label)
        self._ai_s1_prompt = QPlainTextEdit()
        self._ai_s1_prompt.setMinimumHeight(200)
        self._ai_s1_prompt.setMaximumHeight(400)
        self._ai_s1_prompt.setFont(QFont("Consolas", 10))
        self._ai_s1_prompt.setStyleSheet(f"border: 1px solid #ccc; border-radius: {RADIUS_SM}; padding: 8px;")
        stage1_layout.addWidget(self._ai_s1_prompt)

        scroll_layout.addWidget(stage1_group)

        # ---- Uebergang: Confidence -> Stufe 2 ----
        transition2 = QLabel(f"▼  {texts.PROCESSING_AI_TRANSITION_LABEL.format(trigger='low')}")
        transition2.setAlignment(Qt.AlignCenter)
        transition2.setStyleSheet(f"color: {ACCENT_500}; font-size: 14px; font-weight: bold; padding: 8px;")
        self._ai_transition_label = transition2
        scroll_layout.addWidget(transition2)

        # ---- Bereich C: Stufe 2 ----
        stage2_group = QFrame()
        stage2_group.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_0};
                border: 2px solid {PRIMARY_500};
                border-radius: {RADIUS_MD};
                padding: 16px;
            }}
        """)
        self._ai_stage2_group = stage2_group
        stage2_layout = QVBoxLayout(stage2_group)
        stage2_layout.setSpacing(SPACING_SM)

        s2_header = QHBoxLayout()
        s2_title = QLabel(texts.PROCESSING_AI_STAGE2_TITLE)
        s2_title.setFont(QFont(FONT_HEADLINE, 14))
        s2_title.setStyleSheet(f"color: {PRIMARY_900}; border: none;")
        s2_header.addWidget(s2_title)
        s2_header.addStretch()
        self._ai_s2_enabled = QCheckBox(texts.PROCESSING_AI_STAGE2_ENABLED)
        self._ai_s2_enabled.setChecked(True)
        self._ai_s2_enabled.setStyleSheet("border: none;")
        self._ai_s2_enabled.toggled.connect(self._on_s2_enabled_toggled)
        s2_header.addWidget(self._ai_s2_enabled)
        stage2_layout.addLayout(s2_header)

        s2_desc = QLabel(texts.PROCESSING_AI_STAGE2_DESC)
        s2_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; border: none;")
        stage2_layout.addWidget(s2_desc)

        # Disabled-Info (nur sichtbar wenn deaktiviert)
        self._ai_s2_disabled_info = QLabel(texts.PROCESSING_AI_STAGE2_DISABLED_INFO)
        self._ai_s2_disabled_info.setStyleSheet(f"color: {STATUS_COLORS['denied']}; font-style: italic; padding: 8px; border: none;")
        self._ai_s2_disabled_info.setWordWrap(True)
        self._ai_s2_disabled_info.setVisible(False)
        stage2_layout.addWidget(self._ai_s2_disabled_info)

        # Container fuer editierbare Felder (ein/ausblendbar)
        self._ai_s2_fields = QWidget()
        s2_fields_layout = QVBoxLayout(self._ai_s2_fields)
        s2_fields_layout.setContentsMargins(0, 0, 0, 0)
        s2_fields_layout.setSpacing(SPACING_SM)

        # Trigger
        s2_trigger_row = QHBoxLayout()
        s2_trigger_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE2_TRIGGER))
        self._ai_s2_trigger = QComboBox()
        self._ai_s2_trigger.addItem(texts.PROCESSING_AI_STAGE2_TRIGGER_LOW, "low")
        self._ai_s2_trigger.addItem(texts.PROCESSING_AI_STAGE2_TRIGGER_LOW_MEDIUM, "low_medium")
        self._ai_s2_trigger.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        self._ai_s2_trigger.currentIndexChanged.connect(self._on_s2_trigger_changed)
        s2_trigger_row.addWidget(self._ai_s2_trigger)
        s2_trigger_row.addStretch()
        s2_fields_layout.addLayout(s2_trigger_row)

        # Model + Max Tokens
        s2_row = QHBoxLayout()
        s2_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_MODEL))
        self._ai_s2_model = QComboBox()
        self._ai_s2_model.setMinimumWidth(250)
        self._ai_s2_model.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        s2_row.addWidget(self._ai_s2_model)
        s2_row.addSpacing(20)
        s2_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_MAX_TOKENS))
        self._ai_s2_max_tokens = QSpinBox()
        self._ai_s2_max_tokens.setRange(50, 4096)
        self._ai_s2_max_tokens.setValue(200)
        self._ai_s2_max_tokens.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        s2_row.addWidget(self._ai_s2_max_tokens)
        s2_row.addStretch()
        s2_fields_layout.addLayout(s2_row)

        # Version Dropdown + Save As
        s2_version_row = QHBoxLayout()
        s2_version_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_VERSION))
        self._ai_s2_version = QComboBox()
        self._ai_s2_version.setMinimumWidth(300)
        self._ai_s2_version.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        self._ai_s2_version.currentIndexChanged.connect(self._on_s2_version_changed)
        s2_version_row.addWidget(self._ai_s2_version)
        self._btn_s2_save_version = QPushButton(texts.PROCESSING_AI_VERSION_SAVE_AS)
        self._btn_s2_save_version.setStyleSheet(get_button_secondary_style())
        self._btn_s2_save_version.setCursor(Qt.PointingHandCursor)
        self._btn_s2_save_version.clicked.connect(lambda: self._save_prompt_version('stage2'))
        s2_version_row.addWidget(self._btn_s2_save_version)
        s2_version_row.addStretch()
        s2_fields_layout.addLayout(s2_version_row)

        # Prompt Editor
        prompt2_label = QLabel(texts.PROCESSING_AI_STAGE_PROMPT)
        prompt2_label.setStyleSheet("border: none;")
        s2_fields_layout.addWidget(prompt2_label)
        self._ai_s2_prompt = QPlainTextEdit()
        self._ai_s2_prompt.setMinimumHeight(200)
        self._ai_s2_prompt.setMaximumHeight(400)
        self._ai_s2_prompt.setFont(QFont("Consolas", 10))
        self._ai_s2_prompt.setStyleSheet(f"border: 1px solid #ccc; border-radius: {RADIUS_SM}; padding: 8px;")
        s2_fields_layout.addWidget(self._ai_s2_prompt)

        stage2_layout.addWidget(self._ai_s2_fields)

        scroll_layout.addWidget(stage2_group)

        # ---- Bereich D: Ergebnis ----
        result_label = QLabel(f"▼  {texts.PROCESSING_AI_RESULT_TITLE}: {texts.PROCESSING_AI_RESULT_DESC}")
        result_label.setAlignment(Qt.AlignCenter)
        result_label.setStyleSheet(f"color: {SUCCESS}; font-size: 13px; padding: 12px;")
        result_label.setWordWrap(True)
        scroll_layout.addWidget(result_label)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _on_s2_enabled_toggled(self, checked: bool):
        """Toggle Stufe 2 aktiv/deaktiviert."""
        self._ai_s2_fields.setVisible(checked)
        self._ai_s2_disabled_info.setVisible(not checked)
        if checked:
            self._ai_stage2_group.setStyleSheet(f"""
                QFrame {{
                    background-color: {PRIMARY_0};
                    border: 2px solid {PRIMARY_500};
                    border-radius: {RADIUS_MD};
                    padding: 16px;
                }}
            """)
        else:
            self._ai_stage2_group.setStyleSheet(f"""
                QFrame {{
                    background-color: {PRIMARY_100};
                    border: 2px dashed {PRIMARY_500};
                    border-radius: {RADIUS_MD};
                    padding: 16px;
                }}
            """)

    def _on_s2_trigger_changed(self, index: int):
        """Aktualisiert das Transition-Label wenn der Trigger geaendert wird."""
        trigger = self._ai_s2_trigger.currentData()
        if trigger == 'low_medium':
            self._ai_transition_label.setText(
                f"▼  {texts.PROCESSING_AI_TRANSITION_LABEL.format(trigger='low oder medium')}")
        else:
            self._ai_transition_label.setText(
                f"▼  {texts.PROCESSING_AI_TRANSITION_LABEL.format(trigger='low')}")

    def _on_s1_version_changed(self, index: int):
        """Laedt einen Stufe-1-Prompt aus der Version."""
        if index <= 0 or index > len(self._ai_s1_versions):
            return
        version = self._ai_s1_versions[index - 1]
        self._ai_s1_prompt.setPlainText(version.get('prompt_text', ''))
        model = version.get('model', '')
        idx = self._ai_s1_model.findText(model)
        if idx >= 0:
            self._ai_s1_model.setCurrentIndex(idx)
        mt = version.get('max_tokens', 150)
        self._ai_s1_max_tokens.setValue(int(mt))

    def _on_s2_version_changed(self, index: int):
        """Laedt einen Stufe-2-Prompt aus der Version."""
        if index <= 0 or index > len(self._ai_s2_versions):
            return
        version = self._ai_s2_versions[index - 1]
        self._ai_s2_prompt.setPlainText(version.get('prompt_text', ''))
        model = version.get('model', '')
        idx = self._ai_s2_model.findText(model)
        if idx >= 0:
            self._ai_s2_model.setCurrentIndex(idx)
        mt = version.get('max_tokens', 200)
        self._ai_s2_max_tokens.setValue(int(mt))

    def _load_ai_classification_settings(self):
        """Laedt KI-Einstellungen und Prompt-Versionen vom Server."""
        self._refresh_ai_classification_provider_info()

        try:
            data = self._processing_settings_api.get_ai_settings_admin()
            settings = data.get('settings', {})

            if not settings:
                return

            # Stufe 1 befuellen
            s1_model = settings.get('stage1_model', 'openai/gpt-4o-mini')
            self._restore_model_selection(self._ai_s1_model, s1_model)

            self._ai_s1_max_tokens.setValue(int(settings.get('stage1_max_tokens', 150)))
            self._ai_s1_prompt.setPlainText(settings.get('stage1_prompt', ''))

            # Stufe 2 befuellen
            s2_enabled = settings.get('stage2_enabled')
            if isinstance(s2_enabled, str):
                s2_enabled = s2_enabled == '1'
            self._ai_s2_enabled.setChecked(bool(s2_enabled))

            s2_model = settings.get('stage2_model', 'openai/gpt-4o-mini')
            self._restore_model_selection(self._ai_s2_model, s2_model)

            self._ai_s2_max_tokens.setValue(int(settings.get('stage2_max_tokens', 200)))
            self._ai_s2_prompt.setPlainText(settings.get('stage2_prompt', ''))

            trigger = settings.get('stage2_trigger', 'low')
            trigger_idx = self._ai_s2_trigger.findData(trigger)
            if trigger_idx >= 0:
                self._ai_s2_trigger.setCurrentIndex(trigger_idx)

            # Versionen laden
            self._load_prompt_versions()

        except Exception as e:
            logger.error(f"KI-Settings laden fehlgeschlagen: {e}")
            from ui.toast import ToastManager
            ToastManager.instance().show_error(texts.PROCESSING_AI_LOAD_ERROR)

    def _refresh_ai_classification_provider_info(self):
        """Laedt aktiven Provider und aktualisiert Banner + Modell-Dropdowns."""
        try:
            provider_info = self._ai_providers_api.get_active_provider()
            if provider_info and provider_info.get('provider'):
                provider = provider_info['provider']
                name = provider_info.get('name', '')

                banner_text = texts.AI_CLASSIFICATION_PROVIDER_INFO.format(
                    provider=provider.capitalize(), name=name
                )
                if provider == 'openrouter':
                    banner_text += "\n" + texts.AI_CLASSIFICATION_PROVIDER_ALL_MODELS
                else:
                    banner_text += "\n" + texts.AI_CLASSIFICATION_PROVIDER_OPENAI_ONLY
                self._ai_provider_banner.setText(banner_text)

                self._update_model_dropdowns(provider)
            else:
                self._ai_provider_banner.setText(texts.AI_CLASSIFICATION_NO_PROVIDER)
                self._update_model_dropdowns('openrouter')
        except Exception as e:
            logger.warning(f"Provider-Info laden fehlgeschlagen: {e}")
            self._update_model_dropdowns('openrouter')

    def _update_model_dropdowns(self, provider: str):
        """Aktualisiert Modell-Auswahl basierend auf Provider."""
        from config.ai_models import get_models_for_provider

        models = get_models_for_provider(provider)

        current_s1 = self._ai_s1_model.currentText()
        current_s2 = self._ai_s2_model.currentText()

        for combo in [self._ai_s1_model, self._ai_s2_model]:
            combo.blockSignals(True)
            combo.clear()
            for m in models:
                combo.addItem(m["name"], m["id"])
            combo.blockSignals(False)

        if current_s1:
            self._restore_model_selection(self._ai_s1_model, current_s1)
        if current_s2:
            self._restore_model_selection(self._ai_s2_model, current_s2)

    def _restore_model_selection(self, combo: QComboBox, model_id: str):
        """Stellt Modell-Auswahl wieder her oder mappt auf Aequivalent."""
        from config.ai_models import find_equivalent_model

        idx = combo.findData(model_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return

        idx = combo.findText(model_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return

        provider = 'openrouter'
        if combo.count() > 0:
            first_id = combo.itemData(0) or ''
            if '/' not in str(first_id):
                provider = 'openai'

        equivalent = find_equivalent_model(model_id, provider)
        idx = combo.findData(equivalent)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return

        if model_id:
            combo.addItem(model_id, model_id)
            combo.setCurrentIndex(combo.count() - 1)

    def _load_prompt_versions(self):
        """Laedt Prompt-Versionen fuer beide Stufen."""
        try:
            # Stage 1
            self._ai_s1_versions = self._processing_settings_api.get_prompt_versions('stage1')
            self._ai_s1_version.blockSignals(True)
            self._ai_s1_version.clear()
            self._ai_s1_version.addItem(texts.PROCESSING_AI_VERSION_CURRENT)
            for v in self._ai_s1_versions:
                label = v.get('label') or f"v{v.get('version_number', '?')}"
                is_default = v.get('is_default')
                if is_default:
                    label = f"{label} ({texts.PROCESSING_AI_VERSION_SYSTEM_DEFAULT})"
                self._ai_s1_version.addItem(label)
            self._ai_s1_version.setCurrentIndex(0)
            self._ai_s1_version.blockSignals(False)

            # Stage 2
            self._ai_s2_versions = self._processing_settings_api.get_prompt_versions('stage2')
            self._ai_s2_version.blockSignals(True)
            self._ai_s2_version.clear()
            self._ai_s2_version.addItem(texts.PROCESSING_AI_VERSION_CURRENT)
            for v in self._ai_s2_versions:
                label = v.get('label') or f"v{v.get('version_number', '?')}"
                is_default = v.get('is_default')
                if is_default:
                    label = f"{label} ({texts.PROCESSING_AI_VERSION_SYSTEM_DEFAULT})"
                self._ai_s2_version.addItem(label)
            self._ai_s2_version.setCurrentIndex(0)
            self._ai_s2_version.blockSignals(False)

        except Exception as e:
            logger.error(f"Prompt-Versionen laden fehlgeschlagen: {e}")

    def _save_ai_classification_settings(self):
        """Speichert KI-Einstellungen auf dem Server."""
        try:
            s1_model = self._ai_s1_model.currentData() or self._ai_s1_model.currentText()
            s2_model = self._ai_s2_model.currentData() or self._ai_s2_model.currentText()
            data = {
                'stage1_model': s1_model,
                'stage1_prompt': self._ai_s1_prompt.toPlainText(),
                'stage1_max_tokens': self._ai_s1_max_tokens.value(),
                'stage2_enabled': self._ai_s2_enabled.isChecked(),
                'stage2_model': s2_model,
                'stage2_prompt': self._ai_s2_prompt.toPlainText(),
                'stage2_max_tokens': self._ai_s2_max_tokens.value(),
                'stage2_trigger': self._ai_s2_trigger.currentData() or 'low',
            }

            self._processing_settings_api.save_ai_settings(data)

            from ui.toast import ToastManager
            ToastManager.instance().show_success(texts.PROCESSING_AI_SAVE_SUCCESS)

            self._load_prompt_versions()

        except Exception as e:
            logger.error(f"KI-Settings speichern fehlgeschlagen: {e}")
            from ui.toast import ToastManager
            ToastManager.instance().show_error(texts.PROCESSING_AI_SAVE_ERROR)

    def _save_prompt_version(self, stage: str):
        """Speichert den aktuellen Prompt als benannte Version."""
        from PySide6.QtWidgets import QInputDialog
        label, ok = QInputDialog.getText(
            self,
            texts.PROCESSING_AI_VERSION_SAVE_AS,
            texts.PROCESSING_AI_VERSION_LABEL,
        )
        if not ok:
            return

        try:
            if stage == 'stage1':
                prompt = self._ai_s1_prompt.toPlainText()
                model = self._ai_s1_model.currentData() or self._ai_s1_model.currentText()
                max_tokens = self._ai_s1_max_tokens.value()
            else:
                prompt = self._ai_s2_prompt.toPlainText()
                model = self._ai_s2_model.currentData() or self._ai_s2_model.currentText()
                max_tokens = self._ai_s2_max_tokens.value()

            data = {
                f'{stage}_prompt': prompt,
                f'{stage}_model': model,
                f'{stage}_max_tokens': max_tokens,
                f'{stage}_version_label': label.strip() if label.strip() else None,
            }

            self._processing_settings_api.save_ai_settings(data)

            from ui.toast import ToastManager
            ToastManager.instance().show_success(texts.PROCESSING_AI_SAVE_SUCCESS)

            self._load_prompt_versions()

        except Exception as e:
            logger.error(f"Prompt-Version speichern fehlgeschlagen: {e}")
            from ui.toast import ToastManager
            ToastManager.instance().show_error(texts.PROCESSING_AI_SAVE_ERROR)
