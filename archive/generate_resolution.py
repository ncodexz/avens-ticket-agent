"""
Generates the human-readable resolution text. Unlike decide_verdict.py,
this genuinely IS an LLM's job — writing a clear explanation and a concrete
action is language generation, not a decision with a fixed set of outcomes.

The verdict (request_type, decision_reason) is already decided before this
runs — this step explains and proposes an action, it does not re-decide
anything.
"""

from core.state import TicketRaw, Verdict, SimilarTicket
from llm_client import chat_json

PROMPT_TEMPLATE = """You are writing the resolution text for an Ayvens IT ticket.

The classification has ALREADY been decided — do not question or change it,
only explain it and propose a concrete next action consistent with it.

Classification: {request_type}
Reason: {decision_reason}
Confidence: {confidence}

Ticket:
{ticket_text}

Similar past tickets and how they were resolved (use these for tone/pattern,
not as ground truth for this ticket):
{similar_text}

Write a short resolution (3-5 sentences) in the ticket's own language, with:
1. A one-line diagnosis consistent with the classification above.
2. A concrete next action.
3. If confidence is below 0.7, say explicitly what information is missing.

Return ONLY this JSON: {{"resolution_text": "..."}}
"""


def generate_resolution(ticket: TicketRaw, verdict: Verdict, similar: list[SimilarTicket]) -> str:
    similar_text = "\n".join(
        f"- {s['text']} -> {s['resolution']} (similarity {s['similarity']})" for s in similar
    ) or "(none found)"

    prompt = PROMPT_TEMPLATE.format(
        request_type=verdict["request_type"],
        decision_reason=verdict["decision_reason"],
        confidence=verdict["confidence"],
        ticket_text=ticket["text"],
        similar_text=similar_text,
    )
    result = chat_json(prompt)
    return result["resolution_text"]
