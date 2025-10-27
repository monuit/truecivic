"""Kafka producer utilities."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping

from confluent_kafka import Producer

from .config import KafkaSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KafkaProducerFactory:
    """Factory for creating Kafka producers with shared configuration."""

    settings: KafkaSettings

    def create(self) -> Producer:
        """Instantiate a configured Kafka producer."""
        config = {
            "bootstrap.servers": self.settings.bootstrap_servers,
            "client.id": self.settings.client_id,
            "enable.idempotence": True,
            "compression.type": "snappy",
            "linger.ms": 20,
        }
        return Producer(config)


class JobPublisher:
    """Publish job payloads onto the Kafka jobs topic."""

    def __init__(self, producer: Producer, settings: KafkaSettings) -> None:
        self._producer = producer
        self._settings = settings

    def publish(self, job_name: str, payload: Mapping[str, Any] | None = None) -> None:
        """Serialize and publish a job payload."""
        message = {
            "job": job_name,
            "payload": payload or {},
        }
        logger.debug("Publishing job %s", message)
        self._producer.produce(
            self._settings.jobs_topic,
            value=json.dumps(message).encode("utf-8"),
        )
        self._producer.flush(timeout=5.0)
