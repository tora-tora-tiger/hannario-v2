import tempfile
import unittest
from pathlib import Path

from letta_discord_tools import LETTA_DISCORD_TOOL_SPECS


def load_function(source_code: str, function_name: str, log_dir: Path):
    namespace = {"LOG_DIR": str(log_dir)}
    exec(source_code, namespace)
    return namespace[function_name]


class LettaDiscordToolsTest(unittest.TestCase):
    def test_tool_names_are_unique(self) -> None:
        names = [spec.name for spec in LETTA_DISCORD_TOOL_SPECS]

        self.assertEqual(len(names), len(set(names)))

    def test_list_observed_discord_channels_source(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "discord_observations.jsonl").write_text(
                "\n".join(
                    [
                        '{"channel_id":"1","channel_name":"general","timestamp":"2026-05-31T00:00:00+00:00","author_display_name":"alice"}',
                        '{"channel_id":"1","channel_name":"general","timestamp":"2026-05-31T00:01:00+00:00","author_display_name":"bob"}',
                    ]
                ),
                encoding="utf-8",
            )
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "list_observed_discord_channels"
            )
            function = load_function(spec.source_code, spec.name, temp_dir)

            result = function()

            self.assertIn("#general (1): 2 observations", result)
            self.assertIn("latest_author=bob", result)
        finally:
            (temp_dir / "discord_observations.jsonl").unlink(missing_ok=True)
            temp_dir.rmdir()

    def test_get_recent_discord_observations_source(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "discord_observations.jsonl").write_text(
                (
                    '{"channel_id":"1","channel_name":"general",'
                    '"timestamp":"2026-05-31T00:00:00+00:00",'
                    '"author_display_name":"alice","author_id":"111",'
                    '"clean_content":"こんにちは"}'
                ),
                encoding="utf-8",
            )
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "get_recent_discord_observations"
            )
            function = load_function(spec.source_code, spec.name, temp_dir)

            result = function("1", 10)

            self.assertIn("observed_same_channel_context_oldest_first:", result)
            self.assertIn("alice (111): こんにちは", result)
        finally:
            (temp_dir / "discord_observations.jsonl").unlink(missing_ok=True)
            temp_dir.rmdir()

    def test_get_latest_discord_channel_summary_source(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "channel_summaries.jsonl").write_text(
                (
                    '{"channel_id":"1","channel_name":"general",'
                    '"created_at":"created","first_observed_at":"first",'
                    '"last_observed_at":"last","record_count":2,"summary":"要約"}'
                ),
                encoding="utf-8",
            )
            spec = next(
                spec
                for spec in LETTA_DISCORD_TOOL_SPECS
                if spec.name == "get_latest_discord_channel_summary"
            )
            function = load_function(spec.source_code, spec.name, temp_dir)

            result = function("1")

            self.assertIn("latest_same_channel_summary:", result)
            self.assertIn("Use this only as older background", result)
            self.assertIn("要約", result)
        finally:
            (temp_dir / "channel_summaries.jsonl").unlink(missing_ok=True)
            temp_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
