# hannario-v2

Small Discord companion bot for a single private server.

## Current Architecture

```text
Discord
  -> bot.py
      -> Letta server (Docker Compose)
          -> OpenAI model + embedding
          -> Docker volume
          -> read-only /logs mount for custom tools
```

- `bot.py` owns Discord I/O.
- `discord_context.py` formats Discord messages for Letta.
- `letta_agent.py` owns Letta message calls, replies, and tool diagnostics.
- Letta owns agent state, message history, memory blocks, and custom tools.
- OpenAI keys are used by the Letta server, the bot's optional auto-summary
  task, and local OpenAI helper scripts.
- Letta data is stored in the Docker volume `hannario-v2_letta_pgdata`.
- Local runtime logs are written under `logs/`, which is ignored by git.

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

The compose service mounts local `logs/` into the Letta container as read-only
`/logs` so custom Letta tools can read bot observation logs.

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

Then register read-only Discord observation tools with the Letta agent:

```sh
uv run python scripts/register_letta_discord_tools.py
```

The registered tools are:

- `list_observed_discord_channels`
- `get_recent_discord_observations`
- `get_latest_discord_channel_summary`

## Run The Bot

Make sure `.env` contains:

```env
DISCORD_TOKEN=...
LETTA_BASE_URL=http://localhost:8283
LETTA_AGENT_ID=...
DISCORD_CONTEXT_MESSAGE_LIMIT=5
DISCORD_INCLUDE_CHANNEL_SUMMARY=0
DISCORD_WAKE_WORDS=はんなり男,はんなり
DISCORD_SILENCE_PHRASES=黙って,消えて,静かにして,もういい,呼んでない
DISCORD_REPLY_TRIGGER_ENABLED=1
DISCORD_WAKE_WORD_TRIGGER_ENABLED=1
DISCORD_ACTIVE_REPLY_ENABLED=1
DISCORD_SILENCE_ENABLED=1
DISCORD_RANDOM_REPLY_ENABLED=0
DISCORD_ACTIVE_REPLY_WINDOW_SECONDS=300
DISCORD_SILENCE_SECONDS=1800
DISCORD_RANDOM_REPLY_RATE=0.1
DISCORD_RANDOM_REPLY_COOLDOWN_SECONDS=900
DISCORD_RANDOM_REPLY_MIN_CHARS=6
DISCORD_AUTO_SUMMARY_ENABLED=0
DISCORD_AUTO_SUMMARY_INTERVAL_SECONDS=600
DISCORD_AUTO_SUMMARY_LIMIT=20
DISCORD_AUTO_SUMMARY_MIN_NEW_MESSAGES=5
DISCORD_HEARTBEAT_ENABLED=0
DISCORD_HEARTBEAT_INTERVAL_SECONDS=900
DISCORD_HEARTBEAT_CONSULT_LETTA_ENABLED=0
DISCORD_HEARTBEAT_OBSERVATION_LIMIT=20
DISCORD_HEARTBEAT_POST_ENABLED=0
DISCORD_HEARTBEAT_POST_COOLDOWN_SECONDS=3600
DISCORD_HEARTBEAT_POST_MAX_CHARS=500
```

Then run:

```sh
uv run python bot.py
```

## Current Behavior

- `!ping` replies with `pong`.
- The bot replies when it is mentioned, when a message replies to the bot, or
  when a message contains one of `DISCORD_WAKE_WORDS`.
- After the bot replies, the channel stays active for
  `DISCORD_ACTIVE_REPLY_WINDOW_SECONDS`; during that window, ordinary follow-up
  messages in the same channel can also trigger replies.
- If a message contains one of `DISCORD_SILENCE_PHRASES`, the bot stops replying
  to active follow-up messages in that channel for `DISCORD_SILENCE_SECONDS`.
  Explicit mentions, Discord replies to the bot, and wake words still work.
- If `DISCORD_RANDOM_REPLY_ENABLED=1`, the bot can occasionally join ordinary
  non-triggered conversations. Random participation uses
  `DISCORD_RANDOM_REPLY_RATE`, ignores short messages and commands, and has a
  per-channel cooldown.
- On reply, the bot sends the cleaned Discord message context to Letta.
- The Letta input includes exact current time in UTC and Asia/Tokyo local time.
- On reply, the bot also sends up to `DISCORD_CONTEXT_MESSAGE_LIMIT` recent
  messages from the same channel as context. Set it to `0` to disable this.
- If `DISCORD_INCLUDE_CHANNEL_SUMMARY=1`, the bot also sends the latest saved
  same-channel summary from `logs/channel_summaries.jsonl` as supplemental
  background. Current and recent messages are marked as higher priority.
- If `DISCORD_AUTO_SUMMARY_ENABLED=1`, the bot periodically summarizes
  observed channel messages and appends results to `logs/channel_summaries.jsonl`.
- If `DISCORD_HEARTBEAT_ENABLED=1`, the bot runs a periodic heartbeat tick.
  By default this logs only and does not post to Discord. If
  `DISCORD_HEARTBEAT_CONSULT_LETTA_ENABLED=1`, heartbeat sends recent
  observations to Letta for a private status check and logs the structured
  decision. If `DISCORD_HEARTBEAT_POST_ENABLED=1`, valid `consider_reply`
  decisions may be posted to Discord with a per-channel cooldown.
