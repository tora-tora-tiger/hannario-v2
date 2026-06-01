import unittest

from scripts.vm_operator_report import build_remote_command


class VmOperatorReportTest(unittest.TestCase):
    def test_build_remote_command_runs_selected_report(self):
        command = build_remote_command(
            "/srv/hannario-v2",
            "quality",
            "6h",
            20,
        )

        self.assertIn("repo=/srv/hannario-v2", command)
        self.assertIn("scripts/operator_quality_review.py", command)
        self.assertIn("--since 6h", command)
        self.assertIn("--limit 20", command)

    def test_build_remote_command_fails_safely_when_repo_or_uv_missing(self):
        command = build_remote_command(
            "/srv/hannario-v2",
            "summary",
            "24h",
            12,
        )

        self.assertIn("repo_missing=", command)
        self.assertIn("uv_missing=1", command)
        self.assertIn("exit 2", command)
        self.assertIn("exit 3", command)

    def test_build_remote_command_avoids_vm_writes(self):
        command = build_remote_command(
            "/srv/hannario-v2",
            "recommendations",
            "24h",
            12,
        )

        forbidden = [
            "sudo",
            "apt ",
            "install",
            "mkdir",
            "cp ",
            "rm ",
            "systemctl",
            "docker compose up",
            "docker compose down",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, command)

    def test_build_remote_command_omits_limit_for_recommendations(self):
        command = build_remote_command(
            "/srv/hannario-v2",
            "recommendations",
            "24h",
            12,
        )

        self.assertIn("scripts/operator_recommendations.py", command)
        self.assertIn("--since 24h", command)
        self.assertNotIn("--limit", command)


if __name__ == "__main__":
    unittest.main()
