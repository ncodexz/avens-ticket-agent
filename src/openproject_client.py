"""
OpenProject client — implements read_ticket, create_comment, update_status,
reassign, and priority-ordered listing for the agent's tool contract.
"""

import requests
from requests.auth import HTTPBasicAuth

OPENPROJECT_BASE_URL = "https://projects.alenia.io"
PROJECT_IDENTIFIER = "hackathon-ticket-masters"
SECRET_SCOPE = "ticket-masters-dev-scope"
SECRET_KEY = "op-ticket-masters-dev-secret"


def _auth():
    token = dbutils.secrets.get(scope=SECRET_SCOPE, key=SECRET_KEY)
    return HTTPBasicAuth("apikey", token)


def read_ticket(ticket_id: int) -> dict:
    """Fetch a work package from OpenProject and return its key fields."""
    url = f"{OPENPROJECT_BASE_URL}/api/v3/work_packages/{ticket_id}"
    resp = requests.get(url, auth=_auth())
    resp.raise_for_status()
    wp = resp.json()
    return {
        "id": wp["id"],
        "subject": wp.get("subject"),
        "description": (wp.get("description") or {}).get("raw", ""),
        "priority": wp.get("_links", {}).get("priority", {}).get("title"),
        "status": wp.get("_links", {}).get("status", {}).get("title"),
        "type": wp.get("_links", {}).get("type", {}).get("title"),
        "lockVersion": wp["lockVersion"],
        "raw": wp,
    }


def create_comment(ticket_id: int, text: str) -> dict:
    """Add a comment (activity) to a ticket."""
    url = f"{OPENPROJECT_BASE_URL}/api/v3/work_packages/{ticket_id}/activities"
    resp = requests.post(url, auth=_auth(), json={"comment": {"raw": text}})
    resp.raise_for_status()
    return resp.json()


def _status_href(status_name: str) -> str:
    resp = requests.get(f"{OPENPROJECT_BASE_URL}/api/v3/statuses", auth=_auth())
    resp.raise_for_status()
    for s in resp.json()["_embedded"]["elements"]:
        if s["name"].lower() == status_name.lower():
            return s["_links"]["self"]["href"]
    names = [s["name"] for s in resp.json()["_embedded"]["elements"]]
    raise ValueError(f"Status '{status_name}' not found. Available: {names}")


def update_status(ticket_id: int, status_name: str) -> dict:
    """Update a ticket's status, respecting OpenProject's lockVersion concurrency check."""
    ticket = read_ticket(ticket_id)
    body = {
        "lockVersion": ticket["lockVersion"],
        "_links": {"status": {"href": _status_href(status_name)}},
    }
    url = f"{OPENPROJECT_BASE_URL}/api/v3/work_packages/{ticket_id}"
    resp = requests.patch(url, auth=_auth(), json=body)
    resp.raise_for_status()
    return resp.json()


def reassign(ticket_id: int, user_search: str) -> dict:
    """Reassign a ticket to a user matched by name (e.g. 'Data Integration User')."""
    params = {"filters": f'[{{"name":{{"operator":"~","values":["{user_search}"]}}}}]'}
    resp = requests.get(f"{OPENPROJECT_BASE_URL}/api/v3/users", auth=_auth(), params=params)
    resp.raise_for_status()
    elements = resp.json()["_embedded"]["elements"]
    if not elements:
        raise ValueError(f"User '{user_search}' not found")
    user_href = elements[0]["_links"]["self"]["href"]

    ticket = read_ticket(ticket_id)
    body = {"lockVersion": ticket["lockVersion"], "_links": {"assignee": {"href": user_href}}}
    url = f"{OPENPROJECT_BASE_URL}/api/v3/work_packages/{ticket_id}"
    resp = requests.patch(url, auth=_auth(), json=body)
    resp.raise_for_status()
    return resp.json()


def list_open_tickets_by_priority() -> list:
    """Return open tickets for the hackathon project, sorted by priority descending."""
    url = f"{OPENPROJECT_BASE_URL}/api/v3/projects/{PROJECT_IDENTIFIER}/work_packages"
    params = {
        "sortBy": '[["priority","desc"]]',
        "filters": '[{"status":{"operator":"o","values":[]}}]',
    }
    resp = requests.get(url, auth=_auth(), params=params)
    resp.raise_for_status()
    return resp.json()["_embedded"]["elements"]