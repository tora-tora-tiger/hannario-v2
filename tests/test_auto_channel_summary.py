import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_channel_summary import (
    AutoSummaryConfig,
    find_summary_candidates,
    format_channel_context,
    load_auto_summary_config_from_env,
    run_auto_channel_summaries_once,
)


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


class AutoChannelSummaryTest(unittest.TestCase):
    def test_find_summary_candidates_uses_new_records_since_latest_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation_path = root / "discord_observations.jsonl"
            summary_path = root / "channel_summaries.jsonl"
            records = [
                {
                    "timestamp": "2026-05-31T00:00:00+00:00",
                    "channel_id": "123",
                    "channel_name": "general",
                    "author_display_name": "alice",
                    "author_id": "1",
                    "clean_content": "one",
                },
                {
                    "timestamp": "2026-05-31T00:01:00+00:00",
                    "channel_id": "123",
                    "channel_name": "general",
                    "author_display_name": "alice",
                    "author_id": "1",
                    "clean_content": "two",
                },
                {
                    "timestamp": "2026-05-31T00:02:00+00:00",
                    "channel_id": "123",
                    "channel_name": "general",
                    "author_display_name": "alice",
                    "author_id": "1",
                    "clean_content": "three",
                },
            ]
            write_jsonl(observation_path, records)
            write_jsonl(
                summary_path,
                [
                    {
                        "channel_id": "123",
                        "last_observed_at": "2026-05-31T00:00:00+00:00",
                        "summary": "old",
                    }
                ],
            )

            config = AutoSummaryConfig(
                enabled=True,
                limit=10,
                min_new_messages=2,
                observation_path=observation_path,
                summary_path=summary_path,
            )

            candidates = find_summary_candidates(config)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].channel_id, "123")
            self.assertEqual(candidates[0].new_record_count, 2)
            self.assertEqual(candidates[0].latest_summary_at, "2026-05-31T00:00:00+00:00")

    def test_find_summary_candidates_skips_when_not_enough_new_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation_path = root / "discord_observations.jsonl"
            summary_path = root / "channel_summaries.jsonl"
            write_jsonl(
                observation_path,
                [
                    {
                        "timestamp": "2026-05-31T00:00:00+00:00",
                        "channel_id": "123",
                        "channel_name": "general",
                        "clean_content": "one",
                    },
                    {
                        "timestamp": "2026-05-31T00:01:00+00:00",
                        "channel_id": "123",
                        "channel_name": "general",
                        "clean_content": "two",
                    },
                ],
            )
            write_jsonl(
                summary_path,
                [
                    {
                        "channel_id": "123",
                        "last_observed_at": "2026-05-31T00:00:00+00:00",
                        "summary": "old",
                    }
                ],
            )

            config = AutoSummaryConfig(
                enabled=True,
                limit=10,
                min_new_messages=2,
                observation_path=observation_path,
                summary_path=summary_path,
            )

            self.assertEqual(find_summary_candidates(config), [])

    def test_run_auto_channel_summaries_once_saves_summary_without_api_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation_path = root / "discord_observations.jsonl"
            summary_path = root / "channel_summaries.jsonl"
            write_jsonl(
                observation_path,
                [
                    {
                        "timestamp": "2026-05-31T00:00:00+00:00",
                        "channel_id": "123",
                        "channel_name": "general",
                        "author_display_name": "alice",
                        "author_id": "1",
                        "clean_content": "hello",
                    },
                    {
                        "timestamp": "2026-05-31T00:01:00+00:00",
                        "channel_id": "123",
                        "channel_name": "general",
                        "author_display_name": "bob",
                        "author_id": "2",
                        "clean_content": "world",
                    },
                ],
            )
            config = AutoSummaryConfig(
                enabled=True,
                limit=10,
                min_new_messages=2,
                observation_path=observation_path,
                summary_path=summary_path,
            )

            result = run_auto_channel_summaries_once(
                config,
                summarize=lambda context: f"summary for {context.splitlines()[1]}",
            )

            self.assertEqual(result.summarized, 1)
            self.assertEqual(result.errors, 0)
            saved = [json.loads(line) for line in summary_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["channel_id"], "123")
            self.assertEqual(saved[0]["record_count"], 2)
            self.assertIn("summary for channel: general (123)", saved[0]["summary"])

    def test_format_channel_context(self) -> None:
        text = format_channel_context(
            [
                {
                    "timestamp": "2026-05-31T00:00:00+00:00",
                    "channel_id": "123",
                    "channel_name": "general",
                    "author_display_name": "alice",
                    "author_id": "1",
                    "clean_content": "hello",
                }
            ],
            "123",
        )

        self.assertIn("observed_same_channel_context_oldest_first:", text)
        self.assertIn("channel: general (123)", text)
        self.assertIn("alice (1): hello", text)

    def test_load_auto_summary_config_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DISCORD_AUTO_SUMMARY_ENABLED": "1",
                "DISCORD_AUTO_SUMMARY_INTERVAL_SECONDS": "30",
                "DISCORD_AUTO_SUMMARY_LIMIT": "7",
                "DISCORD_AUTO_SUMMARY_MIN_NEW_MESSAGES": "3",
            },
        ):
            config = load_auto_summary_config_from_env()

        self.assertTrue(config.enabled)
        self.assertEqual(config.interval_seconds, 30)
        self.assertEqual(config.limit, 7)
        self.assertEqual(config.min_new_messages, 3)


if __name__ == "__main__":
    unittest.main()
