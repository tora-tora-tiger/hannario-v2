import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any


DEFAULT_LOG_PATH = Path("logs/discord_mentions.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show recent logged Discord mention conversations.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent records to show.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Path to the mention JSONL log.",
    )
    parser.add_argument(
        "--curator-input",
        action="store_true",
        help="Print records as compact text suitable for curator dry-run input.",
    )
    return parser.parse_args()


def read_recent_records(path: Path, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        raise ValueError("limit must be positive.")

    if not path.exists():
        raise FileNotFoundError(path)

    records: deque[dict[str, Any]] = deque(maxlen=limit)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))

    return list(records)


def print_record(record: dict[str, Any]) -> None:
    timestamp = record.get("timestamp", "unknown-time")
    channel = record.get("channel_name") or record.get("channel_id") or "unknown-channel"
    author = record.get("author_display_name") or record.get("author_id") or "unknown-author"
    user_text = record.get("clean_content") or ""
    bot_reply = record.get("bot_reply") or ""

    print(f"[{timestamp}] #{channel} / {author}")
    print(f"User: {user_text}")
    print(f"Bot: {bot_reply}")


def print_curator_input(record: dict[str, Any]) -> None:
    user_text = record.get("clean_content") or ""
    bot_reply = record.get("bot_reply") or ""

    print(f"ユーザー: {user_text}")
    print(f"Bot: {bot_reply}")


def main() -> None:
    args = parse_args()

    try:
        records = read_recent_records(args.path, args.limit)
    except FileNotFoundError:
        print(f"No mention log found at {args.path}. Run the bot and mention it first.")
        return

    if not records:
        print(f"No mention records found in {args.path}.")
        return

    for index, record in enumerate(records):
        if index:
            print()
        if args.curator_input:
            print_curator_input(record)
        else:
            print_record(record)


if __name__ == "__main__":
    main()
