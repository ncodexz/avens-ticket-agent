from collections import Counter

from core.sources import csv_export
from tests.conftest import needs_export


@needs_export
def test_reads_all_real_tickets():
    tickets = csv_export.read_tickets()
    assert len(tickets) == 1752
    assert Counter(t.source_status for t in tickets) == {"Closed": 1301, "New": 451}
    assert {t.priority for t in tickets} == {"Low", "Normal", "High"}
    assert all(t.created_at.tzinfo is not None for t in tickets)


@needs_export
def test_known_real_ticket():
    ticket = next(t for t in csv_export.read_tickets() if t.op_id == 32364)
    assert ticket.title == "Make TOYOTA missing in LMS for Epic Umbrella Company SL"
    assert ticket.priority == "Low" and ticket.source_status == "New"
