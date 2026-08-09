#!/usr/bin/env python3
"""
Cognitive Dark — Find the IG Link (V2.9.3).

Jab ig_diagnose kehti hai "page par IG linked nahi" lekin aapko lagta hai
linkage hai — yeh script aapke token ke UNDER SAARE Facebook pages ko list
karta hai aur HAR page par instagram_business_account check karta hai.

Isse 2 cheezein clear hoti hain:
  1. Aapke kitne pages hain aur kaunsa page IG se linked hai.
  2. Sahi IG business account ID kya hai (jo secrets mein daalni hai).

Koi token print nahi hota (sirf masked). READ-ONLY.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import requests

GRAPH = "https://graph.facebook.com"
V = "v25.0"


def first_env(*names):
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return ""


def mask(tok):
    if not tok:
        return "(missing)"
    return f"{tok[:6]}...{tok[-4:]}"


def get(url, params):
    try:
        r = requests.get(url, params=params, timeout=30)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"raw": r.text[:300]}
    except Exception as exc:
        return 0, {"error": str(exc)}


def main():
    fb_tok = first_env("FB_ACCESS_TOKEN", "FACEBOOK_ACCESS_TOKEN", "IG_ACCESS_TOKEN",
                       "INSTAGRAM_ACCESS_TOKEN")
    if not fb_tok:
        print("❌ FB_ACCESS_TOKEN / FACEBOOK_ACCESS_TOKEN nahi mila.")
        return 1

    print("=" * 72)
    print("🔎 FIND THE IG LINK — saare pages scan")
    print("=" * 72)
    print(f"Token: {mask(fb_tok)}\n")

    # 1) All pages under this token
    code, d = get(f"{GRAPH}/{V}/me/accounts",
                  {"access_token": fb_tok, "fields": "id,name,category",
                   "limit": 100})
    if code != 200:
        err = d.get("error", {})
        print(f"❌ /me/accounts failed: {err.get('message', d)}")
        return 1
    pages = d.get("data", [])
    if not pages:
        print("❌ Token ke under koi page nahi mila.")
        print("   (token page-token hai? /me/accounts sirf user-token se chalta hai)")
        return 1

    print(f"✅ {len(pages)} page(s) token ke under mile:\n")
    found = []
    for p in pages:
        pid = p["id"]
        pcode, pd = get(f"{GRAPH}/{V}/{pid}",
                        {"access_token": fb_tok,
                         "fields": "id,name,instagram_business_account,category"})
        ig_linked = (pd.get("instagram_business_account") or {}).get("id") if pcode == 200 else None
        ig_name = (pd.get("instagram_business_account") or {}).get("username", "") if pcode == 200 else ""
        status = f"✅ IG LINKED → id={ig_linked} (@{ig_name})" if ig_linked else "❌ koi IG linked nahi"
        print(f"  Page {pid}")
        print(f"    name     : {pd.get('name') if pcode == 200 else '?'}  (category: {pd.get('category') if pcode == 200 else '?'})")
        print(f"    IG link  : {status}")
        print()
        if ig_linked:
            found.append({"page_id": pid, "page_name": pd.get("name"),
                          "ig_id": ig_linked, "ig_username": ig_name})

    print("=" * 72)
    if found:
        print("✅ ✅ LINKED PAGES MILIYE — ye values GitHub secrets mein honi chahiyein:")
        for f in found:
            print(f"\n  FACEBOOK_PAGE_ID={f['page_id']}     # {f['page_name']}")
            print(f"  INSTAGRAM_USER_ID={f['ig_id']}        # @{f['ig_username']}")
            print(f"  FACEBOOK_ACCESS_TOKEN=<yahan token>   # jo abhi use ho raha hai")
            print(f"  INSTAGRAM_ACCESS_TOKEN=<wahi token>")
    else:
        print("❌ KISI bhi page par Instagram linked NAHI mila.")
        print("   Asal linking abhi karni hai: Instagram app → Settings →")
        print("   Account type and tools → Linked accounts → Facebook Page")
    print("=" * 72)
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
