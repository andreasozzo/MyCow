# 🐄 MyCow

**The proactive layer for Claude Code.**

[![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)](LICENSE)

Claude Code is reactive — it waits for you to talk to it. MyCow adds the proactive layer: autonomous agents that work while you're not watching, contact you on Telegram, and execute planned tasks via cron.

---

## Quick start (5 minutes)

**Windows:**
```powershell
irm https://raw.githubusercontent.com/andreasozzo/mycow/master/install/install.ps1 | iex
```

**Mac / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/andreasozzo/mycow/master/install/install.sh | bash
```

Then:
```bash
cd ~/MyCow
# Open .env and add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
mycow start
# Opens http://localhost:3333 — create your first agent from the wizard
```

---

## Prerequisites

- [Node.js](https://nodejs.org) + [Claude Code CLI](https://github.com/anthropics/claude-code): `npm install -g @anthropic-ai/claude-code`
- [Python 3.11+](https://python.org)
- A Telegram bot (create one with [@BotFather](https://t.me/botfather) in 2 minutes)

---

## What it does

- **Cron scheduler** — runs Claude Code tasks at fixed times (`0 8 * * *` = every morning at 8)
- **Heartbeat** — every N minutes the agent autonomously decides whether to act (monitoring, event alerts)
- **Bidirectional Telegram** — agents contact you proactively; you reply and send commands via `/run`, `/stop`, `/logs`
- **Web UI** — agent dashboard, real-time logs, agent creation wizard, skill management
- **Skill system** — modular capabilities (web search, git workflow, notifications) enabled per agent
- **Kill switch** — `/stop` on Telegram stops everything immediately

---

## How it works

Each agent is a self-contained folder:

```
agents/news-monitor/
├── CLAUDE.md       ← identity and behavior
├── cron.yaml       ← schedule, heartbeat, permissions
└── memory/         ← persistent state
```

**Minimal `cron.yaml`:**
```yaml
name: news-monitor
enabled: true
heartbeat: 3600          # checks every hour
permissions:
  internet: true
  telegram_without_approval: true
crons:
  - id: morning-brief
    schedule: "0 8 * * *"
    model: claude-haiku-4-5-20251001
    prompt: >
      Find the 3 most important AI news today.
      Write the text to send via Telegram as output.
```

**Cron vs Heartbeat:**
- **Cron** — *always* runs at the fixed schedule. Use for planned reports.
- **Heartbeat** — the agent *decides* whether to act. Use for monitoring and alerts.

---

## Available skills

| Skill | Description | Env |
|-------|-------------|-----|
| `brave-search` | Private web search via Brave Search API | `BRAVE_API_KEY` |
| `web-fetch` | Download and read web pages | — |
| `telegram-notify` | Telegram message formatting | — |
| `git-workflow` | Semantic commits, branches, PRs | — |

```bash
mycow skill install brave-search
mycow skill add brave-search --agent news-monitor
```

### Coding agents

MyCow is a natural fit for developer workflows. You can create agents that:
- **Watch a repository** and notify you when tests fail or a PR needs review
- **Run tests on schedule** — pull the latest code at midnight, execute your test suite, send results to Telegram
- **Auto-generate changelogs** — read git history weekly and write human-readable summaries
- **Create branches and PRs** — refactor code, run linters, commit with semantic messages, open draft PRs while you sleep

The `git-workflow` skill gives agents semantic commit + PR capabilities. Combine it with `bash` permissions (scoped to `git *` and your test runner) for safe, auditable automation.

See [Developer Agents](https://github.com/andreasozzo/mycow/wiki/Developer-Agents) in the wiki for detailed examples.

---

## Security

- Explicit opt-in permissions per agent (`--allowedTools` without `--dangerously-skip-permissions`)
- API only on `127.0.0.1:3333` — never exposed to the network
- Secrets in `.env`, never in agent files
- Kill switch: `/stop` on Telegram → `EMERGENCY_STOP` file blocks all executions

See [docs/SECURITY.md](docs/SECURITY.md) for the full security model.

---

## Documentation

- [docs/AGENTS.md](docs/AGENTS.md) — agent structure, cron.yaml, CLAUDE.md, examples
- [docs/SKILLS.md](docs/SKILLS.md) — available skills, installation, creating custom skills
- [docs/SECURITY.md](docs/SECURITY.md) — permissions, EMERGENCY_STOP, Tailscale

---

## License

Business Source License 1.1 — free for personal and non-commercial use.
For commercial use: see [COMMERCIAL.md](COMMERCIAL.md).
Becomes MIT 4 years after the first public release.
