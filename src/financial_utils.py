import pandas as pd
import numpy as np
import logging

log = logging.getLogger(__name__)

def calculate_historical_volatility(close_prices_series: pd.Series, window: int = 20, trading_days_per_year: int = 252) -> float:
    """
    Calculates annualized historical volatility from a series of close prices.
    Args:
        close_prices_series: Pandas Series of close prices.
        window: Rolling window period for standard deviation.
        trading_days_per_year: Number of trading days in a year for annualization.
    Returns:
        Annualized historical volatility (float), or np.nan if calculation fails.
    """
    if not isinstance(close_prices_series, pd.Series):
        log.error("Input 'close_prices_series' must be a Pandas Series.")
        return np.nan
    
    cleaned_series = close_prices_series.dropna()
    # We need 'window' points for rolling calculation AFTER log returns (which itself needs 1 prior point)
    # So, we need cleaned_series to have at least window + 1 points.
    if len(cleaned_series) < window + 1:
        log.warning(f"Not enough data points ({len(cleaned_series)}) to calculate {window}-period rolling volatility after log returns. Need at least {window + 1}.")
        return np.nan

    # Calculate log returns. The first value will be NaN.
    log_returns = np.log(cleaned_series / cleaned_series.shift(1))
    
    # Rolling std dev of log returns.
    # The first 'window-1' values of rolling_std_dev will be NaN after the initial NaN from log_returns.
    # So, we need at least 'window' log_return values for the first non-NaN std.
    # This means we need 'window'+1 original price points.
    rolling_std_dev = log_returns.rolling(window=window).std()

    if rolling_std_dev.empty: # Should not happen if len(cleaned_series) >= window + 1
        log.warning("Rolling standard deviation series is empty.")
        return np.nan

    last_std = rolling_std_dev.iloc[-1] # Get the last valid rolling standard deviation

    if pd.isna(last_std):
        log.warning(f"Could not calculate {window}-period rolling standard deviation (result was NaN). This might be due to insufficient data points ({len(cleaned_series)}) for the window after processing log returns.")
        return np.nan
    
    historical_volatility = last_std * np.sqrt(trading_days_per_year)
    return historical_volatility
