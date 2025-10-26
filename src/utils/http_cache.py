"""HTTP cache validation utilities.

Provides helpers for working with conditional requests (ETag and Last-Modified)
so adapters can avoid re-downloading unchanged payloads.

Responsibility: Manage conditional GET validators for HTTP requests
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class CacheValidator:
    """Represents cache validation headers for conditional GET requests."""

    etag: Optional[str] = None
    last_modified: Optional[str] = None

    def apply(self, base_headers: Dict[str, str]) -> Dict[str, str]:
        """Return a copy of ``base_headers`` with conditional headers applied."""
        headers = dict(base_headers)
        if self.etag:
            headers["If-None-Match"] = self.etag
        if self.last_modified:
            headers["If-Modified-Since"] = self.last_modified
        return headers

    def update_from_response(self, response) -> bool:
        """Update validator from an ``httpx.Response`` and return True if changed."""
        updated = False
        new_etag = response.headers.get("ETag")
        new_last_modified = response.headers.get("Last-Modified")

        if new_etag and new_etag != self.etag:
            self.etag = new_etag
            updated = True
        if new_last_modified and new_last_modified != self.last_modified:
            self.last_modified = new_last_modified
            updated = True
        return updated

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Serialize validator to a dictionary for persistence."""
        return {
            "etag": self.etag,
            "last_modified": self.last_modified,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, str]]) -> "CacheValidator":
        """Deserialize a validator from stored metadata."""
        if not data:
            return cls()
        return cls(
            etag=data.get("etag"),
            last_modified=data.get("last_modified"),
        )

    def has_validators(self) -> bool:
        """Return True when any conditional header is available."""
        return bool(self.etag or self.last_modified)
