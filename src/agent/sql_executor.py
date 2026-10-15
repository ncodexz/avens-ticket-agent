"""
Validates that a proposed query is read-only, then executes it against the
REAL Databricks SQL Warehouse (via databricks_client.py). Replaces the
in-memory SQLite mock now that we have real access.
"""

from agent.databricks_client import execute_query as _execute_query_real

FORBIDDEN_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]


def validate_select_only(sql: str) -> tuple[bool, str]:
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return False, "Query must start with SELECT."
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            return False, f"Query contains forbidden keyword: {keyword}."
    return True, ""


def execute_query(sql: str) -> list[dict]:
    return _execute_query_real(sql)