import numpy as np
import pandas as pd
from scipy.stats import norm

def compute_greeks(df: pd.DataFrame, S: float, config: dict = None, sigma=None) -> pd.DataFrame:
    if df.empty or 'T' not in df.columns:
        return df

    df = df.copy()

    # Get risk-free rate from config or default
    r = config.get('risk_free_rate', 0.03) if config else 0.03

    # Ensure sigma is a float or fallback
    try:
        sigma = float(sigma)
    except Exception:
        sigma = df['impliedVolatility'].mean() if 'impliedVolatility' in df.columns else 0.5

    # Filter out invalid rows
    df = df[df['T'].notnull() & (df['T'] > 0)].copy()
    if df.empty or sigma <= 0:
        return df

    # Compute d1 and d2
    df['d1'] = df.apply(lambda row:
        (np.log(S / row['strike']) + (r + 0.5 * sigma**2) * row['T']) / (sigma * np.sqrt(row['T'])),
        axis=1
    )
    df['d2'] = df['d1'] - sigma * np.sqrt(df['T'])

    # Delta
    df['delta'] = df.apply(
        lambda row: norm.cdf(row['d1']) if row['type'].lower() == 'call' else -norm.cdf(-row['d1']),
        axis=1
    )

    # Gamma
    df['gamma'] = df.apply(
        lambda row: norm.pdf(row['d1']) / (S * sigma * np.sqrt(row['T'])),
        axis=1
    )

    # Theta
    def theta_row(row):
        pdf = norm.pdf(row['d1'])
        common = -S * pdf * sigma / (2 * np.sqrt(row['T']))
        if row['type'].lower() == 'call':
            return common - r * row['strike'] * np.exp(-r * row['T']) * norm.cdf(row['d2'])
        else:
            return common + r * row['strike'] * np.exp(-r * row['T']) * norm.cdf(-row['d2'])

    df['theta'] = df.apply(theta_row, axis=1)

    # Vega
    df['vega'] = df.apply(
        lambda row: S * norm.pdf(row['d1']) * np.sqrt(row['T']) * 0.01,
        axis=1
    )

    return df.drop(columns=['d1', 'd2'])
