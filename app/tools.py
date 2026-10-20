"""Simple Python implementations of the support assistant tools."""

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.schemas import (
	EmailValidationArgs,
	SimulatedSupportEmailArgs,
	TicketCreateArgs,
	TicketRecord,
	TicketStatus,
	TicketStatusArgs,
)
from app.storage import create_or_get_ticket, get_ticket


def create_support_ticket(
	arguments: TicketCreateArgs | Mapping[str, object],
	*,
	database_path: str | Path | None = None,
) -> TicketRecord:
	"""Validate the request and create or retrieve its SQLite ticket."""
	args = TicketCreateArgs.model_validate(arguments)
	ticket = TicketRecord(
		ticket_id=f"TKT-{uuid4().hex[:12]}",
		title=args.title,
		description=args.description,
		priority=args.priority,
		status="open",
		created_at=datetime.now(timezone.utc),
	)
	return create_or_get_ticket(ticket, args.idempotency_key, database_path)


def get_ticket_status(
	ticket_id: str,
	*,
	database_path: str | Path | None = None,
) -> TicketStatus:
	"""Return the stored status, or raise a clear error for an unknown ID."""
	args = TicketStatusArgs.model_validate({"ticket_id": ticket_id})
	ticket = get_ticket(args.ticket_id, database_path)
	if ticket is None:
		raise KeyError(f"Ticket not found: {args.ticket_id}")
	return ticket.status


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
