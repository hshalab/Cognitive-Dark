#!/usr/bin/env python3
"""
Cognitive Dark — IG Publish Capability Probe (V2.9.6).

Sach sach pata lagata hai ke IG ID valid hai ya nahi — bina instagram_basic
scope ke bhi. Kaise? POST /{ig_id}/media par ek chhota sa REELS container
request bhejta hai (koi actual video nahi — sirf media_type + ek dummy
video_url). API agar:
  • "Cannot find IG User with id ..." → IG ID GALAT hai
  • video_url/link-related error        → IG ID SAHI hai, bas url validate
  • 200                                  → container ban gaya (ID perfect)
Koi media publish NAHI hota — bas probe.
"""

import os
import sys
import json
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


def main():
    ig_id = first_env("IG_BUSINESS_ACCOUNT_ID", "INSTAGRAM_USER_ID")
    tok = first_env("IG_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN", "FB_ACCESS_TOKEN",
                    "FACEBOOK_ACCESS_TOKEN")
    print("=" * 72)
    print("🎯 IG PUBLISH CAPABILITY PROBE")
    print("=" * 72)
    print(f"IG ID    : {ig_id}")
    print(f"Token    : {mask(tok)}\n")

    if not ig_id or not tok:
        print("❌ IG ID ya token missing.")
        return 1

    # 1) Try simple GET (works only with instagram_basic — informational)
    try:
        r = requests.get(f"{GRAPH}/{V}/{ig_id}",
                         params={"access_token": tok, "fields": "id,username"},
                         timeout=30)
        if r.status_code == 200:
            d = r.json()
            print(f"✅ GET /{ig_id} → id={d.get('id')} username=@{d.get('username')}")
            print("   (instagram_basic scope mila hua hai!)")
        else:
            err = r.json().get("error", {})
            print(f"ℹ️ GET /{ig_id} failed: {err.get('code')} {err.get('message', '')[:120]}")
            print("   (yeh normal hai bina instagram_basic ke — publish abhi check karte hain)")
    except Exception as exc:
        print(f"ℹ️ GET failed: {exc}")

    # 2) THE REAL PROBE — POST /{ig_id}/media (no actual media, just a container req)
    print("\n--- POST /{ig_id}/media probe (koi media publish nahi hota) ---")
    try:
        r = requests.post(f"{GRAPH}/{V}/{ig_id}/media",
                          data={"access_token": tok, "media_type": "REELS",
                                "video_url": "https://example.com/probe.mp4",
                                "caption": "probe"},
                          timeout=30)
        if r.status_code == 200:
            d = r.json()
            print(f"✅✅ CONTAINER CREATED! id={d.get('id')} — IG ID PERFECT hai!")
            print("   (probe container ab expire ho jayega — koi post nahi hua)")
            # cleanup: delete the container so nothing lingers
            try:
                requests.delete(f"{GRAPH}/{V}/{d['id']}",
                                params={"access_token": tok}, timeout=30)
                print("   (probe container delete kar diya ✓)")
            except Exception:
                pass
            print("\n🎉 VERDICT: IG ID sahi hai + token publish kar sakta hai!")
            return 0
        err = r.json().get("error", {})
        msg = err.get("message", "")
        code = err.get("code", "?")
        print(f"❌ POST failed: code={code} subcode={err.get('error_subcode','-')}")
        print(f"   message: {msg[:300]}")
        msg_l = msg.lower()
        print("\n--- VERDICT ---")
        if "cannot find ig user" in msg_l or "does not exist" in msg_l:
            print("❌ IG ID GALAT hai (ya is page/token ke under nahi).")
            print("   → IG app → profile → View Page Source → search 178414")
            print("   → ya Business Suite se sahi IG ID lo")
        elif "not linked" in msg_l or "link" in msg_l:
            print("❌ IG account is page se linked nahi ya token ka page alag hai.")
        elif "permission" in msg_l or "scopes" in msg_l or code == 10:
            print("⚠️ Token mein instagram_content_publish ka masla — naya token chahiye.")
        elif "url" in msg_l or "video_url" in msg_l:
            print("✅ IG ID SAHI hai! (error sirf dummy url ki wajah se hai —")
            print("   asli video se publish ho jayegi)")
            return 0
        else:
            print(f"ℹ️ Unclear error — code {code}. Google kar ke dekho ya screen bhejo.")
        return 1
    except Exception as exc:
        print(f"❌ POST exception: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
