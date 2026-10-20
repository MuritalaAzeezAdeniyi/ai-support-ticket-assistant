"""Tests for permission checks at the tool execution boundary."""

import pytest
from pydantic import ValidationError

from app.permissions import (
	PermissionDeniedError,
	execute_action,
	record_human_approval,
)


def ticket_arguments(key: str = "permission-test") -> dict[str, str]:
	return {
		"title": "Cannot sign in",
		"description": "The password reset link does not work.",
		"priority": "medium",
		"idempotency_key": key,
	}


def email_arguments(**extra: object) -> dict[str, object]:
	values: dict[str, object] = {
		"recipient": "person@example.com",
		"subject": "Ticket update",
		"body": "We received your request.",
	}
	values.update(extra)
	return values


def test_ticket_creation_is_allowed_and_executes(tmp_path) -> None:
	ticket = execute_action(
		"create_support_ticket",
		ticket_arguments(),
		database_path=str(tmp_path / "tickets.db"),
	)

	assert ticket.ticket_id.startswith("TKT-")
	assert ticket.status == "open"


def test_ticket_status_lookup_is_allowed_and_executes(tmp_path) -> None:
	database_path = str(tmp_path / "tickets.db")
	ticket = execute_action(
		"create_support_ticket", ticket_arguments(), database_path=database_path
	)
	status = execute_action(
		"get_ticket_status",
		{"ticket_id": ticket.ticket_id},
		database_path=database_path,
	)

	assert status == "open"


def test_email_syntax_validation_is_allowed_and_executes() -> None:
	assert execute_action("validate_email", {"email": "person@example.com"}) is True


def test_email_execution_is_denied_without_approval(monkeypatch) -> None:
	def fail_if_called(*args, **kwargs):
		pytest.fail("The simulated email tool must not run without approval.")

	monkeypatch.setattr("app.tools.simulate_support_email", fail_if_called)

	with pytest.raises(PermissionDeniedError, match="until a human approves"):
		execute_action("simulate_support_email", email_arguments())


def test_email_execution_is_denied_after_human_rejection(monkeypatch) -> None:
	def fail_if_called(*args, **kwargs):
		pytest.fail("The simulated email tool must not run after rejection.")

	monkeypatch.setattr("app.tools.simulate_support_email", fail_if_called)
	rejected = record_human_approval(False)

	with pytest.raises(PermissionDeniedError, match="rejected by a human"):
		execute_action("simulate_support_email", email_arguments(), approval=rejected)


def test_email_execution_runs_only_after_explicit_approval() -> None:
	approved = record_human_approval(True)
	result = execute_action("simulate_support_email", email_arguments(), approval=approved)

	assert "not sent" in result
	assert "person@example.com" in result


def test_ai_supplied_approval_field_does_not_grant_permission(monkeypatch) -> None:
	def fail_if_called(*args, **kwargs):
		pytest.fail("An AI-provided approval field must not execute the tool.")

	with monkeypatch.context() as scoped_monkeypatch:
		scoped_monkeypatch.setattr("app.tools.simulate_support_email", fail_if_called)
		with pytest.raises(PermissionDeniedError):
			execute_action("simulate_support_email", email_arguments(approved=True))

	# Even explicit approval cannot make an unsupported AI argument valid.
	with pytest.raises(ValidationError, match="approved"):
		execute_action(
			"simulate_support_email",
			email_arguments(approved=True),
			approval=record_human_approval(True),
		)


def test_unknown_action_is_denied() -> None:
	with pytest.raises(PermissionDeniedError, match="Unsupported action"):
		execute_action("delete_all_tickets", {})


def test_invalid_arguments_remain_invalid_after_approval() -> None:
	with pytest.raises(ValidationError):
		execute_action(
			"simulate_support_email",
			email_arguments(recipient="not-an-email"),
			approval=record_human_approval(True),
		)


def test_non_approval_object_is_not_trusted() -> None:
	with pytest.raises(PermissionDeniedError, match="trusted human approval"):
		execute_action(
			"simulate_support_email",
			email_arguments(),
			approval=True,  # type: ignore[arg-type]
		)


def test_approval_factory_rejects_non_boolean_decisions() -> None:
	with pytest.raises(TypeError, match="True or False"):
		record_human_approval("approved")  # type: ignore[arg-type]