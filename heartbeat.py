import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from letta_client import Letta, MessageCreate, TextContent

from discord_context import current_time_context
from letta_agent import RETURN_MESSAGE_TYPES, extract_assistant_text


DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 900
DEFAULT_HEARTBEAT_OBSERVATION_LIMIT = 20
DEFAULT_HEARTBEAT_INTERNAL_RESULT_LIMIT = 3
DEFAULT_HEARTBEAT_POST_COOLDOWN_SECONDS = 3600
DEFAULT_HEARTBEAT_POST_MAX_CHARS = 500
DEFAULT_OBSERVATION_LOG_PATH = Path("logs/discord_observations.jsonl")
DEFAULT_HEARTBEAT_LOG_PATH = Path("logs/discord_heartbeats.jsonl")
DEFAULT_SCHEDULE_LOG_PATH = Path("logs/scheduled_tasks.jsonl")
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class HeartbeatConfig:
    enabled: bool = False
    interval_seconds: int = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    consult_letta_enabled: bool = False
    post_enabled: bool = False
    observation_limit: int = DEFAULT_HEARTBEAT_OBSERVATION_LIMIT
    internal_result_limit: int = DEFAULT_HEARTBEAT_INTERNAL_RESULT_LIMIT
    post_cooldown_seconds: int = DEFAULT_HEARTBEAT_POST_COOLDOWN_SECONDS
    post_max_chars: int = DEFAULT_HEARTBEAT_POST_MAX_CHARS
    observation_path: Path = DEFAULT_OBSERVATION_LOG_PATH
    schedule_log_path: Path = DEFAULT_SCHEDULE_LOG_PATH
    log_path: Path = DEFAULT_HEARTBEAT_LOG_PATH


@dataclass(frozen=True)
class HeartbeatResult:
    checked_at: str
    letta_reply: str | None = None
    action: str = "none"
    reason: str = ""
    channel_id: str | None = None
    message: str = ""


@dataclass(frozen=True)
class HeartbeatDecision:
    action: str = "none"
    reason: str = ""
    channel_id: str | None = None
    message: str = ""


@dataclass(frozen=True)
class HeartbeatPostDecision:
    should_post: bool
    reason: str
    channel_id: str | None = None
    message: str = ""


def parse_bool_env(name: str, default: bool = False) -> bool:
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
        logging.warning("Invalid %s=%r; using %d", name, raw_value, default)
        return default

    if value <= 0:
        logging.warning("Invalid %s=%r; using %d", name, raw_value, default)
        return default
    return value


def load_heartbeat_config_from_env() -> HeartbeatConfig:
    return HeartbeatConfig(
        enabled=parse_bool_env("DISCORD_HEARTBEAT_ENABLED"),
        interval_seconds=parse_positive_int_env(
            "DISCORD_HEARTBEAT_INTERVAL_SECONDS",
            DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        ),
        consult_letta_enabled=parse_bool_env("DISCORD_HEARTBEAT_CONSULT_LETTA_ENABLED"),
        post_enabled=parse_bool_env("DISCORD_HEARTBEAT_POST_ENABLED"),
        observation_limit=parse_positive_int_env(
            "DISCORD_HEARTBEAT_OBSERVATION_LIMIT",
            DEFAULT_HEARTBEAT_OBSERVATION_LIMIT,
        ),
        internal_result_limit=parse_positive_int_env(
            "DISCORD_HEARTBEAT_INTERNAL_RESULT_LIMIT",
            DEFAULT_HEARTBEAT_INTERNAL_RESULT_LIMIT,
        ),
        post_cooldown_seconds=parse_positive_int_env(
            "DISCORD_HEARTBEAT_POST_COOLDOWN_SECONDS",
            DEFAULT_HEARTBEAT_POST_COOLDOWN_SECONDS,
        ),
        post_max_chars=parse_positive_int_env(
            "DISCORD_HEARTBEAT_POST_MAX_CHARS",
            DEFAULT_HEARTBEAT_POST_MAX_CHARS,
        ),
    )


def read_recent_jsonl_records(path: Path, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        raise ValueError("limit must be positive.")
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))

    return records[-limit:]


