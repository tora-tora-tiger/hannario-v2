from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_MENTION_LOG_PATH = Path("logs/discord_mentions.jsonl")
DEFAULT_OBSERVATION_LOG_PATH = Path("logs/discord_observations.jsonl")
DEFAULT_HEARTBEAT_LOG_PATH = Path("logs/discord_heartbeats.jsonl")
DEFAULT_SCHEDULE_LOG_PATH = Path("logs/scheduled_tasks.jsonl")
DEFAULT_MEMORY_WRITE_LOG_PATH = Path("logs/letta_memory_writes.jsonl")

FALLBACK_REPLY = "ごめん、今ちょっと考える側につながらない。"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize recent bot operations from local JSONL logs.",
    )
    parser.add_argument(
        "--since",
        default="24h",
        help="Lookback window such as 30m, 6h, or 2d. Use 'all' for all records.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Maximum number of conversation items to print.",
    )
    parser.add_argument("--mentions-path", type=Path, default=DEFAULT_MENTION_LOG_PATH)
    parser.add_argument(
        "--observations-path",
        type=Path,
        default=DEFAULT_OBSERVATION_LOG_PATH,
    )
    parser.add_argument("--heartbeats-path", type=Path, default=DEFAULT_HEARTBEAT_LOG_PATH)
    parser.add_argument("--schedule-path", type=Path, default=DEFAULT_SCHEDULE_LOG_PATH)
    parser.add_argument(
        "--memory-writes-path",
        type=Path,
        default=DEFAULT_MEMORY_WRITE_LOG_PATH,
    )
    return parser.parse_args()


def parse_lookback(value: str) -> timedelta | None:
    normalized = value.strip().lower()
    if normalized == "all":
        return None
    if len(normalized) < 2:
        raise ValueError("since must be like 30m, 6h, 2d, or all.")

    unit = normalized[-1]
    number_text = normalized[:-1]
    try:
        amount = float(number_text)
    except ValueError as exc:
        raise ValueError("since must be like 30m, 6h, 2d, or all.") from exc

    if amount < 0:
        raise ValueError("since must not be negative.")

    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise ValueError("since unit must be m, h, d, or all.")


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_snapshot_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    name = Path(value).name
    if not name.endswith("Z.json"):
        return None
    raw = name.removesuffix("Z.json")
    if "T" not in raw:
        return None
    date_text, time_text = raw.split("T", 1)
    if "." in time_text:
        hh_mm_ss, fraction = time_text.split(".", 1)
        normalized_time = hh_mm_ss.replace("-", ":") + "." + fraction
    else:
        normalized_time = time_text.replace("-", ":")
    return parse_timestamp(f"{date_text}T{normalized_time}+00:00")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            records.append(
                {
                    "_invalid_json": True,
                    "_line_number": line_number,
                    "_path": str(path),
                }
            )
            continue
        records.append(record)
    return records


def record_timestamp(record: dict[str, Any]) -> datetime | None:
    for key in ("timestamp", "checked_at", "created_at"):
        parsed = parse_timestamp(record.get(key))
        if parsed is not None:
            return parsed
    parsed_snapshot = parse_snapshot_timestamp(record.get("snapshot_path"))
    if parsed_snapshot is not None:
        return parsed_snapshot
    return None


def filter_since(
    records: list[dict[str, Any]],
    *,
    now: datetime,
    lookback: timedelta | None,
) -> list[dict[str, Any]]:
    if lookback is None:
        return records

    cutoff = now - lookback
    filtered = []
    for record in records:
        timestamp = record_timestamp(record)
        if timestamp is not None and timestamp >= cutoff:
            filtered.append(record)
    return filtered


def truncate(value: str, limit: int = 120) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def channel_label(record: dict[str, Any]) -> str:
    channel = record.get("channel_name") or record.get("channel_id") or "-"
    return f"#{channel}" if not str(channel).startswith("#") else str(channel)


def author_label(record: dict[str, Any]) -> str:
    return str(record.get("author_display_name") or record.get("author_id") or "-")


def count_invalid(records: list[dict[str, Any]]) -> int:
    return sum(1 for record in records if record.get("_invalid_json"))


