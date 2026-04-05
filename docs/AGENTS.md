# Agents

Un agente MyCow è una cartella in `agents/` con tre file obbligatori: `CLAUDE.md`, `cron.yaml` e una cartella `memory/`. Il daemon legge questi file per sapere cosa fare, quando farlo e con quali permessi.

---

## Struttura cartella

```
agents/
└── nome-agente/
    ├── CLAUDE.md          ← identità, comportamento, skill attive
    ├── cron.yaml          ← schedule, heartbeat, permessi, prompt
    └── memory/
        ├── core.md        ← fatti stabili (chi sei, cosa fai)
        ├── working.md     ← stato corrente, task in corso
        └── decisions.md   ← log decisioni prese dall'agente
```

---

## CLAUDE.md

Il file di identità dell'agente. Claude Code lo legge come prompt di sistema prima di ogni esecuzione.

```markdown
# nome-agente

Descrizione breve: cosa fa questo agente e il suo stile operativo.

## Stile
- Regole di comportamento specifiche
- Tono, formato output, vincoli

## Heartbeat Behavior

Istruzioni per il comportamento autonomo (eseguito ogni N minuti).
La differenza rispetto al cron: il heartbeat DECIDE lui se agire o no.

Esempio:
- Se X è cambiato dall'ultimo check: agisci e scrivi in output il messaggio da inviare
- Se tutto è nella norma: non fare nulla, non inviare messaggi

## Skills Attive
- ../../../skills/global/brave-search/skill.md
- ../../../skills/global/telegram-notify/skill.md
```

**Sezioni:**
- Header + descrizione: obbligatorio
- `## Stile`: opzionale, ma raccomandato
- `## Heartbeat Behavior`: obbligatorio se heartbeat > 0 in cron.yaml
- `## Skills Attive`: lista percorsi relativi alle skill da usare

---

## cron.yaml

Configurazione completa dell'agente: schedule, heartbeat, permessi e prompt.

```yaml
name: nome-agente          # deve corrispondere al nome cartella
enabled: true              # false per disabilitare senza cancellare

heartbeat: 3600            # intervallo heartbeat in secondi (0 = disabilitato)
heartbeat_model: claude-haiku-4-5-20251001  # modello per heartbeat (opzionale)

telegram_chat_id: "123456789"  # chat ID Telegram per notifiche di questo agente

permissions:
  bash: false                    # permette comandi bash (default: false)
  internet: true                 # permette WebSearch e WebFetch (default: false)
  write_outside_dir: false       # permette scrittura fuori dalla cartella agente
  telegram_without_approval: true  # invia su Telegram senza conferma manuale

crons:
  - id: morning-brief            # identificatore univoco del cron
    schedule: "0 8 * * *"        # espressione cron standard
    model: claude-haiku-4-5-20251001  # modello Claude da usare
    prompt: >
      Prompt completo da eseguire a orario fisso.
      Scrivi in output il testo da inviare via Telegram.

  - id: evening-recap
    schedule: "0 18 * * *"
    model: claude-sonnet-4-6
    prompt: >
      Secondo cron con schedule diverso.
```

**Campi obbligatori:** `name`, `enabled`, `permissions`, `crons`

**Campi opzionali:** `heartbeat`, `heartbeat_model`, `telegram_chat_id`

---

## Cron vs Heartbeat

| | Cron | Heartbeat |
|---|---|---|
| **Quando esegue** | A orari fissi (schedule) | Ogni N secondi in loop |
| **Decide se agire** | No — esegue sempre | Sì — valuta lo stato e decide |
| **Prompt** | Definito in `crons[].prompt` | Definito in `## Heartbeat Behavior` del CLAUDE.md |
| **Uso tipico** | Report quotidiani, task pianificati | Monitoring, alert su eventi |
| **Esempio** | "Ogni mattina cerca le news e invia digest" | "Ogni ora controlla se ci sono breaking news urgenti, se sì avvisa" |

Il heartbeat è più simile a un loop di monitoraggio che a un task scheduler. L'agente decide autonomamente se c'è qualcosa da fare.

---

## Esempio completo: news-monitor

**`agents/news-monitor/CLAUDE.md`**
```markdown
# news-monitor

Sei un giornalista sintetico. Monitori le notizie quotidiane e invii brief concisi.

## Stile
- Massimo 3 notizie per brief
- Tono asciutto e informativo, niente commenti
- Italiano, fonti citate con URL

## Heartbeat Behavior

Controlla se memory/today.md esiste ed è stato creato oggi.
- Se non esiste o è di ieri: non fare nulla.
- Se esiste ed è di oggi: aggiungi una riga con timestamp e "status: ok".

## Skills Attive
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
      Cerca le 3 notizie più importanti di oggi nel mondo e in Italia.
      Per ogni notizia: titolo, una riga di sintesi, fonte URL.
      Scrivi il risultato in memory/today.md.
      Poi scrivi in output il testo formattato da inviare via Telegram.
```

---

## Creare un agente

**Via wizard (raccomandato):**
```
http://localhost:3333/wizard.html
```

**Via CLI:**
```bash
mycow agent create nome-agente
```

**Manualmente:**
1. Crea la cartella `agents/nome-agente/`
2. Crea `CLAUDE.md` con identità e comportamento
3. Crea `cron.yaml` con schedule e permessi
4. Crea `memory/core.md`, `memory/working.md`, `memory/decisions.md`
5. Riavvia il daemon (o usa `/resume nome-agente` via Telegram)

---

## Comandi Telegram

| Comando | Effetto |
|---------|---------|
| `/run nome` | Esegui il primo cron manualmente |
| `/pause nome` | Metti in pausa cron e heartbeat |
| `/resume nome` | Riprendi |
| `/logs nome` | Ultimi 5 log |
| `/heartbeat nome` | Forza heartbeat immediato |
| `/schedule nome` | Prossime esecuzioni cron |
| `/stop` | Kill switch globale — ferma tutto |
