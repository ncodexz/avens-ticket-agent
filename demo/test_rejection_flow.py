import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from langgraph.types import Command
from demo.test_sql_approval_flow import app as sql_app
from agent.approval_flow import build_approval_graph
from agent.ticket_actions import propose_comment, propose_status
from tests.mock_openproject import (
    validate_comment_proposal, validate_status_proposal,
    execute_comment, execute_status,
)

comment_graph = build_approval_graph(propose_comment, validate_comment_proposal, execute_comment)
status_graph = build_approval_graph(propose_status, validate_status_proposal, execute_status)

if __name__ == "__main__":
    print("=== SQL: rejecting ===")
    config = {"configurable": {"thread_id": "sql-reject-1"}}
    sql_app.invoke(
        {"ticket_text": "El código local ES-4471 aparece sin mapeo asignado en el sistema."},
        config=config,
    )
    print(sql_app.invoke(Command(resume={"approved": False}), config=config))

    print("\n=== Comment: rejecting ===")
    config = {"configurable": {"thread_id": "comment-reject-1"}}
    comment_graph.invoke({
        "input_data": {
            "ticket_id": "ROUTE-UC1",
            "ticket_text": "El código local ES-4471 aparece sin mapeo asignado en el sistema.",
            "resolution_text": "El código ES-4471 no tiene holding asignado en MD_LOCALVALUE_T.",
        }
    }, config=config)
    print(comment_graph.invoke(Command(resume={"approved": False}), config=config))

    print("\n=== Status: rejecting ===")
    config = {"configurable": {"thread_id": "status-reject-1"}}
    status_graph.invoke(
        {"input_data": {"ticket_id": "ROUTE-UC1", "escalation_level": "level_2_technical"}},
        config=config,
    )
    print(status_graph.invoke(Command(resume={"approved": False}), config=config))