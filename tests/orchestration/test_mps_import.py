from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from parliament.imports import mps
from parliament.orchestration.models import EtlJobWatermark


class MpsImportWatermarkTests(TestCase):
    def setUp(self) -> None:
        self.dataset = [
            {
                "name": "Alice Example",
                "party_name": "Example Party",
                "offices": [],
                "extra": {},
            }
        ]

    def test_updates_watermark_when_dataset_changes(self) -> None:
        with patch("parliament.imports.mps._import_mps") as mock_import:
            result = mps.import_mps_dataset(self.dataset, source="test-source")
        self.assertTrue(result)
        mock_import.assert_called_once()
        called_records, called_download, called_update = mock_import.call_args[0]
        self.assertEqual(called_records, self.dataset)
        self.assertFalse(called_download)
        self.assertFalse(called_update)

        watermark = EtlJobWatermark.objects.get(job_name="mps.test-source")
        expected_fingerprint = mps._fingerprint_dataset(self.dataset)
        self.assertEqual(watermark.last_token, expected_fingerprint)
        self.assertEqual(watermark.metadata["fingerprint"], expected_fingerprint)
        self.assertEqual(watermark.metadata["count"], len(self.dataset))
        self.assertEqual(watermark.metadata["source"], "test-source")

    def test_skips_when_dataset_unchanged_without_headshots(self) -> None:
        fingerprint = mps._fingerprint_dataset(self.dataset)
        EtlJobWatermark.objects.create(
            job_name="mps.test-source",
            last_token=fingerprint,
            metadata={"fingerprint": fingerprint},
        )
        with patch("parliament.imports.mps._import_mps") as mock_import:
            result = mps.import_mps_dataset(self.dataset, source="test-source")
        self.assertFalse(result)
        mock_import.assert_not_called()

    def test_runs_when_headshot_refresh_requested(self) -> None:
        fingerprint = mps._fingerprint_dataset(self.dataset)
        EtlJobWatermark.objects.create(
            job_name="mps.test-source",
            last_token=fingerprint,
            metadata={"fingerprint": fingerprint},
        )
        with patch("parliament.imports.mps._import_mps") as mock_import:
            result = mps.import_mps_dataset(
                self.dataset,
                download_headshots=True,
                source="test-source",
            )
        self.assertTrue(result)
        mock_import.assert_called_once()
