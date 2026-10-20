"""Block 3: investigate a routed ticket and propose an answer. Nothing is written anywhere.

Design taken from the previous project (propose_sql + generate_resolution), kept to
TWO model calls per ticket instead of a long loop, because the prompt is sent each time:
1. the model proposes ALL the read-only queries it needs, in one reply (1 to 3, by use case);
2. the code checks each one (core.sql_guard) and runs it on Databricks;
3. if some failed, the model gets the errors once and corrects them;
4. the model reads the real results and writes the answer.
The model also decides whether the ticket is an 'email' ticket (comment + row) or an
'sql' ticket (the query and its result are the answer); this is not taken from the use
case because we do not know whether the use case decides it.
The closest solved tickets (block 2, same use case) are given as precedents.
The proposal still needs human approval (block 4).
"""

import json
import re
from dataclasses import dataclass, field

from core import llm_client, sql_guard
from core.config import env
from core.ticket import Ticket

QUERIES_BY_USE_CASE = {"UC1": 4, "UC2": 4, "UC3": 3}
MAX_ROWS_SHOWN = 20      # rows of each result given back to the model
MAX_RESULT_CHARS = 2500
MAX_PRECEDENT_CHARS = 600
MAX_DESCRIPTION_CHARS = 4000
MAX_TOKENS = 2500        # reasoning models spend tokens thinking before they answer

SCHEMA = """Available tables (only the useful columns are listed). Always write the full catalog.schema.table name.

- {catalog}.silver.contract (one row per contract): subsidiarycode (int), contractcode (int), contractlegacycode (text, sometimes
  the text 'NULL'), contractcodesynt (text 'CON_<hex>': THIS is the format used in tickets), vehiclecode (int), vehiclecodesynt
  (text 'VEH_<hex>'), subsidiarycodesynt (int), productfamilycodesynt, contractstatuscode, contractstatusdescription, customercode,
  contractdateregistration, contractdatedelivery, contractdatetermination, lpulicenseplate, filename.
- {catalog}.bronze.contract_history: same keys as silver.contract, raw history with filename.
- {catalog}.silver.vehicle (one row per vehicle): subsidiarycode (int), vehiclecode (int), vehiclecodesynt (text 'VEH_<hex>'),
  subsidiarycodesynt (int), vehicleidentificationnumber (real VIN), vehicleidentificationnumbersynt (NOT a usable VIN: do not
  match it with a VIN from a ticket), vehregplatenumber (license plate), vehcharmodel, filename.
- {catalog}.bronze.vehicle_history: same keys as silver.vehicle, raw history.
- {catalog}.silver.subsidiary_t: SubsiDiaryCode (text, e.g. '24601' or '01201'), CompanyName (text; THIS is how a subsidiary is
  named in tickets), EmailContact.
- {catalog}.gold.fleet_report (one row per contract PER MONTH): subsidiaryCode (int), contractCode (int), vehRegPlateNumber,
  vehicleIdentificationNumber, contractLegacyCode (numeric text, NOT 'CON_...'), executionDate. A contract that exists in
  silver.contract may still be absent from gold.fleet_report: this is a real gap of the process, not a mistake in your query.
- {catalog}.silver.localvalue_t (UC1, one row per local code per subsidiary and class): CLASSID (int), SUBSIDIARYCODE (text),
  LOCALCODE, LOCALVALUE, STATUS, HOLDINGID. A value is "not mapped" when HOLDINGID is NULL or empty.
- {catalog}.silver.holdingvalue_t (UC1, the global values a local value maps to): CLASSID (int), NAME, DESCRIPTION, PARENTID,
  SHORTDESCRIPTION, HOLDINGID. Join to localvalue_t on (HOLDINGID, CLASSID).
- {catalog}.bronze.localvalue_history_t (UC1, who changed a mapping and when): CLASSID, SUBSIDIARYCODE (text), LOCALCODE, LOCALVALUE,
  IDUSER, EXECUTIONDATE, HOLDINGID.
- {catalog}.monitoring.main_t (processing log): id, message_type, entityname ('contract', 'vehicle'), layer (FILE, BRONZE, SILVER),
  status (PROCESSED or FAILED), error_message, date_process. A FAILED row names the record as '[CON_<hex>|<subsidiary>]' and the
  reason (for example 'mandatory field is null'): search it with error_message LIKE '%CON_<hex>%'. It has NO pk_values column.
- {catalog}.monitoring.file_log (one row per record received in an input file): table_name, filename, filepath, file_reference_date,
  date_received, file_record_count, pk_columns, pk_values. pk_values looks like 'VEH_3d1eca905af12459|01201' ('CODE|SUBSIDIARY').
  Use it to know whether a record arrived in the input file."""

