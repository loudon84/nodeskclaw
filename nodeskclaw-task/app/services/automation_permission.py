from __future__ import annotations

_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({"automation:view", "automation:manage", "automation:run"}),
    "operator": frozenset({"automation:view", "automation:manage", "automation:run"}),
    "workspace_manager": frozenset({"automation:view", "automation:run"}),
    "member": frozenset({"automation:view", "automation:run"}),
    "viewer": frozenset({"automation:view"}),
}


def has_automation_permission(org_role: str | None, permission: str, *, is_super_admin: bool = False) -> bool:
    if is_super_admin:
        return True
    role = (org_role or "").strip()
    return permission in _ROLE_PERMISSIONS.get(role, frozenset())


def can_manage_automation(
    *,
    org_role: str | None,
    user_id: str,
    owner_user_id: str,
    is_super_admin: bool = False,
) -> bool:
    if is_super_admin:
        return True
    if has_automation_permission(org_role, "automation:manage", is_super_admin=is_super_admin):
        return True
    if user_id == owner_user_id and has_automation_permission(
        org_role, "automation:run", is_super_admin=is_super_admin
    ):
        return True
    return False
