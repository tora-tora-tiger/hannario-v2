import argparse
from pathlib import Path

from curator_llm_dry_run import build_proposal
from curator_memory import get_playbook_value
from preview_memory_apply import append_preview
from show_recent_mentions import DEFAULT_LOG_PATH, read_recent_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run LLM curator dry-run on recent mention logs. Does not write memory.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Number of recent mention records to include.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Path to the mention JSONL log.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the curator proposal JSON.",
    )
    return parser.parse_args()


def record_to_curator_text(record: dict) -> str:
    user_text = record.get("clean_content") or ""
    bot_reply = record.get("bot_reply") or ""
    recent_context = record.get("recent_context") or []
    lines = []

    if recent_context:
        lines.append("直近文脈:")
        for item in recent_context:
            item_author = (
                item.get("author_display_name")
                or item.get("author_id")
                or "unknown-author"
            )
            item_text = item.get("clean_content") or ""
            lines.append(f"- {item_author}: {item_text}")

    lines.extend([f"ユーザー: {user_text}", f"Bot: {bot_reply}"])
    return "\n".join(lines)


def records_to_curator_input(records: list[dict]) -> str:
    return "\n\n".join(record_to_curator_text(record) for record in records)


def write_proposal_json(path: Path, proposal_json: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{proposal_json.rstrip()}\n", encoding="utf-8")


def main() -> None:
    args = parse_args()

    try:
        records = read_recent_records(args.path, args.limit)
    except FileNotFoundError:
        print(f"No mention log found at {args.path}. Run the bot and mention it first.")
        return

    if not records:
        print(f"No mention records found in {args.path}.")
        return

    curator_input = records_to_curator_input(records)
    proposal = build_proposal(curator_input)

    print("Curator input:")
    print(curator_input)
    print()
    print("Proposal:")
    proposal_json = proposal.model_dump_json(indent=2)
    print(proposal_json)

    if args.output is not None:
        write_proposal_json(args.output, proposal_json)
        print()
        print(f"Wrote proposal JSON to {args.output}")

    if proposal.action == "append" and proposal.proposal is not None:
        preview = append_preview(get_playbook_value(), proposal.proposal)
        print()
        print("Playbook preview:")
        print(preview)

    print()
    print("No memory was written.")


if __name__ == "__main__":
    main()
