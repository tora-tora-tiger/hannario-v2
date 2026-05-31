import json
from pathlib import Path
from typing import Any

from letta_client import Letta

from letta_agent import LettaToolEvent
from memory_snapshot import (
    DEFAULT_SNAPSHOT_DIR,
    capture_snapshot,
    diff_snapshot_text,
    latest_snapshot_paths,
    load_snapshot,
)


DEFAULT_MEMORY_WRITE_AUDIT_LOG_PATH = Path("logs/letta_memory_writes.jsonl")
MEMORY_READ_TOOL_NAMES = {
    "memory_search",
    "memory_retrieve",
    "memory_read",
    "memory_get",
}


def is_memory_write_tool_name(name: str) -> bool:
    normalized = name.strip()
    return normalized.startswith("memory_") and normalized not in MEMORY_READ_TOOL_NAMES


def memory_write_tool_calls(events: list[LettaToolEvent]) -> list[LettaToolEvent]:
    return [
        event
        for event in events
        if event.kind == "call" and is_memory_write_tool_name(event.name)
    ]


def has_memory_write_tool_call(events: list[LettaToolEvent]) -> bool:
    return bool(memory_write_tool_calls(events))


def audit_record(
    discord_message_id: int,
    events: list[LettaToolEvent],
    snapshot_path: Path | None,
    diff_text: str,
) -> dict[str, Any]:
    return {
        "discord_message_id": str(discord_message_id),
        "memory_write_tools": [
            {
                "name": event.name,
                "arguments": event.arguments,
            }
            for event in memory_write_tool_calls(events)
        ],
        "snapshot_path": str(snapshot_path) if snapshot_path is not None else None,
        "diff": diff_text,
    }


def append_memory_write_audit(
    path: Path,
    record: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        file.write("\n")


def capture_memory_write_snapshot_and_diff(
    client: Letta,
    agent_id: str,
    *,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> tuple[Path, str]:
    snapshot = capture_snapshot(client, agent_id, snapshot_dir)
    latest = latest_snapshot_paths(snapshot_dir)
    if latest is None:
        return snapshot, ""

    before_path, after_path = latest
    if after_path != snapshot:
        return snapshot, ""

    diff_text = diff_snapshot_text(
        load_snapshot(before_path),
        load_snapshot(after_path),
        before_path.name,
        after_path.name,
    )
    return snapshot, diff_text


def audit_memory_write_events(
    client: Letta,
    agent_id: str,
    discord_message_id: int,
    events: list[LettaToolEvent],
    *,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    audit_log_path: Path = DEFAULT_MEMORY_WRITE_AUDIT_LOG_PATH,
) -> dict[str, Any] | None:
    if not has_memory_write_tool_call(events):
        return None

    snapshot, diff_text = capture_memory_write_snapshot_and_diff(
        client,
        agent_id,
        snapshot_dir=snapshot_dir,
    )
    record = audit_record(discord_message_id, events, snapshot, diff_text)
    append_memory_write_audit(audit_log_path, record)
    return record
