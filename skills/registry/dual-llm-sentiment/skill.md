# Skill: Dual-LLM Sentiment

## Goal
Analizza le news recenti su ETF commodities usando due LLM in parallelo:
- **Claude** via CLI (gratuito, abbonamento Pro/Max)
- **OpenAI GPT-4o-mini** via API (~$0.08/mese per uso tipico)

Confronta i due sentiment: il consenso amplifica il segnale, il disaccordo lo attenua.

---

## Come usarla

```bash
# Singolo ticker
python3 skills/dual-llm-sentiment/sentiment.py GLD

# Multipli
python3 skills/dual-llm-sentiment/sentiment.py GLD USO UNG
```

Oppure da subprocess:

```python
import subprocess, json

result = subprocess.run(
    ["python3", "skills/dual-llm-sentiment/sentiment.py", "GLD", "SLV"],
    capture_output=True, text=True, timeout=120
)
data = json.loads(result.stdout)
```

---

## Output JSON

```json
{
  "ticker": "GLD",
  "commodity": "Gold",
  "timestamp": "2026-04-13T22:00:00",
  "news_count": 6,
  "claude": {
    "score": 0.65,
    "confidence": 82,
    "direction": "bullish",
    "top_catalyst": "Central banks increasing gold reserves",
    "summary": "..."
  },
  "openai": {
    "score": 0.58,
    "confidence": 75,
    "direction": "bullish",
    "top_catalyst": "Gold rises on safe-haven demand",
    "summary": "..."
  },
  "consensus": "agree",
  "avg_score": 0.923,
  "avg_confidence": 79
}
```

---

## Logica consenso

| consensus | Condizione | Effetto avg_score |
|-----------|-----------|-------------------|
| `agree` | Entrambi > 0.1 o entrambi < -0.1 | × 1.5 (amplificato) |
| `both_neutral` | Entrambi < ±0.1 | neutro |
| `disagree` | Direzioni opposte | × 0.5 (attenuato) |
| `no_news` | Brave non trova news | score = 0 |

---

## Scenari di fallback

| Scenario | Comportamento |
|----------|--------------|
| Nessuna news | `consensus: "no_news"`, score 0, nessun crash |
| Claude CLI timeout | campo `error` in `claude`, OpenAI funziona |
| OpenAI timeout | campo `error` in `openai`, Claude funziona |
| BRAVE_API_KEY mancante | news vuote → `no_news` |

---

## Ticker supportati

| Ticker | Commodity |
|--------|-----------|
| GLD | Gold |
| SLV | Silver |
| USO | WTI Crude Oil |
| UNG | Natural Gas |
| WEAT | Wheat |
| CORN | Corn |
| DBA | Agricultural commodities |
| CPER | Copper |
| DBC | Broad commodities |
| URA | Uranium nuclear energy |

---

## Dipendenze

```bash
pip install requests
```

Richiede nel `.env`:
- `BRAVE_API_KEY` — Brave Search API (gratuito fino a 2000 query/mese)
- `OPENAI_API_KEY` — GPT-4o-mini (~$0.08/mese per uso tipico)

Claude gira via CLI — **nessuna `ANTHROPIC_API_KEY` necessaria**.

---

## Costi stimati

| Componente | Costo |
|------------|-------|
| Claude via CLI | €0 (abbonamento Pro/Max) |
| OpenAI GPT-4o-mini | ~$0.0003/chiamata |
| Brave Search | Gratuito fino a 2000 query/mese |

6 ticker × 2 scan/giorno × 22 giorni = ~264 chiamate/mese = **~$0.08/mese**.

---

## Note su Claude CLI

- `claude -p "prompt"` esegue un singolo prompt senza sessione interattiva
- `--output-format json` restituisce `{"result": "testo risposta"}` parsabile
- Non serve `--dangerously-skip-permissions` (nessun tool eseguito, solo testo)
- Se `claude` non è nel PATH del daemon, usa il path completo (es. `/usr/local/bin/claude`)
