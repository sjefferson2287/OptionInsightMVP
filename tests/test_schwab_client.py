import pytest
import pandas as pd
import requests
import requests_mock
from unittest.mock import patch
from decouple import config as decouple_config # For mocking config values if needed

# Module to test
from src import schwab_client 

# Mock SCHWAB_ACCESS_TOKEN etc. if they are accessed at module level,
# though schwab_client.py seems to load them inside functions or at header definition.
# For HEADERS, we might need to patch schwab_client.HEADERS if they are defined at import time
# and we want to ensure our mock token is used.
# However, since decouple loads from .env, direct patching of os.getenv or config might be better.

@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("SCHWAB_ACCESS_TOKEN", "mock_access_token")
    monkeypatch.setenv("SCHWAB_CLIENT_CORREL_ID", "mock_correl_id")
    # schwab_client.HEADERS will be re-evaluated if we reload the module or if it's defined in a way that re-reads config
    # For simplicity, assume decouple.config inside schwab_client.py picks these up.


@pytest.fixture
def mock_schwab_headers():
    return {
        "Authorization": "Bearer mock_access_token",
        "Schwab-Client-CorrelId": "mock_correl_id",
        "Schwab-Resource-Version": "1"
    }

def test_get_price_history_success(requests_mock, mock_env_vars, mock_schwab_headers):
    symbol = "AAPL"
    start_ts = 1700000000000
    end_ts = 1700000086400
    mock_response = {
        "candles": [
            {"open": 150.0, "high": 152.0, "low": 149.0, "close": 151.0, "volume": 1000, "datetime": 1700000000000},
            {"open": 151.0, "high": 153.0, "low": 150.0, "close": 152.0, "volume": 1200, "datetime": 1700000086400}
        ],
        "symbol": symbol,
        "empty": False
    }
    expected_url = f"{schwab_client.BASE}/pricehistory"
    requests_mock.get(expected_url, json=mock_response, status_code=200, request_headers=mock_schwab_headers)
    
    df = schwab_client.get_price_history(symbol, start_ts, end_ts)
    assert not df.empty
    assert len(df) == 2
    assert df.iloc[0]['open'] == 150.0
    assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume', 'datetime']

def test_get_price_history_empty(requests_mock, mock_env_vars, mock_schwab_headers):
    symbol = "AAPL"
    start_ts = 1700000000000
    end_ts = 1700000086400
    mock_response = {"candles": [], "symbol": symbol, "empty": True}
    expected_url = f"{schwab_client.BASE}/pricehistory"
    requests_mock.get(expected_url, json=mock_response, status_code=200, request_headers=mock_schwab_headers)

    df = schwab_client.get_price_history(symbol, start_ts, end_ts)
    assert df.empty
    # Check if it returns the predefined columns for an empty DataFrame
    assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume', 'datetime']


def test_get_price_history_error(requests_mock, mock_env_vars, mock_schwab_headers):
    symbol = "AAPL"
    start_ts = 1700000000000
    end_ts = 1700000086400
    expected_url = f"{schwab_client.BASE}/pricehistory"
    requests_mock.get(expected_url, status_code=500, request_headers=mock_schwab_headers)

    with pytest.raises(requests.exceptions.HTTPError):
        schwab_client.get_price_history(symbol, start_ts, end_ts)

def test_get_option_chain_success(requests_mock, mock_env_vars, mock_schwab_headers):
    symbol = "AAPL"
    mock_response = {
        "symbol": "AAPL",
        "status": "SUCCESS",
        "callExpDateMap": {
            "2025-01-17:23": { # Expiration Date:DaysToExpiration
                "150.0": [ # Strike Price
                    {"putCall": "CALL", "symbol": "AAPL C Jan 17 2025 150", "strikePrice": 150.0, "expirationDate": 1737081600000, "last": 10.0, "vol": 100}
                ]
            }
        },
        "putExpDateMap": {
            "2025-01-17:23": {
                "140.0": [
                    {"putCall": "PUT", "symbol": "AAPL P Jan 17 2025 140", "strikePrice": 140.0, "expirationDate": 1737081600000, "last": 5.0, "vol": 50}
                ]
            }
        }
    }
    expected_url = f"{schwab_client.BASE}/chains"
    requests_mock.get(expected_url, json=mock_response, status_code=200, request_headers=mock_schwab_headers)

    df = schwab_client.get_option_chain(symbol)
    assert not df.empty
    assert len(df) == 2
    assert df[df['putCall'] == 'CALL'].iloc[0]['last'] == 10.0
    assert df[df['putCall'] == 'PUT'].iloc[0]['last'] == 5.0
    assert 'expirationDate' in df.columns
    assert 'strikePrice' in df.columns


