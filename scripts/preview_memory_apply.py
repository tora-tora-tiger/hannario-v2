import argparse

from curator_memory import get_playbook_value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview appending one playbook proposal. Does not write memory.",
    )
    parser.add_argument(
        "proposal",
        help="Full playbook line to append, e.g. 'P006: ...'.",
    )
    return parser.parse_args()


def append_preview(current_value: str, proposal: str) -> str:
    proposal = proposal.strip()
    if not proposal:
        raise ValueError("Proposal must not be empty.")

    if not current_value.strip():
        return proposal

    return f"{current_value.rstrip()}\n{proposal}"


def main() -> None:
    args = parse_args()
    current_value = get_playbook_value()
    preview_value = append_preview(current_value, args.proposal)

    print("Current playbook:")
    print(current_value)
    print()
    print("Preview:")
    print(preview_value)
    print()
    print("No memory was written.")


if __name__ == "__main__":
    main()
