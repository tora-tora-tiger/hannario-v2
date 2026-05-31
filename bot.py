import asyncio
import logging
import os
from typing import Any

import discord
from dotenv import load_dotenv
from letta_client import Letta

from letta_agent import ask_letta


COMMAND_PREFIX = "!"
DEFAULT_LETTA_BASE_URL = "http://localhost:8283"
LETTA_ERROR_REPLY = "ごめん、今ちょっと考える側につながらない。"


def should_ignore_message(message: discord.Message, bot_user: discord.ClientUser) -> bool:
    return message.author == bot_user or message.author.bot


def is_ping_command(message: discord.Message) -> bool:
    return message.content.strip() == f"{COMMAND_PREFIX}ping"


def is_mentioned(message: discord.Message, bot_user: discord.ClientUser) -> bool:
    return bot_user in message.mentions


class HannarioClient(discord.Client):
    def __init__(self, *, letta_client: Letta, letta_agent_id: str | None, **kwargs: Any):
        super().__init__(**kwargs)
        self.letta_client = letta_client
        self.letta_agent_id = letta_agent_id

    async def on_ready(self) -> None:
        if self.user is None:
            return

        logging.info("Logged in as %s (id=%s)", self.user, self.user.id)

    async def on_message(self, message: discord.Message) -> None:
        if self.user is None:
            return

        if should_ignore_message(message, self.user):
            return

        if is_ping_command(message):
            await message.channel.send("pong")
            return

        if not is_mentioned(message, self.user):
            return

        channel_name = getattr(message.channel, "name", "direct-message")
        logging.info(
            "Received mention from %s (%s) in #%s (%s)",
            message.author.display_name,
            message.author.id,
            channel_name,
            message.channel.id,
        )

        if self.letta_agent_id is None:
            logging.warning("Cannot reply because LETTA_AGENT_ID is not set")
            await message.reply("LETTA_AGENT_ID がまだ設定されていません。", mention_author=False)
            return

        async with message.channel.typing():
            try:
                reply = await asyncio.wait_for(
                    asyncio.to_thread(
                        ask_letta,
                        self.letta_client,
                        self.letta_agent_id,
                        message,
                        self.user,
                    ),
                    timeout=45,
                )
            except Exception:
                logging.exception("Failed to get Letta reply")
                reply = LETTA_ERROR_REPLY
            else:
                logging.info(
                    "Received Letta reply for Discord message %s (%d chars)",
                    message.id,
                    len(reply),
                )

        await message.reply(reply, mention_author=False)


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Missing DISCORD_TOKEN. Create .env from .env.example.")

    intents = discord.Intents.default()
    intents.message_content = True

    letta_client = Letta(base_url=os.getenv("LETTA_BASE_URL", DEFAULT_LETTA_BASE_URL))
    letta_agent_id = os.getenv("LETTA_AGENT_ID")

    client = HannarioClient(
        intents=intents,
        letta_client=letta_client,
        letta_agent_id=letta_agent_id,
    )
    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
