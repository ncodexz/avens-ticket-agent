"""UC2 / UC3 by rules: the record is looked up layer by layer (core.diagnose) and the answer
is built from the closed vocabulary of the official solutions. No model is called, so the
cost is zero tokens and the same ticket always gets the same answer.

Three outcomes:
- determined: Proposal(status='ok') with `solution` = layer, error_type, error_column,
  action, recipient (what the delivery row needs) and a comment written from the evidence.
- undetermined: Proposal(status='undetermined'): the rules looked and found no cause.
  A person decides; core.undetermined keeps the list. Nothing is invented.
- None: the ticket names no CON_/VEH_ code, so the rules have nothing to look up and the
  caller uses the free investigation.
"""
from core import diagnose

COMMENTS = {
    ("input_file", "missing_row"): (
        "The record {code} is not in the input file, bronze or silver: it never arrived. "
        "{recipient} has to send it again (action: {action})."),
    ("input_file", "missing_data_in_column"): (
        "The record {code} arrived with {column} empty in one input file and filled in the next, "
        "so it is left out of the report. {recipient} has to send the file again with {column} "
        "filled (action: {action})."),
    ("bronze", "missing_row"): (
        "The record {code} is in the input file but has no row in bronze. {evidence} "
        "Reload the file into bronze (action: {action})."),
    ("silver", "missing_row"): (
        "The record {code} is in bronze but has no row in silver. {evidence} "
        "Reload bronze into silver (action: {action})."),
}

UNDETERMINED_COMMENT = ("After checking the input file, bronze, silver and the processing log, no cause "
                        "was found for {code}. Reason: {reason}. A person has to review it.")


def solution_of(diagnosis):
    """The fields the delivery step needs (all from the closed vocabulary)."""
    return {"layer": diagnosis.layer, "error_type": diagnosis.error_type,
            "error_column": diagnosis.error_column, "action": diagnosis.action,
            "recipient": diagnosis.email_recipient}


def comment_of(diagnosis):
    template = COMMENTS[(diagnosis.layer, diagnosis.error_type)]
    return template.format(code=diagnosis.code, recipient=diagnosis.email_recipient or "The subsidiary",
                           action=diagnosis.action, column=diagnosis.error_column,
                           evidence=" ".join(e for e in diagnosis.evidence[1:]))


def solve(ticket, run_sql=None, catalog=None):
    """Proposal, or None when the ticket gives no record code."""
    from core.solver import Proposal
    code = diagnose.extract_code(f"{ticket.title}\n{ticket.description}")
    if code is None:
        return None
    diagnosis = diagnose.decide(diagnose.gather_facts(code, run_sql=run_sql, catalog=catalog,
                                                           text=f"{ticket.title}\n{ticket.description}"))
    proposal = Proposal(status="ok", ticket_type="email", model="rules", diagnosis=diagnosis,
                        purpose="Fixed lookups: input file log, bronze, silver, processing log.")
    if diagnosis.status == "determined":
        proposal.solution = solution_of(diagnosis)
        proposal.comment = comment_of(diagnosis)
        proposal.finding = " / ".join(part or "-" for part in diagnosis.label())
        return proposal
    proposal.status = "undetermined"
    proposal.comment = UNDETERMINED_COMMENT.format(code=code, reason=diagnosis.reason)
    proposal.finding = f"undetermined: {diagnosis.reason}"
    return proposal
