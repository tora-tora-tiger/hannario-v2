from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diff_agent_memory import diff_snapshots, load_snapshot
from memory_snapshot import DEFAULT_SNAPSHOT_DIR


def latest_snapshots(snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR) -> tuple[Path, Path]:
    snapshots = sorted(snapshot_dir.glob("*.json"))
    if len(snapshots) < 2:
        raise SystemExit(
            f"Need at least two snapshots in {snapshot_dir}. "
            "Run scripts/snapshot_agent_memory.py before and after a session."
        )
    return snapshots[-2], snapshots[-1]


def main() -> None:
    before_path, after_path = latest_snapshots()
    before = load_snapshot(before_path)
    after = load_snapshot(after_path)

    print(f"Before: {before_path}")
    print(f"After:  {after_path}")
    print()

    changed = diff_snapshots(before, after, before_path.name, after_path.name)

    if not changed:
        print("No memory block changes.")


if __name__ == "__main__":
    main()
