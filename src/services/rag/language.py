"""Utilities for normalizing language identifiers."""

from __future__ import annotations

from typing import Dict

__all__ = ["DEFAULT_LANGUAGE", "normalize_language"]

DEFAULT_LANGUAGE = "en"

_CANONICAL_LANGUAGES: Dict[str, str] = {
    "EN": "en",
    "ENGLISH": "en",
    "EN-CA": "en",
    "EN-US": "en",
    "FR": "fr",
    "FRENCH": "fr",
    "FR-CA": "fr",
    "FR-FR": "fr",
}


def normalize_language(value: str | None) -> str:
    """Normalize user-supplied language strings to canonical slugs."""
    if not value:
        return DEFAULT_LANGUAGE

    normalized = value.strip().replace("_", "-").upper()
    direct = _CANONICAL_LANGUAGES.get(normalized)
    if direct:
        return direct

    if normalized.startswith("FR"):
        return "fr"
    if normalized.startswith("EN"):
        return "en"

    return DEFAULT_LANGUAGE
