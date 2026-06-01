# Operator Runbook

This runbook describes how an agent should help operate this bot over time.
It is intentionally conservative: read first, write only when the operator has
approved the exact category of change.

## Operating Model

The operator wants the agent to help with:

- reading VM status
- reading bot and Letta logs
- spotting noisy behavior or failures
- proposing config changes
- preparing deployment and recovery steps

The agent may run read-only SSH checks against the VM. The agent must not run
VM write operations or `sudo` without explicit approval.

## VM Access

Default host:

```text
172.17.2.4
```

Use non-interactive SSH:

```sh
ssh -o BatchMode=yes -o ConnectTimeout=5 172.17.2.4 '...read-only command...'
```

Avoid commands that can block for input. Prefer commands that finish quickly and
use `--no-pager` where applicable.

## Read-Only Status Script

From the local repo, use:

```sh
uv run python scripts/vm_readonly_status.py --host 172.17.2.4
```

This script checks only read-only state:

- OS, uptime, disk, memory
- available commands
- repo status if the repo exists
- user systemd service status if installed
- recent user journal entries if available
- Docker and Letta status if Docker is installed and the repo exists

It is safe to run before the VM is fully prepared. Missing tools are reported as
warnings rather than treated as fatal.

## Remote Operator Reports

After the repo and `uv` exist on the VM, run the app-log reports over SSH from
the local development machine:

```sh
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report summary --since 24h --limit 12
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report quality --since 24h --limit 30
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report recommendations --since 24h
```

This wrapper is read-only. If the repo or `uv` is missing, it reports that and
exits without trying to install anything.

## Routine Checks

When the bot is running, a routine operation pass should inspect:

1. VM resource pressure: disk, memory, uptime
2. bot service state: `systemctl --user status hannario-bot.service`
3. bot logs: recent `journalctl --user -u hannario-bot.service`
4. Letta logs: `docker compose logs --tail 200 letta`
5. local readiness: `uv run python scripts/check_deploy_readiness.py`
6. app logs: recent mentions, observations, heartbeats, scheduled deliveries
7. memory drift: latest memory write audit and snapshot diff

Use the local operator report as the first pass over app logs:

```sh
uv run python scripts/operator_report.py --since 24h --limit 12
uv run python scripts/operator_quality_review.py --since 24h --limit 30
uv run python scripts/operator_recommendations.py --since 24h
uv run python scripts/operator_backup_inventory.py
```

This summarizes triggered replies, observed conversations, heartbeat decisions,
scheduled task deliveries, memory write audits, and obvious warnings.
The quality review extracts likely review items such as fallback replies, long
replies, non-explicit participation, safety-sensitive prompts, heartbeat post
gate passes, and memory writes.
The recommendations command turns those review items into likely operational
actions.
The backup inventory command is read-only and reports which durable local
targets exist before a backup run.

## Backup Discipline

Use backups as a checkpoint before changing runtime behavior, not only after a
failure. The minimum protected set is:

- Letta/Postgres Docker volume, usually `hannario-v2_letta_pgdata` on the VM
- `data/local.sqlite3`
- `logs/`
- `memory_snapshots/`
- `.env`
- `.env.letta`

Before requesting or running any risky operation, check:

```sh
uv run python scripts/operator_backup_inventory.py
```

Take a fresh backup before:

- first unattended VM run
- Letta volume migration or container image changes
- memory-block cleanup
- schema or schedule-store changes
- package upgrades on the VM

For restore, stop the user service first, restore files, start Letta, run
readiness checks, then start the bot. If a restore was needed because of odd
conversation behavior, inspect `operator_quality_review.py` before re-enabling
proactive posting.

## What To Watch

Operational warning signs:

- bot service repeatedly restarts
- Letta is unreachable
- Discord fallback replies appear often
- Letta tool returns show non-success status
- heartbeat posts too frequently
- random/active replies feel too noisy
- memory write audit shows unexpected playbook or persona edits
- `data/local.sqlite3` cannot be opened
- disk usage grows quickly from logs or snapshots

## Change Policy

Safe read-only operations:

- `ssh ... 'uname -a'`
- `ssh ... 'df -h'`
- `ssh ... 'free -h'`
- `ssh ... 'journalctl --user ... --no-pager'`
- `ssh ... 'systemctl --user status ... --no-pager'`
- local scripts that only read logs or preview prompts

Needs explicit approval or operator action:

- installing packages
- editing files on the VM
- copying secrets
- enabling or restarting systemd services
- Docker commands that create, stop, or remove containers
- `sudo`
- deleting logs, DBs, Docker volumes, or snapshots

## Bootstrap Stance

Do not replace Ubuntu's system Python. Keep it for the OS.

Use `uv` to install and run the project Python version. This project pins
Python `>=3.12,<3.13`, and `uv` can manage that without mutating system Python.

The Ubuntu `git` package is sufficient. It can be updated during normal VM
bootstrap, but it does not need a custom install.

Docker should be installed intentionally for Letta. Use the official Docker
Engine installation path for Ubuntu when the operator is ready to prepare the
VM.

## First Supervised Run

The first supervised run should keep proactive behavior conservative:

```env
DISCORD_RANDOM_REPLY_ENABLED=0
DISCORD_AUTO_SUMMARY_ENABLED=0
DISCORD_HEARTBEAT_ENABLED=1
DISCORD_HEARTBEAT_CONSULT_LETTA_ENABLED=1
DISCORD_HEARTBEAT_POST_ENABLED=0
DISCORD_SCHEDULE_ENABLED=1
DISCORD_SCHEDULE_INTERNAL_CONSULT_LETTA_ENABLED=1
```

Observe logs for at least one short session before enabling heartbeat posts or
random participation on the VM.
