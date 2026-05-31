import asyncio
import logging
import os
import random
from datetime import UTC, datetime
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
from heartbeat import (
    HeartbeatConfig,
    HeartbeatPostDecision,
    append_heartbeat_log,
    decide_heartbeat_post,
    load_heartbeat_config_from_env,
    record_heartbeat_post,
    run_heartbeat_once,
)
from letta_agent import LettaToolEvent, ask_letta_with_diagnostics
from memory_audit import audit_memory_write_events, has_memory_write_tool_call
from response_policy import (
    ConversationStateStore,
    ResponseDecision,
    ResponsePolicyConfig,
    author_is_bot_user,
    channel_key,
    decide_response,
    load_response_policy_config_from_env,
    mark_channel_active,
)


COMMAND_PREFIX = "!"
DEFAULT_LETTA_BASE_URL = "http://localhost:8283"
DEFAULT_CONTEXT_MESSAGE_LIMIT = 5
MAX_CONTEXT_MESSAGE_LIMIT = 20
DEFAULT_CHANNEL_SUMMARY_MAX_AGE_SECONDS = 3600
LETTA_ERROR_REPLY = "ごめん、今ちょっと考える側につながらない。"
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


def should_ignore_message(message: discord.Message, bot_user: discord.ClientUser) -> bool:
    return message.author == bot_user or message.author.bot


def is_ping_command(message: discord.Message) -> bool:
    return message.content.strip() == f"{COMMAND_PREFIX}ping"


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


def channel_summary_max_age_seconds() -> int:
    raw_value = os.getenv("DISCORD_CHANNEL_SUMMARY_MAX_AGE_SECONDS")
    if raw_value is None:
        return DEFAULT_CHANNEL_SUMMARY_MAX_AGE_SECONDS

    try:
        value = int(raw_value)
    except ValueError:
        logging.warning(
            "Invalid DISCORD_CHANNEL_SUMMARY_MAX_AGE_SECONDS=%r; using %d",
            raw_value,
            DEFAULT_CHANNEL_SUMMARY_MAX_AGE_SECONDS,
        )
        return DEFAULT_CHANNEL_SUMMARY_MAX_AGE_SECONDS

    if value <= 0:
        logging.warning(
            "Invalid DISCORD_CHANNEL_SUMMARY_MAX_AGE_SECONDS=%r; using %d",
            raw_value,
            DEFAULT_CHANNEL_SUMMARY_MAX_AGE_SECONDS,
        )
        return DEFAULT_CHANNEL_SUMMARY_MAX_AGE_SECONDS

    return value


