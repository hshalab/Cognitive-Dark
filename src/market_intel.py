#!/usr/bin/env python3
"""
Coercion Files — Market Intelligence.

Doosre channels ke PUBLIC data se seekhta hai (views, likes, comments, title
pattern, duration, publish time). Kisi doosre channel ka RETENTION data YouTube
kisi ko nahi deta — woh sirf aapka apna milta hai — is liye retention hamesha
aapki apni videos se aata hai (dekhiye reward_from_metrics).

Data sources (priority):
  1. data/competitor_videos.json  — aap khud seeding kar sakte hain (schema niche)
  2. YouTube Data API search      — agar YOUTUBE_API_KEY ya OAuth token ho to top
                                    videos ko queries se fetch karta hai

competitor_videos.json schema (list):
  [{"video_id","title","channel","published_at","view_count","like_count",
    "comment_count","duration_seconds","query"}]

Output:
  - pillar/hook prior means (jo ml_engine.apply_seed_priors kha sakta hai)
  - title-pattern weights (number, power-word, question, length bucket)
  - best duration bucket, best publish weekday/hour (UTC)
  - market_report() human-readable
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from config.settings import DATA_DIR, PILLARS

logger = logging.getLogger("market_intel")

COMPETITOR_FILE = DATA_DIR / "competitor_videos.json"

# Curated public-data patterns (NOT fabricated per-channel stats). Yeh woh broad
# shape hai jo faceless-psychology Shorts mein 2025-26 mein documented taur par
# chali hai. Real competitor data aate hi yeh override ho jate hain.
CURATED_PATTERN_PRIORS = {
    ("coercive_control", "warning"): 1.35,
    ("coercive_control", "red_flag"): 1.30,
    ("con_artists", "warning"): 1.28,
    ("mass_psychology", "chilling_fact"): 1.18,
    ("con_artists", "chilling_fact"): 1.15,
    ("coercive_control", "chilling_fact"): 1.12,
    ("brainwashing_myths", "chilling_fact"): 1.05,
    ("cults", "warning"): 0.92,
    ("interrogation", "question_hook"): 0.80,
    ("mind_control_history", "chilling_fact"): 0.78,
    ("stoic_defense", "chilling_fact"): 0.68,
}

POWER_WORDS = {
    "never", "secret", "stop", "instantly", "shocking", "hidden", "exposed",
    "truth", "lie", "trick", "trap", "warning", "always", "everyone",
    "nobody", "finally", "really", "actually", "scared",
}
QUESTION_RE = re.compile(r"\b(why|how|what|when|do you|are you|would you|can you)\b", re.I)
NUMBER_RE = re.compile(r"\b\d+\b")


# ─────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────
def load_competitor_videos() -> list[dict]:
    if not COMPETITOR_FILE.exists():
        return []
    try:
        data = json.loads(COMPETITOR_FILE.read_text(encoding="utf-8"))
        return [v for v in data if isinstance(v, dict) and v.get("title")]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("competitor file unreadable: %s", exc)
        return []


def save_competitor_videos(videos: list[dict]) -> None:
    COMPETITOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMPETITOR_FILE.write_text(
        json.dumps(videos, indent=2, ensure_ascii=False), encoding="utf-8")


def load_competitor_titles(path: Path | str | None = None) -> list[str]:
    """Load real competitor titles from data/competitor_seed.txt.

    One title per line; lines starting with # and blank lines are ignored.
    These are ACTUAL top-channel / viral-shorts titles from the niche used
    to derive hook/pillar frequencies — NOT fabricated view counts.
    """
    seed = Path(path) if path else DATA_DIR / "competitor_seed.txt"
    if not seed.exists():
        return []
    titles = []
    for line in seed.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if t and not t.startswith("#"):
            titles.append(t)
    return titles


def titles_to_videos(titles: list[str]) -> list[dict]:
    """Convert bare competitor titles to pseudo-video dicts for analysis.

    We don't fabricate view counts; instead every title carries equal unit
    weight and the analysis learns from PATTERN FREQUENCY — how often each
    pillar/hook/style appears across top-channel titles. Buckets with more
    titles get higher confidence (higher n) and a frequency-derived score.
    """
    return [{"video_id": f"seed-{i}", "title": t, "view_count": 1,
             "like_count": 0, "comment_count": 0, "duration_seconds": 45,
             "published_at": "", "query": "competitor_seed"}
            for i, t in enumerate(titles)]


def fetch_youtube_search(queries: list[str], max_per_query: int = 25) -> list[dict]:
    """YouTube Data API search → top videos with stats (public data only)."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    use_oauth = not api_key
    out: list[dict] = []
    try:
        from googleapiclient.discovery import build
        if use_oauth:
            # Reuse the OAuth upload token (readonly is included)
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            from platforms.youtube import _resolve_credentials
            path, _ = _resolve_credentials()
            if not path:
                logger.warning("no API key or OAuth creds — cannot fetch market data")
                return out
            info = json.loads(Path(path).read_text(encoding="utf-8"))
            creds = Credentials.from_authorized_user_info(info)
            if (creds.expired or not creds.valid) and creds.refresh_token:
                creds.refresh(Request())
            yt = build("youtube", "v3", credentials=creds)
        else:
            yt = build("youtube", "v3", developerKey=api_key)

        for q in queries:
            res = yt.search().list(part="id,snippet", q=q, type="video",
                                   order="viewCount", maxResults=max_per_query,
                                   videoDuration="short").execute()
            ids = [i["id"]["videoId"] for i in res.get("items", []) if i.get("id")]
            if not ids:
                continue
            stats = yt.videos().list(part="snippet,statistics,contentDetails",
                                     id=",".join(ids)).execute()
            for it in stats.get("items", []):
                cd = it.get("contentDetails", {}).get("duration", "")
                out.append({
                    "video_id": it["id"],
                    "title": it["snippet"]["title"],
                    "channel": it["snippet"].get("channelTitle", ""),
                    "published_at": it["snippet"].get("publishedAt", ""),
                    "view_count": int(it.get("statistics", {}).get("viewCount", 0) or 0),
                    "like_count": int(it.get("statistics", {}).get("likeCount", 0) or 0),
                    "comment_count": int(it.get("statistics", {}).get("commentCount", 0) or 0),
                    "duration_seconds": _iso8601(cd),
                    "query": q,
                })
    except Exception as exc:
        logger.warning("YouTube market fetch failed: %s", exc)
    return out


