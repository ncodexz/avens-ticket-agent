from dataclasses import replace

from core import ticket_ids
from core.sources import csv_export
from tests.conftest import needs_export


@needs_export
def test_friday_261_match_exactly_one_openproject_ticket():
    tickets = csv_export.read_tickets()
    friday = ticket_ids.load_mapping_csv(name="friday")
    matched, report = ticket_ids.attach_mapping_ids(tickets, friday)
    assert report.matched == 261 and report.ambiguous == 0
    assert len({t.mapping_id for t in matched if t.mapping_id}) == 261


@needs_export
def test_thursday_two_tickets_share_the_same_text_and_get_no_id():
    tickets = csv_export.read_tickets()
    thursday = ticket_ids.load_mapping_csv(name="thursday")
    result, report = ticket_ids.attach_mapping_ids(tickets, thursday)
    assert report.matched == 1489 and report.ambiguous == 2 and report.missing == 261
    used = [t.mapping_id for t in result if t.mapping_id]
    assert len(used) == len(set(used))          # no mapping id is assigned twice


@needs_export
def test_match_ignores_spacing_and_case():
    ticket = csv_export.read_tickets()[0]
    row = {"ID": "999", "title": ticket.title.upper(), "description": "  " + ticket.description.replace(" ", "  ") + " "}
    result, report = ticket_ids.attach_mapping_ids([ticket], [row])
    assert result[0].mapping_id == "999" and report.matched == 1


def test_ambiguous_or_missing_never_guesses():
    from datetime import datetime, timezone
    from core.ticket import Ticket

    t = Ticket("a", "b", "Low", "csv", datetime(2026, 1, 1, tzinfo=timezone.utc), op_id=1)
    two = [{"ID": "1", "title": "a", "description": "b"}, {"ID": "2", "title": "a", "description": "b"}]
    result, report = ticket_ids.attach_mapping_ids([t], two)
    assert result[0].mapping_id is None and report.ambiguous == 1
    result, report = ticket_ids.attach_mapping_ids([t], [])
    assert result[0].mapping_id is None and report.missing == 1


def test_several_mapping_tables_are_read_and_joined(monkeypatch):
    monkeypatch.setenv("COMMON_CATALOG", "cat")
    monkeypatch.setenv("MAPPING_TABLE", "ticket_id_mapping_thursday, ticket_id_mapping_friday")
    asked = []

    def fake(sql):
        asked.append(sql)
        return [{"ID": "1" if "thursday" in sql else "2", "title": "t", "description": "d"}]
    rows = ticket_ids.load_mapping_table(run_sql=fake)
    assert [r["ID"] for r in rows] == ["1", "2"]
    assert "cat.solutions.ticket_id_mapping_thursday" in asked[0] and "cat.solutions.ticket_id_mapping_friday" in asked[1]


def test_one_table_still_works(monkeypatch):
    monkeypatch.setenv("COMMON_CATALOG", "cat")
    monkeypatch.setenv("MAPPING_TABLE", "ticket_id_mapping_friday")
    assert len(ticket_ids.load_mapping_table(run_sql=lambda sql: [{"ID": "2", "title": "t", "description": "d"}])) == 1


@needs_export
def test_thursday_and_friday_together_match_every_open_ticket():
    open_tickets = [t for t in csv_export.read_tickets() if t.source_status == "New"]
    _, report = ticket_ids.attach_mapping_ids(open_tickets, ticket_ids.load_mapping_csvs())
    assert (report.matched, report.ambiguous, report.missing) == (len(open_tickets), 0, 0)
