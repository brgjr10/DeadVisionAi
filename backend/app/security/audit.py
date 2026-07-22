"""
Immutable audit logging for HAIOS.
Records every tool execution, model invocation, and permission check.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.observability.logging_config import get_logger

logger = get_logger(__name__)

_AUDIT_LOG_PATH = Path("./logs/audit.jsonl")


def _write_audit_entry(entry: dict[str, Any]) -> None:
    """Append a JSON audit entry to the audit log file (append-only)."""
    _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, default=str) + "\n"
    with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line)


class AuditLogger:
    """Append-only audit logger for security-relevant events."""

    def _base_entry(self, event_type: str, session_id: Optional[str]) -> dict[str, Any]:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "session_id": session_id,
        }

    def log_tool_execution(
        self,
        session_id: Optional[str],
        tool_id: str,
        params: dict[str, Any],
        outcome: str,
    ) -> None:
        """Log a tool execution event. Params are hashed to avoid leaking sensitive data."""
        params_hash = hashlib.sha256(
            json.dumps(params, sort_keys=True, default=str).encode()
        ).hexdigest()
        entry = self._base_entry("tool_execution", session_id)
        entry.update({"tool_id": tool_id, "params_hash": params_hash, "outcome": outcome})
        _write_audit_entry(entry)
        logger.info("audit_tool_execution", **entry)

    def log_model_invocation(
        self,
        session_id: Optional[str],
        provider_id: str,
        model_id: str,
        tokens: int,
    ) -> None:
        """Log a model invocation event."""
        entry = self._base_entry("model_invocation", session_id)
        entry.update(
            {"provider_id": provider_id, "model_id": model_id, "tokens": tokens}
        )
        _write_audit_entry(entry)
        logger.info("audit_model_invocation", **entry)

    def log_permission_check(
        self,
        session_id: Optional[str],
        action: str,
        granted: bool,
    ) -> None:
        """Log a permission check event."""
        entry = self._base_entry("permission_check", session_id)
        entry.update({"action": action, "granted": granted})
        _write_audit_entry(entry)
        logger.debug("audit_permission_check", **entry)

    def log_unauthorized_attempt(
        self,
        session_id: Optional[str],
        action: str,
    ) -> None:
        """Log an unauthorized access attempt."""
        entry = self._base_entry("unauthorized_attempt", session_id)
        entry.update({"action": action})
        _write_audit_entry(entry)
        logger.warning("audit_unauthorized_attempt", **entry)


audit_logger = AuditLogger()
