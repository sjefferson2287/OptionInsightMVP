import pandas as pd

def generate_report(symbol, df, indicators, filters):
    if df.empty or indicators.empty:
        return pd.DataFrame()

    latest_rsi = indicators['RSI'].dropna().iloc[-1]
    upper_band = indicators['UpperBB'].dropna().iloc[-1]
    lower_band = indicators['LowerBB'].dropna().iloc[-1]
    latest_close = indicators['Close'].dropna().iloc[-1]

    # Apply filters
    df = df[
        (df['impliedVolatility'] >= filters.get("min_iv", 0.2)) &
        (df['delta'].abs() >= filters.get("min_delta", 0.3)) &
        (df['theta'] <= filters.get("max_theta", -0.1))
    ].copy()

    # Score system
    df['score'] = 0
    df.loc[df['delta'].abs() >= 0.5, 'score'] += 1
    df.loc[df['theta'] > -0.15, 'score'] += 1
    df.loc[df['mispricing'].abs() >= 1.0, 'score'] += 1
    df.loc[df['impliedVolatility'] >= 0.4, 'score'] += 1

    # Add context
    df['ticker'] = symbol
    df['RSI'] = latest_rsi
    df['Close'] = latest_close
    df['UpperBB'] = upper_band
    df['LowerBB'] = lower_band

    return df[[
        'ticker', 'contractSymbol', 'strike', 'type', 'expiration', 'lastPrice',
        'theoretical_price', 'mispricing', 'impliedVolatility',
        'delta', 'theta', 'vega', 'RSI', 'Close', 'UpperBB', 'LowerBB', 'score'
    ]]
