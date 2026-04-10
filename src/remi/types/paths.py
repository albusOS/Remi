"""Canonical paths for the REMI package."""

from pathlib import Path

REMI_PACKAGE_DIR = Path(__file__).resolve().parent.parent
DOMAIN_YAML_PATH = REMI_PACKAGE_DIR / "shell" / "config" / "domain.yaml"
