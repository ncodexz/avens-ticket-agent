"""UC1 (a local value is missing, unmapped or mapped to the wrong holding value) without a
model writing SQL.

The previous design let the model write every query, so the same ticket got different
queries on each run (and a different answer). Here:
1. a SMALL model call reads the ticket and returns the subsidiary and the local values;
2. FOUR fixed queries (all checked by core.sql_guard) collect the evidence: the current
   mapping, its history, the candidate holding values, and how the other subsidiaries map
   the same value;
3. a model call must CHOOSE, for each value, an action and a target among the holding
   values that appear in the evidence. A target that is not in the evidence is not accepted.

If the ticket gives no subsidiary or no value, solve() returns None and the caller uses
the free investigation instead.
"""
import re

from core import llm_client, sql_guard
from core.config import env
from core.solver import (MAX_DESCRIPTION_CHARS, MAX_TOKENS, Proposal, QueryRecord, format_precedents,
                         format_rows, parse_answer)

MAX_VALUES = 6
MAX_WORDS = 8
MAX_CANDIDATES_SHOWN = 15
ACTIONS = ("remap", "map", "create_holding", "keep", "unclear")
STOPWORDS = {"THE", "AND", "FOR", "NOT", "CODE", "LOCAL", "VALUE", "MODEL", "MAKE", "SL", "WITH", "FROM"}

EXTRACT_PROMPT = """Read this IT ticket about a local value that maps to a global holding value (a make, model, product family or customer class).
Reply with ONLY one JSON object:
{{"company": "<the subsidiary name exactly as written in the ticket, e.g. 'Tiny Refrigerator Corporation SL'; empty if there is none>",
 "values": [{{"text": "<the local code or local value exactly as written in the ticket>", "meaning": "<what the ticket says it should be, e.g. 'Jaguar'; empty if it does not say>"}}]}}
At most {max_values} values (the first ones if there are more). Never shorten or change the text of a value: 'ID. BUZZ' stays 'ID. BUZZ'.

Title: {title}
Description:
{description}"""

SUBSIDIARY = "(SELECT SubsiDiaryCode FROM {catalog}.silver.subsidiary_t WHERE CompanyName = '{company}' LIMIT 1)"
HOLDING_JOIN = ("{kind} JOIN {catalog}.silver.holdingvalue_t hv "
                "ON hv.HOLDINGID = {alias}.HOLDINGID AND hv.CLASSID = {alias}.CLASSID")

CURRENT_SQL = ("SELECT lv.CLASSID, lv.LOCALCODE, lv.LOCALVALUE, lv.STATUS, lv.HOLDINGID, hv.NAME AS holding_name, "
               "hv.DESCRIPTION AS holding_description FROM {catalog}.silver.localvalue_t lv " + HOLDING_JOIN.format(
                   kind="LEFT", catalog="{catalog}", alias="lv") +
               " WHERE lv.SUBSIDIARYCODE = {subsidiary} AND (UPPER(lv.LOCALCODE) IN ({values}) "
               "OR UPPER(lv.LOCALVALUE) IN ({values})) LIMIT 50")
HISTORY_SQL = ("SELECT lh.CLASSID, lh.LOCALCODE, lh.LOCALVALUE, lh.HOLDINGID, hv.NAME AS holding_name, lh.EXECUTIONDATE "
               "FROM {catalog}.bronze.localvalue_history_t lh " + HOLDING_JOIN.format(
                   kind="LEFT", catalog="{catalog}", alias="lh") +
               " WHERE lh.SUBSIDIARYCODE = {subsidiary} AND (UPPER(lh.LOCALCODE) IN ({values}) "
               "OR UPPER(lh.LOCALVALUE) IN ({values})) ORDER BY lh.EXECUTIONDATE DESC LIMIT 50")
CANDIDATES_SQL = ("SELECT hv.CLASSID, hv.NAME, hv.DESCRIPTION, hv.HOLDINGID FROM {catalog}.silver.holdingvalue_t hv "
                  "WHERE {class_filter} AND ({conditions}) LIMIT 50")
