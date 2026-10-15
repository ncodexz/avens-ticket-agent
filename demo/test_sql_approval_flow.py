"""
Minimal LangGraph demo proving the full flow works end to end:
propose SQL -> validate -> PAUSE for human approval -> resume -> execute.

The expensive step (propose_sql, which calls the LLM) lives in its own node
that runs exactly once. The node that calls interrupt() does nothing but
read already-computed state, so re-running it on resume costs nothing.
"""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

from agent.propose_sql import propose_sql
from agent.sql_executor import validate_select_only, execute_query

class SQLApprovalState(TypedDict):
    ticket_text: str
    proposal: Optional[dict]
    approved: Optional[bool]
    result: Optional[list]
    error: Optional[str]


def propose(state: SQLApprovalState) -> SQLApprovalState:
    proposal = propose_sql(state["ticket_text"])
    is_valid, reason = validate_select_only(proposal["sql"])
    if not is_valid:
        return {**state, "error": f"Rejected before reaching human: {reason}"}
    return {**state, "proposal": proposal}


def wait_for_approval(state: SQLApprovalState) -> SQLApprovalState:
    if state.get("error"):
        return state

    decision = interrupt({
        "table": state["proposal"]["table"],
        "sql": state["proposal"]["sql"],
        "purpose": state["proposal"]["purpose"],
    })

    return {**state, "approved": decision.get("approved", False)}


def execute(state: SQLApprovalState) -> SQLApprovalState:
    if state.get("error"):
        return state
    if not state.get("approved"):
        return {**state, "result": None, "error": "Human rejected the query."}

    rows = execute_query(state["proposal"]["sql"])
    return {**state, "result": rows}


graph = StateGraph(SQLApprovalState)
graph.add_node("propose", propose)
graph.add_node("wait_for_approval", wait_for_approval)
graph.add_node("execute", execute)
graph.set_entry_point("propose")
graph.add_edge("propose", "wait_for_approval")
graph.add_edge("wait_for_approval", "execute")
graph.add_edge("execute", END)

app = graph.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "sql-approval-demo-1"}}
    ticket_text = """Missing contract CON_a496abb07de48cbc in Fleet Report - Wise Potato Industries SL

    Good morning,
    Sorry to bother you - I may be missing something, but I can't see contract CON_a496abb07de48cbc for Wise Potato Industries SL in the Fleet Report. Would you mind double-checking whether it should be there?
    Many thanks in advance"""

    print("=== Running until interrupt ===")
    result = app.invoke({"ticket_text": ticket_text}, config=config)
    print(result)

    print("\n=== Simulating human approval ===")
    final_result = app.invoke(Command(resume={"approved": True}), config=config)
    print(final_result)