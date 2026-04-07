# Skills

A skill is a set of operational instructions in Markdown that teaches an agent how to use a specific tool (web search, Telegram notifications, git, etc.). Skills are included in the Claude Code context before every execution.

---

## Available skills

| Skill | Description | Required env |
|-------|-------------|--------------|
| `brave-search` | Web search via Brave Search API — private, no tracking | `BRAVE_API_KEY` |
| `web-fetch` | Download and read web pages with requests + BeautifulSoup | — |
| `telegram-notify` | Guide on how to format output for Telegram | — |
| `git-workflow` | Conventions for semantic commits, branches, PRs | — |

---

## Installing a skill

**Via CLI:**
```bash
mycow skill install brave-search
```

**Via Web UI:** Settings → Skills → Install

**Via API:**
```bash
curl -X POST http://localhost:3333/api/skills/install \
  -H "Content-Type: application/json" \
  -d '{"name": "brave-search"}'
```

After installation, the skill is available in `skills/global/` and can be enabled on any agent.

---

## Enabling a skill on an agent

**Via CLI:**
```bash
mycow skill add brave-search --agent news-monitor
```

**Via Web UI:** Agent detail → Skills tab → toggle ON

**Manually** — add to the agent's `CLAUDE.md`:
```markdown
## Active Skills
- ../../../skills/global/brave-search/skill.md
```

---

## Uninstalling a skill

```bash
mycow skill uninstall brave-search
```

This removes the skill from `skills/global/` and updates the `CLAUDE.md` of all agents that were using it.

---

## Creating a custom skill

Each skill is a folder in `skills/registry/` with two files.

**Structure:**
```
skills/
└── registry/
    └── my-skill/
        ├── skill.md        ← operational instructions for Claude Code
        └── manifest.yaml   ← metadata and requirements
```

**`manifest.yaml`:**
```yaml
name: my-skill
version: 1.0.0
description: Brief description of what this skill does
requires_env:
  - MY_API_KEY      # required environment variables (empty list if none)
```

**`skill.md`:**
```markdown
# My Skill

Operational instructions for Claude Code on how to use this tool.

## When to use it
Describe in which situations the agent should use this skill.

## How to use it
Concrete steps, code examples, API endpoints, parameters, output parsing.

## Error handling
What to do if the API returns 429, 401, timeout, etc.

## Limits
Constraints to respect (rate limits, max characters, costs, etc.)
```

After creating the skill in `skills/registry/`, install it with:
```bash
mycow skill install my-skill
```

---

## Required environment variables

Some skills require API keys in the `.env` file:

```bash
# .env
BRAVE_API_KEY=BSA...          # for brave-search
TELEGRAM_BOT_TOKEN=...        # for telegram-notify (already used by the daemon)
```

The status of variables is visible in Web UI → Settings and via API:
```bash
curl http://localhost:3333/api/skills
# → requires_env field + env_configured for each skill
```
