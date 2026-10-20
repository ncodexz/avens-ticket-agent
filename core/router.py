"""Routing: decide which use case (UC1, UC2, UC3) a ticket belongs to.

Design (taken from the previous project's router_b; the UC2 vs UC3 rule was changed so
  that a contract missing from the Fleet Report is UC2, and UC1 is protected):
- ONE model call returns a probability for each use case.
- The model only estimates. Plain Python decides whether the result is ambiguous.
- Only the title and description go to the model, never a solution comment.
Use case definitions come from the Participant Kit.
"""

import json
import re
from dataclasses import dataclass, field

from core import llm_client
from core.ticket import Ticket

USE_CASES = ("UC1", "UC2", "UC3")
AMBIGUITY_MARGIN = 0.20   # top two scores closer than this -> ambiguous
MIN_CONFIDENCE = 0.50     # best score lower than this -> ambiguous
MAX_DESCRIPTION_CHARS = 4000

PROMPT = """You are routing an Ayvens IT ticket to one of three use cases.

UC1 - Normalization Management: new local codes appear, existing local codes
change, new holding values required, existing holding values change,
mappings are incorrect, values are not mapped.

UC2 - Monthly Report Reconciliation: contract count differences, customer
count differences, status discrepancies, missing business activity.

UC3 - Data Verification & Correction: missing dates, missing contract data,
missing vehicle data, incorrect status information, data quality issues.

Disambiguation rules:
- UC1 first: if the ticket is about a value, code or mapping that is not
  mapped or is mapped incorrectly (a make, model, product family, customer
  segment...), classify it as UC1, even if the wording names a vehicle,
  a model or a contract.
- UC2 vs UC3: if the ticket says that a contract is missing from the
  Fleet Report, or reports a monthly reconciliation difference (counts,
  totals, summary numbers that don't match), classify it as UC2
  (Monthly Report Reconciliation).
- If the ticket names a specific contract or vehicle that is missing or has
  incorrect data, and does NOT refer to the report or the reconciliation,
  classify it as UC3 (Data Verification & Correction).

Ticket title: {title}
Ticket description:
{description}

Reply with ONLY a JSON object with the probability of each use case (they must sum to 1):
{{"UC1": 0.0, "UC2": 0.0, "UC3": 0.0}}"""


class RoutingError(Exception):
    pass


@dataclass
class RouteResult:
    scores: dict
    top_uc: str
    is_ambiguous: bool
    reason: str
    model: str = ""
    total_tokens: int = 0
    raw: str = field(default="", repr=False)


def build_messages(ticket: Ticket):
    prompt = PROMPT.format(
        title=ticket.title, description=ticket.description[:MAX_DESCRIPTION_CHARS]
    )
    return [{"role": "user", "content": prompt}]


def parse_scores(text):
    match = re.search(r"\{.*?\}", text, flags=re.DOTALL)
    if not match:
        raise RoutingError(f"No JSON in model answer: {text[:200]!r}")
    try:
        data = json.loads(match.group(0))
        scores = {uc: float(data[uc]) for uc in USE_CASES}
    except (ValueError, KeyError, TypeError) as error:
        raise RoutingError(f"Bad scores in model answer: {text[:200]!r}") from error
    total = sum(scores.values())
    if total <= 0 or any(value < 0 for value in scores.values()):
        raise RoutingError(f"Scores cannot be used: {scores}")
    return {uc: value / total for uc, value in scores.items()}


def decide(scores):
    """The code, not the model, decides whether the answer is ambiguous."""
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    (top_uc, top), (_, second) = ranked[0], ranked[1]
    if top < MIN_CONFIDENCE:
        return top_uc, True, f"best score {top:.2f} is below {MIN_CONFIDENCE}"
    if top - second < AMBIGUITY_MARGIN:
        return top_uc, True, f"top two scores differ by {top - second:.2f}, less than {AMBIGUITY_MARGIN}"
    return top_uc, False, "clear"


def route(ticket: Ticket, run_id=None, chat=None):
    """chat is the function that calls the model; tests replace it with a fake one."""
    chat = chat or llm_client.chat
    answer = chat("routing", build_messages(ticket), run_id=run_id, ticket_id=ticket.op_id)
    scores = parse_scores(answer.text)
    top_uc, ambiguous, reason = decide(scores)
    return RouteResult(
        scores=scores, top_uc=top_uc, is_ambiguous=ambiguous, reason=reason,
        model=answer.model, total_tokens=answer.total_tokens, raw=answer.text,
    )
