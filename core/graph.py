"""The whole flow as a LangGraph graph: route -> decide -> solve -> human approval -> delivery.

The functions of the other modules are the nodes; this file only connects them. Nothing in
rules, mapping or the router changed, so the measured results stay valid.

                     +--> rules (UC2, UC3) --+--> undetermined (no row, CSV for a person)
    route --decide---+                       +--> approval --> deliver_email / deliver_sql
                     +--> mapping (UC1) -----+        |                      \
                     |                       |        +--> rejected          registry
                     +--> manual (routing failed)
    rules or mapping that find nothing to work with -> free (the model investigates) -> approval

The decision node is `decide`: plain Python reads the routing result and returns the name
of the next node. The model only estimates the use case (core.router); it never picks a node.
Human approval is a real pause: `interrupt` stops the graph and `Command(resume=...)` continues it.
Everything that touches the outside is passed in (`Deps`), so the tests need no model and no Databricks.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from core import registry, router, rules, solver, undetermined
from core.router import RoutingError
from core.ticket import Ticket


class FlowState(TypedDict, total=False):
    ticket: Ticket
    route: Any            # core.router.RouteResult
    uc: str
    proposal: Any         # core.solver.Proposal
    approval: dict        # {"approved": bool, "comment": str}
    outcome: str          # delivered | rejected | undetermined | manual


@dataclass
class Deps:
    """What the graph needs from the outside. None means: use the real one."""
    run_id: str = ""
    chat: Optional[Callable] = None            # calls the model
    run_sql: Optional[Callable] = None         # runs a read-only query on Databricks
    catalog: Optional[str] = None
    neighbours_fn: Optional[Callable] = None   # closest solved tickets (core.rag.retrieve_similar)
    send_email: Optional[Callable] = None      # writes one row to solutions_emails_sent (Spark only)
    registry_path: Any = None
    undetermined_path: Any = None


def _neighbours(deps, ticket, uc):
    fn = deps.neighbours_fn
    if fn is None:
        from core import rag
        fn = rag.retrieve_similar
    try:
        return fn(ticket, k=3, uc=uc)
    except Exception:   # no index built yet: the model still works, without precedents
        return []


def build_graph(deps=None, checkpointer=None):
    deps = deps or Deps()

    def log(state, record_state, ticket_type=None, comment=None, row=None, extra=None):
        registry.append_record(deps.run_id, state["ticket"], uc=state.get("uc"), ticket_type=ticket_type,
                               state=record_state, proposed_comment=comment, delivered_row=row,
                               extra=extra, path=deps.registry_path)

    # ---- nodes ---------------------------------------------------------------------------
    def route_node(state: FlowState):
        ticket = state["ticket"]
        try:
            result = router.route(ticket, run_id=deps.run_id, chat=deps.chat)
        except RoutingError as error:
            log(state, "pending", extra={"routing_error": str(error)})
            return {"route": None, "uc": "", "outcome": "manual"}
        log({**state, "uc": result.top_uc}, "pending",
            extra={"scores": result.scores, "ambiguous": result.is_ambiguous, "reason": result.reason})
        return {"route": result, "uc": result.top_uc}

    def rules_node(state: FlowState):
        return {"proposal": rules.solve(state["ticket"], run_sql=deps.run_sql, catalog=deps.catalog)}

    def mapping_node(state: FlowState):
        from core import mapping
        spent = {"tokens": 0, "calls": 0, "model": ""}
        neighbours = _neighbours(deps, state["ticket"], "UC1")
        done = mapping.solve(state["ticket"], neighbours, spent, run_id=deps.run_id, chat=deps.chat,
                             run_sql=deps.run_sql, catalog=deps.catalog)
        if done is not None:
            done.total_tokens, done.calls, done.model = spent["tokens"], spent["calls"], spent["model"]
        return {"proposal": done}

    def free_node(state: FlowState):
        uc = state["uc"]
        neighbours = _neighbours(deps, state["ticket"], uc)
        return {"proposal": solver._solve_free(state["ticket"], uc, neighbours, run_id=deps.run_id,
                                               chat=deps.chat, run_sql=deps.run_sql, catalog=deps.catalog)}

    def undetermined_node(state: FlowState):
        proposal = state["proposal"]
        added = undetermined.record(state["ticket"], proposal.diagnosis, path=deps.undetermined_path)
        log(state, "undetermined", comment=proposal.comment,
            extra={"finding": proposal.finding, "listed_now": added})
        return {"outcome": "undetermined"}

    def manual_node(state: FlowState):
        return {"outcome": "manual"}

    def approval_node(state: FlowState):
        proposal = state["proposal"]
        log(state, "pending", ticket_type=proposal.ticket_type, comment=proposal.comment,
            extra={"finding": proposal.finding, "model": proposal.model, "tokens": proposal.total_tokens})
        answer = interrupt({
            "ticket_id": state["ticket"].op_id, "uc": state["uc"], "ticket_type": proposal.ticket_type,
            "finding": proposal.finding, "comment": proposal.comment, "solution": proposal.solution,
            "statements": proposal.statements,
        })
        return {"approval": {"approved": bool(answer.get("approved")), "comment": answer.get("comment")}}

    def deliver_email_node(state: FlowState):
        proposal = state["proposal"]
        comment = state["approval"].get("comment") or proposal.comment
        ticket = state["ticket"]
        ticket_id = str(ticket.mapping_id or ticket.op_id)   # the id Alenia's solutions table uses
        row = {"ticket_id": ticket_id, **proposal.solution, "comment": comment}
        if deps.send_email is not None:
            deps.send_email(row)
        log(state, "closed", ticket_type="email", comment=comment, row=row)
        return {"outcome": "delivered"}

    def deliver_sql_node(state: FlowState):
        proposal = state["proposal"]
        comment = state["approval"].get("comment") or proposal.comment
        # The approval of a UC1 ticket is the confirmation of the change. The statements stay as text.
        log(state, "closed", ticket_type="sql", comment=comment, row={"statements": proposal.statements})
        return {"outcome": "delivered"}

    def rejected_node(state: FlowState):
        proposal = state["proposal"]
        log(state, "rejected", ticket_type=proposal.ticket_type, comment=proposal.comment)
        return {"outcome": "rejected"}

    # ---- decisions (plain Python, no model) -----------------------------------------------
    def decide(state: FlowState):
        if state.get("route") is None:
            return "manual"
        return "mapping" if state["uc"] == "UC1" else "rules"

    def after_solving(state: FlowState):
        proposal = state.get("proposal")
        if proposal is None:
            return "free"
        if proposal.status == "undetermined":
            return "undetermined"
        return "approval"

    def after_free(state: FlowState):
        return "approval"

    def after_approval(state: FlowState):
        if not state["approval"]["approved"]:
            return "rejected"
        return "deliver_sql" if state["proposal"].ticket_type == "sql" else "deliver_email"

    graph = StateGraph(FlowState)
    for name, node in [("route", route_node), ("rules", rules_node), ("mapping", mapping_node),
                       ("free", free_node), ("undetermined", undetermined_node), ("manual", manual_node),
                       ("approval", approval_node), ("deliver_email", deliver_email_node),
                       ("deliver_sql", deliver_sql_node), ("rejected", rejected_node)]:
        graph.add_node(name, node)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", decide, ["rules", "mapping", "manual"])
    graph.add_conditional_edges("rules", after_solving, ["free", "undetermined", "approval"])
    graph.add_conditional_edges("mapping", after_solving, ["free", "undetermined", "approval"])
    graph.add_conditional_edges("free", after_free, ["approval"])
    graph.add_conditional_edges("approval", after_approval, ["rejected", "deliver_sql", "deliver_email"])
    for final in ("undetermined", "manual", "deliver_email", "deliver_sql", "rejected"):
        graph.add_edge(final, END)
    return graph.compile(checkpointer=checkpointer or MemorySaver())


def _config(ticket):
    return {"configurable": {"thread_id": str(ticket.op_id)}}


def start(graph, ticket):
    """Run a ticket until it ends or waits for a person. Returns the graph result; when it is waiting,
    result["__interrupt__"] holds what the person has to approve."""
    return graph.invoke({"ticket": ticket}, _config(ticket))


def resume(graph, ticket, approved, comment=None):
    """The person decided: continue the ticket from the approval."""
    return graph.invoke(Command(resume={"approved": approved, "comment": comment}), _config(ticket))
