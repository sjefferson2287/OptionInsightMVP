import os
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from decouple import config
from polygon.rest import RESTClient

POLYGON_KEY = config("POLYGON_API_KEY", default="") # Get key, default to empty string if not found
BASE_URL = "https://api.polygon.io"

def get_stock_data(symbol: str, days: int = 30) -> pd.DataFrame:
    if not POLYGON_KEY:
        print("Error: POLYGON_API_KEY is not set. Please configure it in your .env file or environment variables.")
        return pd.DataFrame()

    try:
        # Calculate from and to dates
        to_date = date.today()
        from_date = to_date - timedelta(days=days)
        from_date_str = from_date.strftime("%Y-%m-%d")
        to_date_str = to_date.strftime("%Y-%m-%d")

        client = RESTClient(POLYGON_KEY) # Initialize client outside 'with' block
        # Corrected method name from stocks_equities_aggregates to get_aggs
        aggs = client.get_aggs(symbol, 1, "day", from_date_str, to_date_str)


        # Check for empty response
        if not aggs: # Changed from resp.results to aggs (directly a list)
            print(f"No results found for {symbol} from {from_date_str} to {to_date_str}")
            return pd.DataFrame()
        
        df = pd.DataFrame(aggs) # df will have columns: open, high, low, close, volume, vwap, timestamp, transactions, otc

        # Convert timestamp to datetime and set as 'Date'
        df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Select and rename columns to the desired format
        df = df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
        
        # Keep only the required columns
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        
        df = df.set_index('Date')
        return df

    except Exception as e:
        print(f"Error fetching stock data for {symbol}: {e}")
        return pd.DataFrame()


def get_option_chain(
    symbol: str,
    expiration: str = None,
    max_days_to_expiry: int = None
) -> pd.DataFrame:
    if not POLYGON_KEY: # Check if the API key is set
        print("Error: POLYGON_API_KEY is not set. Please configure it in your .env file or environment variables.")
        return pd.DataFrame() # Return empty DataFrame if key is missing

    base_url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
    all_results = []
    url = base_url

    # Paginate, always sending apiKey & limit
    while url:
        resp = requests.get(url, params={"apiKey": POLYGON_KEY, "limit": 250})
        resp.raise_for_status()
        data = resp.json()
        all_results.extend(data.get("results", []))
        url = data.get("next_url")

    rows = []
    today = date.today()

    for o in all_results:
        details = o.get("details", {}) or {}
        day     = o.get("day", {}) or {}
        greeks  = o.get("greeks", {}) or {}

        exp_str = details.get("expiration_date")
        if not exp_str:
            continue

        # Compute days to expiry
        exp_dt = datetime.strptime(exp_str, "%Y-%m-%d").date()
        days_to_expiry = (exp_dt - today).days

        # 1) Horizon filter
        if max_days_to_expiry is not None and days_to_expiry > max_days_to_expiry:
            continue

        # 2) Volume filter: skip zero‐volume
        volume = day.get("volume", 0) or 0
        if volume < 1:
            continue

        # 3) Open interest
        oi = o.get("open_interest", 0)

        # 4) lastPrice with bid/ask fallback
        last_price = day.get("close")
        if last_price is None:
            quote = o.get("last_quote", {}) or {}
            bid, ask = quote.get("bid"), quote.get("ask")
            if bid is not None and ask is not None:
                last_price = (bid + ask) / 2

        # 5) Expiry bucket tagging
        if days_to_expiry <= 7:
            bucket = "0-7"
        elif days_to_expiry <= 30:
            bucket = "8-30"
        elif days_to_expiry <= 60:
            bucket = "31-60"
        else:
            bucket = "60+"

        row = {
            "ticker":         symbol,
            "contractSymbol": details.get("ticker"),
            "strike":         details.get("strike_price"),
            "expiration":     exp_str,
            "daysToExpiry":   days_to_expiry,
            "expiryBucket":   bucket,
            "type":           details.get("contract_type"),
            "lastPrice":      last_price,
            "volume":         volume,
            "impliedVolatility": o.get("implied_volatility"),
            "delta":          greeks.get("delta"),
            "gamma":          greeks.get("gamma"),
            "theta":          greeks.get("theta"),
            "vega":           greeks.get("vega"),
            "openInterest":   oi,
        }

        # 6) Exact-date filter
        if expiration is None or exp_str == expiration:
            rows.append(row)

    return pd.DataFrame(rows)

def get_intraday_data(symbol: str, multiplier: int = 1, timespan: str = "minute", from_date: str = None, to_date: str = None) -> pd.DataFrame:
    """
    Fetch intraday data for a given symbol from Polygon.
    """
    if not POLYGON_KEY: # Check if the API key is set
        print("Error: POLYGON_API_KEY is not set. Please configure it in your .env file or environment variables.")
        return pd.DataFrame() # Return empty DataFrame if key is missing


    if not from_date or not to_date:
        raise ValueError("Both 'from_date' and 'to_date' must be provided for intraday data.")

    url = f"{BASE_URL}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
    params = {
        "apiKey": POLYGON_KEY
    }
    response = requests.get(url, params=params)
    response.raise_for_status()  # Raise an error for bad responses
    data = response.json()

    if "results" in data:
        # Convert results to a DataFrame
        df = pd.DataFrame(data["results"])
        # Convert timestamps to readable datetime
        df["t"] = pd.to_datetime(df["t"], unit="ms")
        df.rename(columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}, inplace=True)
        return df
    else:
        print(f"No intraday data found for {symbol}: {data}")
        return pd.DataFrame()

# Example usage
if __name__ == "__main__":
    symbol = "AAPL"
    from_date = "2025-04-01"
    to_date = "2025-04-21"
    intraday_data = get_intraday_data(symbol, multiplier=1, timespan="minute", from_date=from_date, to_date=to_date)
    print(intraday_data.head())
