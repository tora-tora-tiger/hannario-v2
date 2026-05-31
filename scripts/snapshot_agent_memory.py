import sys
from pathlib import Path

from dotenv import load_dotenv
from letta_client import Letta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from curator_memory import require_agent_id
from letta_settings import letta_base_url
from memory_snapshot import build_snapshot, save_snapshot, snapshot_path


def build_agent_snapshot() -> dict:
    load_dotenv()

    client = Letta(base_url=letta_base_url())
    return build_snapshot(client, require_agent_id())


def main() -> None:
    path = snapshot_path()
    save_snapshot(build_agent_snapshot(), path)
    print(path)


if __name__ == "__main__":
    main()
