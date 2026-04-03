# MyCow 🐄

## Cos'è MyCow
MyCow è un layer proattivo per Claude Code. Permette di creare agenti autonomi con heartbeat, cron schedulati e comunicazione bidirezionale via Telegram. Gli agenti lavorano mentre l'utente non sta guardando.

**Posizionamento:** Semplice dove OpenClaw è complesso. Sicuro dove OpenClaw è pericoloso. Focalizzato dove altri framework sono generici.

---

## Decisioni Architetturali (non riaprire senza motivo)

### Stack
- **Daemon:** Python 3.11+ — cross-platform, zero compilazione
- **Scheduler:** APScheduler — cron in-process, no dipendenze esterne
- **Telegram:** python-telegram-bot — asincrono, bidirezionale
- **Web UI:** HTML/JS/CSS puro servito dal daemon Python — zero build step
- **Web Search:** Brave Search API — privata, economica, API semplice
- **Web Fetch:** requests + BeautifulSoup — leggero, no browser
- **AI Core:** Claude Code CLI in subprocess non-interattivo

### Perché HTML/JS puro e non Next.js/React
Zero build step, zero Node dipendenza per la UI, `pip install mycow && mycow start` apre il browser. La UI può evolversi dopo senza cambiare architettura.

### Perché non Docker
Barriera troppo alta per il target. MyCow deve installarsi in 2 minuti.

### Claude Code CLI — Come si wrappa
```bash
# Comando base non-interattivo
claude -p "prompt" \
  --allowedTools "Read,Write,Bash(git *)" \
  --output-format json \
  --max-turns 10 \
  --working-dir agents/nome/

# Flags importanti
# -p / --print       → non-interattivo, stampa e termina
# --output-format    → text | json | stream-json
# --allowedTools     → permessi espliciti (mai --dangerously-skip-permissions)
# --max-turns        → limite iterazioni per sicurezza
# --append-system-prompt → aggiunge istruzioni senza sostituire il default
# --continue         → riprende ultima sessione
# --bare             → skip auto-discovery (per CI/script puri)
```

**Gotcha noto:** Claude Code CLI può bloccarsi senza TTY nonostante `-p`. Usare sempre timeout espliciti nel subprocess Python.

```python
result = subprocess.run(
    ["claude", "-p", prompt, "--output-format", "json"],
    capture_output=True,
    text=True,
    timeout=300,  # sempre timeout
    cwd=agent_working_dir
)
```

---

## Struttura Repository

```
mycow/
  daemon/
    main.py              # entrypoint, avvia tutto
    scheduler.py         # APScheduler, gestisce cron agenti
    agent_runner.py      # wrappa Claude Code CLI in subprocess
    telegram_bridge.py   # bot Telegram bidirezionale
    api.py               # API REST locale (localhost:3333)
  web/
    index.html           # dashboard agenti
    agent.html           # dettaglio agente + log
    wizard.html          # crea nuovo agente
    skills.html          # gestione skill
    settings.html        # configurazione globale
    assets/
      app.js
      style.css
  agents/                # cartelle agenti (gitignore contenuto sensibile)
    .gitkeep
  skills/
    global/              # skill condivise tra tutti gli agenti
    manifest/            # manifest YAML delle skill installate
  install/
    install.ps1          # Windows
    install.sh           # Mac/Linux
  CLAUDE.md              # questo file
  COMMERCIAL.md          # info licenza commerciale
  LICENSE                # BSL 1.1
  README.md
```

---

## Struttura Agente

Ogni agente è una cartella autonoma generata dal wizard:

```
agents/
  agent-name/
    CLAUDE.md            # identità, obiettivi, comportamenti, skill attive
    cron.yaml            # schedule e trigger
    memory/
      core.md            # fatti stabili, non cambia spesso
      working.md         # stato corrente, task in corso
      decisions.md       # log decisioni prese dall'agente
    skills/              # symlink o copia dalle global skills
    .claude/
      settings.json      # permessi espliciti Claude Code
```

### Formato cron.yaml
```yaml
name: news-monitor
enabled: true
schedule: "0 8 * * *"      # ogni mattina alle 8
heartbeat: 3600            # heartbeat ogni ora (secondi)
telegram_chat_id: "xxxxx"
permissions:
  bash: false
  internet: true
  write_outside_dir: false
  telegram_without_approval: true
```

---

## Skill System

Le skill sono file markdown con istruzioni operative + manifest YAML.

```
skills/
  global/
    brave-search/
      skill.md
      manifest.yaml
    web-fetch/
      skill.md
      manifest.yaml
    telegram-notify/
      skill.md
      manifest.yaml
    git-workflow/
      skill.md
      manifest.yaml
```

### Formato manifest.yaml
```yaml
name: brave-search
version: 1.0.0
description: Cerca sul web via Brave Search API
requires_env:
  - BRAVE_API_KEY
mcp_server: null
```

Il CLAUDE.md di ogni agente include le skill attive con riferimento al file:
```markdown
## Skills Attive
- ../../../skills/global/brave-search/skill.md
- ../../../skills/global/telegram-notify/skill.md
```

---

## Sicurezza — Principi Non Negoziabili

1. **Permessi opt-in** — ogni agente ha permessi espliciti. Tutto il resto è negato.
2. **Mai `--dangerously-skip-permissions`** — usare sempre `--allowedTools` con least privilege.
3. **Timeout sempre** — ogni subprocess Claude Code ha timeout esplicito.
4. **Nessuna porta aperta di default** — Telegram è pull-based, Tailscale è opzionale.
5. **Kill switch globale** — `/stop` su Telegram ferma tutti gli agenti immediatamente.
6. **Secrets in .env** — mai in CLAUDE.md o file versionati.

---

## Licenza

**Business Source License 1.1 (BSL 1.1)**
- Uso personale/non commerciale: gratuito
- Uso commerciale: richiede licenza (contatto in COMMERCIAL.md)
- Change Date: 4 anni dalla prima release pubblica → diventa MIT

---

## Contesto di Sviluppo

- **OS sviluppo primario:** Windows, PowerShell nativo
- **Target utente:** Developer/power user con Claude Code già installato
- **Prerequisiti utente:** Node.js + Claude Code CLI + Python 3.11+
- **Installer Windows:** `irm https://mycow.dev/install.ps1 | iex`

---

## Cosa NON fare

- Non aggiungere Docker come requisito
- Non usare framework frontend complessi (React, Next.js, Vue) — HTML/JS puro
- Non aprire porte di rete senza Tailscale
- Non usare `--dangerously-skip-permissions`
- Non fare feature creep — lo scope V1 è fisso
- Non reinventare Claude Code — wrapparlo, non sostituirlo
- Non usare database complessi — file JSON/YAML/Markdown sono sufficienti per V1
