from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.utils import timezone

from .factory import create_coordinator
from .runner import HourlyRunCoordinator

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()
_scheduler: Optional["WeekdayHourlyEtlScheduler"] = None


def scheduler_enabled(flag) -> bool:
    if isinstance(flag, str):
        return flag.strip().lower() in {"1", "true", "yes", "on"}
    return bool(flag)


def start_scheduler() -> "WeekdayHourlyEtlScheduler":
    scheduler = ensure_scheduler()
    scheduler.start()
    return scheduler


def ensure_scheduler() -> "WeekdayHourlyEtlScheduler":
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            coordinator = create_coordinator()
            tz = getattr(settings, "ETL_SCHEDULER_TIME_ZONE",
                         settings.TIME_ZONE)
            _scheduler = WeekdayHourlyEtlScheduler(
                coordinator, timezone_name=tz)
        return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.shutdown()
            _scheduler = None


def current_window_start():
    now = timezone.now()
    return now.replace(minute=0, second=0, microsecond=0)


class WeekdayHourlyEtlScheduler:
    """APScheduler wrapper that runs the coordinator every weekday hour."""

    def __init__(
        self,
        coordinator: HourlyRunCoordinator,
        *,
        timezone_name: str = "UTC",
    ) -> None:
        self._coordinator = coordinator
        self._scheduler = BackgroundScheduler(timezone=timezone_name)
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            trigger = CronTrigger(day_of_week="mon-fri", minute=0)
            self._scheduler.add_job(
                self._run_window,
                trigger=trigger,
                id="etl-weekday-hourly",
                max_instances=1,
                coalesce=True,
            )
            self._scheduler.start()
            self._started = True
            logger.info("Weekday ETL scheduler started")
        self.run_now()

    def shutdown(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Weekday ETL scheduler stopped")

    def wait_forever(self) -> None:
        while True:  # pragma: no cover - interactive loop
            time.sleep(60)

    def run_now(self) -> None:
        self._run_window()

    def _run_window(self) -> None:
        window_start = current_window_start()
        if window_start.weekday() >= 5:
            logger.debug(
                "Skipping ETL window %s; weekend execution is disabled", window_start
            )
            return
        results = self._coordinator.run(window_start)
        summary = {
            name: {
                "status": result.status,
                "attempt": result.attempt,
                "duration": result.duration_seconds,
            }
            for name, result in results.items()
        }
        logger.info("Window %s completed with results: %s",
                    window_start, summary)
