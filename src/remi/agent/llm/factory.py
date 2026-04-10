"""LLM provider factory — settings-driven provider resolution.

Adapters are registered declaratively in ``_ADAPTERS`` as
``(module_path, class_name)`` tuples.  The factory loads them via
``importlib.import_module`` at ``create()`` time — no top-level imports
of SDK-dependent code.  Each adapter guards its own SDK import in
``_get_client()`` and raises a clear ``RuntimeError`` if the package is
missing.
"""

from __future__ import annotations

import importlib
from typing import Any

from remi.agent.llm.types import LLMProvider, ProviderConfig, ProviderFactory, SecretsSettings

_ADAPTERS: dict[str, tuple[str, str]] = {
    "openai": ("remi.agent.llm.adapters.openai", "OpenAIProvider"),
    "openai_compatible": ("remi.agent.llm.adapters.openai", "OpenAIProvider"),
    "anthropic": ("remi.agent.llm.adapters.anthropic", "AnthropicProvider"),
    "gemini": ("remi.agent.llm.adapters.gemini", "GeminiProvider"),
}

_SECRET_KEY_MAP: dict[str, str] = {
    "openai": "openai_api_key",
    "openai_compatible": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "gemini": "google_api_key",
}


def _load_adapter(name: str) -> type[LLMProvider]:
    """Resolve an adapter class by backend name via importlib."""
    entry = _ADAPTERS.get(name)
    if entry is None:
        available = ", ".join(sorted(_ADAPTERS)) or "(none)"
        raise ValueError(
            f"Unknown LLM provider '{name}'. "
            f"Available: {available}. "
            f"Install the provider package and ensure it is registered."
        )
    module_path, class_name = entry
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls  # type: ignore[no-any-return]


class LLMProviderFactory(ProviderFactory):
    """Creates LLM provider instances by name.

    Provider classes are looked up in the static ``_ADAPTERS`` registry and
    loaded via ``importlib.import_module`` on first use.
    """

    def __init__(self, secrets: SecretsSettings) -> None:
        self._secrets = secrets

    def create(self, name: str, **overrides: Any) -> LLMProvider:
        cls = _load_adapter(name)
        config = self._build_config(name, **overrides)
        return cls(config)

    def available(self) -> list[str]:
        return sorted(_ADAPTERS)

    def has(self, name: str) -> bool:
        return name in _ADAPTERS

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
