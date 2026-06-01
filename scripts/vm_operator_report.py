from __future__ import annotations

import argparse
import shlex
import subprocess


DEFAULT_HOST = "172.17.2.4"
DEFAULT_REPO_PATH = "/home/keitaito/hannario-v2"
REPORT_COMMANDS = {
    "summary": "scripts/operator_report.py",
    "quality": "scripts/operator_quality_review.py",
    "recommendations": "scripts/operator_recommendations.py",
}
REPORTS_WITH_LIMIT = {"summary", "quality"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run read-only operator reports on the VM over non-interactive SSH.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    parser.add_argument("--connect-timeout", type=int, default=5)
    parser.add_argument(
        "--report",
        choices=sorted(REPORT_COMMANDS),
        default="summary",
        help="Which remote operator report to run.",
    )
    parser.add_argument("--since", default="24h")
    parser.add_argument("--limit", type=int, default=12)
    return parser.parse_args()


def build_remote_command(repo_path: str, report: str, since: str, limit: int) -> str:
    script = REPORT_COMMANDS[report]
    repo = shlex.quote(repo_path)
    quoted_script = shlex.quote(script)
    quoted_since = shlex.quote(since)
    quoted_limit = shlex.quote(str(limit))
    report_args = f"--since {quoted_since}"
    if report in REPORTS_WITH_LIMIT:
        report_args = f"{report_args} --limit {quoted_limit}"

    return "\n".join(
        [
            "set -eu",
            f"repo={repo}",
            'if ! test -d "$repo"; then',
            '  printf "repo_missing=%s\\n" "$repo"',
            "  exit 2",
            "fi",
            'cd "$repo"',
            "if ! command -v uv >/dev/null 2>&1; then",
            '  printf "uv_missing=1\\n"',
            "  exit 3",
            "fi",
            f"uv run python {quoted_script} {report_args}",
        ]
    )


def run_remote_report(host: str, command_text: str, connect_timeout: int) -> int:
    remote_command = "sh -lc " + shlex.quote(command_text)
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        host,
        remote_command,
    ]
    completed = subprocess.run(command, text=True, check=False)
    return completed.returncode


def main() -> None:
    args = parse_args()
    command = build_remote_command(args.repo_path, args.report, args.since, args.limit)
    raise SystemExit(run_remote_report(args.host, command, args.connect_timeout))


if __name__ == "__main__":
    main()
