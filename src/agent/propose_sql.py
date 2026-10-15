"""
Given a ticket and the table schema, ask the LLM to propose a single
read-only SQL query plus a plain-language purpose explaining why that query
is needed. This step NEVER executes anything — it only proposes. Execution
only happens after human approval.
"""

from llm_client import chat_json
from tests.mock_database import SCHEMA, TABLES


PROMPT_TEMPLATE = """You are proposing a SQL query to investigate a support ticket.
You may ONLY propose a single SELECT query. Never propose INSERT, UPDATE,
DELETE, DROP, or any statement that changes data.

Available tables, columns, and one real example row per table (so you can
see the actual format of each value):
{schema}

Rules you must follow:
- Never invent a value that is not stated in the ticket text. If the ticket
  does not mention a year, do not add a year to your filter.
- Identifiers in the ticket (like "VH-1123" or "ES-4471") must be matched
  against the column whose example value actually looks like that format —
  check the example row for each table before deciding which column to
  filter on. Do not assume which column an identifier belongs to.
- A subsidiary or filial named in the ticket (like "Portugal") is a NAME,
  not a code. If a table's example row shows subsidiary as a code (not a
  name), you must resolve the name via CF_SUBSIDIARIES_T (which maps
  subsidiary_name to subsidiary_id) — never compare a name directly to a
  code column.

Ticket text:
{ticket_text}

Return JSON with exactly these fields:
- "table": the single table name you need to query (must be one of the
  available tables above)
- "sql": the SELECT query you propose, as a plain string
- "purpose": one or two sentences, in plain language, explaining to a human
  reviewer WHY this query is needed and what it will confirm or rule out
"""


def propose_sql(ticket_text: str) -> dict:
    schema_lines = []
    for table, columns in SCHEMA.items():
        example_row = TABLES[table][0] if TABLES[table] else {}
        schema_lines.append(
            f"- {table}: columns = {', '.join(columns)} | example row = {example_row}"
        )
    schema_text = "\n".join(schema_lines)
    prompt = PROMPT_TEMPLATE.format(schema=schema_text, ticket_text=ticket_text)
    result = chat_json(prompt)
    return result