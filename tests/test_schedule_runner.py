import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from schedule_db import create_scheduled_task
from schedule_runner import (
    DEFAULT_SCHEDULE_DUE_LIMIT,
    DEFAULT_SCHEDULE_INTERVAL_SECONDS,
    DEFAULT_SCHEDULE_LOG_PATH,
    ScheduleConfig,
    append_scheduled_task_delivery_log,
    build_scheduled_task_delivery,
    load_schedule_config_from_env,
    scheduled_task_delivery_record,
)


class ScheduleRunnerTest(unittest.TestCase):
    def test_load_schedule_config_defaults_disabled(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_schedule_config_from_env()

        self.assertEqual(
            config,
            ScheduleConfig(
                enabled=False,
                interval_seconds=DEFAULT_SCHEDULE_INTERVAL_SECONDS,
                due_limit=DEFAULT_SCHEDULE_DUE_LIMIT,
                internal_consult_letta_enabled=False,
                log_path=DEFAULT_SCHEDULE_LOG_PATH,
            ),
        )

    def test_load_schedule_config_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DISCORD_SCHEDULE_ENABLED": "1",
                "DISCORD_SCHEDULE_INTERVAL_SECONDS": "15",
                "DISCORD_SCHEDULE_DUE_LIMIT": "2",
                "DISCORD_SCHEDULE_INTERNAL_CONSULT_LETTA_ENABLED": "1",
                "HANNARIO_DB_PATH": "data/custom.sqlite3",
            },
        ):
            config = load_schedule_config_from_env()

        self.assertTrue(config.enabled)
        self.assertEqual(config.interval_seconds, 15)
        self.assertEqual(config.due_limit, 2)
        self.assertTrue(config.internal_consult_letta_enabled)
        self.assertEqual(config.db_path, Path("data/custom.sqlite3"))

    def test_delivery_record_and_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            log_path = Path(temp_dir) / "scheduled_tasks.jsonl"
            task = create_scheduled_task(
                channel_id="123",
                message="hello",
                due_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
                note="delivery note",
                db_path=db_path,
            )
            delivery = build_scheduled_task_delivery(
                task,
                checked_at="2026-06-01T10:00:00+00:00",
                should_send=True,
                reason="ok",
                internal_result="考えた",
                status_after="done",
            )

            append_scheduled_task_delivery_log(log_path, delivery)

            record = json.loads(log_path.read_text(encoding="utf-8"))

        self.assertEqual(scheduled_task_delivery_record(delivery), record)
        self.assertEqual(record["task_id"], 1)
        self.assertEqual(record["kind"], "post")
        self.assertEqual(record["channel_id"], "123")
        self.assertEqual(record["message"], "hello")
        self.assertEqual(record["note"], "delivery note")
        self.assertTrue(record["should_send"])
        self.assertEqual(record["internal_result"], "考えた")
        self.assertEqual(record["status_after"], "done")


if __name__ == "__main__":
    unittest.main()
