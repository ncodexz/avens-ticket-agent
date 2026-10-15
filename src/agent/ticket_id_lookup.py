"""
Resolves the internal ticket_id needed for delivery (send_fake_email_solution.py)
by matching a ticket's title and description against
solutions.ticket_id_mapping_thursday, exactly as described in Guzman's email.
"""

from agent.databricks_client import execute_query

CATALOG = "aiops_participants_synthethic_data"


def get_ticket_id(title: str, description: str) -> int | None:
    safe_title = title.strip().replace("'", "''")

    query = f"""
        SELECT ID FROM {CATALOG}.solutions.ticket_id_mapping_thursday
        WHERE TRIM(title) = '{safe_title}'
    """
    result = execute_query(query)
    if not result:
        return None
    if len(result) > 1:
        print(f"[WARN] {len(result)} tickets matched this title — using the first one")
    return result[0]["ID"]