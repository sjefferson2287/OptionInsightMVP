import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("POLYGON_API_KEY")
BASE_URL = "https://api.polygon.io"

def get_option_chain_snapshot(symbol):
    url = f"{BASE_URL}/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if "results" in data:
        return data["results"]
    else:
        print("Error in API response:", data)
        return []

def get_btc_price():
    url = f"{BASE_URL}/v2/aggs/ticker/X:BTCUSD/prev?adjusted=true&apiKey={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if "results" in data and len(data["results"]) > 0:
        return data["results"][0]["c"]  # Close price
    else:
        print("Error getting BTC price:", data)
        return None
