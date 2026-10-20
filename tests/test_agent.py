"""Offline tests for Gemini response handling and guarded function calling."""

from types import SimpleNamespace

import pytest

from app.agent import AgentError, TOOL_NAMES, run_agent
from app.permissions import HumanApproval, PermissionDeniedError


class FakeClient:
	"""Small stand-in for the Google Gen AI client; no network calls are made."""

	def __init__(self, responses=None, error=None):
		self.responses = list(responses or [])
		self.error = error
		self.calls = []
		self.closed = False
		self.models = self

	def generate_content(self, **kwargs):
		self.calls.append(kwargs)
		if self.error is not None:
			raise self.error
		return self.responses.pop(0)

	def close(self):
		self.closed = True


def function_response(name: str, args: dict, text: str = "Calling tool"):
	from google.genai import types

	call = SimpleNamespace(name=name, args=args)
	model_content = types.Content(
		role="model",
		parts=[types.Part.from_function_call(name=name, args=args)],
	)
	return SimpleNamespace(
		function_calls=[call],
		candidates=[SimpleNamespace(content=model_content)],
		text=text,
	)


def final_response(text: str):
	return SimpleNamespace(function_calls=None, candidates=[], text=text)


def ticket_arguments() -> dict[str, str]:
	return {
		"title": "Cannot sign in",
		"description": "The password reset link does not work.",
		"priority": "medium",
		"idempotency_key": "agent-test-key",
	}


def email_arguments(**extra: object) -> dict[str, object]:
	values: dict[str, object] = {
		"recipient": "person@example.com",
		"subject": "Ticket update",
		"body": "We received your request.",
	}
	values.update(extra)
	return values


def test_regular_message_returns_gemini_text_without_tool_calls(tmp_path, monkeypatch):
	monkeypatch.setattr("app.agent.get_gemini_api_key", lambda: None)
	client = FakeClient([final_response("Hello, how can I help?")])

	answer = run_agent("Hello", client=client, audit_path=tmp_path / "audit.jsonl")

	assert answer == "Hello, how can I help?"
	assert len(client.calls) == 1
	assert client.closed is False  # Injected clients remain owned by their caller.
	declared = client.calls[0]["config"].tools[0].function_declarations
	assert {item.name for item in declared} == TOOL_NAMES
	assert client.calls[0]["config"].automatic_function_calling.disable is True


def test_valid_tool_call_is_guarded_and_result_is_sent_to_gemini(tmp_path):
	client = FakeClient(
		[
			function_response("create_support_ticket", ticket_arguments()),
			final_response("Ticket TKT was created and is open."),
		]
	)
	answer = run_agent(
		"Create a ticket",
		client=client,
		database_path=tmp_path / "tickets.db",
		audit_path=tmp_path / "audit.jsonl",
	)

	assert "Ticket TKT" in answer
	assert len(client.calls) == 2
	second_turn = client.calls[1]["contents"]
	tool_content = second_turn[-1]
	assert tool_content.role == "tool"
	assert tool_content.parts[0].function_response.name == "create_support_ticket"
	result = tool_content.parts[0].function_response.response["result"]
	assert result["ticket_id"].startswith("TKT-")
	assert result["status"] == "open"


def test_unknown_tool_is_denied_and_audited_without_leaking_name(tmp_path):
	unknown_name = "unexpected_tool_secret_name"
	client = FakeClient(
		[
			function_response(unknown_name, {"secret": "payload"}),
			final_response("I cannot run that action."),
		]
	)

	answer = run_agent(
		"Do something",
		client=client,
		audit_path=tmp_path / "audit.jsonl",
	)

	assert "Unsupported action was not completed" in answer
	log = (tmp_path / "audit.jsonl").read_text()
	assert '"action": "unknown"' in log
	assert unknown_name not in log
	tool_result = client.calls[1]["contents"][-1].parts[0].function_response.response
	assert tool_result["error"]["category"] == "permission_denied"


def test_unexposed_email_alias_cannot_use_approval_to_execute(tmp_path, monkeypatch):
	def fail_if_called(*args, **kwargs):
		pytest.fail("A tool name outside the agent allowlist must not execute.")

	monkeypatch.setattr("app.tools.simulate_support_email", fail_if_called)
	client = FakeClient(
		[
			function_response("send_support_email", email_arguments()),
			final_response("The request was rejected."),
		]
	)

	answer = run_agent(
		"Prepare an email",
		client=client,
		approval=HumanApproval(approved=True),
		audit_path=tmp_path / "audit.jsonl",
	)

	assert "Unsupported action was not completed" in answer
	assert '"action": "unknown"' in (tmp_path / "audit.jsonl").read_text()
	assert client.calls[1]["contents"][-1].parts[0].function_response.response["error"]["category"] == "permission_denied"


def test_invalid_tool_arguments_are_returned_as_safe_error(tmp_path):
	client = FakeClient(
		[
			function_response("create_support_ticket", {**ticket_arguments(), "priority": "urgent"}),
			final_response("I could not create that ticket."),
		]
	)

	answer = run_agent(
		"Create a ticket",
		client=client,
		database_path=tmp_path / "tickets.db",
		audit_path=tmp_path / "audit.jsonl",
	)

	assert "create_support_ticket was not completed" in answer
	tool_result = client.calls[1]["contents"][-1].parts[0].function_response.response
	assert tool_result["error"]["category"] == "invalid_arguments"
	assert "urgent" not in repr(tool_result)


