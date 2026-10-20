from core import block1, registry
from tests.conftest import needs_export


@needs_export
def test_block1_end_to_end_on_real_tickets_without_model(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "runs_dir", lambda: tmp_path)
    ordered = block1.run(source="csv", status="New", limit=5, do_route=False)
    assert len(ordered) == 5 and all(t.mapping_id for t in ordered)
    assert len(registry.read_records()) == 5


@needs_export
def test_block1_can_select_real_closed_tickets_by_id(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "runs_dir", lambda: tmp_path)
    from core.sources import csv_export
    closed = [t.op_id for t in csv_export.read_tickets() if t.source_status == "Closed"][:3]
    ordered = block1.run(source="csv", ids=closed, do_route=False)
    assert {t.op_id for t in ordered} == set(closed)
    assert all(t.source_status == "Closed" for t in ordered)
