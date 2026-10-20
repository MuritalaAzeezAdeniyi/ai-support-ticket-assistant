"""Append-only JSON Lines audit logging with deliberately limited fields."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Literal


DEFAULT_AUDIT_PATH = Path(__file__).resolve().parent.parent / "data" / "audit.jsonl"
AUDIT_PATH_ENV_VAR = "AI_SUPPORT_TICKET_AUDIT_PATH"
AuditOutcome = Literal["success", "failure", "denied", "approval_granted", "approval_rejected"]


class AuditLoggingError(RuntimeError):
	"""Raised when an audit event cannot be written safely."""


def _resolve_audit_path(audit_path: str | Path | None = None) -> Path:
	if audit_path is None:
		audit_path = os.environ.get(AUDIT_PATH_ENV_VAR, DEFAULT_AUDIT_PATH)
	return Path(audit_path).expanduser()


def write_audit_event(
	action: str,
	outcome: AuditOutcome,
	*,
	error_category: str | None = None,
	ticket_id: str | None = None,
	audit_path: str | Path | None = None,
) -> None:
	"""Append one safe event; raw arguments and message contents are never accepted."""
	event: dict[str, str] = {
		"timestamp": datetime.now(timezone.utc).isoformat(),
		"action": action,
		"outcome": outcome,
	}
	if error_category is not None:
		event["error_category"] = error_category
	if ticket_id is not None:
		event["ticket_id"] = ticket_id

	path = _resolve_audit_path(audit_path)
	try:
		path.parent.mkdir(parents=True, exist_ok=True)
		with path.open("a", encoding="utf-8", newline="\n") as audit_file:
			audit_file.write(json.dumps(event, ensure_ascii=False) + "\n")
	except (OSError, TypeError, ValueError) as error:
		raise AuditLoggingError(
			"Audit logging failed; the action outcome could not be safely recorded."
		) from error