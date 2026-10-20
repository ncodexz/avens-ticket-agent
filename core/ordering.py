"""Resolution order: Immediate > High > Normal > Low; oldest first inside a priority."""


def order_tickets(tickets):
    return sorted(tickets, key=lambda ticket: ticket.sort_key())
