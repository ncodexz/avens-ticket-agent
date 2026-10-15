import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from langgraph.types import Command
from agent.approval_flow import build_approval_graph
from agent.ticket_actions import propose_comment, propose_status
from tests.mock_openproject import (
    validate_comment_proposal, validate_status_proposal,
    execute_comment, execute_status,
)

comment_graph = build_approval_graph(propose_comment, validate_comment_proposal, execute_comment)
status_graph = build_approval_graph(propose_status, validate_status_proposal, execute_status)

if __name__ == "__main__":
    comment_input = {
        "input_data": {
            "ticket_id": "ROUTE-UC1",
            "ticket_text": "El código local ES-4471 aparece sin mapeo asignado en el sistema.",
            "resolution_text": "El código ES-4471 no tiene holding asignado en MD_LOCALVALUE_T. Se asignará el holding correcto.",
        }
    }
    config1 = {"configurable": {"thread_id": "comment-demo-1"}}
    print("=== Comment: proposing ===")
    print(comment_graph.invoke(comment_input, config=config1))
    print("\n=== Comment: approving ===")
    print(comment_graph.invoke(Command(resume={"approved": True}), config=config1))

    status_input = {
        "input_data": {"ticket_id": "ROUTE-UC1", "escalation_level": "level_2_technical"},
    }
    config2 = {"configurable": {"thread_id": "status-demo-1"}}
    print("\n=== Status: proposing ===")
    print(status_graph.invoke(status_input, config=config2))
    print("\n=== Status: approving ===")
    print(status_graph.invoke(Command(resume={"approved": True}), config=config2))