PROPOSE_PROMPT = """You are investigating ONE IT ticket about a fleet management data pipeline (input file -> bronze -> silver -> gold).
You may only run read-only SELECT queries. Write them all now; you will get the results afterwards.

{schema}

Use case decided by the router: {uc}. Write at most {max_queries} queries, in this order:
- UC1 (local value or mapping problem): (1) the CURRENT mapping of that local value for that subsidiary (match it on LOCALCODE OR on
  LOCALVALUE: the name in the ticket can be either one, and a code such as 200146 can hold the value 'FGM'), with the name of the holding
  value it points to (LEFT JOIN holdingvalue_t), whether HOLDINGID is NULL or not. A value can be missing, not mapped (HOLDINGID empty)
  or mapped to the WRONG holding value: a ticket that says a value "shows as X" or "is classified as X" usually means the last one;
  (2) ALWAYS its history in bronze.localvalue_history_t for that subsidiary and LOCALCODE (or LOCALVALUE), newest first: silver only
  keeps the final mapping, so a wrong holding value that was later corrected is visible only in the history. If the history has
  several rows with different HOLDINGID, name both holding values (join holdingvalue_t) and say which came last.
  (3) CANDIDATE holding values: the rows of holdingvalue_t of the SAME CLASSID as that local value (take the class from localvalue_t
  with a subquery) whose NAME or DESCRIPTION contains ANY of the one or two distinctive words of the local value or of the make/model
  the ticket asks for (NAME LIKE '%MITSUBISHI%' OR NAME LIKE '%FUSO%' OR DESCRIPTION LIKE '%FUSO%'), LIMIT 20. Never require all the
  words together: the real name may contain only one of them (the holding 'FUSO' for 'MITSUBISHI FUSO'). If the local value does not
  exist yet, use the class of the holding values named in the ticket instead.
  (4) HOW THE REST OF THE GROUP maps the same value: localvalue_t rows of OTHER subsidiaries with the same LOCALVALUE (or LOCALCODE),
  joined to holdingvalue_t, as SELECT hv.NAME, COUNT(*) AS subsidiaries ... GROUP BY hv.NAME ORDER BY subsidiaries DESC LIMIT 10.
  The answer must name the holding value to map to. If the other subsidiaries agree on one holding value and this one differs, that
  value is the likely target. Do NOT conclude that the current mapping is correct when the ticket says it is wrong and the rest of
  the group maps it differently. BUT the ticket comes first: if the ticket itself says which value is correct or gives the reason
  (for example "they invoice as a business, so not private"), follow the ticket and use the group only as support. Use the group's
  majority as the target only when the ticket does not say. If no holding value fits, say that it has to be created.
- UC2 (contract or vehicle missing or wrong in the Fleet Report): (1) the record in silver.contract / silver.vehicle; (2) its history
  in bronze.contract_history / bronze.vehicle_history: SELECT * for that record ordered by filename, so that every column is returned
  (do not pick columns). Compare the rows: a field that is EMPTY or null in one row and filled in another is the likely cause, because a
  record with a mandatory field empty is left out of the report; (3) whether it reached gold.fleet_report; (4) failures of that
  record in monitoring.main_t.
- UC3 (record missing from the data): (1) the record in silver; (2) what monitoring.file_log shows for its pk_values (did it arrive
  in the input file?); (3) failures in monitoring.main_t. Conclude later with one of: never received in the input file; in the
  input file but missing from silver and bronze; in bronze but missing from silver.
Do not add a query whose answer the ticket does not need.

Rules:
- A 'CON_...' code in the ticket matches contractcodesynt, never contractcode. A 'VEH_...' code matches vehiclecodesynt.
- A company name in the ticket is a NAME: get its code with a subquery on silver.subsidiary_t, for example
  subsidiarycodesynt = (SELECT CAST(SubsiDiaryCode AS INT) FROM {catalog}.silver.subsidiary_t WHERE CompanyName = '...').
  In file_log and localvalue_t the subsidiary code is TEXT ('01201').
- Join silver.contract to gold.fleet_report on BOTH subsidiarycode and contractcode, never on contractcode alone.
- Never invent a value that is not in the ticket. Do not add a date filter if no date is mentioned.
- Search a local value exactly as the ticket writes it first (keep prefixes and punctuation, 'ID. BUZZ' is not 'BUZZ'); only then try shorter forms.
- LOCALCODE, LOCALVALUE and SUBSIDIARYCODE in localvalue_t and localvalue_history_t are TEXT. Always compare them with quotes
  (LOCALCODE = '76', SUBSIDIARYCODE = '20301'), never as a number, and never CAST them to a number: some codes are words ('JA') and
  the query fails.
- Use CAST(x AS STRING), never VARCHAR without a length. Never combine tables with UNION; use separate queries.
- Every query needs a WHERE or a LIMIT (50 at most). Select only the columns you need.

Ticket title: {title}
Ticket description:
{description}

Closest solved tickets of the same use case (precedents; follow their method and wording, change the values):
{precedents}

Reply with ONLY one JSON object:  {{"queries": ["SELECT ...", "SELECT ..."], "purpose": "one sentence: why these queries"}}
If the precedents already show the answer and no data check is needed, reply with an empty list of queries."""

