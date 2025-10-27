"""Utilities for normalizing jurisdiction identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

# MARK: Canonical definitions

_CANONICAL_JURISDICTIONS: Dict[str, str] = {
    "CANADA": "canada-federal",
    "CANADA-FEDERAL": "canada-federal",
    "FEDERAL": "canada-federal",
    "FED": "canada-federal",
    "CA": "canada-federal",
    "CA-FED": "canada-federal",
    "CANADA-AB": "canada-ab",
    "ALBERTA": "canada-ab",
    "AB": "canada-ab",
    "CANADA-BC": "canada-bc",
    "BRITISH COLUMBIA": "canada-bc",
    "BC": "canada-bc",
    "CANADA-MB": "canada-mb",
    "MANITOBA": "canada-mb",
    "MB": "canada-mb",
    "CANADA-NB": "canada-nb",
    "NEW BRUNSWICK": "canada-nb",
    "NB": "canada-nb",
    "CANADA-NL": "canada-nl",
    "NEWFOUNDLAND AND LABRADOR": "canada-nl",
    "NL": "canada-nl",
    "CANADA-NS": "canada-ns",
    "NOVA SCOTIA": "canada-ns",
    "NS": "canada-ns",
    "CANADA-NT": "canada-nt",
    "NORTHWEST TERRITORIES": "canada-nt",
    "NT": "canada-nt",
    "CANADA-NU": "canada-nu",
    "NUNAVUT": "canada-nu",
    "NU": "canada-nu",
    "CANADA-ON": "canada-on",
    "ONTARIO": "canada-on",
    "ON": "canada-on",
    "CANADA-PE": "canada-pe",
    "PRINCE EDWARD ISLAND": "canada-pe",
    "PE": "canada-pe",
    "CANADA-QC": "canada-qc",
    "QUEBEC": "canada-qc",
    "QC": "canada-qc",
    "CANADA-SK": "canada-sk",
    "SASKATCHEWAN": "canada-sk",
    "SK": "canada-sk",
    "CANADA-YT": "canada-yt",
    "YUKON": "canada-yt",
    "YT": "canada-yt",
}

# MARK: Public API


def normalize_jurisdiction(value: str | None) -> str:
    """Normalize a jurisdiction string to a canonical slug."""
    if not value:
        return "canada-federal"
    normalized = value.strip().replace("_", "-").replace(" ", "-")
    normalized = normalized.upper()
    return _CANONICAL_JURISDICTIONS.get(normalized, normalized.lower())


@dataclass(frozen=True)
class JurisdictionSet:
    """Small helper to expose selectable jurisdictions to the frontend."""

    choices: tuple[str, ...]

    @staticmethod
    def from_env(value: str | None) -> "JurisdictionSet":
        if not value:
            return JurisdictionSet(("canada-federal",))
        parts = [normalize_jurisdiction(part)
                 for part in value.split(",") if part.strip()]
        if not parts:
            parts = ["canada-federal"]
        return JurisdictionSet(tuple(dict.fromkeys(parts)))
