"""Validation tests for support assistant Pydantic models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import (
	EmailValidationArgs,
	SimulatedSupportEmailArgs,
	TicketCreateArgs,
	TicketRecord,
	TicketStatusArgs,
)


def valid_ticket_args(**overrides: object) -> dict[str, object]:
	"""Return a valid ticket-creation payload with optional overrides."""
	values: dict[str, object] = {
		"title": "Cannot sign in",
		"description": "The password reset link does not work.",
		"priority": "medium",
		"idempotency_key": "request-123",
	}
	values.update(overrides)
	return values


def test_valid_ticket_creation_arguments_are_trimmed() -> None:
	args = TicketCreateArgs.model_validate(
		valid_ticket_args(title="  Cannot sign in  ", description="  Login issue  ")
	)

	assert args.title == "Cannot sign in"
	assert args.description == "Login issue"
	assert args.priority == "medium"


@pytest.mark.parametrize("field", ["title", "description"])
def test_missing_required_ticket_text_is_rejected(field: str) -> None:
	payload = valid_ticket_args()
	del payload[field]

	with pytest.raises(ValidationError):
		TicketCreateArgs.model_validate(payload)


@pytest.mark.parametrize("field", ["title", "description"])
@pytest.mark.parametrize("value", ["", "   "])
def test_empty_ticket_text_is_rejected(field: str, value: str) -> None:
	with pytest.raises(ValidationError):
		TicketCreateArgs.model_validate(valid_ticket_args(**{field: value}))


def test_ticket_text_over_maximum_length_is_rejected() -> None:
	with pytest.raises(ValidationError):
		TicketCreateArgs.model_validate(valid_ticket_args(title="x" * 121))
	with pytest.raises(ValidationError):
		TicketCreateArgs.model_validate(valid_ticket_args(description="x" * 2001))


@pytest.mark.parametrize("priority", ["low", "medium", "high", "critical"])
def test_supported_priorities_are_accepted(priority: str) -> None:
	args = TicketCreateArgs.model_validate(valid_ticket_args(priority=priority))

	assert args.priority == priority


def test_unsupported_priority_is_rejected() -> None:
	with pytest.raises(ValidationError):
		TicketCreateArgs.model_validate(valid_ticket_args(priority="urgent"))


@pytest.mark.parametrize("status", ["open", "in_progress", "resolved"])
def test_supported_ticket_statuses_are_accepted(status: str) -> None:
	ticket = TicketRecord.model_validate(
		{
			"ticket_id": "T-123",
			"title": "Cannot sign in",
			"description": "Login issue",
			"priority": "high",
			"status": status,
			"created_at": datetime.now(timezone.utc),
		}
	)

	assert ticket.status == status


def test_unsupported_ticket_status_is_rejected() -> None:
	with pytest.raises(ValidationError):
		TicketRecord.model_validate(
			{
				"ticket_id": "T-123",
				"title": "Cannot sign in",
				"description": "Login issue",
				"priority": "high",
				"status": "closed",
				"created_at": datetime.now(timezone.utc),
			}
		)


def test_ticket_status_lookup_requires_non_empty_ticket_id() -> None:
	with pytest.raises(ValidationError):
		TicketStatusArgs.model_validate({})
	with pytest.raises(ValidationError):
		TicketStatusArgs.model_validate({"ticket_id": "   "})


def test_valid_email_syntax_is_accepted() -> None:
	args = EmailValidationArgs.model_validate({"email": "person@example.com"})

	assert str(args.email) == "person@example.com"


@pytest.mark.parametrize("email", ["", "not-an-email", "missing-domain@", "@example.com"])
def test_malformed_email_syntax_is_rejected(email: str) -> None:
	with pytest.raises(ValidationError):
		EmailValidationArgs.model_validate({"email": email})


def test_simulated_email_accepts_valid_recipient_and_content() -> None:
	args = SimulatedSupportEmailArgs.model_validate(
		{
			"recipient": "person@example.com",
			"subject": "  Ticket update  ",
			"body": "  We received your request.  ",
		}
	)

	assert args.subject == "Ticket update"
	assert args.body == "We received your request."


def test_invalid_simulated_email_recipient_is_rejected() -> None:
	with pytest.raises(ValidationError):
		SimulatedSupportEmailArgs.model_validate(
			{"recipient": "invalid", "subject": "Update", "body": "Message"}
		)


@pytest.mark.parametrize("field", ["subject", "body"])
@pytest.mark.parametrize("value", ["", "   "])
def test_empty_simulated_email_content_is_rejected(field: str, value: str) -> None:
	payload = {"recipient": "person@example.com", "subject": "Update", "body": "Message"}
	payload[field] = value

	with pytest.raises(ValidationError):
		SimulatedSupportEmailArgs.model_validate(payload)


@pytest.mark.parametrize(
	("model", "payload", "forbidden_field"),
	[
		(TicketCreateArgs, valid_ticket_args(ticket_id="AI-123"), "ticket_id"),
		(
			TicketCreateArgs,
			valid_ticket_args(created_at=datetime.now(timezone.utc)),
			"created_at",
		),
		(
			SimulatedSupportEmailArgs,
			{"recipient": "person@example.com", "subject": "Hi", "body": "Hello", "approved": True},
			"approved",
		),
	],
)
def test_ai_cannot_supply_application_controlled_fields(
	model: type[TicketCreateArgs] | type[SimulatedSupportEmailArgs],
	payload: dict[str, object],
	forbidden_field: str,
) -> None:
	with pytest.raises(ValidationError, match=forbidden_field):
		model.model_validate(payload)