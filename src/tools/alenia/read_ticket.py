"""
Real implementation of the ORG tool `read_ticket`, backed by OpenProject.
Adapts openproject_client's raw response into the shape tools/base.py
expects (TicketRaw), so agent/ code never needs to know OpenProject exists.
"""

from core.state import TicketRaw
from openproject_client import read_ticket as _read_ticket_from_openproject


def read_ticket(ticket_id: str) -> TicketRaw:
    wp = _read_ticket_from_openproject(int(ticket_id))
    subject = wp["subject"] or ""
    description = wp["description"] or ""
    text = f"{subject}\n\n{description}".strip()

    return TicketRaw(
        ticket_id=str(wp["id"]),
        text=text,
        fields={
            "priority": wp["priority"],
            "status": wp["status"],
            "type": wp["type"],
        },
    )