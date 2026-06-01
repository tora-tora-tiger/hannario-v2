from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from scripts.operator_quality_review import ReviewItem, collect_review_items
    from scripts.operator_report import (
        DEFAULT_HEARTBEAT_LOG_PATH,
        DEFAULT_MEMORY_WRITE_LOG_PATH,
        DEFAULT_MENTION_LOG_PATH,
        filter_since,
        parse_lookback,
        read_jsonl,
    )
except ModuleNotFoundError:
    from operator_quality_review import ReviewItem, collect_review_items
    from operator_report import (
        DEFAULT_HEARTBEAT_LOG_PATH,
        DEFAULT_MEMORY_WRITE_LOG_PATH,
        DEFAULT_MENTION_LOG_PATH,
        filter_since,
        parse_lookback,
        read_jsonl,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turn operator quality review items into concrete recommendations.",
    )
    parser.add_argument(
        "--since",
        default="24h",
        help="Lookback window such as 30m, 6h, or 2d. Use 'all' for all records.",
    )
    parser.add_argument("--mentions-path", type=Path, default=DEFAULT_MENTION_LOG_PATH)
    parser.add_argument("--heartbeats-path", type=Path, default=DEFAULT_HEARTBEAT_LOG_PATH)
    parser.add_argument(
        "--memory-writes-path",
        type=Path,
        default=DEFAULT_MEMORY_WRITE_LOG_PATH,
    )
    return parser.parse_args()


def recommendation_lines(items: list[ReviewItem]) -> list[str]:
    category_counts = Counter(item.category for item in items)
    lines: list[str] = []

    fallback_count = category_counts["fallback"]
    if fallback_count:
        lines.append(
            f"- High: {fallback_count} fallback reply/replies. Check Letta availability, "
            "`LETTA_AGENT_ID`, OpenAI/API errors, and run `uv run python scripts/smoke_letta.py`."
        )

    tool_error_count = category_counts["tool_error"]
    if tool_error_count:
        lines.append(
            f"- High: {tool_error_count} tool return error(s). Inspect the associated "
            "`letta_tool_events`, then re-register tools with "
            "`uv run python scripts/register_letta_tools.py` if source changed."
        )

    memory_write_count = category_counts["memory_write"]
    if memory_write_count:
        lines.append(
            f"- High: {memory_write_count} memory write audit record(s). Review "
            "`logs/letta_memory_writes.jsonl` and `uv run python scripts/diff_latest_memory_snapshots.py`."
        )

    safety_count = category_counts["safety_prompt"]
    if safety_count:
        lines.append(
            f"- Medium: {safety_count} safety-sensitive prompt(s). Keep DB/web tools "
            "read-only and verify refusals stay short and tool-grounded."
        )

    long_reply_count = category_counts["long_reply"]
    if long_reply_count:
        lines.append(
            f"- Medium: {long_reply_count} long reply/replies. Consider reinforcing "
            "the playbook rule for short answers, especially for tool result summaries."
        )

    odd_reply_count = category_counts["odd_reply"]
    if odd_reply_count:
        lines.append(
            f"- Medium: {odd_reply_count} odd or stale-sounding reply/replies. Review "
            "recent context priority and stale summary handling."
        )

    heartbeat_count = category_counts["heartbeat_post_gate"]
    if heartbeat_count:
        lines.append(
            f"- Medium: {heartbeat_count} heartbeat post gate pass(es). Review for noise "
            "before enabling long unattended proactive posting."
        )

    active_count = category_counts["trigger_active"]
    random_count = category_counts["trigger_random"]
    if active_count or random_count:
        lines.append(
            f"- Low: {active_count} active and {random_count} random participation item(s). "
            "If this feels noisy, increase cooldowns or lower random reply rate."
        )

    if not lines:
        lines.append("- No immediate configuration changes recommended from the selected logs.")

    return lines


def top_examples(items: list[ReviewItem], *, limit: int = 5) -> list[str]:
    examples = []
    for item in items[:limit]:
        examples.append(
            f"- [{item.severity}] {item.category} at {item.timestamp} "
            f"{item.channel}: {item.reason}"
        )
    return examples


def load_review_items(args: argparse.Namespace) -> list[ReviewItem]:
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
    return collect_review_items(
        mention_records=mention_records,
        heartbeat_records=heartbeat_records,
        memory_records=memory_records,
    )


def main() -> None:
    args = parse_args()
    items = load_review_items(args)
    print("# Operator Recommendations")
    print(f"Window: {args.since}")
    print()
    print("## Recommendations")
    for line in recommendation_lines(items):
        print(line)

    if items:
        print()
        print("## Top Review Items")
        for line in top_examples(items):
            print(line)


if __name__ == "__main__":
    main()
