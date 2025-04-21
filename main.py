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
    """Loads configuration from config.json"""
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found. Please create it.")
        return None
    except json.JSONDecodeError:
        print("Error: config.json is not valid JSON.")
        return None

def main(symbols=None, expiration=None):
    """Main function to fetch data, calculate metrics, and generate report."""
    config = load_config()
    if config is None:
        return  # Exit if config loading failed

    # 1) Determine symbols and expiration
    symbols_to_run      = symbols if symbols else config.get("symbols", [])
    if not symbols_to_run:
        print("Error: No symbols specified in config.json or via command line.")
        return

    effective_expiration = expiration if expiration is not None else config.get("expiration")

    # 2) Load parameters
    lookback            = config.get("lookback_days", 30)
    filters             = config.get("filters", {})
    tech_filters        = config.get("technical_filters", {})
    max_days_to_expiry  = config.get("max_days_to_expiry")

    all_results = []

    for symbol in symbols_to_run:
        symbol = symbol.upper()
        print(f"Analyzing {symbol}...")

        # --- Stock data & volatility ---
        stock_df = get_stock_data(symbol, lookback)
        if stock_df is None or stock_df.empty:
            print(f"  • No stock data for {symbol}, skipping.")
            continue
        if len(stock_df) < 2:
            print(f"  • Only {len(stock_df)} days of data for {symbol}, need ≥2, skipping.")
            continue

        last_close = stock_df["Close"].iloc[-1]

        # 20‑day rolling std → hist_vol
        rolling_std = stock_df["Close"].pct_change().rolling(window=20).std()
        if rolling_std.empty:
            print(f"  • Not enough data for volatility calc for {symbol}, skipping.")
            continue

        last_std = rolling_std.iloc[-1]
        if isinstance(last_std, pd.Series):
            na_flag = last_std.isna().any()
        else:
            na_flag = pd.isna(last_std)
        if na_flag:
            print(f"  • Volatility result NaN for {symbol}, skipping.")
            continue

        try:
            scalar_std = last_std.item() if isinstance(last_std, pd.Series) else last_std
            hist_vol = float(scalar_std) * (252 ** 0.5)
        except Exception as e:
            print(f"  • Error converting volatility to float for {symbol}: {e}, skipping.")
            continue

        # --- Indicators ---
        indicators = compute_indicators(stock_df)
        if indicators is None or indicators.empty:
            print(f"  • Indicators failed for {symbol}, skipping.")
            continue

        # --- Option chain ---
        option_chain = get_option_chain(
            symbol,
            expiration=effective_expiration,
            max_days_to_expiry=max_days_to_expiry
        )
        if option_chain is None or option_chain.empty:
            print(f"  • No options for {symbol} (exp={effective_expiration}), skipping.")
            continue

        # --- Theoretical pricing & Greeks ---
        sigma_val = hist_vol
        option_chain = calculate_theoretical_prices(
            option_chain,
            last_close,
            effective_expiration,
            hist_vol=sigma_val
        )
        if option_chain is None or option_chain.empty:
            print(f"  • Pricing failed for {symbol}, skipping.")
            continue

        option_chain = compute_greeks(option_chain, last_close, sigma=sigma_val)
        if option_chain is None or option_chain.empty:
            print(f"  • Greeks failed for {symbol}, skipping.")
            continue

        # --- Build your report ---
        report = generate_report(symbol, option_chain, indicators, filters, tech_filters)
        if report is not None and not report.empty:
            all_results.append(report)

    # --- Save results ---
    if all_results:
        try:
            final_df = pd.concat(all_results, ignore_index=True)
            os.makedirs("output", exist_ok=True)
            output_file = os.path.join("output", "report.csv")
            final_df.to_csv(output_file, index=False)
            print(f"Report saved to {output_file}")
        except Exception as e:
            print(f"Error saving final report: {e}")
    else:
        print("No qualifying trades found across all symbols.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OptionInsight MVP Scanner")
    parser.add_argument("--symbols", nargs="+",
                        help="Override tickers (default from config.json)")
    parser.add_argument("--expiration", type=str, default=None,
                        help="Option expiration date (YYYY-MM-DD); omit to scan all.")
    args = parser.parse_args()

    main(symbols=args.symbols, expiration=args.expiration)
