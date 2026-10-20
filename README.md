# AI Support Ticket Assistant

A beginner-friendly Python project demonstrating safe AI tool/function calling. The current implementation includes Gemini function calling, Pydantic validation, support tools, SQLite ticket storage with idempotent creation, application-level permissions and approval, and JSON Lines audit logging. The Streamlit interface is not implemented yet.

> This project does not send real emails. The support-email function only prepares a simulation description, and execution requires an application-controlled human approval decision.

## Project documents

- [Specification](docs/specification.md)
- [Acceptance criteria](docs/acceptance-criteria.md)
- [Architecture](docs/architecture.md)
- [AI usage log](AI_USAGE_LOG.md)

## Install and configure

Use the project virtual environment, then install the listed dependencies:

```powershell
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` to a Gemini Developer API key. The `.env` file is ignored by Git; never commit credentials. `GEMINI_MODEL` selects the model and defaults to `gemini-flash-latest`; availability depends on Google's current API/model access and is not guaranteed. `GEMINI_TOOL_CALL_ROUNDS` sets the maximum tool-call rounds per request and defaults to `3`.

`python-dotenv` loads a local `.env`; existing process environment variables take precedence. You can also set the variables directly in your shell.

## Gemini function-calling flow

Run one request from the project root:

```powershell
python -m app.agent "Please create a ticket about the login page failing"
```

Gemini receives declarations for only `create_support_ticket`, `get_ticket_status`, `validate_email`, and `simulate_support_email`. Automatic SDK function execution is disabled. The application validates each model-requested call in Python and sends it through `execute_action()` in `app/permissions.py`; that boundary applies permission checks, Pydantic validation, SQLite/idempotency, and audit logging. Tool outcomes are returned to Gemini, which can then produce the final response. Provider failures are reported safely, and the agent does not blindly retry tools.

The email action remains a simulation and requires a separate application-controlled `HumanApproval` decision. The model cannot approve itself, and the command-line entry point has no human approval interface, so email requests through the CLI are denied by default. Approval must be supplied by trusted application code; a conversational statement from the model or an `approved` tool argument is never approval.

## Tests

Run the complete automated suite with:

```powershell
python -m pytest tests -v
```

Agent tests use mocked Gemini responses and do not require a live API key, paid account, or network connection.

## Ticket database configuration

Tickets are stored in a local SQLite database. By default, the database is created at `data/tickets.db` in the project directory. Set `AI_SUPPORT_TICKET_DB_PATH` to change the database file path. Tests pass temporary database paths so they do not modify the application database.

## Audit log

Tool execution successes and failures, permission denials, and human approval decisions are appended as one JSON object per line. By default, the log is `data/audit.jsonl` in the project directory. Set `AI_SUPPORT_TICKET_AUDIT_PATH` to choose a different file path.

Audit entries include a UTC timestamp, action, outcome, and—when relevant—a safe error category or ticket ID. They deliberately exclude API keys and credentials, raw request payloads, full ticket descriptions, and full email contents. The guarded `execute_action()` path raises safe `ActionExecutionError` exceptions with a stable category for invalid arguments, missing tickets, idempotency conflicts, and unexpected tool errors. Permission denials remain `PermissionDeniedError` exceptions. If the audit file cannot be written, the application raises an explicit audit error rather than silently ignoring the problem; if the action itself already completed, the message warns that its success could not be recorded and should be verified before retrying.

The audit log remains `data/audit.jsonl` by default and can be moved with `AI_SUPPORT_TICKET_AUDIT_PATH`. Gemini model availability, rate limits, network access, and account configuration are external dependencies; no real email is sent.
