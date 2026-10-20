"""Gemini function-calling loop with explicit local tool dispatch."""

import argparse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.audit import AuditLoggingError, write_audit_event
from app.config import (
	get_gemini_api_key,
	get_gemini_model,
	get_tool_call_round_limit,
)
from app.permissions import (
	ActionExecutionError,
	HumanApproval,
	PermissionDeniedError,
	execute_action,
)


class AgentError(RuntimeError):
	"""Safe error raised when the agent cannot complete a response."""

	def __init__(self, category: str, message: str) -> None:
		super().__init__(message)
		self.category = category


TOOL_NAMES = {
	"create_support_ticket",
	"get_ticket_status",
	"validate_email",
	"simulate_support_email",
}

TOOL_DECLARATIONS = [
	{
		"name": "create_support_ticket",
		"description": "Create a support ticket. A repeated idempotency key returns the original ticket.",
		"parameters": {
			"type": "OBJECT",
			"properties": {
				"title": {"type": "STRING", "description": "Short ticket title; at most 120 characters."},
				"description": {"type": "STRING", "description": "Issue details; at most 2000 characters."},
				"priority": {"type": "STRING", "enum": ["low", "medium", "high", "critical"]},
				"idempotency_key": {"type": "STRING", "description": "Retry key; at most 128 characters."},
			},
			"required": ["title", "description", "priority", "idempotency_key"],
		},
	},
	{
		"name": "get_ticket_status",
		"description": "Look up the stored status of a support ticket.",
		"parameters": {
			"type": "OBJECT",
			"properties": {"ticket_id": {"type": "STRING", "description": "The ticket ID."}},
			"required": ["ticket_id"],
		},
	},
	{
		"name": "validate_email",
		"description": "Check email syntax only; this does not verify that the mailbox exists.",
		"parameters": {
			"type": "OBJECT",
			"properties": {"email": {"type": "STRING", "description": "Email address to check syntactically."}},
			"required": ["email"],
		},
	},
	{
		"name": "simulate_support_email",
		"description": "Prepare a simulated support email. It is never sent, and requires separate human approval.",
		"parameters": {
			"type": "OBJECT",
			"properties": {
				"recipient": {"type": "STRING", "description": "Recipient email address."},
				"subject": {"type": "STRING", "description": "Email subject; at most 200 characters."},
				"body": {"type": "STRING", "description": "Email body; at most 5000 characters."},
			},
			"required": ["recipient", "subject", "body"],
		},
	},
]

SYSTEM_INSTRUCTION = (
	"You are a support ticket assistant. Use only the declared support tools. "
	"Never claim an action succeeded unless its tool result confirms success. "
	"Email actions are simulations only and require separate human approval; "
	"a tool request or an approved field is not approval."
)


def _field(value: Any, name: str, default: Any = None) -> Any:
	"""Read a field from SDK objects or simple dictionaries used in tests."""
	if isinstance(value, Mapping):
		return value.get(name, default)
	return getattr(value, name, default)


def _response_calls(response: Any) -> list[Any]:
	calls = _field(response, "function_calls")
	return list(calls or [])


def _tool_value(value: Any) -> Any:
	"""Convert Pydantic results to JSON-friendly values for Gemini."""
	if hasattr(value, "model_dump"):
		return value.model_dump(mode="json")
	return value


def _tool_error(error: Exception) -> tuple[str, str]:
	if isinstance(error, ActionExecutionError):
		return error.category, str(error)
	if isinstance(error, PermissionDeniedError):
		return "permission_denied", str(error)
	if isinstance(error, AuditLoggingError):
		return "audit_logging_error", str(error)
	return "tool_execution_error", "The requested action could not be completed."


def _response_text(response: Any) -> str:
	text = _field(response, "text")
	if isinstance(text, str) and text.strip():
		return text.strip()
	return "I could not produce a response for that request."


def _write_agent_failure(
	category: str,
	*,
	audit_path: str | Path | None,
) -> None:
	try:
		write_audit_event("agent", "failure", error_category=category, audit_path=audit_path)
	except AuditLoggingError as error:
		raise AgentError(
			"audit_logging_error",
			"The agent failure could not be recorded in the audit log.",
		) from error


