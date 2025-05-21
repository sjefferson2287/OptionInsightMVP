import argparse
import json
import os
import pandas as pd
import time
import logging
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Assuming your custom modules are in a 'src' folder relative to main.py
from src.fetch_data import get_stock_data, get_option_chain
from src.indicators import compute_indicators
from src.pricing_models import calculate_theoretical_prices
from src.greeks import compute_greeks
from src.report import generate_report

def load_config():
    """Loads configuration from config.json"""
    log.debug("Trying to load config...")
    try:
        with open("config.json", "r") as f:
            config_data = json.load(f)
            log.debug("config.json loaded successfully.")
            return config_data
    except FileNotFoundError:
        log.error("config.json not found. Please create it.")
        return None
    except json.JSONDecodeError:
        log.error("config.json is not valid JSON.")
        return None

def main(symbols=None, expiration=None):
    """Main function to fetch data, calculate metrics, and generate report."""
    log.debug("Starting main function...")
    overall_start_time = time.time() # Optional profiling

    config = load_config()
    if config is None:
        log.debug("Exiting because config failed to load.")
        return
    indicator_config = config.get("indicators", {})

    log.debug("Config loaded, setting up variables...")
    # Load settings with defaults
    symbols_to_run = symbols if symbols else config.get("symbols", [])
    if not symbols_to_run:
        log.error("No symbols specified in config.json or via command line.")
        return

    effective_expiration = expiration if expiration is not None else config.get("expiration")
    lookback = config.get("lookback_days", 30)
    filters = config.get("filters", {})
    tech_filters = config.get("technical_filters", {})
    max_days_to_expiry = config.get("max_days_to_expiry")

    all_results = []
    log.debug("Starting symbol loop...")

    for symbol in symbols_to_run:
        symbol_start_time = time.time() # Optional profiling
        log.debug(f"----- Processing {symbol} -----")

        # 1. Stock data & indicators
        log.debug(f"Getting stock data for {symbol}...")
        stock_df = get_stock_data(symbol, lookback)
        if stock_df is None or stock_df.empty:
            log.warning(f"No stock data fetched for {symbol}, skipping.")
            continue
        log.debug(f"Got stock data for {symbol}. Time: {time.time() - symbol_start_time:.2f}s")

        if len(stock_df) < 2:
            log.warning(f"Not enough historical data ({len(stock_df)} days) for {symbol} to calculate volatility, skipping.")
            continue

        last_close = stock_df["Close"].iloc[-1]

        log.debug(f"Calculating hist_vol for {symbol}...")
        step_start_time = time.time() # Optional profiling
        rolling_std = stock_df["Close"].pct_change().rolling(window=20).std()
        if rolling_std.empty:
            log.warning(f"Could not calculate historical volatility (rolling stddev series empty) for {symbol}, skipping.")
            continue
        last_std = rolling_std.iloc[-1]
        na_flag = False
        if isinstance(last_std, pd.Series):
            na_flag = last_std.isna().any()
        else:
            na_flag = pd.isna(last_std)
        if na_flag:
            log.warning(f"Could not calculate historical volatility (result was NaN) for {symbol}, skipping.")
            continue
        try:
            if isinstance(last_std, pd.Series):
                 scalar_std = last_std.item()
            else:
                 scalar_std = last_std
            hist_vol = float(scalar_std) * (252 ** 0.5)
            log.debug(f"Calculated hist_vol for {symbol}: {hist_vol:.4f}. Time: {time.time() - step_start_time:.2f}s")
        except ValueError as e:
             log.warning(f"Error converting volatility std dev to float for {symbol}: {e}. Skipping.")
             continue
        except Exception as e:
             log.warning(f"Unexpected error calculating final hist_vol for {symbol}: {e}. Skipping.")
             continue

        log.debug(f"Calculating indicators for {symbol}...")
        step_start_time = time.time() # Optional profiling
        ema_fast = indicator_config.get("ema_fast", 12)
        ema_slow = indicator_config.get("ema_slow", 26)
        macd_fast = indicator_config.get("macd_fast", 12)
        macd_slow = indicator_config.get("macd_slow", 26)
        macd_signal = indicator_config.get("macd_signal", 9)
        indicators = compute_indicators(
            stock_df,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            macd_fast=macd_fast,
            macd_slow=macd_slow,
            macd_signal=macd_signal
        )
        if indicators is None or indicators.empty:
            log.warning(f"Could not compute indicators for {symbol}, skipping.")
            continue
        log.debug(f"Calculated indicators for {symbol}. Time: {time.time() - step_start_time:.2f}s")

        # 2. Option chain
        log.debug(f"Getting option chain for {symbol}...")
        step_start_time = time.time() # Optional profiling
        option_chain = get_option_chain(
            symbol,
            expiration=effective_expiration,
            max_days_to_expiry=max_days_to_expiry
        )
        if option_chain is None or option_chain.empty:
            log.warning(f"No options fetched for {symbol} (exp={effective_expiration}), skipping.")
            continue
        log.debug(f"Got option chain for {symbol}. Rows: {len(option_chain)}. Time: {time.time() - step_start_time:.2f}s")

        # 3. Theoretical pricing & Greeks
        sigma_val = hist_vol
        log.debug(f"Calculating prices for {symbol}...")
        step_start_time = time.time() # Optional profiling
        option_chain = calculate_theoretical_prices(
            option_chain,
            last_close,
            config=config, # Pass the config for risk_free_rate
            hist_vol=sigma_val
        )
        if option_chain is None or option_chain.empty:
            log.warning(f"Pricing failed for {symbol}, skipping.")
            continue
        log.debug(f"Calculated prices for {symbol}. Time: {time.time() - step_start_time:.2f}s")

        log.debug(f"Calculating greeks for {symbol}...")
        step_start_time = time.time() # Optional profiling
        option_chain = compute_greeks(option_chain, last_close, config=config, sigma=sigma_val)
        if option_chain is None or option_chain.empty:
            log.warning(f"Greeks calculation failed for {symbol}, skipping.")
            continue
        log.debug(f"Calculated greeks for {symbol}. Time: {time.time() - step_start_time:.2f}s")

        # 4. Build report rows
        log.debug(f"Generating report for {symbol}...")
        step_start_time = time.time() # Optional profiling
        report = generate_report(symbol, option_chain, indicators, filters, tech_filters)
        log.debug(f"Finished generating report for {symbol}. Time: {time.time() - step_start_time:.2f}s")

        if report is not None and not report.empty:
            log.debug(f"Appending report for {symbol} ({len(report)} rows).")
            all_results.append(report)
        else:
            log.debug(f"Report for {symbol} was empty or None.")
        log.debug(f"----- Finished {symbol}. Total time: {time.time() - symbol_start_time:.2f}s -----") # ADDED

    log.debug("Finished symbol loop.")

    # 5. Concatenate & save
    log.debug("Checking if results exist...")
    if all_results:
        log.debug(f"Found {len(all_results)} reports to concatenate.")
        try:
            log.debug("Concatenating results...")
            final_df = pd.concat(all_results, ignore_index=True)
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            from datetime import datetime
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_file = os.path.join(output_dir, f"report_{ts}.csv")
            log.debug(f"Saving final report ({len(final_df)} rows) to {out_file}...")
            final_df.to_csv(out_file, index=False)
            log.info(f"Report saved to {out_file}") # Use log.info for the final report location
            log.debug("Report saving complete.")
        except Exception as e:
            log.error(f"Error during final concatenation or saving: {e}")
    else:
        log.warning("No qualifying trades found across all symbols.")
        log.debug("No results to save.")

    log.debug(f"Reached end of main function. Total runtime: {time.time() - overall_start_time:.2f}s") # ADDED

if __name__ == "__main__":
    log.debug("Script entry point (__name__ == '__main__')")
    parser = argparse.ArgumentParser(description="OptionInsight MVP Scanner")
    parser.add_argument(
        "--symbols", nargs="+",
        help="Override tickers (default from config.json)"
    )
    parser.add_argument(
        "--expiration", type=str, default=None,
        help="Option expiration date (YYYY-MM-DD). Omit to scan all expirations."
    )
    log.debug("Parsing arguments...")
    args = parser.parse_args()
    log.debug(f"Arguments parsed: {args}")

    log.debug("Calling main function...")
    main(symbols=args.symbols, expiration=args.expiration)
    log.debug("main function finished.")
