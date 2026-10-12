"""
THE CONTRACT. This file defines the SHAPE of each tool the agent depends on,
nothing else. It must never import from mock/ or alenia/ — those depend on
this file, not the other way around.

If Alenia's real tools end up named differently or returning slightly
different fields, we don't change this contract: we write a thin adapter
inside tools/alenia/ that translates their real function into this shape.
agent/ code never changes because of that.
"""

from typing import Protocol
from core.state import TicketRaw, SimilarTicket


class ReadTicket(Protocol):
    def __call__(self, ticket_id: str) -> TicketRaw: ...


class RetrieveSimilarTickets(Protocol):
    def __call__(self, ticket: TicketRaw, k: int = 3) -> list[SimilarTicket]: ...


class CreateComment(Protocol):
    def __call__(self, ticket_id: str, comment: str) -> None: ...


class UpdateStatus(Protocol):
    def __call__(self, ticket_id: str, status: str) -> None: ...