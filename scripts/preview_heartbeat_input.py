import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from heartbeat import (
    DEFAULT_HEARTBEAT_INTERNAL_RESULT_LIMIT,
    DEFAULT_HEARTBEAT_OBSERVATION_LIMIT,
    DEFAULT_OBSERVATION_LOG_PATH,
    DEFAULT_SCHEDULE_LOG_PATH,
    build_heartbeat_input,
    read_recent_internal_result_records,
    read_recent_jsonl_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview the private heartbeat input sent to Letta.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_HEARTBEAT_OBSERVATION_LIMIT,
        help="Number of recent observed records to include.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_OBSERVATION_LOG_PATH,
        help="Path to the observation JSONL log.",
    )
    parser.add_argument(
        "--internal-result-limit",
        type=int,
        default=DEFAULT_HEARTBEAT_INTERNAL_RESULT_LIMIT,
        help="Number of recent internal schedule results to include.",
    )
    parser.add_argument(
        "--schedule-log-path",
        type=Path,
        default=DEFAULT_SCHEDULE_LOG_PATH,
        help="Path to the scheduled task JSONL log.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        records = read_recent_jsonl_records(args.path, args.limit)
        internal_results = read_recent_internal_result_records(
            args.schedule_log_path,
            args.internal_result_limit,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    print(build_heartbeat_input(records, internal_results=internal_results))
    print()
    print("No Letta message was sent.")


if __name__ == "__main__":
    main()
