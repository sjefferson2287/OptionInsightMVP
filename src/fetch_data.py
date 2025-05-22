import os
import re
import math
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from decouple import config
import src.schwab_client as schwab

# For Polygon-specific functions that are not yet data-source aware
POLYGON_API_KEY_GLOBAL = config("POLYGON_API_KEY", default="")
POLYGON_BASE_URL_GLOBAL = "https://api.polygon.io"

def get_stock_data(symbol: str, days: int = 30) -> pd.DataFrame:
    data_source = config("data_source", default="polygon")

    if data_source == "schwab":
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        end_ms = int(end_dt.timestamp() * 1000)
        start_ms = int(start_dt.timestamp() * 1000)
        df = schwab.get_price_history(symbol, start_ms, end_ms, frequency="daily")
        if not df.empty and 'datetime' in df.columns:
            df['Date'] = pd.to_datetime(df['datetime'], unit='ms', errors='coerce').dt.date
            df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
            # Ensure all expected columns are present, filling with NaN if necessary
            expected_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = pd.NA # Or float('nan')
            df = df[['Date'] + expected_cols].set_index('Date')
        return df
    elif data_source == "polygon":
        local_polygon_key = config("POLYGON_API_KEY", default="") 
        if not local_polygon_key:
            print("Error: POLYGON_API_KEY is not set for Polygon data source.")
            return pd.DataFrame()
        try:
            from polygon.rest import RESTClient 
            to_date = date.today()
            from_date = to_date - timedelta(days=days)
            client = RESTClient(local_polygon_key)
            aggs = client.get_aggs(symbol, 1, "day", from_date.strftime("%Y-%m-%d"), to_date.strftime("%Y-%m-%d"))
            if not aggs:
                print(f"No results found for {symbol} from {from_date} to {to_date} using Polygon")
                return pd.DataFrame()
            df = pd.DataFrame(aggs)
            df['Date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
            df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].set_index('Date')
            return df
        except Exception as e:
            print(f"Error fetching Polygon stock data for {symbol}: {e}")
            return pd.DataFrame()
    else:
        print(f"Error: Unknown data_source configured: {data_source}")
        return pd.DataFrame()

def get_option_chain(
    symbol: str,
    expiration: str = None, 
    max_days_to_expiry: int = None
) -> pd.DataFrame:
    data_source = config("data_source", default="polygon")
    today_date = date.today()

    if data_source == "schwab":
        df = schwab.get_option_chain(symbol) 
        if not df.empty:
            if 'expirationDate' in df.columns:
                df['expirationDate'] = pd.to_datetime(df['expirationDate'], unit='ms', errors='coerce').dt.strftime('%Y-%m-%d')
            
            if 'expirationDate' in df.columns:
                 df['daysToExpiry'] = (pd.to_datetime(df['expirationDate']).dt.date - today_date).dt.days
            else:
                 df['daysToExpiry'] = pd.NA


            if expiration is not None and 'expirationDate' in df.columns:
                df = df[df['expirationDate'] == expiration]
            if max_days_to_expiry is not None and 'daysToExpiry' in df.columns:
                df = df[df['daysToExpiry'] <= max_days_to_expiry]
            
            rename_map = {
                'symbol': 'contractSymbol', 'strikePrice': 'strike',
                'expirationDate': 'expiration', 'putCall': 'type',
                'last': 'lastPrice', 'vol': 'volume',
                # Add other mappings as necessary based on schwab_client output
                # 'bid': 'bid', 'ask': 'ask', 'openInterest': 'openInterest', 'delta': 'delta', etc.
            }
            df = df.rename(columns=rename_map)
            if 'type' in df.columns:
                 df['type'] = df['type'].str.lower()
        return df
    elif data_source == "polygon":
        local_polygon_key = config("POLYGON_API_KEY", default="")
        if not local_polygon_key:
            print("Error: POLYGON_API_KEY is not set for Polygon option chain.")
            return pd.DataFrame()
        
        polygon_option_base_url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
        all_results = []
        url = polygon_option_base_url

        while url:
            try:
                resp = requests.get(url, params={"apiKey": local_polygon_key, "limit": 250})
                resp.raise_for_status()
                data = resp.json()
                all_results.extend(data.get("results", []))
                url = data.get("next_url")
            except requests.exceptions.RequestException as e:
                print(f"Error during Polygon option chain pagination: {e}")
                return pd.DataFrame() 

        rows = []
        for o in all_results:
            details = o.get("details", {}) or {}
            day_data = o.get("day", {}) or {}
            greeks  = o.get("greeks", {}) or {}
            exp_str = details.get("expiration_date")
            if not exp_str: continue

            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d").date()
            days_to_expiry_val = (exp_dt - today_date).days

            if max_days_to_expiry is not None and days_to_expiry_val > max_days_to_expiry: continue
            volume_val = day_data.get("volume", 0) or 0
            if volume_val < 1: continue

            last_price = day_data.get("close")
            if last_price is None:
                quote = o.get("last_quote", {}) or {}
                bid, ask = quote.get("bid"), quote.get("ask")
                if bid is not None and ask is not None: last_price = (bid + ask) / 2

            if days_to_expiry_val <= 7: bucket = "0-7"
            elif days_to_expiry_val <= 30: bucket = "8-30"
            elif days_to_expiry_val <= 60: bucket = "31-60"
            else: bucket = "60+"

            row = {
                "ticker": symbol, "contractSymbol": details.get("ticker"),
                "strike": details.get("strike_price"), "expiration": exp_str,
                "daysToExpiry": days_to_expiry_val, "expiryBucket": bucket,
                "type": details.get("contract_type"), "lastPrice": last_price,
                "volume": volume_val, "impliedVolatility": o.get("implied_volatility"),
                "delta": greeks.get("delta"), "gamma": greeks.get("gamma"),
                "theta": greeks.get("theta"), "vega": greeks.get("vega"),
                "openInterest": o.get("open_interest", 0),
            }
            if expiration is None or exp_str == expiration: rows.append(row)
        return pd.DataFrame(rows)
    else:
        print(f"Error: Unknown data_source configured: {data_source}")
        return pd.DataFrame()

