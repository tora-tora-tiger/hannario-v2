import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.check_deploy_readiness import check_env, is_placeholder_env_value


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


if __name__ == "__main__":
    unittest.main()
