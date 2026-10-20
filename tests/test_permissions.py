"""Tests for permission checks at the tool execution boundary."""

import json

import pytest

from app.audit import AuditLoggingError
from app.permissions import (
	ActionExecutionError,
	PermissionDeniedError,
	execute_action,
	record_human_approval,
)


@pytest.fixture(autouse=True)
def use_temporary_audit_log(tmp_path, monkeypatch):
	"""Keep all permission tests away from the real project audit file."""
	path = tmp_path / "audit.jsonl"
	monkeypatch.setenv("AI_SUPPORT_TICKET_AUDIT_PATH", str(path))
	return path


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
	with pytest.raises(ActionExecutionError) as error:
		execute_action(
			"simulate_support_email",
			email_arguments(approved=True),
			approval=record_human_approval(True),
		)
	assert error.value.category == "invalid_arguments"
	assert "approved" not in str(error.value)


def test_unknown_action_is_denied() -> None:
	with pytest.raises(PermissionDeniedError, match="Unsupported action"):
		execute_action("delete_all_tickets", {})


def test_invalid_arguments_remain_invalid_after_approval() -> None:
	with pytest.raises(ActionExecutionError) as error:
		execute_action(
			"simulate_support_email",
			email_arguments(recipient="not-an-email"),
			approval=record_human_approval(True),
		)
	assert error.value.category == "invalid_arguments"
	assert "not-an-email" not in str(error.value)


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


def test_successful_action_is_audited_with_ticket_id(use_temporary_audit_log, tmp_path) -> None:
	ticket = execute_action(
		"create_support_ticket",
		ticket_arguments(),
		database_path=str(tmp_path / "tickets.db"),
	)
	events = [json.loads(line) for line in use_temporary_audit_log.read_text().splitlines()]

	assert events[-1]["outcome"] == "success"
	assert events[-1]["action"] == "create_support_ticket"
	assert events[-1]["ticket_id"] == ticket.ticket_id
	assert "timestamp" in events[-1]


def test_missing_approval_and_rejection_are_audited(use_temporary_audit_log) -> None:
	with pytest.raises(PermissionDeniedError):
		execute_action("simulate_support_email", email_arguments())

	decision = record_human_approval(False)
	with pytest.raises(PermissionDeniedError):
		execute_action("simulate_support_email", email_arguments(), approval=decision)

	events = [json.loads(line) for line in use_temporary_audit_log.read_text().splitlines()]
	assert events[0]["outcome"] == "denied"
	assert events[1]["outcome"] == "approval_rejected"
	assert events[2]["outcome"] == "denied"
	assert events[2]["error_category"] == "permission_denied"


def test_tool_failure_is_audited_without_raw_error_details(use_temporary_audit_log) -> None:
	with pytest.raises(ActionExecutionError) as error:
		execute_action("validate_email", {"email": "not-an-email"})
	assert error.value.category == "invalid_arguments"

	event = json.loads(use_temporary_audit_log.read_text().splitlines()[0])
	assert event["outcome"] == "failure"
	assert event["error_category"] == "invalid_arguments"
	assert "not-an-email" not in use_temporary_audit_log.read_text()


def test_unexpected_tool_error_is_normalized_and_audited(
	monkeypatch, use_temporary_audit_log
) -> None:
	def raise_internal_error(*args, **kwargs):
		raise RuntimeError("database password=do-not-leak")

	monkeypatch.setattr("app.tools.validate_email", raise_internal_error)

	with pytest.raises(ActionExecutionError) as error:
		execute_action("validate_email", {"email": "person@example.com"})

	assert error.value.category == "tool_execution_error"
	assert "database password" not in str(error.value)
	contents = use_temporary_audit_log.read_text()
	assert "database password" not in contents
	assert '"error_category": "tool_execution_error"' in contents


def test_unknown_action_is_not_reflected_into_audit_log(use_temporary_audit_log) -> None:
	secret_action = "unsupported-secret-token-123"
	with pytest.raises(PermissionDeniedError):
		execute_action(secret_action, {})

	event = json.loads(use_temporary_audit_log.read_text().splitlines()[0])
	assert event["action"] == "unknown"
	assert secret_action not in use_temporary_audit_log.read_text()


