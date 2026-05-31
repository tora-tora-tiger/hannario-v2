from collections.abc import Sequence

import discord


def clean_message_content(message: discord.Message, bot_user: discord.ClientUser) -> str:
    content = message.content
    mention_patterns = (
        f"<@{bot_user.id}>",
        f"<@!{bot_user.id}>",
    )

    for pattern in mention_patterns:
        content = content.replace(pattern, "")

    return " ".join(content.split())


def format_discord_message(
    message: discord.Message,
    bot_user: discord.ClientUser,
    recent_messages: Sequence[discord.Message] | None = None,
) -> str:
    channel_name = getattr(message.channel, "name", "direct-message")
    guild_name = message.guild.name if message.guild else "direct-message"
    clean_content = clean_message_content(message, bot_user)
    lines = [
        "Discord mention",
        f"guild: {guild_name} ({message.guild.id if message.guild else 'dm'})",
        f"channel: {channel_name} ({message.channel.id})",
    ]

    if recent_messages:
        lines.append("recent_channel_context_oldest_first:")
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

    return "\n".join(lines)