def tool_events_from_mentions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for record in records:
        raw_events = record.get("letta_tool_events") or []
        if isinstance(raw_events, list):
            events.extend(event for event in raw_events if isinstance(event, dict))
    return events


def is_tool_return_error(event: dict[str, Any]) -> bool:
    if event.get("kind") != "return":
        return False
    status = str(event.get("status") or "").strip().lower()
    return bool(status and status not in {"success", "ok"})


def print_counts(title: str, counter: Counter[str]) -> None:
    print(title)
    if not counter:
        print("- none")
        return
    for key, count in counter.most_common():
        print(f"- {key}: {count}")


def print_conversation_summary(records: list[dict[str, Any]], limit: int) -> None:
    print("## Conversations")
    if not records:
        print("No triggered conversation records in the selected window.")
        return

    trigger_counts = Counter(str(record.get("response_trigger") or "mention") for record in records)
    channel_counts = Counter(channel_label(record) for record in records)
    fallback_count = sum(1 for record in records if record.get("bot_reply") == FALLBACK_REPLY)
    tool_events = tool_events_from_mentions(records)
    tool_call_counts = Counter(
        str(event.get("name") or "-")
        for event in tool_events
        if event.get("kind") == "call"
    )
    tool_error_count = sum(1 for event in tool_events if is_tool_return_error(event))
    memory_like_count = sum(
        1
        for record in records
        if "memory_" in json.dumps(record, ensure_ascii=False)
    )

    print(f"Triggered replies: {len(records)}")
    print(f"Fallback replies: {fallback_count}")
    print(f"Letta tool calls logged: {sum(tool_call_counts.values())}")
    print(f"Letta tool return errors logged: {tool_error_count}")
    print(f"Records mentioning memory tools: {memory_like_count}")
    print_counts("By trigger:", trigger_counts)
    print_counts("By channel:", channel_counts)
    if tool_call_counts:
        print_counts("By Letta tool:", tool_call_counts)

    print()
    print("Recent triggered replies:")
    for record in records[-limit:]:
        timestamp = record.get("timestamp") or "unknown-time"
        trigger = record.get("response_trigger") or "mention"
        user_text = truncate(str(record.get("clean_content") or ""), 100)
        bot_reply = truncate(str(record.get("bot_reply") or ""), 120)
        print(f"- [{timestamp}] {channel_label(record)} / {author_label(record)} / {trigger}")
        print(f"  User: {user_text}")
        print(f"  Bot:  {bot_reply}")


def print_observation_summary(records: list[dict[str, Any]]) -> None:
    print("## Observations")
    if not records:
        print("No observation records in the selected window.")
        return

    channel_counts = Counter(channel_label(record) for record in records)
    author_counts = Counter(author_label(record) for record in records)
    print(f"Observed non-bot messages: {len(records)}")
    print_counts("By channel:", channel_counts)
    print_counts("Top authors:", Counter(dict(author_counts.most_common(8))))


def print_heartbeat_summary(records: list[dict[str, Any]]) -> None:
    print("## Heartbeats")
    if not records:
        print("No heartbeat records in the selected window.")
        return

    actions = Counter(str(record.get("action") or "none") for record in records)
    post_count = sum(1 for record in records if record.get("post_should_post") is True)
    print(f"Heartbeat decisions: {len(records)}")
    print(f"Posts allowed by gate: {post_count}")
    print_counts("By action:", actions)
    print("Recent decisions:")
    for record in records[-5:]:
        checked_at = record.get("checked_at") or "unknown-time"
        action = record.get("action") or "none"
        reason = truncate(str(record.get("reason") or ""), 100)
        post_reason = truncate(str(record.get("post_reason") or ""), 80)
        print(f"- [{checked_at}] action={action} reason={reason} post={post_reason}")


