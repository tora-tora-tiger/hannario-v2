import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schedule_db import SCHEDULE_KIND_POST, db_path_from_env, list_due_scheduled_tasks, mark_scheduled_task_done
from schedule_runner import (
    DEFAULT_SCHEDULE_DUE_LIMIT,
    DEFAULT_SCHEDULE_LOG_PATH,
    append_scheduled_task_delivery_log,
    build_scheduled_task_delivery,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Complete due non-post scheduled tasks without sending Discord messages.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=db_path_from_env(),
        help="SQLite database path.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_SCHEDULE_LOG_PATH,
        help="Schedule delivery log path.",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_SCHEDULE_DUE_LIMIT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checked_at = datetime.now(UTC).isoformat()
    tasks = [
        task
        for task in list_due_scheduled_tasks(db_path=args.db_path, kind="all", limit=args.limit)
        if task.kind != SCHEDULE_KIND_POST
    ]

    if not tasks:
        print("No due internal scheduled tasks found.")
        return

    for task in tasks:
        updated_task = mark_scheduled_task_done(task.id, db_path=args.db_path)
        status_after = updated_task.status if updated_task is not None else None
        delivery = build_scheduled_task_delivery(
            task,
            checked_at=checked_at,
            should_send=False,
            reason=f"internal_{task.kind}",
            status_after=status_after,
        )
        append_scheduled_task_delivery_log(args.log_path, delivery)
        print(f"completed internal task #{task.id}: kind={task.kind} status_after={status_after}")


if __name__ == "__main__":
    main()
