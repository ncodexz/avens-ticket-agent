"""
Mock version of the ORG tool `update_status`. Alenia's real version updates
the OpenProject work package status. Ours just prints/logs.
"""


def update_status(ticket_id: str, status: str) -> None:
    print(f"[mock update_status] ticket={ticket_id} -> {status}")