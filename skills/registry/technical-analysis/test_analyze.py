#!/usr/bin/env python3
"""
Unit test per la skill technical-analysis.
Confronta output con valori attesi e verifica coerenza.
"""

from analyze import analyze
import json


def test_gld():
    """Test su GLD (oro) - deve restituire tutti i campi."""
    result = analyze("GLD", period="3mo", interval="1d")

    # Verifica struttura
    assert "error" not in result, f"Errore: {result.get('error')}"
    assert result["ticker"] == "GLD"
    assert "indicators" in result
    assert "trend" in result

    ind = result["indicators"]

    # RSI deve essere tra 0 e 100
    assert 0 <= ind["rsi_14"] <= 100, f"RSI fuori range: {ind['rsi_14']}"

    # SMA deve essere positivo
    assert ind["sma_20"] > 0, f"SMA20 non valido: {ind['sma_20']}"

    # Volume ratio deve essere positivo
    assert ind["volume_ratio"] > 0, f"Volume ratio non valido: {ind['volume_ratio']}"

    # Bollinger position deve essere uno dei valori attesi
    assert ind["bollinger_position"] in ["lower", "middle", "upper"]

    # MACD histogram deve essere un numero
    assert isinstance(ind["macd_histogram"], float)

    print(f"GLD OK - RSI: {ind['rsi_14']}, SMA20: {ind['sma_20']}, "
          f"Vol ratio: {ind['volume_ratio']}, BB: {ind['bollinger_position']}")
    print(f"  Trend: {result['trend']}")
    return True


def test_multiple():
    """Test su più ticker commodity."""
    tickers = ["GLD", "SLV", "USO", "UNG", "CPER"]
    for ticker in tickers:
        result = analyze(ticker, period="1mo", interval="1d")
        if "error" in result:
            print(f"  SKIP {ticker}: {result['error']}")
            continue
        rsi = result["indicators"]["rsi_14"]
        price = result["price"]
        print(f"  {ticker}: prezzo ${price:.2f}, RSI {rsi:.1f}")


def test_invalid_ticker():
    """Test su ticker non esistente."""
    result = analyze("XXXYZNOTREAL")
    assert "error" in result, "Dovrebbe ritornare errore per ticker invalido"
    print(f"  Ticker invalido gestito correttamente")


if __name__ == "__main__":
    print("=== Test GLD ===")
    test_gld()

    print("\n=== Test multipli ===")
    test_multiple()

    print("\n=== Test ticker invalido ===")
    test_invalid_ticker()

    print("\nTutti i test passati.")
