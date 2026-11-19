"""
Post-migrate signal handler to seed group permissions.

ContentTypes and Permissions are created by Django's post_migrate signal,
so we use the same mechanism to assign permissions to groups after they exist.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# ---------------------------------------------------------------------------
# Permission matrix: {group_name: {app_label.model_name: [actions]}}
# ---------------------------------------------------------------------------

# Entries for models in future apps (departments, packages, pricing) are
# included ahead of time. They are skipped gracefully until those models
# exist, and applied automatically once the owning app is migrated.
CROSS_APP = ("patients", "examinations", "cms")

GROUP_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "admin": {
        "accounts.user": ["add", "change", "delete", "view"],
        "accounts.company": ["add", "change", "delete", "view"],
        "accounts.staffassignment": ["add", "change", "delete", "view"],
        # Future models (skipped until migrated)
        "accounts.companyexampackage": ["add", "change", "delete", "view"],
        "examinations.department": ["add", "change", "delete", "view"],
        "examinations.departmenttemplate": ["add", "change", "delete", "view"],
        "examinations.exampackage": ["add", "change", "delete", "view"],
    },
    "doctor": {
        "accounts.user": ["view"],
        "accounts.company": ["view"],
        "accounts.companyexampackage": ["view"],
        "examinations.department": ["view"],
        "examinations.departmenttemplate": ["view"],
        "examinations.exampackage": ["view"],
    },
    "nurse": {
        "accounts.user": ["view"],
        "examinations.department": ["view"],
        "examinations.departmenttemplate": ["view"],
        "examinations.exampackage": ["view"],
    },
    "labtech": {
        "examinations.department": ["view"],
        "examinations.departmenttemplate": ["view"],
        "examinations.exampackage": ["view"],
    },
    "company_admin": {
        "accounts.company": ["view"],
        "accounts.companyexampackage": ["view"],
    },
}


@receiver(post_migrate)
def assign_group_permissions(sender, **kwargs) -> None:
    """
    Assign Django model permissions to role groups after migrate.

    Runs when the accounts app or any app that owns matrix models migrates.
    The assignment is idempotent (``group.permissions.add``) and gracefully
    skips models whose ContentType/Permission rows do not yet exist.
    """
    if sender.name != "accounts" and sender.name not in CROSS_APP:
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
