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
- `discord_context.py` formats Discord messages for Letta.
- `letta_agent.py` owns Letta message calls and response extraction.
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

To manually replace one memory block:

```sh
uv run python scripts/update_memory_block.py playbook "New full playbook text"
```

This replaces the entire block value. It is not an append operation.

## Memory Operating Rules

- Current default: allow Letta's conversational agent to update its own memory.
- `playbook` entries use stable IDs like `P001`.
- Prefer append or targeted edits conceptually; avoid rewriting the whole playbook casually.
- `scripts/update_memory_block.py` performs a full replacement.
- Curator scripts are advisory tools for inspection and manual review.
- If memory drift becomes a problem, make memory blocks read-only and route writes through a gate.

See [docs/curator_design.md](docs/curator_design.md) for the curator and
optional write gate design.
See [docs/curator_examples.md](docs/curator_examples.md) for expected curator
behavior examples.
Machine-readable curator examples live in `data/curator_examples.jsonl`.

To test the current curator dry-run stub:

```sh
uv run python scripts/curator_dry_run.py "ユーザー: 今後はたろうって呼んで"
```

To evaluate the rule-based curator stub against the example data:

```sh
uv run python scripts/eval_curator_stub.py
```

To evaluate the LLM curator against the example data:

```sh
uv run python scripts/eval_curator_llm.py
```

This uses the OpenAI API once per example and does not write memory.

To preview appending a proposal to the playbook:

```sh
uv run python scripts/preview_memory_apply.py "P006: ユーザーが希望した呼び方を尊重する。"
```

This reads memory but does not write memory.

To test the LLM curator dry-run:

```sh
uv run python scripts/curator_llm_dry_run.py "ユーザー: 今後はたろうって呼んで"
```

This reads `OPENAI_API_KEY` from `.env.letta` and does not write memory.

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
- Mention conversations are appended to `logs/discord_mentions.jsonl`.

## Conversation Logs

The bot currently logs only messages that mention it. It does not log all server
messages.

Logs are written to `logs/discord_mentions.jsonl`, and `logs/` is ignored by
git.

Each JSONL record contains minimal Discord context and the bot reply. It does
not include Discord tokens, OpenAI keys, Letta internal responses, raw Discord
message dumps, or attachment contents.

To show recent mention logs:

```sh
uv run python scripts/show_recent_mentions.py
```

To print recent logs as curator input text:

```sh
uv run python scripts/show_recent_mentions.py --limit 1 --curator-input
```

To run the LLM curator dry-run on recent mention logs and show an append preview:

```sh
uv run python scripts/curate_recent_mentions.py --limit 1
```

## Not Implemented Yet

- Automatic curator apply or read-only memory write gate.
- Heartbeat or scheduled autonomous actions.
- Discord API tools beyond reading messages and sending replies.
- Web or database tools.
- Deployment or process supervision.
