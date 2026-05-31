from dataclasses import dataclass


@dataclass(frozen=True)
class LettaDiscordToolSpec:
    name: str
    description: str
    source_code: str
    return_char_limit: int = 8000


LIST_OBSERVED_DISCORD_CHANNELS_SOURCE = r'''LOG_DIR = globals().get("LOG_DIR", "/logs")


def list_observed_discord_channels() -> str:
    """List Discord channels found in the observation log.

    Returns:
        A short text list of observed Discord channels with counts and latest timestamps.
    """
    import json
    from pathlib import Path

    path = Path(LOG_DIR) / "discord_observations.jsonl"
    if not path.exists():
        return "No observation log is available."

    stats = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        channel_id = str(record.get("channel_id") or "unknown-id")
        timestamp = record.get("timestamp") or "unknown-time"
        item = stats.setdefault(
            channel_id,
            {
                "channel_id": channel_id,
                "channel_name": record.get("channel_name") or "unknown-channel",
                "count": 0,
                "latest_observed_at": timestamp,
                "latest_author": "unknown-author",
            },
        )
        item["count"] += 1
        item["channel_name"] = record.get("channel_name") or item["channel_name"]
        item["latest_observed_at"] = timestamp
        item["latest_author"] = (
            record.get("author_display_name")
            or record.get("author_id")
            or "unknown-author"
        )

    if not stats:
        return "No observed Discord channels found."

    channels = sorted(
        stats.values(),
        key=lambda item: str(item.get("latest_observed_at") or ""),
        reverse=True,
    )
    return "\n".join(
        f"#{item['channel_name']} ({item['channel_id']}): "
        f"{item['count']} observations, latest={item['latest_observed_at']}, "
        f"latest_author={item['latest_author']}"
        for item in channels
    )
'''


GET_RECENT_DISCORD_OBSERVATIONS_SOURCE = r'''LOG_DIR = globals().get("LOG_DIR", "/logs")


def get_recent_discord_observations(channel_id: str, limit: int = 10) -> str:
    """Get recent observed non-mention messages for one Discord channel.

    Args:
        channel_id: Discord channel ID to inspect.
        limit: Maximum number of recent observations to return. Values are clamped to 1..50.

    Returns:
        A text block of recent observed same-channel messages in oldest-first order.
    """
    import json
    from collections import deque
    from pathlib import Path

    safe_limit = max(1, min(int(limit), 50))
    path = Path(LOG_DIR) / "discord_observations.jsonl"
    if not path.exists():
        return "No observation log is available."

    records = deque(maxlen=safe_limit)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if str(record.get("channel_id")) == str(channel_id):
            records.append(record)

    if not records:
        return f"No observations found for channel_id={channel_id}."

    latest = records[-1]
    channel_name = latest.get("channel_name") or "unknown-channel"
    lines = [
        "observed_same_channel_context_oldest_first:",
        f"channel: {channel_name} ({channel_id})",
    ]
    for record in records:
        timestamp = record.get("timestamp") or "unknown-time"
        author = (
            record.get("author_display_name")
            or record.get("author_id")
            or "unknown-author"
        )
        author_id = record.get("author_id") or "unknown-id"
        text = record.get("clean_content") or ""
        lines.append(f"- {timestamp} {author} ({author_id}): {text}")

    return "\n".join(lines)
'''


GET_LATEST_DISCORD_CHANNEL_SUMMARY_SOURCE = r'''LOG_DIR = globals().get("LOG_DIR", "/logs")


def get_latest_discord_channel_summary(channel_id: str) -> str:
    """Get the latest saved observation summary for one Discord channel.

    Args:
        channel_id: Discord channel ID to inspect.

    Returns:
        The latest saved same-channel summary, or a message saying none is available.
    """
    import json
    from pathlib import Path

    path = Path(LOG_DIR) / "channel_summaries.jsonl"
    if not path.exists():
        return "No channel summary log is available."

    latest = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if str(record.get("channel_id")) == str(channel_id):
            latest = record

    if latest is None:
        return f"No saved summary found for channel_id={channel_id}."

    channel_name = latest.get("channel_name") or "unknown-channel"
    created_at = latest.get("created_at") or "unknown-time"
    first_observed_at = latest.get("first_observed_at") or "unknown-start"
    last_observed_at = latest.get("last_observed_at") or "unknown-end"
    record_count = latest.get("record_count") or "?"
    summary = latest.get("summary") or ""

    return "\n".join(
        [
            "latest_same_channel_summary:",
            "note: Use this only as older background if more recent same-channel context is available.",
            f"channel: {channel_name} ({channel_id})",
            f"created_at: {created_at}",
            f"observed_range: {first_observed_at} -> {last_observed_at}",
            f"record_count: {record_count}",
            "summary:",
            summary,
        ]
    )
'''


LETTA_DISCORD_TOOL_SPECS = [
    LettaDiscordToolSpec(
        name="list_observed_discord_channels",
        description="List Discord channels observed by the bot, with counts and latest timestamps.",
        source_code=LIST_OBSERVED_DISCORD_CHANNELS_SOURCE,
    ),
    LettaDiscordToolSpec(
        name="get_recent_discord_observations",
        description="Read recent observed non-mention messages for one Discord channel.",
        source_code=GET_RECENT_DISCORD_OBSERVATIONS_SOURCE,
    ),
    LettaDiscordToolSpec(
        name="get_latest_discord_channel_summary",
        description="Read the latest saved observation summary for one Discord channel.",
        source_code=GET_LATEST_DISCORD_CHANNEL_SUMMARY_SOURCE,
    ),
]
