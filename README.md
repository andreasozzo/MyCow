# 🐄 MyCow

**The proactive layer for Claude Code.**

Claude Code è reattivo — aspetta che tu gli parli. MyCow aggiunge il layer proattivo: agenti autonomi che lavorano mentre non stai guardando, ti contattano su Telegram, e eseguono task pianificati via cron.

---

## Prerequisiti

- [Node.js](https://nodejs.org) (per Claude Code CLI)
- [Claude Code CLI](https://github.com/anthropics/claude-code): `npm install -g @anthropic-ai/claude-code`
- [Python 3.11+](https://python.org)

---

## Installazione (Windows)

```powershell
irm https://mycow.dev/install.ps1 | iex
```

Oppure manualmente:

```powershell
git clone https://github.com/tuonome/mycow
cd mycow
pip install -r requirements.txt
copy .env.example .env
# Apri .env e configura le tue API keys
python daemon/main.py start
```

---

## Come funziona

Ogni agente è una cartella in `agents/` con:
- `CLAUDE.md` — identità, task cron, comportamento heartbeat
- `cron.yaml` — schedule, heartbeat, permessi
- `memory/` — stato persistente dell'agente

Il daemon avvia:
- **CronScheduler** — esegue task a orari fissi
- **HeartbeatManager** — l'agente valuta autonomamente se agire ogni N minuti
- **TelegramBridge** — comunicazione bidirezionale con l'utente
- **API REST** — backend per la Web UI su `http://localhost:3333`

---

## Sicurezza

- Permessi espliciti opt-in per ogni agente (`--allowedTools`)
- Mai `--dangerously-skip-permissions`
- API solo su `127.0.0.1`
- Kill switch via Telegram: `/stop`

---

## Licenza

Business Source License 1.1 — gratuito per uso personale e non commerciale.
Per uso commerciale: vedi [COMMERCIAL.md](COMMERCIAL.md).
Diventa MIT 4 anni dalla prima release pubblica.
