# VM Setup Checklist

This is the supervised, one-step-at-a-time checklist for the dedicated bot VM.
It intentionally avoids wrapping the initial setup in a script.

Current target:

- host: `172.17.2.4`
- user: `keitaito`
- repo path: `/home/keitaito/hannario-v2`
- OS: Ubuntu 24.04

## 0. Read-Only Baseline

Run from the local development machine:

```sh
uv run python scripts/vm_readonly_status.py --host 172.17.2.4
```

Proceed only if the output still matches the expected fresh state:

- `uv=missing`
- `docker=missing`
- `repo_missing=/home/keitaito/hannario-v2`
- `hannario-bot.service` not found

## 1. OS Packages

Run on the VM:

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

## 2. Docker

Install Docker Engine for Ubuntu using Docker's official apt repository flow.
After installation, check:

```sh
docker --version
docker compose version
```

If Docker should be usable without `sudo`, run:

```sh
sudo usermod -aG docker keitaito
```

Then log out and back in before checking:

```sh
docker ps
```

## 3. uv

Run as the normal user:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new shell, then check:

```sh
uv --version
```

## 4. Repository

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

## 5. Environment Files

Run from the repo directory:

```sh
cp .env.example .env
cp .env.letta.example .env.letta
```

Edit:

- `.env`: set `DISCORD_TOKEN`
- `.env.letta`: set `OPENAI_API_KEY`

Keep `LETTA_AGENT_ID` as a placeholder until the agent is created.

Recommended first VM values in `.env`:

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

## 6. Python Environment

Run from the repo directory:

```sh
uv sync
mkdir -p logs data memory_snapshots
chmod u+rwX logs data memory_snapshots
uv run python -m unittest discover -s tests
```

## 7. Letta

Run from the repo directory:

```sh
docker compose up -d letta
docker compose ps
docker compose logs --tail 100 letta
```

## 8. Agent And Tools

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

## 9. Foreground Bot Smoke

Run from the repo directory:

```sh
uv run python bot.py
```

Confirm one Discord mention reply, then stop with `Ctrl-C`.

## 10. First Backup

Before installing the service, check durable state:

```sh
uv run python scripts/operator_backup_inventory.py
```

Take a manual backup using the flow in [deployment.md](deployment.md).

## 11. User Service

Run from the repo directory:

```sh
mkdir -p ~/.config/systemd/user
cp deploy/systemd/hannario-bot.service.example ~/.config/systemd/user/hannario-bot.service
systemctl --user daemon-reload
systemctl --user enable --now hannario-bot.service
systemctl --user status hannario-bot.service --no-pager
```

If the service must survive logout, run this privileged host operation:

```sh
sudo loginctl enable-linger keitaito
```

## 12. Post-Deploy Check

Run from the local development machine:

```sh
uv run python scripts/vm_readonly_status.py --host 172.17.2.4
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report summary --since 24h --limit 12
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report quality --since 24h --limit 30
uv run python scripts/vm_operator_report.py --host 172.17.2.4 --report recommendations --since 24h
```

Keep proactive Discord posting disabled until those reports look reasonable.