def _iso8601(s: str) -> int:
    m = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


# ─────────────────────────────────────────────────────────────
def sync_competitor_data(queries: list[str] = None, max_per_query: int = 10,
                         keep_newest: int = 200) -> dict:
    """Fetch LIVE top videos from YouTube for the niche and merge them into
    data/competitor_videos.json (bounded, deduped by video_id).

    V2.9: this is how the system learns "viral channels ke hisaab se" —
    real, public, current data — without any fabricated stats.

    Returns {"fetched": n, "total_stored": n, "queries": [...]}.
    """
    if queries is None:
        queries = [
            "cult psychology shorts", "coercive control signs",
            "con artist psychology", "gaslighting red flags",
            "mind control history", "how scams work psychology",
            "stoicism manipulation", "body language lies",
        ]
    fetched = fetch_youtube_search(queries, max_per_query=max_per_query)
    if not fetched:
        return {"fetched": 0, "total_stored": 0, "queries": queries,
                "note": "no YouTube key/OAuth — live sync skipped (seed data used)"}

    existing = load_competitor_videos()
    by_id = {v["video_id"]: v for v in existing if v.get("video_id")}
    for v in fetched:
        by_id[v["video_id"]] = v      # newest wins
    merged = list(by_id.values())
    # keep the highest-engagement slice (not just newest) when over budget
    if len(merged) > keep_newest:
        merged.sort(key=lambda v: (float(v.get("view_count", 0) or 0) +
                                   10 * float(v.get("like_count", 0) or 0)),
                    reverse=True)
        merged = merged[:keep_newest]
    save_competitor_videos(merged)
    logger.info("Competitor sync: %d new, %d total stored", len(fetched), len(merged))
    return {"fetched": len(fetched), "total_stored": len(merged), "queries": queries}


# Feature extraction
# ─────────────────────────────────────────────────────────────
def _norm_log(values: list[float]) -> list[float]:
    if not values:
        return []
    logs = [math.log10(max(1.0, v)) for v in values]
    lo, hi = min(logs), max(logs)
    if hi - lo < 1e-9:
        return [0.5 for _ in values]
    return [(x - lo) / (hi - lo) for x in logs]


def classify_hook(title: str) -> str:
    t = title.lower()
    if QUESTION_RE.search(t):
        return "question_hook"
    if any(w in t for w in ("sign", "red flag", "tactic", "trick", "step", "things")):
        return "red_flag"
    if any(w in t for w in ("run", "never", "warning", "beware", "if they", "don't")):
        return "warning"
    if any(w in t for w in ("later", "truth", "actually", "reason", "why you", "turned out")):
        return "plot_twist"
    if NUMBER_RE.search(t) and ("day" in t or "step" in t or "sign" in t):
        return "timeline"
    if any(w in t for w in ("case", "story", "confession", "admitted")):
        return "confession"
    if re.search(r"#?\d+\b", t) and ("case" in t or "file" in t):
        return "case_file"
    return "chilling_fact"


