# src/schwab_api.py

import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()  # ← load SCHWAB_CLIENT_ID & SECRET from .env

# Correct production endpoints
_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
_PREFS_URL = "https://api.schwab.com/public/user/v1/preferences"

def get_access_token(client_id: str = None, client_secret: str = None) -> str:
    client_id     = client_id     or os.getenv("SCHWAB_CLIENT_ID")
    client_secret = client_secret or os.getenv("SCHWAB_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EnvironmentError("Missing SCHWAB_CLIENT_ID or SCHWAB_CLIENT_SECRET")
    resp = requests.post(
        _TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=HTTPBasicAuth(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def get_streamer_info(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(_PREFS_URL, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    acct     = data["streamerInfo"]["accounts"][0]
    streamer = data["streamerInfo"]
    return {
        "customer_id": acct["schwabClientCustomerId"],
        "corr_id":     acct["schwabClientCorrelId"],
        "host":        streamer["streamerHost"],
        "port":        streamer["streamerPort"],
    }

if __name__ == "__main__":
    token = get_access_token()
    print("Access Token:", token[:8] + "…")
    info = get_streamer_info(token)
    print("Streamer Info:", info)
