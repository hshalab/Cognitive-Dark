#!/usr/bin/env python3
"""
Cognitive Dark — Meta (Facebook + Instagram) LONG-LIVED Token Generator.

The pipeline was failing with 'session invalidated' / 'cannot parse token'
because short-lived or stale tokens were being pasted. This script does the
FULL proper flow and prints LONG-LIVED tokens you can paste into GitHub
secrets (they last 60+ days):

  1. Facebook Login (localhost redirect) → short user token
  2. exchange → LONG-LIVED user token
  3. /me/accounts → LONG-LIVED PAGE token  (use for FB AND IG uploads)
  4. page → instagram_business_account id  (IG target)

Outputs exactly what to paste:
  FB_PAGE_ID=...
  FACEBOOK_ACCESS_TOKEN=<page token>
  IG_BUSINESS_ACCOUNT_ID=...
  IG_ACCESS_TOKEN=<same page token>

Setup (one time):
  • Meta App: developers.facebook.com → My Apps → Create App (Business type)
  • App → Settings → Basic → copy App ID + App Secret
  • App → Facebook Login → Settings → Valid OAuth Redirect URIs →
    add:  http://localhost:8081/
  • Add your FB account as Admin of the app AND admin of the Page;
    the Page must be linked to an Instagram Business/Creator account.

Run:  python scripts/get_meta_tokens.py --app-id ID --app-secret SECRET
"""

import argparse
import http.server
import json
import sys
import urllib.parse
import urllib.request

REDIRECT = "http://localhost:8081/"
SCOPE = ("pages_show_list,pages_read_engagement,pages_manage_posts,"
         "pages_manage_videos,instagram_basic,instagram_content_publish")
V = "v25.0"


def get(url: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{qs}", timeout=60) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--app-secret", required=True)
    a = ap.parse_args()

    auth = ("https://www.facebook.com/" + V + "/dialog/oauth?" +
            urllib.parse.urlencode({
                "client_id": a.app_id, "redirect_uri": REDIRECT,
                "scope": SCOPE, "response_type": "code"}))
    print("═" * 66)
    print("1) Browser mein login ho kar ye URL kholein aur approve karein:")
    print(auth)
    print("\n2) localhost:8081 par redirect ka intezar hai...")
    print("═" * 66)

    holder = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q:
                holder["code"] = q["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h2>Done! Terminal par wapas jayen.</h2>")
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, *x):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 8081), H)
    srv.timeout = 600
    srv.handle_request()
    if "code" not in holder:
        sys.exit("❌ Code nahi mila")

    short = get(f"https://graph.facebook.com/{V}/oauth/access_token",
                {"client_id": a.app_id, "client_secret": a.app_secret,
                 "redirect_uri": REDIRECT, "code": holder["code"]})["access_token"]

    long_user = get(f"https://graph.facebook.com/{V}/oauth/access_token",
                    {"grant_type": "fb_exchange_token", "client_id": a.app_id,
                     "client_secret": a.app_secret,
                     "fb_exchange_token": short})["access_token"]

    pages = get(f"https://graph.facebook.com/{V}/me/accounts",
                {"access_token": long_user}).get("data", [])
    if not pages:
        sys.exit("❌ Koi Page nahi mila — is account ka koi FB Page nahi hai")
    print("\nMile pages:")
    for p in pages:
        print(f"   • {p['name']}  ({p['id']})")
    pick = pages[0]
    if len(pages) > 1:
        name = input("Kaun sa Page use karna hai? (naam likhein): ").strip()
        for p in pages:
            if name.lower() in p["name"].lower():
                pick = p

    page_id, page_token = pick["id"], pick["access_token"]

    ig_id = ""
    try:
        ig = get(f"https://graph.facebook.com/{V}/{page_id}",
                 {"fields": "instagram_business_account",
                  "access_token": page_token})
        ig_id = ig.get("instagram_business_account", {}).get("id", "")
    except Exception as e:
        print("⚠️ IG account link nahi mila:", e)

    print("\n" + "═" * 66)
    print("🔑 GITHUB SECRETS MEIN YE DAALEIN (long-lived):")
    print("═" * 66)
    print(f"FB_PAGE_ID={page_id}")
    print(f"FACEBOOK_ACCESS_TOKEN={page_token}")
    print(f"IG_BUSINESS_ACCOUNT_ID={ig_id or '❌ (Page se IG link karein)'}")
    print(f"IG_ACCESS_TOKEN={page_token}")
    print("\n✅ Page token 60+ din chalta hai; FB aur IG dono isi se upload honge.")


if __name__ == "__main__":
    main()
