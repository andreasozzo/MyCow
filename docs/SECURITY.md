# Security

MyCow è progettato con un modello di sicurezza esplicito: **ogni permesso è opt-in, tutto il resto è negato**.

---

## Principi non negoziabili

1. **Permessi espliciti** — ogni agente dichiara esattamente cosa può fare in `cron.yaml`. Nessun permesso implicito.
2. **Mai `--dangerously-skip-permissions`** — MyCow usa sempre `--allowedTools` con least privilege. Non c'è modo di aggirarlo via configurazione.
3. **Timeout su tutto** — ogni subprocess Claude Code ha un timeout esplicito (default 300s). Un agente bloccato non blocca il daemon.
4. **Secrets mai in chiaro** — token e API key vivono in `.env`, mai in `CLAUDE.md` o `cron.yaml`. Il subprocess dell'agente non riceve `TELEGRAM_BOT_TOKEN`.
5. **API solo su localhost** — il daemon Flask ascolta su `127.0.0.1:3333`, mai su `0.0.0.0`.
6. **Kill switch globale** — `/stop` su Telegram ferma immediatamente tutti gli agenti.

---

## Modello di permessi

I permessi si configurano in `cron.yaml` per ogni agente:

```yaml
permissions:
  bash: false                    # esecuzione comandi shell
  internet: true                 # WebSearch e WebFetch
  write_outside_dir: false       # scrittura fuori da agents/nome/
  telegram_without_approval: true  # invio Telegram senza conferma
```

**Livelli risultanti per `--allowedTools`:**

| Configurazione | Tools permessi |
|----------------|----------------|
| `bash: false` | `Read, Write` |
| `bash: false` + `internet: true` | `Read, Write, WebSearch, WebFetch` |
| `bash: true` | `Read, Write, Bash(git *), Bash(npm test), Bash(python *)` |

Gli agenti non ricevono mai `Bash(*)` illimitato — i comandi bash permessi sono una lista fissa.

---

## EMERGENCY_STOP

Il kill switch crea un file `EMERGENCY_STOP` nella root del progetto.

**Come si attiva:**
- Comando Telegram: `/stop`
- API: `POST /api/stop-all`
- Manualmente: `touch EMERGENCY_STOP` nella root

**Effetto:**
- Scheduler e HeartbeatManager si fermano immediatamente
- Ogni chiamata a `run_agent()` viene bloccata con stato `"blocked"` prima di avviare qualsiasi subprocess
- Il daemon rimane in esecuzione (API e web UI funzionano ancora)

**Come rimuoverlo:**
```bash
rm EMERGENCY_STOP   # Mac/Linux
del EMERGENCY_STOP  # Windows
```

Oppure via Web UI → Settings → "Riabilita agenti".

---

## Secrets

**Dove vanno:**
```bash
# .env (mai committato)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
BRAVE_API_KEY=...
ANTHROPIC_API_KEY=...
```

**Il file `.env` non viene mai letto dagli agenti.** Il daemon carica le variabili all'avvio e le rimuove dall'ambiente del subprocess prima di avviare Claude Code:

```python
clean_env = {k: v for k, v in os.environ.items()
             if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
```

**Cosa non fare:**
- Non mettere token in `CLAUDE.md` o `cron.yaml`
- Non committare `.env` (è nel `.gitignore`)
- Non usare secrets come parte del prompt

---

## API locale

L'API Flask è accessibile solo da localhost per design. Nessuna autenticazione necessaria perché non è esposta in rete.

Se hai bisogno di accesso remoto (es. da telefono via Telegram), **usa Telegram** — è già integrato e cifrato.

Per accesso remoto alla Web UI:

### Tailscale (raccomandato)

Tailscale crea una VPN zero-config tra i tuoi dispositivi senza aprire porte pubbliche.

```bash
# Installa Tailscale
# Mac:   brew install tailscale
# Linux: curl -fsSL https://tailscale.com/install.sh | sh
# Win:   https://tailscale.com/download/windows

# Avvia
tailscale up

# Accedi alla Web UI dal tuo telefono via IP Tailscale
# Es: http://100.x.x.x:3333
```

---

## Input sanitization

Il bridge Telegram sanitizza tutti i comandi in entrata:
- Max 2000 caratteri per messaggio
- Pattern bloccati: `--dangerously`, `rm -rf`, `format c:`, `del /f /s`
- Whitelist chat_id: solo i chat ID configurati in `.env` possono inviare comandi

---

## Reporting vulnerabilità

Se trovi una vulnerabilità di sicurezza, non aprire una issue pubblica. Contatta direttamente tramite i recapiti in [COMMERCIAL.md](../COMMERCIAL.md).
