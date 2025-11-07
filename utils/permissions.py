"""Centralized permission helpers for scheduler commands."""
from typing import Iterable, Optional, Set

import discord

# These are the two elevated roles requested by the team.
_DEFAULT_PRIVILEGED_ROLES = {"tank ops", "server admin"}

# Shared human-friendly text for error responses.
PERMISSION_REQUIREMENT_TEXT = (
    "Tank Ops or Server Admin role, or Manage Events / Manage Guild permission"
)
PERMISSION_DENIED_MESSAGE = f"❌ Requires {PERMISSION_REQUIREMENT_TEXT}."


def _normalize_roles(role_names: Optional[Iterable[str]]) -> Set[str]:
    """Return a case-insensitive set from an iterable of role names."""
    if not role_names:
        return set()
    return {name.lower() for name in role_names if isinstance(name, str)}


def has_scheduler_privileges(
    member: discord.Member, allowed_roles: Optional[Iterable[str]] = None
) -> bool:
    """
    Determine whether the invoking member can run privileged commands.

    A member is authorized when they have either:
    * The Tank Ops or Server Admin role (or a server-configured override)
    * The Manage Events or Manage Guild permission
    """
    if not isinstance(member, discord.Member):
        return False

    privileged_roles = (
        _normalize_roles(allowed_roles) or _DEFAULT_PRIVILEGED_ROLES
    )
    member_roles = {role.name.lower() for role in getattr(member, "roles", [])}

    if privileged_roles & member_roles:
        return True

    perms = getattr(member, "guild_permissions", None)
    return bool(perms and (perms.manage_events or perms.manage_guild))


__all__ = [
    "has_scheduler_privileges",
    "PERMISSION_REQUIREMENT_TEXT",
    "PERMISSION_DENIED_MESSAGE",
]
