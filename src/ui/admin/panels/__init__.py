"""ACENCIA ATLAS - Admin-Panels (Package)."""

from ui.admin.panels.passwords import PasswordsPanel
from ui.admin.panels.document_rules import DocumentRulesPanel
from ui.admin.panels.ai_classification import AiClassificationPanel
from ui.admin.panels.ai_providers import AiProvidersPanel
from ui.admin.panels.model_pricing import ModelPricingPanel

__all__ = [
    'PasswordsPanel',
    'DocumentRulesPanel',
    'AiClassificationPanel',
    'AiProvidersPanel',
    'ModelPricingPanel',
]
