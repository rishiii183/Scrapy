import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

TOKEN_PATH = r"C:\Users\rishi\.gemini\antigravity\plugin_data\gsheets\token.json"
SPREADSHEET_ID = "12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY"

def get_access_token():
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Check expiry
    expiry_str = data["token"].get("expiry")
    access_token = data["token"]["access_token"]
    refresh_token = data["token"]["refresh_token"]
    client_id = data["client_id"]
    client_secret = data["client_secret"]
    
    # Try using existing access token
    headers = {"Authorization": f"Bearer {access_token}"}
    test_url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}?fields=properties.title"
    req = urllib.request.Request(test_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            info = json.loads(resp.read().decode("utf-8"))
            print(f"Token active. Spreadsheet title: {info.get('properties', {}).get('title')}")
            return access_token
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("Token expired. Refreshing token via Google OAuth endpoint...")
            token_url = "https://oauth2.googleapis.com/token"
            body = urllib.parse.urlencode({
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }).encode("utf-8")
            refresh_req = urllib.request.Request(token_url, data=body, method="POST")
            with urllib.request.urlopen(refresh_req) as ref_resp:
                ref_data = json.loads(ref_resp.read().decode("utf-8"))
                new_token = ref_data["access_token"]
                print("Token successfully refreshed!")
                return new_token
        else:
            raise

if __name__ == "__main__":
    token = get_access_token()
    print("Google Sheets Access verification complete.")
