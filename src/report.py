import pandas as pd

def generate_report(symbol: str,
                    df: pd.DataFrame,
                    indicators: pd.DataFrame,
                    filters: dict,
                    tech_filters: dict) -> pd.DataFrame:
    """
    Builds a filtered, scored report of options for `symbol`.

    Expects:
      - df already has option fields (lastPrice, Greeks, volume, etc.)
      - indicators is a DataFrame indexed by Date (and optionally Ticker)
        with columns ['RSI','UpperBB','LowerBB','Close'] for that symbol.
      - filters contains option filters.
      - tech_filters contains technical filters.
    """
    if df.empty or indicators.empty:
        return pd.DataFrame()

    # --- MODIFIED SECTION START ---
    # 1) Pull the latest indicator values and extract scalar item
    latest = indicators.iloc[-1]
    df = df.copy()
    # Use .item() to get the scalar value from the single-item Series
    try:
        if "RSI" in latest:
             df["RSI"]     = latest["RSI"].item()
        if "UpperBB" in latest:
             df["UpperBB"] = latest["UpperBB"].item()
        if "LowerBB" in latest:
             df["LowerBB"] = latest["LowerBB"].item()
        if "Close" in latest:
            df["Close"] = latest["Close"].item()
    except ValueError as e:
        print(f"Warning: Could not extract scalar item from 'latest' indicators for {symbol}. Check 'latest' variable structure. Error: {e}")
        # Assign NaN or handle error as appropriate if scalar extraction fails
        df["RSI"] = pd.NA
        df["UpperBB"] = pd.NA
        df["LowerBB"] = pd.NA
        df["Close"] = pd.NA

    # --- MODIFIED SECTION END ---


    # --- MODIFIED SECTION START ---
    # 2) Bollinger-Band Break Filters (Using tech_filters dictionary)
    if tech_filters.get("bb_break_lower"): # Use tech_filters
        tol = tech_filters.get("bb_tolerance", 0.0) # Use tech_filters
        # Ensure Close and LowerBB columns exist and are not NaN before filtering
        if "Close" in df.columns and "LowerBB" in df.columns:
             df = df.dropna(subset=["Close", "LowerBB"])
             df = df[df["Close"] <= df["LowerBB"] * (1 + tol)]
    if tech_filters.get("bb_break_upper"): # Use tech_filters
        tol = tech_filters.get("bb_tolerance", 0.0) # Use tech_filters
        # Ensure Close and UpperBB columns exist and are not NaN before filtering
        if "Close" in df.columns and "UpperBB" in df.columns:
             df = df.dropna(subset=["Close", "UpperBB"])
             df = df[df["Close"] >= df["UpperBB"] * (1 - tol)]
    # --- MODIFIED SECTION END ---


    # 3) Option-based filters (Using filters dictionary)
    # Ensure necessary columns exist before filtering
    required_option_cols = ["delta", "theta", "impliedVolatility", "openInterest"]
    if not all(col in df.columns for col in required_option_cols):
        print(f"Warning: Missing required option columns for filtering in {symbol}. Skipping option filters.")
    else:
        # Drop rows with NaN in critical filter columns if necessary
        df = df.dropna(subset=required_option_cols)
        mask = (
            (df["delta"].abs() >= filters.get("min_delta", 0.0)) &
            (df["theta"]        <= filters.get("max_theta", 0.0)) &
            (df["impliedVolatility"] >= filters.get("min_iv", 0.0)) &
            (df["openInterest"] >= filters.get("min_open_interest", 0))
        )
        df = df[mask]


    # --- MODIFIED SECTION START ---
    # 4) Scoring (Check columns exist before using them)
    score = pd.Series(0, index=df.index) # Initialize score Series

    # Option scores
    if "delta" in df.columns:
         score += (df["delta"].abs() >= filters.get("min_delta", 0.0)).astype(int)
    if "theta" in df.columns:
         score += (df["theta"] <= filters.get("max_theta", 0.0)).astype(int)
    if "impliedVolatility" in df.columns:
         score += (df["impliedVolatility"] >= filters.get("min_iv", 0.0)).astype(int)
    if "openInterest" in df.columns:
         score += (df["openInterest"] >= filters.get("min_open_interest", 0)).astype(int)

    # Optional BB score (Check required columns exist and are not NaN)
    if "Close" in df.columns and "LowerBB" in df.columns and tech_filters.get("bb_break_lower"):
         temp_df_bb = df.dropna(subset=["Close", "LowerBB"])
         bb_score = (temp_df_bb["Close"] <= temp_df_bb["LowerBB"] * (1 + tech_filters.get("bb_tolerance",0.0))).astype(int)
         score = score.add(bb_score, fill_value=0) # Add scores aligning index, fill missing with 0
    # Add similar check for bb_break_upper if you want to score that

    df["score"] = score
    # --- MODIFIED SECTION END ---


    # 5) Pick your output columns
    columns = [
        "ticker", "contractSymbol", "strike", "type", "expiration",
        "lastPrice", "theoretical_price", "mispricing", "impliedVolatility",
        "delta", "theta", "vega", "openInterest", "volume",
        "daysToExpiry", "expiryBucket", "RSI", "UpperBB", "LowerBB", "Close", "score" # Added Close here
    ]
    # Ensure only columns that actually exist in df are selected
    existing_columns = [c for c in columns if c in df.columns]
    return df[existing_columns].reset_index(drop=True)