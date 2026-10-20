"""Behavior tests for the in-memory support assistant tools."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import TicketCreateArgs
from app.tools import (
	create_support_ticket,
	get_ticket_status,
	reset_ticket_store,
	simulate_support_email,
	validate_email,
)


@pytest.fixture(autouse=True)
def clean_ticket_store() -> None:
	"""Start and finish each test with an empty ticket store."""
	reset_ticket_store()
	yield
	reset_ticket_store()


def valid_ticket_args() -> TicketCreateArgs:
	return TicketCreateArgs(
		title="Cannot sign in",
		description="The password reset link does not work.",
		priority="medium",
		idempotency_key="test-request-1",
	)


def test_create_support_ticket_returns_open_ticket_with_generated_fields() -> None:
	before_creation = datetime.now(timezone.utc)

	ticket = create_support_ticket(valid_ticket_args())

	after_creation = datetime.now(timezone.utc)
	assert ticket.ticket_id.startswith("TKT-")
	assert len(ticket.ticket_id) == 16
	assert ticket.created_at.tzinfo is not None
	assert before_creation <= ticket.created_at <= after_creation
	assert ticket.status == "open"
	assert ticket.title == "Cannot sign in"


def test_ticket_status_can_be_retrieved_by_id() -> None:
	ticket = create_support_ticket(valid_ticket_args())

	assert get_ticket_status(ticket.ticket_id) == "open"


def test_unknown_ticket_id_raises_predictable_error() -> None:
	with pytest.raises(KeyError, match="Ticket not found: TKT-missing"):
		get_ticket_status("TKT-missing")


@pytest.mark.parametrize("ticket_id", ["", "   "])
def test_invalid_ticket_id_is_rejected(ticket_id: str) -> None:
	with pytest.raises(ValidationError):
		get_ticket_status(ticket_id)


def test_invalid_ticket_creation_arguments_are_rejected() -> None:
	with pytest.raises(ValidationError):
		create_support_ticket(
			{
				"title": " ",
				"description": "Issue details",
				"priority": "medium",
				"idempotency_key": "test-request-2",
			}
		)


def test_validate_email_accepts_valid_syntax() -> None:
	assert validate_email({"email": "person@example.com"}) is True


@pytest.mark.parametrize("email", ["not-an-email", "person@", "@example.com"])
def test_validate_email_rejects_invalid_syntax(email: str) -> None:
	with pytest.raises(ValidationError):
		validate_email({"email": email})


def test_simulated_email_is_prepared_without_sending() -> None:
	result = simulate_support_email(
		{
			"recipient": "person@example.com",
			"subject": "Ticket update",
			"body": "We received your request.",
		}
	)

	assert "not sent" in result
	assert "person@example.com" in result
	assert "Ticket update" in result
	assert "We received your request." in result


def test_simulated_email_rejects_invalid_request() -> None:
	with pytest.raises(ValidationError):
		simulate_support_email(
			{"recipient": "invalid", "subject": "Update", "body": "Message"}
		)