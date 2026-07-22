"""
Permission system for HAIOS.
Defines roles, capabilities, and per-session authorization checks.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"
    SERVICE = "service"


class ToolCategory(str, Enum):
    FILESYSTEM = "filesystem"
    SHELL = "shell"
    BROWSER = "browser"
    GIT = "git"
    MEMORY = "memory"
    WEB_SEARCH = "web_search"
    CODE_INTELLIGENCE = "code_intelligence"
    OCR_STT_TTS = "ocr_stt_tts"


# Default permissions per role
_ROLE_PERMISSIONS: dict[Role, set[ToolCategory]] = {
    Role.ADMIN: set(ToolCategory),
    Role.USER: {
        ToolCategory.FILESYSTEM,
        ToolCategory.WEB_SEARCH,
        ToolCategory.MEMORY,
        ToolCategory.CODE_INTELLIGENCE,
        ToolCategory.GIT,
    },
    Role.READONLY: {
        ToolCategory.WEB_SEARCH,
        ToolCategory.MEMORY,
    },
    Role.SERVICE: set(ToolCategory),
}


class PermissionChecker:
    """Checks whether a session role is authorized to use a tool category."""

    def is_allowed(
        self,
        role: Role,
        category: ToolCategory,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Return True if the role has permission to use the given tool category.
        Logs the permission check result.
        """
        allowed = category in _ROLE_PERMISSIONS.get(role, set())
        logger.debug(
            "permission_check",
            session_id=session_id,
            role=role.value,
            category=category.value,
            granted=allowed,
        )
        return allowed

    def require(
        self,
        role: Role,
        category: ToolCategory,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Assert that the role has permission; raise PermissionError otherwise.
        """
        if not self.is_allowed(role, category, session_id):
            logger.warning(
                "permission_denied",
                session_id=session_id,
                role=role.value,
                category=category.value,
            )
            raise PermissionError(
                f"Role '{role.value}' is not authorized to use tool category '{category.value}'"
            )


permission_checker = PermissionChecker()


def check_permission(role: Role, category: ToolCategory, session_id: Optional[str] = None) -> bool:
    """Convenience function to check permission."""
    return permission_checker.is_allowed(role, category, session_id)