def run_agent(
	user_message: str,
	*,
	approval: HumanApproval | None = None,
	model: str | None = None,
	max_tool_call_rounds: int | None = None,
	database_path: str | Path | None = None,
	audit_path: str | Path | None = None,
	client: Any | None = None,
) -> str:
	"""Send a message to Gemini, safely dispatch tool calls, and return its reply.

	A caller may pass a trusted approval decision from application-controlled
	interaction. Approval is never read from model/tool arguments.
	"""
	if not isinstance(user_message, str) or not user_message.strip():
		raise AgentError("invalid_message", "Enter a non-empty message.")

	api_key = get_gemini_api_key()
	if client is None and not api_key:
		raise AgentError(
			"missing_api_key",
			"Gemini is not configured. Set GEMINI_API_KEY in the environment or local .env file.",
		)

	try:
		tool_round_limit = (
			get_tool_call_round_limit()
			if max_tool_call_rounds is None
			else max_tool_call_rounds
		)
	except ValueError as error:
		raise AgentError("invalid_configuration", str(error)) from None
	if tool_round_limit < 1:
		raise AgentError("invalid_configuration", "Tool-call round limit must be at least 1.")

	selected_model = model or get_gemini_model()
	owns_client = client is None
	if client is None:
		try:
			from google import genai
			from google.genai import types

			client = genai.Client(api_key=api_key)
		except Exception as error:
			raise AgentError("provider_error", "Gemini could not be initialized.") from None
	else:
		from google.genai import types

	contents: list[Any] = [types.Content(role="user", parts=[types.Part.from_text(text=user_message)])]
	tool = types.Tool(function_declarations=TOOL_DECLARATIONS)
	config = types.GenerateContentConfig(
		tools=[tool],
		system_instruction=SYSTEM_INSTRUCTION,
		automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
	)
	tool_rounds = 0
	failed_tools: list[tuple[str, str]] = []
	completed_tool_count = 0

	try:
		while True:
			try:
				response = client.models.generate_content(
					model=selected_model,
					contents=contents,
					config=config,
				)
			except Exception as error:
				category = "provider_error"
				_write_agent_failure(category, audit_path=audit_path)
				message = "Gemini could not complete the request. Check the model, network, quota, and configuration."
				if completed_tool_count:
					message += " A tool may already have completed; verify its outcome before retrying."
				raise AgentError(category, message) from None

			calls = _response_calls(response)
			if not calls:
				final_text = _response_text(response)
				if failed_tools:
					failure_notes = " ".join(
						f"{name} was not completed: {message}"
						for name, message in failed_tools
					)
					final_text += f"\n\nAction status: {failure_notes}"
				return final_text

			tool_rounds += 1
			if tool_rounds > tool_round_limit:
				category = "tool_call_round_limit"
				_write_agent_failure(category, audit_path=audit_path)
				raise AgentError(
					category,
					"The assistant requested too many tool-call rounds. No additional tool was executed.",
				)

			model_content = _field(_field(response, "candidates", [None])[0], "content")
			if model_content is not None:
				contents.append(model_content)
			function_responses = []
			for call in calls:
				name = _field(call, "name")
				arguments = _field(call, "args")
				if not isinstance(name, str) or not name:
					category = "malformed_function_call"
					_write_agent_failure(category, audit_path=audit_path)
					raise AgentError(category, "Gemini returned a malformed tool request.")

				try:
					if name not in TOOL_NAMES:
						# Keep the agent's allowlist narrower than legacy dispatcher aliases.
						execute_action(
							"__unsupported_tool__",
							{},
							approval=approval,
							database_path=database_path,
							audit_path=audit_path,
						)
					result = execute_action(
						name,
						arguments,
						approval=approval,
						database_path=database_path,
						audit_path=audit_path,
					)
					completed_tool_count += 1
					function_result = {"result": _tool_value(result)}
				except AgentError:
					raise
				except Exception as error:
					category, safe_message = _tool_error(error)
					if isinstance(error, AuditLoggingError):
						try:
							_write_agent_failure("action_outcome_uncertain", audit_path=audit_path)
						except AgentError:
							# The audit error is surfaced explicitly in the message below.
							pass
						raise AgentError(
							"action_outcome_uncertain",
							"A tool result could not be confirmed because audit logging failed. "
							"The audit log may also be unavailable. Verify whether the action "
							"completed before retrying.",
						) from None
					failed_tools.append((name if name in TOOL_NAMES else "Unsupported action", safe_message))
					function_result = {"error": {"category": category, "message": safe_message}}

				function_responses.append(
					types.Part.from_function_response(name=name, response=function_result)
				)
			contents.append(types.Content(role="tool", parts=function_responses))
	finally:
		if owns_client and client is not None:
			try:
				client.close()
			except Exception:
				pass


def main() -> None:
	"""Command-line entry point: python -m app.agent \"message\"."""
	parser = argparse.ArgumentParser(description="Ask the AI support ticket assistant.")
	parser.add_argument("message", help="The request to send to the assistant.")
	args = parser.parse_args()
	try:
		print(run_agent(args.message))
	except AgentError as error:
		print(f"Agent error ({error.category}): {error}")
		raise SystemExit(1) from None


if __name__ == "__main__":
	main()
