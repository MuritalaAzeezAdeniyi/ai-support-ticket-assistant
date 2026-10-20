# Acceptance Criteria

These criteria define observable behavior for the initial project. They are intended to become automated tests as application logic is added.

## Project setup and scope

- [ ] The repository contains the documented `app/`, `tests/`, and `docs/` structure, the root project files, and no unrelated features.
- [ ] The project uses Gemini through `google-genai` when AI integration is implemented; model availability is treated as configurable rather than guaranteed.
- [ ] Ticket data is stored locally with SQLite.
- [ ] The email action is simulation-only; no real email is sent.
- [ ] `.env.example` contains variable names with blank/placeholder values only, and no credentials are committed.
- [ ] No Git commit is created as part of this work.

## Typed inputs and validation

- [ ] Every tool has a typed argument schema and tool arguments are validated with Pydantic in Python before execution.
- [ ] Missing required tool arguments are rejected with a clear, predictable validation error.
- [ ] Malformed values are rejected with a clear, predictable validation error.
- [ ] Unsupported priority values are rejected; accepted values are explicitly defined and consistently tested when implementation begins.
- [ ] `validate_email` distinguishes syntactically valid and invalid addresses without asserting mailbox, account, or deliverability status.

## Ticket creation and idempotency

- [ ] A valid ticket can be created with title, description, supported priority, and an idempotency key.
- [ ] A created ticket is persisted in SQLite and has an identifier, status, and creation timestamp.
- [ ] Repeating ticket creation with the same idempotency key does not create a second ticket and returns/references the original result.
- [ ] Using a different idempotency key permits a separate ticket, subject to normal validation.
- [ ] A storage failure is reported as a failure; the assistant does not report successful creation unless persistence succeeded.

## Ticket status

- [ ] `get_ticket_status` returns the actual status read from SQLite for an existing ticket.
- [ ] A missing ticket produces a clear not-found result and does not invent a status.

## Approval and simulated email

- [ ] A tool request from the AI alone never counts as human approval.
- [ ] A simulated email request can be recorded as pending and does not execute before explicit human approval is received by the application.
- [ ] An explicit rejection prevents execution and is recorded.
- [ ] An explicit approval allows only the validated simulation to execute, and the result is reported accurately.
- [ ] The simulation does not send an email over a network or use real email-delivery credentials.
- [ ] The approval decision and action outcome are auditable.

## Audit logging

- [ ] Tool requests are recorded in the audit log.
- [ ] Approval and rejection decisions are recorded.
- [ ] Successful tool executions are recorded.
- [ ] Failed tool executions are recorded with safe, useful context.
- [ ] Audit data does not expose API keys or other secrets.

## Errors and provider behavior

- [ ] Invalid arguments, missing tickets, provider errors, timeouts, and rate limits have understandable and predictable error handling.
- [ ] A provider failure is not represented as a successful tool execution.
- [ ] The final response distinguishes completed actions, pending approval, rejected actions, and failures.
- [ ] Secret values are not included in user-facing errors or logs.

## Tests and documentation

- [ ] Automated tests cover schemas, tools, permissions, idempotency, and agent/provider behavior.
- [ ] Tests cover the safety boundary that model tool requests cannot approve consequential actions.
- [ ] The README explains setup, configuration without committing secrets, running the app, and running tests when those commands are implemented.
- [ ] Documentation is consistent with implementation; unresolved values such as priority names are specified before tests depend on them.
