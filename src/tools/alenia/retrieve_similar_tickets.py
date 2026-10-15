"""
Real implementation of the ORG tool `retrieve_similar_tickets`, meant to
query Alenia's Mosaic AI Vector Search index over historical tickets.

STATUS: not implemented yet — we haven't confirmed whether a Vector Search
endpoint exists for our team. This raises on purpose instead of silently
falling back to fake data.
"""

from core.state import TicketRaw, SimilarTicket


def retrieve_similar_tickets(ticket: TicketRaw, k: int = 3) -> list[SimilarTicket]:
    raise NotImplementedError(
        "retrieve_similar_tickets: real Vector Search connection not built yet."
    )