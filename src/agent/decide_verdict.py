"""
Deterministic decision table. This is plain Python on purpose.

Lesson learned the hard way: asking an LLM to both extract facts AND decide
AND police its own confidence, all in one free-text reasoning block, is
unstable — fixing one test case silently breaks another, and the model
ignores explicit numeric rules (e.g. "keep confidence below 0.75 when
signals conflict"). Real systems (CORTEX - arxiv 2510.00311; a documented
SOC triage agent) solve this the same way we do here: extraction stays
with the LLM, the verdict is a fixed rule table in code.

Rule order matters — read top to bottom, first match wins.
"""

from core.state import Signals, RequestType


def decide_verdict(signals: Signals) -> tuple[RequestType, float, str]:
    if signals.get("requester_expresses_doubt"):
        return "indeterminate", 0.6, "requester expresses doubt"

    if signals.get("official_communication_mentioned"):
        return "communicated_change", 0.9, "official communication mentioned"

    if signals.get("incorrect_value_explicitly_stated"):
        return "real_error", 0.9, "explicit value mismatch stated"

    looks_new = signals.get("looks_new")
    is_broken = signals.get("something_that_worked_is_now_broken")

    if looks_new and not is_broken:
        return "legitimate_new_request", 0.9, "new item, nothing broken"
    if is_broken and not looks_new:
        return "real_error", 0.9, "broken, not new, no communication"
    if looks_new and is_broken:
        return "indeterminate", 0.5, "genuine conflict between signals"

    return "indeterminate", 0.3, "no clear signal"