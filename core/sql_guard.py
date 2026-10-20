"""Safety check for the SQL that a model writes while it investigates a ticket.

The investigation is read-only and does not ask for approval (decision of the
project), so this check is what keeps it read-only. The rules are strict on purpose:
a query that is refused is simply written again by the model.

Allowed: ONE statement that starts with SELECT or WITH, that reads only tables of the
data catalog in the schemas bronze, silver, gold and monitoring, and that has a WHERE
or a LIMIT (so it never scans a whole table by accident).
"""

import re

ALLOWED_SCHEMAS = ("bronze", "silver", "gold", "monitoring")

FORBIDDEN_WORDS = (
    "insert", "update", "delete", "drop", "create", "alter", "truncate", "merge",
    "grant", "revoke", "copy", "call", "exec", "execute", "set", "use", "optimize",
    "vacuum", "refresh", "load", "put", "remove", "rename", "restore", "into",
    "read_files", "input_file_name",
)


class UnsafeSQL(Exception):
    """The query is refused; the message says why, so the model can fix it."""


def _without_literals(text):
    """Replace quoted text by '' so that values such as 'update' do not trip the checks."""
    return re.sub(r"'(?:[^']|'')*'", "''", text)


def check(sql, catalog):
    """Return the query ready to run, or raise UnsafeSQL."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSQL("The query is empty.")
    if "--" in cleaned or "/*" in cleaned:
        raise UnsafeSQL("Comments are not allowed in the query.")
    bare = _without_literals(cleaned)
    if ";" in bare:
        raise UnsafeSQL("Only one statement is allowed.")
    if not re.match(r"(?is)^\s*(select|with)\b", bare):
        raise UnsafeSQL("Only SELECT queries are allowed.")
    for word in FORBIDDEN_WORDS:
        if re.search(rf"(?i)\b{word}\b", bare):
            raise UnsafeSQL(f"The word '{word}' is not allowed: queries are read-only.")
    if not re.search(r"(?i)\b(where|limit)\b", bare):
        raise UnsafeSQL("Add a WHERE or a LIMIT so the query does not scan a whole table.")

    cte_names = {name.lower() for name in re.findall(r"(?i)\b(\w+)\s+as\s*\(", bare)}
    tables = re.findall(r"(?i)\b(?:from|join)\s+([\w.`]+)", bare)
    if not tables:
        raise UnsafeSQL("The query must read from a table.")
    for table in tables:
        name = table.replace("`", "")
        if name.lower() in cte_names:
            continue
        parts = name.split(".")
        if len(parts) != 3:
            raise UnsafeSQL(f"Write the full table name catalog.schema.table, not '{name}'.")
        table_catalog, schema, _ = parts
        if table_catalog.lower() != catalog.lower():
            raise UnsafeSQL(f"Only tables of the catalog '{catalog}' can be read, not '{table_catalog}'.")
        if schema.lower() not in ALLOWED_SCHEMAS:
            raise UnsafeSQL(f"Only the schemas {', '.join(ALLOWED_SCHEMAS)} can be read, not '{schema}'.")
    return cleaned
