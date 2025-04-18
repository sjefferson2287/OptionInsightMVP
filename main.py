import argparse
import json
import os
import pandas as pd
from src.fetch_data import get_stock_data, get_option_chain
from src.indicators import compute_indicators
from src.pricing_models import calculate_theoretical_prices
from src.greeks import compute_greeks
from src.report import generate_report

def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

def main(symbols=None, expiration=None):
    config = load_config()
    symbols = symbols or config["symbols"]
    expiration = expiration or config["expiration"]
    lookback = config.get("lookback_days", 30)
    filters = config.get("filters", {})

    all_results = []

    for symbol in symbols:
        print(f"Analyzing {symbol}...")

        stock_df = get_stock_data(symbol, lookback)
        if stock_df.empty:
            continue

        last_close = stock_df["Close"].iloc[-1]
        hist_vol = stock_df["Close"].pct_change().rolling(window=20).std().iloc[-1] * (252 ** 0.5)

        indicators = compute_indicators(stock_df)
        option_chain = get_option_chain(symbol, expiration)
        if option_chain.empty:
            continue

        option_chain = calculate_theoretical_prices(option_chain, last_close, expiration, hist_vol=hist_vol)
        option_chain = compute_greeks(option_chain, last_close, sigma=hist_vol)
        report = generate_report(symbol, option_chain, indicators, filters)

        if not report.empty:
            all_results.append(report)

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        os.makedirs("output", exist_ok=True)
        final_df.to_csv("output/report.csv", index=False)
        print("Report saved to output/report.csv")
    else:
        print("No qualifying trades found.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", help="Stock symbols")
    parser.add_argument("--expiration", type=str, help="Option expiration date")
    args = parser.parse_args()

    main(symbols=args.symbols, expiration=args.expiration)
