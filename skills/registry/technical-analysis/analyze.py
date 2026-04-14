#!/usr/bin/env python3
"""
Skill technical-analysis per MyCow.
Input: ticker, period (default 3mo), interval (default 1d)
Output: JSON con indicatori tecnici
"""

import sys
import json
import yfinance as yf
import talib
import numpy as np
from datetime import datetime


def analyze(ticker: str, period: str = "3mo", interval: str = "1d") -> dict:
    """Scarica dati da yfinance e calcola indicatori via ta-lib."""

    # Download dati
    data = yf.download(ticker, period=period, interval=interval, progress=False)

    if data.empty:
        return {"error": f"Nessun dato per {ticker}", "ticker": ticker}

    # Estrai arrays per ta-lib (flatten per evitare MultiIndex)
    close = data["Close"].values.flatten().astype(float)
    high = data["High"].values.flatten().astype(float)
    low = data["Low"].values.flatten().astype(float)
    volume = data["Volume"].values.flatten().astype(float)

    # Indicatori
    rsi_14 = talib.RSI(close, timeperiod=14)
    sma_20 = talib.SMA(close, timeperiod=20)
    sma_50 = talib.SMA(close, timeperiod=50)
    macd, macd_signal, macd_hist = talib.MACD(close, 12, 26, 9)
    upper_bb, middle_bb, lower_bb = talib.BBANDS(close, timeperiod=20)

    # Volume ratio (volume attuale / media 20 giorni)
    vol_sma_20 = talib.SMA(volume, timeperiod=20)
    volume_ratio = volume[-1] / vol_sma_20[-1] if vol_sma_20[-1] > 0 else 1.0

    # Prezzo corrente
    current_price = float(close[-1])

    # Posizione rispetto a Bollinger
    bb_position = "middle"
    if current_price <= float(lower_bb[-1]):
        bb_position = "lower"
    elif current_price >= float(upper_bb[-1]):
        bb_position = "upper"

    result = {
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "period": period,
        "interval": interval,
        "price": current_price,
        "indicators": {
            "rsi_14": round(float(rsi_14[-1]), 2),
            "sma_20": round(float(sma_20[-1]), 2),
            "sma_50": round(float(sma_50[-1]), 2) if not np.isnan(sma_50[-1]) else None,
            "macd": round(float(macd[-1]), 4),
            "macd_signal": round(float(macd_signal[-1]), 4),
            "macd_histogram": round(float(macd_hist[-1]), 4),
            "bollinger_upper": round(float(upper_bb[-1]), 2),
            "bollinger_lower": round(float(lower_bb[-1]), 2),
            "bollinger_position": bb_position,
            "volume_last": int(volume[-1]),
            "volume_avg_20": int(vol_sma_20[-1]),
            "volume_ratio": round(float(volume_ratio), 2),
        },
        "trend": {
            "price_vs_sma20": "above" if current_price > float(sma_20[-1]) else "below",
            "price_vs_sma50": (
                "above" if not np.isnan(sma_50[-1]) and current_price > float(sma_50[-1])
                else "below" if not np.isnan(sma_50[-1])
                else "n/a"
            ),
            "macd_direction": "bullish" if float(macd_hist[-1]) > 0 else "bearish",
            "rsi_zone": (
                "oversold" if float(rsi_14[-1]) < 30
                else "overbought" if float(rsi_14[-1]) > 70
                else "neutral"
            ),
        },
    }

    return result


def analyze_watchlist(tickers: list, period: str = "3mo", interval: str = "1d") -> list:
    """Analizza una lista di ticker."""
    results = []
    for ticker in tickers:
        try:
            results.append(analyze(ticker, period, interval))
        except Exception as e:
            results.append({"ticker": ticker, "error": str(e)})
    return results


if __name__ == "__main__":
    # Uso da CLI: python analyze.py GLD SLV USO
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["GLD"]
    results = analyze_watchlist(tickers)
    print(json.dumps(results, indent=2))
