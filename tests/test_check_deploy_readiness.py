import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.check_deploy_readiness import (
    check_env,
    check_writable_directory,
    is_placeholder_env_value,
)


class CheckDeployReadinessTest(unittest.TestCase):
    def test_placeholder_env_values_are_detected(self):
        self.assertTrue(is_placeholder_env_value("your_discord_bot_token_here"))
        self.assertTrue(is_placeholder_env_value("your_letta_agent_id_here"))
        self.assertTrue(is_placeholder_env_value("your_openai_api_key_here"))
        self.assertFalse(is_placeholder_env_value("real-looking-value"))
        self.assertFalse(is_placeholder_env_value(None))

    def test_check_env_requires_all_runtime_secrets_without_printing_values(self):
        env = {
            "DISCORD_TOKEN": "discord-token",
            "LETTA_BASE_URL": "http://localhost:8283",
            "LETTA_AGENT_ID": "agent-123",
            "OPENAI_API_KEY": "sk-test",
        }
        output = io.StringIO()

        with patch.dict(os.environ, env, clear=True), redirect_stdout(output):
            ok = check_env()

        self.assertTrue(ok)
        rendered = output.getvalue()
        self.assertIn("[OK] env DISCORD_TOKEN: set", rendered)
        self.assertIn("[OK] env OPENAI_API_KEY: set", rendered)
        self.assertNotIn("discord-token", rendered)
        self.assertNotIn("sk-test", rendered)

    def test_check_env_rejects_placeholders(self):
        env = {
            "DISCORD_TOKEN": "your_discord_bot_token_here",
            "LETTA_BASE_URL": "http://localhost:8283",
            "LETTA_AGENT_ID": "your_letta_agent_id_here",
            "OPENAI_API_KEY": "your_openai_api_key_here",
        }
        output = io.StringIO()

        with patch.dict(os.environ, env, clear=True), redirect_stdout(output):
            ok = check_env()

        self.assertFalse(ok)
        rendered = output.getvalue()
        self.assertIn("[FAIL] env DISCORD_TOKEN: placeholder", rendered)
        self.assertIn("[FAIL] env LETTA_AGENT_ID: placeholder", rendered)
        self.assertIn("[FAIL] env OPENAI_API_KEY: placeholder", rendered)

    def test_check_writable_directory_reports_missing_path(self):
        ok, detail = check_writable_directory(Path("missing-path"))

        self.assertFalse(ok)
        self.assertEqual(detail, "missing")

    def test_check_writable_directory_accepts_writable_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ok, detail = check_writable_directory(Path(temp_dir))

        self.assertTrue(ok)
        self.assertEqual(detail, "writable directory")

    def test_check_writable_directory_rejects_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "file"
            path.write_text("content", encoding="utf-8")

            ok, detail = check_writable_directory(path)

        self.assertFalse(ok)
        self.assertEqual(detail, "not a directory")


if __name__ == "__main__":
    unittest.main()
