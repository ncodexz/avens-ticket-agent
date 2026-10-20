"""Block 1 end to end: read tickets, match ids, order by priority, route, register.

Usage (from the project root):
    python -m core.block1 --source csv --status New --limit 10
    python -m core.block1 --source csv --ids 32364 32365
    python -m core.block1 --source openproject --limit 5
Add --no-route to stop before calling any model.
"""

import argparse
import uuid
from collections import Counter

from core import registry, ticket_ids
from core.config import mode
from core.ordering import order_tickets
from core.router import RoutingError, route


def load_tickets(source, status="New", ids=None):
    if source == "csv":
        from core.sources import csv_export

        tickets = csv_export.read_tickets()
        mapping_rows = ticket_ids.load_mapping_csv(name="thursday") + ticket_ids.load_mapping_csv(name="friday")
    elif source == "openproject":
        from core.sources import openproject

        tickets = openproject.read_tickets(only_open=(status == "New"))
        mapping_rows = ticket_ids.load_mapping_table()
    else:
        raise ValueError(f"Unknown source: {source!r}")
    if ids:
        tickets = [t for t in tickets if t.op_id in set(ids)]
    elif status != "all":
        tickets = [t for t in tickets if t.source_status == status]
    return ticket_ids.attach_mapping_ids(tickets, mapping_rows)


def run(source="csv", status="New", ids=None, limit=None, do_route=True):
    run_id = uuid.uuid4().hex[:8]
    tickets, report = load_tickets(source, status, ids)
    ordered = order_tickets(tickets)
    if limit:
        ordered = ordered[:limit]
    print(f"run {run_id} | mode {mode()} | source {source} | {len(tickets)} tickets read, {len(ordered)} to process")
    print(f"id match: {report.matched} matched, {report.ambiguous} ambiguous, {report.missing} missing")
    for ticket in ordered:
        line = f"[{ticket.priority:<9}] op {ticket.op_id} map {ticket.mapping_id} | {ticket.title[:70]}"
        uc, extra = None, {}
        if do_route:
            try:
                result = route(ticket, run_id=run_id)
                uc = result.top_uc
                scores = " ".join(f"{k}={v:.2f}" for k, v in result.scores.items())
                line += f"\n    -> {uc} ({scores}) ambiguous={result.is_ambiguous} [{result.reason}] tokens={result.total_tokens}"
                extra = {"scores": result.scores, "ambiguous": result.is_ambiguous,
                         "reason": result.reason, "model": result.model}
            except RoutingError as error:
                line += f"\n    -> routing failed: {error}"
                extra = {"routing_error": str(error)}
        print(line)
        registry.append_record(run_id, ticket, uc=uc, extra=extra)
    return ordered


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["csv", "openproject"], default="csv")
    parser.add_argument("--status", choices=["New", "Closed", "all"], default="New")
    parser.add_argument("--ids", type=int, nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-route", action="store_true")
    args = parser.parse_args()
    run(args.source, args.status, args.ids, args.limit, do_route=not args.no_route)


if __name__ == "__main__":
    main()
