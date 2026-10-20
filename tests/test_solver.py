import json
from datetime import datetime, timezone

from core import solver
from core.llm_client import LLMResult
from core.rag import Neighbour
from core.ticket import Ticket

CAT = "aiops_participants_synthethic_data"


def ticket():
    return Ticket(title="Missing Contract CON_1", description="Contract CON_1 from Acme SL is missing",
                  priority="Normal", source="csv", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), op_id=7)


def script(*answers):
    """A fake model that gives the given answers one after the other."""
    sent = []
    queue = list(answers)

    def chat(step, messages, max_tokens=1500, run_id=None, ticket_id=None):
        assert step == "solving"
        sent.append([m["content"] for m in messages])
        text = queue.pop(0)
        return LLMResult(text if isinstance(text, str) else json.dumps(text), "fake-model", 100, 20, 120, 0.1)
    chat.sent = sent
    return chat


def sql_runner(rows=None, error=None):
    calls = []

    def run(sql):
        calls.append(sql)
        if error:
            raise RuntimeError(error)
        return rows if rows is not None else []
    run.calls = calls
    return run


def solve(chat, runner, neighbours=(), uc="UC3"):  # free investigation: the rules are tested apart
    return solver.solve(ticket(), uc, list(neighbours), chat=chat, run_sql=runner, catalog=CAT, use_rules=False)


GOOD = f"SELECT * FROM {CAT}.silver.contract WHERE contractcodesynt = 'CON_1'"
BAD = f"DELETE FROM {CAT}.silver.contract WHERE contractcodesynt = 'CON_1'"
PLAN = {"queries": [GOOD], "purpose": "see if it exists"}
DONE = {"done": True, "ticket_type": "email", "finding": "never received",
        "comment": "The contract was never received.", "ready_to_close": False}


def test_normal_flow_is_two_model_calls_and_the_results_reach_the_model():
    chat = script(PLAN, DONE)
    runner = sql_runner(rows=[{"contractcodesynt": "CON_1"}])
    result = solve(chat, runner)
    assert result.status == "ok" and result.calls == 2 and result.total_tokens == 240
    assert result.comment == "The contract was never received." and result.finding == "never received"
    assert result.purpose == "see if it exists" and result.ready_to_close is False
    assert runner.calls == [GOOD] and result.queries[0].status == "ok" and result.queries[0].detail == "1 rows"
    assert "Result (1 rows)" in chat.sent[1][-1] and "CON_1" in chat.sent[1][-1]


def test_no_queries_goes_straight_to_the_answer():
    chat = script({"queries": []}, DONE)
    runner = sql_runner()
    result = solve(chat, runner, uc="UC2")
    assert result.status == "ok" and result.calls == 2 and runner.calls == []
    assert "No queries were run" in chat.sent[1][-1]


def test_extra_queries_beyond_the_use_case_limit_are_ignored():
    chat = script({"queries": [GOOD] * 5}, DONE)
    runner = sql_runner()
    solve(chat, runner, uc="UC2")
    assert len(runner.calls) == solver.QUERIES_BY_USE_CASE["UC2"]


def test_unsafe_query_is_not_run_and_is_repaired_once():
    chat = script({"queries": [BAD]}, {"queries": [GOOD]}, DONE)
    runner = sql_runner()
    result = solve(chat, runner)
    assert runner.calls == [GOOD] and result.calls == 3 and result.status == "ok"
    assert [q.status for q in result.queries] == ["refused", "ok"]
    assert "REFUSED" in chat.sent[1][-1]


def test_database_error_is_repaired_once_and_a_second_failure_is_shown_not_repaired_again():
    chat = script(PLAN, {"queries": [GOOD]}, DONE)
    result = solve(chat, sql_runner(error="column not found"))
    assert result.calls == 3 and [q.status for q in result.queries] == ["failed", "failed"]
    assert result.status == "ok"
    assert "FAILED: column not found" in chat.sent[2][-1]


def test_gives_up_when_the_plan_is_never_readable():
    result = solve(script("no json", "still no json"), sql_runner())
    assert result.status == "gave_up" and result.calls == 2


def test_one_unreadable_reply_is_tolerated():
    result = solve(script("oops", PLAN, DONE), sql_runner())
    assert result.status == "ok" and result.calls == 3


