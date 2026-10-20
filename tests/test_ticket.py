from datetime import datetime, timezone

import pytest

from core.ticket import Ticket


def make(priority, day, op_id):
    return Ticket(
        title="t", description="d", priority=priority, source="csv",
        created_at=datetime(2026, 10, day, tzinfo=timezone.utc), op_id=op_id,
    )


def test_order_by_priority_then_age():
    tickets = [make("Low", 1, 1), make("High", 3, 2), make("High", 2, 3),
               make("Immediate", 5, 4), make("Normal", 1, 5)]
    order = [t.op_id for t in sorted(tickets, key=lambda t: t.sort_key())]
    assert order == [4, 3, 2, 5, 1]


def test_unknown_priority_fails():
    with pytest.raises(ValueError):
        make("Urgent", 1, 1)


def test_naive_datetime_fails():
    with pytest.raises(ValueError):
        Ticket(title="t", description="d", priority="Low", source="csv",
               created_at=datetime(2026, 10, 1))
