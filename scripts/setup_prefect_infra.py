"""One-stop utility for preparing Prefect infrastructure dependencies.

Running this script will:
1. Ensure a shared S3-compatible result storage block exists (pointing at MinIO).
2. Update concurrency limits for the tags used by our production flows.

Usage:
    uv run python scripts/setup_prefect_infra.py

Assumes Prefect credentials / API keys are already configured via environment
variables (e.g., PREFECT_API_KEY, PREFECT_API_URL).
"""

from __future__ import annotations

import asyncio
import os
from typing import Dict

from prefect.client.orion import OrionClient  # type: ignore[import]
from prefect.exceptions import ObjectNotFound  # type: ignore[import]
from prefect.filesystems import S3  # type: ignore[import]

RESULT_BLOCK_NAME = "minio-results"

CONCURRENCY_TAG_ENV_MAPPING: Dict[str, tuple[str, int]] = {
    "openparliament-api": ("PREFECT_CONCURRENCY_LIMIT_OPENPARLIAMENT", 2),
    "parliament-db-write": ("PREFECT_CONCURRENCY_LIMIT_DB_WRITES", 1),
    "legisinfo-enrichment": ("PREFECT_CONCURRENCY_LIMIT_LEGISINFO", 1),
}


async def ensure_result_block() -> None:
    """Create or update the shared S3 filesystem block for task results."""

    root_user = os.getenv("MINIO_ROOT_USER")
    root_password = os.getenv("MINIO_ROOT_PASSWORD")
    endpoint = os.getenv("MINIO_PRIVATE_ENDPOINT")
    secure = os.getenv("MINIO_SECURE", "true").lower() == "true"
    processed_bucket = os.getenv(
        "MINIO_BUCKET_PROCESSED", "parl-processed-prod")
    result_suffix = os.getenv("PREFECT_RESULT_BUCKET_PATH", "prefect-results")

    if not all([root_user, root_password, endpoint]):
        raise RuntimeError(
            "MINIO_PRIVATE_ENDPOINT, MINIO_ROOT_USER, and MINIO_ROOT_PASSWORD must be set before running this script"
        )

    scheme = "https" if secure else "http"
    endpoint_url = f"{scheme}://{endpoint}".rstrip("/")
    bucket_path = f"{processed_bucket}/{result_suffix}".strip("/")

    filesystem = S3(
        bucket_path=bucket_path,
        aws_access_key_id=root_user,
        aws_secret_access_key=root_password,
        endpoint_url=endpoint_url,
        client_kwargs={"verify": secure},
    )

    await filesystem.save(name=RESULT_BLOCK_NAME, overwrite=True)
    print(
        f"✅ Result storage block '{RESULT_BLOCK_NAME}' now points to s3://{bucket_path}")


async def ensure_concurrency_limits(client: OrionClient) -> None:
    """Create/update concurrency limits based on environment defaults."""

    for tag, (env_var, default_limit) in CONCURRENCY_TAG_ENV_MAPPING.items():
        raw_value = os.getenv(env_var)
        try:
            limit = int(raw_value) if raw_value else default_limit
        except ValueError:
            limit = default_limit

        try:
            existing = await client.read_concurrency_limit_by_tag(tag)
        except ObjectNotFound:
            existing = None

        if existing and existing.limit == limit:
            print(
                f"ℹ️ Concurrency limit for tag '{tag}' already set to {limit}")
            continue

        if existing:
            await client.delete_concurrency_limit(existing.id)

        await client.create_concurrency_limit(tag=tag, limit=limit)
        print(f"✅ Set concurrency limit {limit} for tag '{tag}'")


async def main() -> None:
    await ensure_result_block()

    async with OrionClient() as client:
        await ensure_concurrency_limits(client)

    print("Finished Prefect infrastructure configuration")


if __name__ == "__main__":
    asyncio.run(main())
