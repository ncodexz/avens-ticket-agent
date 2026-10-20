from datetime import datetime, timezone

from core import registry
from core.ticket import Ticket


def test_append_only_and_last_line_is_current_state(tmp_path):
    path = tmp_path / "registry.jsonl"
    t = Ticket("a", "b", "Low", "csv", datetime(2026, 1, 1, tzinfo=timezone.utc), op_id=7, mapping_id="70")
    registry.append_record("r1", t, uc="UC1", path=path)
    registry.append_record("r2", t, uc="UC1", state="closed", path=path)
    assert len(registry.read_records(path)) == 2          # nothing was overwritten
    assert registry.current_state(path)[7]["state"] == "closed"
    assert registry.read_records(path)[0]["mode"] in ("local", "databricks")


def test_missing_registry_reads_as_empty(tmp_path):
    assert registry.read_records(tmp_path / "nope.jsonl") == []
