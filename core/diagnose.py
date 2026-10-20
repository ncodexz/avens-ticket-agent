"""Rule-based diagnosis of a missing contract or vehicle. No model is involved.

The record travels input file -> bronze -> silver (-> gold report). The cause is the first
station where it fails, and the answer uses the closed vocabulary of the official
solutions: layer, error_type, error_column, action.

Two separate parts, so the decision can be tested without Databricks:
- gather_facts(code, run_sql, catalog): runs fixed, guarded, read-only queries.
- decide(facts): pure function, facts in, Diagnosis out.

What the rules can and cannot see (measured on the exported data):
- For tickets that are still open, the trail is in the tables (file_log, bronze, silver,
  main_t). For tickets already closed the data was repaired, so the trail is gone.
- A record present in every layer has no trail: the diagnosis is "undetermined" and a
  person decides. Nothing is invented.
"""
import re
from dataclasses import dataclass, field

from core import sql_guard
from core.config import env

CODE_PATTERN = re.compile(r"\b(CON|VEH)_([0-9a-fA-F]+)\b")
FULL_HEX_LENGTH = 16
INTERNAL_RECIPIENT = "dataintegration@team.io"

# Per kind: bronze table, silver table, key column in both.
KINDS = {
    "CON": {"bronze": "bronze.contract_history", "silver": "silver.contract", "key": "contractcodesynt"},
    "VEH": {"bronze": "bronze.vehicle_history", "silver": "silver.vehicle", "key": "vehiclecodesynt"},
}

# Columns of the bronze history that change from row to row without meaning a data problem.
IGNORED_COLUMNS = {"filename", "dataactiondate", "dataactiontype", "iduser", "executiondate"}
EMPTY_TEXTS = {"", "null", "none", "nan"}

# The only two columns named as the cause in the 1000 official solved examples. Many other
# columns (amounts, rates) are legitimately empty in one file and filled in the next, so
# "differs between files" alone is not a cause. Extend this set when Alenia gives its list
# of mandatory fields.
MANDATORY_COLUMNS = {"productfamilycodesynt", "contractrealstartdatesynt"}

FILE_LOG_SQL = ("SELECT filename, pk_values FROM {catalog}.monitoring.file_log "
                "WHERE pk_values LIKE '{code}|%' LIMIT 20")
BRONZE_SQL = "SELECT * FROM {catalog}.{bronze} WHERE {key} = '{code}' LIMIT 20"
SILVER_SQL = "SELECT {key} FROM {catalog}.{silver} WHERE {key} = '{code}' LIMIT 1"
MAIN_T_SQL = ("SELECT layer, status, error_message FROM {catalog}.monitoring.main_t "
              "WHERE error_message LIKE '%{code}%' LIMIT 20")
SUBSIDIARIES_SQL = "SELECT CompanyName, EmailContact FROM {catalog}.silver.subsidiary_t LIMIT 200"
EMAIL_SQL = ("SELECT EmailContact FROM {catalog}.silver.subsidiary_t "
             "WHERE SubsiDiaryCode = '{subsidiary}' LIMIT 1")


@dataclass
class Diagnosis:
    status: str                      # determined | undetermined
    reason: str = ""                 # why it is undetermined
    code: str = ""
    layer: str = ""
    error_type: str = ""
    error_column: str = ""
    action: str = ""
    email_recipient: str = ""
    evidence: list = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    def label(self):
        """The four official columns, for comparing with the labelled examples."""
        return (self.layer, self.error_type, self.error_column, self.action)


def extract_code(text):
    """First CON_/VEH_ code in the text, or None. Returned with an upper-case prefix."""
    match = CODE_PATTERN.search(text or "")
    return f"{match.group(1).upper()}_{match.group(2).lower()}" if match else None


def is_empty(value):
    return value is None or str(value).strip().lower() in EMPTY_TEXTS


def differing_empty_columns(rows, only=None):
    """Columns empty in some bronze rows and filled in others (needs two rows or more).
    `only` limits the check to those columns.

    A field that is empty in one file and filled in the next is the signature of an input
    file that arrived incomplete. Columns that are empty in every row say nothing."""
    if len(rows) < 2:
        return []
    found = []
    for column in rows[0]:
        if column in IGNORED_COLUMNS or column.startswith("metadata"):
            continue
        if only is not None and column not in only:
            continue
        values = [row.get(column) for row in rows]
        if any(is_empty(v) for v in values) and any(not is_empty(v) for v in values):
            found.append(column)
    return found


def official_column_name(column):
    """productfamilycodesynt -> productfamilycode (the name the official solutions use)."""
    return column[:-4] if column.endswith("synt") else column


def email_from_text(subsidiaries, text):
    """EmailContact of the subsidiary whose CompanyName appears in the text (the longest name
    wins), or ''. A record that never arrived leaves no trace in file_log, so the ticket text
    is the only place that names its subsidiary."""
    lowered = (text or "").lower()
    best = ("", "")
    for row in subsidiaries or []:
        name = str(row.get("CompanyName", "")).strip()
        if name and name.lower() in lowered and len(name) > len(best[0]):
            best = (name, str(row.get("EmailContact", "")).strip())
    return best[1]