def classify_pillar(title: str) -> str:
    t = title.lower()
    table = {
        "coercive_control": ("gaslight", "manipulat", "narcissist", "red flag",
                             "toxic", "boundary", "love bomb", "silent treatment"),
        "con_artists": ("scam", "fraud", "con artist", "swindler", "catfish",
                        "romance scam", "phish"),
        "cults": ("cult", "jonestown", "nxivm", "brainwash", "recruit"),
        "mass_psychology": ("crowd", "propaganda", "social media", "viral",
                            "persuasion", "influence", "behavior"),
        "brainwashing_myths": ("brain", "mind trick", "psychology fact",
                               "cognitive", "subconscious"),
        "interrogation": ("lie", "detect", "interrogation", "body language",
                          "microexpression"),
        "mind_control_history": ("cia", "mkultra", "experiment", "declassified",
                                 "mind control"),
        "stoic_defense": ("stoic", "marcus aurelius", "mental toughness",
                          "discipline", "emotion"),
    }
    for key, words in table.items():
        if any(w in t for w in words):
            return key
    # default to the first pillar (kept generic)
    return PILLARS[0]["key"] if PILLARS else "coercive_control"


def _features(v: dict) -> dict:
    title = v.get("title", "")
    words = title.split()
    return {
        "pillar": classify_pillar(title),
        "hook": classify_hook(title),
        "has_number": bool(NUMBER_RE.search(title)),
        "has_power": any(w.lower() in POWER_WORDS for w in words),
        "is_question": bool(QUESTION_RE.search(title)),
        "title_len": len(title),
        "duration": int(v.get("duration_seconds", 0) or 0),
        "views": float(v.get("view_count", 0) or 0),
        "likes": float(v.get("like_count", 0) or 0),
        "comments": float(v.get("comment_count", 0) or 0),
    }


def _composite_score(v: dict, view_norm: float) -> float:
    """Blend public signals. Engagement rate weighted, views normalized 0..1."""
    views = max(1.0, v["views"])
    eng = (v["likes"] + 2 * v["comments"]) / views  # engagement rate
    eng = min(1.0, eng * 20.0)  # 5%+ engagement → cap
    return round(0.65 * view_norm + 0.35 * eng, 4)


# ─────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────
def analyze(videos: list[dict] | None = None) -> dict:
    # Priority: explicit videos > competitor_videos.json (with real stats) >
    # competitor_seed.txt (real top-channel titles, frequency learning) >
    # hard-coded curated fallback.
    if videos is None:
        videos = load_competitor_videos()
        source = "competitor_videos"
        if not videos:
            titles = load_competitor_titles()
            if titles:
                videos = titles_to_videos(titles)
                source = "competitor_titles"
        if not videos:
            return {
                "source": "curated_patterns",
                "video_count": 0,
                "pair_means": [
                    {"pillar": p, "hook": h, "mean": m, "n": 4}
                    for (p, h), m in CURATED_PATTERN_PRIORS.items()
                ],
                "title_patterns": _curated_title_patterns(),
                "duration_best_s": 42,
                "publish_window": {"weekday": "mon-fri", "hour_utc": [11, 16, 21]},
            }
    elif videos:
        source = "provided"
    else:
        # Caller passed an explicit empty list — use curated fallback.
        return {
            "source": "curated_patterns",
            "video_count": 0,
            "pair_means": [
                {"pillar": p, "hook": h, "mean": m, "n": 4}
                for (p, h), m in CURATED_PATTERN_PRIORS.items()
            ],
            "title_patterns": _curated_title_patterns(),
            "duration_best_s": 42,
            "publish_window": {"weekday": "mon-fri", "hour_utc": [11, 16, 21]},
        }

    feats = [_features(v) for v in videos]
    norms = _norm_log([f["views"] for f in feats])
    for f, n in zip(feats, norms, strict=True):
        f["score"] = _composite_score(f, n)

    # When learning from competitor titles (no real view counts), score each
    # pattern by its FREQUENCY among top-channel titles — the more often a
    # pillar/hook shows up in winners, the stronger the prior. With real
    # view stats, the composite score dominates instead.
    use_views = any(f["views"] > 1 for f in feats)
    n_total = len(feats) or 1
    counts: dict[tuple, int] = defaultdict(int)
    for f in feats:
        counts[(f["pillar"], f["hook"])] += 1
    bucket: dict[tuple, list[float]] = defaultdict(list)
    for f in feats:
        bucket[(f["pillar"], f["hook"])].append(f["score"])
    pair_means = sorted(
        ({"pillar": p, "hook": h,
          "mean": round((sum(s) / len(s)) if use_views
                        else (0.3 + 0.7 * counts[(p, h)] / n_total), 3),
          "n": len(s), "count": counts[(p, h)]}
         for (p, h), s in bucket.items()),
        key=lambda x: x["mean"], reverse=True)

    # Title patterns
    patterns = {
        "has_number": _avg(feats, "has_number"),
        "has_power_word": _avg(feats, "has_power"),
        "is_question": _avg(feats, "is_question"),
        "title_len_best": _best_len(feats),
    }
    dur = round(_weighted_avg(feats, "duration"))
    pub = _best_publish_window(videos)

    return {
        "source": source,
        "video_count": len(videos),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "pair_means": pair_means,
        "title_patterns": patterns,
        "duration_best_s": dur,
        "publish_window": pub,
    }


