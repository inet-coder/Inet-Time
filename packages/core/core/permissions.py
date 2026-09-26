from core.db.models import AdminRole


def has_permission(role: AdminRole, key: str) -> bool:
    if role.permissions.get("all"):
        return True
    return bool(role.permissions.get(key))
