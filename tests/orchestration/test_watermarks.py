from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from parliament.orchestration.watermarks import get_watermark, update_watermark


class WatermarkTests(TestCase):
    def test_update_and_retrieve(self) -> None:
        current = timezone.now()
        update_watermark(
            "example",
            token="initial",
            timestamp=current,
            metadata={"seq": 1},
        )
        watermark = get_watermark("example")
        self.assertEqual(watermark.token, "initial")
        self.assertEqual(watermark.metadata.get("seq"), 1)
        self.assertIsNotNone(watermark.timestamp)
        self.assertAlmostEqual(
            watermark.timestamp.timestamp(),
            current.timestamp(),
            delta=1.0,
        )

    def test_rejects_timestamp_regression(self) -> None:
        later = timezone.now()
        update_watermark("regression", token="later", timestamp=later)
        earlier = later - timedelta(hours=2)
        update_watermark("regression", token="earlier", timestamp=earlier)
        watermark = get_watermark("regression")
        self.assertEqual(watermark.token, "later")
        self.assertAlmostEqual(
            watermark.timestamp.timestamp(),
            later.timestamp(),
            delta=1.0,
        )

    def test_progress_with_equal_timestamp(self) -> None:
        reference = timezone.now()
        update_watermark(
            "same_ts",
            token="token-a",
            timestamp=reference,
            metadata={"vote": 1},
        )
        update_watermark(
            "same_ts",
            token="token-b",
            timestamp=reference,
            metadata={"vote": 2},
        )
        watermark = get_watermark("same_ts")
        self.assertEqual(watermark.token, "token-b")
        self.assertEqual(watermark.metadata.get("vote"), 2)
