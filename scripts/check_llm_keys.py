#!/usr/bin/env python3
"""
Coercion Files — LLM / API Key Checker (V2.9.12).

GitHub Actions ke andar secrets ko test karta hai (key kabhi print nahi hoti):

  GROQ_API_KEY      — /openai/v1/models call
  GEMINI_API_KEY    — model list call
  PEXELS_API_KEY    — /v1/search probe
  PIXABAY_API_KEY   — /api/ probe

Har key ka status: VALID / INVALID / RATE-LIMITED / MISSING / ERROR
Exit code 0 agar sab theek, 1 agar koi broken (job red nahi karta — report hi hai).
"""

import os
import sys
import urllib.error
import urllib.request


def probe(url, headers=None, timeout=20):
    hdrs = {"User-Agent": "CoercionFiles-CI/1.0"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]
    except Exception as e:
        return 0, str(e).encode()


def check(name, present, status, detail=""):
    print(f"  {name:<16} {'[OK]' if status == 'valid' else '[X]'} {status.upper():<12} {detail}")


def main():
    print("API KEY CHECKER (values kabhi print nahi hotin)")
    print("=" * 60)
    bad = 0

    # Groq
    groq = os.environ.get("GROQ_API_KEY", "")
    if not groq:
        check("GROQ", False, "missing", "GROQ_API_KEY secret nahi hai")
        bad += 1
    else:
        code, body = probe("https://api.groq.com/openai/v1/models",
                           {"Authorization": f"Bearer {groq}"})
        if code == 200:
            check("GROQ", True, "valid", "(models list OK)")
        elif code == 401 or code == 403:
            check("GROQ", True, "invalid", f"HTTP {code} — key galat/expired")
            bad += 1
        elif code == 429:
            check("GROQ", True, "rate-limited", "HTTP 429")
            bad += 1
        else:
            check("GROQ", True, "error", f"HTTP {code} {body[:80]}")
            bad += 1

    # Gemini
    gem = os.environ.get("GEMINI_API_KEY", "")
    if not gem:
        check("GEMINI", False, "missing", "GEMINI_API_KEY secret nahi hai")
        bad += 1
    else:
        code, body = probe("https://generativelanguage.googleapis.com/v1beta/models?key=" + gem)
        if code == 200:
            check("GEMINI", True, "valid", "(model list OK)")
        elif code in (400, 401, 403):
            check("GEMINI", True, "invalid", f"HTTP {code} — key galat/expired")
            bad += 1
        elif code == 429:
            check("GEMINI", True, "rate-limited", "HTTP 429")
            bad += 1
        else:
            check("GEMINI", True, "error", f"HTTP {code} {body[:80]}")
            bad += 1

    # Pexels
    pex = os.environ.get("PEXELS_API_KEY", "")
    if not pex:
        check("PEXELS", False, "missing", "PEXELS_API_KEY secret nahi hai (clips fallback use hoga)")
    else:
        code, _ = probe("https://api.pexels.com/v1/search?query=dark&per_page=1",
                        {"Authorization": pex})
        check("PEXELS", True, "valid" if code == 200 else "error", f"HTTP {code}")

    # Pixabay
    pix = os.environ.get("PIXABAY_API_KEY", "")
    if not pix:
        check("PIXABAY", False, "missing", "PIXABAY_API_KEY secret nahi hai")
    else:
        code, _ = probe(f"https://pixabay.com/api/?key={pix}&q=dark&per_page=1")
        check("PIXABAY", True, "valid" if code == 200 else "error", f"HTTP {code}")

    print("=" * 60)
    print("Verdict:", "SAB KEYS THEEK" if bad == 0 else f"{bad} key(s) ko fix karna hai")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
