from dataclasses import dataclass


@dataclass(frozen=True)
class LettaDiscordToolSpec:
    name: str
    description: str
    source_code: str
    return_char_limit: int = 8000
    tags: tuple[str, ...] = ("hannario", "discord", "read-only")
    default_requires_approval: bool = False


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


GET_RECENT_DISCORD_INTERNAL_RESULTS_SOURCE = r'''LOG_DIR = globals().get("LOG_DIR", "/logs")


def get_recent_discord_internal_results(
    channel_id: str = "",
    limit: int = 5,
    kind: str = "all",
) -> str:
    """Get recent internal scheduled task results.

    Args:
        channel_id: Optional related Discord channel ID filter.
        limit: Maximum number of results to return. Values are clamped to 1..20.
        kind: One of all, think, observe, or follow_up.

    Returns:
        A text block of recent private internal results in oldest-first order.
    """
    import json
    from collections import deque
    from pathlib import Path

    safe_limit = max(1, min(int(limit), 20))
    safe_kind = str(kind or "all").strip().lower()
    if safe_kind not in {"all", "think", "observe", "follow_up"}:
        safe_kind = "all"
    safe_channel_id = str(channel_id or "").strip()

    path = Path(LOG_DIR) / "scheduled_tasks.jsonl"
    if not path.exists():
        return "No scheduled task log is available."

    records = deque(maxlen=safe_limit)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        record_kind = str(record.get("kind") or "post")
        if record_kind == "post":
            continue
        if not record.get("internal_result"):
            continue
        if safe_kind != "all" and record_kind != safe_kind:
            continue
        if safe_channel_id and str(record.get("channel_id") or "") != safe_channel_id:
            continue
        records.append(record)

    if not records:
        return "No internal scheduled task results found."

    lines = ["recent_internal_discord_results_oldest_first:"]
    for record in records:
        checked_at = record.get("checked_at") or "unknown-time"
        task_id = record.get("task_id") or "-"
        record_kind = record.get("kind") or "unknown-kind"
        related_channel_id = record.get("channel_id") or "unknown-channel"
        note = record.get("note") or record.get("message") or ""
        result = " ".join(str(record.get("internal_result") or "").split())
        lines.append(
            f"- {checked_at} task=#{task_id} kind={record_kind} "
            f"channel_id={related_channel_id} note={note} result={result}"
        )

    return "\n".join(lines)
'''


LIST_DISCORD_SCHEDULES_SOURCE = r'''DB_PATH = globals().get("DB_PATH", "/data/local.sqlite3")


def list_discord_schedules(status: str = "pending", limit: int = 10, channel_id: str = "") -> str:
    """List scheduled Discord tasks.

    Args:
        status: One of pending, done, cancelled, or all.
        limit: Maximum number of tasks to return. Values are clamped to 1..50.
        channel_id: Optional Discord channel ID filter.

    Returns:
        A text list of scheduled tasks.
    """
    import sqlite3
    from pathlib import Path

    safe_status = str(status or "pending").strip().lower()
    if safe_status not in {"pending", "done", "cancelled", "all"}:
        safe_status = "pending"
    safe_limit = max(1, min(int(limit), 50))

    path = Path(DB_PATH)
    if not path.exists():
        return f"No schedule database is available at {path}."

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        column_names = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(scheduled_tasks)").fetchall()
        }
        if "kind" not in column_names:
            connection.execute(
                "ALTER TABLE scheduled_tasks ADD COLUMN kind TEXT NOT NULL DEFAULT 'post'"
            )
        if "note" not in column_names:
            connection.execute("ALTER TABLE scheduled_tasks ADD COLUMN note TEXT")
        connection.commit()

        clauses = []
        params = []
        if safe_status != "all":
            clauses.append("status = ?")
            params.append(safe_status)
        if str(channel_id).strip():
            clauses.append("channel_id = ?")
            params.append(str(channel_id))

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = connection.execute(
            f"""
            SELECT * FROM scheduled_tasks
            {where}
            ORDER BY due_at ASC, id ASC
            LIMIT ?
            """,
            [*params, safe_limit],
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        return "No scheduled Discord tasks found."

    lines = ["scheduled_discord_tasks:"]
    for row in rows:
        lines.append(
            f"#{row['id']} [{row['status']}] kind={row['kind']} channel_id={row['channel_id']} "
            f"due_at={row['due_at']} message={row['message']} note={row['note'] or ''}"
        )
    return "\n".join(lines)
'''


