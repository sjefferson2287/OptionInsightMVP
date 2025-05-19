import os
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from decouple import config
from polygon import RESTClient

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
        # Use list_aggs instead of stocks_equities_aggregates
        aggs = client.list_aggs(
            ticker=symbol,
            multiplier=1,
            timespan="day",
            from_=from_date_str,
            to=to_date_str,
            limit=50000 # Max limit
        )

        # Convert iterator to list
        results = list(aggs)

        # Check for empty response
        if not results:
            print(f"No results found for {symbol} from {from_date_str} to {to_date_str}")
            return pd.DataFrame()

        df = pd.DataFrame(results)
        # Ensure 't' (timestamp) is present before converting
        if 't' not in df.columns and 'timestamp' not in df.columns:
             # The new client might name the timestamp column differently or it might be nested.
             # For now, let's assume 'timestamp' is the direct column name if 't' is not present.
             # If 'timestamp' is also not present, we might need to inspect 'results' more closely.
             # This part may need adjustment based on the actual structure of `aggs` items.
             # Based on Polygon docs, 't' is the official field for timestamp in aggregates.
             # However, the objects returned by list_aggs might have attributes like `open`, `high`, `low`, `close`, `volume`, `vwap`, `timestamp`, `transactions`, `otc`.
             # Let's assume the objects have attributes that match the old 'o', 'h', 'l', 'c', 'v' structure or can be mapped.
             # The new client's objects likely have direct attributes like .open, .high, etc.
             # So, we might need to construct the DataFrame differently.

             # Re-checking the example: `for a in client.list_aggs(...): aggs.append(a)`. `a` is an object.
             # The DataFrame constructor should ideally handle a list of these objects.
             # Let's assume the column names are 'open', 'high', 'low', 'close', 'volume', 'timestamp' directly from the objects.
             # If `t` is not in `df.columns` after `pd.DataFrame(results)`, it means the objects from `list_aggs`
             # might not have a 't' attribute directly, but rather a 'timestamp' attribute.
             # The previous code used 't' from `resp.results`. The new client might provide objects with attributes.
             # Let's assume the DataFrame columns will be named after the attributes of the agg objects.
             # The `polygon-api-client` `Agg` object has attributes: open, high, low, close, volume, vwap, timestamp, transactions, otc.
             # So, 'timestamp' should be the correct column name for the ms timestamp.
             if 'timestamp' not in df.columns:
                 print(f"Timestamp column ('t' or 'timestamp') not found in results for {symbol}")
                 return pd.DataFrame() # Or handle error appropriately
        
        # If 't' exists (from old client structure, though unlikely now) convert it
        if 't' in df.columns:
            df['timestamp_col'] = pd.to_datetime(df['t'], unit='ms')
        elif 'timestamp' in df.columns: # This is expected with the new client
            df['timestamp_col'] = pd.to_datetime(df['timestamp'], unit='ms')
        else:
            # This case should ideally be caught by the check above.
            print(f"Critical: Neither 't' nor 'timestamp' found after initial check for {symbol}")
            return pd.DataFrame()

        df = df.rename(columns={
            'open': 'Open',      # Assuming new client uses 'open'
            'high': 'High',      # Assuming new client uses 'high'
            'low': 'Low',        # Assuming new client uses 'low'
            'close': 'Close',    # Assuming new client uses 'close'
            'volume': 'Volume',  # Assuming new client uses 'volume'
            'timestamp_col': 'Date' # Renaming the converted timestamp column to 'Date'
        })
        # Drop original timestamp column if it wasn't 'timestamp_col' (e.g. if 't' or 'timestamp' was used for conversion)
        if 't' in df.columns and 't' != 'Date':
            df = df.drop(columns=['t'])
        if 'timestamp' in df.columns and 'timestamp' != 'Date':
            df = df.drop(columns=['timestamp'])

        df = df.set_index('Date')
        # Select only the required columns, in case list_aggs returned more (like vwap, transactions etc.)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]

    except Exception as e:
            'h': 'High',
            'l': 'Low',
            'c': 'Close',
            'v': 'Volume',
            'timestamp': 'Date'
        })
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
