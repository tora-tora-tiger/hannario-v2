import json
import tempfile
import unittest
from pathlib import Path

from letta_agent import LettaToolEvent
from memory_audit import (
    append_memory_write_audit,
    audit_record,
    has_memory_write_tool_call,
    is_memory_write_tool_name,
    memory_write_tool_calls,
)


class MemoryAuditTest(unittest.TestCase):
    def test_is_memory_write_tool_name(self) -> None:
        self.assertTrue(is_memory_write_tool_name("memory_insert"))
        self.assertTrue(is_memory_write_tool_name("memory_replace"))
        self.assertFalse(is_memory_write_tool_name("memory_search"))
        self.assertFalse(is_memory_write_tool_name("list_observed_discord_channels"))

    def test_memory_write_tool_calls(self) -> None:
        events = [
            LettaToolEvent(kind="call", name="memory_insert", arguments="{}"),
            LettaToolEvent(kind="return", name="memory_insert"),
            LettaToolEvent(kind="call", name="memory_search", arguments="{}"),
        ]

        calls = memory_write_tool_calls(events)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "memory_insert")
        self.assertTrue(has_memory_write_tool_call(events))

    def test_audit_record(self) -> None:
        events = [
            LettaToolEvent(kind="call", name="memory_replace", arguments='{"label":"playbook"}'),
        ]

        record = audit_record(123, events, Path("memory_snapshots/a.json"), "diff")

        self.assertEqual(record["discord_message_id"], "123")
        self.assertEqual(record["memory_write_tools"][0]["name"], "memory_replace")
        self.assertEqual(record["snapshot_path"], "memory_snapshots/a.json")
        self.assertEqual(record["diff"], "diff")

    def test_append_memory_write_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit.jsonl"
            append_memory_write_audit(path, {"discord_message_id": "123"})

            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(records, [{"discord_message_id": "123"}])


if __name__ == "__main__":
    unittest.main()
