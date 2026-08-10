#!/usr/bin/env python3
"""
Coercion Files — Instagram / Facebook Graph API Diagnostic.

Yeh script aapke Instagram setup ki tafteesh karti hai aur batati hai ke
upload kyun fail ho raha hai — account type, FB page link, token scopes,
app mode, sab kuch. Token kahin print/commit nahi hota.

Env vars (koi bhi naming chalegi):
  IG_BUSINESS_ACCOUNT_ID / INSTAGRAM_USER_ID / IG_BUSINESS_ACCOUNT_ID
  IG_ACCESS_TOKEN / INSTAGRAM_ACCESS_TOKEN  (fallback: FACEBOOK_ACCESS_TOKEN)
  FB_PAGE_ID / FACEBOOK_PAGE_ID
  FB_ACCESS_TOKEN / FACEBOOK_ACCESS_TOKEN

Usage:
  python scripts/instagram_diagnose.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH = "https://graph.facebook.com"
API_VERSION = "v25.0"
OK = "✅"
BAD = "❌"
WARN = "⚠️"


def first_env(*names):
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return ""


def mask(tok):
    if not tok:
        return "(missing)"
    if len(tok) <= 12:
        return "***"
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
    ig_id = first_env("IG_BUSINESS_ACCOUNT_ID", "INSTAGRAM_USER_ID", "IG_BUSINESS_ACCOUNT_ID")
    ig_tok = first_env("IG_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN", "FB_ACCESS_TOKEN", "FACEBOOK_ACCESS_TOKEN")
    page_id = first_env("FB_PAGE_ID", "FACEBOOK_PAGE_ID")
    fb_tok = first_env("FB_ACCESS_TOKEN", "FACEBOOK_ACCESS_TOKEN")

    print("=" * 72)
    print("🔬 INSTAGRAM / FACEBOOK GRAPH API DIAGNOSTIC")
    print("=" * 72)

    # 1. Variables present?
    print("\n1. CREDENTIALS PRESENCE")
    print(f"   IG business account id : {OK if ig_id else BAD}  {ig_id or '(missing)'}")
    print(f"   IG access token        : {OK if ig_tok else BAD}  {mask(ig_tok)}")
    print(f"   FB page id             : {OK if page_id else WARN}  {page_id or '(missing)'}")
    print(f"   FB access token        : {OK if fb_tok else WARN}  {mask(fb_tok)}")

    if not ig_tok or not ig_id:
        print(f"\n{BAD} IG credentials adhoore hain. Pehle inhein env/.env mein daalein.")
        print("    Phir: INSTAGRAM_BUSINESS_ACCOUNT_ID aur INSTAGRAM_ACCESS_TOKEN")
        sys.exit(1)

    # 2. Token metadata: valid? scopes? app? expires?
    print("\n2. TOKEN INSPECTION (debug_token)")
    tok_to_inspect = ig_tok
    app_id = first_env("FACEBOOK_APP_ID", "FB_APP_ID", "META_APP_ID")
    app_secret = first_env("FACEBOOK_APP_SECRET", "FB_APP_SECRET", "META_APP_SECRET")
    if app_id and app_secret:
        code, d = get(f"{GRAPH}/debug_token", {
            "input_token": tok_to_inspect, "access_token": f"{app_id}|{app_secret}"})
        if code == 200 and "data" in d:
            data = d["data"]
            valid = data.get("is_valid")
            print(f"   token valid        : {OK if valid else BAD} {valid}")
            print(f"   app id             : {data.get('app_id')} ({data.get('application','?')})")
            print(f"   token type         : {data.get('type')}")
            scopes = data.get("scopes", []) or []
            print(f"   scopes ({len(scopes)})     : {', '.join(scopes) or '(none)'}")
            needed = {"instagram_basic", "instagram_content_publish",
                      "pages_show_list", "pages_read_engagement"}
            missing = needed - set(scopes)
            if missing:
                print(f"   {BAD} MISSING scopes  : {', '.join(sorted(missing))}")
                print("      In scopes ke bina Reels publish nahi hogi.")
            else:
                print(f"   {OK} zaroori scopes mojood hain")
            exp = data.get("expires_at", 0)
            if exp and exp != 0:
                from datetime import datetime, timezone
                print(f"   expires at         : {datetime.fromtimestamp(exp, timezone.utc).isoformat()}")
            elif data.get("type") == "PAGE":
                print("   expires at         : never (page token)")
        else:
            print(f"   {WARN} debug_token failed: {d}")
    else:
        print(f"   {WARN} FACEBOOK_APP_ID/SECRET nahi diye — token inspect skip.")
        print("      (optional: app dashboard se le kar .env mein daalein)")

    # 3. Fetch IG account fields — yahi #10 error ke kareeb hai
    print("\n3. INSTAGRAM ACCOUNT ACCESS")
    code, d = get(f"{GRAPH}/{API_VERSION}/{ig_id}", {
        "access_token": ig_tok,
        "fields": "id,username,name,profile_picture_url,biography,media_count,"
                  "followers_count,follows_count,ig_id,media_count,biography,profile_picture_url",
    })
    if code == 200 and "id" in d:
        print(f"   {OK} account accessible")
        print(f"     username      : {d.get('username')}")
        print(f"     name          : {d.get('name')}")
        print(f"     followers     : {d.get('followers_count','?')}")
        print(f"     media_count   : {d.get('media_count','?')}")
        print(f"     biography     : {d.get('biography','?')[:60]}")
    else:
        err = d.get("error", {}) if isinstance(d, dict) else {}
        print(f"   {BAD} account access FAILED (HTTP {code})")
        print(f"      message : {err.get('message','?')}")
        print(f"      code    : {err.get('code','?')} / subcode {err.get('error_subcode','?')}")
        print(f"      fbtrace : {err.get('fbtrace_id','?')}")
        if err.get("code") == 10:
            print("\n   >>> (#10) permission error. Sab se mumkin wajuhat:")
            print("       1. App LIVE nahi hai (dev mode mein publishing band)")
            print("       2. IG account Business/Creator nahi")
            print("       3. Token scopes mein instagram_content_publish nahi")
            print("       4. IG account FB page se linked nahi")

    # 4. Linked FB page check
    if page_id and fb_tok:
        print("\n4. FACEBOOK PAGE → IG LINKAGE")
        code, d = get(f"{GRAPH}/{API_VERSION}/{page_id}", {
            "access_token": fb_tok,
            "fields": "id,name,instagram_business_account,category",
        })
        if code == 200:
            print(f"   {OK} page: {d.get('name')} (category: {d.get('category','?')})")
            ig_linked = d.get("instagram_business_account", {}).get("id")
            if ig_linked:
                match = "✓ matches" if ig_linked == ig_id else "✗ DOES NOT MATCH"
                print(f"   {OK if ig_linked == ig_id else BAD} linked IG id: {ig_linked}  {match}")
            else:
                print(f"   {BAD} is page par koi Instagram account linked NAHI.")
                print("      FB Page → Settings → Linked accounts → Instagram → Connect.")
        else:
            err = d.get("error", {})
            print(f"   {BAD} page access failed: {err.get('message','?')}")
    else:
        print("\n4. FACEBOOK PAGE → IG LINKAGE (skipped — FB creds missing)")

    # 5. Content publishing capability probe (dry, koi media create nahi karta)
    print("\n5. CONTENT PUBLISH CAPABILITY")
    code, d = get(f"{GRAPH}/{API_VERSION}/{ig_id}/content_publishing_limit", {
        "access_token": ig_tok, "fields": "quota_usage,rate_limit_settings,config"})
    if code == 200:
        print(f"   {OK} content_publishing endpoint reachable — token publish kar sakta hai.")
        if "config" in d:
            print(f"     config: {d['config']}")
        if "quota_usage" in d:
            print(f"     quota used today: {d['quota_usage']}")
    else:
        err = d.get("error", {}) if isinstance(d, dict) else {}
        print(f"   {BAD} content publishing NAHI chal raha: {err.get('message','?')}")
        print(f"      code {err.get('code')} / type {err.get('type')}")

    # 6. Recent media list (public/published)
    print("\n6. RECENT INSTAGRAM MEDIA")
    code, d = get(f"{GRAPH}/{API_VERSION}/{ig_id}/media", {
        "access_token": ig_tok,
        "fields": "id,caption,media_type,timestamp,permalink,like_count,comments_count",
        "limit": 10})
    if code == 200:
        media = d.get("data", [])
        print(f"   {OK} {len(media)} recent media mile")
        for m in media[:10]:
            cap = (m.get("caption") or "")[:45].replace("\n", " ")
            likes = m.get("like_count", "?")
            print(f"     {m.get('id')}  {m.get('media_type','?'):12} "
                  f"❤ {likes:>4}  {m.get('timestamp','')[:10]}  {cap}")
    else:
        err = d.get("error", {})
        print(f"   {BAD} media list failed: {err.get('message','?')}")

    print("\n" + "=" * 72)
    print("Diagnostic complete. Upar #3 aur #5 ke errors sab se ahem hain.")
    print("=" * 72)


if __name__ == "__main__":
    main()
