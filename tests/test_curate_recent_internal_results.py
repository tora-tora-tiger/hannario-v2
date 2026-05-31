import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from curate_recent_internal_results import (
    filter_internal_result_records,
    record_to_curator_text,
    records_to_curator_input,
)


class CurateRecentInternalResultsTest(unittest.TestCase):
    def test_record_to_curator_text(self) -> None:
        text = record_to_curator_text(
            {
                "task_id": 7,
                "kind": "think",
                "channel_id": "123",
                "message": "internal",
                "note": "考える",
                "internal_result": "考えた",
            }
        )

        self.assertIn("内部予定結果:", text)
        self.assertIn("kind: think", text)
        self.assertIn("note: 考える", text)
        self.assertIn("result: 考えた", text)

    def test_records_to_curator_input(self) -> None:
        text = records_to_curator_input(
            [
                {"task_id": 1, "kind": "think", "internal_result": "one"},
                {"task_id": 2, "kind": "observe", "internal_result": "two"},
            ]
        )

        self.assertIn("task_id: 1", text)
        self.assertIn("task_id: 2", text)
        self.assertIn("\n\n", text)

    def test_filter_internal_result_records(self) -> None:
        records = filter_internal_result_records(
            [
                {"kind": "post", "internal_result": "skip"},
                {"kind": "think", "internal_result": ""},
                {"kind": "think", "internal_result": "keep"},
            ]
        )

        self.assertEqual(records, [{"kind": "think", "internal_result": "keep"}])


if __name__ == "__main__":
    unittest.main()
