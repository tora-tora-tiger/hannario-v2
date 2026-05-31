from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import discord

from channel_summaries import format_channel_summary_for_prompt


LOCAL_TIME_ZONE = ZoneInfo("Asia/Tokyo")


def clean_message_content(message: discord.Message, bot_user: discord.ClientUser) -> str:
    content = message.content
    mention_patterns = (
        f"<@{bot_user.id}>",
        f"<@!{bot_user.id}>",
    )

    for pattern in mention_patterns:
        content = content.replace(pattern, "")

    return " ".join(content.split())


def current_time_context(now: datetime | None = None) -> str:
    actual_now = now or datetime.now(UTC)
    if actual_now.tzinfo is None:
        actual_now = actual_now.replace(tzinfo=UTC)
    utc_now = actual_now.astimezone(UTC)
    local_now = actual_now.astimezone(LOCAL_TIME_ZONE)
    return "\n".join(
        [
            "current_time:",
            f"utc: {utc_now.isoformat()}",
            f"local: {local_now.isoformat()}",
            "local_timezone: Asia/Tokyo",
        ]
    )


def format_discord_message(
    message: discord.Message,
    bot_user: discord.ClientUser,
    recent_messages: Sequence[discord.Message] | None = None,
    channel_summary: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> str:
    channel_name = getattr(message.channel, "name", "direct-message")
    guild_name = message.guild.name if message.guild else "direct-message"
    clean_content = clean_message_content(message, bot_user)
    lines = [
        "Discord message",
        f"guild: {guild_name} ({message.guild.id if message.guild else 'dm'})",
        f"channel: {channel_name} ({message.channel.id})",
        "priority: Prefer current_message and recent_same_channel_context. Use supplemental summaries only as older background.",
        current_time_context(now),
    ]

    if recent_messages:
        lines.append("recent_same_channel_context_oldest_first:")
        for recent_message in recent_messages:
            recent_content = clean_message_content(recent_message, bot_user)
            if not recent_content:
                continue
            lines.append(
                "- "
                f"{recent_message.created_at.isoformat()} "
                f"{recent_message.author.display_name} "
                f"({recent_message.author.id}): "
                f"{recent_content}"
            )

    lines.extend(
        [
            "current_message:",
            f"author: {message.author.display_name} ({message.author.id})",
            f"content: {clean_content or message.content}",
        ]
    )

    summary_text = format_channel_summary_for_prompt(channel_summary)
    if summary_text is not None:
        lines.append(summary_text)

    return "\n".join(lines)
