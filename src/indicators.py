import pandas as pd
import numpy as np

def compute_ema_crossover(df: pd.DataFrame, fast: int = 12, slow: int = 26) -> pd.Series:
    """
    Returns a Series of 1 (EMA_fast > EMA_slow) or 0.
    """
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    return (ema_fast > ema_slow).astype(int)

def compute_macd_hist(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    Adds MACD, MACD_Signal, MACD_Hist to df.
    """
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd     = ema_fast - ema_slow
    macd_sig = macd.ewm(span=signal, adjust=False).mean()
    hist     = macd - macd_sig

    df["MACD"]        = macd
    df["MACD_Signal"] = macd_sig
    df["MACD_Hist"]   = hist
    return df

def compute_fibonacci(df: pd.DataFrame, window: int = None) -> pd.DataFrame:
    """
    Adds fib_236, fib_382, fib_500, fib_618, fib_786 (levels)
    and fibDist_236… fibDist_786 (abs % dist) based on min/max over window.
    """
    if window is None or window == 0:
        df_window = df
    else:
        df_window = df.iloc[-window:]

    min_close = df_window["Close"].min()
    max_close = df_window["Close"].max()
    price_range = max_close - min_close

    ratios = [0.236, 0.382, 0.5, 0.618, 0.786]

    for ratio in ratios:
        level = max_close - price_range * ratio
        pct_label = str(int(ratio * 1000))
        df[f"fib_{pct_label}"] = level
        df[f"fibDist_{pct_label}"] = np.where(level != 0, abs(df["Close"] - level) / level, np.nan)
    return df

def compute_indicators(df: pd.DataFrame, ema_fast: int = 12, ema_slow: int = 26, macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9) -> pd.DataFrame:
    """
    Compute and return a DataFrame with:
      - MA20, UpperBB, LowerBB
      - RSI (14)
      - EMA_Signal (12/26)
      - MACD, MACD_Signal, MACD_Hist
      - Fibonacci levels & distances (last 30 days)
    """
    df = df.copy()

    # Bollinger Bands
    df["MA20"]    = df["Close"].rolling(window=20).mean()
    df["STD20"]   = df["Close"].rolling(window=20).std()
    df["UpperBB"] = df["MA20"] + 2 * df["STD20"]
    df["LowerBB"] = df["MA20"] - 2 * df["STD20"]

    # RSI (14)
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0).rolling(window=14).mean()
    loss  = -delta.clip(upper=0).rolling(window=14).mean()
    rs    = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # EMA crossover signal
    df["EMA_Signal"] = compute_ema_crossover(df, fast=ema_fast, slow=ema_slow)

    # MACD histogram
    df = compute_macd_hist(df, fast=macd_fast, slow=macd_slow, signal=macd_signal)

    # Fibonacci levels & distances
    df = compute_fibonacci(df, window=len(df))

    # Clean up intermediate
    df.drop(columns=["STD20"], inplace=True)

    return df