def print_schedule_summary(records: list[dict[str, Any]]) -> None:
    print("## Schedule")
    if not records:
        print("No schedule delivery records in the selected window.")
        return

    kinds = Counter(str(record.get("kind") or "post") for record in records)
    statuses = Counter(str(record.get("status_after") or "-") for record in records)
    sent_count = sum(1 for record in records if record.get("should_send") is True)
    internal_count = sum(1 for record in records if record.get("internal_result"))
    print(f"Schedule records: {len(records)}")
    print(f"Discord posts attempted: {sent_count}")
    print(f"Internal results stored: {internal_count}")
    print_counts("By kind:", kinds)
    print_counts("By status:", statuses)
    print("Recent schedule records:")
    for record in records[-5:]:
        checked_at = record.get("checked_at") or "unknown-time"
        task_id = record.get("task_id") or "-"
        kind = record.get("kind") or "post"
        text = truncate(str(record.get("note") or record.get("message") or ""), 100)
        print(f"- [{checked_at}] task=#{task_id} kind={kind}: {text}")


def print_memory_summary(records: list[dict[str, Any]]) -> None:
    print("## Memory Writes")
    if not records:
        print("No memory write audit records in the selected window.")
        return

    tool_counts: Counter[str] = Counter()
    for record in records:
        for tool in record.get("memory_write_tools") or []:
            tool_counts[str(tool.get("name") or "-")] += 1

    print(f"Memory write audit records: {len(records)}")
    print_counts("By tool:", tool_counts)
    print("Recent memory writes:")
    for record in records[-5:]:
        message_id = record.get("discord_message_id") or "-"
        snapshot = record.get("snapshot_path") or "-"
        diff = truncate(str(record.get("diff") or ""), 160)
        print(f"- discord_message_id={message_id} snapshot={snapshot}")
        if diff:
            print(f"  Diff: {diff}")


def print_warnings(
    *,
    mention_records: list[dict[str, Any]],
    heartbeat_records: list[dict[str, Any]],
    memory_records: list[dict[str, Any]],
    all_records: list[dict[str, Any]],
) -> None:
    warnings: list[str] = []

    invalid_count = count_invalid(all_records)
    if invalid_count:
        warnings.append(f"{invalid_count} invalid JSONL lines were found.")

    fallback_count = sum(1 for record in mention_records if record.get("bot_reply") == FALLBACK_REPLY)
    if fallback_count:
        warnings.append(f"{fallback_count} fallback replies indicate Letta/API failures.")

    tool_error_count = sum(
        1
        for event in tool_events_from_mentions(mention_records)
        if is_tool_return_error(event)
    )
    if tool_error_count:
        warnings.append(f"{tool_error_count} Letta tool return errors need review.")

    heartbeat_posts = sum(1 for record in heartbeat_records if record.get("post_should_post") is True)
    if heartbeat_posts:
        warnings.append(f"{heartbeat_posts} heartbeat decisions passed the post gate.")

    if memory_records:
        warnings.append(f"{len(memory_records)} memory write audit records need review.")

    print("## Operator Notes")
    if not warnings:
        print("- No obvious operational warnings from the selected logs.")
        return
    for warning in warnings:
        print(f"- {warning}")


def main() -> None:
    args = parse_args()
    lookback = parse_lookback(args.since)
    now = datetime.now(UTC)

    mention_records_all = read_jsonl(args.mentions_path)
    observation_records_all = read_jsonl(args.observations_path)
    heartbeat_records_all = read_jsonl(args.heartbeats_path)
    schedule_records_all = read_jsonl(args.schedule_path)
    memory_records_all = read_jsonl(args.memory_writes_path)

    mention_records = filter_since(mention_records_all, now=now, lookback=lookback)
    observation_records = filter_since(observation_records_all, now=now, lookback=lookback)
    heartbeat_records = filter_since(heartbeat_records_all, now=now, lookback=lookback)
    schedule_records = filter_since(schedule_records_all, now=now, lookback=lookback)
    memory_records = filter_since(memory_records_all, now=now, lookback=lookback)

    print("# Operator Report")
    print(f"Window: {args.since}")
    print()
    print_conversation_summary(mention_records, args.limit)
    print()
    print_observation_summary(observation_records)
    print()
    print_heartbeat_summary(heartbeat_records)
    print()
    print_schedule_summary(schedule_records)
    print()
    print_memory_summary(memory_records)
    print()
    print_warnings(
        mention_records=mention_records,
        heartbeat_records=heartbeat_records,
        memory_records=memory_records,
        all_records=[
            *mention_records_all,
            *observation_records_all,
            *heartbeat_records_all,
            *schedule_records_all,
            *memory_records_all,
        ],
    )


if __name__ == "__main__":
    main()