def get_intraday_data(symbol: str, multiplier: int = 1, timespan: str = "minute", from_date: str = None, to_date: str = None) -> pd.DataFrame:
    if not POLYGON_API_KEY_GLOBAL:
        print("Error: POLYGON_API_KEY is not set for intraday data.")
        return pd.DataFrame()
    if not from_date or not to_date:
        raise ValueError("Both 'from_date' and 'to_date' must be provided for intraday data.")

    url = f"{POLYGON_BASE_URL_GLOBAL}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
    params = {"apiKey": POLYGON_API_KEY_GLOBAL}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if "results" in data:
            df = pd.DataFrame(data["results"])
            df["t"] = pd.to_datetime(df["t"], unit="ms")
            df.rename(columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}, inplace=True)
            return df
        else:
            print(f"No intraday data found for {symbol}: {data}")
            return pd.DataFrame()
    except Exception as e:
        print(f"Error fetching Polygon intraday data for {symbol}: {e}")
        return pd.DataFrame()

def get_historic_option_price(contract_symbol: str, as_of_date: date) -> float:
    if not POLYGON_API_KEY_GLOBAL:
        print("Error: POLYGON_API_KEY is not set for historic option price.")
        return math.nan

    match = re.fullmatch(r"O:([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})", contract_symbol)
    if not match:
        print(f"Error: Could not parse contract symbol: {contract_symbol}")
        return math.nan

    underlying_ticker, exp_yy, exp_mm, exp_dd, option_type_char, strike_val_str = match.groups()
    expiration_date_str = f"20{exp_yy}-{exp_mm}-{exp_dd}"
    option_type = "call" if option_type_char == "C" else "put"
    strike_price = float(strike_val_str) / 1000.0
    
    api_url = f"{POLYGON_BASE_URL_GLOBAL}/v3/historic/options/{underlying_ticker}/{expiration_date_str}/{strike_price}/{option_type}"
    as_of_date_str = as_of_date.strftime("%Y-%m-%d")
    params = {
        "apiKey": POLYGON_API_KEY_GLOBAL, "timestamp.gte": as_of_date_str, "timestamp.lte": as_of_date_str,
        "limit": 1, "sort": "timestamp", "order": "desc", "adjusted": "true"
    }
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get("results")
        if results and len(results) > 0:
            last_trade_price = results[0].get("p")
            if last_trade_price is not None: return float(last_trade_price)
            else: print(f"Price ('p') field not found for {contract_symbol} on {as_of_date_str}. Result: {results[0]}")
        return math.nan
    except requests.exceptions.HTTPError as http_err:
        if response.status_code != 404: 
            print(f"HTTP error: {http_err} for {contract_symbol} on {as_of_date_str}")
        return math.nan
    except Exception as e:
        print(f"Error fetching historic option price for {contract_symbol} on {as_of_date_str}: {e}")
        return math.nan

if __name__ == "__main__":
    data_src = config("data_source", default="polygon")
    print(f"Using data_source: {data_src}")
    
    test_symbol = "AAPL"
    if data_src == "schwab":
        print("\nTesting Schwab get_stock_data:")
        stock_df_s = get_stock_data(test_symbol, days=5)
        print(stock_df_s.head())

        print("\nTesting Schwab get_option_chain:")
        option_df_s = get_option_chain(test_symbol, max_days_to_expiry=30)
        print(option_df_s.head())
        if not option_df_s.empty:
            print(option_df_s[['contractSymbol', 'strike', 'expiration', 'type', 'lastPrice', 'volume', 'daysToExpiry']].head())

    elif data_src == "polygon":
        print("\nTesting Polygon get_stock_data:")
        stock_df_p = get_stock_data(test_symbol, days=5)
        print(stock_df_p.head())

        print("\nTesting Polygon get_option_chain:")
        option_df_p = get_option_chain(test_symbol, max_days_to_expiry=30)
        print(option_df_p.head())
        if not option_df_p.empty and 'contractSymbol' in option_df_p.columns:
            print(option_df_p[['contractSymbol', 'strike', 'expiration', 'type', 'lastPrice', 'volume', 'daysToExpiry']].head())
            sample_contract = option_df_p['contractSymbol'].iloc[0]
            print(f"\nTesting Polygon get_historic_option_price for {sample_contract}:")
            historic_price = get_historic_option_price(sample_contract, date.today() - timedelta(days=30)) # Adjust date
            print(f"Historic price: {historic_price}")
        else:
            print("Skipping get_historic_option_price test as no sample contract from option chain.")

        print("\nTesting Polygon get_intraday_data:")
        intraday_df = get_intraday_data(test_symbol, from_date=(date.today() - timedelta(days=1)).strftime("%Y-%m-%d"), to_date=(date.today() - timedelta(days=1)).strftime("%Y-%m-%d"))
        print(intraday_df.head())
