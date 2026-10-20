"""Simple Python implementations of the support assistant tools."""

from collections.abc import Mapping
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import (
	EmailValidationArgs,
	SimulatedSupportEmailArgs,
	TicketCreateArgs,
	TicketRecord,
	TicketStatus,
	TicketStatusArgs,
)


# This in-memory store is temporary; a later stage will replace it with SQLite.
_tickets: dict[str, TicketRecord] = {}


def reset_ticket_store() -> None:
	"""Remove all in-memory tickets, mainly to keep tests independent."""
	_tickets.clear()


def create_support_ticket(
	arguments: TicketCreateArgs | Mapping[str, object],
) -> TicketRecord:
	"""Validate the request and create an open ticket in memory."""
	args = TicketCreateArgs.model_validate(arguments)
	ticket = TicketRecord(
		ticket_id=f"TKT-{uuid4().hex[:12]}",
		title=args.title,
		description=args.description,
		priority=args.priority,
		status="open",
		created_at=datetime.now(timezone.utc),
	)
	_tickets[ticket.ticket_id] = ticket
	return ticket


def get_ticket_status(ticket_id: str) -> TicketStatus:
	"""Return the stored status, or raise a clear error for an unknown ID."""
	args = TicketStatusArgs.model_validate({"ticket_id": ticket_id})
	try:
		return _tickets[args.ticket_id].status
	except KeyError:
		raise KeyError(f"Ticket not found: {args.ticket_id}") from None


def validate_email(arguments: EmailValidationArgs | Mapping[str, object]) -> bool:
	"""Return True for syntactically valid email input; does not check existence."""
	EmailValidationArgs.model_validate(arguments)
	return True


def simulate_support_email(
	arguments: SimulatedSupportEmailArgs | Mapping[str, object],
) -> str:
	"""Describe the proposed email without sending it or deciding approval."""
	args = SimulatedSupportEmailArgs.model_validate(arguments)
	return (
		"Email prepared for simulation only; it was not sent. "
		f"To: {args.recipient}; Subject: {args.subject}; Body: {args.body}"
	)
