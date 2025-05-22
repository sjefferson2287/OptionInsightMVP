# src/streamer.py
import json
import ssl
import uuid
import websocket
import time # Added for timestamp generation
from decouple import config

# URL removed, will be constructed dynamically
CERT_FILE = config("SCHWAB_CERT_FILE", default="cert.pem")
KEY_FILE = config("SCHWAB_KEY_FILE", default="key.pem")

class SchwabStreamer:
    def __init__(self, streamer_info: dict):
        self.streamer_info = streamer_info
        self.customer_id = self.streamer_info['clientCustomerId']
        self.correl_id = self.streamer_info['clientCorrelId']
        self.session_token = self.streamer_info['sessionToken'] # This is the token for WebSocket auth

        try:
            with open(CERT_FILE, 'r') as cf, open(KEY_FILE, 'r') as kf:
                pass
        except FileNotFoundError as e:
            print(f"Error: SSL certificate or key file not found. Paths: {CERT_FILE}, {KEY_FILE}. Details: {e}")
            raise

        # Construct the WebSocket URL
        # Replace {$userId} in streamerServiceUrl
        service_url_template = self.streamer_info['streamerServiceUrl']
        service_url = service_url_template.replace("{$userId}", self.customer_id)

        # Build the full URL with query parameters
        # Ensure all keys from streamer_info are used as per the user's example
        # The user's example uses 'sessionToken' for 'authorization' and 'accessToken' query params.
        # And 'clientCustomerId' for 'participantId', 'clientCorrelId' for 'clientCorrelId'.
        
        # Note: The problem description uses 'schwabClientCustomerId' and 'schwabClientCorrelId' for query params
        # but the JSON example from GET User Preferences uses 'clientCustomerId' and 'clientCorrelId'.
        # We will use the keys as found in the streamer_info dict.
        
        dynamic_url = (
            f"wss://{self.streamer_info['streamerSocketUrl']}:{self.streamer_info['streamerSocketPort']}"
            f"{service_url}?"
            f"authorization={self.session_token}&" # sessionToken from streamer_info
            f"participantId={self.customer_id}&"   # clientCustomerId from streamer_info
            f"accessToken={self.session_token}&"   # sessionToken from streamer_info
            f"timestamp={int(time.time()*1000)}&"
            f"clientCorrelId={self.correl_id}"      # clientCorrelId from streamer_info
        )
        print(f"Constructed WebSocket URL: {dynamic_url}") # For debugging

        ssl_opts = {"certfile": CERT_FILE, "keyfile": KEY_FILE, "cert_reqs": ssl.CERT_NONE} # Added cert_reqs per user example
        # server_hostname might be needed if SNI issues arise, e.g.
        # ssl_opts["server_hostname"] = self.streamer_info['streamerSocketUrl']

        try:
            self.ws = websocket.create_connection(dynamic_url, sslopt=ssl_opts)
        except ConnectionRefusedError as e:
            print(f"Connection to {dynamic_url} refused. Details: {e}")
            raise
        except ssl.SSLError as e:
            print(f"SSL Error during connection to {dynamic_url}. Certs: ({CERT_FILE}, {KEY_FILE}). Details: {e}")
            raise
        except websocket.WebSocketException as e:
            print(f"WebSocket connection error to {dynamic_url}. Details: {e}")
            raise
        
        # LOGIN
        # Use session_token for Authorization parameter in LOGIN command
        login_request = {
            "requests":[
                {"requestid":"1","service":"ADMIN","command":"LOGIN",
                 "SchwabClientCustomerId": self.customer_id,
                 "SchwabClientCorrelId": self.correl_id,
                 "parameters":{
                    "Authorization": self.session_token, # Use sessionToken from streamer_info
                    "SchwabClientChannel":"APIAPP",
                    "SchwabClientFunctionId":"BOT"
                }}
            ]
        }
        self.send(login_request)
        # It's good practice to wait for and check the LOGIN response
        # For simplicity here, we're assuming login succeeds.
        # A robust implementation would parse the response to confirm.

    def send(self, obj):
        try:
            self.ws.send(json.dumps(obj))
        except websocket.WebSocketConnectionClosedException as e:
            print(f"Error sending message: WebSocket connection is closed. Details: {e}")
            raise # Or handle reconnection logic
        except Exception as e:
            print(f"Error sending message via WebSocket: {e}")
            raise


    def subscribe(self, service: str, symbols: list, fields: str = "0,1,2,3"):
        if not symbols:
            print(f"Warning: No symbols provided for {service} subscription. Skipping.")
            return

        # Use instance variables for customer_id and correl_id
        subscription_request = {
            "requests": [{
                "requestid": str(uuid.uuid4()),
                "service": service.upper(),
                "command": "SUBS",
                "SchwabClientCustomerId": self.customer_id, # Use instance variable
                "SchwabClientCorrelId": self.correl_id,   # Use instance variable
                "parameters": {"keys": ",".join(symbols), "fields": fields}
            }]
        }
        self.send(subscription_request)
        print(f"Sent subscription request for {service} with symbols: {symbols} and fields: {fields}")


    def run(self, on_message_callback):
        try:
            while True:
                raw_message = self.ws.recv()
                if not raw_message: # Handle empty message, might indicate connection issue
                    print("Received empty message from WebSocket, possible connection issue.")
                    # Consider attempting to reconnect or break
                    time.sleep(1) # Avoid tight loop on empty messages
                    continue
                
                message = json.loads(raw_message)
                
                # Handle different types of messages (responses, data, heartbeats)
                if "response" in message: # Handle responses to requests (LOGIN, SUBS)
                    print(f"Received response: {message['response']}")
                    # You might want to check status of LOGIN/SUBS here
                elif "data" in message:
                    on_message_callback(message["data"])
                elif "notify" in message: # Handle notifications like heartbeats
                    # print(f"Received notification: {message['notify']}")
                    pass # Usually heartbeats, can be ignored or logged
                else:
                    print(f"Received unhandled message type: {message}")

        except websocket.WebSocketConnectionClosedException:
            print("WebSocket connection closed.")
            # Implement reconnection logic if desired
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from WebSocket: {raw_message}. Error: {e}")
        except KeyboardInterrupt:
            print("Streamer interrupted by user. Closing connection.")
        except Exception as e:
            print(f"An error occurred in the streamer run loop: {e}")
        finally:
            if self.ws and self.ws.connected:
                self.ws.close()
            print("SchwabStreamer stopped.")
            
    def close(self):
        if self.ws and self.ws.connected:
            print("Closing WebSocket connection.")
            self.ws.close()

