# AI Support Ticket Assistant

A beginner-friendly Python project being built in stages to demonstrate safe AI tool/function calling. The current implementation includes Pydantic validation, Python support-tool functions, SQLite ticket storage with idempotent creation, application-level permissions and approval, and JSON Lines audit logging. AI integration and the user interface are not implemented yet.

> This project does not send real emails. The support-email function only prepares a simulation description, and execution requires an application-controlled human approval decision.

## Project documents

- [Specification](docs/specification.md)
- [Acceptance criteria](docs/acceptance-criteria.md)
- [Architecture](docs/architecture.md)
- [AI usage log](AI_USAGE_LOG.md)

## Ticket database configuration

Tickets are stored in a local SQLite database. By default, the database is created at `data/tickets.db` in the project directory. Set `AI_SUPPORT_TICKET_DB_PATH` to change the database file path. Tests pass temporary database paths so they do not modify the application database.

## Audit log

Tool execution successes and failures, permission denials, and human approval decisions are appended as one JSON object per line. By default, the log is `data/audit.jsonl` in the project directory. Set `AI_SUPPORT_TICKET_AUDIT_PATH` to choose a different file path.

Audit entries include a UTC timestamp, action, outcome, and—when relevant—a safe error category or ticket ID. They deliberately exclude API keys and credentials, raw request payloads, full ticket descriptions, and full email contents. The guarded `execute_action()` path raises safe `ActionExecutionError` exceptions with a stable category for invalid arguments, missing tickets, idempotency conflicts, and unexpected tool errors. Permission denials remain `PermissionDeniedError` exceptions. If the audit file cannot be written, the application raises an explicit audit error rather than silently ignoring the problem; if the action itself already completed, the message warns that its success could not be recorded and should be verified before retrying.

## Tests

Run the schema, tool, storage, and permission tests with `python -m pytest tests/test_schemas.py tests/test_tools.py tests/test_storage.py tests/test_permissions.py -v`.

The project does not currently connect to Gemini. Configuration names in `.env.example` are placeholders; do not commit real credentials.
