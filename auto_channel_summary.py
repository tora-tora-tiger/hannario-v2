import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI

from channel_summaries import DEFAULT_SUMMARY_LOG_PATH, read_latest_channel_summary
from conversation_log import DEFAULT_OBSERVATION_LOG_PATH


DEFAULT_AUTO_SUMMARY_INTERVAL_SECONDS = 600
DEFAULT_AUTO_SUMMARY_LIMIT = 20
DEFAULT_AUTO_SUMMARY_MIN_NEW_MESSAGES = 5
DEFAULT_SUMMARY_MODEL = "gpt-4o-mini"
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AutoSummaryConfig:
    enabled: bool = False
    interval_seconds: int = DEFAULT_AUTO_SUMMARY_INTERVAL_SECONDS
    limit: int = DEFAULT_AUTO_SUMMARY_LIMIT
    min_new_messages: int = DEFAULT_AUTO_SUMMARY_MIN_NEW_MESSAGES
    observation_path: Path = DEFAULT_OBSERVATION_LOG_PATH
    summary_path: Path = DEFAULT_SUMMARY_LOG_PATH


@dataclass(frozen=True)
class ChannelSummaryCandidate:
    channel_id: str
    channel_name: str
    records: list[dict[str, Any]]
    new_record_count: int
    latest_summary_at: str | None


@dataclass(frozen=True)
class AutoSummaryResult:
    summarized: int
    skipped: int
    errors: int


SummaryFunction = Callable[[str], str]


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


def load_auto_summary_config_from_env() -> AutoSummaryConfig:
    return AutoSummaryConfig(
        enabled=parse_bool_env("DISCORD_AUTO_SUMMARY_ENABLED"),
        interval_seconds=parse_positive_int_env(
            "DISCORD_AUTO_SUMMARY_INTERVAL_SECONDS",
            DEFAULT_AUTO_SUMMARY_INTERVAL_SECONDS,
        ),
        limit=parse_positive_int_env("DISCORD_AUTO_SUMMARY_LIMIT", DEFAULT_AUTO_SUMMARY_LIMIT),
        min_new_messages=parse_positive_int_env(
            "DISCORD_AUTO_SUMMARY_MIN_NEW_MESSAGES",
            DEFAULT_AUTO_SUMMARY_MIN_NEW_MESSAGES,
        ),
    )


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def group_observations_by_channel(
    records: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        channel_id = str(record.get("channel_id") or "unknown-id")
        grouped.setdefault(channel_id, []).append(record)
    return grouped


def records_after_timestamp(
    records: list[dict[str, Any]],
    timestamp: str | None,
) -> list[dict[str, Any]]:
    if timestamp is None:
        return records
    return [record for record in records if str(record.get("timestamp") or "") > timestamp]


def recent_records(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return records[-limit:]


def channel_label(records: list[dict[str, Any]], channel_id: str) -> str:
    if not records:
        return f"unknown-channel ({channel_id})"
    record = records[-1]
    return f"{record.get('channel_name') or 'unknown-channel'} ({channel_id})"


def format_channel_context(records: list[dict[str, Any]], channel_id: str) -> str:
    lines = [
        "observed_same_channel_context_oldest_first:",
        f"channel: {channel_label(records, channel_id)}",
    ]

    for record in records:
        timestamp = record.get("timestamp", "unknown-time")
        author = (
            record.get("author_display_name")
            or record.get("author_id")
            or "unknown-author"
        )
        author_id = record.get("author_id") or "unknown-id"
        text = record.get("clean_content") or ""
        lines.append(f"- {timestamp} {author} ({author_id}): {text}")

    return "\n".join(lines)


def summary_instructions() -> str:
    return """You summarize observed Discord channel context for a small private companion bot.

The input contains observed non-mention messages from one Discord channel.
Do not propose memory writes.
Do not invent facts outside the input.
Keep the output in Japanese.

Return:
- 概要: 1-2 short sentences.
- 話題: concise bullet list of main topics.
- 継続中の文脈: anything that may matter if the bot is mentioned soon.
"""


def extract_response_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    raise RuntimeError(f"Could not extract summary text from {type(response)!r}")


def load_openai_env() -> None:
    load_dotenv(".env")
    load_dotenv(".env.letta")

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY. Add it to .env.letta first.")


def summarize_context(context: str) -> str:
    load_openai_env()
    client = OpenAI()
    response = client.responses.create(
        model=os.getenv("SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL),
        instructions=summary_instructions(),
        input=context,
        temperature=0,
    )
    return extract_response_text(response)


def summary_log_record(
    records: list[dict[str, Any]],
    context: str,
    summary: str,
    *,
    model: str,
) -> dict[str, Any]:
    first = records[0]
    last = records[-1]
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "channel_id": str(last.get("channel_id")) if last.get("channel_id") else None,
        "channel_name": last.get("channel_name"),
        "record_count": len(records),
        "first_observed_at": first.get("timestamp"),
        "last_observed_at": last.get("timestamp"),
        "model": model,
        "context": context,
        "summary": summary,
    }


def save_summary(
    path: Path,
    records: list[dict[str, Any]],
    context: str,
    summary: str,
    *,
    model: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = summary_log_record(records, context, summary, model=model)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        file.write("\n")


def find_summary_candidates(config: AutoSummaryConfig) -> list[ChannelSummaryCandidate]:
    records = read_jsonl_records(config.observation_path)
    grouped = group_observations_by_channel(records)
    candidates: list[ChannelSummaryCandidate] = []

    for channel_id, channel_records in grouped.items():
        latest_summary = read_latest_channel_summary(channel_id, config.summary_path)
        latest_summary_at = None
        if latest_summary is not None:
            latest_summary_at = latest_summary.get("last_observed_at")

        new_records = records_after_timestamp(channel_records, latest_summary_at)
        if len(new_records) < config.min_new_messages:
            continue

        records_to_summarize = recent_records(channel_records, config.limit)
        channel_name = (
            records_to_summarize[-1].get("channel_name")
            or channel_records[-1].get("channel_name")
            or "unknown-channel"
        )
        candidates.append(
            ChannelSummaryCandidate(
                channel_id=channel_id,
                channel_name=channel_name,
                records=records_to_summarize,
                new_record_count=len(new_records),
                latest_summary_at=latest_summary_at,
            )
        )

    return sorted(
        candidates,
        key=lambda item: str(item.records[-1].get("timestamp") or ""),
        reverse=True,
    )


def run_auto_channel_summaries_once(
    config: AutoSummaryConfig,
    *,
    summarize: SummaryFunction = summarize_context,
) -> AutoSummaryResult:
    candidates = find_summary_candidates(config)
    errors = 0
    summarized = 0

    for candidate in candidates:
        try:
            context = format_channel_context(candidate.records, candidate.channel_id)
            summary = summarize(context)
            save_summary(
                config.summary_path,
                candidate.records,
                context,
                summary,
                model=os.getenv("SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL),
            )
        except Exception:
            errors += 1
            logging.exception(
                "Failed to summarize Discord channel %s (%s)",
                candidate.channel_name,
                candidate.channel_id,
            )
            continue

        summarized += 1
        logging.info(
            "Saved Discord channel summary for #%s (%s): records=%d new_records=%d",
            candidate.channel_name,
            candidate.channel_id,
            len(candidate.records),
            candidate.new_record_count,
        )

    return AutoSummaryResult(
        summarized=summarized,
        skipped=len(group_observations_by_channel(read_jsonl_records(config.observation_path)))
        - len(candidates),
        errors=errors,
    )
