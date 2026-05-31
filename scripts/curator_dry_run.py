import argparse
import json
import os
import re

from dotenv import load_dotenv
from letta_client import Letta

from letta_settings import letta_base_url


CANDIDATE_KEYWORDS = (
    "覚えて",
    "今後",
    "呼んで",
    "呼ぶ",
    "やめて",
    "嫌",
    "苦手",
)
PLAYBOOK_ID_PATTERN = re.compile(r"^P(?P<number>\d{3}):", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a dry-run memory update proposal. Does not write memory.",
    )
    parser.add_argument(
        "conversation",
        help="Conversation text to inspect.",
    )
    return parser.parse_args()


def next_playbook_id(playbook_value: str) -> str:
    numbers = [
        int(match.group("number"))
        for match in PLAYBOOK_ID_PATTERN.finditer(playbook_value)
    ]
    next_number = max(numbers, default=0) + 1
    return f"P{next_number:03d}"


def get_playbook_value() -> str:
    load_dotenv()

    agent_id = os.getenv("LETTA_AGENT_ID")
    if not agent_id:
        raise SystemExit("Missing LETTA_AGENT_ID. Add it to .env first.")

    client = Letta(base_url=letta_base_url())
    block = client.agents.blocks.retrieve(
        agent_id=agent_id,
        block_label="playbook",
    )
    return block.value


def build_proposal(conversation: str, playbook_value: str) -> dict[str, str | None]:
    if any(keyword in conversation for keyword in CANDIDATE_KEYWORDS):
        playbook_id = next_playbook_id(playbook_value)
        return {
            "action": "append",
            "target": "playbook",
            "reason": "The conversation contains a possible durable preference signal.",
            "proposal": f"{playbook_id}: TODO: write proposal manually.",
        }

    return {
        "action": "none",
        "target": None,
        "reason": "No obvious durable memory update signal was detected by the stub.",
        "proposal": None,
    }


def main() -> None:
    args = parse_args()
    playbook_value = get_playbook_value()
    proposal = build_proposal(args.conversation, playbook_value)
    print(json.dumps(proposal, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
