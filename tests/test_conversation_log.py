import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from hannario.conversation_log import (
    mention_log_record,
    observation_log_record,
    tool_event_log_record,
)
from hannario.letta_agent import LettaToolEvent


def fake_message(
    content: str,
    *,
    message_id: int = 100,
    author_name: str = "alice",
    author_id: int = 111,
    created_at: datetime | None = None,
) -> SimpleNamespace:
    guild = SimpleNamespace(id=1, name="test-guild")
    channel = SimpleNamespace(id=2, name="general")
    author = SimpleNamespace(id=author_id, display_name=author_name)
    return SimpleNamespace(
        id=message_id,
        content=content,
        guild=guild,
        channel=channel,
        author=author,
        created_at=created_at or datetime(2026, 5, 31, tzinfo=UTC),
    )


class ConversationLogTest(unittest.TestCase):
    def test_observation_log_record_contains_minimal_message_context(self) -> None:
        bot_user = SimpleNamespace(id=999)
        message = fake_message(
            "こんにちは",
            message_id=99,
            author_name="alice",
            author_id=111,
        )

        record = observation_log_record(message, bot_user)

        self.assertEqual(
            record,
            {
                "timestamp": "2026-05-31T00:00:00+00:00",
                "guild_id": "1",
                "guild_name": "test-guild",
                "channel_id": "2",
                "channel_name": "general",
                "message_id": "99",
                "author_id": "111",
                "author_display_name": "alice",
                "clean_content": "こんにちは",
            },
        )

    def test_mention_log_record_includes_recent_context(self) -> None:
        bot_user = SimpleNamespace(id=999)
        recent_messages = [
            fake_message("前の話", message_id=101, author_name="bob", author_id=222),
            fake_message(
                "<@999> botの返事",
                message_id=102,
                author_name="bot",
                author_id=999,
            ),
        ]
        current_message = fake_message(
            "<@999> 今の話は？",
            message_id=103,
            author_name="alice",
            author_id=111,
        )

        record = mention_log_record(
            current_message,
            bot_user,
            "前の話です",
            recent_messages=recent_messages,
        )

        self.assertEqual(record["message_id"], "103")
        self.assertEqual(record["response_trigger"], "mention")
        self.assertEqual(record["clean_content"], "今の話は？")
        self.assertEqual(record["bot_reply"], "前の話です")
        self.assertEqual(
            record["recent_context"],
            [
                {
                    "timestamp": "2026-05-31T00:00:00+00:00",
                    "message_id": "101",
                    "author_id": "222",
                    "author_display_name": "bob",
                    "clean_content": "前の話",
                },
                {
                    "timestamp": "2026-05-31T00:00:00+00:00",
                    "message_id": "102",
                    "author_id": "999",
                    "author_display_name": "bot",
                    "clean_content": "botの返事",
                },
            ],
        )

    def test_mention_log_record_includes_compact_channel_summary(self) -> None:
        bot_user = SimpleNamespace(id=999)
        current_message = fake_message("<@999> 今の話は？", message_id=103)
        summary = {
            "created_at": "created",
            "channel_id": "2",
            "channel_name": "general",
            "record_count": 2,
            "first_observed_at": "first",
            "last_observed_at": "last",
            "model": "model",
            "summary": "summary",
            "context": "large context",
        }

        record = mention_log_record(
            current_message,
            bot_user,
            "前の話です",
            channel_summary=summary,
        )

        self.assertEqual(record["channel_summary"]["summary"], "summary")
        self.assertNotIn("context", record["channel_summary"])

    def test_mention_log_record_can_record_response_trigger(self) -> None:
        bot_user = SimpleNamespace(id=999)
        current_message = fake_message("はんなりどう思う？", message_id=103)

        record = mention_log_record(
            current_message,
            bot_user,
            "そうだね",
            response_trigger="wake_word",
        )

        self.assertEqual(record["response_trigger"], "wake_word")

    def test_mention_log_record_includes_letta_tool_events(self) -> None:
        bot_user = SimpleNamespace(id=999)
        current_message = fake_message("<@999> チャンネル一覧", message_id=103)
        events = [
            LettaToolEvent(
                kind="call",
                name="list_observed_discord_channels",
                arguments="{}",
            ),
            LettaToolEvent(
                kind="return",
                name="list_observed_discord_channels",
                status="success",
                text="#general: 1 observation",
            ),
        ]

        record = mention_log_record(
            current_message,
            bot_user,
            "一覧です",
            letta_tool_events=events,
        )

        self.assertEqual(
            record["letta_tool_events"],
            [
                {
                    "kind": "call",
                    "name": "list_observed_discord_channels",
                    "arguments": "{}",
                    "status": None,
                    "text_preview": None,
                },
                {
                    "kind": "return",
                    "name": "list_observed_discord_channels",
                    "arguments": None,
                    "status": "success",
                    "text_preview": "#general: 1 observation",
                },
            ],
        )

    def test_tool_event_log_record_truncates_return_text(self) -> None:
        event = LettaToolEvent(
            kind="return",
            name="tool",
            status="success",
            text="x" * 600,
        )

        record = tool_event_log_record(event)

        self.assertEqual(len(record["text_preview"]), 503)
        self.assertTrue(record["text_preview"].endswith("..."))


if __name__ == "__main__":
    unittest.main()
