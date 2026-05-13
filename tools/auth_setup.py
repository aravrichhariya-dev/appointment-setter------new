"""
One-time OAuth setup. Run this ONCE on your local machine (not the server).

    python tools/auth_setup.py

It will open a browser window asking you to authorise access to Google Calendar.
After you approve, token.json is saved in the project root.

Then copy both files to the server:
    scp credentials.json token.json root@<YOUR_DROPLET_IP>:<YOUR_PROJECT_PATH>/
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(_HERE, "credentials.json")
TOKEN_FILE = os.path.join(_HERE, "token.json")


def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: credentials.json not found at {CREDENTIALS_FILE}")
        print("Download it from Google Cloud Console → APIs & Services → Credentials → your OAuth client → Download JSON")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    droplet_ip = os.getenv("DROPLET_IP", "<YOUR_DROPLET_IP>")
    project_path = os.getenv("PROJECT_PATH", "<YOUR_PROJECT_PATH>")
    print(f"\nDone! token.json saved to: {TOKEN_FILE}")
    print("\nNext: copy both files to the server:")
    print(f"  scp credentials.json token.json root@{droplet_ip}:{project_path}/")


if __name__ == "__main__":
    main()
