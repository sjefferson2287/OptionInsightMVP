# src/backtest.py

import json
import os
from datetime import datetime, timedelta

import pandas as pd
import math

from src.fetch_data import get_stock_data, get_option_chain, get_historic_option_price
from src.indicators import compute_indicators
from src.pricing_models import calculate_theoretical_prices
from src.greeks import compute_greeks
from src.report import generate_report

def load_config():
    with open("config.json") as f:
        return json.load(f)

def should_exit(current_date, entry, stock_indicators, tech_filters):
    """
    Return True the moment any exit condition is met.
    - RSI above overbought
    - EMA crossover flips bearish
    """
    # get indicator values at this date
    try:
        rsi = stock_indicators.loc[current_date, "RSI"]
        ema_signal = stock_indicators.loc[current_date, "EMA_Signal"]
    except KeyError:
        return False

    # exit if overbought
    if rsi >= tech_filters.get("rsi_overbought", 70):
        return True

    # exit if EMA fast < EMA slow (signal flips to 0)
    if ema_signal == 0:
        return True

    return False

def backtest_single_leg(
    symbol: str,
    start_date: str,
    end_date: str,
    lookback: int,
    filters: dict,
    tech_filters: dict,
    max_days_to_expiry: int,
):
    """
    1) Each trading day between start_date and end_date:
       - build stock history & indicators up to that day
       - scan for best-scoring contract (entry)
    2) From entry date, step forward day-by-day:
       - check exit signals
       - or expire
    3) Record PnL per trade
    """
    # prepare full stock history
    total_days = lookback + (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
    stock_hist = get_stock_data(symbol, days=total_days)
    stock_hist.index = pd.to_datetime(stock_hist.index).date

    results = []
    current = pd.to_datetime(start_date).date()
    last    = pd.to_datetime(end_date).date()

    while current <= last:
        # **ENTRY**: prepare lookback slice
        hist_slice = stock_hist.loc[:current].tail(lookback)
        if len(hist_slice) < lookback:
            current += timedelta(days=1)
            continue

        last_close = hist_slice["Close"].iloc[-1]
        iv_hist = hist_slice["Close"].pct_change().rolling(20).std().iloc[-1] * (252 ** 0.5)
        indicators = compute_indicators(hist_slice)

        # fetch option chain and price it / compute greeks
        option_chain = get_option_chain(symbol, expiration=None, max_days_to_expiry=max_days_to_expiry)
        if option_chain.empty:
            current += timedelta(days=1)
            continue

        option_chain = calculate_theoretical_prices(option_chain, last_close, hist_vol=iv_hist)
        option_chain = compute_greeks(option_chain, last_close, sigma=iv_hist)

        # generate report (this applies your filters & scoring)
        report = generate_report(symbol, option_chain, indicators, filters, tech_filters)
        if report.empty:
            current += timedelta(days=1)
            continue

        # pick the top contract by score → entry
        entry = report.sort_values(["score", "mispricing"], ascending=[False, False]).iloc[0]
        entry_date  = current
        
        # Get historic entry price
        entry_price = get_historic_option_price(entry["contractSymbol"], entry_date)
        if math.isnan(entry_price):
            # print(f"Debug: {current} - Entry price is NaN for {entry['contractSymbol']} on {entry_date}. Skipping trade.")
            current += timedelta(days=1)
            continue
            
        exp_date    = pd.to_datetime(entry["expiration"]).date()

        # **EXIT**: walk day by day until signal or expiry
        exit_price = entry_price # Default if no exit signal or price found before expiry
        exit_date  = entry_date
        
        # If position held until expiry, exit price is price on expiry date.
        # If exited earlier due to signal, exit price is on that signal day.
        
        temp_exit_date = entry_date
        found_exit_signal = False
        while temp_exit_date < exp_date:
            temp_exit_date += timedelta(days=1)
            if temp_exit_date > last: # Ensure we don't go beyond overall backtest end_date
                break 
            
            # rebuild indicators up to new date
            hist2 = stock_hist.loc[:temp_exit_date].tail(lookback)
            if len(hist2) < lookback: # Not enough data for indicators
                continue
            inds2 = compute_indicators(hist2)

            if should_exit(temp_exit_date, entry, inds2, tech_filters):
                exit_date = temp_exit_date
                exit_price = get_historic_option_price(entry["contractSymbol"], exit_date)
                found_exit_signal = True
                break
        
        if not found_exit_signal and exit_date == entry_date: # Held to expiry or beyond backtest end
            exit_date = min(exp_date, last) # Actual exit is on expiry or last day of backtest
            exit_price = get_historic_option_price(entry["contractSymbol"], exit_date)

        # If exit_price is still nan (e.g. no trade on exit_date), PnL will be nan.
        # This is acceptable as it flags an issue with that specific trade's data.
        if math.isnan(exit_price):
            # print(f"Debug: {current} - Exit price is NaN for {entry['contractSymbol']} on {exit_date}. PnL will be NaN.")
            pass # Let PnL be NaN

        pnl = (exit_price - entry_price) * 100 if not math.isnan(exit_price) and not math.isnan(entry_price) else math.nan # per‐contract ×100
        results.append({
            "symbol":       symbol,
            "entry_date":   entry_date,
            "exit_date":    exit_date,
            "contract":     entry["contractSymbol"],
            "strike":       entry["strike"],
            "entry_price":  entry_price,
            "exit_price":   exit_price,
            "pnl":          pnl,
            "score":        entry["score"],
            "days_held":    (exit_date - entry_date).days
        })

        # advance to next trading day after entry to pick a new trade
        current = entry_date + timedelta(days=1)

    return pd.DataFrame(results)


if __name__ == "__main__":
    # load settings
    cfg = load_config()
    filters      = cfg.get("filters", {})
    tech_filters = cfg.get("technical_filters", {})
    lookback     = cfg.get("lookback_days", 30)
    max_dte      = cfg.get("max_days_to_expiry", 60)

    # backtest params
    symbol    = "AAPL"
    start     = "2025-01-02"
    end       = "2025-03-31"

    print(f"Backtest {symbol} {start}→{end} with signal exits…")
    bt = backtest_single_leg(
        symbol=symbol,
        start_date=start,
        end_date=end,
        lookback=lookback,
        filters=filters,
        tech_filters=tech_filters,
        max_days_to_expiry=max_dte
    )

    # summary
    if not bt.empty:
        total = len(bt)
        # Handle potential NaNs in PnL before summing/averaging
        valid_pnl = bt["pnl"].dropna()
        
        wins  = valid_pnl.gt(0).sum()
        ret   = valid_pnl.sum()
        avg   = valid_pnl.mean() if not valid_pnl.empty else 0.0

        print(f"Trades: {total}, Wins: {wins}/{total}, Total PnL: ${ret:.2f}, Avg: ${avg:.2f}")

        os.makedirs("output", exist_ok=True)
        out_path = f"output/backtest_{symbol}_{start}_{end}.csv"
        bt.to_csv(out_path, index=False)
        print(f"Backtest results saved to {out_path}")
    else:
        print("No trades were made during the backtest period.")
