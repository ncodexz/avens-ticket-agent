import pytest

from core import router
from core.llm_client import LLMResult
from core.router import RoutingError, decide, parse_scores
from core.sources import csv_export
from tests.conftest import needs_export


def fake_chat(answer):
    def chat(step, messages, run_id=None, ticket_id=None):
        assert step == "routing"
        fake_chat.sent = messages[0]["content"]
        return LLMResult(answer, "fake-model", 100, 20, 120, 0.1)
    return chat


def test_parse_scores_accepts_text_around_json_and_normalises():
    scores = parse_scores('Here you go: {"UC1": 2, "UC2": 1, "UC3": 1} done')
    assert scores == {"UC1": 0.5, "UC2": 0.25, "UC3": 0.25}


@pytest.mark.parametrize("bad", ["no json", '{"UC1": 1}', '{"UC1": "a", "UC2": 0, "UC3": 0}', '{"UC1": 0, "UC2": 0, "UC3": 0}'])
def test_parse_scores_rejects_unusable_answers(bad):
    with pytest.raises(RoutingError):
        parse_scores(bad)


def test_decide_clear_close_and_low_confidence():
    assert decide({"UC1": 0.9, "UC2": 0.05, "UC3": 0.05}) == ("UC1", False, "clear")
    assert decide({"UC1": 0.55, "UC2": 0.40, "UC3": 0.05})[1] is True   # too close
    assert decide({"UC1": 0.45, "UC2": 0.20, "UC3": 0.35})[1] is True   # low confidence


@needs_export
def test_route_a_real_ticket_sends_only_title_and_description():
    ticket = next(t for t in csv_export.read_tickets() if t.op_id == 32364)
    result = router.route(ticket, chat=fake_chat('{"UC1": 0.93, "UC2": 0.02, "UC3": 0.05}'))
    assert result.top_uc == "UC1" and not result.is_ambiguous and result.total_tokens == 120
    assert ticket.title in fake_chat.sent and "TOYOTA" in fake_chat.sent
    assert "New" not in fake_chat.sent.split("Ticket title:")[1]   # status is not sent