def is_channel_summary_fresh(
    channel_summary: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    created_at = channel_summary.get("created_at")
    if not isinstance(created_at, str):
        return False

    try:
        created_datetime = datetime.fromisoformat(created_at)
    except ValueError:
        return False

    if created_datetime.tzinfo is None:
        created_datetime = created_datetime.replace(tzinfo=UTC)

    actual_now = now or datetime.now(UTC)
    if actual_now.tzinfo is None:
        actual_now = actual_now.replace(tzinfo=UTC)

    age_seconds = (actual_now.astimezone(UTC) - created_datetime.astimezone(UTC)).total_seconds()
    return age_seconds <= channel_summary_max_age_seconds()


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
            if has_memory_write_tool_call([event]):
                logging.warning(
                    "Letta memory write tool call for Discord message %s: %s args=%s",
                    discord_message_id,
                    event.name,
                    truncate_log_text(event.arguments),
                )
            else:
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


def audit_letta_memory_writes(
    letta_client: Letta,
    letta_agent_id: str,
    discord_message_id: int,
    events: list[LettaToolEvent],
) -> None:
    record = audit_memory_write_events(
        letta_client,
        letta_agent_id,
        discord_message_id,
        events,
    )
    if record is None:
        return

    logging.warning(
        "Saved Letta memory write audit for Discord message %s: snapshot=%s tools=%s",
        discord_message_id,
        record.get("snapshot_path"),
        ", ".join(tool["name"] for tool in record.get("memory_write_tools", [])),
    )

    diff_text = record.get("diff") or ""
    if diff_text:
        logging.warning(
            "Letta memory diff after Discord message %s:\n%s",
            discord_message_id,
            truncate_log_text(diff_text, limit=2000),
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


async def fetch_referenced_message(message: discord.Message) -> discord.Message | None:
    reference = getattr(message, "reference", None)
    if reference is None or getattr(reference, "resolved", None) is not None:
        return None

    message_id = getattr(reference, "message_id", None)
    if message_id is None:
        return None

    fetch_message = getattr(message.channel, "fetch_message", None)
    if fetch_message is None:
        return None

    try:
        return await fetch_message(message_id)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        logging.warning(
            "Could not fetch referenced message %s in channel %s",
            message_id,
            message.channel.id,
            exc_info=True,
        )
        return None


async def decide_response_for_message(
    message: discord.Message,
    bot_user: discord.ClientUser,
    config: ResponsePolicyConfig,
    conversation_states: ConversationStateStore,
) -> ResponseDecision:
    decision = decide_response(
        message,
        bot_user,
        config,
        conversation_states,
        random_value=random.random(),
    )
    if decision.should_respond or not config.reply_trigger_enabled:
        return decision

    referenced_message = await fetch_referenced_message(message)
    if referenced_message is None:
        return decision

    if author_is_bot_user(referenced_message.author, bot_user):
        return ResponseDecision(True, "reply")

    return decision


class HannarioClient(discord.Client):
    def __init__(
        self,
        *,
        letta_client: Letta,
        letta_agent_id: str | None,
        auto_summary_config: AutoSummaryConfig,
        heartbeat_config: HeartbeatConfig,
        response_policy_config: ResponsePolicyConfig,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.letta_client = letta_client
        self.letta_agent_id = letta_agent_id
        self.auto_summary_config = auto_summary_config
        self.heartbeat_config = heartbeat_config
        self.response_policy_config = response_policy_config
        self.conversation_states: ConversationStateStore = {}
        self.heartbeat_post_times: dict[str, datetime] = {}
        self.auto_summary_task: asyncio.Task[None] | None = None
        self.heartbeat_task: asyncio.Task[None] | None = None

    async def on_ready(self) -> None:
        if self.user is None:
            return

        logging.info("Logged in as %s (id=%s)", self.user, self.user.id)
        self.start_auto_summary_task()
        self.start_heartbeat_task()

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

    def start_heartbeat_task(self) -> None:
        if not self.heartbeat_config.enabled:
            return
        if self.heartbeat_task is not None and not self.heartbeat_task.done():
            return

        self.heartbeat_task = asyncio.create_task(
            run_heartbeat_loop(
                self.heartbeat_config,
                self.letta_client,
                self.letta_agent_id,
                self,
                self.heartbeat_post_times,
            ),
        )
        logging.info(
            "Started Discord heartbeat task: interval=%ds",
            self.heartbeat_config.interval_seconds,
        )

    async def on_message(self, message: discord.Message) -> None:
        if self.user is None:
            return

        if should_ignore_message(message, self.user):
            return

        decision = await decide_response_for_message(
            message,
            self.user,
            self.response_policy_config,
            self.conversation_states,
        )

        if not decision.should_respond:
            await asyncio.to_thread(log_observed_message, message, self.user)
            if is_ping_command(message):
                await message.channel.send("pong")
            if decision.trigger in {
                "silenced",
                "active_cooldown",
                "active_repeated_content",
                "random_repeated_content",
            }:
                logging.info(
                    "Skipping response trigger=%s from %s (%s) in #%s (%s)",
                    decision.trigger,
                    message.author.display_name,
                    message.author.id,
                    getattr(message.channel, "name", "direct-message"),
                    message.channel.id,
                )
            return

        if decision.trigger != "mention":
            await asyncio.to_thread(log_observed_message, message, self.user)

        channel_name = getattr(message.channel, "name", "direct-message")
        logging.info(
            "Received response trigger=%s from %s (%s) in #%s (%s)",
            decision.trigger,
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
                if is_channel_summary_fresh(channel_summary):
                    logging.info(
                        "Including channel summary created at %s for Discord message %s",
                        channel_summary.get("created_at"),
                        message.id,
                    )
                else:
                    logging.info(
                        "Skipping stale channel summary created at %s for Discord message %s",
                        channel_summary.get("created_at"),
                        message.id,
                    )
                    channel_summary = None

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
                if has_memory_write_tool_call(letta_reply.tool_events):
                    try:
                        await asyncio.to_thread(
                            audit_letta_memory_writes,
                            self.letta_client,
                            self.letta_agent_id,
                            message.id,
                            letta_reply.tool_events,
                        )
                    except Exception:
                        logging.exception(
                            "Failed to audit Letta memory write for Discord message %s",
                            message.id,
                        )
                logging.info(
                    "Received Letta reply for Discord message %s (%d chars)",
                    message.id,
                    len(reply),
                )

        await message.reply(reply, mention_author=False)
        mark_channel_active(
            self.conversation_states,
            channel_key(message),
            self.response_policy_config,
        )
        await asyncio.to_thread(
            log_mention_reply,
            message,
            self.user,
            reply,
            recent_messages=recent_messages,
            channel_summary=channel_summary,
            response_trigger=decision.trigger,
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


async def run_heartbeat_loop(
    config: HeartbeatConfig,
    letta_client: Letta,
    letta_agent_id: str | None,
    discord_client: discord.Client,
    last_post_at_by_channel: dict[str, datetime],
) -> None:
    while True:
        try:
            result = await asyncio.to_thread(
                run_heartbeat_once,
                config,
                client=letta_client,
                agent_id=letta_agent_id,
            )
            post_decision = await maybe_post_heartbeat_result(
                config,
                result,
                discord_client,
                last_post_at_by_channel,
            )
            await asyncio.to_thread(
                append_heartbeat_log,
                config.log_path,
                result,
                post_decision,
            )
        except Exception:
            logging.exception("Discord heartbeat run failed")

        await asyncio.sleep(config.interval_seconds)


async def maybe_post_heartbeat_result(
    config: HeartbeatConfig,
    result,
    discord_client: discord.Client,
    last_post_at_by_channel: dict[str, datetime],
) -> HeartbeatPostDecision:
    post_decision = decide_heartbeat_post(config, result, last_post_at_by_channel)
    if not post_decision.should_post:
        if result.action == "consider_reply":
            logging.info(
                "Skipping heartbeat post: reason=%s channel_id=%s",
                post_decision.reason,
                post_decision.channel_id,
            )
        return post_decision

    assert post_decision.channel_id is not None
    try:
        channel_id = int(post_decision.channel_id)
    except ValueError:
        logging.warning(
            "Skipping heartbeat post because channel_id is invalid: %s",
            post_decision.channel_id,
        )
        return HeartbeatPostDecision(
            False,
            "invalid_channel_id",
            channel_id=post_decision.channel_id,
            message=post_decision.message,
        )

    channel = discord_client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await discord_client.fetch_channel(channel_id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            logging.warning(
                "Skipping heartbeat post because channel %s could not be fetched",
                post_decision.channel_id,
                exc_info=True,
            )
            return HeartbeatPostDecision(
                False,
                "fetch_failed",
                channel_id=post_decision.channel_id,
                message=post_decision.message,
            )

    send = getattr(channel, "send", None)
    if send is None:
        logging.warning(
            "Skipping heartbeat post because channel %s cannot send messages",
            post_decision.channel_id,
        )
        return HeartbeatPostDecision(
            False,
            "cannot_send",
            channel_id=post_decision.channel_id,
            message=post_decision.message,
        )

    await send(post_decision.message)
    record_heartbeat_post(last_post_at_by_channel, post_decision.channel_id)
    logging.info("Posted heartbeat message to channel %s", post_decision.channel_id)
    return post_decision


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
    heartbeat_config = load_heartbeat_config_from_env()
    response_policy_config = load_response_policy_config_from_env()

    client = HannarioClient(
        intents=intents,
        letta_client=letta_client,
        letta_agent_id=letta_agent_id,
        auto_summary_config=auto_summary_config,
        heartbeat_config=heartbeat_config,
        response_policy_config=response_policy_config,
    )
    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