GROUP_SQL = ("SELECT CASE WHEN UPPER(lv.LOCALCODE) IN ({values}) THEN UPPER(lv.LOCALCODE) ELSE UPPER(lv.LOCALVALUE) END "
             "AS matched_value, hv.NAME AS holding_name, hv.HOLDINGID, COUNT(DISTINCT lv.SUBSIDIARYCODE) AS subsidiaries "
             "FROM {catalog}.silver.localvalue_t lv " + HOLDING_JOIN.format(kind="INNER", catalog="{catalog}", alias="lv") +
             " WHERE lv.SUBSIDIARYCODE <> {subsidiary} AND (UPPER(lv.LOCALCODE) IN ({values}) "
             "OR UPPER(lv.LOCALVALUE) IN ({values})) GROUP BY 1, 2, 3 ORDER BY subsidiaries DESC LIMIT 40")

CHOOSE_PROMPT = """You are fixing ONE IT ticket about a local value mapping. A local value (LOCALCODE / LOCALVALUE of a subsidiary)
points to a global holding value (HOLDINGID). All the queries already ran; this is the evidence.

Ticket title: {title}
Ticket description:
{description}

Subsidiary: {company}
Values in the ticket: {values}

1. CURRENT mapping of these values in the subsidiary:
{current}

2. HISTORY of these values in the subsidiary (newest first):
{history}

3. CANDIDATE holding values (words taken from the ticket):
{candidates}

4. HOW THE OTHER SUBSIDIARIES map the same values (number of distinct subsidiaries):
{group}

Closest solved tickets (precedents; follow their method, change the values):
{precedents}

For EACH value of the ticket choose ONE action:
- "remap": it points to a wrong holding value. target_holdingid = one HOLDINGID that appears in sections 1-4.
- "map": it has no holding value (missing row or empty HOLDINGID). target_holdingid = one HOLDINGID of sections 1-4.
- "create_holding": no holding value of sections 1-4 fits; the holding value has to be created.
- "keep": the current mapping is already right (say why).
- "unclear": the evidence does not show what is right; a person must decide.
Rules:
- The ticket comes first: if it says which value is right or gives the reason, follow it; use what the other subsidiaries do only when the ticket does not say.
- A HOLDINGID that is filled but has no holding_name points to a holding value that does not exist: choose remap to a listed one or create_holding.
- The holding value that the ticket says the value is wrongly mapped to (and that section 1 shows it points to now) is never the target of a "remap": choose a different HOLDINGID. A local code and its name can both appear in the ticket ("9, Autonomo"); they are searched separately.
- Never invent a HOLDINGID, a name or a number. Quote subsidiary counts only from section 4.
- Do not answer "keep" when the ticket says something is wrong and the evidence agrees with the ticket.
- If a query FAILED, say so and use "unclear" for what depends on it.
Reply with ONLY one JSON object:
{{"decisions": [{{"value": "...", "action": "remap|map|create_holding|keep|unclear", "target_holdingid": "...or empty", "target_name": "...or empty", "reason": "one short sentence"}}],
 "comment": "the comment to post on the ticket: 2 to 5 sentences naming each value, the action and the target", "ready_to_close": false}}"""


def _quote(text):
    return str(text).replace("'", "''").replace("\\", "")


def _words(values):
    """Distinctive words for the candidate search: from each value and from what it should be."""
    found = []
    for item in values:
        for text in (item["text"], item["meaning"]):
            for word in re.findall(r"[A-Za-z0-9]+", text):
                word = word.upper()
                if word in STOPWORDS or word in found:
                    continue
                if len(word) >= 3 or (len(word) == 2 and any(c.isdigit() for c in word)):
                    found.append(word)
    return found[:MAX_WORDS]


def _compact(text):
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def search_terms(text):
    """What to look for in the database for one value as the ticket writes it. Tickets often
    join the code and the name ('POO (POOL CONTRACT)', '9, Autonomo', '200074 PORSCHE OTHER'),
    but the tables keep them in separate columns, so the whole text and each part are searched."""
    terms = [text]
    parts = re.split(r"\s*[(),]\s*|\s+[-/]\s+", text)
    first = re.match(r"^(\d+)\s+(\S.*)$", text)
    if first:
        parts += [first.group(1), first.group(2)]
    for part in parts:
        part = " ".join(part.split())
        if part and part.upper() not in [t.upper() for t in terms]:
            terms.append(part)
    return terms


