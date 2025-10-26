"""Quick runtime probe for the OpenParliament bills adapter.

Runs a single fetch and prints status plus telemetry metrics.
"""

from __future__ import annotations
from src.adapters.openparliament_bills import OpenParliamentBillsAdapter

import asyncio
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def main() -> None:
    adapter = OpenParliamentBillsAdapter()
    try:
        response = await adapter.fetch(parliament=44, session=1, limit=5)
        print("status:", response.status)
        record_count = len(response.data) if response.data else 0
        print("records:", record_count)
        print("metrics:")
        print(json.dumps(response.metrics.model_dump(), indent=2))
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(main())
