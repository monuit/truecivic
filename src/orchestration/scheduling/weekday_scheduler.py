"""Weekday-only scheduler for Kafka job publishing."""

from __future__ import annotations

import datetime
import logging
from typing import Iterable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..kafka.producer import JobPublisher

logger = logging.getLogger(__name__)


class WeekdayHourlyScheduler:
    """Schedule Kafka job dispatch for weekday hours."""

    def __init__(self, publisher: JobPublisher, jobs: Iterable[str]) -> None:
        self._publisher = publisher
        self._jobs = tuple(jobs)
        self._scheduler = BackgroundScheduler(timezone="UTC")

    def start(self) -> None:
        """Start scheduling weekday hourly jobs."""
        trigger = CronTrigger(day_of_week="mon-fri", minute=0)
        self._scheduler.add_job(self._dispatch_jobs,
                                trigger=trigger, id="weekday-hourly")
        self._scheduler.start()
        logger.info("Weekday hourly scheduler started")

    def shutdown(self) -> None:
        """Gracefully stop the scheduler."""
        self._scheduler.shutdown(wait=False)

    def run_fallback(self) -> None:
        """Run fallback execution for missed jobs."""
        now = datetime.datetime.utcnow()
        if now.weekday() >= 5:
            logger.debug("Fallback skip on weekend")
            return
        self._dispatch_jobs()

    def _dispatch_jobs(self) -> None:
        """Publish all configured jobs."""
        for job in self._jobs:
            self._publisher.publish(job)
            logger.debug("Scheduled job %s", job)
