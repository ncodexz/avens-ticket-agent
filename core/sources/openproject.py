"""Ticket source: the live OpenProject of Alenia (read only).

Connection: HTTPS REST with HTTP Basic auth (user 'apikey', password = token).
The token lives in a Databricks secret, never in the project.
This module only does GET requests: OPENPROJECT_WRITE_ENABLED is not used here.
"""

import json

import requests
from requests.auth import HTTPBasicAuth

from core.config import env
from core.databricks_access import get_secret
from core.sources.csv_export import parse_iso
from core.ticket import Ticket

PAGE_SIZE = 200


def _auth():
    token = get_secret(
        env("OPENPROJECT_SECRET_SCOPE", required=True),
        env("OPENPROJECT_SECRET_KEY", required=True),
    )
    return HTTPBasicAuth("apikey", token)


def to_ticket(item):
    """Convert one OpenProject work package (JSON) into a Ticket."""
    return Ticket(
        title=item["subject"],
        description=(item.get("description") or {}).get("raw", ""),
        priority=item["_links"]["priority"]["title"],
        source="openproject",
        created_at=parse_iso(item["createdAt"]),
        op_id=int(item["id"]),
        source_status=item["_links"]["status"]["title"],
    )


def read_tickets(only_open=True, limit=None):
    base = env("OPENPROJECT_BASE_URL", required=True).rstrip("/")
    project = env("OPENPROJECT_PROJECT", required=True)
    auth = _auth()
    filters = [{"status": {"operator": "o", "values": None}}] if only_open else []
    tickets, page = [], 1
    while True:
        response = requests.get(
            f"{base}/api/v3/projects/{project}/work_packages",
            params={"pageSize": PAGE_SIZE, "offset": page, "filters": json.dumps(filters)},
            auth=auth,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        tickets += [to_ticket(item) for item in data["_embedded"]["elements"]]
        if len(tickets) >= data["total"] or not data["_embedded"]["elements"]:
            break
        page += 1
    return tickets[:limit] if limit else tickets


def read_ticket(op_id):
    base = env("OPENPROJECT_BASE_URL", required=True).rstrip("/")
    response = requests.get(f"{base}/api/v3/work_packages/{op_id}", auth=_auth(), timeout=60)
    response.raise_for_status()
    return to_ticket(response.json())
