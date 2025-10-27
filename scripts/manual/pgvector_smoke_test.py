"""Deprecated pgvector smoke test stub."""

from __future__ import annotations


def main(*_args, **_kwargs) -> int:  # pragma: no cover - compatibility shim
    raise RuntimeError(
        "pgvector smoke test has been removed; use qdrant_smoke_test.py instead"
    )


if __name__ == "__main__":
    raise SystemExit(main())
