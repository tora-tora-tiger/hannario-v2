import asyncio
import logging
import os
from typing import Any

import discord
from dotenv import load_dotenv
from letta_client import Letta

from auto_channel_summary import (
    AutoSummaryConfig,
    load_auto_summary_config_from_env,
    run_auto_channel_summaries_once,
)
from channel_summaries import read_latest_channel_summary
from conversation_log import log_mention_reply, log_observed_message
from letta_agent import LettaToolEvent, ask_letta_with_diagnostics


COMMAND_PREFIX = "!"
DEFAULT_LETTA_BASE_URL = "http://localhost:8283"
DEFAULT_CONTEXT_MESSAGE_LIMIT = 5
MAX_CONTEXT_MESSAGE_LIMIT = 20
LETTA_ERROR_REPLY = "ごめん、今ちょっと考える側につながらない。"
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


def should_ignore_message(message: discord.Message, bot_user: discord.ClientUser) -> bool:
    return message.author == bot_user or message.author.bot


def is_ping_command(message: discord.Message) -> bool:
    return message.content.strip() == f"{COMMAND_PREFIX}ping"


def is_mentioned(message: discord.Message, bot_user: discord.ClientUser) -> bool:
    return bot_user in message.mentions


def context_message_limit() -> int:
    raw_value = os.getenv("DISCORD_CONTEXT_MESSAGE_LIMIT")
    if raw_value is None:
        return DEFAULT_CONTEXT_MESSAGE_LIMIT

    try:
        value = int(raw_value)
    except ValueError:
        logging.warning(
            "Invalid DISCORD_CONTEXT_MESSAGE_LIMIT=%r; using %d",
            raw_value,
            DEFAULT_CONTEXT_MESSAGE_LIMIT,
        )
        return DEFAULT_CONTEXT_MESSAGE_LIMIT

    return max(0, min(value, MAX_CONTEXT_MESSAGE_LIMIT))


def include_channel_summary() -> bool:
    return os.getenv("DISCORD_INCLUDE_CHANNEL_SUMMARY", "").strip().lower() in TRUTHY_ENV_VALUES


def truncate_log_text(value: str | None, limit: int = 240) -> str:
    if value is None:
        return ""
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def log_letta_tool_events(discord_message_id: int, events: list[LettaToolEvent]) -> None:
    for event in events:
        if event.kind == "call":
            logging.info(
                "Letta tool call for Discord message %s: %s args=%s",
                discord_message_id,
                event.name,
                truncate_log_text(event.arguments),
            )
        elif event.kind == "return":
            logging.info(
                "Letta tool return for Discord message %s: %s status=%s chars=%d preview=%s",
                discord_message_id,
                event.name,
                event.status,
                len(event.text or ""),
                truncate_log_text(event.text),
            )


async def fetch_recent_channel_messages(
    message: discord.Message,
    limit: int,
) -> list[discord.Message]:
    if limit <= 0:
        return []

    history = getattr(message.channel, "history", None)
    if history is None:
        return []

    try:
        messages = [
            prior_message
            async for prior_message in history(
                limit=limit,
                before=message,
                oldest_first=False,
            )
            if prior_message.content.strip()
        ]
    except (discord.Forbidden, discord.HTTPException):
        logging.warning(
            "Could not fetch recent messages for channel %s",
            message.channel.id,
            exc_info=True,
        )
        return []

    messages.reverse()
    return messages


