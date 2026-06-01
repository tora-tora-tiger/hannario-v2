from __future__ import annotations

import os
import shutil
import socket
import sqlite3
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hannario.schedule_db import db_path_from_env, initialize_database


REQUIRED_ENV = ("DISCORD_TOKEN", "LETTA_BASE_URL", "LETTA_AGENT_ID", "OPENAI_API_KEY")
RECOMMENDED_PATHS = ("logs", "data", "memory_snapshots")
PLACEHOLDER_ENV_VALUES = {
    "your_discord_bot_token_here",
    "your_letta_agent_id_here",
    "your_openai_api_key_here",
    "...",
}


def status_line(ok: bool, label: str, detail: str = "") -> str:
    prefix = "OK" if ok else "FAIL"
    if detail:
        return f"[{prefix}] {label}: {detail}"
    return f"[{prefix}] {label}"


def check_command(name: str) -> bool:
    path = shutil.which(name)
    print(status_line(path is not None, f"command {name}", path or "not found"))
    return path is not None


def check_optional_command(name: str) -> None:
    path = shutil.which(name)
    prefix = "OK" if path else "WARN"
    detail = path or "not found"
    print(f"[{prefix}] optional command {name}: {detail}")


def check_env() -> bool:
    ok = True
    for name in REQUIRED_ENV:
        value = os.getenv(name)
        present = bool(value)
        placeholder = is_placeholder_env_value(value)
        valid = present and not placeholder
        ok = ok and valid
        if not present:
            detail = "missing"
        elif placeholder:
            detail = "placeholder"
        else:
            detail = "set"
        print(status_line(valid, f"env {name}", detail))
    return ok


def is_placeholder_env_value(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip() in PLACEHOLDER_ENV_VALUES


def check_paths() -> bool:
    ok = True
    for raw_path in RECOMMENDED_PATHS:
        path = Path(raw_path)
        valid, detail = check_writable_directory(path)
        ok = ok and valid
        print(status_line(valid, f"path {raw_path}", detail))
    return ok


def check_writable_directory(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    if not path.is_dir():
        return False, "not a directory"
    if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
        return False, "not writable"
    return True, "writable directory"


def check_sqlite() -> bool:
    db_path = db_path_from_env()
    try:
        initialize_database(db_path)
        with sqlite3.connect(db_path) as connection:
            connection.execute("SELECT COUNT(*) FROM scheduled_tasks").fetchone()
    except sqlite3.Error as exc:
        print(status_line(False, "sqlite", str(exc)))
        return False

    print(status_line(True, "sqlite", str(db_path)))
    return True


def check_letta() -> bool:
    base_url = (os.getenv("LETTA_BASE_URL") or "").rstrip("/")
    if not base_url:
        print(status_line(False, "letta http", "LETTA_BASE_URL missing"))
        return False

    request = Request(f"{base_url}/v1/health")
    try:
        with urlopen(request, timeout=5) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except URLError as exc:
        print(status_line(False, "letta http", str(exc)))
        return False
    except (ConnectionResetError, TimeoutError, socket.timeout) as exc:
        print(status_line(False, "letta http", str(exc)))
        return False

    ok = 200 <= status < 500
    print(status_line(ok, "letta http", f"status={status}"))
    return ok


def main() -> None:
    load_dotenv()
    load_dotenv(".env.letta")

    checks = [
        check_command("uv"),
        check_command("python3"),
        check_env(),
        check_paths(),
        check_sqlite(),
        check_letta(),
    ]
    check_optional_command("docker")

    if not all(checks):
        raise SystemExit(1)

    print("Deploy readiness checks passed.")


if __name__ == "__main__":
    main()
