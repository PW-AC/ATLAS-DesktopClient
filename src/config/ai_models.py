"""
Zentrale Modell-Definitionen pro KI-Provider.

Wird von admin_view.py fuer dynamische Modell-ComboBoxen verwendet.
"""

MODELS_OPENROUTER = [
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini (OpenAI)"},
    {"id": "openai/gpt-4o", "name": "GPT-4o (OpenAI)"},
    {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet"},
    {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku"},
    {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash"},
]

MODELS_OPENAI = [
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
    {"id": "gpt-4o", "name": "GPT-4o"},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
]


def get_models_for_provider(provider: str) -> list:
    """Gibt verfuegbare Modelle fuer den Provider zurueck."""
    if provider == "openrouter":
        return MODELS_OPENROUTER
    elif provider == "openai":
        return MODELS_OPENAI
    return MODELS_OPENROUTER


def map_model_to_provider(model_id: str, target_provider: str) -> str:
    """Mappt Modell-ID zwischen Providern.
    
    openai/gpt-4o -> gpt-4o (fuer OpenAI)
    gpt-4o -> openai/gpt-4o (fuer OpenRouter)
    """
    if target_provider == "openai":
        if model_id.startswith("openai/"):
            return model_id[7:]
        return model_id
    elif target_provider == "openrouter":
        if "/" not in model_id:
            return f"openai/{model_id}"
        return model_id
    return model_id


def find_equivalent_model(model_id: str, target_provider: str) -> str:
    """Findet das aequivalente Modell beim Ziel-Provider."""
    mapped = map_model_to_provider(model_id, target_provider)
    models = get_models_for_provider(target_provider)
    for m in models:
        if m["id"] == mapped:
            return mapped
    if models:
        return models[0]["id"]
    return model_id
