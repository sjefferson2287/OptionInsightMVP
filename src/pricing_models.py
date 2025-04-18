import pandas as pd
import numpy as np
from scipy.stats import norm

def black_scholes(S, K, T, r, sigma, option_type='call'):
    try:
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if option_type == 'call':
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    except:
        return np.nan

def calculate_theoretical_prices(df, stock_close, expiration, r=0.03, hist_vol=None):
    from datetime import datetime

    if df.empty:
        return df

    today = datetime.today()
    df = df.copy()
    df['T'] = (pd.to_datetime(df['expiration']) - today).dt.days / 365

    sigma = hist_vol if hist_vol is not None else 0.5  # fallback vol

    df['theoretical_price'] = df.apply(
        lambda row: black_scholes(
            stock_close,
            row['strike'],
            row['T'],
            r,
            sigma,
            row['type']
        ),
        axis=1
    )

    df['mispricing'] = df['lastPrice'] - df['theoretical_price']
    return df
