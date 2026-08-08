"""Role / visibility ACL templates."""

from __future__ import annotations

from app.models.enums import (
    FilePermission,
    KbPermission,
    SetPermission,
    SubjectType,
    UiRole,
    Visibility,
)

KB_ROLE_PERMISSIONS: dict[str, list[str]] = {
    UiRole.viewer.value: [KbPermission.read.value],
    UiRole.editor.value: [
        KbPermission.read.value,
        KbPermission.upload.value,
        KbPermission.update.value,
    ],
    UiRole.manager.value: [
        KbPermission.read.value,
        KbPermission.upload.value,
        KbPermission.update.value,
        KbPermission.delete.value,
        KbPermission.manage.value,
        KbPermission.manage_acl.value,
    ],
}

FILE_ROLE_PERMISSIONS: dict[str, list[str]] = {
    UiRole.viewer.value: [FilePermission.read.value, FilePermission.download.value],
    UiRole.editor.value: [
        FilePermission.read.value,
        FilePermission.download.value,
        FilePermission.update.value,
    ],
    UiRole.manager.value: [
        FilePermission.read.value,
        FilePermission.download.value,
        FilePermission.update.value,
        FilePermission.delete.value,
        FilePermission.manage_acl.value,
    ],
}

SET_ROLE_PERMISSIONS: dict[str, list[str]] = {
    UiRole.viewer.value: [SetPermission.read.value, SetPermission.use.value],
    UiRole.editor.value: [
        SetPermission.read.value,
        SetPermission.use.value,
        SetPermission.update.value,
    ],
    UiRole.manager.value: [
        SetPermission.read.value,
        SetPermission.use.value,
        SetPermission.update.value,
        SetPermission.manage.value,
        SetPermission.delete.value,
        SetPermission.manage_acl.value,
    ],
}


def visibility_acl_specs(
    visibility: str,
    *,
    org_id: str,
    department: str | None,
    permissions: list[str],
) -> list[tuple[str, str, str]]:
    """Return (subject_type, subject_id, permission) for visibility templates."""
    if visibility == Visibility.private.value:
        return []
    if visibility == Visibility.department.value:
        if not department:
            return []
        return [(SubjectType.department.value, department, p) for p in permissions]
    if visibility == Visibility.organization.value:
        return [(SubjectType.organization.value, org_id, p) for p in permissions]
    return []


ALLOWED_MEMBER_ROLES = {"member", "operator", "admin"}
