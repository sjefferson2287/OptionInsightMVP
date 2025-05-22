import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


def black_scholes(S, K, T, r, sigma, option_type='call'):
    """Calculates Black-Scholes option price."""
    try:
        # Handle invalid inputs that cause math errors / warnings
        if pd.isna(T) or pd.isna(sigma) or pd.isna(S) or pd.isna(K):
             return np.nan
        if T < 0 or sigma <= 0 or S <= 0 or K <= 0:
             return np.nan
        if np.isclose(T, 0): T = 1e-6 # Assign a very small T to avoid division by zero

        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type == 'call':
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        elif option_type == 'put':
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        else:
            log.warning(f"Unknown option type '{option_type}' in black_scholes.")
            return np.nan

        return max(0, price)

    except Exception as e:
        log.error(f"Error in black_scholes: S={S}, K={K}, T={T}, r={r}, sigma={sigma}, type={option_type}, Error: {e}")
        return np.nan

def calculate_theoretical_prices(df: pd.DataFrame, stock_close: float, config: dict = None, hist_vol: float = None) -> pd.DataFrame:
    """
    Calculates theoretical option prices using Black-Scholes.
    """
    log.debug("Inside calculate_theoretical_prices...")

    if df.empty:
        log.debug("Input DataFrame is empty.")
        return df

    try:
        df_calc = df.copy()
        log.debug("Calculating T...")
        today_dt = datetime.today().date()
        df_calc['expiration_dt'] = pd.to_datetime(df_calc['expiration'], errors='coerce')

        if df_calc['expiration_dt'].isnull().any():
            log.warning("Found invalid or missing expiration dates.")

        days_to_expiry = (df_calc['expiration_dt'] - pd.Timestamp(today_dt)).dt.days
        df_calc['T'] = np.where(days_to_expiry <= 0, np.nan, days_to_expiry / 365.0)
        log.debug(f"Calculated T. Min: {df_calc['T'].min():.4f}, Max: {df_calc['T'].max():.4f}, NaNs: {df_calc['T'].isna().sum()}")

    except Exception as e:
        log.error(f"Error calculating time to expiry (T): {e}. Returning original df.")
        return df.copy()

    sigma = 0.5
    if hist_vol is not None:
        try:
            sigma = float(hist_vol)
            if sigma <= 0:
                log.warning(f"Historical volatility ({hist_vol}) is not positive. Using fallback 0.5.")
                sigma = 0.5
        except (ValueError, TypeError):
            log.warning(f"Could not convert hist_vol ({hist_vol}) to float. Using fallback 0.5.")
            sigma = 0.5
    log.debug(f"Using sigma: {sigma:.4f}")

    log.debug("Applying Black-Scholes...")
    r = config.get('risk_free_rate', 0.03) if config else 0.03

    required_cols = ['strike', 'T', 'type']
    if not all(col in df_calc.columns for col in required_cols):
        log.error("Missing required columns ('strike', 'T', 'type') for Black-Scholes calculation.")
        return df.copy()
    else:
        theoretical_prices = df_calc.apply(
            lambda row: black_scholes(
                S=stock_close,
                K=row['strike'],
                T=row['T'],
                r=r,
                sigma=sigma,
                option_type=str(row['type']).lower()
            ),
            axis=1
        )
        df_calc['theoretical_price'] = theoretical_prices
        log.debug(f"Applied Black-Scholes. Theoretical price NaNs: {df_calc['theoretical_price'].isna().sum()}")

    log.debug("Calculating mispricing...")
    if 'lastPrice' in df_calc.columns and 'theoretical_price' in df_calc.columns:
         df_calc['mispricing'] = df_calc['lastPrice'] - df_calc['theoretical_price']
         log.debug(f"Calculated mispricing. Mispricing NaNs: {df_calc['mispricing'].isna().sum()}")
    else:
         log.warning("Missing 'lastPrice' or 'theoretical_price' column, cannot calculate mispricing.")
         df_calc['mispricing'] = np.nan

    df_calc = df_calc.drop(columns=['expiration_dt'], errors='ignore')
    log.debug("Finished calculate_theoretical_prices.")

    return df_calc
