"""
Routing — adapted version (inspired by closed-choice, calibrated-confidence
models like Jev/TypeSafe AI). One LLM call returns a probability per use
case instead of a single label. The ambiguity check is plain Python, not
the LLM's job — same discipline as decide_verdict.py: the model estimates,
the code decides.

Experiment file: compared against router_a.py (single label) to decide
which routing approach the real system should use.
"""

from llm_client import chat_json

KNOWN_CATEGORIES = """
UC1 - Normalization Management: new local codes appear, existing local codes
change, new holding values required, existing holding values change,
mappings are incorrect, values are not mapped.

UC2 - Monthly Report Reconciliation: contract count differences, customer
count differences, status discrepancies, missing business activity.

UC3 - Data Verification & Correction: missing dates, missing contract data,
missing vehicle data, incorrect status information, data quality issues.
"""

PROMPT_TEMPLATE = """You are routing an Ayvens IT ticket to one of three use cases.

{categories}

Ticket:
{ticket_text}

Estimate the probability (0.0 to 1.0) that this ticket belongs to each use
case. The three probabilities should add up to approximately 1.0.

Return ONLY this JSON: {{"UC1": 0.0, "UC2": 0.0, "UC3": 0.0}}
"""

AMBIGUITY_MARGIN = 0.20        # top vs second place too close
MIN_CONFIDENCE_THRESHOLD = 0.5  # top score too low on its own — not enough signal


def route_b(ticket_text: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(categories=KNOWN_CATEGORIES, ticket_text=ticket_text)
    scores = chat_json(prompt)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_uc, top_score = ranked[0]
    second_uc, second_score = ranked[1]

    is_ambiguous = (top_score - second_score) < AMBIGUITY_MARGIN
    is_insufficient_information = top_score < MIN_CONFIDENCE_THRESHOLD

    needs_human_review = is_ambiguous or is_insufficient_information

    return {
        "scores": scores,
        "use_case": top_uc if not needs_human_review else None,
        "is_ambiguous": is_ambiguous,
        "is_insufficient_information": is_insufficient_information,
        "needs_human_review": needs_human_review,
        "top_two": [(top_uc, top_score), (second_uc, second_score)],
    }