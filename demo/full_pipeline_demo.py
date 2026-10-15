import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from langgraph.types import Command

from agent.router_b import route_b
from agent.generate_resolution_from_sql import generate_resolution
from agent.decide_escalation import decide_escalation
from agent.approval_flow import build_approval_graph
from agent.ticket_actions import propose_comment, propose_status
from tests.mock_openproject import (
    validate_comment_proposal, validate_status_proposal,
    execute_comment, execute_status,
)
from demo.test_sql_approval_flow import app as sql_app


def run_full_pipeline(ticket_id: str, ticket_text: str, approve_all: bool = True):
    print(f"\n{'='*60}\nTicket: {ticket_id}\n{'='*60}")

    # 1. Route
    routing = route_b(ticket_text)
    print(f"Routing: {routing}")
    if routing["needs_human_review"]:
        print("-> Ambiguous or insufficient info. Stopping for human triage.")
        return

    # 2. Propose + approve + execute SQL
    sql_config = {"configurable": {"thread_id": f"{ticket_id}-sql"}}
    sql_app.invoke({"ticket_text": ticket_text}, config=sql_config)
    sql_final = sql_app.invoke(Command(resume={"approved": approve_all}), config=sql_config)
    if sql_final.get("error"):
        print(f"-> SQL step stopped: {sql_final['error']}")
        return
    sql_result = sql_final["result"]
    sql_text = sql_final["proposal"]["sql"]
    print(f"SQL proposed: {sql_text}")
    print(f"SQL result: {sql_result}")

        # 3. Generate resolution from the real result
    resolution = generate_resolution(ticket_text, sql_text, sql_result)
    resolution_text = resolution["resolution_text"]
    ready_to_close = resolution["ready_to_close"]
    print(f"Resolution: {resolution_text} (ready_to_close={ready_to_close})")

    # 4. Decide escalation
    # decide_escalation only reads request_type (to check "indeterminate")
    # and confidence. We now force "indeterminate" whenever routing flagged
    # review OR the resolution itself says this isn't actually finished -
    # that second part is the fix for the Closed-while-pending-action bug.
    verdict = {
        "request_type": "indeterminate" if (routing["needs_human_review"] or not ready_to_close) else "real_error",
        "confidence": max(routing["scores"].values()),
    }
    escalation_level, needs_more_info = decide_escalation(verdict)
    print(f"Escalation: {escalation_level} (needs_more_info={needs_more_info})")

    # 5. Propose + approve comment
    comment_graph = build_approval_graph(propose_comment, validate_comment_proposal, execute_comment)
    comment_config = {"configurable": {"thread_id": f"{ticket_id}-comment"}}
    comment_graph.invoke({
        "input_data": {"ticket_id": ticket_id, "ticket_text": ticket_text, "resolution_text": resolution_text}
    }, config=comment_config)
    comment_final = comment_graph.invoke(Command(resume={"approved": approve_all}), config=comment_config)
    print(f"Comment result: {comment_final.get('result') or comment_final.get('error')}")

    # 6. Propose + approve status
    status_graph = build_approval_graph(propose_status, validate_status_proposal, execute_status)
    status_config = {"configurable": {"thread_id": f"{ticket_id}-status"}}
    status_graph.invoke({
        "input_data": {"ticket_id": ticket_id, "escalation_level": escalation_level}
    }, config=status_config)
    status_final = status_graph.invoke(Command(resume={"approved": approve_all}), config=status_config)
    print(f"Status result: {status_final.get('result') or status_final.get('error')}")


if __name__ == "__main__":
    run_full_pipeline(
        "ROUTE-UC1",
        "El código local ES-4471 aparece sin mapeo asignado en el sistema.",
    )