- The bot replies in the same channel.
- The bot ignores messages from itself and other bots.
- If Letta fails, the bot sends a short fallback reply instead of crashing.
- Letta tool calls and tool returns are logged by the bot when returned by Letta.
- Triggered conversations are appended to `logs/discord_mentions.jsonl`.
- Non-mention user messages are appended to `logs/discord_observations.jsonl`
  for observation only. They are not directly sent to Letta yet.

## Daily Workflow

Before a play session:

```sh
uv run python scripts/snapshot_agent_memory.py
docker compose up -d letta
uv run python bot.py
```

After a play session:

```sh
uv run python scripts/snapshot_agent_memory.py
uv run python scripts/diff_latest_memory_snapshots.py
uv run python scripts/list_observed_channels.py
```

This lets the agent use Letta memory freely while still making memory drift and
channel summaries visible.

If automatic summaries are disabled, run a manual summary after the session:

```sh
uv run python scripts/summarize_all_observed_channels.py --limit 20 --save
```

## Logs And Summaries

The bot logs mention conversations and non-mention user message observations.
Only triggered conversations are sent directly to Letta.

Triggered records in `logs/discord_mentions.jsonl` contain minimal Discord
context, the recent channel context sent to Letta, the optional supplemental
channel summary sent to Letta, the response trigger, and the bot reply.

Observation records in `logs/discord_observations.jsonl` contain minimal
Discord context and cleaned message content. They do not include bot replies
because no reply is generated.

Saved summaries are appended to `logs/channel_summaries.jsonl`.

Heartbeat decisions are appended to `logs/discord_heartbeats.jsonl`.

Logs do not include Discord tokens, OpenAI keys, Letta internal responses, raw
Discord message dumps, or attachment contents.

Automatic summaries are controlled by:

```env
DISCORD_AUTO_SUMMARY_ENABLED=1
DISCORD_AUTO_SUMMARY_INTERVAL_SECONDS=600
DISCORD_AUTO_SUMMARY_LIMIT=20
DISCORD_AUTO_SUMMARY_MIN_NEW_MESSAGES=5
```

The bot summarizes a channel only when at least
`DISCORD_AUTO_SUMMARY_MIN_NEW_MESSAGES` new observed messages exist since that
channel's latest saved summary.

Useful commands:

```sh
uv run python scripts/show_recent_mentions.py
uv run python scripts/show_recent_observations.py
uv run python scripts/show_recent_heartbeats.py
uv run python scripts/list_observed_channels.py
uv run python scripts/show_channel_summaries.py
```

Channel-specific inspection:

```sh
uv run python scripts/show_recent_observations.py --channel はんなり男
uv run python scripts/show_channel_context.py --channel はんなり男
uv run python scripts/show_channel_summaries.py --channel はんなり男
uv run python scripts/show_channel_summaries.py --channel はんなり男 --show-context
```

Debug context construction:

```sh
uv run python scripts/show_context_debug.py
uv run python scripts/preview_mention_input_with_summary.py
uv run python scripts/preview_heartbeat_input.py
```

Summarize observations:

```sh
uv run python scripts/summarize_channel_observations.py --channel はんなり男
uv run python scripts/summarize_channel_observations.py --channel はんなり男 --save
uv run python scripts/summarize_all_observed_channels.py --limit 20
uv run python scripts/summarize_all_observed_channels.py --limit 20 --max-channels 1
uv run python scripts/summarize_all_observed_channels.py --limit 20 --save
```

## Memory Operations

To inspect the agent's current memory blocks:

```sh
uv run python scripts/show_agent_memory.py
```

To save a local snapshot of the current memory blocks:

```sh
uv run python scripts/snapshot_agent_memory.py
```

Snapshots are written under `memory_snapshots/`, which is ignored by git.

To diff two memory snapshots:

```sh
uv run python scripts/diff_agent_memory.py memory_snapshots/before.json memory_snapshots/after.json
```

To diff the latest two snapshots:

```sh
uv run python scripts/diff_latest_memory_snapshots.py
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

Curator commands:

```sh
uv run python scripts/curator_dry_run.py "ユーザー: 今後はたろうって呼んで"
uv run python scripts/curator_llm_dry_run.py "ユーザー: 今後はたろうって呼んで"
uv run python scripts/eval_curator_stub.py
uv run python scripts/eval_curator_llm.py
uv run python scripts/show_recent_mentions.py --limit 1 --curator-input
uv run python scripts/curate_recent_mentions.py --limit 1
uv run python scripts/preview_memory_apply.py "P006: ユーザーが希望した呼び方を尊重する。"
```

`eval_curator_llm.py`, `curator_llm_dry_run.py`, and
`curate_recent_mentions.py` use the OpenAI API and do not write memory.

## Not Implemented Yet

- Automatic curator apply or read-only memory write gate.
- More advanced scheduled autonomous actions beyond heartbeat.
- Discord write tools beyond sending replies.
- Web or database tools.
- Deployment or process supervision.
