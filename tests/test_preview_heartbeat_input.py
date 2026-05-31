import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from preview_heartbeat_input import parse_args


class PreviewHeartbeatInputTest(unittest.TestCase):
    def test_parse_args_defaults(self) -> None:
        original_argv = sys.argv
        try:
            sys.argv = ["preview_heartbeat_input.py"]
            args = parse_args()
        finally:
            sys.argv = original_argv

        self.assertEqual(args.limit, 20)
        self.assertEqual(args.path, Path("logs/discord_observations.jsonl"))
        self.assertEqual(args.internal_result_limit, 3)
        self.assertEqual(args.schedule_log_path, Path("logs/scheduled_tasks.jsonl"))


if __name__ == "__main__":
    unittest.main()
