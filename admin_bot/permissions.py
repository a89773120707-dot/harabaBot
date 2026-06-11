"""Проверка доступа к админ-боту."""

from admin_bot.config import OWNER_ID, ADMIN_IDS


def is_owner(user_id: int) -> bool:
    """Owner — полный доступ, нельзя отключить."""
    return user_id == OWNER_ID


def is_admin(user_id: int) -> bool:
    """Admin — доступ к админке. Owner всегда admin."""
    return is_owner(user_id) or user_id in ADMIN_IDS


def can_modify_user(actor_id: int, target_id: int) -> tuple[bool, str]:
    """Проверить, может ли actor_id изменять target_id.

    Returns:
        (can_modify, reason)
    """
    if not is_admin(actor_id):
        return False, "⛔ Нет доступа."

    if is_owner(target_id):
        return False, "⛔ Owner нельзя отключить, удалить или поставить на паузу."

    return True, ""