def test_get_option_chain_empty_map(requests_mock, mock_env_vars, mock_schwab_headers):
    symbol = "AAPL"
    mock_response = {
        "symbol": "AAPL",
        "status": "SUCCESS",
        "callExpDateMap": {}, # Empty map
        "putExpDateMap": {}   # Empty map
    }
    expected_url = f"{schwab_client.BASE}/chains"
    requests_mock.get(expected_url, json=mock_response, status_code=200, request_headers=mock_schwab_headers)
    
    df = schwab_client.get_option_chain(symbol)
    assert df.empty
    # Check for predefined columns for an empty DataFrame
    expected_cols = ['symbol', 'description', 'strikePrice', 'expirationDate', 'putCall', 'bid', 'ask', 'last', 'volume', 'openInterest']
    assert all(col in df.columns for col in expected_cols)


def test_get_option_chain_malformed_data(requests_mock, mock_env_vars, mock_schwab_headers):
    symbol = "AAPL"
    # Example of malformed: callExpDateMap is not a dict
    mock_response = {"symbol": "AAPL", "status": "SUCCESS", "callExpDateMap": "not_a_dict", "putExpDateMap": {}}
    expected_url = f"{schwab_client.BASE}/chains"
    requests_mock.get(expected_url, json=mock_response, status_code=200, request_headers=mock_schwab_headers)

    df = schwab_client.get_option_chain(symbol)
    assert df.empty # Should return empty df due to malformed part

    # Example: strikes is not a dict
    mock_response_strikes_not_dict = {
        "symbol": "AAPL", "status": "SUCCESS", 
        "callExpDateMap": {"2025-01-17:23": "not_a_dict_of_strikes"}, 
        "putExpDateMap": {}
    }
    requests_mock.get(expected_url, json=mock_response_strikes_not_dict, status_code=200, request_headers=mock_schwab_headers, overwrite_response=True)
    df_strikes = schwab_client.get_option_chain(symbol)
    assert df_strikes.empty


def test_get_option_chain_error(requests_mock, mock_env_vars, mock_schwab_headers):
    symbol = "AAPL"
    expected_url = f"{schwab_client.BASE}/chains"
    requests_mock.get(expected_url, status_code=401, request_headers=mock_schwab_headers) # Unauthorized

    with pytest.raises(requests.exceptions.HTTPError):
        schwab_client.get_option_chain(symbol)

# It might be necessary to explicitly reload schwab_client or patch its HEADERS 
# if decouple.config() is only called once at module import time.
# For these tests, we assume that each call to a schwab_client function
# that uses HEADERS will effectively use the mocked environment variables
# because decouple.config() is called at the top of schwab_client.py to define HEADERS.
# If HEADERS were defined inside each function, it would be more robust to mocking.
# A more direct way to ensure headers are mocked is to patch 'schwab_client.HEADERS' itself.

@patch('src.schwab_client.HEADERS', {
    "Authorization": "Bearer mock_access_token_patched",
    "Schwab-Client-CorrelId": "mock_correl_id_patched",
    "Schwab-Resource-Version": "1"
})
def test_get_price_history_with_patched_headers(requests_mock, mock_env_vars): # mock_env_vars still useful if config() used elsewhere
    symbol = "AAPL"
    start_ts = 1700000000000
    end_ts = 1700000086400
    mock_response = {
        "candles": [{"open": 150.0, "high": 152.0, "low": 149.0, "close": 151.0, "volume": 1000, "datetime": 1700000000000}],
        "symbol": symbol, "empty": False
    }
    # The request_headers in requests_mock.get should match the patched HEADERS
    requests_mock.get(f"{schwab_client.BASE}/pricehistory", json=mock_response, status_code=200, 
                      request_headers={
                          "Authorization": "Bearer mock_access_token_patched",
                          "Schwab-Client-CorrelId": "mock_correl_id_patched",
                          "Schwab-Resource-Version": "1"
                      })
    
    df = schwab_client.get_price_history(symbol, start_ts, end_ts)
    assert not df.empty
    assert df.iloc[0]['open'] == 150.0