RESULTS_PROMPT = """{results}

Now write the answer, grounded ONLY in these results (do not invent facts). The comment must recommend the same holding value as the finding; if they differ, fix it before answering. Never count rows as subsidiaries unless the query counted distinct subsidiaries. If a query FAILED, say that the query failed and
quote the error; never claim the data is wrong or invalid because of it, and set ready_to_close to false. Reply with ONLY one JSON object:
{{"done": true, "ticket_type": "email", "finding": "one sentence", "comment": "the comment to post on the ticket", "ready_to_close": false}}
ticket_type is "sql" only if the ticket asks for a query and its result; otherwise "email".
ready_to_close is true only if nothing else has to happen (the fix is already applied, or there is nothing to do)."""

REPAIR_PROMPT = """{results}

Some queries did not work. Reply with ONLY one JSON object holding the corrected version of the queries that failed
(just those): {{"queries": ["SELECT ..."]}}. Fix only what the error says."""


@dataclass
class QueryRecord:
    sql: str
    status: str            # ok | refused | failed
    detail: str = ""       # row count, or the reason


@dataclass
class Proposal:
    status: str                      # ok | gave_up | undetermined (the rules found no cause)
    ticket_type: str = ""
    comment: str = ""
    finding: str = ""
    ready_to_close: bool = False
    purpose: str = ""
    queries: list = field(default_factory=list)
    model: str = ""
    total_tokens: int = 0
    calls: int = 0
    last_answer: str = field(default="", repr=False)
    decisions: list = field(default_factory=list)   # UC1 only: one entry per local value
    solution: dict = field(default_factory=dict)    # UC2/UC3 by rules: layer, error_type, error_column, action, recipient
    statements: list = field(default_factory=list)   # UC1: the UPDATE / INSERT text to confirm (never run here)
    diagnosis: object = field(default=None, repr=False)   # UC2/UC3 by rules: the core.diagnose.Diagnosis


