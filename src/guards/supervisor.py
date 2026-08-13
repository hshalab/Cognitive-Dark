#!/usr/bin/env python3
"""USASupervisor — gate ka aakhri judge (fail-closed).

Supervisor 4 cheezein verify karta hai:

1. INDEPENDENCE AUDIT — har guard ne asal mein measure kiya?
   • har verdict `independent=True` ho
   • har verdict ka `evidence` khali na ho
   • kisi guard ne UNKNOWN nahi diya (measure nahi kar saka = HOLD)
   • producer ke self-scores guards tak pahunche hi nahi (gate unhein
     strip kar deta hai — supervisor dobara assert karta hai)

2. USA AUDIENCE CALIBRATION —
   • content English mein hai (ASCII ratio >= 0.92)
   • roman-Urdu/ghair-angrezi tokens nahi (USA audience ke liye)
   • British spellings nahi (colour/behaviour...) — USA consistency
   • ₹/₨/PKR nahi — sirf $/dollars
   • publish window ET 6am-11pm (USA audience jag rahi ho)

3. CROSS-PLATFORM NATIVENESS — har platform ki copy distinct hai
   (identical copy teeno platforms par = spam signal)

4. FINAL GRADE + RELEASE —
   A = sab PASS + evidence complete
   B = PASS + 1-2 WARN
   C = PASS + 2+ WARN (release hoti hai magar note ke saath)
   F = koi FAIL/UNKNOWN → HOLD (video gate se nahi guzarti)

Fail-CLOSED principle: supervisor shak hone par video HOLD karta hai.
Koi measurement "nahi ho saki" to wo pass nahi — HOLD.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("guards.supervisor")

# Roman-Urdu/ghair-angrezi tokens jo USA content mein nahi hone chahiye
# (word-boundary match, sirf clear words — English false-positives avoid)
NON_EN_TOKENS = [
    "hain", "karo", "karna", "karte", "karne", "theek", "thik", "zaroor",
    "zaroorat", "nahi", "matlab", "tum", "wala", "wali", "kyun", "kyon",
    "kaise", "aisa", "yeh", "isliye", "usay", "chahiye", "abhi", "kya",
    "khud", "bohat", "bahut", "bhi", "kuch", "magar", "lekin", "jabke",
    "taake", "apna", "apni", "logon", "doston", "shukriya", "madad",
    "insaan", "insaani", "cheezein", "kaun", "kabhi", "pehle", "hua",
    "hota", "hoti", "jata", "jati", "sabse", "kisi", "koi", "gaya",
    "gayi", "dena", "lena", "dikhaye", "batata", "bolta", "chalti",
]
BRITISH = ["colour", "behaviour", "favourite", "programme", "organise",
           "recognise", "analysing", "centre", "defence", "offence"]
# V3.5: "rs." jaise tokens ko WORD-BOUNDARY ke saath match karo — warna
# "transfers." jaise har English lafz mein "rs." mil jata hai (false positive)
NON_US_CURRENCY = ["₹", "₨"]
USA_MIN_HOUR, USA_MAX_HOUR = 6, 23

NON_EN_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in NON_EN_TOKENS) + r")\b", re.I)
BRITISH_RE = re.compile(
    r"\b(?:" + "|".join(BRITISH) + r")\b", re.I)
CURRENCY_RE = re.compile(
    r"\u20b9|₨|\b(?:pkr|rs\.|rupees)\b", re.I)


def _text_of(payload: dict) -> str:
    script = payload.get("script") or {}
    pkg = payload.get("package") or {}
    parts = [
        str(pkg.get("title") or ""), str(pkg.get("description") or ""),
        str(script.get("title") or ""), str(script.get("hook") or ""),
        " ".join(str(s.get("caption", "")) for s in (script.get("scenes") or [])),
    ]
    return "\n".join(parts)


class USASupervisor:
    name = "supervisor"

    def review(self, payload: dict, verdicts: list) -> dict:
        """Final judge. Returns {released, grade, violations, notes, checks}."""
        violations, notes, checks = [], [], {}

        # ── 1) Independence audit ─────────────────────────────────
        unknown = [v for v in verdicts if v.status == "UNKNOWN"]
        no_evidence = [v for v in verdicts if not v.evidence]
        dependent = [v for v in verdicts if not v.independent]
        if unknown:
            violations.append("fail-closed: guards measure nahi kar sake — "
                              f"{[v.guard for v in unknown]}")
        if no_evidence:
            violations.append("guard ne koi evidence hi nahi diya — "
                              f"{[v.guard for v in no_evidence]} (independent "
                              "measurement ke baghair pass = jhoot)")
        if dependent:
            violations.append("guard producer ke scores par rely kar raha hai — "
                              f"{[v.guard for v in dependent]}")
        checks["independence"] = {
            "unknown": [v.guard for v in unknown],
            "no_evidence": [v.guard for v in no_evidence],
            "dependent": [v.guard for v in dependent],
        }
        # producer self-scores strip ho chuke hone chahiye
        script = payload.get("script") or {}
        leaked = [k for k in ("script_quality", "hook_score", "ctr_score")
                  if k in script]
        if leaked:
            violations.append(f"producer self-scores gate tak leak ho gaye: "
                              f"{leaked} — guards independent nahi rahe")
        checks["producer_scores_leaked"] = leaked

        # ── 2) USA audience calibration ───────────────────────────
        text = _text_of(payload)
        letters = sum(1 for ch in text if ch.isalpha())
        ascii_letters = sum(1 for ch in text if ch.isascii() and ch.isalpha())
        ascii_ratio = round(ascii_letters / max(1, letters), 3)
        non_en_hits = sorted(set(NON_EN_RE.findall(text)))
        brit_hits = sorted(set(BRITISH_RE.findall(text)))
        curr_hits = CURRENCY_RE.findall(text)
        if ascii_ratio < 0.92:
            violations.append(f"content {ascii_ratio:.0%} ASCII — English nahi "
                              "hai (USA audience)")
        if non_en_hits:
            violations.append(f"non-English tokens: {non_en_hits[:8]} — "
                              "USA audience ke liye nahi")
        if brit_hits:
            violations.append(f"British spellings: {brit_hits} — USA English "
                              "consistency ke liye American spelling chahiye")
        if curr_hits:
            violations.append(f"non-USD currency symbols: {curr_hits} — USA "
                              "audience $ mein sochti hai")
        checks["usa_audience"] = {"ascii_ratio": ascii_ratio,
                                  "non_en": non_en_hits,
                                  "british": brit_hits,
                                  "currency": curr_hits}

        # ── 3) Publish window (ET) ────────────────────────────────
        publish_at = payload.get("publish_at")
        window_ok = True
        window_note = "no publish time given"
        if publish_at is not None:
            try:
                from datetime import datetime, timezone
                from zoneinfo import ZoneInfo
                if isinstance(publish_at, str):
                    publish_at = datetime.fromisoformat(publish_at)
                if publish_at.tzinfo is None:
                    publish_at = publish_at.replace(tzinfo=timezone.utc)
                et_hour = publish_at.astimezone(ZoneInfo("America/New_York")).hour
                window_ok = USA_MIN_HOUR <= et_hour <= USA_MAX_HOUR
                window_note = f"publish {et_hour}:00 ET"
                if not window_ok:
                    violations.append(f"publish window {et_hour}:00 ET — USA "
                                      f"audience ke liye {USA_MIN_HOUR}-{USA_MAX_HOUR}h "
                                      "ET chahiye (raat 2 baje = dead post)")
            except ValueError:
                window_note = f"bad publish_at: {publish_at}"
                window_ok = False
                violations.append("publish time invalid")
        checks["publish_window"] = {"ok": window_ok, "note": window_note}

        # ── 4) Cross-platform nativness ────────────────────────────
        siblings = payload.get("sibling_packages") or {}
        if siblings:
            from ml_engine import token_overlap
            own = payload.get("package") or {}
            for other_p, other_pkg in siblings.items():
                ov = token_overlap(
                    str(own.get("description") or "") + str(own.get("title") or ""),
                    str(other_pkg.get("description") or "") + str(other_pkg.get("title") or ""))
                if ov > 0.9:
                    violations.append(f"copy {other_p} se {ov:.0%} identical — "
                                      "cross-platform spam signal")
                else:
                    notes.append(f"copy vs {other_p}: {ov:.0%} distinct ✓")
        checks["siblings"] = {p: "distinct" for p in siblings}

        # ── Grade + release ───────────────────────────────────────
        fails = [v for v in verdicts if v.status in ("FAIL", "UNKNOWN")]
        warns = [v for v in verdicts if v.status == "WARN"]
        passed = [v for v in verdicts if v.status == "PASS"]
        if fails or violations:
            grade = "F"
        elif len(warns) >= 3:
            grade = "C"
        elif warns:
            grade = "B"
        elif passed:
            grade = "A"
        else:
            grade = "F"

        released = not fails and not violations
        if not released:
            notes.append(f"HOLD: {len(fails)} guard fail + "
                         f"{len(violations)} supervisor violations")
        return {"released": bool(released), "grade": grade,
                "violations": violations, "notes": notes, "checks": checks,
                "guard_summary": {"pass": len(passed), "warn": len(warns),
                                  "fail": len(fails)}}
