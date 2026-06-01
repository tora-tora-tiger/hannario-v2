import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import discord

from hannario.discord_context import clean_message_content
from hannario.channel_summaries import compact_summary_record


DEFAULT_LOG_PATH = Path("logs/discord_mentions.jsonl")
DEFAULT_OBSERVATION_LOG_PATH = Path("logs/discord_observations.jsonl")


def message_timestamp(message: discord.Message) -> str:
    return message.created_at.isoformat()


def context_log_record(
    message: discord.Message,
    bot_user: discord.ClientUser,
) -> dict[str, Any]:
    return {
        "timestamp": message_timestamp(message),
        "message_id": str(message.id),
        "author_id": str(message.author.id),
        "author_display_name": message.author.display_name,
        "clean_content": clean_message_content(message, bot_user),
    }


def tool_event_log_record(event: Any) -> dict[str, Any]:
    return {
        "kind": getattr(event, "kind", None),
        "name": getattr(event, "name", None),
        "arguments": getattr(event, "arguments", None),
        "status": getattr(event, "status", None),
        "text_preview": compact_tool_text(getattr(event, "text", None)),
    }


def compact_tool_text(value: Any, limit: int = 500) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def mention_log_record(
    message: discord.Message,
    bot_user: discord.ClientUser,
    bot_reply: str,
    recent_messages: Sequence[discord.Message] | None = None,
    channel_summary: dict[str, Any] | None = None,
    response_trigger: str = "mention",
    letta_tool_events: Sequence[Any] | None = None,
) -> dict[str, Any]:
    guild = message.guild
    channel_name = getattr(message.channel, "name", "direct-message")

    return {
        "timestamp": message_timestamp(message),
        "guild_id": str(guild.id) if guild else None,
        "guild_name": guild.name if guild else None,
        "channel_id": str(message.channel.id),
        "channel_name": channel_name,
        "message_id": str(message.id),
        "author_id": str(message.author.id),
        "author_display_name": message.author.display_name,
        "response_trigger": response_trigger,
        "clean_content": clean_message_content(message, bot_user),
        "recent_context": [
            context_log_record(recent_message, bot_user)
            for recent_message in recent_messages or []
        ],
        "channel_summary": compact_summary_record(channel_summary),
        "letta_tool_events": [
            tool_event_log_record(event) for event in letta_tool_events or []
        ],
        "bot_reply": bot_reply,
    }


def observation_log_record(
    message: discord.Message,
    bot_user: discord.ClientUser,
) -> dict[str, Any]:
    guild = message.guild
    channel_name = getattr(message.channel, "name", "direct-message")

    return {
        "timestamp": message_timestamp(message),
        "guild_id": str(guild.id) if guild else None,
        "guild_name": guild.name if guild else None,
        "channel_id": str(message.channel.id),
        "channel_name": channel_name,
        "message_id": str(message.id),
        "author_id": str(message.author.id),
        "author_display_name": message.author.display_name,
        "clean_content": clean_message_content(message, bot_user),
    }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        file.write("\n")


def log_mention_reply(
    message: discord.Message,
    bot_user: discord.ClientUser,
    bot_reply: str,
    *,
    recent_messages: Sequence[discord.Message] | None = None,
    channel_summary: dict[str, Any] | None = None,
    response_trigger: str = "mention",
    letta_tool_events: Sequence[Any] | None = None,
    path: Path = DEFAULT_LOG_PATH,
) -> None:
    append_jsonl(
        path,
        mention_log_record(
            message,
            bot_user,
            bot_reply,
            recent_messages=recent_messages,
            channel_summary=channel_summary,
            response_trigger=response_trigger,
            letta_tool_events=letta_tool_events,
        ),
    )


def log_observed_message(
    message: discord.Message,
    bot_user: discord.ClientUser,
    path: Path = DEFAULT_OBSERVATION_LOG_PATH,
) -> None:
    append_jsonl(path, observation_log_record(message, bot_user))
