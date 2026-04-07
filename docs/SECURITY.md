# Security

MyCow is designed with an explicit security model: **every permission is opt-in, everything else is denied**.

---

## Non-negotiable principles

1. **Explicit permissions** — each agent declares exactly what it can do in `cron.yaml`. No implicit permissions.
2. **Never `--dangerously-skip-permissions`** — MyCow always uses `--allowedTools` with least privilege. There is no way to bypass this via configuration.
3. **Timeout on everything** — every Claude Code subprocess has an explicit timeout (default 300s). A stuck agent does not block the daemon.
4. **Secrets never in plaintext** — tokens and API keys live in `.env`, never in `CLAUDE.md` or `cron.yaml`. The agent subprocess does not receive `TELEGRAM_BOT_TOKEN`.
5. **API only on localhost** — the Flask daemon listens on `127.0.0.1:3333`, never on `0.0.0.0`.
6. **Global kill switch** — `/stop` on Telegram immediately stops all agents.

---

## Permission model

Permissions are configured in `cron.yaml` for each agent:

```yaml
permissions:
  bash: false                    # shell command execution
  internet: true                 # WebSearch and WebFetch
  write_outside_dir: false       # write outside agents/name/
  telegram_without_approval: true  # send Telegram without confirmation
```

**Resulting levels for `--allowedTools`:**

| Configuration | Allowed tools |
|----------------|----------------|
| `bash: false` | `Read, Write` |
| `bash: false` + `internet: true` | `Read, Write, WebSearch, WebFetch` |
| `bash: true` | `Read, Write, Bash(git *), Bash(npm test), Bash(python *)` |

Agents never receive unlimited `Bash(*)` — the allowed bash commands are a fixed list.

---

## EMERGENCY_STOP

The kill switch creates an `EMERGENCY_STOP` file in the project root.

**How to activate it:**
- Telegram command: `/stop`
- API: `POST /api/stop-all`
- Manually: `touch EMERGENCY_STOP` in the root

**Effect:**
- Scheduler and HeartbeatManager stop immediately
- Every call to `run_agent()` is blocked with state `"blocked"` before starting any subprocess
- The daemon remains running (API and web UI still work)

**How to remove it:**
```bash
rm EMERGENCY_STOP   # Mac/Linux
del EMERGENCY_STOP  # Windows
```

Or via Web UI → Settings → "Re-enable agents".

---

## Secrets

**Where they go:**
```bash
# .env (never committed)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
BRAVE_API_KEY=...
ANTHROPIC_API_KEY=...
```

**The `.env` file is never read by agents.** The daemon loads the variables at startup and removes them from the subprocess environment before starting Claude Code:

```python
clean_env = {k: v for k, v in os.environ.items()
             if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
```

**What not to do:**
- Do not put tokens in `CLAUDE.md` or `cron.yaml`
- Do not commit `.env` (it's in `.gitignore`)
- Do not use secrets as part of the prompt

---

## Local API

The Flask API is accessible only from localhost by design. No authentication is needed because it is not exposed to the network.

If you need remote access (e.g. from your phone via Telegram), **use Telegram** — it is already integrated and encrypted.

For remote access to the Web UI:

### Tailscale (recommended)

Tailscale creates a zero-config VPN between your devices without opening public ports.

```bash
# Install Tailscale
# Mac:   brew install tailscale
# Linux: curl -fsSL https://tailscale.com/install.sh | sh
# Win:   https://tailscale.com/download/windows

# Start
tailscale up

# Access the Web UI from your phone via Tailscale IP
# E.g.: http://100.x.x.x:3333
```

---

## Input sanitization

The Telegram bridge sanitizes all incoming commands:
- Max 2000 characters per message
- Blocked patterns: `--dangerously`, `rm -rf`, `format c:`, `del /f /s`
- chat_id whitelist: only the chat IDs configured in `.env` can send commands

---

## Vulnerability reporting

If you find a security vulnerability, do not open a public issue. Contact directly using the details in [COMMERCIAL.md](../COMMERCIAL.md).
