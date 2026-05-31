import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


DEFAULT_WAKE_WORDS = ("はんなり男", "はんなり")
DEFAULT_SILENCE_PHRASES = ("黙って", "消えて", "静かにして", "もういい", "呼んでない")
DEFAULT_ACTIVE_REPLY_WINDOW_SECONDS = 300
DEFAULT_SILENCE_SECONDS = 1800
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ResponsePolicyConfig:
    wake_words: tuple[str, ...] = DEFAULT_WAKE_WORDS
    silence_phrases: tuple[str, ...] = DEFAULT_SILENCE_PHRASES
    reply_trigger_enabled: bool = True
    wake_word_trigger_enabled: bool = True
    active_reply_enabled: bool = True
    silence_enabled: bool = True
    active_reply_window_seconds: int = DEFAULT_ACTIVE_REPLY_WINDOW_SECONDS
    silence_seconds: int = DEFAULT_SILENCE_SECONDS


@dataclass(frozen=True)
class ResponseDecision:
    should_respond: bool
    trigger: str = "none"


@dataclass
class ChannelConversationState:
    active_until: datetime | None = None
    silenced_until: datetime | None = None


ConversationStateStore = dict[str, ChannelConversationState]


def parse_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in TRUTHY_ENV_VALUES


def parse_positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return default

    if value <= 0:
        return default
    return value


def parse_wake_words(value: str | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_WAKE_WORDS
    return tuple(word.strip() for word in value.split(",") if word.strip())


def parse_silence_phrases(value: str | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_SILENCE_PHRASES
    return tuple(phrase.strip() for phrase in value.split(",") if phrase.strip())


def load_response_policy_config_from_env() -> ResponsePolicyConfig:
    return ResponsePolicyConfig(
        wake_words=parse_wake_words(os.getenv("DISCORD_WAKE_WORDS")),
        silence_phrases=parse_silence_phrases(os.getenv("DISCORD_SILENCE_PHRASES")),
        reply_trigger_enabled=parse_bool_env("DISCORD_REPLY_TRIGGER_ENABLED", True),
        wake_word_trigger_enabled=parse_bool_env("DISCORD_WAKE_WORD_TRIGGER_ENABLED", True),
        active_reply_enabled=parse_bool_env("DISCORD_ACTIVE_REPLY_ENABLED", True),
        silence_enabled=parse_bool_env("DISCORD_SILENCE_ENABLED", True),
        active_reply_window_seconds=parse_positive_int_env(
            "DISCORD_ACTIVE_REPLY_WINDOW_SECONDS",
            DEFAULT_ACTIVE_REPLY_WINDOW_SECONDS,
        ),
        silence_seconds=parse_positive_int_env("DISCORD_SILENCE_SECONDS", DEFAULT_SILENCE_SECONDS),
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


def contains_silence_phrase(content: str, silence_phrases: tuple[str, ...]) -> bool:
    normalized = content.casefold()
    return any(phrase.casefold() in normalized for phrase in silence_phrases)


def channel_key(message: Any) -> str:
    channel = getattr(message, "channel", None)
    return str(getattr(channel, "id", "unknown-channel"))


def current_time() -> datetime:
    return datetime.now(UTC)


def get_channel_state(
    state_store: ConversationStateStore,
    channel_id: str,
) -> ChannelConversationState:
    return state_store.setdefault(channel_id, ChannelConversationState())


def is_active(state: ChannelConversationState, now: datetime) -> bool:
    return state.active_until is not None and state.active_until > now


def is_silenced(state: ChannelConversationState, now: datetime) -> bool:
    return state.silenced_until is not None and state.silenced_until > now


def silence_channel(
    state_store: ConversationStateStore,
    channel_id: str,
    config: ResponsePolicyConfig,
    *,
    now: datetime | None = None,
) -> ChannelConversationState:
    actual_now = now or current_time()
    state = get_channel_state(state_store, channel_id)
    state.active_until = None
    state.silenced_until = actual_now + timedelta(seconds=config.silence_seconds)
    return state


def mark_channel_active(
    state_store: ConversationStateStore,
    channel_id: str,
    config: ResponsePolicyConfig,
    *,
    now: datetime | None = None,
) -> ChannelConversationState:
    actual_now = now or current_time()
    state = get_channel_state(state_store, channel_id)
    state.active_until = actual_now + timedelta(seconds=config.active_reply_window_seconds)
    return state


def decide_response(
    message: Any,
    bot_user: Any,
    config: ResponsePolicyConfig,
    state_store: ConversationStateStore | None = None,
    *,
    now: datetime | None = None,
) -> ResponseDecision:
    actual_now = now or current_time()
    content = getattr(message, "content", "")
    channel_id = channel_key(message)
    state = None
    if state_store is not None:
        state = get_channel_state(state_store, channel_id)

    if config.silence_enabled and contains_silence_phrase(content, config.silence_phrases):
        if state_store is not None:
            silence_channel(state_store, channel_id, config, now=actual_now)
        return ResponseDecision(False, "silenced")

    if state is not None and is_silenced(state, actual_now):
        return ResponseDecision(False, "silenced")

    if is_mentioned(message, bot_user):
        return ResponseDecision(True, "mention")

    if config.reply_trigger_enabled and is_resolved_reply_to_bot(message, bot_user):
        return ResponseDecision(True, "reply")

    if (
        config.wake_word_trigger_enabled
        and config.wake_words
        and contains_wake_word(content, config.wake_words)
    ):
        return ResponseDecision(True, "wake_word")

    if (
        config.active_reply_enabled
        and state is not None
        and is_active(state, actual_now)
    ):
        return ResponseDecision(True, "active")

    return ResponseDecision(False)
