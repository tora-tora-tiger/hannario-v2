import os
from dataclasses import dataclass
from typing import Any


DEFAULT_WAKE_WORDS = ("はんなり男", "ハンナ")
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ResponsePolicyConfig:
    wake_words: tuple[str, ...] = DEFAULT_WAKE_WORDS
    reply_trigger_enabled: bool = True
    wake_word_trigger_enabled: bool = True


@dataclass(frozen=True)
class ResponseDecision:
    should_respond: bool
    trigger: str = "none"


def parse_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in TRUTHY_ENV_VALUES


def parse_wake_words(value: str | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_WAKE_WORDS
    return tuple(word.strip() for word in value.split(",") if word.strip())


def load_response_policy_config_from_env() -> ResponsePolicyConfig:
    return ResponsePolicyConfig(
        wake_words=parse_wake_words(os.getenv("DISCORD_WAKE_WORDS")),
        reply_trigger_enabled=parse_bool_env("DISCORD_REPLY_TRIGGER_ENABLED", True),
        wake_word_trigger_enabled=parse_bool_env("DISCORD_WAKE_WORD_TRIGGER_ENABLED", True),
    )


def is_mentioned(message: Any, bot_user: Any) -> bool:
    return bot_user in getattr(message, "mentions", [])


def author_is_bot_user(author: Any, bot_user: Any) -> bool:
    return author == bot_user or str(getattr(author, "id", "")) == str(getattr(bot_user, "id", ""))


def is_resolved_reply_to_bot(message: Any, bot_user: Any) -> bool:
    reference = getattr(message, "reference", None)
    if reference is None:
        return False

    resolved = getattr(reference, "resolved", None)
    if resolved is None:
        return False

    author = getattr(resolved, "author", None)
    if author is None:
        return False

    return author_is_bot_user(author, bot_user)


def contains_wake_word(content: str, wake_words: tuple[str, ...]) -> bool:
    normalized = content.casefold()
    return any(word.casefold() in normalized for word in wake_words)


def decide_response(
    message: Any,
    bot_user: Any,
    config: ResponsePolicyConfig,
) -> ResponseDecision:
    if is_mentioned(message, bot_user):
        return ResponseDecision(True, "mention")

    if config.reply_trigger_enabled and is_resolved_reply_to_bot(message, bot_user):
        return ResponseDecision(True, "reply")

    content = getattr(message, "content", "")
    if (
        config.wake_word_trigger_enabled
        and config.wake_words
        and contains_wake_word(content, config.wake_words)
    ):
        return ResponseDecision(True, "wake_word")

    return ResponseDecision(False)
