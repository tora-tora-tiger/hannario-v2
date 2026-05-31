import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memory_snapshot import block_value, diff_snapshot_text, load_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diff two memory snapshot JSON files.",
    )
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    return parser.parse_args()


def print_block_diff(
    label: str,
    before_value: str,
    after_value: str,
    before_name: str,
    after_name: str,
) -> bool:
    text = diff_snapshot_text(
        {"blocks": {label: {"value": before_value}}},
        {"blocks": {label: {"value": after_value}}},
        before_name,
        after_name,
    )
    if not text:
        return False
    print(text)
    print()
    return True


def diff_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
    before_name: str,
    after_name: str,
) -> bool:
    labels = sorted(
        set(before.get("blocks", {})) | set(after.get("blocks", {})),
    )
    changed = False

    for label in labels:
        changed = print_block_diff(
            label,
            block_value(before, label),
            block_value(after, label),
            before_name,
            after_name,
        ) or changed

    return changed


def main() -> None:
    args = parse_args()
    before = load_snapshot(args.before)
    after = load_snapshot(args.after)
    changed = diff_snapshots(before, after, args.before.name, args.after.name)

    if not changed:
        print("No memory block changes.")


if __name__ == "__main__":
    main()
