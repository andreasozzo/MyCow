# Agents

A MyCow agent is a folder in `agents/` with three required files: `CLAUDE.md`, `cron.yaml`, and a `memory/` folder. The daemon reads these files to know what to do, when to do it, and with what permissions.

---

## Folder structure

```
agents/
└── agent-name/
    ├── CLAUDE.md          ← identity, behavior, active skills
    ├── cron.yaml          ← schedule, heartbeat, permissions, prompts
    └── memory/
        ├── core.md        ← stable facts (who you are, what you do)
        ├── working.md     ← current state, tasks in progress
        └── decisions.md   ← log of decisions made by the agent
```

---

## CLAUDE.md

The agent's identity file. Claude Code reads it as a system prompt before every execution.

```markdown
# agent-name

Brief description: what this agent does and its operational style.

## Style
- Specific behavioral rules
- Tone, output format, constraints

## Heartbeat Behavior

Instructions for autonomous behavior (executed every N minutes).
The difference from cron: the heartbeat DECIDES on its own whether to act or not.

Example:
- If X has changed since the last check: act and write the message to send as output
- If everything is normal: do nothing, send no messages

## Active Skills
- ../../../skills/global/brave-search/skill.md
- ../../../skills/global/telegram-notify/skill.md
```

**Sections:**
- Header + description: required
- `## Style`: optional, but recommended
- `## Heartbeat Behavior`: required if heartbeat > 0 in cron.yaml
- `## Active Skills`: list of relative paths to skills to use

---

## cron.yaml

Complete agent configuration: schedule, heartbeat, permissions, and prompts.

```yaml
name: agent-name          # must match the folder name
enabled: true              # false to disable without deleting

heartbeat: 3600            # heartbeat interval in seconds (0 = disabled)
heartbeat_model: claude-haiku-4-5-20251001  # model for heartbeat (optional)

telegram_chat_id: "123456789"  # Telegram chat ID for this agent's notifications

permissions:
  bash: false                    # allow bash commands (default: false)
  internet: true                 # allow WebSearch and WebFetch (default: false)
  write_outside_dir: false       # allow writing outside the agent folder
  telegram_without_approval: true  # send to Telegram without manual confirmation

crons:
  - id: morning-brief            # unique cron identifier
    schedule: "0 8 * * *"        # standard cron expression
    model: claude-haiku-4-5-20251001  # Claude model to use
    prompt: >
      Full prompt to execute at a fixed time.
      Write the text to send via Telegram as output.

  - id: evening-recap
    schedule: "0 18 * * *"
    model: claude-sonnet-4-6
    prompt: >
      Second cron with a different schedule.
```

**Required fields:** `name`, `enabled`, `permissions`, `crons`

**Optional fields:** `heartbeat`, `heartbeat_model`, `telegram_chat_id`

---

## Cron vs Heartbeat

| | Cron | Heartbeat |
|---|---|---|
| **When it runs** | At fixed times (schedule) | Every N seconds in a loop |
| **Decides whether to act** | No — always executes | Yes — evaluates state and decides |
| **Prompt** | Defined in `crons[].prompt` | Defined in `## Heartbeat Behavior` of CLAUDE.md |
| **Typical use** | Daily reports, planned tasks | Monitoring, event alerts |
| **Example** | "Every morning find the news and send a digest" | "Every hour check for urgent breaking news, if so notify" |

The heartbeat is more like a monitoring loop than a task scheduler. The agent autonomously decides if there is something to do.

---

## Full example: news-monitor

**`agents/news-monitor/CLAUDE.md`**
```markdown
# news-monitor

You are a concise journalist. You monitor daily news and send brief summaries.

## Style
- Maximum 3 news items per brief
- Dry and informative tone, no commentary
- English, sources cited with URL

## Heartbeat Behavior

Check if memory/today.md exists and was created today.
- If it doesn't exist or is from yesterday: do nothing.
- If it exists and is from today: add a line with timestamp and "status: ok".

## Active Skills
- ../../../skills/global/brave-search/skill.md
```

**`agents/news-monitor/cron.yaml`**
```yaml
name: news-monitor
enabled: true
heartbeat: 3600
heartbeat_model: claude-haiku-4-5-20251001
telegram_chat_id: ""
permissions:
  bash: false
  internet: true
  write_outside_dir: false
  telegram_without_approval: true
crons:
  - id: morning-brief
    schedule: "0 8 * * *"
    model: claude-haiku-4-5-20251001
    prompt: >
      Find the 3 most important news stories today in the world.
      For each: title, one line summary, source URL.
      Write the result to memory/today.md.
      Then write the formatted text to send via Telegram as output.
```

---

## Creating an agent

**Via wizard (recommended):**
```
http://localhost:3333/wizard.html
```

**Via CLI:**
```bash
mycow agent create agent-name
```

**Manually:**
1. Create the folder `agents/agent-name/`
2. Create `CLAUDE.md` with identity and behavior
3. Create `cron.yaml` with schedule and permissions
4. Create `memory/core.md`, `memory/working.md`, `memory/decisions.md`
5. Restart the daemon (or use `/resume agent-name` via Telegram)

---

## Telegram commands

| Command | Effect |
|---------|---------|
| `/run name` | Manually run the first cron |
| `/pause name` | Pause cron and heartbeat |
| `/resume name` | Resume |
| `/logs name` | Last 5 logs |
| `/heartbeat name` | Force immediate heartbeat |
| `/schedule name` | Next cron executions |
| `/stop` | Global kill switch — stops everything |
