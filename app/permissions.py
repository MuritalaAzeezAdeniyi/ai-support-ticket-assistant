"""Small permission checks and an application-controlled email approval token."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.audit import AuditLoggingError, AuditOutcome, write_audit_event
from app.storage import IdempotencyConflictError

class PermissionDeniedError(PermissionError):
	"""Raised when an action is unsupported or lacks required approval."""


class ActionExecutionError(RuntimeError):
	"""Safe, predictable failure returned by the guarded execution path."""

	def __init__(self, category: str, message: str) -> None:
		super().__init__(message)
		self.category = category


@dataclass(frozen=True)
class HumanApproval:
	"""A decision recorded by the application after a human review."""

	approved: bool


def record_human_approval(
	approved: bool,
	*,
	audit_path: str | Path | None = None,
) -> HumanApproval:
	"""Create an approval decision from a trusted application interaction.

	Only application code that receives a human decision should call this helper.
	The decision is passed separately from model/tool arguments.
	"""
	if not isinstance(approved, bool):
		raise TypeError("Human approval decision must be True or False.")
	try:
		write_audit_event(
			"simulate_support_email",
			"approval_granted" if approved else "approval_rejected",
			audit_path=audit_path,
		)
	except AuditLoggingError as error:
		raise AuditLoggingError(
			"The approval decision was not recorded, so no approval was issued."
		) from error
	return HumanApproval(approved=approved)


def check_permission(action: str, approval: HumanApproval | None = None) -> None:
	"""Allow ordinary validated tools and require human approval for email."""
	if action in {"create_support_ticket", "get_ticket_status", "validate_email"}:
		return

	if action in {"simulate_support_email", "send_support_email"}:
		if approval is None:
			raise PermissionDeniedError(
				"Simulated support email is denied until a human approves it."
			)
		if not isinstance(approval, HumanApproval):
			raise PermissionDeniedError("A trusted human approval decision is required.")
		if not approval.approved:
			raise PermissionDeniedError("Simulated support email was rejected by a human.")
		return

	raise PermissionDeniedError("Unsupported action.")


def execute_action(
	action: str,
	arguments: Any,
	*,
	approval: HumanApproval | None = None,
	database_path: str | Path | None = None,
	audit_path: str | Path | None = None,
) -> Any:
	"""Check authorization, then validate and execute one supported tool.

	The approval parameter is keyword-only and separate from tool arguments so
	model-provided fields cannot grant permission.
	"""
	try:
		check_permission(action, approval)
	except PermissionDeniedError as error:
		audit_action = action if action in {
			"create_support_ticket",
			"get_ticket_status",
			"validate_email",
			"simulate_support_email",
			"send_support_email",
		} else "unknown"
		try:
			write_audit_event(
				audit_action,
				"denied",
				error_category="permission_denied",
				audit_path=audit_path,
			)
		except AuditLoggingError as audit_error:
			raise AuditLoggingError(
				"The action was denied, but the denial could not be recorded."
			) from audit_error
		if audit_action == "unknown":
			raise PermissionDeniedError("Unsupported action.") from None
		raise error from None

	# Import at call time to keep permissions independent from tool definitions
	# and make it straightforward to test whether denied actions execute.
	from app import tools

	try:
		if action == "create_support_ticket":
			result = tools.create_support_ticket(arguments, database_path=database_path)
		elif action == "get_ticket_status":
			from app.schemas import TicketStatusArgs

			validated = TicketStatusArgs.model_validate(arguments)
			result = tools.get_ticket_status(
				validated.ticket_id, database_path=database_path
			)
		elif action == "validate_email":
			result = tools.validate_email(arguments)
		elif action in {"simulate_support_email", "send_support_email"}:
			result = tools.simulate_support_email(arguments)
		else:
			# check_permission rejects unknown actions before this point.
			raise PermissionDeniedError(f"Unsupported action: {action}")
	except Exception as error:
		category = _error_category(error)
		try:
			write_audit_event(
				action,
				"failure",
				error_category=category,
				audit_path=audit_path,
			)
		except AuditLoggingError as audit_error:
			raise AuditLoggingError(
				"The action failed, and its failure could not be recorded in the audit log."
			) from audit_error
		raise ActionExecutionError(category, _safe_error_message(category)) from None

	try:
		from app.schemas import TicketRecord

		ticket_id = result.ticket_id if isinstance(result, TicketRecord) else None
		write_audit_event(
			action, "success", ticket_id=ticket_id, audit_path=audit_path
		)
	except AuditLoggingError as error:
		raise AuditLoggingError(
			"The action may have completed, but its success could not be recorded. "
			"Verify the result before retrying."
		) from error
	return result


def _error_category(error: Exception) -> str:
	"""Map expected exceptions to safe, stable audit categories."""
	if isinstance(error, ValidationError):
		return "invalid_arguments"
	if isinstance(error, IdempotencyConflictError):
		return "idempotency_conflict"
	if isinstance(error, KeyError):
		return "ticket_not_found"
	if isinstance(error, PermissionDeniedError):
		return "permission_denied"
	return "tool_execution_error"


def _safe_error_message(category: str) -> str:
	"""Return a user-safe message without echoing raw arguments or internals."""
	messages = {
		"invalid_arguments": "The action arguments are invalid.",
		"idempotency_conflict": "This request key was already used with different ticket details.",
		"ticket_not_found": "The requested ticket was not found.",
		"permission_denied": "The action is not permitted.",
		"tool_execution_error": "The action could not be completed due to an internal error.",
	}
	return messages.get(category, messages["tool_execution_error"])
