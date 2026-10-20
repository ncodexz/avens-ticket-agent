"""Tests for core/mapping.py (UC1): no model and no Databricks needed."""
import json
from datetime import datetime, timezone

from core import mapping, solver
from core.llm_client import LLMResult
from core.ticket import Ticket

CAT = "aiops_participants_synthethic_data"
JAGUAR, SKODA = "EE3FA430-60A4-5794-8B67-B624194E8733", "991589FD-12A4-5259-8527-B93740EBC831"


def ticket(description="Local make code JA in Digital Pretzel Partners SL is normalised to SKODA. JA is Jaguar. Please correct."):
    return Ticket(title="Wrong make", description=description, priority="Normal", source="csv",
                  created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), op_id=9)


def fake_chat(**answers):
    """Answers by step: extraction=..., choice=..., solving=[...]. Records what it was sent."""
    queues = {step: (list(a) if isinstance(a, list) else [a]) for step, a in answers.items()}
    sent = []

    def chat(step, messages, max_tokens=1500, run_id=None, ticket_id=None):
        sent.append((step, messages[-1]["content"]))
        text = queues[step].pop(0)
        return LLMResult(text if isinstance(text, str) else json.dumps(text), "fake", 100, 20, 120, 0.1)
    chat.sent = sent
    return chat


def warehouse(fail=(), current=None):
    """Answers each of the four fixed queries by what it reads."""
    calls = []

    def run(sql):
        calls.append(sql)
        kind = ("history" if "localvalue_history_t" in sql else "group" if "COUNT(DISTINCT" in sql
                else "candidates" if "FROM " + CAT + ".silver.holdingvalue_t hv" in sql else "current")
        if kind in fail:
            raise RuntimeError(f"{kind} broke")
        return {
            "current": current if current is not None else [{"CLASSID": "3", "LOCALCODE": "JA", "LOCALVALUE": "JAGUAR", "STATUS": "A",
                         "HOLDINGID": SKODA, "holding_name": "SKODA", "holding_description": "SKODA"}],
            "history": [],
            "candidates": [{"CLASSID": "3", "NAME": "JAGUAR", "DESCRIPTION": "JAGUAR", "HOLDINGID": JAGUAR},
                           {"CLASSID": "3", "NAME": "SKODA", "DESCRIPTION": "SKODA", "HOLDINGID": SKODA}],
            "group": [{"matched_value": "JA", "holding_name": "JAGUAR", "HOLDINGID": JAGUAR, "subsidiaries": 27}],
        }[kind]
    run.calls = calls
    return run


EXTRACTED = {"company": "Digital Pretzel Partners SL", "values": [{"text": "JA", "meaning": "Jaguar"}]}
CHOSEN = {"decisions": [{"value": "JA", "action": "remap", "target_holdingid": JAGUAR, "target_name": "JAGUAR",
                         "reason": "27 subsidiaries map it to JAGUAR"}],
          "comment": "JA is mapped to SKODA; remap it to JAGUAR.", "ready_to_close": False}


def run_solve(chat, run_sql, uc="UC1", **kw):
    return solver.solve(ticket(**kw), uc, [], chat=chat, run_sql=run_sql, catalog=CAT)


def test_four_fixed_queries_run_through_the_guard_and_the_model_is_called_twice():
    chat, sql = fake_chat(extraction=EXTRACTED, choice=CHOSEN), warehouse()
    result = run_solve(chat, sql)
    assert result.status == "ok" and result.calls == 2 and result.total_tokens == 240
    assert len(sql.calls) == 4 and [q.status for q in result.queries] == ["ok"] * 4
    assert [step for step, _ in chat.sent] == ["extraction", "choice"]
    assert result.decisions[0]["action"] == "remap" and result.decisions[0]["target_holdingid"] == JAGUAR
    assert result.finding == "JA: remap -> JAGUAR" and result.comment.startswith("JA is mapped")
    assert "27" in chat.sent[1][1] and "(should be: Jaguar)" in chat.sent[1][1]


def test_the_queries_compare_in_upper_case_and_count_distinct_subsidiaries():
    sql = warehouse()
    run_solve(fake_chat(extraction=EXTRACTED, choice=CHOSEN), sql)
    current, history, candidates, group = sql.calls
    assert "UPPER(lv.LOCALCODE) IN ('JA')" in current and "UPPER(lv.LOCALVALUE) IN ('JA')" in current
    assert "ORDER BY lh.EXECUTIONDATE DESC" in history
    assert "hv.CLASSID IN (3)" in candidates and "LIKE '%JAGUAR%'" in candidates
    assert "COUNT(DISTINCT lv.SUBSIDIARYCODE)" in group and "<>" in group and "GROUP BY 1, 2, 3" in group


