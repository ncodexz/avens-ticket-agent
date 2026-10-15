"""
Generates the resolution text for a ticket based on the REAL result of the
approved SQL query, and explicitly flags whether the case is actually ready
to close or still needs a pending action (ours or the requester's) first.
"""

from llm_client import chat_json

PROMPT_TEMPLATE = """You are writing the resolution summary for a support ticket,
based on a SQL query that was run against the system of record.

Ticket text:
{ticket_text}

SQL query run:
{sql}

Query result:
{sql_result}

Return JSON with exactly these fields:
- "resolution_text": a concise, factual explanation of what was found and
  what it means for this ticket. Ground it ONLY in the query result above —
  do not invent facts that aren't in the result.
- "ready_to_close": true ONLY if nothing further needs to happen — the fix
  has already been applied, or the query shows there is nothing to do.
  false if ANY action is still pending before this can be closed, including
  an action your own team still needs to perform (like assigning a mapping
  or loading a record), or something the requester still needs to confirm
  or provide.
"""


def generate_resolution(ticket_text: str, sql: str, sql_result: list) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        ticket_text=ticket_text, sql=sql, sql_result=sql_result
    )
    return chat_json(prompt)