def clean_values(raw):
    """Values from the extraction answer: text and meaning as strings, at most MAX_VALUES."""
    values = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text", "")).split())
        if text and text.lower() not in [v["text"].lower() for v in values]:
            values.append({"text": text, "meaning": " ".join(str(item.get("meaning", "")).split())})
    return values[:MAX_VALUES]


class _Runner:
    """Runs one checked query and records it; a failure is returned as text, never hidden."""

    def __init__(self, run_sql, catalog, proposal):
        self.run_sql, self.catalog, self.proposal = run_sql, catalog, proposal

    def __call__(self, template, **extra):
        sql_text = template.format(catalog=self.catalog, **extra)
        try:
            checked = sql_guard.check(sql_text, self.catalog)
        except sql_guard.UnsafeSQL as error:
            self.proposal.queries.append(QueryRecord(sql_text, "refused", str(error)))
            return None, f"REFUSED: {error}"
        try:
            rows = self.run_sql(checked)
        except Exception as error:
            self.proposal.queries.append(QueryRecord(checked, "failed", str(error)[:300]))
            return None, f"FAILED: {str(error)[:300]}"
        self.proposal.queries.append(QueryRecord(checked, "ok", f"{len(rows)} rows"))
        return rows, format_rows(rows)


def _rank(rows, words):
    def hits(row):
        text = f"{row.get('NAME', '')} {row.get('DESCRIPTION', '')}".upper()
        return sum(word in text for word in words)
    return sorted(rows, key=lambda row: (-hits(row), str(row.get("NAME", ""))))[:MAX_CANDIDATES_SHOWN]


def _known_ids(*row_lists):
    """Every HOLDINGID that appears in the evidence, with its name."""
    known = {}
    for rows in row_lists:
        for row in rows or []:
            holding_id = str(row.get("HOLDINGID", "")).strip().upper()
            name = row.get("holding_name") or row.get("NAME") or ""
            if holding_id and holding_id not in ("NULL", "NONE") and name:
                known[holding_id] = str(name)
    return known


def _current_ids(value, current):
    """HOLDINGIDs the value (as the model wrote it) points to now."""
    value = value.upper().strip()
    ids = set()
    for term, holding_ids in (current or {}).items():
        if not term or not value:
            continue
        if term == value or (len(term) >= 3 and re.search(r"(?<![A-Z0-9])" + re.escape(term) + r"(?![A-Z0-9])", value)):
            ids |= holding_ids
    return ids


def current_map(rows):
    """{LOCALCODE or LOCALVALUE in upper case: {HOLDINGID}} from the current-mapping rows."""
    result = {}
    for row in rows or []:
        holding_id = str(row.get("HOLDINGID", "")).strip().upper()
        if not holding_id or holding_id in ("NULL", "NONE"):
            continue
        for column in ("LOCALCODE", "LOCALVALUE"):
            term = str(row.get(column, "")).strip().upper()
            if term:
                result.setdefault(term, set()).add(holding_id)
    return result


def check_decisions(raw_decisions, known, current=None):
    """Keep only decisions whose target is in the evidence. A target the evidence does not
    contain is not accepted: the decision becomes 'unclear' and says why. `current` maps each
    value (upper case) to the HOLDINGIDs it points to now: a 'remap' to the holding value it
    already has changes nothing, so it also becomes 'unclear'."""
    names = {}
    for holding_id, name in known.items():
        names.setdefault(name.upper(), set()).add(holding_id)
    checked = []
    for item in raw_decisions if isinstance(raw_decisions, list) else []:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action", "")).strip().lower()
        action = action if action in ACTIONS else "unclear"
        decision = {"value": str(item.get("value", "")).strip(), "action": action,
                    "target_holdingid": str(item.get("target_holdingid", "")).strip().upper(),
                    "target_name": str(item.get("target_name", "")).strip(), "reason": str(item.get("reason", "")).strip()}
        if action in ("remap", "map"):
            holding_id = decision["target_holdingid"]
            if holding_id not in known:
                options = names.get(decision["target_name"].upper(), set())
                if len(options) == 1:
                    holding_id = next(iter(options))
                else:
                    decision.update(action="unclear", target_holdingid="",
                                    reason=(decision["reason"] + " [target not found in the evidence]").strip())
                    checked.append(decision)
                    continue
            if action == "remap" and holding_id in _current_ids(decision["value"], current):
                decision.update(action="unclear", target_holdingid="", target_name="",
                                reason=(decision["reason"] + " [the value already points to that holding value]").strip())
                checked.append(decision)
                continue
            decision["target_holdingid"], decision["target_name"] = holding_id, known[holding_id]
        else:
            decision["target_holdingid"] = ""
        checked.append(decision)
    return checked


