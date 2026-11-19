"""Run the diagnosis scan manually: ``python manage.py scan_diagnosis``."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from diagnosis.tasks import scan_diagnosis_task


class Command(BaseCommand):
    help = "Auto-fill work_fitness/disease/consultation for unconcluded examinations."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Max number of examinations to scan.",
        )

    def handle(self, *args, **options) -> None:
        result = scan_diagnosis_task(limit=options["limit"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Scan xong: {result['scanned']} đã xét, {result['filled']} đã điền."
            )
        )
