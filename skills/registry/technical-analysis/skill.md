# Skill: Technical Analysis

## Goal
Calcola indicatori tecnici su ETF commodities usando dati storici da yfinance e ta-lib. Restituisce JSON deterministico — nessun LLM coinvolto nei calcoli.

---

## Come usarla

Chiama lo script Python direttamente come subprocess:

```bash
python3 skills/technical-analysis/analyze.py GLD
python3 skills/technical-analysis/analyze.py GLD SLV USO
```

Oppure importa la funzione in un altro script:

```python
import subprocess, json

result = subprocess.run(
    ["python3", "skills/technical-analysis/analyze.py", "GLD"],
    capture_output=True, text=True, timeout=60
)
data = json.loads(result.stdout)
```

---

## Output JSON

```json
{
  "ticker": "GLD",
  "timestamp": "2026-04-13T08:00:00",
  "period": "3mo",
  "interval": "1d",
  "price": 215.40,
  "indicators": {
    "rsi_14": 58.3,
    "sma_20": 210.5,
    "sma_50": 205.1,
    "macd": 1.234,
    "macd_signal": 0.987,
    "macd_histogram": 0.247,
    "bollinger_upper": 222.1,
    "bollinger_lower": 198.9,
    "bollinger_position": "middle",
    "volume_last": 8500000,
    "volume_avg_20": 7200000,
    "volume_ratio": 1.18
  },
  "trend": {
    "price_vs_sma20": "above",
    "price_vs_sma50": "above",
    "macd_direction": "bullish",
    "rsi_zone": "neutral"
  }
}
```

---

## Parametri

| Parametro | Default | Note |
|-----------|---------|------|
| ticker | — | Simbolo ETF (es. GLD, SLV, USO) |
| period | 3mo | 1mo, 3mo, 6mo, 1y |
| interval | 1d | 1d, 1wk |

---

## Dipendenze richieste

```bash
pip install yfinance ta-lib numpy
```

`ta-lib` richiede la libreria C nativa. Su Windows: usa il wheel precompilato da https://github.com/cgohlke/talib-build

---

## Limiti

- Read-only: non piazza ordini, non accede a nessun broker
- I dati yfinance hanno un ritardo di ~15 minuti per gli ETF USA
- Ta-lib richiede almeno 50 candele per SMA50; con meno dati restituisce `null`
