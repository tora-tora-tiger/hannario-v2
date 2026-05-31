import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schedule_db import DEFAULT_DB_PATH, ScheduledTask, db_path_from_env


DEFAULT_SCHEDULE_INTERVAL_SECONDS = 30
DEFAULT_SCHEDULE_DUE_LIMIT = 5
DEFAULT_SCHEDULE_LOG_PATH = Path("logs/scheduled_tasks.jsonl")
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ScheduleConfig:
    enabled: bool = False
    interval_seconds: int = DEFAULT_SCHEDULE_INTERVAL_SECONDS
    due_limit: int = DEFAULT_SCHEDULE_DUE_LIMIT
    internal_consult_letta_enabled: bool = False
    db_path: Path = DEFAULT_DB_PATH
    log_path: Path = DEFAULT_SCHEDULE_LOG_PATH


@dataclass(frozen=True)
class ScheduledTaskDelivery:
    checked_at: str
    task_id: int
    kind: str
    channel_id: str
    message: str
    should_send: bool
    reason: str
    note: str | None = None
    internal_result: str | None = None
    status_after: str | None = None


def parse_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in TRUTHY_ENV_VALUES


def parse_positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        logging.warning("Invalid %s=%r; using %d", name, raw_value, default)
        return default

    if value <= 0:
        logging.warning("Invalid %s=%r; using %d", name, raw_value, default)
        return default
    return value


def load_schedule_config_from_env() -> ScheduleConfig:
    return ScheduleConfig(
        enabled=parse_bool_env("DISCORD_SCHEDULE_ENABLED"),
        interval_seconds=parse_positive_int_env(
            "DISCORD_SCHEDULE_INTERVAL_SECONDS",
            DEFAULT_SCHEDULE_INTERVAL_SECONDS,
        ),
        due_limit=parse_positive_int_env(
            "DISCORD_SCHEDULE_DUE_LIMIT",
            DEFAULT_SCHEDULE_DUE_LIMIT,
        ),
        internal_consult_letta_enabled=parse_bool_env(
            "DISCORD_SCHEDULE_INTERNAL_CONSULT_LETTA_ENABLED"
        ),
        db_path=db_path_from_env(),
    )


def scheduled_task_delivery_record(delivery: ScheduledTaskDelivery) -> dict[str, Any]:
    return {
        "checked_at": delivery.checked_at,
        "task_id": delivery.task_id,
        "kind": delivery.kind,
        "channel_id": delivery.channel_id,
        "message": delivery.message,
        "note": delivery.note,
        "should_send": delivery.should_send,
        "reason": delivery.reason,
        "status_after": delivery.status_after,
        "internal_result": delivery.internal_result,
    }


def append_scheduled_task_delivery_log(
    path: Path,
    delivery: ScheduledTaskDelivery,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = scheduled_task_delivery_record(delivery)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        file.write("\n")


def build_scheduled_task_delivery(
    task: ScheduledTask,
    *,
    checked_at: str,
    should_send: bool,
    reason: str,
    internal_result: str | None = None,
    status_after: str | None = None,
) -> ScheduledTaskDelivery:
    return ScheduledTaskDelivery(
        checked_at=checked_at,
        task_id=task.id,
        kind=task.kind,
        channel_id=task.channel_id,
        message=task.message,
        note=task.note,
        should_send=should_send,
        reason=reason,
        internal_result=internal_result,
        status_after=status_after,
    )