def _avg(feats, key):
    if not feats:
        return 0.0
    return round(sum(1.0 if f[key] else 0.0 for f in feats) / len(feats), 3)


def _best_len(feats):
    # bucket by 20-char bins
    bins: dict[int, list[float]] = defaultdict(list)
    for f in feats:
        b = max(20, min(100, (f["title_len"] // 20) * 20))
        bins[b].append(f["score"])
    if not bins:
        return 40
    best = max(bins, key=lambda b: sum(bins[b]) / len(bins[b]))
    return best


def _weighted_avg(feats, key):
    denom = sum(f["score"] for f in feats) or 1.0
    return sum(f[key] * f["score"] for f in feats) / denom


def _best_publish_window(videos):
    by_hour: dict[int, list[float]] = defaultdict(list)
    by_day: dict[int, list[float]] = defaultdict(list)
    for v in videos:
        ts = v.get("published_at", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        score = math.log10(max(1.0, float(v.get("view_count", 0) or 0)))
        by_hour[dt.hour].append(score)
        by_day[dt.weekday()].append(score)
    top_hours = sorted(by_hour, key=lambda h: sum(by_hour[h]) / len(by_hour[h]), reverse=True)[:4]
    top_days = sorted(by_day, key=lambda d: sum(by_day[d]) / len(by_day[d]))[:3]
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    return {"weekday": "-".join(names[d] for d in sorted(top_days)),
            "hour_utc": sorted(top_hours)}


def _curated_title_patterns():
    return {
        "has_number": 0.55,
        "has_power_word": 0.82,
        "is_question": 0.40,
        "title_len_best": 40,
        "note": "Direct 1-claim hooks with a power word outperform long documentary titles.",
    }


# ─────────────────────────────────────────────────────────────
# Export to bandit priors
# ─────────────────────────────────────────────────────────────
def priors_for_bandit(analysis: dict | None = None, sample_n: int = 4) -> dict:
    """Convert market analysis into {(pillar,hook): (mean, n)} for ml_engine."""
    a = analysis or analyze()
    out = {}
    for row in a["pair_means"]:
        mean = max(0.1, min(2.0, float(row["mean"]) * 1.6))  # scale 0..~1.6
        out[(row["pillar"], row["hook"])] = (round(mean, 3), int(row.get("n", sample_n)))
    return out


def market_report(analysis: dict | None = None) -> str:
    a = analysis or analyze()
    lines = ["=" * 60, "📊 MARKET INTELLIGENCE REPORT", "=" * 60,
             f"source: {a['source']}  |  videos: {a['video_count']}", ""]
    lines.append("Top (pillar, hook) patterns:")
    for row in a["pair_means"][:10]:
        lines.append(f"  {row['mean']:.2f}  n={row['n']:<3} {row['pillar']:22} / {row['hook']}")
    tp = a["title_patterns"]
    lines += ["", "Title patterns:",
              f"  power words : {tp.get('has_power_word', 0):.0%}",
              f"  has number  : {tp.get('has_number', 0):.0%}",
              f"  is question : {tp.get('is_question', 0):.0%}",
              f"  best length : ~{tp.get('title_len_best', '?')} chars",
              "",
              f"Best duration: ~{a['duration_best_s']}s",
              f"Best window  : {a['publish_window']['weekday']} at "
              f"{a['publish_window']['hour_utc']} (UTC)",
              "=" * 60]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if "--fetch" in sys.argv:
        queries = ["dark psychology facts", "manipulation tactics",
                   "scam psychology", "cult psychology", "gaslighting signs"]
        vids = fetch_youtube_search(queries, max_per_query=20)
        existing = load_competitor_videos()
        seen = {v["video_id"] for v in existing}
        existing += [v for v in vids if v["video_id"] not in seen]
        save_competitor_videos(existing)
        print(f"Saved {len(existing)} competitor videos.")
    print(market_report())
