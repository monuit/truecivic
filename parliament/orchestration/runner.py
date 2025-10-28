from __future__ import annotations

import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Sequence

from django.db import close_old_connections, transaction
from django.utils import timezone

from .definitions import EtlJobDefinition
from .models import EtlJobCheckpoint

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobExecutionResult:
    status: str
    attempt: int
    duration_seconds: float | None


@dataclass(frozen=True)
class PreparedRun:
    run_required: bool
    attempt: int


class HourlyRunCoordinator:
    """Coordinate execution of ETL jobs with checkpoint persistence."""

    def __init__(
            self,
            jobs: Sequence[EtlJobDefinition],
            *,
            checkpoint_model: type[EtlJobCheckpoint] | None = None,
            sleep: Callable[[float], None] | None = None,
            max_workers: int | None = None,
    ) -> None:
        if not jobs:
            raise ValueError("jobs cannot be empty")
        names = {job.name for job in jobs}
        if len(names) != len(jobs):
            raise ValueError("job names must be unique")
        self._jobs = jobs
        self._checkpoint_model = checkpoint_model or EtlJobCheckpoint
        self._sleep = sleep or time.sleep
        self._max_workers = max_workers or min(len(jobs), 4)

    def run(self, window_start) -> Dict[str, JobExecutionResult]:
        """Run the configured jobs for the provided hourly window."""
        results: Dict[str, JobExecutionResult] = {}
        pending: Dict[str, EtlJobDefinition] = {
            job.name: job for job in self._jobs}
        running: Dict[object, EtlJobDefinition] = {}

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            while pending or running:
                ready_to_remove: list[str] = []
                for name, job in list(pending.items()):
                    unmet = self._unmet_dependencies(job.dependencies, results)
                    if unmet and any(
                            results.get(
                                dep) and results[dep].status != self._checkpoint_model.Status.SUCCESS
                            for dep in job.dependencies
                            if dep in results
                    ):
                        self._mark_skipped(job.name, window_start, unmet)
                        results[job.name] = JobExecutionResult(
                            status=self._checkpoint_model.Status.SKIPPED,
                            attempt=0,
                            duration_seconds=0.0,
                        )
                        ready_to_remove.append(name)
                        continue

                    if unmet:
                        continue

                    prepared = self._prepare_run(job.name, window_start)
                    if not prepared.run_required:
                        logger.debug(
                            "Skipping %s; already satisfied for %s",
                            job.name,
                            window_start,
                        )
                        results[job.name] = JobExecutionResult(
                            status=self._checkpoint_model.Status.SUCCESS,
                            attempt=prepared.attempt,
                            duration_seconds=0.0,
                        )
                        ready_to_remove.append(name)
                        continue

                    future = executor.submit(
                        self._execute_job, job, window_start, prepared.attempt
                    )
                    running[future] = job
                    ready_to_remove.append(name)

                for name in ready_to_remove:
                    pending.pop(name, None)

                if not running:
                    break

                done, _ = wait(tuple(running.keys()),
                               return_when=FIRST_COMPLETED)
                for future in done:
                    job = running.pop(future)
                    results[job.name] = future.result()

        for job in pending.values():
            unmet = self._unmet_dependencies(job.dependencies, results)
            self._mark_skipped(job.name, window_start, unmet)
            results[job.name] = JobExecutionResult(
                status=self._checkpoint_model.Status.SKIPPED,
                attempt=0,
                duration_seconds=0.0,
            )

        return results

    def _execute_job(
            self,
            job: EtlJobDefinition,
            window_start,
            attempt: int,
    ) -> JobExecutionResult:
        base_delay = job.retry_delay_seconds or 0.0
        current_attempt = attempt
        while current_attempt <= job.max_attempts:
            start_clock = time.monotonic()
            logger.info(
                "Job %s starting attempt %s for window %s",
                job.name,
                current_attempt,
                window_start,
            )
            try:
                job.func()
            except Exception as exc:  # pragma: no cover - exception path
                duration = time.monotonic() - start_clock
                logger.exception(
                    "Job %s attempt %s failed after %.2fs",
                    job.name,
                    current_attempt,
                    duration,
                )
                self._record_attempt_failure(
                    job.name,
                    current_attempt,
                    duration,
                    exc,
                    final=current_attempt == job.max_attempts,
                )
                if current_attempt == job.max_attempts:
                    return JobExecutionResult(
                        status=self._checkpoint_model.Status.FAILED,
                        attempt=current_attempt,
                        duration_seconds=duration,
                    )
                current_attempt += 1
                self._prepare_retry(job.name, window_start, current_attempt)
                retry_index = current_attempt - attempt
                backoff = base_delay * (2 ** max(retry_index - 1, 0))
                if backoff > 0:
                    self._sleep(backoff)
                continue
            else:
                duration = time.monotonic() - start_clock
                self._mark_success(
                    job.name,
                    current_attempt,
                    duration,
                )
                return JobExecutionResult(
                    status=self._checkpoint_model.Status.SUCCESS,
                    attempt=current_attempt,
                    duration_seconds=duration,
                )
            finally:
                close_old_connections()

        return JobExecutionResult(
            status=self._checkpoint_model.Status.FAILED,
            attempt=current_attempt,
            duration_seconds=None,
        )

    def _prepare_run(self, job_name, window_start) -> PreparedRun:
        with transaction.atomic():
            checkpoint, _ = (
                self._checkpoint_model.objects.select_for_update().get_or_create(
                    job_name=job_name
                )
            )
            if (
                    checkpoint.last_window_start == window_start
                    and checkpoint.status == self._checkpoint_model.Status.SUCCESS
            ):
                return PreparedRun(False, checkpoint.last_attempt or 1)
            attempt = (
                checkpoint.last_attempt + 1
                if checkpoint.last_window_start == window_start
                else 1
            )
            checkpoint.last_window_start = window_start
            checkpoint.last_started_at = timezone.now()
            checkpoint.last_attempt = attempt
            checkpoint.status = self._checkpoint_model.Status.RUNNING
            checkpoint.last_error = ""
            checkpoint.last_duration_seconds = None
            checkpoint.save(
                update_fields=[
                    "last_window_start",
                    "last_started_at",
                    "last_attempt",
                    "status",
                    "last_error",
                    "last_duration_seconds",
                    "updated_at",
                ]
            )
        return PreparedRun(True, attempt)

    def _prepare_retry(self, job_name, window_start, attempt: int) -> None:
        with transaction.atomic():
            checkpoint, _ = self._checkpoint_model.objects.select_for_update().get_or_create(
                job_name=job_name
            )
            checkpoint.last_window_start = window_start
            checkpoint.last_started_at = timezone.now()
            checkpoint.last_attempt = attempt
            checkpoint.status = self._checkpoint_model.Status.RUNNING
            checkpoint.last_error = ""
            checkpoint.save(
                update_fields=[
                    "last_window_start",
                    "last_started_at",
                    "last_attempt",
                    "status",
                    "last_error",
                    "updated_at",
                ]
            )

    def _mark_success(
            self,
            job_name,
            attempt: int,
            duration: float,
    ) -> None:
        with transaction.atomic():
            checkpoint, _ = self._checkpoint_model.objects.select_for_update().get_or_create(
                job_name=job_name
            )
            checkpoint.last_completed_at = timezone.now()
            checkpoint.last_attempt = attempt
            checkpoint.status = self._checkpoint_model.Status.SUCCESS
            checkpoint.last_error = ""
            checkpoint.last_duration_seconds = duration
            checkpoint.save(
                update_fields=[
                    "last_completed_at",
                    "last_attempt",
                    "status",
                    "last_error",
                    "last_duration_seconds",
                    "updated_at",
                ]
            )
        logger.info(
            "Job %s succeeded on attempt %s in %.2fs",
            job_name,
            attempt,
            duration,
        )

    def _record_attempt_failure(
            self,
            job_name,
            attempt: int,
            duration: float,
            exc: Exception,
            *,
            final: bool,
    ) -> None:
        with transaction.atomic():
            checkpoint, _ = self._checkpoint_model.objects.select_for_update().get_or_create(
                job_name=job_name
            )
            checkpoint.last_attempt = attempt
            checkpoint.last_error = self._truncate_error(repr(exc))
            checkpoint.last_duration_seconds = duration
            update_fields = [
                "last_attempt",
                "last_error",
                "last_duration_seconds",
                "updated_at",
            ]
            if final:
                checkpoint.last_completed_at = timezone.now()
                checkpoint.status = self._checkpoint_model.Status.FAILED
                update_fields.extend(["last_completed_at", "status"])
            checkpoint.save(update_fields=update_fields)
        if final:
            logger.error(
                "Job %s failed after %s attempt(s)",
                job_name,
                attempt,
            )

    def _mark_skipped(self, job_name, window_start, unmet: Iterable[str]) -> None:
        reason = ", ".join(sorted(unmet)) or "unknown dependency state"
        with transaction.atomic():
            checkpoint, _ = (
                self._checkpoint_model.objects.select_for_update().get_or_create(
                    job_name=job_name
                )
            )
            checkpoint.last_window_start = window_start
            now = timezone.now()
            checkpoint.last_started_at = now
            checkpoint.last_completed_at = now
            checkpoint.last_attempt = 0
            checkpoint.status = self._checkpoint_model.Status.SKIPPED
            checkpoint.last_error = f"Skipped due to unmet dependencies: {reason}"
            checkpoint.last_duration_seconds = 0.0
            checkpoint.save(
                update_fields=[
                    "last_window_start",
                    "last_started_at",
                    "last_completed_at",
                    "last_attempt",
                    "status",
                    "last_error",
                    "last_duration_seconds",
                    "updated_at",
                ]
            )
        logger.warning("Job %s skipped; unmet dependencies: %s",
                       job_name, reason)

    def _truncate_error(self, error: str, limit: int = 2000) -> str:
        if len(error) <= limit:
            return error
        return f"{error[: limit - 3]}..."

    @staticmethod
    def _unmet_dependencies(
            dependencies: Iterable[str],
            results: Dict[str, JobExecutionResult],
    ) -> Iterable[str]:
        unmet: list[str] = []
        for dep in dependencies:
            if dep not in results or results[dep].status != EtlJobCheckpoint.Status.SUCCESS:
                unmet.append(dep)
        return unmet
