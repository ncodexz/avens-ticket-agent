"""
3-level escalation ladder (deterministic, same reasoning as decide_verdict.py:
this is a decision, not a judgment call, so it's plain Python, not an LLM).

Level 1 - self-service: unambiguous, high-confidence verdict. The proposed
action can be applied without a human reviewing it first.
Level 2 - technical escalation: a human needs to decide, but with context
already gathered (classification, similar past tickets, confidence).
Level 3 - authority escalation: requires permissions/sign-off beyond a
regular technician.

NOTE (provisional): we don't yet have a real signal from Ayvens for when a
ticket actually requires Level 3 (which use cases/fields need authority-level
sign-off), so Level 3 is never returned here — it's a placeholder until we
get that information. We are not guessing it, to avoid inventing a rule
we'd have to unwind later. Same caveat for the 0.85 self-service threshold
below: it is not derived from real Ayvens data, just a reasonable starting
point to validate the pipeline end-to-end.
"""

from core.state import Verdict, EscalationLevel

SELF_SERVICE_CONFIDENCE_THRESHOLD = 0.85  # provisional, not from real Ayvens data


def decide_escalation(verdict: Verdict) -> tuple[EscalationLevel, bool]:
    request_type = verdict["request_type"]
    confidence = verdict["confidence"]

    if request_type == "indeterminate":
        return "level_2_technical", True

    if confidence >= SELF_SERVICE_CONFIDENCE_THRESHOLD:
        return "level_1_self_service", False

    return "level_2_technical", True