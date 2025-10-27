"""Run the weekday Kafka scheduler."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from src.orchestration.kafka.config import KafkaSettings
from src.orchestration.kafka.producer import JobPublisher, KafkaProducerFactory
from src.orchestration.kafka.registry import iter_job_names
from src.orchestration.scheduling.weekday_scheduler import WeekdayHourlyScheduler


class Command(BaseCommand):
    help = "Start the Kafka scheduler that dispatches weekday hourly jobs."

    def handle(self, *args, **options):  # type: ignore[override]
        settings = KafkaSettings.from_env()
        producer = KafkaProducerFactory(settings).create()
        publisher = JobPublisher(producer, settings)
        scheduler = WeekdayHourlyScheduler(publisher, tuple(iter_job_names()))
        scheduler.start()

        self.stdout.write(self.style.SUCCESS(
            "Kafka weekday scheduler running"))
        try:
            self._wait_forever()
        except KeyboardInterrupt:
            scheduler.shutdown()

    def _wait_forever(self) -> None:
        import time

        while True:
            time.sleep(60)