CREATE_DISCORD_SCHEDULE_SOURCE = r'''DB_PATH = globals().get("DB_PATH", "/data/local.sqlite3")


def create_discord_schedule(
    channel_id: str,
    due_at: str,
    message: str,
    timezone: str = "Asia/Tokyo",
    relative_minutes: int = 0,
) -> str:
    """Create a scheduled Discord task.

    Args:
        channel_id: Discord channel ID to post to.
        due_at: ISO timestamp. Naive values are interpreted in timezone.
        message: Message to post when due.
        timezone: IANA timezone for naive due_at values. Default is Asia/Tokyo.
        relative_minutes: For requests like "10 minutes later", set this instead of
            calculating due_at yourself. Values are clamped to 1..10080. Use 0 to ignore.

    Returns:
        A short confirmation including the created task id and stored UTC due_at.
    """
    import sqlite3
    from datetime import UTC, datetime, timedelta
    from pathlib import Path
    from zoneinfo import ZoneInfo

    if not str(channel_id).strip():
        return "Failed to create schedule: channel_id is required."
    if not str(message).strip():
        return "Failed to create schedule: message is required."

    try:
        schedule_timezone = ZoneInfo(timezone)
    except Exception:
        return f"Failed to create schedule: unknown timezone {timezone}."

    try:
        safe_relative_minutes = int(relative_minutes)
    except (TypeError, ValueError):
        safe_relative_minutes = 0

    if safe_relative_minutes:
        safe_relative_minutes = max(1, min(safe_relative_minutes, 10080))
        parsed_due_at = datetime.now(schedule_timezone) + timedelta(minutes=safe_relative_minutes)
    else:
        try:
            parsed_due_at = datetime.fromisoformat(str(due_at))
        except ValueError:
            return "Failed to create schedule: due_at must be an ISO timestamp."

        if parsed_due_at.tzinfo is None:
            parsed_due_at = parsed_due_at.replace(tzinfo=schedule_timezone)

    due_at_utc = parsed_due_at.astimezone(UTC).isoformat()
    created_at = datetime.now(UTC).isoformat()
    if parsed_due_at.astimezone(UTC) <= datetime.now(UTC) + timedelta(seconds=5):
        return (
            "Failed to create schedule: due_at is in the past or too close to now. "
            "Use the current Asia/Tokyo date/time for relative requests and ask the user "
            "to confirm if the intended time is unclear."
        )

    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                message TEXT NOT NULL,
                due_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'done', 'cancelled')),
                kind TEXT NOT NULL DEFAULT 'post',
                created_at TEXT NOT NULL,
                note TEXT,
                created_by TEXT,
                source_message_id TEXT,
                completed_at TEXT,
                cancelled_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_due_pending
            ON scheduled_tasks (status, due_at)
            """
        )
        column_names = {
            row[1]
            for row in connection.execute("PRAGMA table_info(scheduled_tasks)").fetchall()
        }
        if "kind" not in column_names:
            connection.execute(
                "ALTER TABLE scheduled_tasks ADD COLUMN kind TEXT NOT NULL DEFAULT 'post'"
            )
        if "note" not in column_names:
            connection.execute("ALTER TABLE scheduled_tasks ADD COLUMN note TEXT")
        cursor = connection.execute(
            """
            INSERT INTO scheduled_tasks (
                channel_id,
                message,
                due_at,
                kind,
                status,
                created_at
            )
            VALUES (?, ?, ?, 'post', 'pending', ?)
            """,
            (str(channel_id), str(message), due_at_utc, created_at),
        )
        connection.commit()
        task_id = cursor.lastrowid
    finally:
        connection.close()

    return (
        f"Created scheduled Discord task #{task_id}: "
        f"channel_id={channel_id}, due_at={due_at_utc}, message={message}"
    )
'''


