# 🐄 MyCow

**The proactive layer for Claude Code.**

[![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)](LICENSE)

Claude Code è reattivo — aspetta che tu gli parli. MyCow aggiunge il layer proattivo: agenti autonomi che lavorano mentre non stai guardando, ti contattano su Telegram, ed eseguono task pianificati via cron.

---

## Quick start (5 minuti)

**Windows:**
```powershell
irm https://raw.githubusercontent.com/andreasozzo/mycow/master/install/install.ps1 | iex
```

**Mac / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/andreasozzo/mycow/master/install/install.sh | bash
```

Poi:
```bash
cd ~/MyCow
# Apri .env e aggiungi TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID
mycow start
# Apre http://localhost:3333 — crea il tuo primo agente dal wizard
```

---

## Prerequisiti

- [Node.js](https://nodejs.org) + [Claude Code CLI](https://github.com/anthropics/claude-code): `npm install -g @anthropic-ai/claude-code`
- [Python 3.11+](https://python.org)
- Un bot Telegram (crea con [@BotFather](https://t.me/botfather) in 2 minuti)

---

## Cosa fa

- **Cron scheduler** — esegue task Claude Code a orari fissi (`0 8 * * *` = ogni mattina alle 8)
- **Heartbeat** — ogni N minuti l'agente valuta autonomamente se agire (monitoring, alert su eventi)
- **Telegram bidirezionale** — gli agenti ti contattano proattivamente; tu rispondi e comandi via `/run`, `/stop`, `/logs`
- **Web UI** — dashboard agenti, log real-time, wizard creazione agente, gestione skill
- **Skill system** — capacità modulari (ricerca web, git workflow, notifiche) che si abilitano per agente
- **Kill switch** — `/stop` su Telegram ferma tutto immediatamente

---

## Come funziona

Ogni agente è una cartella autonoma:

```
agents/news-monitor/
├── CLAUDE.md       ← identità e comportamento
├── cron.yaml       ← schedule, heartbeat, permessi
└── memory/         ← stato persistente
```

**`cron.yaml` minimo:**
```yaml
name: news-monitor
enabled: true
heartbeat: 3600          # controlla ogni ora
permissions:
  internet: true
  telegram_without_approval: true
crons:
  - id: morning-brief
    schedule: "0 8 * * *"
    model: claude-haiku-4-5-20251001
    prompt: >
      Cerca le 3 news AI più importanti di oggi.
      Scrivi in output il testo da inviare via Telegram.
```

**Cron vs Heartbeat:**
- **Cron** — esegue *sempre* a orario fisso. Usa per report pianificati.
- **Heartbeat** — l'agente *decide lui* se agire. Usa per monitoring e alert.

---

## Skill disponibili

| Skill | Descrizione | Env |
|-------|-------------|-----|
| `brave-search` | Ricerca web privata via Brave Search API | `BRAVE_API_KEY` |
| `web-fetch` | Scarica e legge pagine web | — |
| `telegram-notify` | Formattazione messaggi Telegram | — |
| `git-workflow` | Commit semantici, branch, PR | — |

```bash
mycow skill install brave-search
mycow skill add brave-search --agent news-monitor
```

---

## Sicurezza

- Permessi opt-in espliciti per agente (`--allowedTools` senza `--dangerously-skip-permissions`)
- API solo su `127.0.0.1:3333` — mai esposta in rete
- Secrets in `.env`, mai nei file dell'agente
- Kill switch: `/stop` su Telegram → file `EMERGENCY_STOP` blocca tutte le esecuzioni

Vedi [docs/SECURITY.md](docs/SECURITY.md) per il modello completo.

---

## Documentazione

- [docs/AGENTS.md](docs/AGENTS.md) — struttura agenti, cron.yaml, CLAUDE.md, esempi
- [docs/SKILLS.md](docs/SKILLS.md) — skill disponibili, installazione, creazione custom
- [docs/SECURITY.md](docs/SECURITY.md) — permessi, EMERGENCY_STOP, Tailscale

---

## Licenza

Business Source License 1.1 — gratuito per uso personale e non commerciale.
Per uso commerciale: vedi [COMMERCIAL.md](COMMERCIAL.md).
Diventa MIT 4 anni dalla prima release pubblica.