def gather_facts(code, run_sql=None, catalog=None, text=""):
    """Run the fixed queries for one code. Returns the facts dict used by decide().
    `text` is the ticket text: it names the subsidiary of a record that never arrived."""
    if run_sql is None:
        from core.databricks_access import run_query as run_sql
    catalog = catalog or env("COMMON_CATALOG", required=True)
    kind = KINDS[code[:3]]
    values = dict(catalog=catalog, code=code, key=kind["key"], bronze=kind["bronze"], silver=kind["silver"])
    facts = {"code": code, "kind": code[:3], "errors": []}

    def run(name, template, **extra):
        sql_text = template.format(**{**values, **extra})
        try:
            return run_sql(sql_guard.check(sql_text, catalog))
        except Exception as error:  # a failed query must be visible, never read as "no rows"
            facts["errors"].append(f"{name}: {str(error)[:200]}")
            return None

    file_rows = run("file_log", FILE_LOG_SQL)
    bronze_rows = run("bronze", BRONZE_SQL)
    silver_rows = run("silver", SILVER_SQL)
    main_rows = run("main_t", MAIN_T_SQL)

    facts["in_file_log"] = bool(file_rows)
    facts["in_bronze"] = bool(bronze_rows)
    facts["in_silver"] = bool(silver_rows)
    facts["empty_columns"] = differing_empty_columns(bronze_rows or [], only=MANDATORY_COLUMNS)
    facts["failed_layers"] = sorted({str(r.get("layer", "")).upper() for r in (main_rows or [])
                                     if str(r.get("status", "")).upper() == "FAILED"})
    facts["subsidiary"] = ""
    if file_rows:
        pk = str(file_rows[0].get("pk_values", ""))
        facts["subsidiary"] = pk.split("|")[1] if "|" in pk else ""
    facts["subsidiary_email"] = ""
    if facts["empty_columns"] and facts["subsidiary"]:
        email_rows = run("subsidiary_email", EMAIL_SQL, subsidiary=facts["subsidiary"])
        if email_rows:
            facts["subsidiary_email"] = str(email_rows[0].get("EmailContact", ""))
    if not (file_rows or bronze_rows or silver_rows) and text:
        facts["subsidiary_email"] = email_from_text(run("subsidiaries", SUBSIDIARIES_SQL), text)
    return facts


def decide(facts):
    """Facts in, diagnosis out. The first station where the record fails is the cause."""
    code = facts.get("code", "")

    def undetermined(reason, *evidence):
        return Diagnosis("undetermined", reason, code, evidence=list(evidence), facts=facts)

    if not code:
        return undetermined("no_code", "The ticket names no CON_ or VEH_ code.")
    if facts.get("errors"):
        return undetermined("query_failed", *facts["errors"])

    in_file, in_bronze, in_silver = facts["in_file_log"], facts["in_bronze"], facts["in_silver"]
    empty = facts.get("empty_columns", [])
    hex_length = len(code.split("_", 1)[1])

    if not (in_file or in_bronze or in_silver):
        if hex_length != FULL_HEX_LENGTH:
            return undetermined("code_looks_incomplete",
                                f"{code} has {hex_length} hex characters instead of {FULL_HEX_LENGTH}.")
        if not facts.get("subsidiary_email"):
            return undetermined("subsidiary_unknown",
                                "Never arrived, but the ticket names no known subsidiary to ask for the record.")
        return Diagnosis("determined", "", code, "input_file", "missing_row", "", "input_data_reload",
                         facts.get("subsidiary_email", ""),
                         ["Not in file_log, bronze or silver: it never arrived."], facts)
    if len(empty) > 1:
        return undetermined("several_empty_columns", f"Empty in one file and filled in another: {empty}")
    if empty:
        column = official_column_name(empty[0])
        return Diagnosis("determined", "", code, "input_file", "missing_data_in_column", column,
                         "input_data_reload", facts.get("subsidiary_email", ""),
                         [f"{empty[0]} is empty in one input file and filled in the next."], facts)
    if in_file and not in_bronze:
        proof = ["Received in the input file, no row in bronze."]
        if "BRONZE" in facts.get("failed_layers", []):
            proof.append("monitoring.main_t has a FAILED load into bronze for this record.")
        return Diagnosis("determined", "", code, "bronze", "missing_row", "", "file_to_bronze",
                         INTERNAL_RECIPIENT, proof, facts)
    if in_bronze and not in_silver:
        proof = ["In bronze, no row in silver."]
        if "SILVER" in facts.get("failed_layers", []):
            proof.append("monitoring.main_t has a FAILED load into silver for this record.")
        return Diagnosis("determined", "", code, "silver", "missing_row", "", "bronze_to_silver",
                         INTERNAL_RECIPIENT, proof, facts)
    if in_silver:
        return undetermined("present_in_all_layers",
                            "The record is in the input file, bronze and silver, with no empty field to explain it.")
    return undetermined("inconsistent_trail",
                        f"file_log={in_file}, bronze={in_bronze}, silver={in_silver}")


def diagnose(title, description, run_sql=None, catalog=None):
    """Ticket text in, diagnosis out."""
    code = extract_code(f"{title}\n{description}")
    if code is None:
        return decide({"code": ""})
    return decide(gather_facts(code, run_sql=run_sql, catalog=catalog, text=f"{title}\n{description}"))
