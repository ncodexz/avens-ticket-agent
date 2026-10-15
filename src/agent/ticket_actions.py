"""
Proposals for the two remaining HITL-gated actions: posting a comment and
changing a ticket's status.
"""

from llm_client import chat_json

COMMENT_PROMPT = """You are drafting a comment to post on a support ticket.

Ticket text:
{ticket_text}

Resolution found:
{resolution_text}

Return JSON with exactly these fields:
- "ticket_id": the ticket id this comment is for
- "comment_text": the exact comment to post, written professionally for the
  person who filed the ticket
- "purpose": one or two sentences explaining to a human reviewer why this
  comment is appropriate and what it tells the requester
"""

STATUS_BY_ESCALATION = {
    "level_1_self_service": "Closed",
    "level_2_technical": "In progress",
    "level_3_authority": "On hold",
}


def propose_comment(input_data: dict) -> dict:
    prompt = COMMENT_PROMPT.format(
        ticket_text=input_data["ticket_text"],
        resolution_text=input_data["resolution_text"],
    )
    result = chat_json(prompt)
    result["ticket_id"] = input_data["ticket_id"]
    return result


def propose_status(input_data: dict) -> dict:
    escalation_level = input_data["escalation_level"]
    new_status = STATUS_BY_ESCALATION.get(escalation_level, "In progress")
    return {
        "ticket_id": input_data["ticket_id"],
        "new_status": new_status,
        "purpose": (
            f"Proposing status '{new_status}' because the agent classified "
            f"this ticket as '{escalation_level}'."
        ),
    }