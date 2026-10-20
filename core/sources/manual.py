"""Ticket source: typed by hand (for example from the app)."""

from datetime import datetime, timezone

from core.ticket import Ticket


def make_ticket(title, description, priority="Normal"):
    return Ticket(
        title=title,
        description=description,
        priority=priority,
        source="manual",
        created_at=datetime.now(timezone.utc),
    )
