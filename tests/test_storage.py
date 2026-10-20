"""Tests for local SQLite ticket persistence."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import sqlite3
from threading import Barrier

import pytest

from app.schemas import TicketRecord
from app.storage import (
    IdempotencyConflictError,
    create_or_get_ticket,
    get_ticket,
    initialize_database,
)


def make_ticket(ticket_id: str, title: str = "Cannot sign in") -> TicketRecord:
    return TicketRecord(
        ticket_id=ticket_id,
        title=title,
        description="The password reset link does not work.",
        priority="medium",
        status="open",
        created_at=datetime.now(timezone.utc),
    )


def test_database_is_created_and_ticket_can_be_retrieved(tmp_path) -> None:
    database_path = tmp_path / "nested" / "tickets.sqlite3"
    ticket = make_ticket("TKT-001")

    initialize_database(database_path)
    saved_ticket = create_or_get_ticket(ticket, "request-001", database_path)
    loaded_ticket = get_ticket(ticket.ticket_id, database_path)

    assert database_path.exists()
    assert saved_ticket == ticket
    assert loaded_ticket == ticket


def test_ticket_remains_available_after_connection_reopens(tmp_path) -> None:
    database_path = tmp_path / "tickets.sqlite3"
    ticket = make_ticket("TKT-002")

    create_or_get_ticket(ticket, "request-002", database_path)
    # get_ticket opens a fresh connection, proving data outlives the writer connection.
    loaded_ticket = get_ticket(ticket.ticket_id, database_path)

    assert loaded_ticket == ticket


def test_idempotency_key_has_database_uniqueness_constraint(tmp_path) -> None:
    database_path = tmp_path / "tickets.sqlite3"
    create_or_get_ticket(make_ticket("TKT-003"), "request-003", database_path)

    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO tickets (
                    ticket_id, title, description, priority, status,
                    created_at, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "TKT-OTHER",
                    "Other ticket",
                    "Other description",
                    "low",
                    "open",
                    datetime.now(timezone.utc).isoformat(),
                    "request-003",
                ),
            )


def test_reusing_key_with_different_details_raises_storage_error(tmp_path) -> None:
    database_path = tmp_path / "tickets.sqlite3"
    create_or_get_ticket(make_ticket("TKT-004"), "request-004", database_path)

    with pytest.raises(IdempotencyConflictError, match="different ticket details"):
        create_or_get_ticket(
            make_ticket("TKT-005", title="Different title"),
            "request-004",
            database_path,
        )


def test_concurrent_same_key_requests_do_not_create_duplicates(tmp_path) -> None:
    database_path = tmp_path / "tickets.sqlite3"
    barrier = Barrier(2)

    def create_ticket(ticket_id: str) -> TicketRecord:
        barrier.wait()
        return create_or_get_ticket(
            make_ticket(ticket_id), "shared-request", database_path
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(create_ticket, "TKT-006")
        second_future = executor.submit(create_ticket, "TKT-007")
        first = first_future.result()
        second = second_future.result()

    assert first.ticket_id == second.ticket_id
    with sqlite3.connect(database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE idempotency_key = ?",
            ("shared-request",),
        ).fetchone()[0]
    assert count == 1


def test_missing_ticket_returns_none(tmp_path) -> None:
    assert get_ticket("TKT-missing", tmp_path / "tickets.sqlite3") is None
