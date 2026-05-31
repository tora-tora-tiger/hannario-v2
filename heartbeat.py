import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from letta_client import Letta, MessageCreate, TextContent

from discord_context import current_time_context
from letta_agent import RETURN_MESSAGE_TYPES, extract_assistant_text


DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 900
DEFAULT_HEARTBEAT_OBSERVATION_LIMIT = 20
DEFAULT_OBSERVATION_LOG_PATH = Path("logs/discord_observations.jsonl")
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class HeartbeatConfig:
    enabled: bool = False
    interval_seconds: int = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    consult_letta_enabled: bool = False
    observation_limit: int = DEFAULT_HEARTBEAT_OBSERVATION_LIMIT
    observation_path: Path = DEFAULT_OBSERVATION_LOG_PATH


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
        observation_limit=parse_positive_int_env(
            "DISCORD_HEARTBEAT_OBSERVATION_LIMIT",
            DEFAULT_HEARTBEAT_OBSERVATION_LIMIT,
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


def format_observation_record(record: dict[str, Any]) -> str:
    timestamp = record.get("timestamp") or "unknown-time"
    channel_name = record.get("channel_name") or "unknown-channel"
    channel_id = record.get("channel_id") or "unknown-id"
    author = record.get("author_display_name") or record.get("author_id") or "unknown-author"
    author_id = record.get("author_id") or "unknown-id"
    content = record.get("clean_content") or ""
    return f"- {timestamp} #{channel_name} ({channel_id}) {author} ({author_id}): {content}"


def build_heartbeat_input(
    records: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> str:
    lines = [
        "Discord heartbeat",
        current_time_context(now),
        "instruction:",
        "This is a private heartbeat check. Do not send a Discord message.",
        "Look at recent observed messages and decide whether anything deserves attention later.",
        "Return JSON only.",
        'Allowed actions: "none" or "consider_reply".',
        'Use action "none" unless there is a clear, socially appropriate reason to act.',
        'Schema: {"action":"none","reason":"短い理由","channel_id":null,"message":""}',
        "recent_observations_oldest_first:",
    ]

    if not records:
        lines.append("(no recent observations)")
    else:
        lines.extend(format_observation_record(record) for record in records)

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
    heartbeat_input = build_heartbeat_input(records, now=actual_now)
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
