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
