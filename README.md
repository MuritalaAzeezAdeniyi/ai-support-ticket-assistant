# AI Support Ticket Assistant

A beginner-friendly Python project for demonstrating AI tool/function calling and safe external actions. The planned assistant uses Gemini through `google-genai`, Pydantic validation, SQLite ticket storage, human approval for a simulated email action, idempotency, and audit logging.

> This repository is at the project-definition stage. Application logic and runnable commands have not been implemented yet. No real emails will be sent by this project.

## Project documents

- [Specification](docs/specification.md)
- [Acceptance criteria](docs/acceptance-criteria.md)
- [Architecture](docs/architecture.md)
- [AI usage log](AI_USAGE_LOG.md)

## Planned configuration

Configuration will use environment variables. See `.env.example` for names only. Do not commit API keys or other secrets. Gemini model availability and provider access are not guaranteed.

## Planned tests

Automated tests will cover schemas, tools, permissions, idempotency, and agent/provider behavior. Test and run commands will be added when application logic is implemented.