UPDATE_SQL = ("UPDATE {catalog}.silver.localvalue_t SET HOLDINGID = '{holding}' WHERE SUBSIDIARYCODE = {subsidiary} "
              "AND CLASSID = {classid} AND LOCALCODE = '{code}'")
INSERT_SQL = ("INSERT INTO {catalog}.silver.localvalue_t (CLASSID, SUBSIDIARYCODE, LOCALCODE, LOCALVALUE, STATUS, HOLDINGID) "
              "SELECT {classid}, s.SubsiDiaryCode, '{code}', '{value}', 'A', '{holding}' "
              "FROM {catalog}.silver.subsidiary_t s WHERE s.CompanyName = '{company}'")


def _is_empty_id(value):
    return str(value or "").strip().lower() in ("", "null", "none")


def _rows_of(decision, current_rows):
    """Current rows that belong to the value of a decision (code or value equal, upper case)."""
    terms = {t.upper() for t in search_terms(decision["value"])}
    found, seen = [], set()
    for row in current_rows or []:
        if str(row.get("LOCALCODE", "")).upper() in terms or str(row.get("LOCALVALUE", "")).upper() in terms:
            key = (str(row.get("CLASSID")), str(row.get("LOCALCODE")))
            if key not in seen:
                seen.add(key)
                found.append(row)
    return found


def _classes(*row_lists):
    """{HOLDINGID: CLASSID} for every holding value seen in the evidence."""
    result = {}
    for rows in row_lists:
        for row in rows or []:
            holding_id = str(row.get("HOLDINGID", "")).strip().upper()
            if holding_id and not _is_empty_id(holding_id) and str(row.get("CLASSID", "")).isdigit():
                result[holding_id] = str(row["CLASSID"])
    return result


def attach_changes(decisions, current_rows, classes, catalog, company):
    """Writes, for each decision, the change a person has to confirm: `sql` (text only, nobody
    runs it here: sql_guard refuses UPDATE and INSERT) or `request` when no statement is
    possible. Returns the list of statements. When the current-mapping query failed we cannot
    know whether the row exists, so no statement is written."""
    subsidiary = SUBSIDIARY.format(catalog=catalog, company=_quote(company))
    statements = []
    for decision in decisions:
        decision["sql"], decision["request"] = [], ""
        action = decision["action"]
        if action in ("keep", "unclear"):
            continue
        rows = _rows_of(decision, current_rows)
        if action == "create_holding":
            classid = rows[0].get("CLASSID") if rows else ""
            decision["request"] = (f"Create the holding value '{decision['target_name'] or decision['value']}'"
                                   + (f" in class {classid}" if classid else "")
                                   + " (a person gives its name, description and parent), then map "
                                     f"'{decision['value']}' to it.")
            continue
        if current_rows is None:
            decision["request"] = "The current mapping could not be read: check it before writing any statement."
            continue
        holding = _quote(decision["target_holdingid"])
        if rows:
            for row in rows:
                decision["sql"].append(UPDATE_SQL.format(
                    catalog=catalog, holding=holding, subsidiary=subsidiary,
                    classid=int(row["CLASSID"]), code=_quote(row["LOCALCODE"])))
        elif action == "map" and decision["target_holdingid"] in classes:
            parts = search_terms(decision["value"])
            code = next((p for p in parts[1:] if p.isdigit()), decision["value"])
            name = next((p for p in parts[1:] if not p.isdigit()), decision["value"])
            decision["sql"].append(INSERT_SQL.format(
                catalog=catalog, classid=int(classes[decision["target_holdingid"]]), code=_quote(code),
                value=_quote(name), holding=holding, company=_quote(company)))
        else:
            decision["request"] = "The value was not found in the subsidiary, or its class is unknown: a person writes the statement."
        statements.extend(decision["sql"])
    return statements