def test_unexpected_tool_error_is_normalized_and_audited(
	monkeypatch, use_temporary_audit_log
) -> None:
	def raise_internal_error(*args, **kwargs):
		raise RuntimeError("database password=do-not-leak")

	monkeypatch.setattr("app.tools.validate_email", raise_internal_error)

	with pytest.raises(ActionExecutionError) as error:
		execute_action("validate_email", {"email": "person@example.com"})

	assert error.value.category == "tool_execution_error"
	assert "database password" not in str(error.value)
	contents = use_temporary_audit_log.read_text()
	assert "database password" not in contents
	assert '"error_category": "tool_execution_error"' in contents


def test_audit_entries_are_jsonl_and_exclude_sensitive_payloads(
	use_temporary_audit_log, tmp_path
) -> None:
	description_secret = "FULL PRIVATE TICKET DESCRIPTION 9921"
	email_body_secret = "FULL PRIVATE EMAIL BODY 7713"
	credential_secret = "API_KEY_DO_NOT_LOG_12345"
	ticket_data = ticket_arguments()
	ticket_data["description"] = description_secret
	created = execute_action(
		"create_support_ticket",
		ticket_data,
		database_path=str(tmp_path / "tickets.db"),
	)
	approved = record_human_approval(True)
	execute_action(
		"simulate_support_email",
		email_arguments(body=email_body_secret),
		approval=approved,
	)
	with pytest.raises(ActionExecutionError) as error:
		execute_action(
			"simulate_support_email",
			email_arguments(api_key=credential_secret),
			approval=approved,
		)
	assert error.value.category == "invalid_arguments"

	lines = use_temporary_audit_log.read_text(encoding="utf-8").splitlines()
	events = [json.loads(line) for line in lines]
	assert all(isinstance(event, dict) for event in events)
	assert any(event.get("ticket_id") == created.ticket_id for event in events)
	contents = use_temporary_audit_log.read_text(encoding="utf-8")
	assert description_secret not in contents
	assert email_body_secret not in contents
	assert credential_secret not in contents
	assert "api_key" not in contents
	assert any(event["outcome"] == "approval_granted" for event in events)


def test_missing_ticket_and_idempotency_conflict_have_safe_categories(
	tmp_path, use_temporary_audit_log
) -> None:
	database_path = str(tmp_path / "tickets.db")
	with pytest.raises(ActionExecutionError) as missing_error:
		execute_action(
			"get_ticket_status",
			{"ticket_id": "TKT-does-not-exist"},
			database_path=database_path,
		)
	assert missing_error.value.category == "ticket_not_found"
	assert "TKT-does-not-exist" not in str(missing_error.value)

	execute_action(
		"create_support_ticket",
		ticket_arguments(),
		database_path=database_path,
	)
	with pytest.raises(ActionExecutionError) as conflict_error:
		execute_action(
			"create_support_ticket",
			ticket_arguments_key_and_different_title(),
			database_path=database_path,
		)
	assert conflict_error.value.category == "idempotency_conflict"

	events = [json.loads(line) for line in use_temporary_audit_log.read_text().splitlines()]
	assert [event["error_category"] for event in events if event["outcome"] == "failure"] == [
		"ticket_not_found",
		"idempotency_conflict",
	]


def ticket_arguments_key_and_different_title() -> dict[str, str]:
	return {
		"title": "Different title",
		"description": "The password reset link does not work.",
		"priority": "medium",
		"idempotency_key": "permission-test",
	}


def test_audit_write_failure_is_explicit_and_does_not_claim_success(tmp_path) -> None:
	blocked_parent = tmp_path / "not-a-directory"
	blocked_parent.write_text("block directory creation", encoding="utf-8")

	with pytest.raises(AuditLoggingError, match="may have completed"):
		execute_action(
			"create_support_ticket",
			ticket_arguments(),
			database_path=str(tmp_path / "tickets.db"),
			audit_path=blocked_parent / "audit.jsonl",
		)