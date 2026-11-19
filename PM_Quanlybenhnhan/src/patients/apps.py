from __future__ import annotations

from django.apps import AppConfig


class PatientsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "patients"
    verbose_name = "Patients"

    def ready(self) -> None:
        import patients.signals  # noqa: F401