def solve(ticket, neighbours, spent, run_id=None, chat=None, run_sql=None, catalog=None):
    """Returns a Proposal, or None when the ticket gives no subsidiary or value (the caller
    then uses the free investigation). `spent` is a dict {'tokens', 'calls'} that this
    function updates, so the cost is counted even when it returns None."""
    chat = chat or llm_client.chat
    description = ticket.description[:MAX_DESCRIPTION_CHARS]

    def ask(step, prompt, max_tokens):
        answer = chat(step, [{"role": "user", "content": prompt}], max_tokens=max_tokens,
                      run_id=run_id, ticket_id=ticket.op_id)
        spent["tokens"] += answer.total_tokens
        spent["calls"] += 1
        spent["model"] = answer.model
        return answer, parse_answer(answer.text)

    _, extracted = ask("extraction", EXTRACT_PROMPT.format(
        max_values=MAX_VALUES, title=ticket.title, description=description), 1200)
    if not extracted:
        return None
    company = " ".join(str(extracted.get("company", "")).split())
    values = clean_values(extracted.get("values"))
    haystack = f"{ticket.title} {ticket.description}".lower()
    if not company or company.lower() not in haystack or not values:
        return None

    if run_sql is None:
        from core.databricks_access import run_query as run_sql
    catalog = catalog or env("COMMON_CATALOG", required=True)
    proposal = Proposal(status="gave_up", purpose="Fixed UC1 queries: current mapping, history, candidates, other subsidiaries.")
    run = _Runner(run_sql, catalog, proposal)

    terms = []
    for item in values:
        for term in search_terms(item["text"]):
            if term.upper() not in terms:
                terms.append(term.upper())
    quoted = ", ".join(f"'{_quote(term)}'" for term in terms)
    common = dict(subsidiary=SUBSIDIARY.format(catalog=catalog, company=_quote(company)), values=quoted)
    current_rows, current_text = run(CURRENT_SQL, **common)
    history_rows, history_text = run(HISTORY_SQL, **common)

    words = _words(values)
    conditions = [f"UPPER(hv.NAME) LIKE '%{w}%' OR UPPER(hv.DESCRIPTION) LIKE '%{w}%'" for w in words]
    conditions += [f"REPLACE(REPLACE(UPPER(hv.NAME), ' ', ''), '.', '') LIKE '%{_compact(term)}%'"
                   for term in terms if len(_compact(term)) >= 3]
    classes = sorted({str(r.get("CLASSID")) for r in current_rows or [] if str(r.get("CLASSID", "")).isdigit()})
    class_filter = f"hv.CLASSID IN ({', '.join(classes)})" if classes else "1 = 1"
    candidate_rows, candidates_text = None, "No distinctive words in the ticket."
    if conditions:
        candidate_rows, candidates_text = run(CANDIDATES_SQL, class_filter=class_filter,
                                              conditions=" OR ".join(conditions))
        if candidate_rows is not None:
            candidate_rows = _rank(candidate_rows, words)
            candidates_text = format_rows(candidate_rows)
    group_rows, group_text = run(GROUP_SQL, **common)

    known = _known_ids(current_rows, history_rows, candidate_rows, group_rows)

    prompt = CHOOSE_PROMPT.format(
        title=ticket.title, description=description, company=company,
        values=", ".join(item["text"] + (f" (should be: {item['meaning']})" if item["meaning"] else "")
                         for item in values),
        current=current_text, history=history_text, candidates=candidates_text, group=group_text,
        precedents=format_precedents(neighbours))
    answer, data = ask("choice", prompt, MAX_TOKENS)
    if data is None:
        return None
    comment = str(data.get("comment", "")).strip()
    decisions = check_decisions(data.get("decisions"), known, current_map(current_rows))
    if not comment or not decisions:
        return None
    proposal.status = "ok"
    proposal.ticket_type = "sql"   # a change for a person to confirm; it is not delivered as an email row
    proposal.statements = attach_changes(decisions, current_rows, _classes(current_rows, history_rows, candidate_rows),
                                         catalog, company)
    proposal.comment = comment
    proposal.finding = "; ".join(
        f"{d['value']}: {d['action']}" + (f" -> {d['target_name']}" if d["target_name"] else "") for d in decisions)
    proposal.decisions = decisions
    proposal.ready_to_close = data.get("ready_to_close") is True and all(d["action"] == "keep" for d in decisions)
    proposal.last_answer = answer.text
    return proposal
