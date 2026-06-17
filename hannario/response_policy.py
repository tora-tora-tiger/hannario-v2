import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


DEFAULT_WAKE_WORDS = ("はんなり男", "はんなり")
DEFAULT_SILENCE_PHRASES = ("黙って", "消えて", "静かにして", "もういい", "呼んでない")
DEFAULT_ACTIVE_REPLY_WINDOW_SECONDS = 300
DEFAULT_ACTIVE_REPLY_COOLDOWN_SECONDS = 60
DEFAULT_SILENCE_SECONDS = 1800
DEFAULT_RANDOM_REPLY_RATE = 0.1
DEFAULT_RANDOM_REPLY_COOLDOWN_SECONDS = 900
DEFAULT_RANDOM_REPLY_MIN_CHARS = 6
DEFAULT_NON_EXPLICIT_REPLY_REPEATED_CONTENT_LIMIT = 1
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ResponsePolicyConfig:
    wake_words: tuple[str, ...] = DEFAULT_WAKE_WORDS
    silence_phrases: tuple[str, ...] = DEFAULT_SILENCE_PHRASES
    blocked_category_ids: tuple[str, ...] = ()
    blocked_category_names: tuple[str, ...] = ()
    reply_trigger_enabled: bool = True
    wake_word_trigger_enabled: bool = True
    active_reply_enabled: bool = True
    silence_enabled: bool = True
    random_reply_enabled: bool = False
    active_reply_window_seconds: int = DEFAULT_ACTIVE_REPLY_WINDOW_SECONDS
    active_reply_cooldown_seconds: int = DEFAULT_ACTIVE_REPLY_COOLDOWN_SECONDS
    silence_seconds: int = DEFAULT_SILENCE_SECONDS
    random_reply_rate: float = DEFAULT_RANDOM_REPLY_RATE
    random_reply_cooldown_seconds: int = DEFAULT_RANDOM_REPLY_COOLDOWN_SECONDS
    random_reply_min_chars: int = DEFAULT_RANDOM_REPLY_MIN_CHARS
    non_explicit_reply_repeated_content_limit: int = (
        DEFAULT_NON_EXPLICIT_REPLY_REPEATED_CONTENT_LIMIT
    )


@dataclass(frozen=True)
class ResponseDecision:
    should_respond: bool
    trigger: str = "none"


@dataclass
class ChannelConversationState:
    active_until: datetime | None = None
    active_cooldown_until: datetime | None = None
    silenced_until: datetime | None = None
    random_cooldown_until: datetime | None = None
    last_non_explicit_candidate_content: str = ""
    repeated_non_explicit_candidate_count: int = 0


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


def parse_probability_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = float(raw_value)
    except ValueError:
        return default

    return max(0.0, min(value, 1.0))


