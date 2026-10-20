"""Behavior tests for the SQLite-backed support assistant tools."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import TicketCreateArgs
from app.tools import (
	create_support_ticket,
	get_ticket_status,
	simulate_support_email,
	validate_email,
)


@pytest.fixture
def database_path(tmp_path):
	"""Give each test its own temporary SQLite file."""
	return tmp_path / "tickets.sqlite3"


def valid_ticket_args(**overrides: str) -> TicketCreateArgs:
	values = {
		"title": "Cannot sign in",
		"description": "The password reset link does not work.",
		"priority": "medium",
		"idempotency_key": "test-request-1",
	}
	values.update(overrides)
	return TicketCreateArgs(
		**values,
	)


def test_create_support_ticket_returns_open_ticket_with_generated_fields(database_path) -> None:
	before_creation = datetime.now(timezone.utc)

	ticket = create_support_ticket(valid_ticket_args(), database_path=database_path)

	after_creation = datetime.now(timezone.utc)
	assert ticket.ticket_id.startswith("TKT-")
	assert len(ticket.ticket_id) == 16
	assert ticket.created_at.tzinfo is not None
	assert before_creation <= ticket.created_at <= after_creation
	assert ticket.status == "open"
	assert ticket.title == "Cannot sign in"


def test_ticket_status_can_be_retrieved_by_id(database_path) -> None:
	ticket = create_support_ticket(valid_ticket_args(), database_path=database_path)

	assert get_ticket_status(ticket.ticket_id, database_path=database_path) == "open"


def test_unknown_ticket_id_raises_predictable_error(database_path) -> None:
	with pytest.raises(KeyError, match="Ticket not found: TKT-missing"):
		get_ticket_status("TKT-missing", database_path=database_path)


@pytest.mark.parametrize("ticket_id", ["", "   "])
def test_invalid_ticket_id_is_rejected(ticket_id: str, database_path) -> None:
	with pytest.raises(ValidationError):
		get_ticket_status(ticket_id, database_path=database_path)


def test_invalid_ticket_creation_arguments_are_rejected(database_path) -> None:
	with pytest.raises(ValidationError):
		create_support_ticket(
			{
				"title": " ",
				"description": "Issue details",
				"priority": "medium",
				"idempotency_key": "test-request-2",
			},
			database_path=database_path,
		)


def test_same_key_and_details_return_original_ticket(database_path) -> None:
	first = create_support_ticket(valid_ticket_args(), database_path=database_path)
	retry = create_support_ticket(valid_ticket_args(), database_path=database_path)

	assert retry.ticket_id == first.ticket_id
	assert retry.created_at == first.created_at


def test_same_key_with_different_details_fails_predictably(database_path) -> None:
	create_support_ticket(valid_ticket_args(), database_path=database_path)

	with pytest.raises(ValueError, match="different ticket details"):
		create_support_ticket(
			valid_ticket_args(title="Different issue"), database_path=database_path
		)


def test_different_keys_create_different_tickets(database_path) -> None:
	first = create_support_ticket(valid_ticket_args(), database_path=database_path)
	second = create_support_ticket(
		valid_ticket_args(idempotency_key="another-request"),
		database_path=database_path,
	)

	assert first.ticket_id != second.ticket_id


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