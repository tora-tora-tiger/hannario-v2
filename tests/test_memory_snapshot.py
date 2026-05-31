import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from memory_snapshot import (
    block_value,
    diff_snapshot_text,
    latest_snapshot_paths,
    save_snapshot,
    snapshot_path,
)


class MemorySnapshotTest(unittest.TestCase):
    def test_snapshot_path_is_filesystem_safe(self) -> None:
        path = snapshot_path(
            Path("memory_snapshots"),
            now=datetime(2026, 6, 1, 0, 0, 1, tzinfo=UTC),
        )

        self.assertEqual(path, Path("memory_snapshots/2026-06-01T00-00-01Z.json"))

    def test_save_and_load_latest_snapshot_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir)
            first = snapshot_dir / "1.json"
            second = snapshot_dir / "2.json"
            save_snapshot({"created_at": "1"}, first)
            save_snapshot({"created_at": "2"}, second)

            latest = latest_snapshot_paths(snapshot_dir)

        self.assertEqual(latest, (first, second))

    def test_block_value(self) -> None:
        snapshot = {
            "blocks": {
                "playbook": {
                    "value": "P001: hi",
                }
            }
        }

        self.assertEqual(block_value(snapshot, "playbook"), "P001: hi")
        self.assertEqual(block_value(snapshot, "persona"), "")

    def test_diff_snapshot_text(self) -> None:
        before = {"blocks": {"playbook": {"value": "P001: old"}}}
        after = {"blocks": {"playbook": {"value": "P001: new"}}}

        text = diff_snapshot_text(before, after, "before.json", "after.json")

        self.assertIn("## playbook", text)
        self.assertIn("-P001: old", text)
        self.assertIn("+P001: new", text)

    def test_diff_snapshot_text_empty_when_same(self) -> None:
        before = {"blocks": {"playbook": {"value": "P001: same"}}}
        after = {"blocks": {"playbook": {"value": "P001: same"}}}

        self.assertEqual(diff_snapshot_text(before, after, "before.json", "after.json"), "")


if __name__ == "__main__":
    unittest.main()
