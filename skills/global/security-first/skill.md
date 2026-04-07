# Skill: Security First

## Goal
MyCow executes code autonomously, has access to the filesystem and the internet. Every development decision must treat security as a primary requirement, not an afterthought. MyCow's positioning vs OpenClaw is exactly this: secure by design.

---

## Non-Negotiable Principles

### 1. Least Privilege Always
Each agent has only the permissions needed for its specific task. If an agent reads news and sends Telegram messages, it has no bash access and no filesystem write access.

```yaml
# ✅ Correct — minimal permissions
permissions:
  bash: false
  internet: true
  write_outside_dir: false
  telegram_without_approval: true

# ❌ Never do this
permissions:
  all: true
```

### 2. Never `--dangerously-skip-permissions`
This flag bypasses Claude Code's command blocklist, write restrictions, and permission prompts. Never use it in production, not even "temporarily".

```python
# ✅ Correct
cmd = ["claude", "-p", prompt, "--allowedTools", "Read,Bash(git status)"]

# ❌ Never
cmd = ["claude", "-p", prompt, "--dangerously-skip-permissions"]
```

### 3. Timeout On Everything
Every subprocess has an explicit timeout. An agent that gets stuck must not block the system.

```python
# ✅ Always
result = subprocess.run(cmd, timeout=300, capture_output=True)

# ❌ Never
result = subprocess.run(cmd, capture_output=True)  # can block forever
```

### 4. Secrets Never in Plaintext
```python
# ✅ Always from environment variables
api_key = os.environ.get("BRAVE_API_KEY")

# ❌ Never hardcoded, never in CLAUDE.md, never in versioned files
api_key = "sk-xxxxx"
```

### 5. Input Sanitization
Any input coming from Telegram must be sanitized before being passed to Claude Code. A malicious user could inject instructions.

```python
# Maximum length
MAX_PROMPT_LENGTH = 2000

# Dangerous characters
FORBIDDEN_PATTERNS = [
    "--dangerously",
    "--allowedTools Bash(*)",
    "rm -rf",
    "format c:",
]

def sanitize_telegram_input(text: str) -> str:
    if len(text) > MAX_PROMPT_LENGTH:
        raise ValueError("Input too long")
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in text.lower():
            raise ValueError(f"Forbidden pattern: {pattern}")
    return text.strip()
```

---

## Agent Permission Model

### Access Levels
```
LEVEL 0 — Read Only
  Can read files in its folder
  Can do web searches
  Can send Telegram messages
  CANNOT execute bash
  CANNOT write files

LEVEL 1 — Read + Write (default)
  Everything from LEVEL 0
  Can write in its agent folder
  CANNOT write outside the folder
  CANNOT execute arbitrary bash

LEVEL 2 — Developer
  Everything from LEVEL 1
  Can execute bash with pre-approved commands
  Can write to specific authorized folders
  Requires Telegram approval for critical actions

LEVEL 3 — Admin (requires explicit confirmation)
  Full access
  Each session requires confirmation via Telegram
  Full audit log
```

### Mapping Claude Code --allowedTools
```python
PERMISSION_LEVELS = {
    0: "Read",
    1: "Read,Write",
    2: "Read,Write,Bash(git *),Bash(npm test),Bash(python *)",
    3: "Read,Write,Bash(*)"  # requires Telegram confirmation
}
```

---

## Network Security

### Telegram — Pull Architecture
The Telegram bot calls out to Telegram's servers. No listening port. Zero attack surface without Tailscale.

```
Internet → [Telegram Servers] ← polling MyCow daemon
                                (pull, not push)
```

### Local API
The REST API runs only on localhost. Never bind to 0.0.0.0 without Tailscale.

```python
# ✅ Correct
app.run(host="127.0.0.1", port=3333)

# ❌ Never in production
app.run(host="0.0.0.0", port=3333)
```

### Tailscale (Optional)
If the user wants remote access to the web UI, Tailscale is the only supported method. Zero port forwarding, zero ngrok, zero unverified tunnels.

---

## Audit and Logging

### Every Agent Execution Logs
```json
{
  "timestamp": "2026-03-31T08:00:00Z",
  "agent": "news-monitor",
  "trigger": "cron",
  "prompt_hash": "sha256:xxxxx",
  "tools_used": ["Read", "WebSearch"],
  "duration_seconds": 45,
  "status": "success",
  "telegram_sent": true
}
```

### Sensitive Logs
- Never log the full content of prompts (they may contain sensitive data)
- Never log API keys or tokens
- Use hashes for references to sensitive data

---

## Kill Switch

### Via Telegram
```
/stop              → stops all agents, daemon remains active
/stop news-monitor → stops a specific agent
/pause             → pauses all crons (not a kill)
/status            → status of all agents
```

### Via Web UI
"Stop All" button always visible in the header, red color, requires confirmation.

### Via Filesystem
```bash
# Emergency file — if it exists, the daemon will not start agents
touch mycow/EMERGENCY_STOP
```

---

## Security Checklist Before Every Feature

- [ ] Are permissions at the minimum necessary?
- [ ] Do all subprocesses have timeouts?
- [ ] Are secrets in environment variables?
- [ ] Is input from Telegram sanitized?
- [ ] Is the local API on 127.0.0.1?
- [ ] Do destructive actions require confirmation?
- [ ] Does logging exclude sensitive data?
- [ ] Does the kill switch work for this feature?
