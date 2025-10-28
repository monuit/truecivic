from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from ...factory import create_coordinator
from ...models import EtlJobCheckpoint
from ...scheduler import current_window_start


class Command(BaseCommand):
    help = "Execute the ETL pipeline once for the current hourly window."

    def handle(self, *args, **options):  # type: ignore[override]
        coordinator = create_coordinator()
        window_start = current_window_start()
        results = coordinator.run(window_start)
        formatted = []
        failed = []
        skipped = []
        for name, result in results.items():
            duration = (
                f"{result.duration_seconds:.2f}s"
                if result.duration_seconds is not None
                else "-"
            )
            formatted.append(
                f"{name}: status={result.status}, attempt={result.attempt}, duration={duration}"
            )
            if result.status == EtlJobCheckpoint.Status.FAILED:
                failed.append(name)
            if result.status == EtlJobCheckpoint.Status.SKIPPED:
                skipped.append(name)
        self.stdout.write(f"Window {window_start}:\n" + "\n".join(formatted))
        if failed:
            raise CommandError(f"Jobs failed: {', '.join(failed)}")
        if skipped:
            raise CommandError(
                f"Jobs skipped due to unmet dependencies: {', '.join(skipped)}"
            )
        self.stdout.write(self.style.SUCCESS(
            "ETL window completed successfully"))
