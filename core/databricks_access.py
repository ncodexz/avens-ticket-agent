"""Access to Databricks: login, secrets and SQL.

Two ways in, chosen by ENV_MODE:
- local: OAuth through the browser (the token is cached by the SDK, so no password or token
  is stored in the project) and the SQL warehouse.
- databricks (inside a notebook or job): no login at all. Secrets come from dbutils and SQL
  runs on the cluster's Spark session, because there is no browser to log in with.
Imports are lazy so the rest of the code and the tests work without the Databricks packages.
"""

import base64

from core.config import env, mode


def _dbutils():
    from databricks.sdk.runtime import dbutils

    return dbutils


def _spark():
    from pyspark.sql import SparkSession

    return SparkSession.builder.getOrCreate()


def workspace_client():
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient(host=env("DATABRICKS_HOST", required=True), auth_type="external-browser")


def get_secret(scope, key):
    """Read a secret from a Databricks secret scope (the API returns it base64-encoded)."""
    if mode() == "databricks":
        return _dbutils().secrets.get(scope=scope, key=key)
    response = workspace_client().secrets.get_secret(scope=scope, key=key)
    return base64.b64decode(response.value).decode("utf-8")


def run_query(sql_text):
    """Run one SQL statement and return a list of dicts."""
    if mode() == "databricks":
        return [row.asDict() for row in _spark().sql(sql_text).collect()]
    from databricks import sql

    client = workspace_client()
    host = env("DATABRICKS_HOST", required=True).replace("https://", "")
    warehouse = env("DATABRICKS_WAREHOUSE_ID", required=True)
    with sql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{warehouse}",
        credentials_provider=lambda: client.config.authenticate,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql_text)
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
