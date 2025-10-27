"""Embedding service utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Sequence

from openai import OpenAI


@dataclass(frozen=True)
class EmbeddingConfig:
    """Configuration for embedding generation."""

    api_key: str
    model: str

    @staticmethod
    def from_env() -> "EmbeddingConfig":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for embeddings")
        model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        return EmbeddingConfig(api_key=api_key, model=model)


class EmbeddingService:
    """Wrapper around OpenAI embeddings with configured model."""

    def __init__(self, config: EmbeddingConfig) -> None:
        self._client = OpenAI(api_key=config.api_key)
        self._model = config.model

    def embed(self, texts: Iterable[str]) -> Sequence[Sequence[float]]:
        """Generate embeddings for the supplied texts."""
        response = self._client.embeddings.create(
            model=self._model,
            input=list(texts),
        )
        return [item.embedding for item in response.data]
