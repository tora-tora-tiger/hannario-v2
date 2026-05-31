import argparse
from pathlib import Path

from curator_llm_dry_run import build_proposal
from curator_memory import get_playbook_value
from preview_memory_apply import append_preview
from show_recent_schedule_deliveries import DEFAULT_SCHEDULE_LOG_PATH, read_recent_records
from curate_recent_mentions import write_proposal_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run LLM curator dry-run on recent internal scheduled task results. "
            "Does not write memory."
        ),
    )
    parser.add_argument("--limit", type=int, default=1, help="Number of records to inspect.")
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_SCHEDULE_LOG_PATH,
        help="Path to the schedule delivery JSONL log.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the curator proposal JSON.",
    )
    return parser.parse_args()


def record_to_curator_text(record: dict) -> str:
    lines = [
        "内部予定結果:",
        f"task_id: {record.get('task_id') or '-'}",
        f"kind: {record.get('kind') or '-'}",
        f"channel_id: {record.get('channel_id') or '-'}",
        f"message: {record.get('message') or ''}",
        f"note: {record.get('note') or ''}",
        f"result: {record.get('internal_result') or ''}",
    ]
    return "\n".join(lines)


def records_to_curator_input(records: list[dict]) -> str:
    return "\n\n".join(record_to_curator_text(record) for record in records)


def filter_internal_result_records(records: list[dict]) -> list[dict]:
    return [
        record
        for record in records
        if record.get("internal_result") and record.get("kind") != "post"
    ]


def main() -> None:
    args = parse_args()

    try:
        records = read_recent_records(args.path, args.limit)
    except FileNotFoundError:
        print(f"No schedule delivery log found at {args.path}. Run internal schedule first.")
        return

    records = filter_internal_result_records(records)
    if not records:
        print("No internal result records found.")
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
