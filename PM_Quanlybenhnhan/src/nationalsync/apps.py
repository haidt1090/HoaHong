from django.apps import AppConfig


class NationalSyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nationalsync"
    verbose_name = "National Health Portal Sync"
