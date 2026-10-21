# AI Usage Log

## Stage 1 — Project definition and structure

- Used AI assistance to inspect the repository and define the initial project documentation and directory/file structure.
- Created the specification, testable acceptance criteria, architecture overview, and minimal placeholders for the planned application and test modules.
- Added environment-variable names only to `.env.example`; no API keys or other credentials were added.
- No application logic, dependency installation, or Git commits were performed in this stage.

## Stage 6 — Audit logging and predictable errors

- Implemented append-only JSON Lines audit logging for action outcomes, permission denials, and human approval decisions, with a configurable audit file path.
- Integrated audit events with the permission-controlled execution path and added safe error categories without logging raw arguments or sensitive exception details.
- Added tests for audit records, sensitive-data exclusions, denied and failed actions, and audit-file write failures.
- Updated README documentation to describe audit-log behavior and configuration.
- No AI provider integration, real email delivery, unrelated dependencies, or Git commits were added.

## Stage 7 — Gemini function calling

- Integrated the official `google-genai` SDK with manually dispatched function calls for the four existing support actions.
- Routed each model-requested action through the existing guarded permission and validation boundary; added safe provider, malformed-call, and tool-round-limit handling.
- Added mocked Gemini tests that do not make network calls and updated the example configuration and README instructions.
- Preserved the separate human-approval requirement for simulated email; no real email delivery, Streamlit UI, or Git commit was added.

## Stage 8 — Streamlit UI and final integration

- Implemented a chat-style Streamlit interface that invokes the existing agent and keeps messages in Streamlit session state.
- Added a guarded ticket-status lookup, friendly error mapping, and explicit messaging that email remains denied without a separate trusted approval flow.
- Added focused tests for session-history filtering and safe error display; declared Streamlit as a dependency.
- Updated README setup, launch, test, feature, approval, audit, and limitation guidance; reviewed Git exclusions for local environment files, databases, audit logs, environments, and caches.
- No live Gemini API calls, deployment configuration, real email delivery, or Git commits were performed.
