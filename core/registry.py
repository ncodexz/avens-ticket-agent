"""Small append-only registry: one line per event of a ticket.

Nothing is ever edited or deleted. The current state of a ticket is its last line.
Fields: run_id, mode, ids, use case, ticket type, state (pending/closed/rejected),
proposed comment and delivered row. Later blocks fill the empty fields.
"""

import json
from datetime import datetime, timezone

from core.config import mode, runs_dir

REGISTRY_FILE = "registry.jsonl"


def append_record(run_id, ticket, uc=None, ticket_type=None, state="pending",
                  proposed_comment=None, delivered_row=None, extra=None, path=None):
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "mode": mode(),
        "op_id": ticket.op_id,
        "mapping_id": ticket.mapping_id,
        "source": ticket.source,
        "priority": ticket.priority,
        "uc": uc,
        "ticket_type": ticket_type,
        "state": state,
        "proposed_comment": proposed_comment,
        "delivered_row": delivered_row,
        "extra": extra or {},
    }
    target = path or runs_dir() / REGISTRY_FILE
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_records(path=None):
    target = path or runs_dir() / REGISTRY_FILE
    try:
        with open(target, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    except FileNotFoundError:
        return []


def current_state(path=None):
    """Last line of each ticket, keyed by op_id."""
    return {record["op_id"]: record for record in read_records(path)}
