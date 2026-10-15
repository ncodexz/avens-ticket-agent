"""
Real connection to the Databricks SQL Warehouse, replacing the in-memory
SQLite mock used during development. Uses interactive OAuth (no token
needed) since personal access tokens are disabled for this organization.
"""

from databricks import sql

SERVER_HOSTNAME = "dbc-9906de71-4afe.cloud.databricks.com"
HTTP_PATH = "/sql/1.0/warehouses/6d6323eae613703d"


def get_connection():
    return sql.connect(
        server_hostname=SERVER_HOSTNAME,
        http_path=HTTP_PATH,
        auth_type="databricks-oauth",
    )


def execute_query(sql_query: str) -> list[dict]:
    """
    Runs a SELECT query against the real Databricks warehouse and returns
    the result as a list of dicts (one dict per row), same shape the mock
    sql_executor.py returned, so the rest of the pipeline doesn't need to
    change.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]