"""
Builds a real in-memory SQLite database from the mock tables, validates that
a proposed query is read-only, and executes it. This lets us test the full
propose -> approve -> execute flow with real SQL syntax, against fake data,
before we have real Databricks access.
"""

import sqlite3
from tests.mock_database import TABLES


FORBIDDEN_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]


def validate_select_only(sql: str) -> tuple[bool, str]:
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return False, "Query must start with SELECT."
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            return False, f"Query contains forbidden keyword: {keyword}."
    return True, ""


def build_in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    for table_name, rows in TABLES.items():
        if not rows:
            continue
        columns = list(rows[0].keys())
        column_defs = ", ".join(f'"{col}" TEXT' for col in columns)
        cursor.execute(f'CREATE TABLE "{table_name}" ({column_defs})')
        placeholders = ", ".join("?" for _ in columns)
        for row in rows:
            values = [str(row[col]) if row[col] is not None else None for col in columns]
            cursor.execute(
                f'INSERT INTO "{table_name}" VALUES ({placeholders})', values
            )
    conn.commit()
    return conn


def execute_query(conn: sqlite3.Connection, sql: str) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]