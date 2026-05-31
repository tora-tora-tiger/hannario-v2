# hannario-v2

Small Discord companion bot for a single private server.

## Current Architecture

```text
Discord
  -> bot.py
      -> Letta server (Docker Compose)
          -> OpenAI model + embedding
          -> Docker volume
```

- `bot.py` owns Discord I/O.
- Letta owns agent state, message history, and memory blocks.
- OpenAI keys are only passed to the Letta server.
- Letta data is stored in the Docker volume `hannario-v2_letta_pgdata`.

## Setup

This project uses `uv` with Python 3.12.

```sh
uv sync
cp .env.example .env
cp .env.letta.example .env.letta
```

Set `DISCORD_TOKEN` in `.env`.

Set `OPENAI_API_KEY` in `.env.letta`. Do not wrap the value in quotes.

In the Discord Developer Portal, enable the bot's **Message Content Intent**.

## Start Letta

```sh
docker compose up -d letta
```

Useful commands:

```sh
docker compose logs -f letta
docker compose down
```

The local Letta URL is `http://localhost:8283`.

## Verify Letta

With the Letta server running:

```sh
uv run python scripts/smoke_letta.py
```

The smoke test creates a throwaway agent and sends one message using:

- `openai/gpt-4o-mini`
- `openai/text-embedding-3-small`

## Create The Discord Agent

With the Letta server running:

```sh
uv run python scripts/create_agent.py
```

Copy the printed `LETTA_AGENT_ID=...` line into `.env`.

To inspect the agent's current memory blocks:

```sh
uv run python scripts/show_agent_memory.py
```

## Run The Bot

Make sure `.env` contains:

```env
DISCORD_TOKEN=...
LETTA_BASE_URL=http://localhost:8283
LETTA_AGENT_ID=...
```

Then run:

```sh
uv run python bot.py
```

## Current Behavior

- `!ping` replies with `pong`.
- Mentioning the bot sends the cleaned Discord message context to Letta.
- The bot replies in the same channel.
- The bot ignores messages from itself and other bots.
- If Letta fails, the bot sends a short fallback reply instead of crashing.

## Not Implemented Yet

- Curator or memory write gate.
- Heartbeat or scheduled autonomous actions.
- Discord API tools beyond reading messages and sending replies.
- Web or database tools.
- Deployment or process supervision.
