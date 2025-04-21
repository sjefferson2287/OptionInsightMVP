import pandas as pd

def generate_report(symbol: str,
                    df: pd.DataFrame,
                    indicators: pd.DataFrame,
                    filters: dict,
                    tech_filters: dict) -> pd.DataFrame:
    """
    Builds a scored report of options for `symbol`, and *flags* RSI/BB conditions
    without dropping any rows. Returns every contract that passes the core filters,
    plus four new columns:
      - RSI_Oversold
      - RSI_Overbought
      - BB_Break_Lower
      - BB_Break_Upper
    """

    if df.empty or indicators.empty:
        return pd.DataFrame()

    # 1) Attach the latest indicator values to every row
    latest = indicators.iloc[-1]
    df = df.copy()
    df["RSI"]     = latest["RSI"]
    df["UpperBB"] = latest["UpperBB"]
    df["LowerBB"] = latest["LowerBB"]
    if "Close" in latest:
        df["Close"] = latest["Close"]

    # 2) Compute flags for technical conditions (but do NOT filter)
    rsi_low  = tech_filters.get("rsi_oversold")
    rsi_high = tech_filters.get("rsi_overbought")

    df["RSI_Oversold"]   = (df["RSI"] <= rsi_low) if rsi_low is not None else False
    df["RSI_Overbought"] = (df["RSI"] >= rsi_high) if rsi_high is not None else False

    df["BB_Break_Lower"] = (df["lastPrice"] <= df["LowerBB"]) if tech_filters.get("bb_break_lower") else False
    df["BB_Break_Upper"] = (df["lastPrice"] >= df["UpperBB"]) if tech_filters.get("bb_break_upper") else False

    # 3) Apply your core option filters
    mask = (
        (df["delta"].abs() >= filters.get("min_delta", 0.0)) &
        (df["theta"]        <= filters.get("max_theta", 0.0)) &
        (df["impliedVolatility"] >= filters.get("min_iv", 0.0)) &
        (df["openInterest"] >= filters.get("min_open_interest", 0))
    )
    df = df[mask]

    # 4) Compute your existing score
    df["score"] = (
        (df["delta"].abs() >= filters.get("min_delta", 0.0)).astype(int) +
        (df["theta"]        <= filters.get("max_theta", 0.0)).astype(int) +
        (df["impliedVolatility"] >= filters.get("min_iv", 0.0)).astype(int) +
        (df["openInterest"] >= filters.get("min_open_interest", 0)).astype(int)
    )

    # 5) Include the new flag columns in the output
    columns = [
        "ticker","contractSymbol","strike","type","expiration",
        "lastPrice","theoretical_price","mispricing","impliedVolatility",
        "delta","theta","vega","openInterest","volume","daysToExpiry",
        "expiryBucket","RSI","UpperBB","LowerBB",
        "RSI_Oversold","RSI_Overbought","BB_Break_Lower","BB_Break_Upper",
        "score"
    ]
    existing = [c for c in columns if c in df.columns]
    return df[existing].reset_index(drop=True)
