from core.ordering import order_tickets
from core.sources import csv_export
from core.ticket import PRIORITY_RANK
from tests.conftest import needs_export


@needs_export
def test_real_new_tickets_come_out_in_priority_then_age_order():
    new = [t for t in csv_export.read_tickets() if t.source_status == "New"]
    ordered = order_tickets(new)
    keys = [(PRIORITY_RANK[t.priority], t.created_at) for t in ordered]
    assert keys == sorted(keys)
    assert len(ordered) == 451
    assert ordered[0].priority == "High"
    oldest_high = min((t for t in new if t.priority == "High"), key=lambda t: t.created_at)
    assert ordered[0].op_id == oldest_high.op_id
    assert ordered[-1].priority == "Low"
