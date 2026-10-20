"""Tests for core/graph.py: every path of the graph, with no model and no Databricks."""
import csv
import json

import pytest

from core import graph as flow
from core import registry, solver
from core.llm_client import LLMResult
from core.solver import Proposal
from tests import test_mapping, test_rules

UC1_SCORES = '{"UC1": 0.9, "UC2": 0.05, "UC3": 0.05}'
UC3_SCORES = '{"UC1": 0.05, "UC2": 0.05, "UC3": 0.9}'


def chat_for(scores, **others):
    """Answers the routing step with `scores` and every other step as test_mapping.fake_chat does."""
    inner = test_mapping.fake_chat(**others) if others else None

    def chat(step, messages, **kw):
        if step == "routing":
            return LLMResult(scores, "fake", 100, 20, 120, 0.1)
        return inner(step, messages, **kw)
    return chat


def deps(tmp_path, chat, run_sql, sent=None):
    return flow.Deps(run_id="t", chat=chat, run_sql=run_sql, catalog=test_rules.CAT,
                     neighbours_fn=lambda *a, **k: [], send_email=(sent.append if sent is not None else None),
                     registry_path=tmp_path / "registry.jsonl", undetermined_path=tmp_path / "undetermined.csv")


def states(tmp_path):
    return [record["state"] for record in registry.read_records(tmp_path / "registry.jsonl")]


def test_uc3_stops_at_the_approval_and_an_approved_ticket_delivers_the_email(tmp_path):
    sent = []
    graph = flow.build_graph(deps(tmp_path, chat_for(UC3_SCORES), test_rules.warehouse(), sent))
    ticket = test_rules.ticket()
    paused = flow.start(graph, ticket)
    shown = paused["__interrupt__"][0].value
    assert shown["ticket_type"] == "email" and shown["solution"]["action"] == "input_data_reload"
    assert sent == [] and "outcome" not in paused                      # nothing is delivered before the person answers
    done = flow.resume(graph, ticket, approved=True)
    assert done["outcome"] == "delivered" and len(sent) == 1
    assert sent[0]["recipient"] == "acme@x.com" and sent[0]["action"] == "input_data_reload" and sent[0]["comment"]
    assert sent[0]["ticket_id"] == "11"                                # mapping id when there is one, else the OpenProject id
    assert states(tmp_path)[-1] == "closed"


def test_the_person_can_edit_the_comment_before_it_is_delivered(tmp_path):
    sent = []
    graph = flow.build_graph(deps(tmp_path, chat_for(UC3_SCORES), test_rules.warehouse(), sent))
    ticket = test_rules.ticket()
    flow.start(graph, ticket)
    flow.resume(graph, ticket, approved=True, comment="My own wording")
    assert sent[0]["comment"] == "My own wording"


def test_a_rejected_proposal_delivers_nothing(tmp_path):
    sent = []
    graph = flow.build_graph(deps(tmp_path, chat_for(UC3_SCORES), test_rules.warehouse(), sent))
    ticket = test_rules.ticket()
    flow.start(graph, ticket)
    done = flow.resume(graph, ticket, approved=False)
    assert done["outcome"] == "rejected" and sent == [] and states(tmp_path)[-1] == "rejected"


def test_uc1_goes_through_the_mapping_and_ends_as_a_sql_confirmation(tmp_path):
    sent = []
    chat = chat_for(UC1_SCORES, extraction=test_mapping.EXTRACTED, choice=test_mapping.CHOSEN)
    graph = flow.build_graph(deps(tmp_path, chat, test_mapping.warehouse(), sent))
    ticket = test_mapping.ticket()
    paused = flow.start(graph, ticket)
    shown = paused["__interrupt__"][0].value
    assert shown["ticket_type"] == "sql" and shown["statements"][0].startswith("UPDATE ")
    done = flow.resume(graph, ticket, approved=True)
    assert done["outcome"] == "delivered" and sent == []              # UC1 never writes an email row
    last = registry.read_records(tmp_path / "registry.jsonl")[-1]
    assert last["ticket_type"] == "sql" and last["delivered_row"]["statements"] == shown["statements"]


def test_an_undetermined_ticket_ends_without_approval_and_without_a_row(tmp_path):
    sent = []
    text = f"Contract {test_rules.FULL} is missing in the report"      # no company name: the recipient is unknown
    graph = flow.build_graph(deps(tmp_path, chat_for(UC3_SCORES), test_rules.warehouse(), sent))
    done = flow.start(graph, test_rules.ticket(text))
    assert "__interrupt__" not in done and done["outcome"] == "undetermined" and sent == []
    with open(tmp_path / "undetermined.csv", encoding="utf-8") as handle:
        assert [row["reason"] for row in csv.DictReader(handle)] == ["subsidiary_unknown"]
    assert states(tmp_path)[-1] == "undetermined"


def test_a_routing_failure_goes_to_a_person_and_nothing_is_solved(tmp_path):
    def broken(step, messages, **kw):
        return LLMResult("not json", "fake", 1, 1, 2, 0.0)
    graph = flow.build_graph(deps(tmp_path, broken, test_rules.warehouse()))
    done = flow.start(graph, test_rules.ticket())
    assert done["outcome"] == "manual" and "proposal" not in done


def test_a_ticket_without_a_record_code_falls_back_to_the_free_investigation(tmp_path, monkeypatch):
    calls = []

    def free(ticket, uc, neighbours, **kw):
        calls.append(uc)
        return Proposal(status="ok", ticket_type="email", comment="free answer", finding="f")
    monkeypatch.setattr(solver, "_solve_free", free)
    graph = flow.build_graph(deps(tmp_path, chat_for(UC3_SCORES), test_rules.warehouse()))
    paused = flow.start(graph, test_rules.ticket("The report looks wrong this month"))
    assert calls == ["UC3"] and paused["__interrupt__"][0].value["comment"] == "free answer"


def test_the_graph_has_the_decision_node_and_the_expected_nodes(tmp_path):
    graph = flow.build_graph(deps(tmp_path, chat_for(UC3_SCORES), test_rules.warehouse()))
    names = set(graph.get_graph().nodes)
    assert {"route", "rules", "mapping", "free", "undetermined", "approval",
            "deliver_email", "deliver_sql", "rejected", "manual"} <= names
