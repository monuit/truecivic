from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from ...scheduler import ensure_scheduler, scheduler_enabled, start_scheduler


class Command(BaseCommand):
    help = "Start the in-process weekday ETL scheduler."

    def handle(self, *args, **options):  # type: ignore[override]
        scheduler = ensure_scheduler()
        flag = getattr(settings, "ENABLE_ETL_SCHEDULER", False)
        if not scheduler_enabled(flag):
            self.stdout.write(
                self.style.WARNING(
                    "ENABLE_ETL_SCHEDULER is not enabled; running scheduler on-demand."
                )
            )
        start_scheduler()
        self.stdout.write(self.style.SUCCESS("Weekday ETL scheduler running"))
        try:
            scheduler.wait_forever()
        except KeyboardInterrupt:
            scheduler.shutdown()
            self.stdout.write(self.style.WARNING("Scheduler stopped"))
