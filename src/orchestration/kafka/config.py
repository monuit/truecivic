"""Kafka configuration helpers."""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass(frozen=True)
class KafkaSettings:
    """Strongly typed Kafka configuration."""

    bootstrap_servers: str
    public_bootstrap_servers: Optional[str]
    client_id: str
    group_id: str
    jobs_topic: str

    @staticmethod
    def from_env() -> "KafkaSettings":
        """Load settings from environment variables."""
        internal = os.getenv("KAFKA_URL")
        if not internal:
            raise RuntimeError("KAFKA_URL must be set for Kafka connectivity")

        return KafkaSettings(
            bootstrap_servers=internal,
            public_bootstrap_servers=os.getenv("KAFKA_PUBLIC_URL"),
            client_id=os.getenv("KAFKA_CLIENT_ID", "truecivic-backend"),
            group_id=os.getenv("KAFKA_GROUP_ID", "truecivic-jobs"),
            jobs_topic=os.getenv("KAFKA_JOBS_TOPIC", "truecivic.jobs"),
        )
