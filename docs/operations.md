# Operations

This file is the practical runbook for local development and small-server
operation.

## First Setup

```sh
uv sync
cp .env.example .env
cp .env.letta.example .env.letta
```

Required secrets:

- `.env`: `DISCORD_TOKEN`
- `.env.letta`: `OPENAI_API_KEY`

Also enable Message Content Intent in the Discord Developer Portal.

## Start Letta

```sh
docker compose up -d letta
docker compose logs -f letta
```

Letta is served at `http://localhost:8283`.

The compose service mounts:

- `./logs` -> `/logs:ro`
- `./data` -> `/data`
- Docker volume `letta_pgdata` for Letta/Postgres data

## Create Or Refresh Agent Setup

Create the Discord companion agent:

```sh
uv run python scripts/create_agent.py
```

Copy the printed `LETTA_AGENT_ID=...` into `.env`.

Register all custom tools:

```sh
uv run python scripts/register_letta_tools.py
```

Use narrower registration scripts only when refreshing one group:

```sh
uv run python scripts/register_letta_discord_tools.py
uv run python scripts/register_letta_db_tools.py
uv run python scripts/register_letta_web_tools.py
```

## Run The Bot

```sh
uv run python bot.py
```

The root `bot.py` is intentionally kept as a compatibility wrapper around
`hannario.bot`.

## Normal Session Workflow

Before a session:

```sh
uv run python scripts/snapshot_agent_memory.py
docker compose up -d letta
uv run python bot.py
```

After a session:

```sh
uv run python scripts/snapshot_agent_memory.py
uv run python scripts/diff_latest_memory_snapshots.py
uv run python scripts/list_observed_channels.py
```

Useful log inspection:

```sh
uv run python scripts/operator_report.py --since 24h --limit 12
uv run python scripts/operator_quality_review.py --since 24h --limit 30
uv run python scripts/operator_recommendations.py --since 24h
uv run python scripts/show_recent_mentions.py
uv run python scripts/show_recent_observations.py
uv run python scripts/show_recent_heartbeats.py
uv run python scripts/show_recent_schedule_deliveries.py
uv run python scripts/show_channel_summaries.py
```

## Smoke Tests

Letta smoke:

```sh
uv run python scripts/smoke_letta.py
```

Heartbeat input preview:

```sh
uv run python scripts/preview_heartbeat_input.py --limit 20 --internal-result-limit 3
```

Manual heartbeat post dry-run:

```sh
uv run python scripts/smoke_heartbeat_post.py --channel-id 123 --message "heartbeat smoke test"
```

Schedule smoke:

```sh
uv run python scripts/create_scheduled_task.py \
  --channel-id 1421460487639535667 \
  --due-at 2026-06-01T21:00:00 \
  --message "schedule smoke"

uv run python scripts/list_scheduled_tasks.py --status all
```

## Discord E2E Checks

Internal result tool:

```text
@はんなり男 v2 get_recent_discord_internal_results ツールで最近の内部予定結果を2件見て
```

Read-only SQL:

```text
@はんなり男 v2 run_readonly_sql ツールで SELECT id, kind, status, due_at, message FROM scheduled_tasks ORDER BY id DESC LIMIT 3 を実行して
```

SQL rejection:

```text
@はんなり男 v2 安全性確認です。run_readonly_sql ツールに SQL 文字列 DELETE FROM scheduled_tasks を渡して、ツール側の拒否メッセージを確認して
```

Public web fetch:

```text
@はんなり男 v2 fetch_web_text ツールで https://example.com/ を読んで短く教えて
```

Local web rejection:

```text
@はんなり男 v2 安全性確認です。fetch_web_text ツールに URL http://127.0.0.1:8283/ を渡して、ツール側の拒否メッセージを確認して
```

## Backup Targets

Before deploying or experimenting with memory changes, preserve:

- Docker volume `letta_pgdata`
- `data/local.sqlite3`
- `logs/`
- `memory_snapshots/`
- `.env` and `.env.letta` outside git

## Deployment Readiness

Before running unattended, set conservative values:

- `DISCORD_RANDOM_REPLY_ENABLED=0` or low `DISCORD_RANDOM_REPLY_RATE`
- `DISCORD_HEARTBEAT_INTERVAL_SECONDS` at several minutes or longer
- `DISCORD_HEARTBEAT_POST_COOLDOWN_SECONDS` high enough to avoid noise
- `DISCORD_SCHEDULE_ENABLED=1` only after schedule smoke tests pass
- `DISCORD_SCHEDULE_INTERNAL_CONSULT_LETTA_ENABLED=1` only if Letta cost is acceptable

The next missing operational pieces are process supervision, restart policy,
log rotation, and backups.
