"""Canonical paths for the REMI package."""

from __future__ import annotations

from pathlib import Path

REMI_PACKAGE_DIR = Path(__file__).resolve().parent.parent

APPS_DIR = REMI_PACKAGE_DIR / "apps"

DOMAIN_YAML_PATH = REMI_PACKAGE_DIR / "config" / "domain.yaml"
