"""Small permission checks and an application-controlled email approval token."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class PermissionDeniedError(PermissionError):
	"""Raised when an action is unsupported or lacks required approval."""


@dataclass(frozen=True)
class HumanApproval:
	"""A decision recorded by the application after a human review."""

	approved: bool


def record_human_approval(approved: bool) -> HumanApproval:
	"""Create an approval decision from a trusted application interaction.

	Only application code that receives a human decision should call this helper.
	The decision is passed separately from model/tool arguments.
	"""
	if not isinstance(approved, bool):
		raise TypeError("Human approval decision must be True or False.")
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

	raise PermissionDeniedError(f"Unsupported action: {action}")


def execute_action(
	action: str,
	arguments: Any,
	*,
	approval: HumanApproval | None = None,
	database_path: str | None = None,
) -> Any:
	"""Check authorization, then validate and execute one supported tool.

	The approval parameter is keyword-only and separate from tool arguments so
	model-provided fields cannot grant permission.
	"""
	check_permission(action, approval)

	# Import at call time to keep permissions independent from tool definitions
	# and make it straightforward to test whether denied actions execute.
	from app import tools

	if action == "create_support_ticket":
		return tools.create_support_ticket(arguments, database_path=database_path)
	if action == "get_ticket_status":
		from app.schemas import TicketStatusArgs

		validated = TicketStatusArgs.model_validate(arguments)
		return tools.get_ticket_status(validated.ticket_id, database_path=database_path)
	if action == "validate_email":
		return tools.validate_email(arguments)
	if action in {"simulate_support_email", "send_support_email"}:
		return tools.simulate_support_email(arguments)

	# check_permission rejects unknown actions before this point.
	raise PermissionDeniedError(f"Unsupported action: {action}")
