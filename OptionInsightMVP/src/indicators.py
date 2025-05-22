import pandas as pd

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
    Adds fib_23, fib_38, fib_50, fib_61, fib_78 (levels)
    and fibDist_23… fibDist_78 (abs % dist) based on min/max over window.
    """
    if window:
        slice_df = df.tail(window)
    else:
        slice_df = df
    low, high = slice_df["Close"].min(), slice_df["Close"].max()
    ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
    for r in ratios:
        lvl      = high - (high - low) * r
        col_lvl  = f"fib_{int(r*1000)//10}"
        col_dist = f"fibDist_{int(r*1000)//10}"
        df[col_lvl]     = lvl
        df[col_dist]    = (df["Close"] - lvl).abs() / lvl
    return df

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
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
    df["EMA_Signal"] = compute_ema_crossover(df, fast=12, slow=26)

    # MACD histogram
    df = compute_macd_hist(df, fast=12, slow=26, signal=9)

    # Fibonacci proximity over the last 30 days
    df = compute_fibonacci(df, window=30)

    # Clean up intermediate
    df.drop(columns=["STD20"], inplace=True)

    return df
