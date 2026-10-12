"""
Decides which use case (UC1/UC2/UC3) a ticket belongs to.

For now this is a placeholder: in the real hackathon, tickets probably
arrive already tagged to a queue/project (OpenProject work packages are
typically organized by project), so routing may be nearly free. Until we
know that for certain, this does a simple keyword-based guess so the rest
of the pipeline has something to call.
"""

from core.state import TicketRaw


def route(ticket: TicketRaw) -> str:
    fields = ticket.get("fields", {})
    fields_text = str(fields).lower()

    if "reporting month" in fields_text or "reported figures" in fields_text:
        return "UC2"
    if "customer ids" in fields_text or "business rules" in fields_text:
        return "UC3"
    if any(k in fields for k in ("Class ID", "Holding value", "Local code", "Mapping details")):
        return "UC1"

    # Fallback: default to UC1 and flag it — a real router needs a real
    # signal (queue/project tag) rather than guessing from free text.
    return "UC1"