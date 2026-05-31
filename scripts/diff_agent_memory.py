import argparse
import json
from difflib import unified_diff
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diff two memory snapshot JSON files.",
    )
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    return parser.parse_args()


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def block_value(snapshot: dict[str, Any], label: str) -> str:
    block = snapshot.get("blocks", {}).get(label)
    if block is None:
        return ""
    return block.get("value") or ""


def print_block_diff(
    label: str,
    before_value: str,
    after_value: str,
    before_name: str,
    after_name: str,
) -> bool:
    if before_value == after_value:
        return False

    print(f"## {label}")
    diff = unified_diff(
        before_value.splitlines(),
        after_value.splitlines(),
        fromfile=f"{before_name}:{label}",
        tofile=f"{after_name}:{label}",
        lineterm="",
    )
    for line in diff:
        print(line)
    print()
    return True


def main() -> None:
    args = parse_args()
    before = load_snapshot(args.before)
    after = load_snapshot(args.after)

    labels = sorted(
        set(before.get("blocks", {})) | set(after.get("blocks", {})),
    )
    changed = False

    for label in labels:
        changed = print_block_diff(
            label,
            block_value(before, label),
            block_value(after, label),
            args.before.name,
            args.after.name,
        ) or changed

    if not changed:
        print("No memory block changes.")


if __name__ == "__main__":
    main()
