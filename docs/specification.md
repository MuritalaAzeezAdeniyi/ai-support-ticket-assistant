# AI Support Ticket Assistant — Specification

## Problem

Support teams need a simple way to record and check support requests. This project is a beginner-friendly, local demonstration of connecting an AI model to carefully controlled Python tools. It is intended for a one-week internship assignment about tool/function calling and safe external actions; it is not a production support system.

## Users

- **Support requester:** describes an issue, asks about a ticket, or requests a simulated support email.
- **Operator/reviewer:** reviews a consequential email request and explicitly approves or rejects it.
- **Developer/learner:** runs the application locally, studies the tool-call safety flow, and runs automated tests.

## Features in scope

- Use Gemini via the `google-genai` Python SDK, subject to model availability and provider configuration.
- Expose typed tool schemas and validate tool arguments with Pydantic in Python.
- Store support tickets in a local SQLite database.
- Look up a ticket's stored, actual status.
- Check email syntax only; do not infer that an address or account exists.
- Simulate email sending only, with explicit human approval before execution. No real email is sent.
- Make ticket creation idempotent when a retry uses the same idempotency key.
- Audit tool requests, approval decisions, successful actions, and failures.
- Return clear, predictable errors for invalid input and provider/action failures.

## Tools

| Tool | Purpose | Inputs and rules | Consequential action? |
| --- | --- | --- | --- |
| `create_support_ticket` | Create and persist a support ticket. | Required title, description, supported priority, and an idempotency key for retry safety. Validate fields before storage. | Yes: creates a record; execute only through the validated Python tool path. |
| `get_ticket_status` | Retrieve a ticket's status. | Required ticket identifier; return the status stored in SQLite or a clear not-found error. | No. |
| `validate_email` | Check email-address syntax. | Required address; report syntax validity only, never account existence or deliverability. | No. |
| `send_support_email` | Simulate sending a support email. | Validate recipient and message details. Require explicit application-level human approval before performing the simulation. | Yes: must not execute before approval. No network email delivery. |

The model can request one of these tools, but model output is untrusted input. AI-originated content—including a request to perform an action—is never human approval.

## Data models (conceptual)

- **SupportTicket:** ticket ID, title, description, priority, status, creation timestamp, and idempotency key. Status is initially assigned by the application and later read from storage; it must not be invented by the model.
- **Tool arguments:** structured fields for each tool, validated in Python with Pydantic. Required values must be present and supported priority values must be enforced.
- **Approval decision:** action/request reference, explicit approved or rejected decision, reviewer/approval source as available, and timestamp. A model message cannot populate this as approval.
- **Audit event:** timestamp, action/tool, request or correlation reference, outcome, and safe error/details. Do not write API keys or other secrets to the log.

Exact field types, allowed priority values, status names, and SQLite schema will be defined alongside the application implementation. They must be consistent across validation, storage, documentation, and tests.

## Safety and reliability requirements

1. Validate every tool call with Pydantic before execution; do not trust model-generated arguments.
2. Reject missing or malformed required fields and unsupported priorities with clear errors.
3. Apply Python permission checks to consequential actions. Never treat an AI request as a user's approval.
4. Do not run the simulated email action until explicit human approval is received by the application.
5. Make repeated ticket-creation requests with the same idempotency key return the original result rather than creating duplicates.
6. Audit tool requests, approval outcomes, successes, and failures, without recording credentials.
7. Handle invalid arguments, missing tickets, provider errors, timeouts, and rate limits clearly; do not claim an action succeeded unless it did.
8. Keep credentials out of source control. Provide variable names only in `.env.example`; actual secrets belong in a local, ignored environment file or environment variables.
9. Keep email sending simulated and local; do not integrate real email delivery.

## Out of scope and limitations

- Real email delivery, external ticketing-system integration, user authentication, and production deployment.
- Verifying mailbox ownership, account existence, or email deliverability.
- Guaranteeing a Gemini model or API availability; provider, network, timeout, and rate-limit failures are expected possibilities.
- Treating model output as authoritative, as approval, or as evidence that an action completed.
- Production-grade privacy, compliance, operational monitoring, or multi-user database guarantees.

SQLite is local project storage. The assistant is a learning/demo application, and approval is an application-controlled human action rather than a model-generated tool argument.
