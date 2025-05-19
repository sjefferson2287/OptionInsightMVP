# src/auth_http.py

import os
import ssl
import threading
import webbrowser
import urllib.parse as urlparse
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from requests_oauthlib import OAuth2Session

# ——— CONFIGURATION ———
load_dotenv()  # ensure SCHWAB_CLIENT_ID & SCHWAB_CLIENT_SECRET are in your .env

CLIENT_ID     = os.getenv("SCHWAB_CLIENT_ID")
CLIENT_SECRET = os.getenv("SCHWAB_CLIENT_SECRET")
REDIRECT_URI  = "https://127.0.0.1:8000/callback"

# Use the exact Schwab URLs:
AUTH_URL  = "https://api.schwab.com/oauth/v1/authorize"
TOKEN_URL = "https://api.schwab.com/v1/oauth/token"

# global to capture the authorization code
auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code

        # log every incoming request path
        print("Received request path:", self.path)

        parsed = urlparse.urlparse(self.path)

        # Root ping (curl test)
        if parsed.path == "/":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Server is up on port 8000")
            return

        # OAuth callback
        if parsed.path == "/callback":
            params = urlparse.parse_qs(parsed.query)
            auth_code = params.get("code", [None])[0]
            print("Parsed auth_code =", auth_code)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authorization Received!</h1>"
                b"You can close this window.</body></html>"
            )

            # shut down the server cleanly
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        else:
            # respond 404 so browser doesn’t hang indefinitely
            self.send_response(404)
            self.end_headers()

def run_auth_flow():
    global auth_code

    # 1) Build OAuth2 session and get the authorization URL
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
    authorization_url, _ = oauth.authorization_url(AUTH_URL)

    # 2) Start an HTTP server on localhost:8000
    httpd = HTTPServer(("127.0.0.1", 8000), CallbackHandler)
    print("Starting HTTP server on http://127.0.0.1:8000")  # Debug: Confirm server start
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    # 3) Open the Schwab login/consent page
    print("Opening browser for Schwab OAuth ...")
    print("Authorization URL:", authorization_url)  # Debug: Print the URL
    webbrowser.open(authorization_url, new=1)

    # 4) Wait until the callback writes auth_code
    while auth_code is None:
        time.sleep(0.1)

    # 5) Exchange the code for tokens
    try:
        token = oauth.fetch_token(
            TOKEN_URL,
            code=auth_code,
            auth=(CLIENT_ID, CLIENT_SECRET),
            include_client_id=False
        )
    except Exception as e:
        print("Error fetching token:", e)
        return

    # Print the tokens
    print("Access token:", token.get("access_token"))
    print("Refresh token:", token.get("refresh_token"))

if __name__ == "__main__":
    run_auth_flow()
