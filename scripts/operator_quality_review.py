from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from scripts.operator_report import (
        DEFAULT_HEARTBEAT_LOG_PATH,
        DEFAULT_MEMORY_WRITE_LOG_PATH,
        DEFAULT_MENTION_LOG_PATH,
        FALLBACK_REPLY,
        author_label,
        channel_label,
        filter_since,
        is_tool_return_error,
        parse_lookback,
        read_jsonl,
        truncate,
    )
except ModuleNotFoundError:
    from operator_report import (
        DEFAULT_HEARTBEAT_LOG_PATH,
        DEFAULT_MEMORY_WRITE_LOG_PATH,
        DEFAULT_MENTION_LOG_PATH,
        FALLBACK_REPLY,
        author_label,
        channel_label,
        filter_since,
        is_tool_return_error,
        parse_lookback,
        read_jsonl,
        truncate,
    )


LONG_REPLY_CHARS = 280
NATURAL_TRIGGERS = {"random", "active"}
SAFETY_REVIEW_TERMS = (
    "delete",
    "drop",
    "truncate",
    "127.0.0.1",
    "localhost",
    "人命",
    "かいくぐ",
    "死んだ",
    "死ね",
)
STALE_OR_WEIRD_REPLY_TERMS = (
    "現在起動していない",
    "特にアクションを取る必要がないため",
)


@dataclass(frozen=True)
class ReviewItem:
    severity: str
    category: str
    timestamp: str
    channel: str
    author: str
    reason: str
    user_text: str = ""
    bot_reply: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract likely conversation-quality review items from bot logs.",
    )
    parser.add_argument(
        "--since",
        default="24h",
        help="Lookback window such as 30m, 6h, or 2d. Use 'all' for all records.",
    )
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--mentions-path", type=Path, default=DEFAULT_MENTION_LOG_PATH)
    parser.add_argument("--heartbeats-path", type=Path, default=DEFAULT_HEARTBEAT_LOG_PATH)
    parser.add_argument(
        "--memory-writes-path",
        type=Path,
        default=DEFAULT_MEMORY_WRITE_LOG_PATH,
    )
    return parser.parse_args()


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def review_conversation(record: dict[str, Any]) -> list[ReviewItem]:
    timestamp = str(record.get("timestamp") or "unknown-time")
    channel = channel_label(record)
    author = author_label(record)
    trigger = str(record.get("response_trigger") or "mention")
    user_text = str(record.get("clean_content") or "")
    bot_reply = str(record.get("bot_reply") or "")

    items: list[ReviewItem] = []

    if bot_reply == FALLBACK_REPLY:
        items.append(
            ReviewItem(
                severity="high",
                category="fallback",
                timestamp=timestamp,
                channel=channel,
                author=author,
                reason="Letta/API failure fallback was sent.",
                user_text=user_text,
                bot_reply=bot_reply,
            )
        )

    if len(bot_reply) > LONG_REPLY_CHARS:
        items.append(
            ReviewItem(
                severity="medium",
                category="long_reply",
                timestamp=timestamp,
                channel=channel,
                author=author,
                reason=f"Reply is {len(bot_reply)} characters; may be too verbose for chat.",
                user_text=user_text,
                bot_reply=bot_reply,
            )
        )

    if trigger in NATURAL_TRIGGERS:
        items.append(
            ReviewItem(
                severity="low",
                category=f"trigger_{trigger}",
                timestamp=timestamp,
                channel=channel,
                author=author,
                reason=f"Non-explicit trigger `{trigger}` should be reviewed for social fit.",
                user_text=user_text,
                bot_reply=bot_reply,
            )
        )

    if contains_any(user_text, SAFETY_REVIEW_TERMS):
        items.append(
            ReviewItem(
                severity="medium",
                category="safety_prompt",
                timestamp=timestamp,
                channel=channel,
                author=author,
                reason="User message contains safety-sensitive or tool-bypass terms.",
                user_text=user_text,
                bot_reply=bot_reply,
            )
        )

    if contains_any(bot_reply, STALE_OR_WEIRD_REPLY_TERMS):
        items.append(
            ReviewItem(
                severity="medium",
                category="odd_reply",
                timestamp=timestamp,
                channel=channel,
                author=author,
                reason="Reply contains stale or internal-sounding wording.",
                user_text=user_text,
                bot_reply=bot_reply,
            )
        )

    for event in record.get("letta_tool_events") or []:
        if not isinstance(event, dict) or not is_tool_return_error(event):
            continue
        items.append(
            ReviewItem(
                severity="high",
                category="tool_error",
                timestamp=timestamp,
                channel=channel,
                author=author,
                reason=(
                    f"Letta tool `{event.get('name') or '-'}` returned "
                    f"status `{event.get('status') or '-'}`."
                ),
                user_text=user_text,
                bot_reply=str(event.get("text_preview") or ""),
            )
        )

    return items


