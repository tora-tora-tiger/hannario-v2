import io
import tempfile
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from curator_schema import CuratorProposal
from curate_recent_mentions import record_to_curator_text, write_proposal_json
from show_recent_mentions import print_curator_input, print_record


class RecentMentionsFormatTest(unittest.TestCase):
    def setUp(self) -> None:
        self.record = {
            "timestamp": "2026-05-31T00:00:00+00:00",
            "channel_name": "general",
            "author_display_name": "alice",
            "clean_content": "今の話は？",
            "bot_reply": "ラーメンの話です",
            "recent_context": [
                {
                    "author_display_name": "bob",
                    "clean_content": "今日はラーメンの話をしています",
                }
            ],
        }

    def test_print_record_includes_recent_context(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            print_record(self.record)

        text = output.getvalue()
        self.assertIn("Context:", text)
        self.assertIn("- bob: 今日はラーメンの話をしています", text)
        self.assertIn("User: 今の話は？", text)

    def test_print_curator_input_includes_recent_context(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            print_curator_input(self.record)

        text = output.getvalue()
        self.assertIn("直近文脈:", text)
        self.assertIn("- bob: 今日はラーメンの話をしています", text)
        self.assertIn("ユーザー: 今の話は？", text)

    def test_curator_text_includes_recent_context(self) -> None:
        text = record_to_curator_text(self.record)

        self.assertIn("直近文脈:", text)
        self.assertIn("- bob: 今日はラーメンの話をしています", text)
        self.assertIn("Bot: ラーメンの話です", text)

    def test_curator_proposal_json_can_be_written(self) -> None:
        proposal = CuratorProposal(
            action="none",
            target=None,
            reason="no durable update",
            proposal=None,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "proposal.json"
            write_proposal_json(path, proposal.model_dump_json(indent=2))

            text = path.read_text(encoding="utf-8")

        self.assertIn('"action": "none"', text)
        self.assertTrue(text.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
