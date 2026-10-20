"""Tests for core/rules.py and core/undetermined.py: no model and no Databricks needed."""
import csv
from datetime import datetime, timezone

from core import rules, solver, undetermined
from core.ticket import Ticket

CAT = "aiops_participants_synthethic_data"
FULL = "CON_0123456789abcdef"


def ticket(text=f"Contract {FULL} of Acme SL is missing in the report", op_id=11):
    return Ticket(title="Missing contract", description=text, priority="Normal", source="csv",
                  created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), op_id=op_id)


def warehouse(file_rows=(), bronze=(), silver=(), main=(), email="acme@x.com"):
    calls = []

    def run(sql):
        calls.append(sql)
        if "monitoring.file_log" in sql:
            return list(file_rows)
        if "monitoring.main_t" in sql:
            return list(main)
        if "bronze." in sql:
            return list(bronze)
        if "silver.subsidiary_t" in sql and "CompanyName, EmailContact" in sql:
            return [{"CompanyName": "Acme SL", "EmailContact": "acme@x.com"}, {"CompanyName": "Acme", "EmailContact": "wrong@x.com"}]
        if "silver.subsidiary_t" in sql:
            return [{"EmailContact": email}]
        return list(silver)
    run.calls = calls
    return run


def no_model(*args, **kwargs):
    raise AssertionError("the rules must not call a model")


def solve(runner, uc="UC3", text=None, **kw):
    t = ticket(text, **kw) if text else ticket(**kw)
    return solver.solve(t, uc, [], chat=no_model, run_sql=runner, catalog=CAT)


def test_never_arrived_is_determined_without_a_model_call():
    result = solve(warehouse())
    assert result.status == "ok" and result.calls == 0 and result.total_tokens == 0 and result.model == "rules"
    assert result.solution == {"layer": "input_file", "error_type": "missing_row", "error_column": "",
                               "action": "input_data_reload", "recipient": "acme@x.com"}
    assert FULL in result.comment and "never arrived" in result.comment
    assert result.finding == "input_file / missing_row / - / input_data_reload"


def test_uc2_uses_the_same_rules_as_uc3():
    assert solve(warehouse(), uc="UC2").solution["action"] == "input_data_reload"


def test_empty_field_names_the_column_and_the_subsidiary_email():
    bronze = [{"filename": "a", "productfamilycodesynt": None}, {"filename": "b", "productfamilycodesynt": "LOCAL_1"}]
    result = solve(warehouse(file_rows=[{"filename": "a", "pk_values": f"{FULL}|24601"}], bronze=bronze, silver=[{"x": 1}]))
    assert result.solution["error_type"] == "missing_data_in_column" and result.solution["error_column"] == "productfamilycode"
    assert result.solution["recipient"] == "acme@x.com" and "acme@x.com" in result.comment


def test_in_file_but_not_in_bronze_goes_to_the_internal_team():
    result = solve(warehouse(file_rows=[{"filename": "a", "pk_values": f"{FULL}|24601"}]))
    assert result.solution["layer"] == "bronze" and result.solution["recipient"] == "dataintegration@team.io"
    assert "Reload the file into bronze" in result.comment


def test_a_record_present_everywhere_is_undetermined_and_says_why():
    rows = [{"filename": "a", "x": "1"}, {"filename": "b", "x": "1"}]
    result = solve(warehouse(file_rows=[{"filename": "a", "pk_values": f"{FULL}|24601"}], bronze=rows, silver=[{"x": 1}]))
    assert result.status == "undetermined" and result.solution == {}
    assert result.diagnosis.reason == "present_in_all_layers" and "present_in_all_layers" in result.comment
    assert result.finding == "undetermined: present_in_all_layers"


def test_a_failed_lookup_is_undetermined_never_read_as_never_arrived():
    def broken(sql):
        raise RuntimeError("warehouse down")
    result = solve(broken)
    assert result.status == "undetermined" and result.diagnosis.reason == "query_failed"


def test_no_record_code_falls_back_to_the_free_investigation():
    assert rules.solve(ticket("The contract counts of March do not match the report"), run_sql=warehouse(), catalog=CAT) is None
    asked = []

    def chat(step, messages, max_tokens=1500, run_id=None, ticket_id=None):
        asked.append(step)
        from core.llm_client import LLMResult
        return LLMResult('{"queries": [], "purpose": "x"}' if len(asked) == 1 else
                         '{"done": true, "finding": "f", "comment": "c"}', "fake", 10, 5, 15, 0.0)
    result = solver.solve(ticket("The contract counts of March do not match"), "UC2", [], chat=chat, run_sql=warehouse(), catalog=CAT)
    assert result.status == "ok" and asked == ["solving", "solving"]


# --- the list of undetermined tickets

def diagnosis_for(reason="present_in_all_layers"):
    from core.diagnose import Diagnosis
    return Diagnosis("undetermined", reason, FULL, evidence=["In every layer.", "No empty field."])


def test_record_writes_one_row_per_ticket_without_duplicates(tmp_path):
    path = tmp_path / "outputs" / "undetermined_tickets.csv"
    now = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
    assert undetermined.record(ticket(), diagnosis_for(), path=path, now=now) is True
    assert undetermined.record(ticket(), diagnosis_for(), path=path, now=now) is False
    assert undetermined.record(ticket(op_id=12), diagnosis_for("code_looks_incomplete"), path=path, now=now) is True
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert [r["ticket_id"] for r in rows] == ["11", "12"]
    assert rows[0]["reason"] == "present_in_all_layers" and rows[0]["reviewed"] == "no" and rows[0]["result"] == ""
    assert rows[0]["evidence"] == "In every layer. | No empty field."
    assert "full code" in rows[1]["suggested_next_step"] and rows[0]["created_at"] == "2026-10-18T12:00:00+00:00"
    assert list(rows[0]) == undetermined.COLUMNS


def test_every_reason_of_the_rules_has_a_next_step():
    from core import diagnose
    reasons = {"present_in_all_layers", "code_looks_incomplete", "several_empty_columns", "query_failed", "no_code", "inconsistent_trail"}
    assert reasons <= set(undetermined.NEXT_STEPS)


def test_a_record_that_never_arrived_asks_the_subsidiary_named_in_the_ticket():
    result = solve(warehouse())
    assert result.solution["recipient"] == "acme@x.com"   # the longest matching name wins ('Acme SL', not 'Acme')
    assert "acme@x.com" in result.comment


def test_never_arrived_without_a_known_subsidiary_is_undetermined_not_an_empty_recipient():
    result = solve(warehouse(), text="Contract CON_0123456789abcdef is missing in the report")
    assert result.status == "undetermined" and result.diagnosis.reason == "subsidiary_unknown" and result.solution == {}
