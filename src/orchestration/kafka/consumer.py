"""Kafka consumer for job dispatch."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable, Mapping

from confluent_kafka import Consumer, KafkaException

from .config import KafkaSettings

logger = logging.getLogger(__name__)

JobHandler = Callable[[Mapping[str, object]], None]


@dataclass(frozen=True)
class KafkaConsumerFactory:
    """Factory for building Kafka consumers."""

    settings: KafkaSettings

    def create(self) -> Consumer:
        """Instantiate a configured Kafka consumer."""
        config = {
            "bootstrap.servers": self.settings.bootstrap_servers,
            "group.id": self.settings.group_id,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
        return Consumer(config)


class JobConsumer:
    """Consume job events and dispatch them to registered handlers."""

    def __init__(self, consumer: Consumer, settings: KafkaSettings) -> None:
        self._consumer = consumer
        self._settings = settings
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_name: str, handler: JobHandler) -> None:
        """Register a handler for a specific job."""
        self._handlers[job_name] = handler

    def start(self) -> None:
        """Start the consumer loop."""
        self._consumer.subscribe([self._settings.jobs_topic])
        try:
            while True:
                message = self._consumer.poll(timeout=1.0)
                if message is None:
                    continue
                if message.error():
                    raise KafkaException(message.error())
                self._handle_message(message.value())
                self._consumer.commit(asynchronous=False)
        finally:
            self._consumer.close()

    def _handle_message(self, payload: bytes) -> None:
        """Dispatch a Kafka message to the registered handler."""
        data = json.loads(payload.decode("utf-8"))
        job_name = data.get("job")
        handler = self._handlers.get(job_name)
        if not handler:
            logger.warning("No handler registered for job %s", job_name)
            return
        handler(data.get("payload") or {})
