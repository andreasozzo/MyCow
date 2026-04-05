# Skills

Una skill è un insieme di istruzioni operative in Markdown che insegna a un agente come usare uno strumento specifico (ricerca web, notifiche Telegram, git, ecc.). Le skill vengono incluse nel contesto di Claude Code prima di ogni esecuzione.

---

## Skill disponibili

| Skill | Descrizione | Env richieste |
|-------|-------------|---------------|
| `brave-search` | Ricerca web via Brave Search API — privata, senza tracking | `BRAVE_API_KEY` |
| `web-fetch` | Scarica e legge pagine web con requests + BeautifulSoup | — |
| `telegram-notify` | Guida su come formattare output per Telegram | — |
| `git-workflow` | Convenzioni per commit semantici, branch, PR | — |

---

## Installare una skill

**Via CLI:**
```bash
mycow skill install brave-search
```

**Via Web UI:** Settings → Skills → Installa

**Via API:**
```bash
curl -X POST http://localhost:3333/api/skills/install \
  -H "Content-Type: application/json" \
  -d '{"name": "brave-search"}'
```

Dopo l'installazione, la skill è disponibile in `skills/global/` e può essere abilitata su qualsiasi agente.

---

## Abilitare una skill su un agente

**Via CLI:**
```bash
mycow skill add brave-search --agent news-monitor
```

**Via Web UI:** Dettaglio agente → Tab Skills → toggle ON

**Manualmente** — aggiungi al `CLAUDE.md` dell'agente:
```markdown
## Skills Attive
- ../../../skills/global/brave-search/skill.md
```

---

## Disinstallare una skill

```bash
mycow skill uninstall brave-search
```

Questo rimuove la skill da `skills/global/` e aggiorna il `CLAUDE.md` di tutti gli agenti che la usavano.

---

## Creare una skill custom

Ogni skill è una cartella in `skills/registry/` con due file.

**Struttura:**
```
skills/
└── registry/
    └── mia-skill/
        ├── skill.md        ← istruzioni operative per Claude Code
        └── manifest.yaml   ← metadati e requisiti
```

**`manifest.yaml`:**
```yaml
name: mia-skill
version: 1.0.0
description: Descrizione breve di cosa fa questa skill
requires_env:
  - MIA_API_KEY      # variabili d'ambiente necessarie (lista vuota se nessuna)
```

**`skill.md`:**
```markdown
# Mia Skill

Istruzioni operative per Claude Code su come usare questo strumento.

## Quando usarla
Descrivi in quali situazioni l'agente deve ricorrere a questa skill.

## Come usarla
Passi concreti, esempi di codice, endpoint API, parametri, parsing output.

## Gestione errori
Cosa fare se l'API restituisce 429, 401, timeout, ecc.

## Limiti
Vincoli da rispettare (rate limit, max caratteri, costi, ecc.)
```

Dopo aver creato la skill in `skills/registry/`, installala con:
```bash
mycow skill install mia-skill
```

---

## Variabili d'ambiente richieste

Alcune skill richiedono API key nel file `.env`:

```bash
# .env
BRAVE_API_KEY=BSA...          # per brave-search
TELEGRAM_BOT_TOKEN=...        # per telegram-notify (già usato dal daemon)
```

Lo stato delle variabili è visibile in Web UI → Settings e via API:
```bash
curl http://localhost:3333/api/skills
# → campo requires_env + env_configured per ogni skill
```
