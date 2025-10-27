"""Execute fallback dispatch for missed Kafka jobs."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from src.orchestration.kafka.config import KafkaSettings
from src.orchestration.kafka.producer import JobPublisher, KafkaProducerFactory
from src.orchestration.kafka.registry import iter_job_names
from src.orchestration.scheduling.weekday_scheduler import WeekdayHourlyScheduler


class Command(BaseCommand):
    help = "Trigger a single fallback dispatch cycle for Kafka jobs."

    def handle(self, *args, **options):  # type: ignore[override]
        settings = KafkaSettings.from_env()
        producer = KafkaProducerFactory(settings).create()
        publisher = JobPublisher(producer, settings)
        scheduler = WeekdayHourlyScheduler(publisher, tuple(iter_job_names()))
        scheduler.run_fallback()
        self.stdout.write(self.style.SUCCESS("Fallback dispatch completed"))
