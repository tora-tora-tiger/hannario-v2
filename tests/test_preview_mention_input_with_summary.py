import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from preview_mention_input_with_summary import (
    build_preview_input,
    format_current_message,
    format_latest_channel_summary,
)


class PreviewMentionInputWithSummaryTest(unittest.TestCase):
    def test_format_latest_channel_summary_without_summary(self) -> None:
        self.assertEqual(
            format_latest_channel_summary(None),
            "supplemental_same_channel_summary:\n(no saved summary)",
        )

    def test_format_latest_channel_summary(self) -> None:
        summary = {
            "channel_name": "general",
            "channel_id": "123",
            "created_at": "2026-05-31T00:10:00+00:00",
            "first_observed_at": "2026-05-31T00:00:00+00:00",
            "last_observed_at": "2026-05-31T00:01:00+00:00",
            "record_count": 2,
            "summary": "要約です",
        }

        text = format_latest_channel_summary(summary)

        self.assertIn("supplemental_same_channel_summary:", text)
        self.assertIn("Use this only as older background", text)
        self.assertIn("channel: general (123)", text)
        self.assertIn("record_count: 2", text)
        self.assertIn("要約です", text)

    def test_format_current_message(self) -> None:
        mention = {
            "author_display_name": "alice",
            "author_id": "111",
            "clean_content": "どう思う？",
        }

        text = format_current_message(mention)

        self.assertIn("author: alice (111)", text)
        self.assertIn("content: どう思う？", text)

    def test_build_preview_input(self) -> None:
        mention = {
            "guild_name": "test-guild",
            "guild_id": "1",
            "channel_name": "general",
            "channel_id": "123",
            "author_display_name": "alice",
            "author_id": "111",
            "clean_content": "どう思う？",
            "recent_context": [],
        }
        summary = {
            "channel_name": "general",
            "channel_id": "123",
            "summary": "要約です",
        }

        text = build_preview_input(mention, summary)

        self.assertIn("Discord message", text)
        self.assertIn("priority: Prefer current_message", text)
        self.assertIn("current_time:", text)
        self.assertIn("local_timezone: Asia/Tokyo", text)
        self.assertIn("supplemental_same_channel_summary:", text)
        self.assertIn("saved_discord_api_recent_context_oldest_first:", text)
        self.assertIn("current_message:", text)
        self.assertLess(text.index("current_message:"), text.index("supplemental_same_channel_summary:"))


if __name__ == "__main__":
    unittest.main()