def parse_wake_words(value: str | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_WAKE_WORDS
    return tuple(word.strip() for word in value.split(",") if word.strip())


def parse_silence_phrases(value: str | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_SILENCE_PHRASES
    return tuple(phrase.strip() for phrase in value.split(",") if phrase.strip())


def parse_csv_values(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def load_response_policy_config_from_env() -> ResponsePolicyConfig:
    return ResponsePolicyConfig(
        wake_words=parse_wake_words(os.getenv("DISCORD_WAKE_WORDS")),
        silence_phrases=parse_silence_phrases(os.getenv("DISCORD_SILENCE_PHRASES")),
        blocked_category_ids=parse_csv_values(os.getenv("DISCORD_RESPONSE_BLOCKED_CATEGORY_IDS")),
        blocked_category_names=parse_csv_values(
            os.getenv("DISCORD_RESPONSE_BLOCKED_CATEGORY_NAMES")
        ),
        reply_trigger_enabled=parse_bool_env("DISCORD_REPLY_TRIGGER_ENABLED", True),
        wake_word_trigger_enabled=parse_bool_env("DISCORD_WAKE_WORD_TRIGGER_ENABLED", True),
        active_reply_enabled=parse_bool_env("DISCORD_ACTIVE_REPLY_ENABLED", True),
        silence_enabled=parse_bool_env("DISCORD_SILENCE_ENABLED", True),
        random_reply_enabled=parse_bool_env("DISCORD_RANDOM_REPLY_ENABLED", False),
        active_reply_window_seconds=parse_positive_int_env(
            "DISCORD_ACTIVE_REPLY_WINDOW_SECONDS",
            DEFAULT_ACTIVE_REPLY_WINDOW_SECONDS,
        ),
        active_reply_cooldown_seconds=parse_positive_int_env(
            "DISCORD_ACTIVE_REPLY_COOLDOWN_SECONDS",
            DEFAULT_ACTIVE_REPLY_COOLDOWN_SECONDS,
        ),
        silence_seconds=parse_positive_int_env("DISCORD_SILENCE_SECONDS", DEFAULT_SILENCE_SECONDS),
        random_reply_rate=parse_probability_env(
            "DISCORD_RANDOM_REPLY_RATE",
            DEFAULT_RANDOM_REPLY_RATE,
        ),
        random_reply_cooldown_seconds=parse_positive_int_env(
            "DISCORD_RANDOM_REPLY_COOLDOWN_SECONDS",
            DEFAULT_RANDOM_REPLY_COOLDOWN_SECONDS,
        ),
        random_reply_min_chars=parse_positive_int_env(
            "DISCORD_RANDOM_REPLY_MIN_CHARS",
            DEFAULT_RANDOM_REPLY_MIN_CHARS,
        ),
        non_explicit_reply_repeated_content_limit=parse_positive_int_env(
            "DISCORD_NON_EXPLICIT_REPLY_REPEATED_CONTENT_LIMIT",
            parse_positive_int_env(
                "DISCORD_RANDOM_REPLY_REPEATED_CONTENT_LIMIT",
                DEFAULT_NON_EXPLICIT_REPLY_REPEATED_CONTENT_LIMIT,
            ),
        ),
    )


def exceeds_non_explicit_repeated_content_limit(
    state: ChannelConversationState,
    content: str,
    config: ResponsePolicyConfig,
) -> bool:
    repeated_count = mark_non_explicit_candidate_content(state, content)
    return repeated_count > config.non_explicit_reply_repeated_content_limit


def normalize_non_explicit_candidate_content(content: str) -> str:
    return " ".join(content.casefold().split())


def mark_non_explicit_candidate_content(
    state: ChannelConversationState,
    content: str,
) -> int:
    normalized = normalize_non_explicit_candidate_content(content)
    if normalized and normalized == state.last_non_explicit_candidate_content:
        state.repeated_non_explicit_candidate_count += 1
    else:
        state.last_non_explicit_candidate_content = normalized
        state.repeated_non_explicit_candidate_count = 1 if normalized else 0
    return state.repeated_non_explicit_candidate_count


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


def message_category_id(message: Any) -> str:
    channel = getattr(message, "channel", None)
    category_id = getattr(channel, "category_id", None)
    if category_id is not None:
        return str(category_id)

    category = getattr(channel, "category", None)
    category_id = getattr(category, "id", None)
    if category_id is not None:
        return str(category_id)

    parent = getattr(channel, "parent", None)
    parent_category_id = getattr(parent, "category_id", None)
    if parent_category_id is not None:
        return str(parent_category_id)

    parent_category = getattr(parent, "category", None)
    parent_category_id = getattr(parent_category, "id", None)
    if parent_category_id is not None:
        return str(parent_category_id)

    return ""


def message_category_name(message: Any) -> str:
    channel = getattr(message, "channel", None)
    category = getattr(channel, "category", None)
    category_name = getattr(category, "name", None)
    if category_name:
        return str(category_name)

    parent = getattr(channel, "parent", None)
    parent_category = getattr(parent, "category", None)
    parent_category_name = getattr(parent_category, "name", None)
    if parent_category_name:
        return str(parent_category_name)

    return ""


def is_blocked_category(message: Any, config: ResponsePolicyConfig) -> bool:
    category_id = message_category_id(message)
    if category_id and category_id in config.blocked_category_ids:
        return True

    category_name = message_category_name(message).casefold()
    blocked_category_names = {name.casefold() for name in config.blocked_category_names}
    return bool(category_name and category_name in blocked_category_names)


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


def is_active_on_cooldown(state: ChannelConversationState, now: datetime) -> bool:
    return state.active_cooldown_until is not None and state.active_cooldown_until > now


def is_silenced(state: ChannelConversationState, now: datetime) -> bool:
    return state.silenced_until is not None and state.silenced_until > now


def is_random_on_cooldown(state: ChannelConversationState, now: datetime) -> bool:
    return state.random_cooldown_until is not None and state.random_cooldown_until > now


def is_random_eligible_content(content: str, config: ResponsePolicyConfig) -> bool:
    stripped = content.strip()
    if len(stripped) < config.random_reply_min_chars:
        return False
    if stripped.startswith("!"):
        return False
    return True


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
    state.active_cooldown_until = actual_now + timedelta(
        seconds=config.active_reply_cooldown_seconds,
    )
    return state


def mark_random_cooldown(
    state_store: ConversationStateStore,
    channel_id: str,
    config: ResponsePolicyConfig,
    *,
    now: datetime | None = None,
) -> ChannelConversationState:
    actual_now = now or current_time()
    state = get_channel_state(state_store, channel_id)
    state.random_cooldown_until = actual_now + timedelta(
        seconds=config.random_reply_cooldown_seconds,
    )
    return state


def decide_response(
    message: Any,
    bot_user: Any,
    config: ResponsePolicyConfig,
    state_store: ConversationStateStore | None = None,
    *,
    now: datetime | None = None,
    random_value: float | None = None,
) -> ResponseDecision:
    actual_now = now or current_time()
    content = getattr(message, "content", "")
    channel_id = channel_key(message)
    state = None
    if state_store is not None:
        state = get_channel_state(state_store, channel_id)

    if is_blocked_category(message, config):
        return ResponseDecision(False, "category_blocked")

    if config.silence_enabled and contains_silence_phrase(content, config.silence_phrases):
        if state_store is not None:
            silence_channel(state_store, channel_id, config, now=actual_now)
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

    if state is not None and is_silenced(state, actual_now):
        return ResponseDecision(False, "silenced")

    if (
        config.active_reply_enabled
        and state is not None
        and is_active(state, actual_now)
    ):
        if is_active_on_cooldown(state, actual_now):
            return ResponseDecision(False, "active_cooldown")
        if exceeds_non_explicit_repeated_content_limit(state, content, config):
            return ResponseDecision(False, "active_repeated_content")
        return ResponseDecision(True, "active")

    if (
        config.random_reply_enabled
        and state_store is not None
        and state is not None
        and not is_random_on_cooldown(state, actual_now)
        and is_random_eligible_content(content, config)
    ):
        if exceeds_non_explicit_repeated_content_limit(state, content, config):
            return ResponseDecision(False, "random_repeated_content")

        actual_random_value = 1.0 if random_value is None else random_value
        if actual_random_value < config.random_reply_rate:
            mark_random_cooldown(state_store, channel_id, config, now=actual_now)
            return ResponseDecision(True, "random")

    return ResponseDecision(False)
