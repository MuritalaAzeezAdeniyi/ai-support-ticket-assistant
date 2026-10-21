"""Small Streamlit chat interface for the guarded support assistant agent."""

from collections.abc import Mapping
from typing import Any

from app.agent import AgentError, run_agent
from app.audit import AuditLoggingError
from app.permissions import ActionExecutionError, PermissionDeniedError, execute_action


def friendly_error_message(error: Exception) -> str:
	"""Map expected application errors to short, safe messages for the UI."""
	if isinstance(error, AgentError):
		if error.category == "missing_api_key":
			return "Gemini is not configured. Add GEMINI_API_KEY to your local .env file, then restart the app."
		if error.category == "provider_error":
			return "Gemini is temporarily unavailable or the request failed. Check your model, network, and quota, then try again."
		if error.category == "action_outcome_uncertain":
			return "The action result could not be confirmed. Check the ticket or audit log before retrying."
		return str(error)
	if isinstance(error, ActionExecutionError):
		return str(error)
	if isinstance(error, PermissionDeniedError):
		return "That action is not permitted. Simulated email requires separate human approval."
	if isinstance(error, AuditLoggingError):
		return "The result could not be safely confirmed because the audit log is unavailable. Verify before retrying."
	return "Something went wrong. No internal error details or credentials are shown."


def _chat_history(state: Mapping[str, Any]) -> list[dict[str, str]]:
	"""Return structurally valid chat history without storing credentials."""
	history = state.get("messages", [])
	if not isinstance(history, list):
		return []
	return [
		message
		for message in history
		if isinstance(message, dict)
		and message.get("role") in {"user", "assistant"}
		and isinstance(message.get("content"), str)
	]


def main() -> None:
	"""Render the chat interface and a direct, guarded ticket-status lookup."""
	import streamlit as st

	st.set_page_config(page_title="AI Support Ticket Assistant", page_icon="🎫")
	st.title("AI Support Ticket Assistant")
	st.caption(
		"Ask for help creating or checking support tickets. Ticket actions are validated "
		"and audited before results are reported."
	)
	st.info(
		"Email is simulation-only. This interface has no human approval workflow, "
		"so email simulation requests remain denied. No real emails are sent."
	)

	if "messages" not in st.session_state:
		st.session_state.messages = []

	for message in _chat_history(st.session_state):
		with st.chat_message(message["role"]):
			st.markdown(message["content"])

	if prompt := st.chat_input("How can I help with your support request?"):
		st.session_state.messages.append({"role": "user", "content": prompt})
		with st.chat_message("user"):
			st.markdown(prompt)
		with st.chat_message("assistant"):
			with st.spinner("Checking your request..."):
				try:
					response = run_agent(prompt)
				except Exception as error:
					response = friendly_error_message(error)
				st.markdown(response)
		st.session_state.messages.append({"role": "assistant", "content": response})

	with st.sidebar:
		st.subheader("Check ticket status")
		st.caption("Look up the status currently stored for a ticket.")
		with st.form("ticket_status_form", clear_on_submit=False):
			ticket_id = st.text_input("Ticket ID", placeholder="TKT-123abc")
			check_status = st.form_submit_button("Check status")
		if check_status:
			try:
				status = execute_action("get_ticket_status", {"ticket_id": ticket_id})
			except Exception as error:
				st.error(friendly_error_message(error))
			else:
				st.success(f"Ticket status: {status}")

		st.divider()
		st.caption("Ticket data is stored locally in SQLite. Audit events are stored in a local JSON Lines file.")


if __name__ == "__main__":
	main()