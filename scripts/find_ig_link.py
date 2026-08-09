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
    print("🔎 FIND THE IG LINK")
    print("=" * 72)
    print(f"Token: {mask(fb_tok)}\n")

    found = []

    # 1) Try /me/accounts first (user token → lists ALL pages)
    code, d = get(f"{GRAPH}/{V}/me/accounts",
                  {"access_token": fb_tok, "fields": "id,name,category", "limit": 100})
    if code == 200:
        pages = d.get("data", [])
        print(f"✅ User-token style: {len(pages)} page(s) under this token:\n")
        for p in pages:
            pid = p["id"]
            pcode, pd = get(f"{GRAPH}/{V}/{pid}",
                            {"access_token": fb_tok,
                             "fields": "id,name,instagram_business_account,category"})
            ig = (pd.get("instagram_business_account") or {}) if pcode == 200 else {}
            ig_linked = ig.get("id")
            ig_name = ig.get("username", "")
            status = (f"✅ IG LINKED → id={ig_linked} (@{ig_name})"
                      if ig_linked else "❌ koi IG linked nahi")
            print(f"  Page {pid} — {pd.get('name') if pcode == 200 else '?'}  {status}")
            if ig_linked:
                found.append({"page_id": pid, "page_name": pd.get("name"),
                              "ig_id": ig_linked, "ig_username": ig_name})
    else:
        # 2) Page token → /me returns the page itself. Check IT directly.
        print("ℹ️ /me/accounts user-token style nahi chala (shayad page token hai).")
        print("   Page token se /me = wohi page. Check kar rahe hain:\n")
        code2, me = get(f"{GRAPH}/{V}/me",
                        {"access_token": fb_tok,
                         "fields": "id,name,instagram_business_account,category"})
        if code2 == 200:
            ig = me.get("instagram_business_account") or {}
            ig_linked = ig.get("id")
            ig_name = ig.get("username", "")
            print(f"  Page {me.get('id')} — {me.get('name')}  "
                  f"(category: {me.get('category', '?')})")
            if ig_linked:
                print(f"  ✅ IG LINKED → id={ig_linked} (@{ig_name})")
                found.append({"page_id": me.get("id"), "page_name": me.get("name"),
                              "ig_id": ig_linked, "ig_username": ig_name})
            else:
                print("  ❌ is page par koi Instagram account linked NAHI.")
                print("     (agar aapko linkage dikhti hai to token ki permission")
                print("     ya doosre page ka masla ho sakta hai — FACEBOOK_APP_ID/SECRET")
                print("     secrets mein daalne se token scopes bhi check ho sakte hain)")
        else:
            err = me.get("error", {})
            print(f"  ❌ /me failed: {err.get('message', me)}")

    print("=" * 72)
    if found:
        print("✅ LINKED PAGE MIL GAYI — ye values GitHub secrets mein daalo:")
        for f in found:
            print(f"\n  FACEBOOK_PAGE_ID={f['page_id']}     # {f['page_name']}")
            print(f"  INSTAGRAM_USER_ID={f['ig_id']}        # @{f['ig_username']}")
            print(f"  FACEBOOK_ACCESS_TOKEN=<jo token abhi hai>")
            print(f"  INSTAGRAM_ACCESS_TOKEN=<wahi token>")
    else:
        print("❌ Kisi bhi page par Instagram linked NAHI mila (API ke hisaab se).")
        print("   Options:")
        print("   1. Linking ke baad 10-15 min intezar karo — Meta delay karta hai.")
        print("   2. Instagram app → Settings → Account type and tools →")
        print("      Linked accounts → Facebook → 'Coercion Files' page select karo.")
        print("   3. FACEBOOK_APP_ID + FACEBOOK_APP_SECRET secrets mein daalo")
        print("      taake token scopes inspect ho saken.")
    print("=" * 72)
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
