"""Match the two identifiers of a ticket.

OpenProject numbers (32364...) and Alenia mapping numbers (6041134...) are
different. The mapping table only has ID, title and description, so we match by
normalised title + description. A ticket gets a mapping_id only when exactly one
mapping row matches AND no other ticket has the same text; ambiguous or missing
matches are reported, never guessed.
"""

import csv
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

from core.config import export_dir


def normalize(text):
    return " ".join((text or "").split()).lower()


def key(title, description):
    return (normalize(title), normalize(description))


def load_mapping_csv(path=None, name="friday"):
    """Offline mapping table from the export. name is 'friday' or 'thursday'."""
    if path is None:
        path = (
            Path(export_dir()) / "databricks" / "aiops_participants_synthethic_data"
            / "solutions" / f"ticket_id_mapping_{name}.csv"
        )
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_mapping_csvs(names=("thursday", "friday")):
    """Offline: the rows of several mapping tables together."""
    rows = []
    for name in names:
        rows.extend(load_mapping_csv(name=name))
    return rows


def load_mapping_table(run_sql=None):
    """Live mapping tables from Databricks. MAPPING_TABLE holds one table name or several
    separated by commas: each day Alenia sends its own table (Thursday 190 of the open
    tickets, Friday the other 261), so one table alone leaves tickets without a mapping_id."""
    from core.config import env
    if run_sql is None:
        from core.databricks_access import run_query as run_sql

    names = [name.strip() for name in env("MAPPING_TABLE", required=True).split(",") if name.strip()]
    rows = []
    for name in names:
        table = f"{env('COMMON_CATALOG', required=True)}.solutions.{name}"
        rows.extend(run_sql(f"SELECT ID, title, description FROM {table}"))
    return rows


@dataclass
class MatchReport:
    matched: int = 0
    ambiguous: int = 0
    missing: int = 0


def attach_mapping_ids(tickets, mapping_rows):
    index = defaultdict(set)
    for row in mapping_rows:
        index[key(row["title"], row["description"])].add(str(row["ID"]))
    tickets_per_key = defaultdict(int)
    for ticket in tickets:
        tickets_per_key[key(ticket.title, ticket.description)] += 1
    result, report = [], MatchReport()
    for ticket in tickets:
        ticket_key = key(ticket.title, ticket.description)
        ids = index.get(ticket_key, set())
        # Two tickets with identical text would receive the same mapping id: ambiguous.
        if tickets_per_key[ticket_key] > 1 and ids:
            ids = ids | {"<shared text>"}
        if len(ids) == 1:
            report.matched += 1
            result.append(replace(ticket, mapping_id=next(iter(ids))))
        else:
            if len(ids) > 1:
                report.ambiguous += 1
            else:
                report.missing += 1
            result.append(ticket)
    return result, report
