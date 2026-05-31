import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from response_policy import (
    DEFAULT_WAKE_WORDS,
    ResponsePolicyConfig,
    contains_wake_word,
    decide_response,
    is_resolved_reply_to_bot,
    load_response_policy_config_from_env,
    parse_wake_words,
)


class ResponsePolicyTest(unittest.TestCase):
    def test_parse_wake_words_defaults_when_missing(self) -> None:
        self.assertEqual(parse_wake_words(None), DEFAULT_WAKE_WORDS)

    def test_parse_wake_words_splits_comma_separated_values(self) -> None:
        self.assertEqual(parse_wake_words("はんなり男, ハンナ,, bot"), ("はんなり男", "ハンナ", "bot"))

    def test_contains_wake_word(self) -> None:
        self.assertTrue(contains_wake_word("今日はハンナに聞きたい", ("ハンナ",)))
        self.assertFalse(contains_wake_word("普通の会話", ("ハンナ",)))

    def test_decide_response_prefers_mention(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = SimpleNamespace(
            mentions=[bot_user],
            reference=SimpleNamespace(resolved=SimpleNamespace(author=bot_user)),
            content="ハンナ",
        )

        decision = decide_response(message, bot_user, ResponsePolicyConfig())

        self.assertTrue(decision.should_respond)
        self.assertEqual(decision.trigger, "mention")

    def test_decide_response_to_resolved_reply(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = SimpleNamespace(
            mentions=[],
            reference=SimpleNamespace(resolved=SimpleNamespace(author=SimpleNamespace(id=1))),
            content="そうだね",
        )

        decision = decide_response(message, bot_user, ResponsePolicyConfig())

        self.assertTrue(decision.should_respond)
        self.assertEqual(decision.trigger, "reply")

    def test_decide_response_to_wake_word(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = SimpleNamespace(mentions=[], reference=None, content="はんなり男どう思う？")

        decision = decide_response(message, bot_user, ResponsePolicyConfig())

        self.assertTrue(decision.should_respond)
        self.assertEqual(decision.trigger, "wake_word")

    def test_decide_response_none(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = SimpleNamespace(mentions=[], reference=None, content="普通の会話")

        decision = decide_response(message, bot_user, ResponsePolicyConfig())

        self.assertFalse(decision.should_respond)
        self.assertEqual(decision.trigger, "none")

    def test_reply_trigger_can_be_disabled(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = SimpleNamespace(
            mentions=[],
            reference=SimpleNamespace(resolved=SimpleNamespace(author=bot_user)),
            content="そうだね",
        )

        decision = decide_response(
            message,
            bot_user,
            ResponsePolicyConfig(reply_trigger_enabled=False),
        )

        self.assertFalse(decision.should_respond)

    def test_wake_word_trigger_can_be_disabled(self) -> None:
        bot_user = SimpleNamespace(id=1)
        message = SimpleNamespace(mentions=[], reference=None, content="ハンナ")

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

    def test_load_response_policy_config_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DISCORD_WAKE_WORDS": "はんなり男,ハンナ",
                "DISCORD_REPLY_TRIGGER_ENABLED": "0",
                "DISCORD_WAKE_WORD_TRIGGER_ENABLED": "1",
            },
        ):
            config = load_response_policy_config_from_env()

        self.assertEqual(config.wake_words, ("はんなり男", "ハンナ"))
        self.assertFalse(config.reply_trigger_enabled)
        self.assertTrue(config.wake_word_trigger_enabled)


if __name__ == "__main__":
    unittest.main()