def format_precedents(neighbours):
    if not neighbours:
        return "(none)"
    blocks = []
    for number, item in enumerate(neighbours, 1):
        solution = re.sub(r"```.*?```", "[query omitted]", item.solution, flags=re.DOTALL)
        solution = " ".join(solution.split())[:MAX_PRECEDENT_CHARS]
        blocks.append(f"[{number}] {item.title}\nSolution: {solution}")
    return "\n\n".join(blocks)


def build_prompt(ticket: Ticket, uc, neighbours, catalog):
    return PROPOSE_PROMPT.format(
        schema=SCHEMA.format(catalog=catalog), catalog=catalog, uc=uc,
        max_queries=QUERIES_BY_USE_CASE.get(uc, 3), title=ticket.title,
        description=ticket.description[:MAX_DESCRIPTION_CHARS],
        precedents=format_precedents(neighbours),
    )


def parse_answer(text):
    """First JSON object in the model answer, or None."""
    start = text.find("{")
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


EMPTY_VALUES = (None, "", "null", "NULL", "None")


def _is_empty(value):
    return value in EMPTY_VALUES or (isinstance(value, str) and not value.strip())


def format_rows(rows):
    """Rows as JSON for the model. Empty columns are left out of each row, and when
    there are several rows the columns whose value differs between them are listed
    first: a field filled in one row and empty in another is often the root cause."""
    if not rows:
        return "No rows."
    shown_rows = rows[:MAX_ROWS_SHOWN]
    notes = []
    if len(shown_rows) >= 2:
        differing = {}
        for column in shown_rows[0]:
            values = [row.get(column) for row in shown_rows]
            if len({str(v) for v in values}) > 1:
                differing[column] = ["EMPTY" if _is_empty(v) else v for v in values]
        if differing:
            notes.append("Columns whose value differs between rows: "
                         + json.dumps(differing, default=str, ensure_ascii=False)[:800])
    kept = [{k: v for k, v in row.items() if not _is_empty(v)} for row in shown_rows]
    never_filled = [c for c in shown_rows[0] if all(_is_empty(r.get(c)) for r in shown_rows)]
    if never_filled:
        notes.append(f"{len(never_filled)} columns are empty in every row shown (left out).")
    text = json.dumps(kept, default=str, ensure_ascii=False)[:MAX_RESULT_CHARS]
    more = f" (showing {MAX_ROWS_SHOWN} of {len(rows)} rows)" if len(rows) > MAX_ROWS_SHOWN else ""
    return "\n".join(notes + [text]) + more


def _run_all(queries, catalog, run_sql, proposal):
    """Check and run each query. Returns (text for the model, how many did not work)."""
    parts, bad = [], 0
    for sql_text in queries:
        sql_text = str(sql_text)
        number = len(proposal.queries) + 1
        try:
            checked = sql_guard.check(sql_text, catalog)
        except sql_guard.UnsafeSQL as error:
            proposal.queries.append(QueryRecord(sql_text, "refused", str(error)))
            parts.append(f"Query {number}: {sql_text}\nREFUSED: {error}")
            bad += 1
            continue
        try:
            rows = run_sql(checked)
        except Exception as error:  # the database error text helps the model fix the query
            proposal.queries.append(QueryRecord(checked, "failed", str(error)[:300]))
            parts.append(f"Query {number}: {checked}\nFAILED: {str(error)[:500]}")
            bad += 1
            continue
        proposal.queries.append(QueryRecord(checked, "ok", f"{len(rows)} rows"))
        parts.append(f"Query {number}: {checked}\nResult ({len(rows)} rows): {format_rows(rows)}")
    return "\n\n".join(parts), bad


