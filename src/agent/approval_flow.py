"""
Generic 3-node approval pattern, reused for any action that needs human
approval before executing: propose an action -> pause for approval ->
execute if approved. Used for SQL queries, ticket comments, and status
updates — same shape, different propose/validate/execute functions.
"""

from typing import TypedDict, Optional, Callable
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver


class ApprovalState(TypedDict):
    input_data: dict
    proposal: Optional[dict]
    approved: Optional[bool]
    result: Optional[dict]
    error: Optional[str]


def build_approval_graph(propose_fn: Callable[[dict], dict],
                          validate_fn: Callable[[dict], tuple],
                          execute_fn: Callable[[dict], dict]):
    def propose(state: ApprovalState) -> ApprovalState:
        proposal = propose_fn(state["input_data"])
        is_valid, reason = validate_fn(proposal)
        if not is_valid:
            return {**state, "error": f"Rejected before reaching human: {reason}"}
        return {**state, "proposal": proposal}

    def wait_for_approval(state: ApprovalState) -> ApprovalState:
        if state.get("error"):
            return state
        decision = interrupt(state["proposal"])
        return {**state, "approved": decision.get("approved", False)}

    def execute(state: ApprovalState) -> ApprovalState:
        if state.get("error"):
            return state
        if not state.get("approved"):
            return {**state, "result": None, "error": "Human rejected the action."}
        result = execute_fn(state["proposal"])
        return {**state, "result": result}

    graph = StateGraph(ApprovalState)
    graph.add_node("propose", propose)
    graph.add_node("wait_for_approval", wait_for_approval)
    graph.add_node("execute", execute)
    graph.set_entry_point("propose")
    graph.add_edge("propose", "wait_for_approval")
    graph.add_edge("wait_for_approval", "execute")
    graph.add_edge("execute", END)

    return graph.compile(checkpointer=MemorySaver())