def test_a_quote_in_a_value_is_doubled_not_injected():
    sql = warehouse()
    extracted = {"company": "Digital Pretzel Partners SL", "values": [{"text": "O'NEIL", "meaning": ""}]}
    run_solve(fake_chat(extraction=extracted, choice=CHOSEN), sql, description="O'NEIL in Digital Pretzel Partners SL is wrong")
    assert "'O''NEIL'" in sql.calls[0]


def test_a_target_that_is_not_in_the_evidence_is_not_accepted():
    invented = json.loads(json.dumps(CHOSEN))
    invented["decisions"][0].update(target_holdingid="00000000-0000-0000-0000-000000000000", target_name="NOPE")
    result = run_solve(fake_chat(extraction=EXTRACTED, choice=invented), warehouse())
    assert result.decisions[0]["action"] == "unclear" and "not found in the evidence" in result.decisions[0]["reason"]


def test_the_name_resolves_the_id_when_only_the_id_is_wrong_and_the_name_is_unique():
    wrong_id = json.loads(json.dumps(CHOSEN))
    wrong_id["decisions"][0]["target_holdingid"] = "garbled"
    result = run_solve(fake_chat(extraction=EXTRACTED, choice=wrong_id), warehouse())
    assert result.decisions[0]["target_holdingid"] == JAGUAR


def test_create_holding_and_keep_carry_no_target_and_keep_can_close():
    known = {JAGUAR: "JAGUAR"}
    done = mapping.check_decisions([{"value": "A", "action": "create_holding", "target_holdingid": JAGUAR, "reason": "x"},
                                    {"value": "B", "action": "keep", "reason": "ok"},
                                    {"value": "C", "action": "teleport"}], known)
    assert [d["action"] for d in done] == ["create_holding", "keep", "unclear"]
    assert done[0]["target_holdingid"] == "" and done[1]["target_holdingid"] == ""


def test_a_failed_query_is_shown_to_the_model_and_kept_in_the_record():
    chat = fake_chat(extraction=EXTRACTED, choice=CHOSEN)
    result = run_solve(chat, warehouse(fail=("history",)))
    assert [q.status for q in result.queries] == ["ok", "failed", "ok", "ok"]
    assert "FAILED: history broke" in chat.sent[1][1]


def test_no_company_in_the_ticket_falls_back_to_the_free_investigation_and_counts_the_cost():
    plan = {"queries": [f"SELECT * FROM {CAT}.silver.localvalue_t WHERE LOCALCODE = 'JA'"], "purpose": "look"}
    done = {"done": True, "ticket_type": "email", "finding": "f", "comment": "c", "ready_to_close": False}
    chat = fake_chat(extraction={"company": "", "values": [{"text": "JA"}]}, solving=[plan, done])
    result = run_solve(chat, warehouse())
    assert [step for step, _ in chat.sent] == ["extraction", "solving", "solving"]
    assert result.status == "ok" and result.calls == 3 and result.total_tokens == 360


def test_a_company_that_the_ticket_does_not_contain_is_not_trusted():
    chat = fake_chat(extraction={"company": "Invented Company SL", "values": [{"text": "JA"}]},
                     solving=[{"queries": []}, {"done": True, "finding": "f", "comment": "c"}])
    result = run_solve(chat, warehouse())
    assert [step for step, _ in chat.sent][0] == "extraction" and "solving" in [s for s, _ in chat.sent]
    assert result.decisions == []


def test_other_use_cases_do_not_use_the_mapping_flow():
    chat = fake_chat(solving=[{"queries": []}, {"done": True, "finding": "f", "comment": "c"}])
    run_solve(chat, warehouse(), uc="UC2")
    assert [step for step, _ in chat.sent] == ["solving", "solving"]


def test_words_and_values_helpers():
    values = mapping.clean_values([{"text": " ID.   BUZZ ", "meaning": "VW ID.Buzz"}, "id. buzz", {"text": ""}, 5])
    assert values == [{"text": "ID. BUZZ", "meaning": "VW ID.Buzz"}]
    assert mapping._words(values) == ["BUZZ", "ID"] or mapping._words(values) == ["BUZZ"]
    assert mapping._compact("DS 7 Crossback") == "DS7CROSSBACK"


def test_code_and_name_joined_in_the_ticket_are_searched_apart():
    assert mapping.search_terms("POO (POOL CONTRACT)") == ["POO (POOL CONTRACT)", "POO", "POOL CONTRACT"]
    assert mapping.search_terms("9, Autonomo") == ["9, Autonomo", "9", "Autonomo"]
    assert mapping.search_terms("200074 PORSCHE OTHER") == ["200074 PORSCHE OTHER", "200074", "PORSCHE OTHER"]
    assert mapping.search_terms("SA FS/NV SO") == ["SA FS/NV SO"]
    sql = warehouse()
    extracted = {"company": "Digital Pretzel Partners SL", "values": [{"text": "JA (JAGUAR)", "meaning": ""}]}
    run_solve(fake_chat(extraction=extracted, choice=CHOSEN), sql)
    assert "IN ('JA (JAGUAR)', 'JA', 'JAGUAR')" in sql.calls[0]


