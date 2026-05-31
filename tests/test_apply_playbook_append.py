import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from apply_playbook_append import (
    apply_playbook_append,
    proposal_from_json_text,
    validate_playbook_append,
)


class ApplyPlaybookAppendTest(unittest.TestCase):
    def test_validate_playbook_append(self) -> None:
        self.assertEqual(
            validate_playbook_append(" P006: ユーザーが希望した呼び方を尊重する。 "),
            "P006: ユーザーが希望した呼び方を尊重する。",
        )

    def test_validate_playbook_append_rejects_missing_id(self) -> None:
        with self.assertRaises(ValueError):
            validate_playbook_append("ユーザーが希望した呼び方を尊重する。")

    def test_validate_playbook_append_rejects_multiline(self) -> None:
        with self.assertRaises(ValueError):
            validate_playbook_append("P006: one\nP007: two")

    def test_apply_playbook_append(self) -> None:
        self.assertEqual(
            apply_playbook_append("P001: 既存ルール", "P002: 追加ルール"),
            "P001: 既存ルール\nP002: 追加ルール",
        )

    def test_proposal_from_json_text(self) -> None:
        text = """
        {
          "action": "append",
          "target": "playbook",
          "reason": "durable preference",
          "proposal": "P006: ユーザーが希望した呼び方を尊重する。"
        }
        """

        self.assertEqual(
            proposal_from_json_text(text),
            "P006: ユーザーが希望した呼び方を尊重する。",
        )

    def test_proposal_from_json_text_rejects_none(self) -> None:
        text = """
        {
          "action": "none",
          "target": null,
          "reason": "no durable update",
          "proposal": null
        }
        """

        with self.assertRaises(ValueError):
            proposal_from_json_text(text)


if __name__ == "__main__":
    unittest.main()
