"""
Mock version of the ORG tool `create_comment`. Alenia's real version posts
to OpenProject via its API. Ours just prints/logs, so we can see the final
output locally without a real ticketing system.
"""


def create_comment(ticket_id: str, comment: str) -> None:
    print(f"[mock create_comment] ticket={ticket_id}\n{comment}\n")