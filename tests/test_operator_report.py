import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts import operator_report


class OperatorReportTest(unittest.TestCase):
    def test_parse_lookback(self):
        self.assertEqual(operator_report.parse_lookback("30m"), timedelta(minutes=30))
        self.assertEqual(operator_report.parse_lookback("6h"), timedelta(hours=6))
        self.assertEqual(operator_report.parse_lookback("2d"), timedelta(days=2))
        self.assertIsNone(operator_report.parse_lookback("all"))

    def test_parse_snapshot_timestamp(self):
        parsed = operator_report.parse_snapshot_timestamp(
            "memory_snapshots/2026-05-31T16-57-34.766414Z.json"
        )

        self.assertEqual(
            parsed,
            datetime(2026, 5, 31, 16, 57, 34, 766414, tzinfo=UTC),
        )

    def test_operator_report_prints_core_sections_and_warnings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            mentions = root / "mentions.jsonl"
            observations = root / "observations.jsonl"
            heartbeats = root / "heartbeats.jsonl"
            schedules = root / "schedules.jsonl"
            memory = root / "memory.jsonl"

            mentions.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-06-01T00:00:00+00:00",
                        "channel_name": "general",
                        "author_display_name": "User",
                        "response_trigger": "mention",
                        "clean_content": "hello",
                        "bot_reply": operator_report.FALLBACK_REPLY,
                        "letta_tool_events": [
                            {
                                "kind": "call",
                                "name": "fetch_web_text",
                                "arguments": "{}",
                            },
                            {
                                "kind": "return",
                                "name": "fetch_web_text",
                                "status": "error",
                                "text_preview": "failed",
                            },
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            observations.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-06-01T00:00:01+00:00",
                        "channel_name": "general",
                        "author_display_name": "User",
                        "clean_content": "ordinary chat",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            heartbeats.write_text(
                json.dumps(
                    {
                        "checked_at": "2026-06-01T00:00:02+00:00",
                        "action": "consider_reply",
                        "reason": "clear opening",
                        "post_should_post": True,
                        "post_reason": "ok",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            schedules.write_text(
                json.dumps(
                    {
                        "checked_at": "2026-06-01T00:00:03+00:00",
                        "task_id": 1,
                        "kind": "think",
                        "status_after": "done",
                        "should_send": False,
                        "note": "think later",
                        "internal_result": "done",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            memory.write_text(
                json.dumps(
                    {
                        "snapshot_path": "memory_snapshots/2026-06-01T00-00-04.000000Z.json",
                        "discord_message_id": "123",
                        "memory_write_tools": [{"name": "memory_replace"}],
                        "diff": "changed playbook",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "operator_report.py",
                "--since",
                "24h",
                "--mentions-path",
                str(mentions),
                "--observations-path",
                str(observations),
                "--heartbeats-path",
                str(heartbeats),
                "--schedule-path",
                str(schedules),
                "--memory-writes-path",
                str(memory),
            ]

            with patch.object(operator_report, "datetime") as datetime_mock:
                datetime_mock.now.return_value = datetime(2026, 6, 1, 1, tzinfo=UTC)
                datetime_mock.fromisoformat.side_effect = datetime.fromisoformat
                with patch("sys.argv", argv):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        operator_report.main()

            text = output.getvalue()
            self.assertIn("# Operator Report", text)
            self.assertIn("Triggered replies: 1", text)
            self.assertIn("Fallback replies: 1", text)
            self.assertIn("Letta tool calls logged: 1", text)
            self.assertIn("Letta tool return errors logged: 1", text)
            self.assertIn("Heartbeat decisions: 1", text)
            self.assertIn("Schedule records: 1", text)
            self.assertIn("Memory write audit records: 1", text)
            self.assertIn("fallback replies indicate Letta/API failures", text)
            self.assertIn("Letta tool return errors need review", text)


if __name__ == "__main__":
    unittest.main()
