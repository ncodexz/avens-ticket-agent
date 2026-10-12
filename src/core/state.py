"""
Shared types that travel through the whole pipeline.

Why this file exists: every stage (router, extract_signals, decide_verdict,
generate_resolution, decide_escalation) needs to agree on the SHAPE of a
ticket and of a verdict. If every stage invented its own dict keys, a typo
in one stage would silently break the next one. These types are the
single source of truth for that shape.
"""

from typing import TypedDict, Optional, Literal


# --- What a ticket looks like once Alenia (or our mock) hands it to us ---

class TicketRaw(TypedDict):
    ticket_id: str
    text: str
    fields: dict  # structured fields specific to the use case (Class ID, Subsidiary, etc.)


# --- What a "similar past ticket" from the RAG lookup looks like ---

class SimilarTicket(TypedDict):
    ticket_id: str
    text: str
    resolution: str
    similarity: float  # 0.0-1.0, how close it is to the current ticket


# --- The 5 extracted signals (see agent/extract_signals.py) ---

class Signals(TypedDict):
    looks_new: Optional[bool]
    evidence_new: Optional[str]
    official_communication_mentioned: Optional[bool]
    evidence_communication: Optional[str]
    something_that_worked_is_now_broken: Optional[bool]
    evidence_continuity: Optional[str]
    requester_expresses_doubt: Optional[bool]
    evidence_doubt: Optional[str]
    incorrect_value_explicitly_stated: Optional[bool]
    evidence_incorrect_value: Optional[str]


RequestType = Literal[
    "real_error",
    "legitimate_new_request",
    "communicated_change",
    "indeterminate",
]

EscalationLevel = Literal[
    "level_1_self_service",
    "level_2_technical",
    "level_3_authority",
]


# --- The final verdict, after decide_verdict.py runs ---

class Verdict(TypedDict):
    use_case: str  # "UC1", "UC2", "UC3"
    signals: Signals
    request_type: RequestType
    confidence: float
    decision_reason: str
    needs_more_info: bool


# --- The final output, after generate_resolution.py + decide_escalation.py run ---

class FinalResult(TypedDict):
    ticket_id: str
    verdict: Verdict
    resolution_text: str
    escalation_level: EscalationLevel
    requires_human_review: bool