import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import discord
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import maybe_post_heartbeat_result
from heartbeat import (
    HeartbeatPostDecision,
    HeartbeatResult,
    append_heartbeat_log,
    decide_heartbeat_post,
    load_heartbeat_config_from_env,
)


DEFAULT_MESSAGE = "heartbeat smoke test"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run or send a manual heartbeat post through the same gate as the bot.",
    )
    parser.add_argument(
        "--channel-id",
        required=True,
        help="Discord channel ID to target.",
    )
    parser.add_argument(
        "--message",
        default=DEFAULT_MESSAGE,
        help="Message to use for the manual heartbeat candidate.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually send to Discord. Without this, only the heartbeat post gate is evaluated.",
    )
    return parser.parse_args()


def build_manual_heartbeat_result(
    channel_id: str,
    message: str,
    *,
    now: datetime | None = None,
) -> HeartbeatResult:
    actual_now = now or datetime.now(UTC)
    if actual_now.tzinfo is None:
        actual_now = actual_now.replace(tzinfo=UTC)

    return HeartbeatResult(
        checked_at=actual_now.astimezone(UTC).isoformat(),
        action="consider_reply",
        reason="manual heartbeat post smoke test",
        channel_id=channel_id,
        message=message,
    )


def print_decision(decision: HeartbeatPostDecision) -> None:
    print(
        "post_decision: "
        f"should_post={decision.should_post} "
        f"reason={decision.reason} "
        f"channel_id={decision.channel_id or '-'}"
    )
    if decision.message:
        print(f"message: {decision.message}")


async def send_manual_heartbeat_post(
    result: HeartbeatResult,
) -> HeartbeatPostDecision:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Missing DISCORD_TOKEN in .env.")

    config = load_heartbeat_config_from_env()
    if not config.post_enabled:
        decision = decide_heartbeat_post(config, result, {})
        print_decision(decision)
        raise SystemExit("Set DISCORD_HEARTBEAT_POST_ENABLED=1 before using --send.")

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    future: asyncio.Future[HeartbeatPostDecision] = asyncio.get_running_loop().create_future()

    @client.event
    async def on_ready() -> None:
        try:
            decision = await maybe_post_heartbeat_result(config, result, client, {})
            append_heartbeat_log(config.log_path, result, decision)
            future.set_result(decision)
        except Exception as error:
            future.set_exception(error)
        finally:
            await client.close()

    await client.start(token, log_handler=None)
    return await future


async def async_main() -> None:
    load_dotenv()
    args = parse_args()
    result = build_manual_heartbeat_result(args.channel_id, args.message)
    config = load_heartbeat_config_from_env()

    if not args.send:
        print("Dry run only. No Discord message was sent.")
        print_decision(decide_heartbeat_post(config, result, {}))
        return

    decision = await send_manual_heartbeat_post(result)
    print_decision(decision)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