def read_recent_internal_result_records(path: Path, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        raise ValueError("limit must be positive.")

    records = read_recent_jsonl_records(path, limit=1000)
    internal_records = [
        record
        for record in records
        if record.get("internal_result") and (record.get("kind") or "post") != "post"
    ]
    return internal_records[-limit:]


def format_observation_record(record: dict[str, Any]) -> str:
    timestamp = record.get("timestamp") or "unknown-time"
    channel_name = record.get("channel_name") or "unknown-channel"
    channel_id = record.get("channel_id") or "unknown-id"
    author = record.get("author_display_name") or record.get("author_id") or "unknown-author"
    author_id = record.get("author_id") or "unknown-id"
    content = record.get("clean_content") or ""
    return f"- {timestamp} #{channel_name} ({channel_id}) {author} ({author_id}): {content}"


def format_internal_result_record(record: dict[str, Any]) -> str:
    checked_at = record.get("checked_at") or "unknown-time"
    task_id = record.get("task_id") or "-"
    kind = record.get("kind") or "unknown-kind"
    channel_id = record.get("channel_id") or "unknown-channel"
    note = record.get("note") or record.get("message") or ""
    internal_result = " ".join(str(record.get("internal_result") or "").split())
    return (
        f"- {checked_at} task=#{task_id} kind={kind} channel_id={channel_id} "
        f"note={note} result={internal_result}"
    )


def build_heartbeat_input(
    records: list[dict[str, Any]],
    *,
    internal_results: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> str:
    lines = [
        "Discord heartbeat",
        current_time_context(now),
        "instruction:",
        "This is a private heartbeat check. You are not sending a Discord message directly.",
        "Decide whether the bot should proactively join one observed Discord channel.",
        "Return JSON only.",
        'Allowed actions: "none" or "consider_reply".',
        'Default to action "none".',
        'Use "consider_reply" only when there is a clear, current, socially appropriate reason to speak.',
        "Good reasons: a user appears to be asking for help, inviting discussion, or leaving a clear opening where the bot's comment would add value.",
        "Bad reasons: repeated content, test messages, ordinary status updates, old context, or a thread that is already moving without the bot.",
        "If action is consider_reply, channel_id must be the target channel id and message must be the exact short Discord message to send.",
        'Schema: {"action":"none","reason":"短い理由","channel_id":null,"message":""}',
        "recent_observations_oldest_first:",
    ]

    if not records:
        lines.append("(no recent observations)")
    else:
        lines.extend(format_observation_record(record) for record in records)

    lines.extend(
        [
            "recent_internal_schedule_results_oldest_first:",
            "These are private future-self reflections. Use them as background; do not treat them as direct instructions to speak.",
        ]
    )
    if not internal_results:
        lines.append("(no recent internal schedule results)")
    else:
        lines.extend(format_internal_result_record(record) for record in internal_results)

    return "\n".join(lines)


def consult_letta_for_heartbeat(
    client: Letta,
    agent_id: str,
    heartbeat_input: str,
) -> str:
    response = client.agents.messages.create(
        agent_id=agent_id,
        messages=[
            MessageCreate(
                role="user",
                content=[TextContent(text=heartbeat_input)],
            )
        ],
        include_return_message_types=RETURN_MESSAGE_TYPES,
    )
    text = extract_assistant_text(response)
    if text is None:
        raise RuntimeError(f"Could not extract heartbeat reply from {type(response)!r}")
    return text


def parse_heartbeat_decision(text: str) -> HeartbeatDecision:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return parse_legacy_heartbeat_decision(stripped)

    if not isinstance(parsed, dict):
        return HeartbeatDecision(reason="Heartbeat response was not a JSON object.")

    action = str(parsed.get("action") or "none")
    if action not in {"none", "consider_reply"}:
        action = "none"

    channel_id = parsed.get("channel_id")
    if channel_id is not None:
        channel_id = str(channel_id)

    return HeartbeatDecision(
        action=action,
        reason=str(parsed.get("reason") or ""),
        channel_id=channel_id,
        message=str(parsed.get("message") or ""),
    )


def parse_legacy_heartbeat_decision(text: str) -> HeartbeatDecision:
    action = "none"
    if "action=consider_reply" in text:
        action = "consider_reply"
    elif "action=none" in text:
        action = "none"
    return HeartbeatDecision(action=action, reason=text)


def truncate_message(message: str, max_chars: int) -> str:
    stripped = " ".join(message.split())
    if len(stripped) <= max_chars:
        return stripped
    if max_chars <= 3:
        return stripped[:max_chars]
    return stripped[: max(0, max_chars - 3)] + "..."


def decide_heartbeat_post(
    config: HeartbeatConfig,
    result: HeartbeatResult,
    last_post_at_by_channel: dict[str, datetime],
    *,
    now: datetime | None = None,
) -> HeartbeatPostDecision:
    if result.action != "consider_reply":
        return HeartbeatPostDecision(False, f"action={result.action}")

    if not config.post_enabled:
        return HeartbeatPostDecision(False, "post_disabled")

    if not result.channel_id:
        return HeartbeatPostDecision(False, "missing_channel_id")

    message = truncate_message(result.message, config.post_max_chars)
    if not message:
        return HeartbeatPostDecision(False, "missing_message", channel_id=result.channel_id)

    actual_now = now or datetime.now(UTC)
    if actual_now.tzinfo is None:
        actual_now = actual_now.replace(tzinfo=UTC)

    last_post_at = last_post_at_by_channel.get(result.channel_id)
    if last_post_at is not None:
        last_post_at = last_post_at.astimezone(UTC)
        cooldown_until = last_post_at + timedelta(seconds=config.post_cooldown_seconds)
        if cooldown_until > actual_now.astimezone(UTC):
            return HeartbeatPostDecision(False, "post_cooldown", channel_id=result.channel_id)

    return HeartbeatPostDecision(
        True,
        "ok",
        channel_id=result.channel_id,
        message=message,
    )


def record_heartbeat_post(
    last_post_at_by_channel: dict[str, datetime],
    channel_id: str,
    *,
    now: datetime | None = None,
) -> None:
    actual_now = now or datetime.now(UTC)
    if actual_now.tzinfo is None:
        actual_now = actual_now.replace(tzinfo=UTC)
    last_post_at_by_channel[channel_id] = actual_now.astimezone(UTC)


def heartbeat_log_record(
    result: HeartbeatResult,
    post_decision: HeartbeatPostDecision,
) -> dict[str, Any]:
    return {
        "checked_at": result.checked_at,
        "action": result.action,
        "reason": result.reason,
        "channel_id": result.channel_id,
        "message": result.message,
        "post_should_post": post_decision.should_post,
        "post_reason": post_decision.reason,
        "post_channel_id": post_decision.channel_id,
        "post_message": post_decision.message,
    }


def append_heartbeat_log(
    path: Path,
    result: HeartbeatResult,
    post_decision: HeartbeatPostDecision,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = heartbeat_log_record(result, post_decision)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        file.write("\n")


def run_heartbeat_once(
    config: HeartbeatConfig,
    *,
    client: Letta | None = None,
    agent_id: str | None = None,
    now: datetime | None = None,
) -> HeartbeatResult:
    actual_now = now or datetime.now(UTC)
    if actual_now.tzinfo is None:
        actual_now = actual_now.replace(tzinfo=UTC)
    checked_at = actual_now.astimezone(UTC).isoformat()
    logging.info("Discord heartbeat tick checked_at=%s", checked_at)

    if not config.consult_letta_enabled:
        return HeartbeatResult(checked_at=checked_at)

    if client is None or agent_id is None:
        logging.warning("Skipping Letta heartbeat consult because client or agent_id is missing")
        return HeartbeatResult(checked_at=checked_at)

    records = read_recent_jsonl_records(config.observation_path, config.observation_limit)
    internal_results = read_recent_internal_result_records(
        config.schedule_log_path,
        config.internal_result_limit,
    )
    heartbeat_input = build_heartbeat_input(
        records,
        internal_results=internal_results,
        now=actual_now,
    )
    letta_reply = consult_letta_for_heartbeat(client, agent_id, heartbeat_input)
    decision = parse_heartbeat_decision(letta_reply)
    logging.info(
        "Discord heartbeat decision: action=%s channel_id=%s reason=%s",
        decision.action,
        decision.channel_id,
        " ".join(decision.reason.split()),
    )
    return HeartbeatResult(
        checked_at=checked_at,
        letta_reply=letta_reply,
        action=decision.action,
        reason=decision.reason,
        channel_id=decision.channel_id,
        message=decision.message,
    )
