from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from parliament.orchestration.definitions import EtlJobDefinition
from parliament.orchestration.models import EtlJobCheckpoint
from parliament.orchestration.runner import HourlyRunCoordinator


class HourlyRunCoordinatorTests(TestCase):
    def setUp(self) -> None:
        self.window = timezone.now().replace(minute=0, second=0, microsecond=0)

    def test_success_persists_checkpoint(self) -> None:
        calls: list[str] = []

        def job() -> None:
            calls.append("ran")

        coordinator = HourlyRunCoordinator(
            (EtlJobDefinition("job_success", job, max_attempts=1),),
            sleep=lambda _: None,
        )
        results = coordinator.run(self.window)
        checkpoint = EtlJobCheckpoint.objects.get(job_name="job_success")
        self.assertEqual(results["job_success"].status,
                         EtlJobCheckpoint.Status.SUCCESS)
        self.assertEqual(results["job_success"].attempt, 1)
        self.assertEqual(checkpoint.status, EtlJobCheckpoint.Status.SUCCESS)
        self.assertEqual(checkpoint.last_attempt, 1)
        self.assertEqual(len(calls), 1)

    def test_failure_then_retry(self) -> None:
        attempts: list[int] = []

        def job() -> None:
            attempts.append(len(attempts))
            if len(attempts) < 2:
                raise RuntimeError("boom")

        coordinator = HourlyRunCoordinator(
            (
                EtlJobDefinition(
                    "job_retry",
                    job,
                    max_attempts=3,
                    retry_delay_seconds=0.0,
                ),
            ),
            sleep=lambda _: None,
        )
        results = coordinator.run(self.window)
        checkpoint = EtlJobCheckpoint.objects.get(job_name="job_retry")
        self.assertEqual(results["job_retry"].status,
                         EtlJobCheckpoint.Status.SUCCESS)
        self.assertEqual(results["job_retry"].attempt, 2)
        self.assertEqual(checkpoint.status, EtlJobCheckpoint.Status.SUCCESS)
        self.assertEqual(checkpoint.last_attempt, 2)
        self.assertEqual(len(attempts), 2)

    def test_failure_records_state_without_blocking_others(self) -> None:
        def failing_job() -> None:
            raise RuntimeError("fail")

        executed: list[str] = []

        def should_not_run() -> None:
            executed.append("ran")

        coordinator = HourlyRunCoordinator(
            (
                EtlJobDefinition(
                    "job_fail",
                    failing_job,
                    max_attempts=2,
                    retry_delay_seconds=0.0,
                ),
                EtlJobDefinition("job_after", should_not_run, max_attempts=1),
            ),
            sleep=lambda _: None,
        )
        results = coordinator.run(self.window)
        checkpoint = EtlJobCheckpoint.objects.get(job_name="job_fail")
        self.assertEqual(results["job_fail"].status,
                         EtlJobCheckpoint.Status.FAILED)
        self.assertGreaterEqual(results["job_fail"].attempt, 1)
        self.assertEqual(checkpoint.status, EtlJobCheckpoint.Status.FAILED)
        self.assertEqual(len(executed), 0)
        self.assertIn("job_after", results)
        self.assertEqual(
            results["job_after"].status,
            EtlJobCheckpoint.Status.SUCCESS,
        )
        self.assertTrue(
            EtlJobCheckpoint.objects.filter(job_name="job_after").exists()
        )

    def test_dependency_skip_records_state(self) -> None:
        def job_a() -> None:
            return None

        def job_b() -> None:
            return None

        coordinator = HourlyRunCoordinator(
            (
                EtlJobDefinition("job_a", job_a, max_attempts=1),
                EtlJobDefinition(
                    "job_b",
                    job_b,
                    max_attempts=1,
                    dependencies=("missing",),
                ),
            ),
            sleep=lambda _: None,
        )
        results = coordinator.run(self.window)
        checkpoint = EtlJobCheckpoint.objects.get(job_name="job_b")
        self.assertEqual(results["job_a"].status,
                         EtlJobCheckpoint.Status.SUCCESS)
        self.assertEqual(results["job_b"].status,
                         EtlJobCheckpoint.Status.SKIPPED)
        self.assertEqual(checkpoint.status, EtlJobCheckpoint.Status.SKIPPED)
        self.assertIn("missing", checkpoint.last_error)

    def test_subsequent_run_same_window_skips_execution(self) -> None:
        calls: list[int] = []

        def job() -> None:
            calls.append(1)

        coordinator = HourlyRunCoordinator(
            (EtlJobDefinition("job_repeat", job, max_attempts=1),),
            sleep=lambda _: None,
        )
        coordinator.run(self.window)
        results = coordinator.run(self.window)
        checkpoint = EtlJobCheckpoint.objects.get(job_name="job_repeat")
        self.assertEqual(len(calls), 1)
        self.assertEqual(results["job_repeat"].status,
                         EtlJobCheckpoint.Status.SUCCESS)
        self.assertEqual(results["job_repeat"].attempt, 1)
        self.assertEqual(checkpoint.status, EtlJobCheckpoint.Status.SUCCESS)
