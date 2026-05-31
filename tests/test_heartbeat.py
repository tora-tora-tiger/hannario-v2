import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from heartbeat import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_HEARTBEAT_POST_COOLDOWN_SECONDS,
    DEFAULT_HEARTBEAT_LOG_PATH,
    HeartbeatDecision,
    HeartbeatConfig,
    HeartbeatPostDecision,
    HeartbeatResult,
    append_heartbeat_log,
    build_heartbeat_input,
    decide_heartbeat_post,
    format_observation_record,
    heartbeat_log_record,
    load_heartbeat_config_from_env,
    parse_heartbeat_decision,
    parse_positive_int_env,
    read_recent_jsonl_records,
    record_heartbeat_post,
    run_heartbeat_once,
)


class HeartbeatTest(unittest.TestCase):
    def test_load_heartbeat_config_defaults_disabled(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_heartbeat_config_from_env()

        self.assertEqual(
            config,
            HeartbeatConfig(
                enabled=False,
                interval_seconds=DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
                log_path=DEFAULT_HEARTBEAT_LOG_PATH,
            ),
        )

    def test_load_heartbeat_config_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DISCORD_HEARTBEAT_ENABLED": "1",
                "DISCORD_HEARTBEAT_INTERVAL_SECONDS": "30",
                "DISCORD_HEARTBEAT_CONSULT_LETTA_ENABLED": "1",
                "DISCORD_HEARTBEAT_POST_ENABLED": "1",
                "DISCORD_HEARTBEAT_OBSERVATION_LIMIT": "5",
                "DISCORD_HEARTBEAT_POST_COOLDOWN_SECONDS": "60",
                "DISCORD_HEARTBEAT_POST_MAX_CHARS": "80",
            },
        ):
            config = load_heartbeat_config_from_env()

        self.assertTrue(config.enabled)
        self.assertEqual(config.interval_seconds, 30)
        self.assertTrue(config.consult_letta_enabled)
        self.assertTrue(config.post_enabled)
        self.assertEqual(config.observation_limit, 5)
        self.assertEqual(config.post_cooldown_seconds, 60)
        self.assertEqual(config.post_max_chars, 80)

    def test_parse_positive_int_env_uses_default_for_invalid_value(self) -> None:
        with (
            patch.dict(os.environ, {"TEST_INTERVAL": "bad"}),
            patch("heartbeat.logging.warning"),
        ):
            self.assertEqual(parse_positive_int_env("TEST_INTERVAL", 10), 10)

    def test_run_heartbeat_once_logs_current_time(self) -> None:
        now = datetime(2026, 5, 31, 0, 0, tzinfo=UTC)

        with patch("heartbeat.logging.info") as log_info:
            result = run_heartbeat_once(HeartbeatConfig(), now=now)

        self.assertEqual(result.checked_at, "2026-05-31T00:00:00+00:00")
        log_info.assert_called_once_with(
            "Discord heartbeat tick checked_at=%s",
            "2026-05-31T00:00:00+00:00",
        )

    def test_read_recent_jsonl_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "records.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"timestamp":"1","clean_content":"one"}',
                        '{"timestamp":"2","clean_content":"two"}',
                        '{"timestamp":"3","clean_content":"three"}',
                    ]
                ),
                encoding="utf-8",
            )

            records = read_recent_jsonl_records(path, 2)

        self.assertEqual([record["clean_content"] for record in records], ["two", "three"])

    def test_format_observation_record(self) -> None:
        text = format_observation_record(
            {
                "timestamp": "2026-05-31T00:00:00+00:00",
                "channel_name": "general",
                "channel_id": "123",
                "author_display_name": "alice",
                "author_id": "111",
                "clean_content": "hello",
            }
        )

        self.assertEqual(
            text,
            "- 2026-05-31T00:00:00+00:00 #general (123) alice (111): hello",
        )

    def test_build_heartbeat_input(self) -> None:
        now = datetime(2026, 5, 31, 0, 0, tzinfo=UTC)
        text = build_heartbeat_input(
            [
                {
                    "timestamp": "2026-05-31T00:00:00+00:00",
                    "channel_name": "general",
                    "channel_id": "123",
                    "author_display_name": "alice",
                    "author_id": "111",
                    "clean_content": "hello",
                }
            ],
            now=now,
        )

        self.assertIn("Discord heartbeat", text)
        self.assertIn("current_time:", text)
        self.assertIn("not sending a Discord message directly", text)
        self.assertIn("Return JSON only.", text)
        self.assertIn('Default to action "none".', text)
        self.assertIn('"consider_reply"', text)
        self.assertIn("Bad reasons: repeated content", text)
        self.assertIn("recent_observations_oldest_first:", text)
        self.assertIn("alice (111): hello", text)

    def test_parse_heartbeat_decision_json_none(self) -> None:
        decision = parse_heartbeat_decision(
            '{"action":"none","reason":"特になし","channel_id":null,"message":""}'
        )

        self.assertEqual(
            decision,
            HeartbeatDecision(
                action="none",
                reason="特になし",
                channel_id=None,
                message="",
            ),
        )

    def test_parse_heartbeat_decision_json_consider_reply(self) -> None:
        decision = parse_heartbeat_decision(
            '{"action":"consider_reply","reason":"質問がある","channel_id":"123","message":"大丈夫？"}'
        )

        self.assertEqual(decision.action, "consider_reply")
        self.assertEqual(decision.reason, "質問がある")
        self.assertEqual(decision.channel_id, "123")
        self.assertEqual(decision.message, "大丈夫？")

    def test_parse_heartbeat_decision_rejects_unknown_action(self) -> None:
        decision = parse_heartbeat_decision(
            '{"action":"post_now","reason":"bad","channel_id":"123","message":"hi"}'
        )

        self.assertEqual(decision.action, "none")

    def test_parse_heartbeat_decision_legacy_action(self) -> None:
        decision = parse_heartbeat_decision("特に注目すべきことはありません。action=none")

        self.assertEqual(decision.action, "none")
        self.assertIn("action=none", decision.reason)

    def test_run_heartbeat_once_skips_consult_when_disabled(self) -> None:
        now = datetime(2026, 5, 31, 0, 0, tzinfo=UTC)

        result = run_heartbeat_once(
            HeartbeatConfig(consult_letta_enabled=False),
            client=SimpleNamespace(),
            agent_id="agent",
            now=now,
        )

        self.assertIsNone(result.letta_reply)

    def test_run_heartbeat_once_consults_letta(self) -> None:
        now = datetime(2026, 5, 31, 0, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "observations.jsonl"
            path.write_text(
                '{"timestamp":"2026-05-31T00:00:00+00:00","clean_content":"hello"}\n',
                encoding="utf-8",
            )
            config = HeartbeatConfig(
                consult_letta_enabled=True,
                observation_path=path,
            )

            with patch(
                "heartbeat.consult_letta_for_heartbeat",
                return_value='{"action":"none","reason":"特になし","channel_id":null,"message":""}',
            ):
                result = run_heartbeat_once(
                    config,
                    client=SimpleNamespace(),
                    agent_id="agent",
                    now=now,
                )

        self.assertEqual(result.action, "none")
        self.assertEqual(result.reason, "特になし")

    def test_decide_heartbeat_post_disabled(self) -> None:
        result = HeartbeatResult(
            checked_at="time",
            action="consider_reply",
            channel_id="123",
            message="hello",
        )

        decision = decide_heartbeat_post(HeartbeatConfig(post_enabled=False), result, {})

        self.assertFalse(decision.should_post)
        self.assertEqual(decision.reason, "post_disabled")

    def test_decide_heartbeat_post_requires_consider_reply(self) -> None:
        result = HeartbeatResult(checked_at="time", action="none")

        decision = decide_heartbeat_post(HeartbeatConfig(post_enabled=True), result, {})

        self.assertFalse(decision.should_post)
        self.assertEqual(decision.reason, "action=none")

    def test_decide_heartbeat_post_requires_channel_and_message(self) -> None:
        config = HeartbeatConfig(post_enabled=True)

        missing_channel = decide_heartbeat_post(
            config,
            HeartbeatResult(checked_at="time", action="consider_reply", message="hello"),
            {},
        )
        missing_message = decide_heartbeat_post(
            config,
            HeartbeatResult(checked_at="time", action="consider_reply", channel_id="123"),
            {},
        )

        self.assertEqual(missing_channel.reason, "missing_channel_id")
        self.assertEqual(missing_message.reason, "missing_message")

    def test_decide_heartbeat_post_allows_valid_candidate(self) -> None:
        result = HeartbeatResult(
            checked_at="time",
            action="consider_reply",
            channel_id="123",
            message=" hello ",
        )

        decision = decide_heartbeat_post(HeartbeatConfig(post_enabled=True), result, {})

        self.assertTrue(decision.should_post)
        self.assertEqual(decision.channel_id, "123")
        self.assertEqual(decision.message, "hello")

    def test_decide_heartbeat_post_truncates_message(self) -> None:
        result = HeartbeatResult(
            checked_at="time",
            action="consider_reply",
            channel_id="123",
            message="abcdefghij",
        )

        decision = decide_heartbeat_post(
            HeartbeatConfig(post_enabled=True, post_max_chars=5),
            result,
            {},
        )

        self.assertEqual(decision.message, "ab...")

    def test_decide_heartbeat_post_truncates_very_short_max_chars(self) -> None:
        result = HeartbeatResult(
            checked_at="time",
            action="consider_reply",
            channel_id="123",
            message="abcdefghij",
        )

        decision = decide_heartbeat_post(
            HeartbeatConfig(post_enabled=True, post_max_chars=2),
            result,
            {},
        )

        self.assertEqual(decision.message, "ab")

    def test_decide_heartbeat_post_respects_cooldown(self) -> None:
        now = datetime(2026, 5, 31, 0, 0, tzinfo=UTC)
        result = HeartbeatResult(
            checked_at="time",
            action="consider_reply",
            channel_id="123",
            message="hello",
        )
        last_post_at_by_channel = {
            "123": now,
        }

        decision = decide_heartbeat_post(
            HeartbeatConfig(
                post_enabled=True,
                post_cooldown_seconds=DEFAULT_HEARTBEAT_POST_COOLDOWN_SECONDS,
            ),
            result,
            last_post_at_by_channel,
            now=now,
        )

        self.assertFalse(decision.should_post)
        self.assertEqual(decision.reason, "post_cooldown")

    def test_record_heartbeat_post(self) -> None:
        now = datetime(2026, 5, 31, 0, 0, tzinfo=UTC)
        last_post_at_by_channel: dict[str, datetime] = {}

        record_heartbeat_post(last_post_at_by_channel, "123", now=now)

        self.assertEqual(last_post_at_by_channel["123"], now)

    def test_heartbeat_log_record(self) -> None:
        result = HeartbeatResult(
            checked_at="checked",
            letta_reply='{"action":"none"}',
            action="none",
            reason="特になし",
        )
        post_decision = HeartbeatPostDecision(False, "action=none")

        record = heartbeat_log_record(result, post_decision)

        self.assertEqual(record["checked_at"], "checked")
        self.assertEqual(record["action"], "none")
        self.assertEqual(record["reason"], "特になし")
        self.assertNotIn("letta_reply", record)
        self.assertFalse(record["post_should_post"])
        self.assertEqual(record["post_reason"], "action=none")

    def test_append_heartbeat_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "heartbeats.jsonl"
            append_heartbeat_log(
                path,
                HeartbeatResult(checked_at="checked", action="none"),
                HeartbeatPostDecision(False, "action=none"),
            )

            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["checked_at"], "checked")
        self.assertEqual(records[0]["post_reason"], "action=none")


if __name__ == "__main__":
    unittest.main()
