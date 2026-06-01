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

## Manual VM Setup Plan

This section is written for a step-by-step supervised setup. Do not run the
whole section as one script. Execute one block, inspect the result, then move to
the next block.

Do not replace Ubuntu's system Python. Keep it for the OS. Use `uv` to install
and run the project Python version. The Ubuntu `git` package is sufficient for
this project after normal package updates.

### Step 0: Read-Only Baseline

Run from the local development machine:

```sh
uv run python scripts/vm_readonly_status.py --host 172.17.2.4
```

Expected on a fresh VM:

- Ubuntu 24.04
- `git` and `python3` may exist
- `uv` missing
- Docker missing
- repo missing
- service missing

### Step 1: OS Package Baseline

Requires `sudo` on the VM. Run interactively on the VM when ready:

```sh
sudo apt update
sudo apt upgrade
sudo apt install -y ca-certificates curl gnupg git
```

Check:

```sh
git --version
curl --version
```

### Step 2: Install Docker Engine

Requires `sudo` on the VM. Follow the official Docker Engine installation flow
for Ubuntu. The expected outcome is:

```sh
docker --version
docker compose version
```

Add the operator user to the `docker` group if using Docker without `sudo`:

```sh
sudo usermod -aG docker keitaito
```

Then log out and back in before checking:

```sh
docker ps
```

If Docker group access is not desired, keep Docker as a sudo-managed service and
adjust the operational commands accordingly.

### Step 3: Install uv

Run as the normal user, not with `sudo`:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Start a new shell or source the shell profile, then check:

```sh
uv --version
```

### Step 4: Clone Repository

Run as the normal user:

```sh
cd /home/keitaito
git clone <REPOSITORY_URL> hannario-v2
cd /home/keitaito/hannario-v2
```

Check:

```sh
git status --short
git log -1 --oneline
```

### Step 5: Create Environment Files

Run as the normal user:

```sh
cp .env.example .env
cp .env.letta.example .env.letta
```

Fill secrets locally on the VM:

- `.env`: `DISCORD_TOKEN`
- `.env.letta`: `OPENAI_API_KEY`

Keep `LETTA_AGENT_ID` as a placeholder until the agent is created.

Recommended first VM settings in `.env`:

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
HANNARIO_DB_PATH=data/local.sqlite3
```

Do not commit `.env` or `.env.letta`.

### Step 6: Install Python Dependencies

Run from the repo directory:

```sh
uv sync
uv run python -m unittest discover -s tests
```

### Step 7: Start Letta

Run from the repo directory:

```sh
docker compose up -d letta
docker compose ps
docker compose logs --tail 100 letta
```

### Step 8: Create Agent And Register Tools

Run from the repo directory:

```sh
uv run python scripts/smoke_letta.py
uv run python scripts/create_agent.py
```

Copy the printed `LETTA_AGENT_ID=...` into `.env`, then run:

```sh
uv run python scripts/register_letta_tools.py
uv run python scripts/init_schedule_db.py
uv run python scripts/check_deploy_readiness.py
```

### Step 9: Manual Bot Smoke

Before systemd, run the bot in the foreground:

```sh
uv run python bot.py
```

Use Discord to confirm one mention reply. Stop with `Ctrl-C`.

### Step 10: Install User systemd Service

Run as the normal user from the repo directory:

```sh
mkdir -p ~/.config/systemd/user
cp deploy/systemd/hannario-bot.service.example ~/.config/systemd/user/hannario-bot.service
systemctl --user daemon-reload
systemctl --user enable --now hannario-bot.service
systemctl --user status hannario-bot.service --no-pager
```

For a user service to keep running after logout, this privileged host operation
may be required:

```sh
sudo loginctl enable-linger keitaito
```

### Step 11: Post-Deploy Read-Only Check

Run from the local development machine:

```sh
uv run python scripts/vm_readonly_status.py --host 172.17.2.4
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report summary --since 24h --limit 12
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report quality --since 24h --limit 30
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report recommendations --since 24h
```

At this point, leave proactive posting disabled until logs have been reviewed.

## User systemd

A user-service example is available at:

```text
deploy/systemd/hannario-bot.service.example
```

Install manually on the VM as described in Step 10:

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

For a read-only status sweep from the local development machine:

```sh
uv run python scripts/vm_readonly_status.py --host 172.17.2.4
```

For read-only app-log reports after the repo exists on the VM:

```sh
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report summary --since 24h --limit 12
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report quality --since 24h --limit 30
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report recommendations --since 24h
```

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

See [operator_runbook.md](operator_runbook.md) for the longer operating policy.
