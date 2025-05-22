# test_api.py

import os
from decouple import config
import requests
import yfinance as yf
import json

# load your API key from .env
POLYGON_KEY = config("POLYGON_API_KEY")  

# change this list to test whatever tickers you like
TEST_SYMBOLS = ["MARA", "TLT", "IWM"]

def test_polygon(symbol: str):
    print(f"\n--- Polygon snapshot for {symbol} ---")
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={POLYGON_KEY}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    print(f"Returned {len(results)} contracts")
    # print first 3 raw entries
    for entry in results[:3]:
        print(json.dumps(entry, indent=2))

def test_yfinance(symbol: str):
    print(f"\n--- yfinance history for {symbol} ---")
    ticker = yf.Ticker(symbol)
    # last 5 trading days
    df = ticker.history(period="5d", auto_adjust=True)
    print(df.tail())

if __name__ == "__main__":
    for sym in TEST_SYMBOLS:
        try:
            test_polygon(sym)
        except Exception as e:
            print(f"Polygon error for {sym}: {e}")
        try:
            test_yfinance(sym)
        except Exception as e:
            print(f"yfinance error for {sym}: {e}")
