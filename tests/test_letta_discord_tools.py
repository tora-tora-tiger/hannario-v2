import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from letta_discord_tools import LETTA_DISCORD_TOOL_SPECS
from schedule_db import create_scheduled_task, list_scheduled_tasks


def load_function(
    source_code: str,
    function_name: str,
    log_dir: Path,
    db_path: Path | None = None,
):
    namespace = {"LOG_DIR": str(log_dir)}
    if db_path is not None:
        namespace["DB_PATH"] = str(db_path)
    exec(source_code, namespace)
    return namespace[function_name]


class LettaDiscordToolsTest(unittest.TestCase):
    def test_tool_names_are_unique(self) -> None:
        names = [spec.name for spec in LETTA_DISCORD_TOOL_SPECS]

        self.assertEqual(len(names), len(set(names)))

    def test_list_observed_discord_channels_source(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "discord_observations.jsonl").write_text(
                "\n".join(
                    [
                        '{"channel_id":"1","channel_name":"general","timestamp":"2026-05-31T00:00:00+00:00","author_display_name":"alice"}',
                        '{"channel_id":"1","channel_name":"general","timestamp":"2026-05-31T00:01:00+00:00","author_display_name":"bob"}',
                    ]
                ),
                encoding="utf-8",
            )
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "list_observed_discord_channels"
            )
            function = load_function(spec.source_code, spec.name, temp_dir)

            result = function()

            self.assertIn("#general (1): 2 observations", result)
            self.assertIn("latest_author=bob", result)
        finally:
            (temp_dir / "discord_observations.jsonl").unlink(missing_ok=True)
            temp_dir.rmdir()

    def test_get_recent_discord_observations_source(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "discord_observations.jsonl").write_text(
                (
                    '{"channel_id":"1","channel_name":"general",'
                    '"timestamp":"2026-05-31T00:00:00+00:00",'
                    '"author_display_name":"alice","author_id":"111",'
                    '"clean_content":"こんにちは"}'
                ),
                encoding="utf-8",
            )
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "get_recent_discord_observations"
            )
            function = load_function(spec.source_code, spec.name, temp_dir)

            result = function("1", 10)

            self.assertIn("observed_same_channel_context_oldest_first:", result)
            self.assertIn("alice (111): こんにちは", result)
        finally:
            (temp_dir / "discord_observations.jsonl").unlink(missing_ok=True)
            temp_dir.rmdir()

    def test_get_latest_discord_channel_summary_source(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "channel_summaries.jsonl").write_text(
                (
                    '{"channel_id":"1","channel_name":"general",'
                    '"created_at":"created","first_observed_at":"first",'
                    '"last_observed_at":"last","record_count":2,"summary":"要約"}'
                ),
                encoding="utf-8",
            )
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "get_latest_discord_channel_summary"
            )
            function = load_function(spec.source_code, spec.name, temp_dir)

            result = function("1")

            self.assertIn("latest_same_channel_summary:", result)
            self.assertIn("Use this only as older background", result)
            self.assertIn("要約", result)
        finally:
            (temp_dir / "channel_summaries.jsonl").unlink(missing_ok=True)
            temp_dir.rmdir()

    def test_get_recent_discord_internal_results_source(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "scheduled_tasks.jsonl").write_text(
                "\n".join(
                    [
                        '{"task_id":1,"kind":"post","channel_id":"1","internal_result":"ignore"}',
                        '{"task_id":2,"kind":"think","channel_id":"1","checked_at":"2026-05-31T00:00:00+00:00","note":"あとで考える","internal_result":"考えた"}',
                        '{"task_id":3,"kind":"observe","channel_id":"2","checked_at":"2026-05-31T00:01:00+00:00","note":"見る","internal_result":"見た"}',
                    ]
                ),
                encoding="utf-8",
            )
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "get_recent_discord_internal_results"
            )
            function = load_function(spec.source_code, spec.name, temp_dir)

            result = function(channel_id="1", limit=10, kind="all")

            self.assertIn("recent_internal_discord_results_oldest_first:", result)
            self.assertIn("task=#2 kind=think", result)
            self.assertIn("result=考えた", result)
            self.assertNotIn("task=#1", result)
            self.assertNotIn("task=#3", result)
        finally:
            (temp_dir / "scheduled_tasks.jsonl").unlink(missing_ok=True)
            temp_dir.rmdir()

    def test_list_discord_schedules_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            create_scheduled_task(
                channel_id="123",
                message="予定です",
                due_at=datetime(2026, 6, 1, 12, 0),
                db_path=db_path,
            )
            spec = next(
                spec for spec in LETTA_DISCORD_TOOL_SPECS if spec.name == "list_discord_schedules"
            )
            function = load_function(spec.source_code, spec.name, Path(temp_dir), db_path)

            result = function("pending", 10, "123")

            self.assertIn("scheduled_discord_tasks:", result)
            self.assertIn("#1 [pending] kind=post channel_id=123", result)
            self.assertIn("message=予定です", result)

    def test_create_discord_schedule_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "create_discord_schedule"
            )
            function = load_function(spec.source_code, spec.name, Path(temp_dir), db_path)
            due_at = datetime.now(ZoneInfo("Asia/Tokyo")) + timedelta(days=1)

            result = function("123", due_at.replace(microsecond=0).isoformat(), "21時です")
            tasks = list_scheduled_tasks(db_path=db_path)

            self.assertIn("Created scheduled Discord task #1", result)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].channel_id, "123")
            self.assertEqual(tasks[0].message, "21時です")
            self.assertEqual(tasks[0].kind, "post")

    def test_create_discord_schedule_rejects_past_due_at(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "create_discord_schedule"
            )
            function = load_function(spec.source_code, spec.name, Path(temp_dir), db_path)
            past_due_at = datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(minutes=10)

            result = function("123", past_due_at.isoformat(), "過去です")
            tasks = list_scheduled_tasks(db_path=db_path)

            self.assertIn("Failed to create schedule: due_at is in the past", result)
            self.assertEqual(tasks, [])

    def test_create_discord_schedule_supports_relative_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "create_discord_schedule"
            )
            function = load_function(spec.source_code, spec.name, Path(temp_dir), db_path)

            result = function(
                channel_id="123",
                due_at="",
                message="10分後です",
                timezone="Asia/Tokyo",
                relative_minutes=10,
            )
            tasks = list_scheduled_tasks(db_path=db_path)

            self.assertIn("Created scheduled Discord task #1", result)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].message, "10分後です")

    def test_create_internal_discord_schedule_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "create_internal_discord_schedule"
            )
            function = load_function(spec.source_code, spec.name, Path(temp_dir), db_path)

            result = function(
                kind="think",
                note="この話題をあとで考える",
                relative_minutes=10,
                channel_id="123",
            )
            tasks = list_scheduled_tasks(db_path=db_path)

            self.assertIn("Created internal Discord task #1", result)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].kind, "think")
            self.assertEqual(tasks[0].channel_id, "123")
            self.assertEqual(tasks[0].message, "この話題をあとで考える")
            self.assertEqual(tasks[0].note, "この話題をあとで考える")

    def test_create_internal_discord_schedule_rejects_post_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "create_internal_discord_schedule"
            )
            function = load_function(spec.source_code, spec.name, Path(temp_dir), db_path)

            result = function(kind="post", note="bad", relative_minutes=10, channel_id="123")
            tasks = list_scheduled_tasks(db_path=db_path, status="all")

            self.assertIn("kind must be think, observe, or follow_up", result)
            self.assertEqual(tasks, [])

    def test_cancel_discord_schedule_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            create_scheduled_task(
                channel_id="123",
                message="cancel me",
                due_at=datetime(2026, 6, 1, 12, 0),
                db_path=db_path,
            )
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "cancel_discord_schedule"
            )
            function = load_function(spec.source_code, spec.name, Path(temp_dir), db_path)

            result = function(1)
            tasks = list_scheduled_tasks(db_path=db_path, status="all")

            self.assertEqual(result, "Cancelled scheduled Discord task #1.")
            self.assertEqual(tasks[0].status, "cancelled")


if __name__ == "__main__":
    unittest.main()
