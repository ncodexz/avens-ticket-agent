"""Tests for core/databricks_access.py inside Databricks (ENV_MODE=databricks): no cluster needed."""
from core import databricks_access as access


class FakeRow:
    def __init__(self, **values):
        self.values = values

    def asDict(self):
        return dict(self.values)


class FakeSpark:
    def __init__(self, rows):
        self.rows, self.asked = rows, []

    def sql(self, text):
        self.asked.append(text)
        return self

    def collect(self):
        return self.rows


class FakeDbutils:
    class secrets:
        @staticmethod
        def get(scope, key):
            return f"{scope}/{key}"


def test_inside_databricks_queries_run_on_spark_and_come_back_as_dicts(monkeypatch):
    spark = FakeSpark([FakeRow(a=1, b="x")])
    monkeypatch.setenv("ENV_MODE", "databricks")
    monkeypatch.setattr(access, "_spark", lambda: spark)
    assert access.run_query("SELECT 1") == [{"a": 1, "b": "x"}] and spark.asked == ["SELECT 1"]


def test_inside_databricks_secrets_come_from_dbutils_without_a_login(monkeypatch):
    monkeypatch.setenv("ENV_MODE", "databricks")
    monkeypatch.setattr(access, "_dbutils", lambda: FakeDbutils)
    monkeypatch.setattr(access, "workspace_client", lambda: (_ for _ in ()).throw(AssertionError("no login here")))
    assert access.get_secret("scope", "key") == "scope/key"
