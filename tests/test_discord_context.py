import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from discord_context import clean_message_content, format_discord_message


def fake_message(
    content: str,
    *,
    author_name: str = "alice",
    author_id: int = 111,
    created_at: datetime | None = None,
) -> SimpleNamespace:
    guild = SimpleNamespace(id=1, name="test-guild")
    channel = SimpleNamespace(id=2, name="general")
    author = SimpleNamespace(id=author_id, display_name=author_name)
    return SimpleNamespace(
        content=content,
        guild=guild,
        channel=channel,
        author=author,
        created_at=created_at or datetime(2026, 5, 31, tzinfo=UTC),
    )


class DiscordContextTest(unittest.TestCase):
    def test_clean_message_content_removes_bot_mention(self) -> None:
        bot_user = SimpleNamespace(id=999)
        message = fake_message("<@999> こんにちは  ")

        self.assertEqual(clean_message_content(message, bot_user), "こんにちは")

    def test_format_discord_message_includes_recent_context(self) -> None:
        bot_user = SimpleNamespace(id=999)
        recent_messages = [
            fake_message("さっきの話です", author_name="bob", author_id=222),
            fake_message("了解です", author_name="はんなり男", author_id=999),
        ]
        current_message = fake_message("<@999> どう思う？")

        text = format_discord_message(current_message, bot_user, recent_messages)

        self.assertIn("priority: Prefer current_message", text)
        self.assertIn("recent_same_channel_context_oldest_first:", text)
        self.assertIn("bob (222): さっきの話です", text)
        self.assertIn("はんなり男 (999): 了解です", text)
        self.assertIn("current_message:", text)
        self.assertIn("content: どう思う？", text)

    def test_format_discord_message_includes_channel_summary(self) -> None:
        bot_user = SimpleNamespace(id=999)
        current_message = fake_message("<@999> どう思う？")
        summary = {
            "channel_name": "general",
            "channel_id": "2",
            "created_at": "2026-05-31T00:00:00+00:00",
            "first_observed_at": "2026-05-31T00:00:00+00:00",
            "last_observed_at": "2026-05-31T00:01:00+00:00",
            "record_count": 2,
            "summary": "最近は天気の話をしている。",
        }

        text = format_discord_message(current_message, bot_user, channel_summary=summary)

        self.assertIn("supplemental_same_channel_summary:", text)
        self.assertIn("Use this only as older background", text)
        self.assertIn("最近は天気の話をしている。", text)
        self.assertIn("current_message:", text)
        self.assertLess(text.index("current_message:"), text.index("supplemental_same_channel_summary:"))


if __name__ == "__main__":
    unittest.main()
