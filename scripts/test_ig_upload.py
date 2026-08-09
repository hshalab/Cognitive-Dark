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
    print("\n--- PROBE A: video_url path ---")
    try:
        r = requests.post(f"{GRAPH}/{V}/{ig_id}/media",
                          data={"access_token": tok, "media_type": "REELS",
                                "video_url": "https://example.com/probe.mp4",
                                "caption": "probe"},
                          timeout=30)
        if r.status_code == 200:
            d = r.json()
            print(f"✅✅ CONTAINER CREATED! id={d.get('id')} — IG ID PERFECT hai!")
            _cleanup(tok, d.get("id"))
            print("\n🎉 VERDICT: IG ID sahi hai + token publish kar sakta hai!")
            return 0
        err = r.json().get("error", {})
        print(f"❌ POST video_url failed: code={err.get('code')} subcode={err.get('error_subcode','-')}")
        print(f"   message: {err.get('message','')[:300]}")
    except Exception as exc:
        print(f"❌ POST exception: {exc}")

    # 3) PROBE B — RESUMABLE path (pipeline isi use karta hai!)
    print("\n--- PROBE B: resumable path (pipeline ka asal flow) ---")
    try:
        r = requests.post(f"{GRAPH}/{V}/{ig_id}/media",
                          data={"access_token": tok, "media_type": "REELS",
                                "upload_type": "resumable",
                                "caption": "probe"},
                          timeout=30)
        if r.status_code == 200:
            d = r.json()
            sid = d.get("upload_session_id") or d.get("id")
            print(f"✅✅ RESUMABLE CONTAINER CREATED! session={sid}")
            print("   → PIPELINE CHAL JAYEGA! (rupload ke saath)")
            _cleanup(tok, d.get("id"))
            print("\n🎉 VERDICT: RESUMABLE PATH WORKS — Instagram publish ready!")
            return 0
        err = r.json().get("error", {})
        msg = err.get("message", "")
        code = err.get("code", "?")
        print(f"❌ POST resumable failed: code={code} subcode={err.get('error_subcode','-')}")
        print(f"   message: {msg[:300]}")
        msg_l = msg.lower()
        print("\n--- VERDICT ---")
        if "cannot find ig user" in msg_l or "does not exist" in msg_l:
            print("❌ IG ID GALAT hai (ya is page/token ke under nahi).")
        elif "not linked" in msg_l or "link" in msg_l:
            print("❌ IG account is page se linked nahi ya token ka page alag hai.")
        elif "permission" in msg_l or "scopes" in msg_l or code == 10:
            print("⚠️ APP-LEVEL #10 — app ko Instagram API ki permission nahi.")
            print("   App dashboard (developers.facebook.com) mein yeh check karo:")
            print("   1. App mode = Live (Settings → Basic → App Mode)")
            print("   2. Products mein 'Instagram API' (naya naam) add ho")
            print("   3. Instagram Graph API product setup — app ko IG account")
            print("      se link karna hai (App Review → Permissions →")
            print("      instagram_business_content_publish → Advanced access)")
            print("   4. Page/IG app roles mein add ho (App Roles → Pages)")
        else:
            print(f"ℹ️ Unclear error — code {code}.")
        return 1
    except Exception as exc:
        print(f"❌ POST resumable exception: {exc}")
        return 1


def _cleanup(tok, cid):
    if not cid:
        return
    try:
        requests.delete(f"{GRAPH}/{V}/{cid}", params={"access_token": tok}, timeout=30)
        print("   (probe container delete kar diya ✓)")
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