def test_answer_without_comment_is_asked_again():
    empty = dict(DONE, comment="")
    result = solve(script(PLAN, empty, DONE), sql_runner())
    assert result.status == "ok" and result.comment


def test_gives_up_when_the_comment_stays_empty():
    empty = dict(DONE, comment="")
    assert solve(script(PLAN, empty, empty), sql_runner()).status == "gave_up"


def test_sql_ticket_type_and_ready_to_close():
    done = dict(DONE, ticket_type="SQL", ready_to_close=True)
    result = solve(script(PLAN, done), sql_runner())
    assert result.ticket_type == "sql" and result.ready_to_close is True
    assert solve(script(PLAN, dict(DONE, ticket_type="whatever")), sql_runner()).ticket_type == "email"


def test_json_inside_text_is_found():
    result = solve(script("Sure! " + json.dumps(PLAN) + " ok", "Here: " + json.dumps(DONE)), sql_runner())
    assert result.status == "ok"


def test_prompt_has_ticket_use_case_precedents_schema_and_rules():
    chat = script(PLAN, DONE)
    neighbour = Neighbour(5, "UC3", 0.9, "Missing Contract CON_9", "Never received in the input file.")
    solve(chat, sql_runner(), [neighbour])
    prompt = chat.sent[0][0]
    assert "Missing Contract CON_1" in prompt and "UC3" in prompt
    assert "Missing Contract CON_9" in prompt and "Never received in the input file." in prompt
    for word in (f"{CAT}.silver.contract", "contractcodesynt", "file_log", "pk_values", "main_t", "BOTH subsidiarycode"):
        assert word in prompt


def test_precedents_drop_code_blocks_and_are_short():
    long_text = "Checked the data. ```sql\nSELECT secret FROM t\n``` Finding: never received. " + "z" * 2000
    text = solver.format_precedents([Neighbour(5, "UC3", 0.9, "Title", long_text)])
    assert "SELECT secret" not in text and "[query omitted]" in text and "Finding: never received." in text
    assert len(text) < solver.MAX_PRECEDENT_CHARS + 100
    assert solver.format_precedents([]) == "(none)"


def test_long_results_are_cut():
    rows = [{"n": i, "text": "x" * 200} for i in range(100)]
    text = solver.format_rows(rows)
    assert len(text) < solver.MAX_RESULT_CHARS + 900 and "of 100 rows" in text
    assert solver.format_rows([]) == "No rows."


def test_prompt_plans_match_the_use_case():
    uc2 = solver.build_prompt(ticket(), "UC2", [], CAT)
    assert "at most 4 queries" in uc2 and "bronze.contract_history" in uc2 and "EMPTY or null" in uc2 and "SELECT *" in uc2 and "for example productfamilycodesynt" not in uc2
    uc1 = solver.build_prompt(ticket(), "UC1", [], CAT)
    assert "ALWAYS its history" in uc1 and "bronze.localvalue_history_t" in uc1
    assert "at most 4 queries" in uc1 and "CANDIDATE holding values" in uc1 and "WRONG holding value" in uc1
    assert "ANY of the" in uc1 and "REST OF THE GROUP" in uc1 and "Do NOT conclude" in uc1
    assert "the ticket comes first" in uc1 and "exactly as the ticket writes it" in uc1
    assert "LOCALCODE OR on" in uc1


def test_format_rows_shows_columns_that_differ_between_rows():
    rows = [{"a": "x", "b": None, "c": "same", "d": None},
            {"a": "x", "b": "filled", "c": "same", "d": "null"}]
    text = solver.format_rows(rows)
    assert '"b": ["EMPTY", "filled"]' in text
    assert "1 columns are empty in every row" in text  # only d
    assert '"d"' not in text.split("\n")[-1]
    assert '"c": "same"' in text.split("\n")[-1]


def test_prompts_warn_about_text_codes_and_failed_queries():
    prompt = solver.build_prompt(ticket(), "UC1", [], CAT)
    assert "LOCALCODE = '76'" in prompt and "never CAST them to a number" in prompt
    assert "never claim the data is wrong" in solver.RESULTS_PROMPT


def test_results_prompt_asks_for_a_consistent_comment():
    assert "same holding value as the finding" in solver.RESULTS_PROMPT
