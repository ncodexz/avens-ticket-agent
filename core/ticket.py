"""Single ticket format.

Input:  the data of a ticket from any source (adapters convert it to this shape).
Output: a Ticket object that always has the same fields.
Used by: all of layer 1 (ticket reading) and every later block.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Resolution order: the lower the number, the sooner the ticket is resolved.
PRIORITY_RANK = {"Immediate": 0, "High": 1, "Normal": 2, "Low": 3}

SOURCES = {"openproject", "csv", "databricks", "manual"}


@dataclass(frozen=True)
class Ticket:
    title: str
    description: str
    priority: str
    source: str
    created_at: datetime                 # always timezone-aware (UTC)
    op_id: Optional[int] = None          # OpenProject number (32364...)
    mapping_id: Optional[str] = None     # Alenia internal number (6041134...)
    source_status: Optional[str] = None  # status in the source (New, Closed...)

    def __post_init__(self):
        if not self.title.strip():
            raise ValueError("Ticket has no title")
        if self.priority not in PRIORITY_RANK:
            raise ValueError(f"Unknown priority: {self.priority!r}")
        if self.source not in SOURCES:
            raise ValueError(f"Unknown source: {self.source!r}")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")

    def sort_key(self):
        """Priority first; within a priority, the oldest first."""
        return (PRIORITY_RANK[self.priority], self.created_at, self.op_id or 0)
