import json
from collections import deque
from pathlib import Path
from typing import Any


DEFAULT_SUMMARY_LOG_PATH = Path("logs/channel_summaries.jsonl")


def summary_matches_channel(
    record: dict[str, Any],
    channel_id: str,
) -> bool:
    return str(record.get("channel_id")) == channel_id


def read_latest_channel_summary(
    channel_id: str,
    path: Path = DEFAULT_SUMMARY_LOG_PATH,
) -> dict[str, Any] | None:
    if not path.exists():
        return None

    records: deque[dict[str, Any]] = deque(maxlen=1)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if summary_matches_channel(record, channel_id):
            records.append(record)

    return records[-1] if records else None


def compact_summary_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None

    return {
        "created_at": record.get("created_at"),
        "channel_id": record.get("channel_id"),
        "channel_name": record.get("channel_name"),
        "record_count": record.get("record_count"),
        "first_observed_at": record.get("first_observed_at"),
        "last_observed_at": record.get("last_observed_at"),
        "model": record.get("model"),
        "summary": record.get("summary"),
    }


def format_channel_summary_for_prompt(record: dict[str, Any] | None) -> str | None:
    if record is None:
        return None

    channel_name = record.get("channel_name") or "unknown-channel"
    channel_id = record.get("channel_id") or "unknown-id"
    created_at = record.get("created_at") or "unknown-time"
    first_observed_at = record.get("first_observed_at") or "unknown-start"
    last_observed_at = record.get("last_observed_at") or "unknown-end"
    record_count = record.get("record_count", "?")
    summary = record.get("summary") or ""

    return "\n".join(
        [
            "supplemental_same_channel_summary:",
            "note: Use this only as older background. Prefer current_message and recent_same_channel_context when they conflict.",
            f"channel: {channel_name} ({channel_id})",
            f"created_at: {created_at}",
            f"observed_range: {first_observed_at} -> {last_observed_at}",
            f"record_count: {record_count}",
            "summary:",
            summary,
        ]
    )
