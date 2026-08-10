#!/usr/bin/env python3
"""
Coercion Files — 3-Platform Settings Audit (runs in CI where secrets live).

Reports what each platform currently has + what still needs doing:
  • YouTube : channel identity, subs/views, verification (custom thumbs /
              long uploads), uploads state
  • Facebook: page identity, followers, category, IG link, monetization hints
  • Instagram: account type, followers, media, bio presence
"""

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.ERROR)


def yt_creds():
    raw = os.environ.get("YOUTUBE_CREDENTIALS", "")
    cid, csec, rt = (os.environ.get(k) for k in
                     ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "REFRESH_TOKEN"))
    if cid and csec and rt:
        return {"client_id": cid, "client_secret": csec, "refresh_token": rt,
                "token_uri": "https://oauth2.googleapis.com/token",
                "type": "authorized_user"}
    if raw and os.path.exists(raw):
        return json.load(open(raw, encoding="utf-8"))
    try:
        return json.loads(raw)
    except Exception:
        return None


def main():
    print("═" * 66)
    print("🔍 3-PLATFORM SETTINGS AUDIT")
    print("═" * 66)

    # ── YOUTUBE ──
    print("\n▶ YOUTUBE")
    info = yt_creds()
    if not info:
        print("  ❌ no credentials")
    else:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            creds = Credentials.from_authorized_user_info(info)
            if (creds.expired or not creds.valid) and creds.refresh_token:
                creds.refresh(Request())
            yt = build("youtube", "v3", credentials=creds)
            ch = yt.channels().list(part="snippet,statistics,status,brandingSettings",
                                    mine=True).execute()["items"][0]
            sn, st, stats = ch["snippet"], ch["status"], ch["statistics"]
            br = ch.get("brandingSettings", {}).get("channel", {})
            print(f"  title      : {sn['title']}")
            print(f"  handle     : {sn.get('customUrl', '❌ NOT SET')}")
            print(f"  country    : {sn.get('country', '❌ NOT SET')}")
            print(f"  subs/views : {stats.get('subscriberCount', 0)} / {stats.get('viewCount', 0)}")
            print(f"  linked     : {st.get('isLinked')}")
            print(f"  longUploads: {st.get('longUploadsStatus')}  "
                  f"({'✅ verified' if st.get('longUploadsStatus') == 'allowed' else '⚠️ phone-verify for intermediate features'})")
            print(f"  keywords   : {'✅ set' if br.get('keywords') else '❌ MISSING'}")
            print(f"  description: {'✅ set' if br.get('description') else '❌ MISSING'}")
            print(f"  tracking   : {br.get('trackingAnalyticsAccountId', 'n/a')}")
        except Exception as e:
            print("  ❌", str(e)[:200])

    # ── FACEBOOK ──
    print("\n▶ FACEBOOK")
    import requests
    tok = os.environ.get("FB_ACCESS_TOKEN", "")
    page = os.environ.get("FB_PAGE_ID", "")
    if not tok or not page:
        print("  ❌ no credentials")
    else:
        try:
            r = requests.get(f"https://graph.facebook.com/v25.0/{page}",
                             params={"access_token": tok,
                                     "fields": "name,username,category,about,fan_count,"
                                               "followers_count,link,is_published,"
                                               "instagram_business_account"},
                             timeout=30)
            r.raise_for_status()
            d = r.json()
            print(f"  page       : {d.get('name')} (@{d.get('username', '❌ no username')})")
            print(f"  category   : {d.get('category', '❌ NOT SET')}")
            print(f"  followers  : {d.get('followers_count', d.get('fan_count', 0))}")
            print(f"  about      : {'✅' if d.get('about') else '❌ MISSING'}")
            print(f"  published  : {d.get('is_published')}")
            igb = d.get("instagram_business_account", {}).get("id")
            print(f"  IG linked  : {'✅ ' + igb if igb else '❌ NOT LINKED'}")

            # V2.6: scan ALL pages of this account — IG may be linked to a
            # DIFFERENT page than the one in secrets
            print("\n  ── all pages of this account ──")
            r2 = requests.get("https://graph.facebook.com/v25.0/me/accounts",
                              params={"access_token": tok,
                                      "fields": "name,id,instagram_business_account,"
                                                "followers_count"},
                              timeout=30)
            for p in r2.json().get("data", []):
                igp = p.get("instagram_business_account", {}).get("id")
                print(f"   • {p['name']} ({p['id']}) followers="
                      f"{p.get('followers_count', '?')} IG={'✅ ' + igp if igp else '—'}")
        except Exception as e:
            print("  ❌", str(e)[:200])

    # ── INSTAGRAM ──
    print("\n▶ INSTAGRAM")
    ig = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
    itok = os.environ.get("IG_ACCESS_TOKEN", "") or tok
    if not ig or not itok:
        print("  ❌ no credentials")
    else:
        try:
            r = requests.get(f"https://graph.facebook.com/v25.0/{ig}",
                             params={"access_token": itok,
                                     "fields": "username,name,biography,account_type,"
                                               "followers_count,media_count,category"},
                             timeout=30)
            r.raise_for_status()
            d = r.json()
            print(f"  account    : {d.get('name')} (@{d.get('username')})")
            print(f"  type       : {d.get('account_type')}  "
                  f"({'✅' if d.get('account_type') in ('BUSINESS', 'MEDIA_CREATOR') else '❌ must be Business/Creator'})")
            print(f"  followers  : {d.get('followers_count', 0)}  media: {d.get('media_count', 0)}")
            print(f"  bio        : {'✅' if d.get('biography') else '❌ MISSING'}")
            print(f"  category   : {d.get('category', '❌ NOT SET')}")
        except Exception as e:
            print("  ❌", str(e)[:200])

    print("\n" + "═" * 66)


if __name__ == "__main__":
    main()