def review_heartbeat(record: dict[str, Any]) -> list[ReviewItem]:
    if record.get("post_should_post") is not True:
        return []

    timestamp = str(record.get("checked_at") or "unknown-time")
    channel = str(record.get("post_channel_id") or record.get("channel_id") or "-")
    message = str(record.get("post_message") or record.get("message") or "")
    reason = str(record.get("reason") or "")
    return [
        ReviewItem(
            severity="medium",
            category="heartbeat_post_gate",
            timestamp=timestamp,
            channel=channel,
            author="-",
            reason="Heartbeat decision passed the post gate; review for noise.",
            user_text=reason,
            bot_reply=message,
        )
    ]


def review_memory_write(record: dict[str, Any]) -> list[ReviewItem]:
    tools = record.get("memory_write_tools") or []
    if not tools:
        return []

    timestamp = str(record.get("snapshot_path") or "unknown-time")
    tool_names = ", ".join(str(tool.get("name") or "-") for tool in tools)
    diff = str(record.get("diff") or "")
    return [
        ReviewItem(
            severity="high",
            category="memory_write",
            timestamp=timestamp,
            channel="-",
            author="-",
            reason=f"Memory write tools were used: {tool_names}.",
            user_text=str(record.get("discord_message_id") or ""),
            bot_reply=diff,
        )
    ]


def severity_sort_key(item: ReviewItem) -> tuple[int, str]:
    rank = {"high": 0, "medium": 1, "low": 2}.get(item.severity, 3)
    return rank, item.timestamp


def collect_review_items(
    *,
    mention_records: list[dict[str, Any]],
    heartbeat_records: list[dict[str, Any]],
    memory_records: list[dict[str, Any]],
) -> list[ReviewItem]:
    items: list[ReviewItem] = []
    for record in mention_records:
        items.extend(review_conversation(record))
    for record in heartbeat_records:
        items.extend(review_heartbeat(record))
    for record in memory_records:
        items.extend(review_memory_write(record))
    return sorted(items, key=severity_sort_key)


def print_review_items(items: list[ReviewItem], limit: int) -> None:
    print("# Operator Quality Review")
    if not items:
        print("No review items found in the selected window.")
        return

    severity_counts = Counter(item.severity for item in items)
    category_counts = Counter(item.category for item in items)
    print(f"Review items: {len(items)}")
    print("By severity:")
    for severity, count in severity_counts.most_common():
        print(f"- {severity}: {count}")
    print("By category:")
    for category, count in category_counts.most_common():
        print(f"- {category}: {count}")

    print()
    print("Items:")
    for item in items[:limit]:
        print(
            f"- [{item.severity}] {item.category} / {item.timestamp} / "
            f"{item.channel} / {item.author}"
        )
        print(f"  Reason: {item.reason}")
        if item.user_text:
            print(f"  User/Context: {truncate(item.user_text, 140)}")
        if item.bot_reply:
            print(f"  Bot/Result:   {truncate(item.bot_reply, 180)}")

    remaining = len(items) - limit
    if remaining > 0:
        print(f"... {remaining} more item(s) omitted by --limit.")


def main() -> None:
    args = parse_args()
    lookback = parse_lookback(args.since)
    now = datetime.now(UTC)

    mention_records = filter_since(read_jsonl(args.mentions_path), now=now, lookback=lookback)
    heartbeat_records = filter_since(
        read_jsonl(args.heartbeats_path),
        now=now,
        lookback=lookback,
    )
    memory_records = filter_since(
        read_jsonl(args.memory_writes_path),
        now=now,
        lookback=lookback,
    )

    items = collect_review_items(
        mention_records=mention_records,
        heartbeat_records=heartbeat_records,
        memory_records=memory_records,
    )
    print_review_items(items, args.limit)


if __name__ == "__main__":
    main()