def test_email_without_approval_is_denied_and_never_simulated(tmp_path, monkeypatch):
	def fail_if_called(*args, **kwargs):
		pytest.fail("Email simulation must not run without approval.")

	monkeypatch.setattr("app.tools.simulate_support_email", fail_if_called)
	client = FakeClient(
		[
			function_response("simulate_support_email", email_arguments()),
			final_response("The email is awaiting approval."),
		]
	)

	answer = run_agent(
		"Prepare an email",
		client=client,
		audit_path=tmp_path / "audit.jsonl",
	)

	assert "simulate_support_email was not completed" in answer
	assert '"outcome": "denied"' in (tmp_path / "audit.jsonl").read_text()
	result = client.calls[1]["contents"][-1].parts[0].function_response.response
	assert result["error"]["category"] == "permission_denied"


def test_ai_approved_field_never_approves_email(tmp_path):
	client = FakeClient(
		[
			function_response("simulate_support_email", email_arguments(approved=True)),
			final_response("The request was rejected."),
		]
	)
	answer = run_agent(
		"Send an email",
		client=client,
		audit_path=tmp_path / "audit.jsonl",
	)

	assert "simulate_support_email was not completed" in answer
	response = client.calls[1]["contents"][-1].parts[0].function_response.response
	assert response["error"]["category"] == "permission_denied"


def test_trusted_external_approval_allows_only_simulated_email(tmp_path):
	client = FakeClient(
		[
			function_response("simulate_support_email", email_arguments()),
			final_response("The email was prepared for simulation."),
		]
	)
	answer = run_agent(
		"Prepare an email",
		client=client,
		approval=HumanApproval(approved=True),
		audit_path=tmp_path / "audit.jsonl",
	)

	assert "prepared" in answer
	response = client.calls[1]["contents"][-1].parts[0].function_response.response
	assert response["result"].startswith("Email prepared for simulation only; it was not sent.")


def test_provider_error_is_safe_and_does_not_retry(tmp_path):
	client = FakeClient(error=RuntimeError("private response with token=secret"))

	with pytest.raises(AgentError) as error:
		run_agent("Hello", client=client, audit_path=tmp_path / "audit.jsonl")

	assert error.value.category == "provider_error"
	assert "secret" not in str(error.value)
	assert len(client.calls) == 1


def test_provider_failure_after_ticket_creation_warns_not_to_retry_blindly(tmp_path):
	client = FakeClient(
		[
			function_response("create_support_ticket", ticket_arguments()),
		]
	)
	# The first response succeeds; only the second Gemini request raises.
	request_number = 0

	def fail_after_tool_result(**kwargs):
		nonlocal request_number
		request_number += 1
		if request_number == 1:
			client.calls.append(kwargs)
			return client.responses.pop(0)
		client.calls.append(kwargs)
		raise RuntimeError("provider secret details")

	client.generate_content = fail_after_tool_result

	with pytest.raises(AgentError) as error:
		run_agent(
			"Create ticket",
			client=client,
			database_path=tmp_path / "tickets.db",
			audit_path=tmp_path / "audit.jsonl",
		)

	assert error.value.category == "provider_error"
	assert "verify its outcome before retrying" in str(error.value)
	assert "provider secret" not in str(error.value)
	assert request_number == 2


def test_missing_api_key_fails_before_client_creation(monkeypatch):
	monkeypatch.setattr("app.agent.get_gemini_api_key", lambda: None)

	with pytest.raises(AgentError) as error:
		run_agent("Hello")

	assert error.value.category == "missing_api_key"


def test_tool_call_round_limit_stops_before_next_tool(tmp_path):
	client = FakeClient(
		[
			function_response("validate_email", {"email": "person@example.com"}),
			function_response("validate_email", {"email": "person@example.com"}),
		]
	)

	with pytest.raises(AgentError) as error:
		run_agent(
			"Validate an email",
			client=client,
			max_tool_call_rounds=1,
			audit_path=tmp_path / "audit.jsonl",
		)

	assert error.value.category == "tool_call_round_limit"
	assert len(client.calls) == 2
	assert "tool_call_round_limit" in (tmp_path / "audit.jsonl").read_text()


def test_tool_failure_is_not_reported_as_success_by_agent(tmp_path):
	client = FakeClient(
		[
			function_response("create_support_ticket", ticket_arguments()),
			function_response("get_ticket_status", {"ticket_id": "missing-ticket"}),
			final_response("The ticket is resolved."),
		]
	)
	answer = run_agent(
		"Create then check a ticket",
		client=client,
		database_path=tmp_path / "tickets.db",
		audit_path=tmp_path / "audit.jsonl",
	)

	assert "get_ticket_status was not completed: The requested ticket was not found." in answer
	assert "resolved" in answer
	assert '"error_category": "ticket_not_found"' in (tmp_path / "audit.jsonl").read_text()