CREATE_INTERNAL_DISCORD_SCHEDULE_SOURCE = r'''DB_PATH = globals().get("DB_PATH", "/data/local.sqlite3")


def create_internal_discord_schedule(
    kind: str,
    note: str,
    due_at: str = "",
    timezone: str = "Asia/Tokyo",
    relative_minutes: int = 0,
    channel_id: str = "internal",
    message: str = "",
) -> str:
    """Create an internal scheduled task for the bot's future self.

    Args:
        kind: Internal kind. One of think, observe, or follow_up.
        note: Internal note describing what the bot should think about later.
        due_at: ISO timestamp. Naive values are interpreted in timezone.
        timezone: IANA timezone for naive due_at values. Default is Asia/Tokyo.
        relative_minutes: For requests like "10 minutes later", set this instead of
            calculating due_at yourself. Values are clamped to 1..10080. Use 0 to ignore.
        channel_id: Related Discord channel ID. Use current channel_id when available.
        message: Optional short label. Defaults to note.

    Returns:
        A short confirmation including the created task id and stored UTC due_at.
    """
    import sqlite3
    from datetime import UTC, datetime, timedelta
    from pathlib import Path
    from zoneinfo import ZoneInfo

    safe_kind = str(kind or "").strip().lower()
    if safe_kind not in {"think", "observe", "follow_up"}:
        return "Failed to create internal schedule: kind must be think, observe, or follow_up."
    if not str(note).strip():
        return "Failed to create internal schedule: note is required."

    try:
        schedule_timezone = ZoneInfo(timezone)
    except Exception:
        return f"Failed to create internal schedule: unknown timezone {timezone}."

    try:
        safe_relative_minutes = int(relative_minutes)
    except (TypeError, ValueError):
        safe_relative_minutes = 0

    if safe_relative_minutes:
        safe_relative_minutes = max(1, min(safe_relative_minutes, 10080))
        parsed_due_at = datetime.now(schedule_timezone) + timedelta(minutes=safe_relative_minutes)
    else:
        try:
            parsed_due_at = datetime.fromisoformat(str(due_at))
        except ValueError:
            return "Failed to create internal schedule: due_at must be an ISO timestamp."

        if parsed_due_at.tzinfo is None:
            parsed_due_at = parsed_due_at.replace(tzinfo=schedule_timezone)

    if parsed_due_at.astimezone(UTC) <= datetime.now(UTC) + timedelta(seconds=5):
        return "Failed to create internal schedule: due_at is in the past or too close to now."

    due_at_utc = parsed_due_at.astimezone(UTC).isoformat()
    created_at = datetime.now(UTC).isoformat()
    safe_channel_id = str(channel_id or "internal")
    safe_message = str(message or note)

    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                message TEXT NOT NULL,
                due_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'done', 'cancelled')),
                kind TEXT NOT NULL DEFAULT 'post',
                created_at TEXT NOT NULL,
                note TEXT,
                created_by TEXT,
                source_message_id TEXT,
                completed_at TEXT,
                cancelled_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_due_pending
            ON scheduled_tasks (status, due_at)
            """
        )
        column_names = {
            row[1]
            for row in connection.execute("PRAGMA table_info(scheduled_tasks)").fetchall()
        }
        if "kind" not in column_names:
            connection.execute(
                "ALTER TABLE scheduled_tasks ADD COLUMN kind TEXT NOT NULL DEFAULT 'post'"
            )
        if "note" not in column_names:
            connection.execute("ALTER TABLE scheduled_tasks ADD COLUMN note TEXT")
        cursor = connection.execute(
            """
            INSERT INTO scheduled_tasks (
                channel_id,
                message,
                due_at,
                status,
                kind,
                created_at,
                note
            )
            VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """,
            (safe_channel_id, safe_message, due_at_utc, safe_kind, created_at, str(note)),
        )
        connection.commit()
        task_id = cursor.lastrowid
    finally:
        connection.close()

    return (
        f"Created internal Discord task #{task_id}: "
        f"kind={safe_kind}, channel_id={safe_channel_id}, due_at={due_at_utc}, note={note}"
    )
'''


CANCEL_DISCORD_SCHEDULE_SOURCE = r'''DB_PATH = globals().get("DB_PATH", "/data/local.sqlite3")


def cancel_discord_schedule(task_id: int) -> str:
    """Cancel a pending scheduled Discord task.

    Args:
        task_id: Scheduled task id to cancel.

    Returns:
        A short cancellation result.
    """
    import sqlite3
    from datetime import UTC, datetime
    from pathlib import Path

    path = Path(DB_PATH)
    if not path.exists():
        return f"No schedule database is available at {path}."

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM scheduled_tasks WHERE id = ?",
            (int(task_id),),
        ).fetchone()
        if row is None:
            return f"Scheduled Discord task #{task_id} was not found."
        if row["status"] != "pending":
            return f"Scheduled Discord task #{task_id} is already {row['status']}."

        cancelled_at = datetime.now(UTC).isoformat()
        connection.execute(
            """
            UPDATE scheduled_tasks
            SET status = 'cancelled', cancelled_at = ?, completed_at = NULL
            WHERE id = ? AND status = 'pending'
            """,
            (cancelled_at, int(task_id)),
        )
        connection.commit()
    finally:
        connection.close()

    return f"Cancelled scheduled Discord task #{task_id}."
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
    LettaDiscordToolSpec(
        name="get_recent_discord_internal_results",
        description="Read recent private internal scheduled task results.",
        source_code=GET_RECENT_DISCORD_INTERNAL_RESULTS_SOURCE,
        tags=("hannario", "discord", "schedule", "internal", "read-only"),
    ),
    LettaDiscordToolSpec(
        name="list_discord_schedules",
        description="List scheduled Discord tasks from the local SQLite database.",
        source_code=LIST_DISCORD_SCHEDULES_SOURCE,
        tags=("hannario", "discord", "schedule", "read-only"),
    ),
    LettaDiscordToolSpec(
        name="create_discord_schedule",
        description="Create a scheduled Discord task in the local SQLite database.",
        source_code=CREATE_DISCORD_SCHEDULE_SOURCE,
        tags=("hannario", "discord", "schedule", "write"),
    ),
    LettaDiscordToolSpec(
        name="create_internal_discord_schedule",
        description="Create an internal scheduled task for the bot's future self.",
        source_code=CREATE_INTERNAL_DISCORD_SCHEDULE_SOURCE,
        tags=("hannario", "discord", "schedule", "write", "internal"),
    ),
    LettaDiscordToolSpec(
        name="cancel_discord_schedule",
        description="Cancel a pending scheduled Discord task in the local SQLite database.",
        source_code=CANCEL_DISCORD_SCHEDULE_SOURCE,
        tags=("hannario", "discord", "schedule", "write"),
    ),
]
