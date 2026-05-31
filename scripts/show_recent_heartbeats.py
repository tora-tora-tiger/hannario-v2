import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any


DEFAULT_HEARTBEAT_LOG_PATH = Path("logs/discord_heartbeats.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show recent Discord heartbeat decisions.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent heartbeat records to show.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_HEARTBEAT_LOG_PATH,
        help="Path to the heartbeat JSONL log.",
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
    checked_at = record.get("checked_at") or "unknown-time"
    action = record.get("action") or "none"
    reason = record.get("reason") or ""
    channel_id = record.get("channel_id") or "-"
    post_reason = record.get("post_reason") or "-"
    post_should_post = record.get("post_should_post")

    print(f"[{checked_at}] action={action} channel_id={channel_id}")
    print(f"Reason: {reason}")
    print(f"Post: should_post={post_should_post} reason={post_reason}")

    message = record.get("message") or ""
    if message:
        print(f"Message: {message}")


def main() -> None:
    args = parse_args()

    try:
        records = read_recent_records(args.path, args.limit)
    except FileNotFoundError:
        print(f"No heartbeat log found at {args.path}. Run heartbeat first.")
        return

    if not records:
        print(f"No heartbeat records found in {args.path}.")
        return

    for index, record in enumerate(records):
        if index:
            print()
        print_record(record)


if __name__ == "__main__":
    main()
