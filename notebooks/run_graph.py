# Databricks notebook source
# MAGIC %md
# MAGIC # Ticket Masters: run the ticket graph
# MAGIC Reads open tickets from OpenProject (read only), routes them, solves them and **stops at the human approval**.
# MAGIC Run the cells in order. `DRY_RUN = yes` prints the email row instead of writing it to `solutions_emails_sent`.

# COMMAND ----------

# MAGIC %pip install -r ../requirements.txt

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import os
import sys

dbutils.widgets.text("ticket_id", "", "OpenProject ticket id")
dbutils.widgets.dropdown("dry_run", "yes", ["yes", "no"], "DRY_RUN (yes = do not write the email row)")

# The repo root is the parent of this notebook's folder.
ROOT = os.path.dirname(os.getcwd())
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Not secrets: names of things. The secrets themselves stay in the secret scopes.
os.environ.update({
    "ENV_MODE": "databricks",
    "DATABRICKS_HOST": "https://dbc-9906de71-4afe.cloud.databricks.com",
    "DATABRICKS_CATALOG": "ticket_masters_dev_catalog",
    "COMMON_CATALOG": "aiops_participants_synthethic_data",
    "MAPPING_TABLE": "ticket_id_mapping_thursday,ticket_id_mapping_friday",
    "OPENPROJECT_BASE_URL": "https://projects.alenia.io",
    "OPENPROJECT_PROJECT": "hackathon-ticket-masters",
    "OPENPROJECT_WRITE_ENABLED": "false",
    "OPENPROJECT_SECRET_SCOPE": "ticket-masters-dev-scope",
    "OPENPROJECT_SECRET_KEY": "op-ticket-masters-dev-secret",
    "LLM_SECRET_SCOPE": "aiops-hackathon",
    "LLM_SECRET_KEY": "ai-api-scope-token",
})

# COMMAND ----------

from core import graph as flow
from core import ticket_ids
from core.sources import openproject

CATALOG = os.environ["COMMON_CATALOG"]   # silver / bronze / gold / monitoring tables
OUT_CATALOG = os.environ["DATABRICKS_CATALOG"]   # solutions.solutions_emails_sent


def send_email(row):
    """The team's own function writes the row; it only runs inside Databricks."""
    if dbutils.widgets.get("dry_run") == "yes":
        print("DRY RUN, row not written:", row)
        return
    from src.send_fake_email_solution import send_fake_email_solution
    send_fake_email_solution(
        your_catalog=OUT_CATALOG, ticket_id=row["ticket_id"], layer=row["layer"],
        email_recipient=row["recipient"], error_type=row["error_type"], action=row["action"],
        error_column=row.get("error_column") or None,
    )


graph = flow.build_graph(flow.Deps(run_id="notebook", catalog=CATALOG, send_email=send_email))

tickets, report = ticket_ids.attach_mapping_ids(openproject.read_tickets(only_open=True), ticket_ids.load_mapping_table())
print(f"{len(tickets)} open tickets; mapping ids: {report.matched} matched, {report.ambiguous} ambiguous, {report.missing} missing")
by_id = {str(t.op_id): t for t in tickets}

# COMMAND ----------

# Start one ticket: it runs until it needs a person.
ticket = by_id[dbutils.widgets.get("ticket_id").strip()]
result = flow.start(graph, ticket)
if "__interrupt__" in result:
    shown = result["__interrupt__"][0].value
    print("WAITING FOR APPROVAL")
    for key in ("ticket_id", "uc", "ticket_type", "finding", "comment", "solution", "statements"):
        print(f"{key}: {shown.get(key)}")
else:
    print("Ended without approval:", result.get("outcome"))

# COMMAND ----------

# The person decides. Change APPROVED to False to reject; EDITED_COMMENT = None keeps the proposed comment.
APPROVED = True
EDITED_COMMENT = None
done = flow.resume(graph, ticket, approved=APPROVED, comment=EDITED_COMMENT)
print("outcome:", done["outcome"])
