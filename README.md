# AI Support Ticket Assistant

A beginner-friendly Python project being built in stages to demonstrate safe AI tool/function calling. The current implementation includes Pydantic validation, Python support-tool functions, and SQLite ticket storage with idempotent creation. AI integration, approval enforcement, audit logging, and the user interface are not implemented yet.

> This project does not send real emails. The support-email function only prepares a simulation description; approval enforcement is not implemented yet.

## Project documents

- [Specification](docs/specification.md)
- [Acceptance criteria](docs/acceptance-criteria.md)
- [Architecture](docs/architecture.md)
- [AI usage log](AI_USAGE_LOG.md)

## Ticket database configuration

Tickets are stored in a local SQLite database. By default, the database is created at `data/tickets.db` in the project directory. Set `AI_SUPPORT_TICKET_DB_PATH` to change the database file path. Tests pass temporary database paths so they do not modify the application database.

## Tests

Run the schema, tool, and storage tests with `python -m pytest tests/test_schemas.py tests/test_tools.py tests/test_storage.py -v`.

The project does not currently connect to Gemini or provide approval enforcement or audit logging. Configuration names in `.env.example` are placeholders; do not commit real credentials.
