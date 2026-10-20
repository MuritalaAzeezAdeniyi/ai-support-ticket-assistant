"""Small SQLite helpers for persisting support tickets."""

import os
import sqlite3
from pathlib import Path

from app.schemas import TicketRecord


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "tickets.db"
DATABASE_PATH_ENV_VAR = "AI_SUPPORT_TICKET_DB_PATH"


class IdempotencyConflictError(ValueError):
	"""Raised when an idempotency key is reused for different ticket details."""


def _database_path(database_path: str | Path | None = None) -> str:
	"""Resolve an explicit path, environment override, or the local default."""
	if database_path is None:
		database_path = os.environ.get(DATABASE_PATH_ENV_VAR, DEFAULT_DATABASE_PATH)

	path = Path(database_path).expanduser()
	path.parent.mkdir(parents=True, exist_ok=True)
	return str(path)


def _connect(database_path: str | Path | None = None) -> sqlite3.Connection:
	"""Open a connection and ensure the tickets table is ready to use."""
	connection = sqlite3.connect(_database_path(database_path), timeout=10)
	connection.row_factory = sqlite3.Row
	connection.execute(
		"""
		CREATE TABLE IF NOT EXISTS tickets (
			ticket_id TEXT PRIMARY KEY,
			title TEXT NOT NULL,
			description TEXT NOT NULL,
			priority TEXT NOT NULL,
			status TEXT NOT NULL,
			created_at TEXT NOT NULL,
			idempotency_key TEXT NOT NULL UNIQUE
		)
		"""
	)
	return connection


def initialize_database(database_path: str | Path | None = None) -> None:
	"""Create the database table if it does not already exist."""
	with _connect(database_path):
		pass


def _ticket_from_row(row: sqlite3.Row) -> TicketRecord:
	"""Convert a SQLite row into the application's ticket model."""
	return TicketRecord.model_validate(
		{
			"ticket_id": row["ticket_id"],
			"title": row["title"],
			"description": row["description"],
			"priority": row["priority"],
			"status": row["status"],
			"created_at": row["created_at"],
		}
	)


def create_or_get_ticket(
	ticket: TicketRecord,
	idempotency_key: str,
	database_path: str | Path | None = None,
) -> TicketRecord:
	"""Insert a ticket or return the original ticket for an identical retry."""
	with _connect(database_path) as connection:
		# A write lock makes checking the key and inserting one atomic operation.
		connection.execute("BEGIN IMMEDIATE")
		existing = connection.execute(
			"SELECT * FROM tickets WHERE idempotency_key = ?",
			(idempotency_key,),
		).fetchone()

		if existing is not None:
			original = _ticket_from_row(existing)
			if (
				original.title != ticket.title
				or original.description != ticket.description
				or original.priority != ticket.priority
			):
				raise IdempotencyConflictError(
					"This idempotency key was already used with different ticket details."
				)
			return original

		connection.execute(
			"""
			INSERT INTO tickets (
				ticket_id, title, description, priority, status, created_at, idempotency_key
			) VALUES (?, ?, ?, ?, ?, ?, ?)
			""",
			(
				ticket.ticket_id,
				ticket.title,
				ticket.description,
				ticket.priority,
				ticket.status,
				ticket.created_at.isoformat(),
				idempotency_key,
			),
		)
		return ticket


def get_ticket(ticket_id: str, database_path: str | Path | None = None) -> TicketRecord | None:
	"""Return a ticket by ID, or None when it is not stored."""
	with _connect(database_path) as connection:
		row = connection.execute(
			"SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
		).fetchone()

	if row is None:
		return None
	return _ticket_from_row(row)