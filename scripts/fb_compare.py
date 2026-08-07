#!/usr/bin/env python3
"""Compare 0-view vs high-view videos: length, type (Reel vs video), title style."""
import os
import sys
import requests

V = "v25.0"
GRAPH = "https://graph.facebook.com"

tok = os.environ.get("FB_ACCESS_TOKEN", "")
page = os.environ.get("FB_PAGE_ID", "")
if not tok or not page:
    sys.exit("creds required")

def get(url, params):
    r = requests.get(url, params=params, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(r.text[:200])
    return r.json()

# Full video fields including length and format
out, url = [], f"{GRAPH}/{V}/{page}/videos"
params = {"access_token": tok,
          "fields": "id,title,description,created_time,length,views,format,permalink_url,status",
          "limit": 100}
while url:
    d = get(url, params)
    out += d.get("data", [])
    url = d.get("paging", {}).get("next")
    params = None

print(f"{'created':<11} {'views':>6} {'len(s)':>6}  title")
print("-" * 75)
for v in sorted(out, key=lambda x: int(x.get("views",0) or 0)):
    title = (v.get("title") or v.get("description") or "(no title)")[:50].replace("\n"," ")
    length = v.get("length", "?")
    print(f"{v.get('created_time','')[:10]:<11} {int(v.get('views',0) or 0):>6} {length!s:>6}  {title}")
