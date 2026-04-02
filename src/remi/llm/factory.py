"""LLM provider factory — settings-driven provider resolution.

All adapters are registered declaratively in ``_ADAPTER_MAP``.  The factory
resolves API keys from ``SecretsSettings`` at ``create()`` time — no lambdas,
no ``try/except ImportError`` gates.  Each adapter guards its own SDK import
in ``_get_client()`` and raises a clear ``RuntimeError`` if the package is
missing.
"""

from __future__ import annotations

from typing import Any

from remi.llm.anthropic import AnthropicProvider
from remi.llm.gemini import GeminiProvider
from remi.llm.openai import OpenAIProvider
from remi.llm.types import LLMProvider, ProviderConfig
from remi.types.config import SecretsSettings

_ADAPTER_MAP: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "openai_compatible": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}

_SECRET_KEY_MAP: dict[str, str] = {
    "openai": "openai_api_key",
    "openai_compatible": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "gemini": "google_api_key",
}


class LLMProviderFactory:
    """Creates LLM provider instances by name.

    Provider classes are looked up in the static ``_ADAPTER_MAP`` and
    instantiated with a ``ProviderConfig`` built from the stored secrets.
    """

    def __init__(self, secrets: SecretsSettings) -> None:
        self._secrets = secrets

    def create(self, name: str, **overrides: Any) -> LLMProvider:
        cls = _ADAPTER_MAP.get(name)
        if cls is None:
            available = ", ".join(sorted(_ADAPTER_MAP)) or "(none)"
            raise ValueError(
                f"Unknown LLM provider '{name}'. "
                f"Available: {available}. "
                f"Install the provider package and ensure it is registered."
            )
        config = self._build_config(name, **overrides)
        return cls(config)

    def available(self) -> list[str]:
        return sorted(_ADAPTER_MAP)

    def has(self, name: str) -> bool:
        return name in _ADAPTER_MAP

    def _build_config(self, name: str, **overrides: Any) -> ProviderConfig:
        secret_attr = _SECRET_KEY_MAP.get(name, "")
        api_key = overrides.pop("api_key", None) or (
            getattr(self._secrets, secret_attr, "") if secret_attr else ""
        )
        base_url = overrides.pop("base_url", None)
        return ProviderConfig(api_key=api_key, base_url=base_url, extra=overrides)


def build_provider_factory(secrets: SecretsSettings) -> LLMProviderFactory:
    """Construct the default provider factory from settings."""
    return LLMProviderFactory(secrets)
