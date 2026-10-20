"""Tests for core/diagnose.py: no model and no Databricks needed."""
from core import diagnose

CAT = "aiops_participants_synthethic_data"
CODE = "CON_0123456789abcdef"


def facts(**changes):
    base = {"code": CODE, "kind": "CON", "errors": [], "in_file_log": True, "in_bronze": True,
            "in_silver": True, "empty_columns": [], "failed_layers": [], "subsidiary": "24601",
            "subsidiary_email": "x_sl@very_important_company.com"}
    base.update(changes)
    return base


def test_extract_code():
    assert diagnose.extract_code("Where is contract CON_ABC123def? (Acme)") == "CON_abc123def"
    assert diagnose.extract_code("vehicle VEH_0a1b2c missing") == "VEH_0a1b2c"
    assert diagnose.extract_code("no code here") is None


def test_differing_empty_columns_ignores_columns_empty_everywhere_and_file_names():
    rows = [{"filename": "a.csv", "pf": None, "start": "2020", "end": None},
            {"filename": "b.csv", "pf": "LOCAL_1", "start": "2020", "end": None}]
    assert diagnose.differing_empty_columns(rows) == ["pf"]
    assert diagnose.differing_empty_columns(rows[:1]) == []        # one row cannot be compared
    null_text = [{"a": "null"}, {"a": "x"}]
    assert diagnose.differing_empty_columns(null_text) == ["a"]    # the text 'null' counts as empty


def test_only_mandatory_columns_count_as_a_cause():
    rows = [{"amount": None, "productfamilycodesynt": None},
            {"amount": "10", "productfamilycodesynt": "LOCAL_1"}]
    assert diagnose.differing_empty_columns(rows) == ["amount", "productfamilycodesynt"]
    assert diagnose.differing_empty_columns(rows, only=diagnose.MANDATORY_COLUMNS) == ["productfamilycodesynt"]


def test_never_arrived():
    result = diagnose.decide(facts(in_file_log=False, in_bronze=False, in_silver=False))
    assert result.status == "determined"
    assert result.label() == ("input_file", "missing_row", "", "input_data_reload")


def test_incomplete_code_is_not_called_never_arrived():
    result = diagnose.decide(facts(code="CON_29897d6c4e7679", in_file_log=False, in_bronze=False, in_silver=False))
    assert result.status == "undetermined" and result.reason == "code_looks_incomplete"


def test_empty_field_names_the_official_column_and_the_subsidiary_email():
    result = diagnose.decide(facts(empty_columns=["productfamilycodesynt"]))
    assert result.label() == ("input_file", "missing_data_in_column", "productfamilycode", "input_data_reload")
    assert result.email_recipient == "x_sl@very_important_company.com"
    start = diagnose.decide(facts(empty_columns=["contractrealstartdatesynt"]))
    assert start.error_column == "contractrealstartdate"


def test_empty_field_wins_over_a_missing_layer():
    # The input file is the first station: if it arrived incomplete, that is the cause.
    result = diagnose.decide(facts(empty_columns=["contractrealstartdatesynt"], in_silver=False))
    assert result.layer == "input_file"


def test_several_empty_columns_go_to_a_person():
    result = diagnose.decide(facts(empty_columns=["a", "b"]))
    assert result.status == "undetermined" and result.reason == "several_empty_columns"


def test_missing_from_bronze_and_from_silver():
    bronze = diagnose.decide(facts(in_bronze=False, in_silver=False, failed_layers=["BRONZE"]))
    assert bronze.label() == ("bronze", "missing_row", "", "file_to_bronze")
    assert bronze.email_recipient == diagnose.INTERNAL_RECIPIENT and len(bronze.evidence) == 2
    silver = diagnose.decide(facts(in_silver=False))
    assert silver.label() == ("silver", "missing_row", "", "bronze_to_silver")


def test_present_everywhere_is_left_to_a_person():
    result = diagnose.decide(facts())
    assert result.status == "undetermined" and result.reason == "present_in_all_layers"


def test_failed_query_is_never_read_as_no_rows():
    result = diagnose.decide(facts(errors=["file_log: boom"], in_file_log=False, in_bronze=False, in_silver=False))
    assert result.status == "undetermined" and result.reason == "query_failed"


def test_no_code():
    assert diagnose.decide({"code": ""}).reason == "no_code"


class FakeWarehouse:
    """Answers each fixed query by the table it names."""

    def __init__(self, tables):
        self.tables = tables
        self.queries = []

    def __call__(self, sql_text):
        self.queries.append(sql_text)
        for name, rows in self.tables.items():
            if name in sql_text:
                return rows
        raise AssertionError(f"unexpected query: {sql_text}")


def test_every_template_passes_the_sql_guard_and_runs_end_to_end():
    warehouse = FakeWarehouse({
        "file_log": [{"filename": "contract_24601_2025-10-31.csv", "pk_values": f"{CODE}|24601"}],
        "contract_history": [{"filename": "a", "productfamilycodesynt": None, "x": "1"},
                             {"filename": "b", "productfamilycodesynt": "LOCAL_9", "x": "1"}],
        "silver.contract": [{"contractcodesynt": CODE}],
        "main_t": [],
        "subsidiary_t": [{"EmailContact": "acme_sl@very_important_company.com"}]})
    result = diagnose.diagnose("Missing contract", f"Where is {CODE}?", run_sql=warehouse, catalog=CAT)
    assert result.label() == ("input_file", "missing_data_in_column", "productfamilycode", "input_data_reload")
    assert result.email_recipient == "acme_sl@very_important_company.com"
    assert len(warehouse.queries) == 5 and all(CAT in q for q in warehouse.queries)


def test_vehicle_uses_the_vehicle_tables():
    warehouse = FakeWarehouse({
        "file_log": [{"filename": "f", "pk_values": "VEH_0a1b2c3d4e5f6a7b|24601"}],
        "vehicle_history": [], "silver.vehicle": [], "main_t": []})
    result = diagnose.diagnose("Missing vehicle", "VEH_0a1b2c3d4e5f6a7b is gone", run_sql=warehouse, catalog=CAT)
    assert result.label() == ("bronze", "missing_row", "", "file_to_bronze")


def test_a_database_error_becomes_undetermined():
    def broken(sql_text):
        raise RuntimeError("warehouse is down")
    result = diagnose.diagnose("t", CODE, run_sql=broken, catalog=CAT)
    assert result.status == "undetermined" and result.reason == "query_failed"
