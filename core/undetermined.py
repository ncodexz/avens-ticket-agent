"""The list of tickets the rules could not explain.

The official solutions table has a closed vocabulary with no value for "cause not found", so
these tickets never become a row of solutions_emails_sent. They are kept in a separate CSV for
a person to review: one row per ticket, no duplicates. The file is outside Git (outputs/).
"""
import csv
from datetime import datetime, timezone
from pathlib import Path

from core.config import PROJECT_ROOT, env

COLUMNS = ["ticket_id", "code", "reason", "evidence", "reviewed", "result", "suggested_next_step", "created_at"]

NEXT_STEPS = {
    "present_in_all_layers": ("The record is in every layer with nothing empty to explain it. Compare the value "
                              "shown in the report with silver and ask the requester which field is wrong."),
    "code_looks_incomplete": "Ask the requester for the full code (16 characters after the prefix).",
    "several_empty_columns": "Several mandatory fields differ between files. Check each one with the subsidiary.",
    "query_failed": "A lookup failed. Run the ticket again; if it fails again, check the access to the tables.",
    "no_code": "The ticket has no CON_/VEH_ code. Ask the requester for it.",
    "subsidiary_unknown": "The record never arrived but the ticket names no known subsidiary. Ask the requester which one.",
    "inconsistent_trail": "The layers disagree with each other. Check file_log, bronze and silver by hand.",
}


def default_path():
    return Path(env("UNDETERMINED_FILE", str(PROJECT_ROOT / "outputs" / "undetermined_tickets.csv")))


def known_ids(path):
    path = Path(path)
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as handle:
        return {row["ticket_id"] for row in csv.DictReader(handle)}


def record(ticket, diagnosis, path=None, now=None):
    """Adds the ticket to the list. Returns True if added, False if it was already there."""
    path = Path(path) if path else default_path()
    ticket_id = str(ticket.op_id if ticket.op_id is not None else ticket.mapping_id or "")
    if not ticket_id or ticket_id in known_ids(path):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    row = {"ticket_id": ticket_id, "code": diagnosis.code, "reason": diagnosis.reason,
           "evidence": " | ".join(diagnosis.evidence), "reviewed": "no", "result": "",
           "suggested_next_step": NEXT_STEPS.get(diagnosis.reason, "A person has to review it."),
           "created_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")}
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    return True
