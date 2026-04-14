#!/usr/bin/env python3
"""
Skill dual-llm-sentiment per MyCow.
LLM #1: Claude via CLI (gratuito, usa abbonamento Pro/Max)
LLM #2: OpenAI GPT-4o-mini via API
"""

import os
import sys
import json
import subprocess
import requests
from datetime import datetime
from pathlib import Path


def _load_env() -> None:
    """Carica .env dalla root di MyCow se python-dotenv non è disponibile."""
    try:
        from dotenv import load_dotenv
        # Cerca .env nella root di MyCow (due livelli sopra skills/global/dual-llm-sentiment/)
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
        else:
            load_dotenv()  # fallback: .env nella cwd
    except ImportError:
        # dotenv non installato: carica manualmente
        for candidate in [
            Path(__file__).parent.parent.parent / ".env",
            Path.home() / "mycow" / ".env",
            Path(".env"),
        ]:
            if candidate.exists():
                with open(candidate) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, _, v = line.partition("=")
                            os.environ.setdefault(k.strip(), v.strip())
                break


_load_env()

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SENTIMENT_PROMPT = """Analyze these recent news articles about {commodity} ({ticker}).

NEWS:
{news_text}

Respond ONLY with a JSON object, no other text, no markdown backticks:
{{
  "score": <float from -1.0 (very bearish) to +1.0 (very bullish)>,
  "confidence": <int from 0 to 100>,
  "direction": "<bullish|bearish|neutral>",
  "top_catalyst": "<one sentence describing the main price driver>",
  "summary": "<2-3 sentence summary of the news landscape>"
}}
"""


def search_news(ticker: str, commodity: str) -> str:
    """Cerca news recenti via Brave News Search API."""
    url = "https://api.search.brave.com/res/v1/news/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {
        "q": f"{commodity} {ticker} price",
        "count": 8,
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as e:
        print(f"Brave search error for {ticker}: {e}", file=sys.stderr)
        return ""

    if not results:
        return ""

    news_text = ""
    for i, r in enumerate(results[:8], 1):
        title = r.get("title", "")
        description = r.get("description", "")
        source = r.get("meta_url", {}).get("hostname", "unknown")
        news_text += f"{i}. [{source}] {title}\n   {description}\n\n"

    return news_text


def ask_claude(prompt: str) -> dict:
    """
    Chiama Claude via CLI (gratuito, usa abbonamento Pro/Max).
    Non consuma crediti API.
    """
    try:
        result = subprocess.run(
            [
                "claude",
                "-p", prompt,
                "--model", "claude-haiku-4-5-20251001",
                "--output-format", "json",
            ],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=os.path.expanduser("~"),
        )

        if result.returncode != 0:
            return {
                "score": 0,
                "confidence": 0,
                "direction": "neutral",
                "error": f"CLI exit code {result.returncode}: {result.stderr[:200]}",
            }

        # Claude CLI con --output-format json restituisce {"result": "..."}
        response = json.loads(result.stdout)
        text = response.get("result", "")

        # Pulisci eventuali backtick markdown
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        return json.loads(text)

    except subprocess.TimeoutExpired:
        return {"score": 0, "confidence": 0, "direction": "neutral", "error": "Claude CLI timeout"}
    except json.JSONDecodeError as e:
        return {"score": 0, "confidence": 0, "direction": "neutral", "error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"score": 0, "confidence": 0, "direction": "neutral", "error": str(e)}


def ask_openai(prompt: str) -> dict:
    """Chiama OpenAI GPT-4o-mini via API."""
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500,
            },
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]

        # Pulisci backtick
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        return json.loads(text)

    except requests.exceptions.Timeout:
        return {"score": 0, "confidence": 0, "direction": "neutral", "error": "OpenAI timeout"}
    except json.JSONDecodeError as e:
        return {"score": 0, "confidence": 0, "direction": "neutral", "error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"score": 0, "confidence": 0, "direction": "neutral", "error": str(e)}


def analyze_sentiment(ticker: str, commodity: str) -> dict:
    """Analisi sentiment dual-LLM per un singolo ticker."""

    # 1. Cerca news
    news_text = search_news(ticker, commodity)

    if not news_text:
        return {
            "ticker": ticker,
            "commodity": commodity,
            "timestamp": datetime.now().isoformat(),
            "news_count": 0,
            "claude": {"score": 0, "confidence": 0, "direction": "neutral"},
            "openai": {"score": 0, "confidence": 0, "direction": "neutral"},
            "consensus": "no_news",
            "avg_score": 0,
            "avg_confidence": 0,
        }

    prompt = SENTIMENT_PROMPT.format(
        commodity=commodity, ticker=ticker, news_text=news_text
    )

    # 2. Chiama entrambi gli LLM
    claude_result = ask_claude(prompt)
    openai_result = ask_openai(prompt)

    # 3. Confronta
    s1 = claude_result.get("score", 0)
    s2 = openai_result.get("score", 0)

    if (s1 > 0.1 and s2 > 0.1) or (s1 < -0.1 and s2 < -0.1):
        consensus = "agree"
    elif abs(s1) < 0.1 and abs(s2) < 0.1:
        consensus = "both_neutral"
    else:
        consensus = "disagree"

    # Media pesata: amplifica se concordano, attenua se discordano
    if consensus == "agree":
        avg_score = ((s1 + s2) / 2) * 1.5
    elif consensus == "disagree":
        avg_score = ((s1 + s2) / 2) * 0.5
    else:
        avg_score = (s1 + s2) / 2

    avg_score = max(-1.0, min(1.0, avg_score))  # clamp

    return {
        "ticker": ticker,
        "commodity": commodity,
        "timestamp": datetime.now().isoformat(),
        "news_count": news_text.count("\n\n"),
        "claude": claude_result,
        "openai": openai_result,
        "consensus": consensus,
        "avg_score": round(avg_score, 3),
        "avg_confidence": round(
            (claude_result.get("confidence", 0) + openai_result.get("confidence", 0)) / 2
        ),
    }


# Mappatura ticker → nome commodity
TICKER_MAP = {
    "GLD": "Gold",
    "SLV": "Silver",
    "USO": "WTI Crude Oil",
    "UNG": "Natural Gas",
    "WEAT": "Wheat",
    "CORN": "Corn",
    "DBA": "Agricultural commodities",
    "CPER": "Copper",
    "DBC": "Broad commodities",
    "URA": "Uranium nuclear energy",
}


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["GLD"]
    results = []
    for ticker in tickers:
        commodity = TICKER_MAP.get(ticker, ticker)
        print(f"Analyzing {ticker} ({commodity})...", file=sys.stderr)
        result = analyze_sentiment(ticker, commodity)
        results.append(result)
    print(json.dumps(results, indent=2))
