import io
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from smoke_heartbeat_post import build_manual_heartbeat_result, print_decision

from heartbeat import HeartbeatPostDecision


class SmokeHeartbeatPostTest(unittest.TestCase):
    def test_build_manual_heartbeat_result(self) -> None:
        result = build_manual_heartbeat_result(
            "123",
            "hello",
            now=datetime(2026, 5, 31, 0, 0, tzinfo=UTC),
        )

        self.assertEqual(result.checked_at, "2026-05-31T00:00:00+00:00")
        self.assertEqual(result.action, "consider_reply")
        self.assertEqual(result.channel_id, "123")
        self.assertEqual(result.message, "hello")

    def test_print_decision(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            print_decision(
                HeartbeatPostDecision(
                    True,
                    "ok",
                    channel_id="123",
                    message="hello",
                )
            )

        text = output.getvalue()
        self.assertIn("should_post=True", text)
        self.assertIn("reason=ok", text)
        self.assertIn("channel_id=123", text)
        self.assertIn("message: hello", text)


if __name__ == "__main__":
    unittest.main()