def solve(ticket: Ticket, uc, neighbours, run_id=None, chat=None, run_sql=None, catalog=None, use_rules=True):
    """UC1 goes through core.mapping (fixed queries, the model chooses). UC2 and UC3 go through
    core.rules (the record is looked up layer by layer, no model). The free investigation is the
    fallback: a UC1 ticket that names no subsidiary or value, a UC2/UC3 ticket that names no
    record code. chat and run_sql are replaceable, so tests need neither a model nor Databricks."""
    spent = {"tokens": 0, "calls": 0, "model": ""}
    if uc in ("UC2", "UC3") and use_rules:
        from core import rules
        done = rules.solve(ticket, run_sql=run_sql, catalog=catalog)
        if done is not None:
            return done
    if uc == "UC1":
        from core import mapping
        done = mapping.solve(ticket, neighbours, spent, run_id=run_id, chat=chat, run_sql=run_sql, catalog=catalog)
        if done is not None:
            done.total_tokens, done.calls, done.model = spent["tokens"], spent["calls"], spent["model"]
            return done
    proposal = _solve_free(ticket, uc, neighbours, run_id=run_id, chat=chat, run_sql=run_sql, catalog=catalog)
    proposal.total_tokens += spent["tokens"]
    proposal.calls += spent["calls"]
    return proposal


def _solve_free(ticket: Ticket, uc, neighbours, run_id=None, chat=None, run_sql=None, catalog=None):
    """The free investigation: the model proposes the queries."""
    chat = chat or llm_client.chat
    if run_sql is None:
        from core.databricks_access import run_query as run_sql
    catalog = catalog or env("COMMON_CATALOG", required=True)

    messages = [{"role": "user", "content": build_prompt(ticket, uc, neighbours, catalog)}]
    proposal = Proposal(status="gave_up")

    def ask(reminder):
        """One model call that must return a JSON object; one retry if it does not."""
        for attempt in range(2):
            answer = chat("solving", messages, max_tokens=MAX_TOKENS, run_id=run_id, ticket_id=ticket.op_id)
            proposal.calls += 1
            proposal.total_tokens += answer.total_tokens
            proposal.model = answer.model
            proposal.last_answer = answer.text
            messages.append({"role": "assistant", "content": answer.text})
            data = parse_answer(answer.text)
            if data is not None:
                return data
            if attempt == 0:
                messages.append({"role": "user", "content": reminder})
        return None

    plan = ask('Reply with ONLY one JSON object: {"queries": ["SELECT ..."], "purpose": "..."}.')
    if plan is None or not isinstance(plan.get("queries", []), list):
        return proposal
    proposal.purpose = str(plan.get("purpose", "")).strip()
    queries = [q for q in plan.get("queries", []) if str(q).strip()][:QUERIES_BY_USE_CASE.get(uc, 3)]

    results, bad = _run_all(queries, catalog, run_sql, proposal) if queries else ("No queries were run.", 0)

    if bad:
        messages.append({"role": "user", "content": REPAIR_PROMPT.format(results=results)})
        fix = ask('Reply with ONLY one JSON object: {"queries": ["SELECT ..."]}.')
        if fix is not None and isinstance(fix.get("queries", []), list):
            fixed = [q for q in fix["queries"] if str(q).strip()][:bad]
            if fixed:
                more, _ = _run_all(fixed, catalog, run_sql, proposal)
                results = results + "\n\nCorrected queries:\n" + more

    messages.append({"role": "user", "content": RESULTS_PROMPT.format(results=results)})
    answer = ask('Reply with ONLY one JSON object: {"done": true, "ticket_type": "email", "finding": "...", "comment": "...", "ready_to_close": false}.')
    if answer is None:
        return proposal
    comment = str(answer.get("comment", "")).strip()
    if not comment:
        messages.append({"role": "user", "content": "The answer needs a non-empty 'comment'. Reply again with the JSON object."})
        answer = ask("Reply with the JSON object, including a non-empty 'comment'.")
        comment = str((answer or {}).get("comment", "")).strip()
        if not comment:
            return proposal
    proposal.status = "ok"
    proposal.ticket_type = "sql" if str(answer.get("ticket_type", "")).lower() == "sql" else "email"
    proposal.comment = comment
    proposal.finding = str(answer.get("finding", "")).strip()
    proposal.ready_to_close = answer.get("ready_to_close") is True
    return proposal
