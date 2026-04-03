# Skill: Security First

## Obiettivo
MyCow esegue codice in autonomia, ha accesso al filesystem e a internet. Ogni decisione di sviluppo deve considerare la sicurezza come requisito primario, non come afterthought. Il posizionamento di MyCow vs OpenClaw è proprio questo: sicuro by design.

---

## Principi Non Negoziabili

### 1. Least Privilege Always
Ogni agente ha solo i permessi che servono per il suo task specifico. Se un agente legge news e manda messaggi Telegram, non ha accesso bash né write al filesystem.

```yaml
# ✅ Corretto — permessi minimi
permissions:
  bash: false
  internet: true
  write_outside_dir: false
  telegram_without_approval: true

# ❌ Mai fare questo
permissions:
  all: true
```

### 2. Mai `--dangerously-skip-permissions`
Questo flag bypassa command blocklist, write restrictions e permission prompts di Claude Code. Non usarlo mai in produzione, nemmeno "temporaneamente".

```python
# ✅ Corretto
cmd = ["claude", "-p", prompt, "--allowedTools", "Read,Bash(git status)"]

# ❌ Mai
cmd = ["claude", "-p", prompt, "--dangerously-skip-permissions"]
```

### 3. Timeout Su Tutto
Ogni subprocess ha timeout esplicito. Un agente che si blocca non deve bloccare il sistema.

```python
# ✅ Sempre
result = subprocess.run(cmd, timeout=300, capture_output=True)

# ❌ Mai
result = subprocess.run(cmd, capture_output=True)  # può bloccarsi forever
```

### 4. Secrets Mai in Chiaro
```python
# ✅ Sempre da environment variables
api_key = os.environ.get("BRAVE_API_KEY")

# ❌ Mai hardcoded, mai in CLAUDE.md, mai in file versionati
api_key = "sk-xxxxx"
```

### 5. Input Sanitization
Qualsiasi input che arriva da Telegram prima di essere passato a Claude Code deve essere sanitizzato. Un utente malevolo potrebbe iniettare istruzioni.

```python
# Lunghezza massima
MAX_PROMPT_LENGTH = 2000

# Caratteri pericolosi
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

## Modello di Permessi Agente

### Livelli di Accesso
```
LIVELLO 0 — Read Only
  Può leggere file nella sua cartella
  Può fare ricerche web
  Può mandare messaggi Telegram
  NON può eseguire bash
  NON può scrivere file

LIVELLO 1 — Read + Write (default)
  Tutto il LIVELLO 0
  Può scrivere nella sua cartella agente
  NON può scrivere fuori dalla cartella
  NON può eseguire bash arbitrario

LIVELLO 2 — Developer
  Tutto il LIVELLO 1
  Può eseguire bash con comandi pre-approvati
  Può scrivere in cartelle specifiche autorizzate
  Richiede approvazione Telegram per azioni critiche

LIVELLO 3 — Admin (richiede conferma esplicita)
  Accesso completo
  Ogni sessione richiede conferma via Telegram
  Log audit completo
```

### Mapping Claude Code --allowedTools
```python
PERMISSION_LEVELS = {
    0: "Read",
    1: "Read,Write",
    2: "Read,Write,Bash(git *),Bash(npm test),Bash(python *)",
    3: "Read,Write,Bash(*)"  # richiede conferma Telegram
}
```

---

## Sicurezza Rete

### Telegram — Architettura Pull
Il bot Telegram chiama fuori verso i server Telegram. Nessuna porta in ascolto. Zero surface attack senza Tailscale.

```
Internet → [Telegram Servers] ← polling MyCow daemon
                                (pull, non push)
```

### API Locale
L'API REST gira solo su localhost. Mai bindare su 0.0.0.0 senza Tailscale.

```python
# ✅ Corretto
app.run(host="127.0.0.1", port=3333)

# ❌ Mai in produzione
app.run(host="0.0.0.0", port=3333)
```

### Tailscale (Opzionale)
Se l'utente vuole accesso remoto alla web UI, Tailscale è l'unico metodo supportato. Zero port forwarding, zero ngrok, zero tunnel non verificati.

---

## Audit e Logging

### Ogni Esecuzione Agente Logga
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

### Log Sensibili
- Mai loggare il contenuto completo dei prompt (potrebbero contenere dati sensibili)
- Mai loggare API keys o tokens
- Usa hash per riferimenti a dati sensibili

---

## Kill Switch

### Via Telegram
```
/stop              → ferma tutti gli agenti, daemon rimane attivo
/stop news-monitor → ferma agente specifico
/pause             → pausa tutti i cron (non kill)
/status            → stato di tutti gli agenti
```

### Via Web UI
Bottone "Stop All" sempre visibile in header, colore rosso, richiede conferma.

### Via Filesystem
```bash
# File di emergenza — se esiste, il daemon non avvia agenti
touch mycow/EMERGENCY_STOP
```

---

## Checklist Sicurezza Prima di ogni Feature

- [ ] I permessi sono al minimo necessario?
- [ ] Tutti i subprocess hanno timeout?
- [ ] I secrets sono in variabili d'ambiente?
- [ ] Gli input da Telegram sono sanitizzati?
- [ ] L'API locale è su 127.0.0.1?
- [ ] Le azioni distruttive hanno conferma?
- [ ] Il logging non include dati sensibili?
- [ ] Il kill switch funziona per questa feature?
