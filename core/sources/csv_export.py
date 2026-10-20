"""Ticket source: the CSV exported from OpenProject (work_packages.csv).

Works offline, so it is the source used for tests with real tickets.
"""

import csv
from datetime import datetime
from pathlib import Path

from core.config import export_dir
from core.ticket import Ticket


def parse_iso(value):
    """'2026-10-14T21:12:57.467Z' -> timezone-aware datetime in UTC."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def default_path():
    return Path(export_dir()) / "openproject" / "work_packages.csv"


def read_tickets(path=None):
    path = Path(path) if path else default_path()
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        Ticket(
            title=row["subject"],
            description=row["description"],
            priority=row["priority"],
            source="csv",
            created_at=parse_iso(row["createdAt"]),
            op_id=int(row["id"]),
            source_status=row["status"],
        )
        for row in rows
    ]
