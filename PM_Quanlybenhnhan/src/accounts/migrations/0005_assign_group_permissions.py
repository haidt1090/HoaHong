"""
Migration kept as a placeholder — permission assignment is now handled by
the post_migrate signal in accounts/signals.py.

This approach avoids the issue where ContentTypes/Permissions don't exist
when RunPython executes during migration.
"""

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_staffassignment"),
    ]

    operations = [
        # No-op: permissions are assigned by accounts.signals.assign_group_permissions
    ]
