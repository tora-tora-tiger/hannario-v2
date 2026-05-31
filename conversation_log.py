import json
from pathlib import Path
from typing import Any

import discord

from discord_context import clean_message_content


DEFAULT_LOG_PATH = Path("logs/discord_mentions.jsonl")


def message_timestamp(message: discord.Message) -> str:
    return message.created_at.isoformat()


def mention_log_record(
    message: discord.Message,
    bot_user: discord.ClientUser,
    bot_reply: str,
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
        "bot_reply": bot_reply,
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
    path: Path = DEFAULT_LOG_PATH,
) -> None:
    append_jsonl(path, mention_log_record(message, bot_user, bot_reply))
