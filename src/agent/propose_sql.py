"""
Given a ticket and the REAL table schema from Databricks, ask the LLM to
propose a single read-only SQL query plus a plain-language purpose
explaining why that query is needed. This step NEVER executes anything —
it only proposes. Execution only happens after human approval.
"""

from llm_client import chat_json

CATALOG = "aiops_participants_synthethic_data"

SCHEMA_TEXT = f"""
Available tables (only the relevant columns are listed; more columns exist
but are not useful for ticket investigation):

- {CATALOG}.silver.contract (one row per contract, normalized source data):
  subsidiarycode (int), contractcode (int), contractlegacycode (string,
  sometimes literally 'NULL' as text), contractcodesynt (string, format
  'CON_<hex>' — THIS is the format used in ticket text), vehiclecode (int),
  vehiclecodesynt (string, format 'VEH_<hex>'), contractstatuscode,
  contractstatusdescription, customercode, contractdateregistration,
  contractdatedelivery, contractdatetermination, lpulicenseplate.
  Example: contractcode=5949579, contractcodesynt='CON_a496abb07de48cbc',
  contractstatusdescription='Running and isBillable'.

- {CATALOG}.silver.vehicle (one row per vehicle, normalized source data):
  subsidiarycode (int), vehiclecode (int), vehiclecodesynt (string,
  'VEH_<hex>'), vehicleidentificationnumber (string, real VIN),
  vehicleidentificationnumbersynt (string, NOTE: this field has a data
  quality bug — it is literally the text 'VEHICLEIDENTIFICATIONNUMBER_'
  plus a hash, not a usable VIN format. Do not rely on it matching a VIN
  mentioned in a ticket), vehregplatenumber (string, real license plate),
  vehcharmodel (string, vehicle model description).

- {CATALOG}.silver.subsidiary_t (lookup: subsidiary code to company name):
  SubsiDiaryCode (string), CompanyName (string, format like 'Wise Potato
  Industries SL' — THIS is how subsidiaries are named in ticket text),
  EmailContact (string).

- {CATALOG}.gold.fleet_report (consolidated monthly snapshot — one row per
  contract PER MONTH, partitioned by executionDate): subsidiaryCode (int),
  contractCode (int), vehRegPlateNumber (string), vehicleIdentificationNumber
  (string), contractLegacyCode (string, numeric format, NOT the 'CON_' hex
  format), executionDate (date). NOTE: a contract existing in silver.contract
  does not guarantee it appears in gold.fleet_report — this is a known real
  gap (propagation/ETL issue), not a bug in your query. If investigating
  whether something "exists in the system", check silver first, then
  separately check gold to see if it reached the consolidated report.
"""

PROMPT_TEMPLATE = """You are proposing a SQL query to investigate a support ticket about a
fleet management system. You may ONLY propose a single SELECT query. Never
propose INSERT, UPDATE, DELETE, DROP, or any statement that changes data.

{schema}

Rules you must follow:
- Identifiers in the ticket text starting with "CON_" are contract codes —
  match them against contractcodesynt, never against contractcode (the
  numeric internal code) or contractlegacycode.
- Identifiers starting with "VEH_" are vehicle codes — match them against
  vehiclecodesynt, never against vehiclecode.
- A subsidiary named in the ticket (a company name like "X Industries SL")
  is a NAME, not a code. Resolve it via silver.subsidiary_t
  (CompanyName -> SubsiDiaryCode) — never compare a name directly to a
  numeric subsidiarycode column.
- Never invent a value that is not stated in the ticket text (e.g. don't
  add a date filter if no date is mentioned).
- Always qualify table names with the full catalog.schema.table path shown
  above.

Ticket text:
{ticket_text}

Return JSON with exactly these fields:
- "table": the single table name you need to query (full catalog.schema.table
  path)
- "sql": the SELECT query you propose, as a plain string
- "purpose": one or two sentences, in plain language, explaining to a human
  reviewer WHY this query is needed and what it will confirm or rule out
"""

def propose_sql(ticket_text: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(schema=SCHEMA_TEXT, ticket_text=ticket_text)
    result = chat_json(prompt)
    return result