def test_a_remap_to_the_holding_the_value_already_has_becomes_unclear():
    known = {JAGUAR: "JAGUAR", SKODA: "SKODA"}
    raw = [{"value": "JA", "action": "remap", "target_holdingid": SKODA, "target_name": "SKODA", "reason": "ticket says SKODA"}]
    current = mapping.current_map([{"LOCALCODE": "JA", "LOCALVALUE": "JAGUAR", "HHOLDINGID": "", "HOLDINGID": SKODA}])
    decision = mapping.check_decisions(raw, known, current)[0]
    assert decision["action"] == "unclear" and decision["target_holdingid"] == ""
    assert "already points" in decision["reason"]
    raw[0]["target_holdingid"], raw[0]["target_name"] = JAGUAR, "JAGUAR"
    assert mapping.check_decisions(raw, known, current)[0]["action"] == "remap"


def test_a_short_term_does_not_match_inside_another_value():
    current = mapping.current_map([{"LOCALCODE": "E", "LOCALVALUE": "E", "HOLDINGID": JAGUAR}])
    assert mapping._current_ids("EV30", current) == set() and mapping._current_ids("E", current) == {JAGUAR}


# --- the change a person confirms (UC1 is delivered as a confirmation, not as an email row)

def test_a_remap_becomes_an_update_for_a_person_to_confirm():
    result = run_solve(fake_chat(extraction=EXTRACTED, choice=CHOSEN), warehouse())
    assert result.ticket_type == "sql"
    sub = "(SELECT SubsiDiaryCode FROM " + CAT + ".silver.subsidiary_t WHERE CompanyName = 'Digital Pretzel Partners SL' LIMIT 1)"
    assert result.statements == [f"UPDATE {CAT}.silver.localvalue_t SET HOLDINGID = '{JAGUAR}' WHERE SUBSIDIARYCODE = {sub} "
                                 "AND CLASSID = 3 AND LOCALCODE = 'JA'"]
    assert result.decisions[0]["sql"] == result.statements


def test_the_statements_are_text_only_the_guard_refuses_to_run_them():
    import pytest
    from core import sql_guard
    result = run_solve(fake_chat(extraction=EXTRACTED, choice=CHOSEN), warehouse())
    with pytest.raises(sql_guard.UnsafeSQL):
        sql_guard.check(result.statements[0], CAT)


def test_a_value_with_no_row_is_inserted_with_the_class_of_the_target_holding():
    chosen = {"decisions": [{"value": "9, Autonomo", "action": "map", "target_holdingid": JAGUAR,
                             "target_name": "JAGUAR", "reason": "x"}], "comment": "c", "ready_to_close": False}
    extracted = {"company": "Digital Pretzel Partners SL", "values": [{"text": "9, Autonomo", "meaning": ""}]}
    result = run_solve(fake_chat(extraction=extracted, choice=chosen), warehouse(current=[]))
    assert len(result.statements) == 1 and result.statements[0].startswith(f"INSERT INTO {CAT}.silver.localvalue_t")
    assert "SELECT 3, s.SubsiDiaryCode, '9', 'Autonomo', 'A', '" + JAGUAR + "'" in result.statements[0]
    assert "s.CompanyName = 'Digital Pretzel Partners SL'" in result.statements[0]


def test_create_holding_keep_and_unclear_write_no_statement():
    chosen = {"decisions": [{"value": "JA", "action": "create_holding", "reason": "x"},
                            {"value": "OTHER", "action": "keep", "reason": "x"},
                            {"value": "ZZ", "action": "unclear", "reason": "x"}], "comment": "c", "ready_to_close": False}
    result = run_solve(fake_chat(extraction=EXTRACTED, choice=chosen), warehouse())
    assert result.statements == []
    assert "Create the holding value 'JA' in class 3" in result.decisions[0]["request"]
    assert result.decisions[1]["sql"] == [] and result.decisions[2]["request"] == ""


def test_no_statement_is_written_when_the_current_mapping_could_not_be_read():
    result = run_solve(fake_chat(extraction=EXTRACTED, choice=CHOSEN), warehouse(fail=("current",)))
    assert result.statements == [] and "could not be read" in result.decisions[0]["request"]


def test_a_quote_in_the_local_code_is_doubled_in_the_statement():
    current = [{"CLASSID": "3", "LOCALCODE": "O'NEIL", "LOCALVALUE": "JA", "STATUS": "A", "HOLDINGID": SKODA,
                "holding_name": "SKODA", "holding_description": ""}]
    result = run_solve(fake_chat(extraction=EXTRACTED, choice=CHOSEN), warehouse(current=current))
    assert "LOCALCODE = 'O''NEIL'" in result.statements[0]
