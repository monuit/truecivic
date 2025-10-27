"""Run Kafka job consumer."""

from __future__ import annotations

from typing import Mapping

from django.core.management.base import BaseCommand

from src.orchestration.kafka.config import KafkaSettings
from src.orchestration.kafka.consumer import KafkaConsumerFactory, JobConsumer
from src.orchestration.kafka.registry import iter_job_names
from parliament import jobs


class Command(BaseCommand):
    help = "Start the Kafka consumer that executes parliament jobs."

    def handle(self, *args, **options):  # type: ignore[override]
        settings = KafkaSettings.from_env()
        consumer = KafkaConsumerFactory(settings).create()
        runner = JobConsumer(consumer, settings)

        for job_name in iter_job_names():
            runner.register(job_name, self._wrap_job(getattr(jobs, job_name)))

        self.stdout.write(self.style.SUCCESS("Kafka job consumer running"))
        runner.start()

    def _wrap_job(self, func):  # type: ignore[no-untyped-def]
        def _handler(payload: Mapping[str, object]) -> None:
            func()

        return _handler
