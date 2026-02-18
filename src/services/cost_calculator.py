"""
KI-Kostenberechnung mit tiktoken.

Token-Zaehlung fuer praezise Kostenschaetzung VOR dem Request
und exakte Kostenberechnung NACH dem Request.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken nicht installiert, Fallback auf Zeichenschaetzung (~4 Zeichen = 1 Token)")


@dataclass
class CostEstimate:
    """Kostenschaetzung VOR dem Request (Worst-Case)."""
    prompt_tokens: int
    max_completion_tokens: int
    estimated_cost_usd: float
    model: str


@dataclass
class RealCost:
    """Exakte Kosten NACH dem Request."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    real_cost_usd: float
    model: str


class CostCalculator:
    """Token-Zaehlung und Kostenberechnung fuer OpenAI/OpenRouter."""

    def __init__(self):
        self._encodings: Dict[str, object] = {}
        self._pricing_cache: Dict[str, Tuple[float, float]] = {}

    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        """Zaehlt Tokens mit tiktoken (exakt fuer OpenAI-Modelle).

        Bei fehlender tiktoken-Installation: Fallback ~4 Zeichen pro Token.
        """
        base_model = model.replace("openai/", "")

        if not TIKTOKEN_AVAILABLE:
            return max(1, len(text) // 4)

        if base_model not in self._encodings:
            try:
                self._encodings[base_model] = tiktoken.encoding_for_model(base_model)
            except KeyError:
                self._encodings[base_model] = tiktoken.get_encoding("cl100k_base")

        return len(self._encodings[base_model].encode(text))

    def set_pricing(self, model: str, input_price: float, output_price: float) -> None:
        """Setzt Preise fuer ein Modell ($ pro 1M Tokens)."""
        self._pricing_cache[model] = (input_price, output_price)

    def load_pricing_from_api(self, api_client) -> None:
        """Laedt Preise vom Server (/ai/pricing)."""
        try:
            response = api_client.get("/ai/pricing")
            if not response:
                return
            data = response.get('data', response) if isinstance(response, dict) else {}
            prices = data.get("prices", [])
            for price in prices:
                self.set_pricing(
                    price["model"],
                    price["input_price_per_million"],
                    price["output_price_per_million"]
                )
            logger.info(f"Modell-Preise geladen: {len(prices)} Eintraege")
        except Exception as e:
            logger.warning(f"Modell-Preise laden fehlgeschlagen: {e}")

    def _get_pricing(self, model: str) -> Tuple[float, float]:
        """Preis fuer Modell nachschlagen, mit Fallback-Suche."""
        if model in self._pricing_cache:
            return self._pricing_cache[model]

        base_model = model.replace("openai/", "")
        if base_model in self._pricing_cache:
            return self._pricing_cache[base_model]

        prefixed = f"openai/{model}"
        if prefixed in self._pricing_cache:
            return self._pricing_cache[prefixed]

        return (0.0, 0.0)

    def estimate_cost(
        self,
        prompt_text: str,
        model: str,
        max_tokens: int = 1000
    ) -> CostEstimate:
        """Schaetzt Kosten VOR dem Request (Worst-Case mit max_tokens)."""
        prompt_tokens = self.count_tokens(prompt_text, model)
        input_price, output_price = self._get_pricing(model)

        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (max_tokens / 1_000_000) * output_price

        return CostEstimate(
            prompt_tokens=prompt_tokens,
            max_completion_tokens=max_tokens,
            estimated_cost_usd=round(input_cost + output_cost, 6),
            model=model
        )

    def calculate_real_cost(
        self,
        usage: dict,
        model: str
    ) -> RealCost:
        """Berechnet exakte Kosten NACH dem Request aus usage-Daten."""
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        input_price, output_price = self._get_pricing(model)

        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price

        return RealCost(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            real_cost_usd=round(input_cost + output_cost, 6),
            model=model
        )

    def estimate_from_messages(
        self,
        messages: List[dict],
        model: str,
        max_tokens: int = 1000
    ) -> CostEstimate:
        """Schaetzt Kosten aus einer Message-Liste (wie fuer Chat-Completions)."""
        parts = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
        prompt_text = "\n".join(parts)
        return self.estimate_cost(prompt_text, model, max_tokens)
