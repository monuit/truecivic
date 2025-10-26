"""Shared constants used across Prefect flows.

Keeps concurrency tag names and result storage configuration co-located.
"""

PREFECT_CONCURRENCY_TAG_API = "openparliament-api"
PREFECT_CONCURRENCY_TAG_DB = "parliament-db-write"
PREFECT_CONCURRENCY_TAG_ENRICHMENT = "legisinfo-enrichment"
PREFECT_RESULT_STORAGE_BLOCK = "s3/minio-results"
