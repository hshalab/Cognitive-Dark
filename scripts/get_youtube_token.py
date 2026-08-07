#!/usr/bin/env python3
"""
Cognitive Dark — YouTube OAuth Refresh-Token Generator.

Use this when pointing the pipeline at a NEW channel/account: the OAuth
*client* (id/secret) stays the same, but the REFRESH_TOKEN must be re-granted
while signed into the Google account / brand channel that owns the target
YouTube channel.

Steps:
  1. python scripts/get_youtube_token.py   (uses GOOGLE_CLIENT_ID/SECRET from
     .env or env; or pass via --client-id/--client-secret)
  2. Open the printed URL WHILE SIGNED IN as the target channel's account.
  3. Approve → you'll land on a localhost:8080 page (or an error page whose
     URL contains ?code=... — copy that whole URL and paste it back here).
  4. The script prints your new REFRESH_TOKEN → put it in the GitHub secret.

No dependencies beyond the Python standard library.
"""

import argparse
import http.server
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

SCOPES = ("https://www.googleapis.com/auth/youtube.upload "
          "https://www.googleapis.com/auth/youtube.readonly")
REDIRECT = "http://localhost:8080/"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", default=os.environ.get("GOOGLE_CLIENT_ID", ""))
    ap.add_argument("--client-secret", default=os.environ.get("GOOGLE_CLIENT_SECRET", ""))
    args = ap.parse_args()
    if not args.client_id or not args.client_secret:
        sys.exit("❌ Set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET (env or .env)")

    auth_url = ("https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": args.client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",          # ← this is what yields a refresh token
        "prompt": "consent",               # force re-consent so refresh token returns
    }))

    print("═" * 64)
    print("1) Sign in as the GOOGLE ACCOUNT of the TARGET channel.")
    print("2) Open this URL and approve:\n")
    print(auth_url)
    print("\n3) Waiting for the redirect on localhost:8080 ...")
    print("   (If the page fails to load, copy the ADDRESS-BAR URL that")
    print("    contains ?code=... and paste it below instead.)")
    print("═" * 64)

    code_holder = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(q.query)
            if "code" in qs:
                code_holder["code"] = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h2>Done! Return to the terminal.</h2>")
            else:
                self.send_response(400)
                self.end_headers()
        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 8080), H)
    srv.timeout = 300
    srv.handle_request()
    code = code_holder.get("code")

    if not code:
        url = input("Paste the redirect URL (with ?code=...): ").strip()
        m = re.search(r"[?&]code=([^&]+)", url)
        if not m:
            sys.exit("❌ No code found in that URL")
        code = m.group(1)

    body = urllib.parse.urlencode({
        "client_id": args.client_id,
        "client_secret": args.client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT,
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        tok = json.loads(resp.read())

    print("\n🔑 NEW REFRESH TOKEN:")
    print(tok.get("refresh_token", "❌ not returned — re-run with prompt=consent"))
    print("\n→ GitHub repo → Settings → Secrets → REFRESH_TOKEN mein paste karein.")


if __name__ == "__main__":
    main()
