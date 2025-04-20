import pandas as pd

def generate_report(symbol: str,
                    df: pd.DataFrame,
                    indicators: pd.DataFrame,
                    filters: dict) -> pd.DataFrame:
    """
    Builds a filtered, scored report of options for `symbol`.

    Expects `df` to already include:
      - lastPrice, theoretical_price, mispricing, impliedVolatility,
      - delta, gamma, theta, vega, openInterest,
      - volume, daysToExpiry, expiryBucket

    `indicators` should be the stock indicators DataFrame (with RSI, UpperBB, LowerBB).
    `filters` is your config["filters"] dict, e.g. min_delta, max_theta, min_iv, min_open_interest.
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

    # 2) Apply your filters
    mask = (
        (df["delta"].abs() >= filters.get("min_delta", 0.0)) &
        (df["theta"]        <= filters.get("max_theta", 0.0)) &
        (df["impliedVolatility"] >= filters.get("min_iv", 0.0)) &
        (df["openInterest"] >= filters.get("min_open_interest", 0))
    )
    df = df[mask]

    # 3) Compute a simple score (sum of passing filters)
    df["score"] = (
        (df["delta"].abs() >= filters.get("min_delta", 0.0)).astype(int) +
        (df["theta"]        <= filters.get("max_theta", 0.0)).astype(int) +
        (df["impliedVolatility"] >= filters.get("min_iv", 0.0)).astype(int) +
        (df["openInterest"] >= filters.get("min_open_interest", 0)).astype(int)
    )

    # 4) Select the columns for the final CSV, including volume + expiry buckets
    columns = [
        "ticker",
        "contractSymbol",
        "strike",
        "type",
        "expiration",
        "lastPrice",
        "theoretical_price",
        "mispricing",
        "impliedVolatility",
        "delta",
        "theta",
        "vega",
        "openInterest",
        "volume",
        "daysToExpiry",
        "expiryBucket",
        "RSI",
        "UpperBB",
        "LowerBB",
        "score"
    ]

    # Only include columns that exist in df
    existing = [c for c in columns if c in df.columns]
    return df[existing].reset_index(drop=True)
