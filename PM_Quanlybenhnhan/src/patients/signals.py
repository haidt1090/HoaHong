"""
Post-migrate signal handler to seed patient-related group permissions.

Mirrors accounts.signals but scoped to the patients app so the permission
matrix (Sprint 2a) stays in sync for the Patient model.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# {group_name: {app_label.model_name: [actions]}}
GROUP_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "admin": {
        "patients.patient": ["add", "change", "delete", "view"],
    },
    "doctor": {
        "patients.patient": ["view"],
    },
    "nurse": {
        "patients.patient": ["view"],
    },
    "labtech": {
        "patients.patient": ["view"],
    },
    "company_admin": {
        "patients.patient": ["view"],
    },
}


@receiver(post_migrate)
def assign_patient_group_permissions(sender, **kwargs) -> None:
    """Assign Patient model permissions to role groups after migrate."""
    if sender.name != "patients":
        return

    for group_name, model_perms in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for model_label, actions in model_perms.items():
            app_label, model_name = model_label.split(".")
            try:
                ct = ContentType.objects.get(app_label=app_label, model=model_name)
            except ContentType.DoesNotExist:
                continue
            for action in actions:
                codename = f"{action}_{model_name}"
                try:
                    perm = Permission.objects.get(codename=codename, content_type=ct)
                    group.permissions.add(perm)
                except Permission.DoesNotExist:
                    continue
