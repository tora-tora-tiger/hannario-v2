import argparse
from pathlib import Path
from typing import Any

from show_channel_summaries import (
    DEFAULT_SUMMARY_LOG_PATH,
    read_recent_summary_records,
)
from discord_context import current_time_context
from show_context_debug import format_saved_recent_context
from show_recent_mentions import DEFAULT_LOG_PATH, read_recent_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview a Letta input that combines the latest mention, saved "
            "same-channel recent context, and the latest saved channel summary."
        ),
    )
    parser.add_argument(
        "--mention-path",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Path to the mention JSONL log.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=DEFAULT_SUMMARY_LOG_PATH,
        help="Path to the channel summary JSONL log.",
    )
    return parser.parse_args()


def format_latest_channel_summary(summary: dict[str, Any] | None) -> str:
    if summary is None:
        return "supplemental_same_channel_summary:\n(no saved summary)"

    channel_name = summary.get("channel_name") or "unknown-channel"
    channel_id = summary.get("channel_id") or "unknown-id"
    created_at = summary.get("created_at") or "unknown-time"
    first_observed_at = summary.get("first_observed_at") or "unknown-start"
    last_observed_at = summary.get("last_observed_at") or "unknown-end"
    record_count = summary.get("record_count", "?")
    text = summary.get("summary") or ""

    return "\n".join(
        [
            "supplemental_same_channel_summary:",
            "note: Use this only as older background. Prefer current_message and recent_same_channel_context when they conflict.",
            f"channel: {channel_name} ({channel_id})",
            f"created_at: {created_at}",
            f"observed_range: {first_observed_at} -> {last_observed_at}",
            f"record_count: {record_count}",
            "summary:",
            text,
        ]
    )


def format_current_message(record: dict[str, Any]) -> str:
    author = (
        record.get("author_display_name")
        or record.get("author_id")
        or "unknown-author"
    )
    author_id = record.get("author_id") or "unknown-id"
    text = record.get("clean_content") or ""
    return "\n".join(
        [
            "current_message:",
            f"author: {author} ({author_id})",
            f"content: {text}",
        ]
    )


def build_preview_input(
    mention: dict[str, Any],
    summary: dict[str, Any] | None,
) -> str:
    guild_name = mention.get("guild_name") or "direct-message"
    guild_id = mention.get("guild_id") or "dm"
    channel_name = mention.get("channel_name") or "unknown-channel"
    channel_id = mention.get("channel_id") or "unknown-id"

    return "\n".join(
        [
            "Discord message",
            f"guild: {guild_name} ({guild_id})",
            f"channel: {channel_name} ({channel_id})",
            "priority: Prefer current_message and recent_same_channel_context. Use supplemental summaries only as older background.",
            current_time_context(),
            "",
            format_saved_recent_context(mention),
            "",
            format_current_message(mention),
            "",
            format_latest_channel_summary(summary),
        ]
    )


def latest_summary_for_mention(
    mention: dict[str, Any],
    summary_path: Path,
) -> dict[str, Any] | None:
    channel_id = mention.get("channel_id")
    if channel_id is None:
        return None

    try:
        summaries = read_recent_summary_records(
            summary_path,
            1,
            channel_id=str(channel_id),
        )
    except FileNotFoundError:
        return None

    return summaries[-1] if summaries else None


def main() -> None:
    args = parse_args()

    try:
        mention_records = read_recent_records(args.mention_path, 1)
    except FileNotFoundError:
        print(f"No mention log found at {args.mention_path}. Run the bot and mention it first.")
        return

    if not mention_records:
        print(f"No mention records found in {args.mention_path}.")
        return

    mention = mention_records[-1]
    summary = latest_summary_for_mention(mention, args.summary_path)
    print(build_preview_input(mention, summary))
    print()
    print("No Letta message was sent.")


if __name__ == "__main__":
    main()
