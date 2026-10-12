"""
Extraction-only step. The LLM's ONLY job here is to find 5 independent
facts in the ticket text, each with a supporting quote. It does NOT decide
anything — that's decide_verdict.py's job, in plain Python.

Why split like this: a single prompt that both extracts AND decides is
unstable — fixing one test case silently breaks another, and the model
ignores explicit numeric rules. Real systems (CORTEX - arxiv 2510.00311;
a documented SOC triage agent) solve this the same way: extraction stays
with the LLM, the verdict is a fixed rule table in code (see decide_verdict.py).
"""

import json
from core.state import TicketRaw, Signals
from core.use_cases import USE_CASES
from llm_client import chat_json

PROMPT_TEMPLATE = """You are analyzing an IT ticket for Ayvens, a fleet leasing company.
This ticket belongs to the "{name}" use case: {context}.

Your ONLY job is to extract 5 independent facts from the ticket text. Do NOT draw any final conclusion. Just answer what the text actually says.

For each fact, answer true, false, or null (the ticket does not mention this at all). If true or false, quote the exact phrase that supports it. Do not infer beyond what is written.

1. looks_new: is the item described as newly created / onboarding?
2. official_communication_mentioned: does the ticket reference an announced, approved, or officially communicated CHANGE EVENT (not a reference to a standard/manual value)?
3. something_that_worked_is_now_broken: does the ticket describe something that used to work and is now broken/blocked?
4. requester_expresses_doubt: does the requester themselves say they are unsure?
5. incorrect_value_explicitly_stated: does the ticket state a concrete mismatch between an actual value and a known/expected correct value, regardless of timing?

Return ONLY this JSON:
{{
  "looks_new": true/false/null, "evidence_new": "...",
  "official_communication_mentioned": true/false/null, "evidence_communication": "...",
  "something_that_worked_is_now_broken": true/false/null, "evidence_continuity": "...",
  "requester_expresses_doubt": true/false/null, "evidence_doubt": "...",
  "incorrect_value_explicitly_stated": true/false/null, "evidence_incorrect_value": "..."
}}

Ticket:
{ticket_text}

Additional fields:
{ticket_fields}
"""


def extract_signals(ticket: TicketRaw, use_case: str) -> Signals:
    config = USE_CASES[use_case]
    prompt = PROMPT_TEMPLATE.format(
        name=config["name"],
        context=config["context"],
        ticket_text=ticket["text"],
        ticket_fields=json.dumps(ticket["fields"], ensure_ascii=False),
    )
    return chat_json(prompt)