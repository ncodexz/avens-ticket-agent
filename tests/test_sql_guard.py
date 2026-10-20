import pytest

from core.sql_guard import UnsafeSQL, check

CAT = "aiops_participants_synthethic_data"


def ok(sql):
    return check(sql, CAT)


def test_simple_select_is_accepted_and_semicolon_removed():
    sql = f"SELECT * FROM {CAT}.silver.contract WHERE contractcode = 'CON_1';"
    assert ok(sql) == sql.rstrip(";")


def test_limit_instead_of_where_is_accepted():
    ok(f"SELECT * FROM {CAT}.gold.fleet_report LIMIT 5")


def test_with_clause_and_join_are_accepted():
    ok(f"WITH s AS (SELECT * FROM {CAT}.silver.subsidiary_t WHERE CompanyName = 'A') "
       f"SELECT * FROM s JOIN {CAT}.silver.contract c ON c.subsidiarycode = s.SubsiDiaryCode LIMIT 5")


def test_backticked_names_are_accepted():
    ok(f"SELECT * FROM `{CAT}`.`silver`.`contract` WHERE contractcode = 'x'")


@pytest.mark.parametrize("sql", [
    f"INSERT INTO {CAT}.silver.contract VALUES (1)",
    f"DELETE FROM {CAT}.silver.contract WHERE contractcode = 'x'",
    f"DROP TABLE {CAT}.silver.contract",
    f"UPDATE {CAT}.silver.contract SET contractcode = 'y' WHERE contractcode = 'x'",
    f"CREATE TABLE {CAT}.silver.t AS SELECT * FROM {CAT}.silver.contract WHERE 1=1",
    "SET spark.sql.shuffle.partitions = 1",
])
def test_statements_that_change_things_are_refused(sql):
    with pytest.raises(UnsafeSQL):
        ok(sql)


def test_two_statements_are_refused():
    with pytest.raises(UnsafeSQL, match="one statement"):
        ok(f"SELECT 1 FROM {CAT}.silver.contract LIMIT 1; DROP TABLE x")


def test_comments_are_refused():
    with pytest.raises(UnsafeSQL, match="Comments"):
        ok(f"SELECT * FROM {CAT}.silver.contract WHERE 1=1 -- hello")


def test_forbidden_word_inside_a_text_value_is_fine():
    ok(f"SELECT * FROM {CAT}.monitoring.main_t WHERE message_type = 'update'")


def test_semicolon_inside_a_text_value_is_fine():
    ok(f"SELECT * FROM {CAT}.monitoring.main_t WHERE error_message = 'a;b'")


def test_query_without_where_or_limit_is_refused():
    with pytest.raises(UnsafeSQL, match="WHERE or a LIMIT"):
        ok(f"SELECT * FROM {CAT}.silver.contract")


def test_other_catalog_is_refused():
    with pytest.raises(UnsafeSQL, match="catalog"):
        ok("SELECT * FROM other_catalog.silver.contract LIMIT 1")


def test_other_schema_is_refused():
    with pytest.raises(UnsafeSQL, match="schemas"):
        ok(f"SELECT * FROM {CAT}.solutions.ticket_id_mapping_friday LIMIT 1")


def test_short_table_name_is_refused():
    with pytest.raises(UnsafeSQL, match="full table name"):
        ok("SELECT * FROM contract LIMIT 1")


def test_reading_files_directly_is_refused():
    with pytest.raises(UnsafeSQL):
        ok("SELECT * FROM read_files('dbfs:/mnt/dlk/storage/input/contract/x.csv') LIMIT 1")
    with pytest.raises(UnsafeSQL):
        ok("SELECT * FROM csv.`dbfs:/mnt/x.csv` LIMIT 1")


def test_empty_query_and_non_select_are_refused():
    with pytest.raises(UnsafeSQL):
        ok("   ;")
    with pytest.raises(UnsafeSQL, match="SELECT"):
        ok(f"SHOW TABLES IN {CAT}.silver")
