"""Client for NIA context augmentation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Mapping

import requests


@dataclass(frozen=True)
class NiaConfig:
    """Configuration for the NIA client."""

    endpoint: str
    api_key: str

    @staticmethod
    def from_env() -> "NiaConfig | None":
        endpoint = os.getenv("NIA_ENDPOINT")
        api_key = os.getenv("NIA_API_KEY")
        if not endpoint or not api_key:
            return None
        return NiaConfig(endpoint=endpoint, api_key=api_key)


class NiaClient:
    """Thin HTTP client for NIA context awareness."""

    def __init__(self, config: NiaConfig) -> None:
        self._config = config

    def enrich(self, query: str) -> Iterable[Mapping[str, str]]:
        response = requests.post(
            self._config.endpoint,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            json={"query": query},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("context", [])
