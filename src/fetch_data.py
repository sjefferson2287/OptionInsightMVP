import yfinance as yf
import pandas as pd

def get_stock_data(symbol: str, days: int = 30) -> pd.DataFrame:
    try:
        df = yf.download(symbol, period=f"{days}d", interval="1d")
        return df
    except Exception as e:
        print(f"Error fetching stock data for {symbol}: {e}")
        return pd.DataFrame()

def get_option_chain(symbol: str, expiration: str) -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        opt = ticker.option_chain(expiration)
        calls = opt.calls.copy()
        puts = opt.puts.copy()
        calls['type'] = 'call'
        puts['type'] = 'put'
        df = pd.concat([calls, puts], ignore_index=True)
        df['expiration'] = expiration
        return df
    except Exception as e:
        print(f"Error fetching options for {symbol} @ {expiration}: {e}")
        return pd.DataFrame()
