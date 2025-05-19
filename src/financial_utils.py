import pandas as pd
import numpy as np
import logging

log = logging.getLogger(__name__)

def calculate_historical_volatility(stock_data: pd.DataFrame, window: int = 20) -> float | None:
    """
    Calculates historical volatility using log returns.

    Args:
        stock_data: DataFrame with a 'Close' column.
        window: Rolling window size for calculation.

    Returns:
        Annualized historical volatility (float) or None if calculation fails.
    """
    log.debug(f"Calculating historical volatility with window: {window}")
    if stock_data is None or not isinstance(stock_data, pd.DataFrame) or 'Close' not in stock_data:
        log.warning("Invalid stock_data input for volatility calculation.")
        return None

    if len(stock_data) < window:
        log.warning(f"Not enough data ({len(stock_data)} points) for window size {window} in volatility calculation.")
        return None

    # Calculate log returns
    log_returns = np.log(stock_data['Close'] / stock_data['Close'].shift(1))

    # Calculate rolling standard deviation of log returns
    rolling_std_dev = log_returns.rolling(window=window).std()

    if rolling_std_dev.empty or rolling_std_dev.iloc[-1] == np.nan:
        log.warning("Could not calculate rolling standard deviation or result is NaN.")
        return None
    
    # Annualize the volatility (assuming 252 trading days in a year)
    # Take the most recent rolling standard deviation
    annualized_volatility = rolling_std_dev.iloc[-1] * np.sqrt(252)

    if np.isnan(annualized_volatility):
        log.warning("Resulting annualized volatility is NaN.")
        return None
        
    log.info(f"Calculated annualized volatility: {annualized_volatility:.4f}")
    return annualized_volatility
