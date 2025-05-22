# src/backtest.py

import json
import os
from datetime import datetime, timedelta

import pandas as pd

from src.fetch_data import get_stock_data, get_option_chain
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
        entry_price = entry["lastPrice"]
        entry_date  = current
        exp_date    = pd.to_datetime(entry["expiration"]).date()

        # **EXIT**: walk day by day until signal or expiry
        exit_price = entry_price
        exit_date  = entry_date
        while exit_date < exp_date:
            exit_date += timedelta(days=1)
            # rebuild indicators up to new date
            hist2 = stock_hist.loc[:exit_date].tail(lookback)
            inds2 = compute_indicators(hist2)
            if should_exit(exit_date, entry, inds2, tech_filters):
                # fetch option price for this date
                chain2 = get_option_chain(symbol, expiration=entry["expiration"])
                row2   = chain2.loc[chain2["contractSymbol"] == entry["contractSymbol"]]
                if not row2.empty:
                    exit_price = row2["lastPrice"].iloc[0]
                break

        pnl = (exit_price - entry_price) * 100  # per‐contract ×100
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
    total = len(bt)
    wins  = bt["pnl"].gt(0).sum()
    ret   = bt["pnl"].sum()
    avg   = bt["pnl"].mean()

    print(f"Trades: {total}, Wins: {wins}/{total}, Total PnL: ${ret:.2f}, Avg: ${avg:.2f}")

    os.makedirs("output", exist_ok=True)
    out_path = f"output/backtest_{symbol}_{start}_{end}.csv"
    bt.to_csv(out_path, index=False)
    print(f"Backtest results saved to {out_path}")
