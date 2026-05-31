import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bot import maybe_handle_direct_schedule_request, run_due_scheduled_tasks_once, send_channel_message
from schedule_db import SCHEDULE_KIND_THINK, create_scheduled_task, get_scheduled_task, list_scheduled_tasks
from schedule_runner import ScheduleConfig


class FakeChannel:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)


class FakeClient:
    def __init__(self, channel: FakeChannel | None = None) -> None:
        self.channel = channel

    def get_channel(self, channel_id: int) -> FakeChannel | None:
        if channel_id == 123:
            return self.channel
        return None

    async def fetch_channel(self, channel_id: int) -> FakeChannel | None:
        if channel_id == 123:
            return self.channel
        return None


class ScheduleBotTest(unittest.IsolatedAsyncioTestCase):
    async def test_send_channel_message_sends_to_channel(self) -> None:
        channel = FakeChannel()
        client = FakeClient(channel)

        result = await send_channel_message(client, "123", "hello")  # type: ignore[arg-type]

        self.assertTrue(result.should_post)
        self.assertEqual(result.reason, "ok")
        self.assertEqual(channel.sent_messages, ["hello"])

    async def test_send_channel_message_rejects_invalid_channel_id(self) -> None:
        result = await send_channel_message(FakeClient(), "not-a-number", "hello")  # type: ignore[arg-type]

        self.assertFalse(result.should_post)
        self.assertEqual(result.reason, "invalid_channel_id")

    async def test_run_due_scheduled_tasks_posts_due_tasks_and_marks_done(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            log_path = Path(temp_dir) / "scheduled_tasks.jsonl"
            task = create_scheduled_task(
                channel_id="123",
                message="due message",
                due_at=datetime.now(UTC) - timedelta(minutes=1),
                db_path=db_path,
            )
            create_scheduled_task(
                channel_id="123",
                message="future message",
                due_at=datetime.now(UTC) + timedelta(hours=1),
                db_path=db_path,
            )
            channel = FakeChannel()
            config = ScheduleConfig(
                enabled=True,
                db_path=db_path,
                log_path=log_path,
            )

            await run_due_scheduled_tasks_once(config, FakeClient(channel))  # type: ignore[arg-type]

            updated_task = get_scheduled_task(task.id, db_path=db_path)
            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(channel.sent_messages, ["due message"])
        self.assertIsNotNone(updated_task)
        assert updated_task is not None
        self.assertEqual(updated_task.status, "done")
        self.assertIn('"should_send": true', log_text)
        self.assertIn('"status_after": "done"', log_text)

    async def test_run_due_scheduled_tasks_completes_internal_tasks_without_posting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            log_path = Path(temp_dir) / "scheduled_tasks.jsonl"
            task = create_scheduled_task(
                channel_id="123",
                message="internal message",
                due_at=datetime.now(UTC) - timedelta(minutes=1),
                kind=SCHEDULE_KIND_THINK,
                note="think about this",
                db_path=db_path,
            )
            channel = FakeChannel()
            config = ScheduleConfig(enabled=True, db_path=db_path, log_path=log_path)

            await run_due_scheduled_tasks_once(config, FakeClient(channel))  # type: ignore[arg-type]

            updated_task = get_scheduled_task(task.id, db_path=db_path)
            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(channel.sent_messages, [])
        self.assertIsNotNone(updated_task)
        assert updated_task is not None
        self.assertEqual(updated_task.status, "done")
        self.assertIn('"kind": "think"', log_text)
        self.assertIn('"reason": "internal_think"', log_text)
        self.assertIn('"should_send": false', log_text)

    async def test_run_due_scheduled_tasks_consults_letta_for_internal_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            log_path = Path(temp_dir) / "scheduled_tasks.jsonl"
            create_scheduled_task(
                channel_id="123",
                message="internal message",
                due_at=datetime.now(UTC) - timedelta(minutes=1),
                kind=SCHEDULE_KIND_THINK,
                note="think about this",
                db_path=db_path,
            )
            client = FakeClient(FakeChannel())
            client.letta_client = SimpleNamespace()
            client.letta_agent_id = "agent"
            config = ScheduleConfig(
                enabled=True,
                internal_consult_letta_enabled=True,
                db_path=db_path,
                log_path=log_path,
            )

            with patch("bot.consult_letta_for_internal_task", return_value="考えた"):
                await run_due_scheduled_tasks_once(config, client)  # type: ignore[arg-type]

            log_text = log_path.read_text(encoding="utf-8")

        self.assertIn('"internal_result": "考えた"', log_text)

    async def test_maybe_handle_direct_schedule_request_creates_relative_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "local.sqlite3"
            message = SimpleNamespace(
                id=999,
                content="<@111> 10分後に「直接登録」って言って",
                channel=SimpleNamespace(id=123),
                author=SimpleNamespace(id=456),
            )
            bot_user = SimpleNamespace(id=111)

            with patch.dict("os.environ", {"HANNARIO_DB_PATH": str(db_path)}):
                reply = await maybe_handle_direct_schedule_request(message, bot_user)  # type: ignore[arg-type]
                tasks = list_scheduled_tasks(db_path=db_path)

        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertIn("10分後", reply)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].message, "直接登録")
        self.assertEqual(tasks[0].created_by, "456")
        self.assertEqual(tasks[0].source_message_id, "999")

    async def test_maybe_handle_direct_schedule_request_asks_for_ambiguous_time(self) -> None:
        message = SimpleNamespace(
            id=999,
            content="<@111> 夕方に「曖昧」って言って",
            channel=SimpleNamespace(id=123),
            author=SimpleNamespace(id=456),
        )
        bot_user = SimpleNamespace(id=111)

        reply = await maybe_handle_direct_schedule_request(message, bot_user)  # type: ignore[arg-type]

        self.assertEqual(reply, "「曖昧」は何時に言えばいい？夕方だと少し曖昧だから、具体的な時刻で教えて。")


if __name__ == "__main__":
    unittest.main()
