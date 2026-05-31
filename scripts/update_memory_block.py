import argparse

from dotenv import load_dotenv
from letta_client import Letta

from curator_memory import require_agent_id
from letta_settings import letta_base_url


ALLOWED_LABELS = {"persona", "playbook", "server_context"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace one Letta agent memory block value.",
    )
    parser.add_argument(
        "label",
        choices=sorted(ALLOWED_LABELS),
        help="Memory block label to replace.",
    )
    parser.add_argument(
        "value",
        help="New full block value. This replaces the entire block.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    new_value = args.value.strip()
    if not new_value:
        raise SystemExit("New value must not be empty.")

    agent_id = require_agent_id()
    client = Letta(base_url=letta_base_url())
    current_block = client.agents.blocks.retrieve(
        agent_id=agent_id,
        block_label=args.label,
    )

    print(f"agent_id={agent_id}")
    print(f"block_label={args.label}")
    print()
    print("Current value:")
    print(current_block.value)
    print()
    print("New value:")
    print(new_value)
    print()
    print("This will replace the entire block value.")

    confirmation = input(f"Type '{args.label}' to confirm: ")
    if confirmation != args.label:
        raise SystemExit("Aborted.")

    updated_block = client.agents.blocks.modify(
        agent_id=agent_id,
        block_label=args.label,
        value=new_value,
    )

    print()
    print("Updated value:")
    print(updated_block.value)


if __name__ == "__main__":
    main()
