import json, os
from datetime import datetime, timedelta
import pandas as pd
from .fetch_data import get_stock_data, get_option_chain
from .indicators import compute_indicators
from .pricing_models import calculate_theoretical_prices
from .greeks import compute_greeks
from .report import generate_report

def load_config():
    return json.load(open("config.json"))

def backtest_single_leg(symbol, start_date, end_date, hold_days, lookback, filters, tech_filters, max_days):
    total_days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + lookback
    stock_hist = get_stock_data(symbol, days=total_days)
    stock_hist.index = pd.to_datetime(stock_hist.index).date
    results = []
    current = pd.to_datetime(start_date).date()
    last    = pd.to_datetime(end_date).date()

    while current <= last:
        hist = stock_hist.loc[:current]
        if len(hist) < lookback:
            current += timedelta(days=1); continue

        last_close = hist["Close"].iloc[-1]
        iv_hist    = hist["Close"].pct_change().rolling(20).std().iloc[-1] * (252**0.5)
        indicators = compute_indicators(hist)

        chain = get_option_chain(symbol, expiration=None, max_days_to_expiry=max_days)
        if chain.empty:
            current += timedelta(days=1); continue

        chain = calculate_theoretical_prices(chain, last_close, hist_vol=iv_hist)
        chain = compute_greeks(chain, last_close, sigma=iv_hist)

        report = generate_report(symbol, chain, indicators, filters, tech_filters)
        if report.empty:
            current += timedelta(days=1); continue

        entry = report.sort_values(["score","mispricing"], ascending=[False,False]).iloc[0]
        ep, exp_dt = entry["lastPrice"], pd.to_datetime(entry["expiration"]).date()
        exit_dt = min(current + timedelta(days=hold_days), exp_dt)

        exit_chain = get_option_chain(symbol, expiration=entry["expiration"], max_days_to_expiry=max_days)
        er = exit_chain[exit_chain["contractSymbol"]==entry["contractSymbol"]]
        xp = er["lastPrice"].iloc[0] if not er.empty else None

        pnl = (xp - ep)*100 if xp is not None else None
        results.append({
            "symbol":symbol, "entry_date":current, "exit_date":exit_dt,
            "contract":entry["contractSymbol"], "strike":entry["strike"],
            "entry_price":ep, "exit_price":xp, "pnl":pnl,
            "score":entry["score"], "days_held":(exit_dt-current).days
        })
        current += timedelta(days=1)

    return pd.DataFrame(results)

if __name__ == "__main__":
    cfg  = load_config()
    f    = cfg.get("filters", {})
    tf   = cfg.get("technical_filters", {})
    lb   = cfg.get("lookback_days", 30)
    mdte = cfg.get("max_days_to_expiry", 60)
    # Example params — consider turning these into CLI args later
    sym, start, end, hold = "AAPL", "2025-01-02", "2025-03-31", 7
    print(f"Backtest {sym} {start}→{end} hold {hold}d…")
    bt = backtest_single_leg(sym, start, end, hold, lb, f, tf, mdte)
    wins = bt["pnl"].gt(0).sum()
    total = len(bt); ret = bt["pnl"].sum(); avg = bt["pnl"].mean()
    print(f"Trades: {total}, Wins: {wins}/{total}, PnL: ${ret:.2f}, Avg: ${avg:.2f}")
    os.makedirs("output", exist_ok=True)
    out = f"output/backtest_{sym}_{start}_{end}.csv"
    bt.to_csv(out, index=False)
    print("Saved:", out)
