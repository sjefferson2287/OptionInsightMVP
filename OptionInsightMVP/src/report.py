import pandas as pd
import numpy as np # Make sure numpy is imported

# --- CORRECTED FUNCTION DEFINITION ---
def generate_report(symbol: str,
                    df: pd.DataFrame,
                    indicators: pd.DataFrame,
                    filters: dict, # Should contain option filters only
                    tech_filters: dict) -> pd.DataFrame: # Added tech_filters parameter back
# --- END CORRECTION ---
    """
    Builds a filtered, scored report of options for `symbol`.
    - df: option chain DataFrame with pricing, greeks, volume, etc.
    - indicators: stock-indicators DataFrame (indexed by Date) with columns
      ['Close','MA20','UpperBB','LowerBB','RSI', 'EMA_Signal','MACD_Hist',...]
    - filters: dict of config['filters'] (option filters)
    - tech_filters: dict of config['technical_filters']
    """

    # Bail early if no data
    if df.empty or indicators.empty:
        print(f"DEBUG: DataFrame or indicators empty for {symbol} at start of generate_report.")
        return pd.DataFrame()

    # --- SECTION 1: GET LATEST INDICATORS (Corrected with .item()) ---
    try:
        latest = indicators.iloc[-1]
    except IndexError:
        print(f"Warning: Could not get latest indicators for {symbol} (IndexError). Skipping.")
        return pd.DataFrame()

    # Extract scalar values using .item(), include checks for existence & error handling
    try:
        # Use .get for columns that might be missing in 'latest', providing pd.NA as default
        price     = latest.get("Close", pd.NA)
        lowerBB   = latest.get("LowerBB", pd.NA)
        upperBB   = latest.get("UpperBB", pd.NA)
        rsi_val   = latest.get("RSI", pd.NA)
        # Use .get for optional new indicators, provide default 0 or NA as appropriate
        ema_sig   = latest.get("EMA_Signal", 0) # Assuming 0 is a sensible default
        macd_hist = latest.get("MACD_Hist", 0)  # Assuming 0 is a sensible default

        # Apply .item() ONLY if the value retrieved is a Series (handles scalar case too)
        price     = price.item() if isinstance(price, pd.Series) and len(price)==1 else price
        lowerBB   = lowerBB.item() if isinstance(lowerBB, pd.Series) and len(lowerBB)==1 else lowerBB
        upperBB   = upperBB.item() if isinstance(upperBB, pd.Series) and len(upperBB)==1 else upperBB
        rsi_val   = rsi_val.item() if isinstance(rsi_val, pd.Series) and len(rsi_val)==1 else rsi_val

    except Exception as e:
         print(f"Warning: Unexpected error reading/extracting latest indicators for {symbol}: {e}. Assigning NA/defaults.")
         price, lowerBB, upperBB, rsi_val, ema_sig, macd_hist = pd.NA, pd.NA, pd.NA, pd.NA, 0, 0

    # 1a) Copy options df and attach constants on every row
    df = df.copy()
    # Assign the potentially scalar values
    df["RSI"]     = rsi_val
    df["UpperBB"] = upperBB
    df["LowerBB"] = lowerBB
    df["Close"]   = price # Assign price from indicators
    df["EMA_Signal"] = ema_sig
    df["MACD_Hist"]  = macd_hist

    # 1b) Flag missing indicator signals (check if core values are NA)
    missing = pd.isna(rsi_val) or pd.isna(upperBB) or pd.isna(lowerBB) or pd.isna(price)
    df["missing_signal"] = missing # Assign boolean directly

    # 1c) Compute normalized metrics (vectorized, handle potential NA)
    if all(col in df.columns and pd.api.types.is_numeric_dtype(df[col]) for col in ["Close", "UpperBB", "LowerBB", "RSI"]):
        denominator = df["UpperBB"] - df["LowerBB"]
        df["bb_norm"] = np.where(
            np.isclose(denominator, 0) | denominator.isna() | df["Close"].isna() | df["LowerBB"].isna(),
            np.nan,
            (df["Close"] - df["LowerBB"]) / denominator
        )
        df["bb_norm"] = df["bb_norm"].fillna(0.5)

        df["rsi_norm"] = df["RSI"] / 100.0
        df["rsi_norm"] = df["rsi_norm"].fillna(0.5)
    else:
        print(f"Warning: Missing or non-numeric columns for norm calculations in {symbol}. Assigning defaults.")
        df["bb_norm"] = 0.5
        df["rsi_norm"] = 0.5

    # 1d) Flag whether trend thresholds are met (Using tech_filters now for trend)
    tf       = tech_filters # Assuming trend filters are part of tech_filters
    bb_pct   = tf.get("bb_position_pct", 0.5)
    rsi_pct  = tf.get("rsi_position_pct", 0.5)
    if "bb_norm" in df.columns and "rsi_norm" in df.columns:
        df["trend_pass"] = (df["bb_norm"].fillna(0.5) >= bb_pct) & (df["rsi_norm"].fillna(0.5) >= rsi_pct)
    else:
        df["trend_pass"] = False

    # --- SECTION 2: BOLLINGER BAND FILTERS (Using tech_filters) ---
    if tech_filters.get("bb_break_lower"):
        tol = tech_filters.get("bb_tolerance", 0.0)
        if "Close" in df.columns and "LowerBB" in df.columns and not df["Close"].isnull().all() and not df["LowerBB"].isnull().all():
            df = df[~(df["Close"].isna() | df["LowerBB"].isna()) & (df["Close"] <= df["LowerBB"] * (1 + tol))]
    if tech_filters.get("bb_break_upper"):
        tol = tech_filters.get("bb_tolerance", 0.0)
        if "Close" in df.columns and "UpperBB" in df.columns and not df["Close"].isnull().all() and not df["UpperBB"].isnull().all():
            df = df[~(df["Close"].isna() | df["UpperBB"].isna()) & (df["Close"] >= df["UpperBB"] * (1 - tol))]

    # --- SECTION 3: OPTION FILTERS (Using main 'filters') ---
    required_option_cols = ["delta", "theta", "impliedVolatility", "openInterest"]
    if not all(col in df.columns for col in required_option_cols):
        print(f"Warning: Missing required option columns for filtering in {symbol}. Skipping option filters.")
    elif not df.empty:
        df_filtered = df.dropna(subset=required_option_cols)
        if not df_filtered.empty:
            mask = (
                (df_filtered["delta"].abs() >= filters.get("min_delta", 0.0)) &
                (df_filtered["theta"]        <= filters.get("max_theta", 0.0)) &
                (df_filtered["impliedVolatility"] >= filters.get("min_iv", 0.0)) &
                (df_filtered["openInterest"] >= filters.get("min_open_interest", 0))
            )
            df = df.loc[df_filtered[mask].index]
        else:
            df = df_filtered

    # Return early if filtering made df empty
    if df.empty:
         print(f"Info: DataFrame empty for {symbol} after applying filters.")
         return pd.DataFrame()

    # --- SECTION 4: SCORING ---
    score = pd.Series(0, index=df.index)
    if "EMA_Signal" in df.columns: score += (df["EMA_Signal"].fillna(0) > 0).astype(int)
    if "MACD_Hist" in df.columns: score += (df["MACD_Hist"].fillna(0) > 0).astype(int)
    if "delta" in df.columns: score += (df["delta"].abs() >= filters.get("min_delta", 0.0)).fillna(0).astype(int)
    if "theta" in df.columns: score += (df["theta"] <= filters.get("max_theta", 0.0)).fillna(0).astype(int)
    if "impliedVolatility" in df.columns: score += (df["impliedVolatility"] >= filters.get("min_iv", 0.0)).fillna(0).astype(int)
    if "openInterest" in df.columns: score += (df["openInterest"] >= filters.get("min_open_interest", 0)).fillna(0).astype(int)
    # Add BB break score explicitly if desired
    # if tech_filters.get("bb_break_lower") and "Close" in df.columns ... : score += (...)
    df["score"] = score

    # --- SECTION 6: SELECT OUTPUT COLUMNS ---
    columns = [
        "ticker", "contractSymbol", "strike", "type", "expiration",
        "lastPrice", "theoretical_price", "mispricing", "impliedVolatility",
        "delta", "theta", "vega", "openInterest", "volume",
        "daysToExpiry", "expiryBucket",
        "RSI", "UpperBB", "LowerBB", "Close", # Keep core indicators
        "EMA_Signal", "MACD_Hist", # New indicators
        "bb_norm", "rsi_norm", "trend_pass", "missing_signal", # Calculated metrics
        # "nearFib", # Only include if calculated and needed
        "score"
    ]
    existing_columns = [c for c in columns if c in df.columns]
    df_final = df.reindex(columns=existing_columns).reset_index(drop=True)

    return df_final
