import os
import unittest
from unittest.mock import patch

from bot import (
    DEFAULT_CONTEXT_MESSAGE_LIMIT,
    MAX_CONTEXT_MESSAGE_LIMIT,
    context_message_limit,
)


class ContextMessageLimitTest(unittest.TestCase):
    def test_default_context_limit(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(context_message_limit(), DEFAULT_CONTEXT_MESSAGE_LIMIT)

    def test_context_limit_can_be_disabled(self) -> None:
        with patch.dict(os.environ, {"DISCORD_CONTEXT_MESSAGE_LIMIT": "0"}):
            self.assertEqual(context_message_limit(), 0)

    def test_context_limit_is_capped(self) -> None:
        with patch.dict(os.environ, {"DISCORD_CONTEXT_MESSAGE_LIMIT": "999"}):
            self.assertEqual(context_message_limit(), MAX_CONTEXT_MESSAGE_LIMIT)

    def test_invalid_context_limit_uses_default(self) -> None:
        with (
            patch.dict(os.environ, {"DISCORD_CONTEXT_MESSAGE_LIMIT": "many"}),
            patch("bot.logging.warning"),
        ):
            self.assertEqual(context_message_limit(), DEFAULT_CONTEXT_MESSAGE_LIMIT)


if __name__ == "__main__":
    unittest.main()
