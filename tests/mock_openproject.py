"""
In-memory mock of the two OpenProject actions the agent is allowed to take:
adding a comment and changing status. Statuses match what we confirmed
yesterday in the real OpenProject instance.
"""

VALID_STATUSES = ["New", "In progress", "Closed", "On hold", "Rejected"]

TICKETS = {
    "ROUTE-UC1": {"comments": [], "status": "New"},
    "ROUTE-UC2": {"comments": [], "status": "New"},
    "ROUTE-UC3": {"comments": [], "status": "New"},
}


def validate_comment_proposal(proposal: dict) -> tuple:
    if proposal.get("ticket_id") not in TICKETS:
        return False, f"Unknown ticket: {proposal.get('ticket_id')}"
    if not proposal.get("comment_text"):
        return False, "Comment text is empty."
    return True, ""


def validate_status_proposal(proposal: dict) -> tuple:
    if proposal.get("ticket_id") not in TICKETS:
        return False, f"Unknown ticket: {proposal.get('ticket_id')}"
    if proposal.get("new_status") not in VALID_STATUSES:
        return False, f"Invalid status: {proposal.get('new_status')}"
    return True, ""


def execute_comment(proposal: dict) -> dict:
    ticket_id = proposal["ticket_id"]
    TICKETS[ticket_id]["comments"].append(proposal["comment_text"])
    return {"ticket_id": ticket_id, "comment_added": proposal["comment_text"]}


def execute_status(proposal: dict) -> dict:
    ticket_id = proposal["ticket_id"]
    TICKETS[ticket_id]["status"] = proposal["new_status"]
    return {"ticket_id": ticket_id, "new_status": proposal["new_status"]}