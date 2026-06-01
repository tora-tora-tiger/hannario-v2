# Deployment

This project is intended to run on a small, dedicated VM. The current target is
a private hobby server, so the deployment plan favors simple, inspectable
operations over platform complexity.

## Target Shape

Recommended first production shape:

```text
Ubuntu VM
  /home/keitaito/hannario-v2
    repo checkout
    .env
    .env.letta
    data/local.sqlite3
    logs/
    memory_snapshots/

  Docker Compose
    letta service
    letta_pgdata volume

  user systemd
    hannario-bot.service
```

Letta remains in Docker Compose. The bot can run as a user systemd service via
`uv run python bot.py`. This keeps bot logs available through `journalctl`
without requiring the bot itself to be containerized yet.

## Current VM Readiness

The VM at `172.17.2.4` has been checked read-only.

Observed:

- Ubuntu 24.04 LTS
- user: `keitaito`
- about 32 GB disk, about 4 GB RAM
- `git`, `python3`, `systemctl`, and `journalctl` are present
- `uv` and Docker were not found in `PATH`

This means the next VM setup work requires write operations and likely `sudo`.
Those commands should be run by the operator or explicitly approved before an
agent executes them.

## Required VM Setup

Install or confirm:

- `git`
- `uv`
- Docker Engine with Compose plugin
- user access to Docker, or an agreed service layout that starts Letta with
  system-level Docker

Then clone or update the repository under:

```text
/home/keitaito/hannario-v2
```

Create:

```sh
cp .env.example .env
cp .env.letta.example .env.letta
```

Fill secrets locally on the VM:

- `.env`: `DISCORD_TOKEN`, `LETTA_AGENT_ID`
- `.env.letta`: `OPENAI_API_KEY`

Do not commit these files.

## First Deploy

From the repo directory on the VM:

```sh
uv sync
docker compose up -d letta
uv run python scripts/smoke_letta.py
uv run python scripts/create_agent.py
uv run python scripts/register_letta_tools.py
uv run python scripts/init_schedule_db.py
uv run python scripts/check_deploy_readiness.py
```

Copy the `LETTA_AGENT_ID=...` printed by `create_agent.py` into `.env`, then
run `register_letta_tools.py`.

## User systemd

A user-service example is available at:

```text
deploy/systemd/hannario-bot.service.example
```

Install manually on the VM:

```sh
mkdir -p ~/.config/systemd/user
cp deploy/systemd/hannario-bot.service.example ~/.config/systemd/user/hannario-bot.service
systemctl --user daemon-reload
systemctl --user enable --now hannario-bot.service
```

For a user service to keep running after logout, lingering may be required:

```sh
sudo loginctl enable-linger keitaito
```

That is a privileged host operation and should be done intentionally.

## Operations

Check service state:

```sh
systemctl --user status hannario-bot.service
```

Read bot logs:

```sh
journalctl --user -u hannario-bot.service -n 200 --no-pager
journalctl --user -u hannario-bot.service -f
```

Read Letta logs:

```sh
docker compose logs -f letta
```

Run local readiness checks:

```sh
uv run python scripts/check_deploy_readiness.py
```

Useful Discord E2E checks are listed in [operations.md](operations.md).

## Update Flow

From the VM repo directory:

```sh
git pull
uv sync
docker compose up -d letta
uv run python scripts/register_letta_tools.py
uv run python scripts/check_deploy_readiness.py
systemctl --user restart hannario-bot.service
```

If tool source code changed, always re-run `register_letta_tools.py`.

## Backup Targets

Before long unattended runs, back up:

- Docker volume for Letta/Postgres data
- `data/local.sqlite3`
- `logs/`
- `memory_snapshots/`
- `.env`
- `.env.letta`

For the first deployment, a simple manual backup is acceptable. Automated
rotation can come after the bot proves stable under supervised operation.

## Conservative Production Defaults

Recommended first always-on settings:

```env
DISCORD_RANDOM_REPLY_ENABLED=0
DISCORD_AUTO_SUMMARY_ENABLED=0
DISCORD_HEARTBEAT_ENABLED=1
DISCORD_HEARTBEAT_INTERVAL_SECONDS=900
DISCORD_HEARTBEAT_CONSULT_LETTA_ENABLED=1
DISCORD_HEARTBEAT_POST_ENABLED=0
DISCORD_SCHEDULE_ENABLED=1
DISCORD_SCHEDULE_INTERVAL_SECONDS=30
DISCORD_SCHEDULE_INTERNAL_CONSULT_LETTA_ENABLED=1
```

Enable proactive Discord posting only after observing heartbeat logs:

```env
DISCORD_HEARTBEAT_POST_ENABLED=1
DISCORD_HEARTBEAT_POST_COOLDOWN_SECONDS=3600
```

## Agent Operating Boundaries

The operator has allowed read-only SSH inspection through:

```sh
ssh -o BatchMode=yes -o ConnectTimeout=5 172.17.2.4 '...read-only command...'
```

Write operations on the VM and all `sudo` commands require explicit operator
approval or should be given back as instructions.
