"""Director — user-facing copilot / orchestrator agent."""

from pathlib import Path

MANIFEST_PATH = Path(__file__).parent / "app.yaml"

__all__ = ["MANIFEST_PATH"]
