"""
Routing — traditional version. Single LLM call, picks one use case directly.
Experiment file: compared against router_b.py (probability distribution)
to decide which routing approach the real system should use.
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

Return ONLY this JSON: {{"use_case": "UC1" | "UC2" | "UC3", "reasoning": "..."}}
"""


def route_a(ticket_text: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(categories=KNOWN_CATEGORIES, ticket_text=ticket_text)
    return chat_json(prompt)