if __name__ == '__main__':
    # Example Usage (requires SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET, etc. in .env)
    # And cert.pem, key.pem in the current directory or paths configured in .env
    # This example usage will need to be updated to reflect how streamer_info is obtained.
    # For now, it's commented out as it would require a full auth flow to run standalone.
    
    # from dotenv import load_dotenv
    # from src.auth_http import run_auth_flow # Hypothetical, auth flow needs to return token
    # from src.schwab_client import get_user_preferences # To get streamer_info

    # load_dotenv()

    # def my_message_handler(data_messages):
    #     for message_item in data_messages:
    #         print(f"Received Data: {message_item}")

    # if __name__ == '__main__':
    #     # This is a simplified placeholder. A real run would involve:
    #     # 1. Running the OAuth flow to get an access_token.
    #     # 2. Calling get_user_preferences(access_token) to get streamer_info.
    #     # 3. Passing streamer_info to SchwabStreamer.
        
    #     # Placeholder for streamer_info - replace with actual fetched data
    #     # This example will not run correctly without a valid streamer_info dict.
    #     mock_streamer_info = {
    #         "streamerSocketUrl": "streamer.example.com",
    #         "streamerSocketPort": 443,
    #         "streamerServiceUrl": "/v1/{$userId}",
    #         "sessionToken": "example_session_token",
    #         "clientCorrelId": "example_correl_id",
    #         "clientCustomerId": "example_customer_id",
    #         # "tokenExpiration": "...", # Not directly used by streamer class but part of prefs
    #     }
        
    #     # Check if essential OAuth credentials are set for a more complete test
    #     if not config("SCHWAB_CLIENT_ID") or not config("SCHWAB_CLIENT_SECRET"):
    #         print("SCHWAB_CLIENT_ID or SCHWAB_CLIENT_SECRET not found in .env. Full example requires OAuth.")
    #     else:
    #         try:
    #             print("Attempting to start SchwabStreamer example with mock data...")
    #             # In a real scenario, you'd fetch streamer_info here
    #             # For example:
    #             # access_token_dict = run_auth_flow_and_get_token() # Needs modification to return token
    #             # access_token = access_token_dict['access_token']
    #             # actual_streamer_info = get_user_preferences(access_token)
    #             # streamer = SchwabStreamer(actual_streamer_info)
                
    #             streamer = SchwabStreamer(mock_streamer_info) # Using mock for now
                
    #             streamer.subscribe("LEVELONE_EQUITIES", ["AAPL", "MSFT"])
    #             print("Streamer started with mock data. Waiting for messages... (Ctrl+C to stop)")
    #             streamer.run(my_message_handler)
    #         except FileNotFoundError:
    #             print("Ensure cert.pem and key.pem are present, or configure paths in .env.")
    #         except ValueError as ve:
    #             print(f"Initialization or data error: {ve}")
    #         except Exception as e:
    #             print(f"An unexpected error occurred: {e}")
    pass # Added to satisfy linter when the main block is commented out
