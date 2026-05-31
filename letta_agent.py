from typing import Any

import discord
from letta_client import Letta, MessageCreate, TextContent

from discord_context import format_discord_message


def read_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        parts = [read_text(item) for item in value]
        text = "\n".join(part for part in parts if part)
        return text or None

    if isinstance(value, dict):
        for key in ("text", "content", "message"):
            text = read_text(value.get(key))
            if text:
                return text

    for attr in ("text", "content", "message"):
        if hasattr(value, attr):
            text = read_text(getattr(value, attr))
            if text:
                return text

    return None


def extract_assistant_text(response: Any) -> str | None:
    messages = getattr(response, "messages", None)
    if messages is None and isinstance(response, dict):
        messages = response.get("messages")

    if not messages:
        return read_text(response)

    for message in reversed(messages):
        role = getattr(message, "role", None)
        message_type = getattr(message, "message_type", None)
        if isinstance(message, dict):
            role = message.get("role")
            message_type = message.get("message_type")

        if role == "assistant" or message_type == "assistant_message":
            text = read_text(message)
            if text:
                return text

    return None


def ask_letta(
    client: Letta,
    agent_id: str,
    message: discord.Message,
    bot_user: discord.ClientUser,
) -> str:
    response = client.agents.messages.create(
        agent_id=agent_id,
        messages=[
            MessageCreate(
                role="user",
                content=[TextContent(text=format_discord_message(message, bot_user))],
            )
        ],
    )

    text = extract_assistant_text(response)
    if text is None:
        raise RuntimeError(f"Could not extract assistant text from {type(response)!r}")

    return text
