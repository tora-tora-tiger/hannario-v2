import tempfile
import unittest
from pathlib import Path

from channel_summaries import (
    compact_summary_record,
    format_channel_summary_for_prompt,
    read_latest_channel_summary,
    summary_matches_channel,
)


class ChannelSummariesModuleTest(unittest.TestCase):
    def test_summary_matches_channel(self) -> None:
        self.assertTrue(summary_matches_channel({"channel_id": "123"}, "123"))
        self.assertTrue(summary_matches_channel({"channel_id": 123}, "123"))
        self.assertFalse(summary_matches_channel({"channel_id": "456"}, "123"))

    def test_read_latest_channel_summary(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        path = temp_dir / "summaries.jsonl"
        try:
            path.write_text(
                "\n".join(
                    [
                        '{"channel_id":"123","summary":"old"}',
                        '{"channel_id":"456","summary":"other"}',
                        '{"channel_id":"123","summary":"new"}',
                    ]
                ),
                encoding="utf-8",
            )

            record = read_latest_channel_summary("123", path)

            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record["summary"], "new")
        finally:
            path.unlink(missing_ok=True)
            temp_dir.rmdir()

    def test_read_latest_channel_summary_missing_file(self) -> None:
        self.assertIsNone(read_latest_channel_summary("123", Path("missing.jsonl")))

    def test_compact_summary_record(self) -> None:
        record = {
            "created_at": "created",
            "channel_id": "123",
            "channel_name": "general",
            "record_count": 2,
            "first_observed_at": "first",
            "last_observed_at": "last",
            "model": "model",
            "summary": "summary",
            "context": "large context",
        }

        compact = compact_summary_record(record)

        self.assertEqual(
            compact,
            {
                "created_at": "created",
                "channel_id": "123",
                "channel_name": "general",
                "record_count": 2,
                "first_observed_at": "first",
                "last_observed_at": "last",
                "model": "model",
                "summary": "summary",
            },
        )

    def test_format_channel_summary_for_prompt(self) -> None:
        text = format_channel_summary_for_prompt(
            {
                "channel_name": "general",
                "channel_id": "123",
                "created_at": "created",
                "first_observed_at": "first",
                "last_observed_at": "last",
                "record_count": 2,
                "summary": "summary",
            }
        )

        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("supplemental_same_channel_summary:", text)
        self.assertIn("Use this only as older background", text)
        self.assertIn("channel: general (123)", text)
        self.assertIn("summary", text)

    def test_format_channel_summary_for_prompt_without_record(self) -> None:
        self.assertIsNone(format_channel_summary_for_prompt(None))


if __name__ == "__main__":
    unittest.main()
