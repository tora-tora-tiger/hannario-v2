import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from show_recent_heartbeats import print_record, read_recent_records


class RecentHeartbeatsFormatTest(unittest.TestCase):
    def test_read_recent_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "heartbeats.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"checked_at": "1"}),
                        json.dumps({"checked_at": "2"}),
                        json.dumps({"checked_at": "3"}),
                    ]
                ),
                encoding="utf-8",
            )

            records = read_recent_records(path, 2)

        self.assertEqual([record["checked_at"] for record in records], ["2", "3"])

    def test_print_record(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            print_record(
                {
                    "checked_at": "checked",
                    "action": "consider_reply",
                    "reason": "理由",
                    "channel_id": "123",
                    "post_should_post": False,
                    "post_reason": "post_disabled",
                    "message": "hello",
                }
            )

        text = output.getvalue()
        self.assertIn("[checked] action=consider_reply channel_id=123", text)
        self.assertIn("Reason: 理由", text)
        self.assertIn("Post: should_post=False reason=post_disabled", text)
        self.assertIn("Message: hello", text)


if __name__ == "__main__":
    unittest.main()
