import argparse
import json
import re
from pathlib import Path

from dotenv import load_dotenv
from letta_client import Letta

from curator_memory import require_agent_id
from curator_schema import CuratorProposal
from letta_settings import letta_base_url
from preview_memory_apply import append_preview


PLAYBOOK_LINE_PATTERN = re.compile(r"^P\d{3}:\s+\S")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append one reviewed playbook proposal to Letta memory.",
    )
    parser.add_argument(
        "proposal",
        nargs="?",
        help="Full playbook line to append, e.g. 'P006: ...'.",
    )
    parser.add_argument(
        "--proposal-json",
        type=Path,
        help="Path to a curator proposal JSON file. Must be append/playbook.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply without interactive confirmation.",
    )
    return parser.parse_args()


def proposal_from_json_text(text: str) -> str:
    proposal = CuratorProposal.model_validate(json.loads(text))
    if proposal.action != "append" or proposal.target != "playbook" or proposal.proposal is None:
        raise ValueError("Curator proposal JSON must be action=append and target=playbook.")
    return proposal.proposal


def proposal_from_args(args: argparse.Namespace) -> str:
    if args.proposal_json is not None and args.proposal is not None:
        raise ValueError("Use either positional proposal or --proposal-json, not both.")
    if args.proposal_json is None and args.proposal is None:
        raise ValueError("Provide a proposal line or --proposal-json.")
    if args.proposal_json is not None:
        return proposal_from_json_text(args.proposal_json.read_text(encoding="utf-8"))
    return args.proposal


def validate_playbook_append(proposal: str) -> str:
    normalized = proposal.strip()
    if not normalized:
        raise ValueError("Proposal must not be empty.")
    if "\n" in normalized:
        raise ValueError("Proposal must be a single playbook line.")
    if not PLAYBOOK_LINE_PATTERN.match(normalized):
        raise ValueError("Proposal must start with a stable ID like 'P006: ...'.")
    return normalized


def apply_playbook_append(
    current_value: str,
    proposal: str,
) -> str:
    return append_preview(current_value, validate_playbook_append(proposal))


def confirm_apply(proposal: str) -> None:
    confirmation = input(f"Type 'append {proposal.split(':', 1)[0]}' to confirm: ")
    if confirmation != f"append {proposal.split(':', 1)[0]}":
        raise SystemExit("Aborted.")


def main() -> None:
    load_dotenv()
    args = parse_args()
    try:
        proposal = validate_playbook_append(proposal_from_args(args))
    except ValueError as error:
        raise SystemExit(str(error)) from error

    agent_id = require_agent_id()
    client = Letta(base_url=letta_base_url())
    current_block = client.agents.blocks.retrieve(
        agent_id=agent_id,
        block_label="playbook",
    )
    new_value = apply_playbook_append(current_block.value, proposal)

    print(f"agent_id={agent_id}")
    print("block_label=playbook")
    print()
    print("Proposal:")
    print(proposal)
    print()
    print("Preview:")
    print(new_value)
    print()
    print("This will append one line to the playbook block.")

    if not args.yes:
        confirm_apply(proposal)

    updated_block = client.agents.blocks.modify(
        agent_id=agent_id,
        block_label="playbook",
        value=new_value,
    )

    print()
    print("Updated value:")
    print(updated_block.value)


if __name__ == "__main__":
    main()
