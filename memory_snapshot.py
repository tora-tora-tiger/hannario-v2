import json
from datetime import UTC, datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any

from letta_client import Letta


DEFAULT_SNAPSHOT_DIR = Path("memory_snapshots")


def snapshot_path(
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    *,
    now: datetime | None = None,
) -> Path:
    actual_now = now or datetime.now(UTC)
    if actual_now.tzinfo is None:
        actual_now = actual_now.replace(tzinfo=UTC)
    timestamp = actual_now.astimezone(UTC).isoformat()
    safe_timestamp = timestamp.replace("+00:00", "Z").replace(":", "-")
    return snapshot_dir / f"{safe_timestamp}.json"


def build_snapshot(client: Letta, agent_id: str) -> dict[str, Any]:
    agent = client.agents.retrieve(agent_id, include_relationships="memory")

    blocks = {}
    if agent.memory is not None:
        blocks = {
            block.label: {
                "id": block.id,
                "value": block.value,
            }
            for block in agent.memory.blocks
        }

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "agent_id": agent.id,
        "name": agent.name,
        "blocks": blocks,
    }


def save_snapshot(snapshot: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def capture_snapshot(client: Letta, agent_id: str, snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR) -> Path:
    return save_snapshot(build_snapshot(client, agent_id), snapshot_path(snapshot_dir))


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def block_value(snapshot: dict[str, Any], label: str) -> str:
    block = snapshot.get("blocks", {}).get(label)
    if block is None:
        return ""
    return block.get("value") or ""


def block_diff_text(
    label: str,
    before_value: str,
    after_value: str,
    before_name: str,
    after_name: str,
) -> str:
    if before_value == after_value:
        return ""

    diff = unified_diff(
        before_value.splitlines(),
        after_value.splitlines(),
        fromfile=f"{before_name}:{label}",
        tofile=f"{after_name}:{label}",
        lineterm="",
    )
    return "\n".join([f"## {label}", *diff, ""])


def diff_snapshot_text(
    before: dict[str, Any],
    after: dict[str, Any],
    before_name: str,
    after_name: str,
) -> str:
    labels = sorted(
        set(before.get("blocks", {})) | set(after.get("blocks", {})),
    )
    parts = [
        block_diff_text(
            label,
            block_value(before, label),
            block_value(after, label),
            before_name,
            after_name,
        )
        for label in labels
    ]
    return "\n".join(part for part in parts if part).strip()


def latest_snapshot_paths(snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR) -> tuple[Path, Path] | None:
    snapshots = sorted(snapshot_dir.glob("*.json"))
    if len(snapshots) < 2:
        return None
    return snapshots[-2], snapshots[-1]
