from __future__ import annotations

import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class OrchestrationConfig(AppConfig):
    name = "parliament.orchestration"
    verbose_name = "Orchestration"

    def ready(self) -> None:  # pragma: no cover - executed during app loading
        from .scheduler import scheduler_enabled, start_scheduler

        if not scheduler_enabled(getattr(settings, "ENABLE_ETL_SCHEDULER", False)):
            return
        try:
            start_scheduler()
        except Exception:  # pragma: no cover - guard against scheduler startup failures
            logger.exception("Failed to start ETL scheduler from app config")
