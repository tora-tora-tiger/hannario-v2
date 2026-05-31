import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from response_policy import (
    ChannelConversationState,
    DEFAULT_WAKE_WORDS,
    ResponsePolicyConfig,
    contains_wake_word,
    decide_response,
    is_active,
    is_silenced,
    is_resolved_reply_to_bot,
    load_response_policy_config_from_env,
    mark_channel_active,
    parse_wake_words,
    silence_channel,
)


class ResponsePolicyTest(unittest.TestCase):
    def message(self, content: str, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            mentions=kwargs.get("mentions", []),
            reference=kwargs.get("reference"),
            content=content,
            channel=SimpleNamespace(id=kwargs.get("channel_id", 123)),
        )

    def test_parse_wake_words_defaults_when_missing(self) -> None:
        self.assertEqual(parse_wake_words(None), DEFAULT_WAKE_WORDS)

    def test_parse_wake_words_splits_comma_separated_values(self) -> None:
        self.assertEqual(parse_wake_words("はんなり男, はんなり,, bot"), ("はんなり男", "はんなり", "bot"))

    def test_contains_wake_word(self) -> None:
        self.assertTrue(contains_wake_word("今日ははんなりに聞きたい", ("はんなり",)))
        self.assertFalse(contains_wake_word("普通の会話", ("はんなり",)))

    def test_decide_response_prefers_mention(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = self.message(
            "はんなり",
            mentions=[bot_user],
            reference=SimpleNamespace(resolved=SimpleNamespace(author=bot_user)),
        )

        decision = decide_response(message, bot_user, ResponsePolicyConfig())

        self.assertTrue(decision.should_respond)
        self.assertEqual(decision.trigger, "mention")

    def test_decide_response_to_resolved_reply(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = self.message(
            "そうだね",
            mentions=[],
            reference=SimpleNamespace(resolved=SimpleNamespace(author=SimpleNamespace(id=1))),
        )

        decision = decide_response(message, bot_user, ResponsePolicyConfig())

        self.assertTrue(decision.should_respond)
        self.assertEqual(decision.trigger, "reply")

    def test_decide_response_to_wake_word(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = self.message("はんなり男どう思う？")

        decision = decide_response(message, bot_user, ResponsePolicyConfig())

        self.assertTrue(decision.should_respond)
        self.assertEqual(decision.trigger, "wake_word")

    def test_decide_response_none(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = self.message("普通の会話")

        decision = decide_response(message, bot_user, ResponsePolicyConfig())

        self.assertFalse(decision.should_respond)
        self.assertEqual(decision.trigger, "none")

    def test_reply_trigger_can_be_disabled(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = self.message(
            "そうだね",
            mentions=[],
            reference=SimpleNamespace(resolved=SimpleNamespace(author=bot_user)),
        )

        decision = decide_response(
            message,
            bot_user,
            ResponsePolicyConfig(reply_trigger_enabled=False),
        )

        self.assertFalse(decision.should_respond)

    def test_wake_word_trigger_can_be_disabled(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = self.message("はんなり")

        decision = decide_response(
            message,
            bot_user,
            ResponsePolicyConfig(wake_word_trigger_enabled=False),
        )

        self.assertFalse(decision.should_respond)

    def test_is_resolved_reply_to_bot(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = SimpleNamespace(
            reference=SimpleNamespace(resolved=SimpleNamespace(author=SimpleNamespace(id=1))),
        )

        self.assertTrue(is_resolved_reply_to_bot(message, bot_user))

    def test_decide_response_when_channel_is_active(self) -> None:
        now = datetime(2026, 5, 31, tzinfo=UTC)
        bot_user = SimpleNamespace(id=1)
        state_store = {
            "123": ChannelConversationState(active_until=now + timedelta(seconds=60)),
        }
        message = self.message("それで？")

        decision = decide_response(
            message,
            bot_user,
            ResponsePolicyConfig(),
            state_store,
            now=now,
        )

        self.assertTrue(decision.should_respond)
        self.assertEqual(decision.trigger, "active")

    def test_decide_response_when_channel_active_expired(self) -> None:
        now = datetime(2026, 5, 31, tzinfo=UTC)
        bot_user = SimpleNamespace(id=1)
        state_store = {
            "123": ChannelConversationState(active_until=now - timedelta(seconds=1)),
        }
        message = self.message("それで？")

        decision = decide_response(
            message,
            bot_user,
            ResponsePolicyConfig(),
            state_store,
            now=now,
        )

        self.assertFalse(decision.should_respond)
        self.assertEqual(decision.trigger, "none")

    def test_silence_phrase_updates_state_and_blocks_response(self) -> None:
        now = datetime(2026, 5, 31, tzinfo=UTC)
        bot_user = SimpleNamespace(id=1)
        state_store: dict[str, ChannelConversationState] = {}
        message = self.message("もういい、黙って")

        decision = decide_response(
            message,
            bot_user,
            ResponsePolicyConfig(silence_seconds=60),
            state_store,
            now=now,
        )

        self.assertFalse(decision.should_respond)
        self.assertEqual(decision.trigger, "silenced")
        self.assertTrue(is_silenced(state_store["123"], now + timedelta(seconds=30)))
        self.assertFalse(is_silenced(state_store["123"], now + timedelta(seconds=61)))

    def test_silenced_channel_blocks_even_mention(self) -> None:
        now = datetime(2026, 5, 31, tzinfo=UTC)
        bot_user = SimpleNamespace(id=1)
        state_store = {
            "123": ChannelConversationState(silenced_until=now + timedelta(seconds=60)),
        }
        message = self.message("呼んだよ", mentions=[bot_user])

        decision = decide_response(
            message,
            bot_user,
            ResponsePolicyConfig(),
            state_store,
            now=now,
        )

        self.assertFalse(decision.should_respond)
        self.assertEqual(decision.trigger, "silenced")

    def test_mark_channel_active(self) -> None:
        now = datetime(2026, 5, 31, tzinfo=UTC)
        state_store: dict[str, ChannelConversationState] = {}

        state = mark_channel_active(
            state_store,
            "123",
            ResponsePolicyConfig(active_reply_window_seconds=60),
            now=now,
        )

        self.assertTrue(is_active(state, now + timedelta(seconds=30)))
        self.assertFalse(is_active(state, now + timedelta(seconds=61)))

    def test_silence_channel_clears_active_state(self) -> None:
        now = datetime(2026, 5, 31, tzinfo=UTC)
        state_store = {
            "123": ChannelConversationState(active_until=now + timedelta(seconds=60)),
        }

        state = silence_channel(
            state_store,
            "123",
            ResponsePolicyConfig(silence_seconds=60),
            now=now,
        )

        self.assertIsNone(state.active_until)
        self.assertTrue(is_silenced(state, now + timedelta(seconds=30)))

    def test_load_response_policy_config_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DISCORD_WAKE_WORDS": "はんなり男,はんなり",
                "DISCORD_SILENCE_PHRASES": "黙って,消えて",
                "DISCORD_REPLY_TRIGGER_ENABLED": "0",
                "DISCORD_WAKE_WORD_TRIGGER_ENABLED": "1",
                "DISCORD_ACTIVE_REPLY_ENABLED": "1",
                "DISCORD_SILENCE_ENABLED": "1",
                "DISCORD_ACTIVE_REPLY_WINDOW_SECONDS": "120",
                "DISCORD_SILENCE_SECONDS": "600",
            },
        ):
            config = load_response_policy_config_from_env()

        self.assertEqual(config.wake_words, ("はんなり男", "はんなり"))
        self.assertEqual(config.silence_phrases, ("黙って", "消えて"))
        self.assertFalse(config.reply_trigger_enabled)
        self.assertTrue(config.wake_word_trigger_enabled)
        self.assertTrue(config.active_reply_enabled)
        self.assertTrue(config.silence_enabled)
        self.assertEqual(config.active_reply_window_seconds, 120)
        self.assertEqual(config.silence_seconds, 600)


if __name__ == "__main__":
    unittest.main()
