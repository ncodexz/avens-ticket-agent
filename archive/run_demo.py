"""
End-to-end demo: ORG tools (mock, for now) + our agent, wired together
exactly as the real pipeline will be:

  read_ticket -> retrieve_similar_tickets -> [our agent] -> create_comment -> update_status

Run with: python demo/run_demo.py <ticket_id>
Example:  python demo/run_demo.py UC1-001
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.registry import get_tools
from agent.router import route
from agent.extract_signals import extract_signals
from agent.decide_verdict import decide_verdict
from agent.generate_resolution import generate_resolution
from agent.decide_escalation import decide_escalation


def run_pipeline(ticket_id: str) -> dict:
    read_ticket, retrieve_similar_tickets, create_comment, update_status = get_tools()

    # --- ORG tools ---
    ticket = read_ticket(ticket_id)
    similar = retrieve_similar_tickets(ticket)

    # --- our agent (TEAM = "Generate resolution" in the real architecture) ---
    use_case = route(ticket)
    signals = extract_signals(ticket, use_case)
    request_type, confidence, decision_reason = decide_verdict(signals)
    verdict = {
        "use_case": use_case,
        "signals": signals,
        "request_type": request_type,
        "confidence": confidence,
        "decision_reason": decision_reason,
        "needs_more_info": request_type == "indeterminate",
    }
    resolution_text = generate_resolution(ticket, verdict, similar)
    escalation_level, requires_human_review = decide_escalation(verdict)

    # --- ORG tools again ---
    create_comment(ticket_id, resolution_text)
    update_status(ticket_id, escalation_level)

    return {
        "ticket_id": ticket_id,
        "verdict": verdict,
        "resolution_text": resolution_text,
        "escalation_level": escalation_level,
        "requires_human_review": requires_human_review,
    }


if __name__ == "__main__":
    import json

    ticket_id = sys.argv[1] if len(sys.argv) > 1 else "UC1-001"
    result = run_pipeline(ticket_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))