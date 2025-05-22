# src/schwab_client.py
import pandas as pd
import requests
from decouple import config
import json # Added for json.JSONDecodeError

BASE = "https://api.schwabapi.com/marketdata/v1"
HEADERS = {
    "Authorization": f"Bearer {config('SCHWAB_ACCESS_TOKEN', default='')}",
    "Schwab-Client-CorrelId": config("SCHWAB_CLIENT_CORREL_ID", default=''),
    "Schwab-Resource-Version": "1"
}

def get_price_history(symbol: str, start: int, end: int, frequency: str = "daily") -> pd.DataFrame:
    """
    Fetches OHLCV history via Schwab /pricehistory.
    start/end are UNIX-ms timestamps.
    frequency: 'minute'|'daily' etc.
    """
    params = {
        "symbol": symbol,
        "periodType": "day", # This might need to be dynamic based on start/end range for minute data
        "frequencyType": frequency,
        "frequency": 1,
        "startDate": start,
        "endDate": end
    }
    r = requests.get(f"{BASE}/pricehistory", headers=HEADERS, params=params)
    r.raise_for_status()
    data = r.json()
    # It's good practice to check if 'candles' key exists and is not empty
    candles = data.get("candles", [])
    if not candles:
        # Return an empty DataFrame with expected columns if no data
        # This helps prevent errors downstream if the DataFrame is expected to have certain columns
        # Adjust columns based on actual expected output or leave as is if flexible
        return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'datetime']) 
    return pd.DataFrame(candles)

def get_option_chain(
    symbol: str,
    contractType: str = "ALL",
    strikeCount: int = 50,
    strategy: str = "SINGLE"
) -> pd.DataFrame:
    """
    Fetches option chain via Schwab /chains.
    Flattens callExpDateMap & putExpDateMap into a single DataFrame.
    """
    params = {
        "symbol": symbol,
        "contractType": contractType,
        "strikeCount": strikeCount,
        "strategy": strategy
    }
    r = requests.get(f"{BASE}/chains", headers=HEADERS, params=params)
    r.raise_for_status()
    data = r.json()
    records = []
    # Check if data itself is None or not a dict, or if 'callExpDateMap'/'putExpDateMap' are missing
    if not isinstance(data, dict):
        return pd.DataFrame() # Or raise an error

    for side in ("callExpDateMap", "putExpDateMap"):
        exp_date_map = data.get(side)
        if not isinstance(exp_date_map, dict):
            continue # Skip if the side (call/put map) is not a dictionary or is missing
        for exp, strikes in exp_date_map.items():
            if not isinstance(strikes, dict):
                continue # Skip if strikes for an expiration is not a dictionary
            for strike_px, opts in strikes.items():
                # The spec shows opts.values() but opts is a list of option objects directly in Schwab's example
                # Assuming opts is a list of dicts as per Schwab's /chains example response structure
                if isinstance(opts, list): # Check if opts is a list
                    for opt_details in opts:
                        if isinstance(opt_details, dict): # Ensure each item in list is a dict
                             records.append({**opt_details, "expirationDate": exp, "strikePrice": float(strike_px)})
                # Original spec had opts.values() which implies opts is a dict of dicts.
                # If Schwab API returns strike_px as a key to a list of contracts (opts):
                # Example: "200.0": [ {contract1_details}, {contract2_details} ]
                # The above code handles this.
                # If Schwab API returns strike_px as a key to a dict of contracts (opts):
                # Example: "200.0": { "O:XYZ...": {contract1_details}, "O:ABC...": {contract2_details} }
                # Then the original spec's opts.values() would be correct.
                # Based on Schwab's sample, it's a list of contracts.
    
    if not records:
        # Define columns based on expected fields from Schwab API if records is empty
        # This ensures consistency in DataFrame structure
        # Example columns, adjust as per actual API response fields
        return pd.DataFrame(columns=['symbol', 'description', 'strikePrice', 'expirationDate', 'putCall', 'bid', 'ask', 'last', 'volume', 'openInterest'])
    return pd.DataFrame(records)

def get_user_preferences(access_token: str) -> dict:
    """
    Fetches user preferences, including streamer connection details.
    The access_token is the OAuth token obtained from the /token endpoint.
    Returns a dictionary containing the 'streamerInfo' object.
    """
    # As per Schwab documentation, the User Preferences endpoint is typically:
    # https://api.schwabapi.com/trader/v1/userPreference
    # However, the user's example JSON implies the keys are directly within streamerInfo.
    # Let's assume the endpoint returns a structure containing the "streamerInfo" object.
    preferences_url = "https://api.schwabapi.com/trader/v1/userPreference"
    
    headers = {
        "Authorization": f"Bearer {access_token}"
        # Per Schwab docs, GET /userPreference usually only needs Authorization.
        # Other headers like Schwab-Client-CorrelId are not typically required for this call.
    }
    
    try:
        response = requests.get(preferences_url, headers=headers)
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        preferences_data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user preferences: {e}")
        raise  # Re-raise the exception to be handled by the caller
    except json.JSONDecodeError as e: # More specific than requests.exceptions.JSONDecodeError if requests < 2.27
        print(f"Error decoding JSON from user preferences response: {e}")
        raise

    streamer_info = preferences_data.get("streamerInfo")
    
    # Validate streamer_info structure based on the user's example JSON
    if not streamer_info or not isinstance(streamer_info, dict):
        # Some Schwab documentation might show streamerInfo as a list.
        # If so, and it's a list, one might take the first element:
        # if isinstance(streamer_info, list) and streamer_info:
        #     streamer_info = streamer_info[0]
        # else:
        #     raise ValueError("streamerInfo not found, not a dictionary, or (if a list) is empty in user preferences.")
        raise ValueError("streamerInfo not found or is not a dictionary in user preferences response.")

    # Keys expected within the streamer_info dictionary, based on user's problem description
    expected_keys = [
        "streamerSocketUrl", "streamerSocketPort", "streamerServiceUrl",
        "sessionToken",        # For WebSocket URL query param and LOGIN command's Authorization
        "clientCorrelId",      # For WebSocket URL query param and LOGIN command
        "clientCustomerId"     # For WebSocket URL query param (as participantId), LOGIN command, and {$userId} replacement
    ]
    for key in expected_keys:
        if key not in streamer_info:
            raise ValueError(f"Missing required key '{key}' in streamerInfo from user preferences.")
            
    return streamer_info