class HannarioClient(discord.Client):
    def __init__(
        self,
        *,
        letta_client: Letta,
        letta_agent_id: str | None,
        auto_summary_config: AutoSummaryConfig,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.letta_client = letta_client
        self.letta_agent_id = letta_agent_id
        self.auto_summary_config = auto_summary_config
        self.auto_summary_task: asyncio.Task[None] | None = None

    async def on_ready(self) -> None:
        if self.user is None:
            return

        logging.info("Logged in as %s (id=%s)", self.user, self.user.id)
        self.start_auto_summary_task()

    def start_auto_summary_task(self) -> None:
        if not self.auto_summary_config.enabled:
            return
        if self.auto_summary_task is not None and not self.auto_summary_task.done():
            return

        self.auto_summary_task = asyncio.create_task(
            run_auto_summary_loop(self.auto_summary_config),
        )
        logging.info(
            "Started Discord auto summary task: interval=%ds limit=%d min_new_messages=%d",
            self.auto_summary_config.interval_seconds,
            self.auto_summary_config.limit,
            self.auto_summary_config.min_new_messages,
        )

    async def on_message(self, message: discord.Message) -> None:
        if self.user is None:
            return

        if should_ignore_message(message, self.user):
            return

        if not is_mentioned(message, self.user):
            await asyncio.to_thread(log_observed_message, message, self.user)
            if is_ping_command(message):
                await message.channel.send("pong")
            return

        channel_name = getattr(message.channel, "name", "direct-message")
        logging.info(
            "Received mention from %s (%s) in #%s (%s)",
            message.author.display_name,
            message.author.id,
            channel_name,
            message.channel.id,
        )

        if self.letta_agent_id is None:
            logging.warning("Cannot reply because LETTA_AGENT_ID is not set")
            await message.reply("LETTA_AGENT_ID がまだ設定されていません。", mention_author=False)
            return

        recent_messages = await fetch_recent_channel_messages(
            message,
            context_message_limit(),
        )
        if recent_messages:
            logging.info(
                "Including %d recent channel messages for Discord message %s",
                len(recent_messages),
                message.id,
            )

        channel_summary = None
        if include_channel_summary():
            channel_summary = await asyncio.to_thread(
                read_latest_channel_summary,
                str(message.channel.id),
            )
            if channel_summary is None:
                logging.info("No saved channel summary found for channel %s", message.channel.id)
            else:
                logging.info(
                    "Including channel summary created at %s for Discord message %s",
                    channel_summary.get("created_at"),
                    message.id,
                )

        async with message.channel.typing():
            try:
                letta_reply = await asyncio.wait_for(
                    asyncio.to_thread(
                        ask_letta_with_diagnostics,
                        self.letta_client,
                        self.letta_agent_id,
                        message,
                        self.user,
                        recent_messages,
                        channel_summary,
                    ),
                    timeout=45,
                )
            except Exception:
                logging.exception("Failed to get Letta reply")
                reply = LETTA_ERROR_REPLY
            else:
                reply = letta_reply.text
                log_letta_tool_events(message.id, letta_reply.tool_events)
                logging.info(
                    "Received Letta reply for Discord message %s (%d chars)",
                    message.id,
                    len(reply),
                )

        await message.reply(reply, mention_author=False)
        await asyncio.to_thread(
            log_mention_reply,
            message,
            self.user,
            reply,
            recent_messages=recent_messages,
            channel_summary=channel_summary,
        )


async def run_auto_summary_loop(config: AutoSummaryConfig) -> None:
    while True:
        try:
            result = await asyncio.to_thread(run_auto_channel_summaries_once, config)
        except Exception:
            logging.exception("Discord auto summary run failed")
        else:
            if result.summarized or result.errors:
                logging.info(
                    "Discord auto summary run completed: summarized=%d skipped=%d errors=%d",
                    result.summarized,
                    result.skipped,
                    result.errors,
                )

        await asyncio.sleep(config.interval_seconds)


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Missing DISCORD_TOKEN. Create .env from .env.example.")

    intents = discord.Intents.default()
    intents.message_content = True

    letta_client = Letta(base_url=os.getenv("LETTA_BASE_URL", DEFAULT_LETTA_BASE_URL))
    letta_agent_id = os.getenv("LETTA_AGENT_ID")
    auto_summary_config = load_auto_summary_config_from_env()

    client = HannarioClient(
        intents=intents,
        letta_client=letta_client,
        letta_agent_id=letta_agent_id,
        auto_summary_config=auto_summary_config,
    )
    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
