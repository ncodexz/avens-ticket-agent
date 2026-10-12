"""
Mock version of the ORG tool `read_ticket`. Alenia's real version will pull
from OpenProject; ours pulls from our own hand-written test tickets so we
can build and test everything without it.
"""

from core.state import TicketRaw
from tests.sample_tickets import ALL_TICKETS_BY_ID


def read_ticket(ticket_id: str) -> TicketRaw:
    if ticket_id not in ALL_TICKETS_BY_ID:
        raise KeyError(f"Mock read_ticket: no test ticket registered with id '{ticket_id}'")
    return ALL_TICKETS_BY_ID[ticket_id]