"""
Mock version of the ORG RAG function `retrieve_similar_tickets`. Alenia's
real version queries Mosaic AI Vector Search over historical synthetic
tickets. Ours just returns invented "similar tickets" so the rest of the
pipeline has something to work with during development.

This is intentionally dumb (no real similarity search) — it exists only so
generate_resolution.py has realistic-shaped input to build against.
"""

from core.state import TicketRaw, SimilarTicket


def retrieve_similar_tickets(ticket: TicketRaw, k: int = 3) -> list[SimilarTicket]:
    return [
        SimilarTicket(
            ticket_id=f"HIST-{i:03d}",
            text=f"(mock) historical ticket similar to {ticket['ticket_id']}",
            resolution="(mock) past resolution text — replace with real RAG output",
            similarity=round(0.9 - i * 0.1, 2),
        )
        for i in range(1, k + 1)
    ]