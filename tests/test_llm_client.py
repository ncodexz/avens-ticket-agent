import json

from core import llm_client


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_extract_text_from_string_and_from_blocks():
    assert llm_client.extract_text("hi") == "hi"
    blocks = [{"type": "reasoning", "summary": "..."}, {"type": "text", "text": "pong"}]
    assert llm_client.extract_text(blocks) == "pong"


def test_chat_returns_text_and_logs_tokens(tmp_path, monkeypatch):
    payload = {
        "choices": [{"message": {"content": [{"type": "text", "text": "pong"}]}}],
        "usage": {"prompt_tokens": 108, "completion_tokens": 32, "total_tokens": 140},
    }
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: FakeResponse(payload))
    monkeypatch.setattr(llm_client, "_endpoint_and_headers", lambda p, m: ("http://x", {}))
    monkeypatch.setattr(llm_client, "runs_dir", lambda: tmp_path)
    result = llm_client.chat("routing", [{"role": "user", "content": "ping"}], run_id="r1", ticket_id=5)
    assert result.text == "pong" and result.total_tokens == 140
    log = json.loads((tmp_path / "llm_calls.jsonl").read_text().splitlines()[0])
    assert log["step"] == "routing" and log["total_tokens"] == 140 and log["run_id"] == "r1"
