import sqlite3
import tempfile
import unittest
from pathlib import Path

from letta_db_tools import LETTA_DB_TOOL_SPECS


def load_function(source_code: str, function_name: str, db_path: Path):
    namespace = {"DB_PATH": str(db_path)}
    exec(source_code, namespace)
    return namespace[function_name]


class LettaDbToolsTest(unittest.TestCase):
    def test_tool_names_are_unique(self) -> None:
        names = [spec.name for spec in LETTA_DB_TOOL_SPECS]

        self.assertEqual(len(names), len(set(names)))

    def test_run_readonly_sql_source_select(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
                connection.execute("INSERT INTO items (name) VALUES ('alpha'), ('beta')")
                connection.commit()
            finally:
                connection.close()
            spec = next(spec for spec in LETTA_DB_TOOL_SPECS if spec.name == "run_readonly_sql")
            function = load_function(spec.source_code, spec.name, db_path)

            result = function("SELECT id, name FROM items ORDER BY id", limit=1)

            self.assertIn("sql_result:", result)
            self.assertIn("columns: id, name", result)
            self.assertIn("row_count: 1+", result)
            self.assertIn("name='alpha'", result)
            self.assertNotIn("name='beta'", result)

    def test_run_readonly_sql_source_supports_safe_pragma(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
                connection.commit()
            finally:
                connection.close()
            spec = next(spec for spec in LETTA_DB_TOOL_SPECS if spec.name == "run_readonly_sql")
            function = load_function(spec.source_code, spec.name, db_path)

            result = function("PRAGMA table_info(items)", limit=10)

            self.assertIn("sql_result:", result)
            self.assertIn("columns: cid, name, type", result)

    def test_run_readonly_sql_rejects_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            db_path.touch()
            spec = next(spec for spec in LETTA_DB_TOOL_SPECS if spec.name == "run_readonly_sql")
            function = load_function(spec.source_code, spec.name, db_path)

            result = function("DELETE FROM scheduled_tasks", limit=10)

            self.assertIn("Rejected SQL", result)

    def test_run_readonly_sql_description_mentions_safety_tests(self) -> None:
        spec = next(spec for spec in LETTA_DB_TOOL_SPECS if spec.name == "run_readonly_sql")

        self.assertIn("safety tests", spec.description)
        self.assertIn("rejected", spec.description)

    def test_run_readonly_sql_rejects_multiple_statements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            db_path.touch()
            spec = next(spec for spec in LETTA_DB_TOOL_SPECS if spec.name == "run_readonly_sql")
            function = load_function(spec.source_code, spec.name, db_path)

            result = function("SELECT 1; SELECT 2", limit=10)

            self.assertIn("multiple statements", result)


if __name__ == "__main__":
    unittest.main()
