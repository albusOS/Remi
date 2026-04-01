"""Lightweight token estimation — no external dependencies.

Single source of truth for the heuristic 4-chars-per-token approximation
used for context-budget decisions when a provider-native tokenizer is
unavailable.  Provider-specific ``count_tokens()`` on ``LLMProvider``
should be preferred when accuracy matters.
"""

from __future__ import annotations

CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Return approximate token count for *text*."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate *text* to fit within *max_tokens*, breaking on a line boundary."""
    if estimate_tokens(text) <= max_tokens:
        return text
    char_budget = max_tokens * CHARS_PER_TOKEN
    truncated = text[:char_budget]
    last_nl = truncated.rfind("\n")
    if last_nl > char_budget // 2:
        truncated = truncated[:last_nl]
    return truncated
