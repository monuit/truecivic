"""Smoke test for Qdrant connectivity using Railway-provided environment variables."""

from __future__ import annotations
from src.services.rag.vector_store import QdrantConfig

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Iterable, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


BASE_ENV_DIR = Path(__file__).resolve().parents[2] / "railway" / "env"
DEFAULT_ENV_FILES: Sequence[Path] = (
    BASE_ENV_DIR / "truecivic-prod-server-a.env",
    BASE_ENV_DIR / "truecivic-qdrant.env",
)


def load_env_file(path: Path) -> None:
    """Populate os.environ with key/value pairs from a .env-style file."""
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith("\ufeff"):
                stripped = stripped.lstrip("\ufeff")
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key, value)


def parse_arguments(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Qdrant smoke test")
    parser.add_argument(
        "--env-file",
        type=Path,
        action="append",
        help="Path(s) to Railway env files containing connection details",
    )
    return parser.parse_args(argv)


def run_smoke_test(client: QdrantClient, *, base_collection: str) -> None:
    temp_collection = f"{base_collection}_smoke_{uuid.uuid4().hex[:8]}".strip(
        "_")
    try:
        if client.collection_exists(temp_collection):  # pragma: no cover - safety
            client.delete_collection(collection_name=temp_collection)
        client.create_collection(
            collection_name=temp_collection,
            vectors_config=qmodels.VectorParams(
                size=3, distance=qmodels.Distance.COSINE),
        )
        point = qmodels.PointStruct(
            id=1,
            vector=[0.1, 0.2, 0.3],
            payload={"label": "smoke"},
        )
        client.upsert(collection_name=temp_collection, points=[point])
        response = client.query_points(
            collection_name=temp_collection,
            query=[0.1, 0.2, 0.3],
            limit=1,
            with_payload=True,
        )
        points = list(response.points)
        if not points or int(points[0].id) != 1:
            raise RuntimeError(
                "Qdrant smoke test did not return the inserted point")
    finally:
        try:
            client.delete_collection(collection_name=temp_collection)
        except Exception:  # pragma: no cover - cleanup best effort
            pass


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_arguments(argv)
    env_files: Sequence[Path] = tuple(args.env_file or DEFAULT_ENV_FILES)

    for env_path in env_files:
        load_env_file(env_path)

    config = QdrantConfig.from_env()
    client = QdrantClient(
        host=config.host,
        port=config.port,
        https=config.use_tls,
        api_key=config.api_key,
        timeout=config.timeout_seconds,
        prefer_grpc=False,
    )
    run_smoke_test(client, base_collection=config.collection)

    print("Qdrant smoke test succeeded; round-trip search worked as expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
