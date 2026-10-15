"""
Real implementation of the ORG tool `update_status`, backed by OpenProject.
"""

from openproject_client import update_status as _update_status_on_openproject


def update_status(ticket_id: str, status: str) -> None:
    _update_status_on_openproject(int(ticket_id), status)