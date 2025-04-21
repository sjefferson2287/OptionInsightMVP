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
    # 1) Load settings
    config            = load_config()
    symbols           = symbols or config.get("symbols", [])
    expiration        = expiration if expiration is not None else config.get("expiration")
    lookback          = config.get("lookback_days", 30)
    filters           = config.get("filters", {})
    tech_filters      = config.get("technical_filters", {})    # ← grab your RSI/BB settings
    max_days_to_expiry = config.get("max_days_to_expiry")

    all_results = []

    for symbol in symbols:
        print(f"Analyzing {symbol}...")

        # 2) Stock data & indicators
        stock_df = get_stock_data(symbol, lookback)
        if stock_df.empty:
            print(f"  • No stock data for {symbol}, skipping.")
            continue

        last_close = stock_df["Close"].iloc[-1]
        hist_vol   = (
            stock_df["Close"]
                .pct_change()
                .rolling(window=20).std()
                .iloc[-1]
            * (252 ** 0.5)
        )
        indicators = compute_indicators(stock_df)

        # 3) Option chain (with your horizon)
        option_chain = get_option_chain(
            symbol,
            expiration=expiration,
            max_days_to_expiry=max_days_to_expiry
        )
        if option_chain.empty:
            print(f"  • No options for {symbol} (exp={expiration}), skipping.")
            continue

        # 4) Theoretical pricing & Greeks
        option_chain = calculate_theoretical_prices(
            option_chain,
            last_close,
            expiration,
            hist_vol=hist_vol
        )
        option_chain = compute_greeks(option_chain, last_close, sigma=hist_vol)

        # 5) Build report rows, now passing tech_filters
        report = generate_report(
            symbol,
            option_chain,
            indicators,
            filters,
            tech_filters
        )
        if not report.empty:
            all_results.append(report)

    # 6) Concatenate & save
    valid_results = [df for df in all_results if not df.empty]
    if valid_results:
        final_df = pd.concat(valid_results, ignore_index=True)
        os.makedirs("output", exist_ok=True)
        final_df.to_csv("output/report.csv", index=False)
        print("Report saved to output/report.csv")
    else:
        print("No qualifying trades found.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OptionInsight MVP Scanner")
    parser.add_argument(
        "--symbols", nargs="+",
        help="Override tickers (default from config.json)"
    )
    parser.add_argument(
        "--expiration", type=str,
        help="Option expiration date (YYYY-MM-DD). Omit to scan all expirations."
    )
    args = parser.parse_args()

    main(symbols=args.symbols, expiration=args.expiration)
