"""V3.4 HONESTY SUITE — system ab khud ko jhooti tareef nahi de sakta.

Ye tests us bug ko lock karte hain jahan system weak content ko bhi "strong"
score deta tha aur ML publish hone par hi khud ko reward kar leta tha —
natija: har formula "viral" lagta tha jabke views 0 thay, aur ghalat
content repeat hota rehta tha (YT/FB/IG teeno ka nuqsan).

Har test ek specific jhoot ko pakarta hai. Agar koi future change in tests
ko tor de to samjho system dobara khud ko dhoka dene laga hai.
"""
from pathlib import Path

import pytest

from ml_engine import LearningSystem


# ── 1. Hook scorer ab weak hook ko weak keh sakta hai ──────────────
def test_weak_hook_scores_low():
    from viral_intel import score_hook
    weak = score_hook("Let me tell you something about psychology today")
    strong = score_hook("Why smart people join cults")
    assert weak["score"] < 0.5, weak          # weak FAIL hota hai
    assert weak["weak"] is True
    assert strong["score"] > weak["score"]
    assert strong["weak"] is False


def test_fragment_hook_is_not_strong():
    from viral_intel import score_hook
    # purana fallback "Stop letting them" jaisa fragment deta tha —
    # incomplete hook ab strong nahi maana jaata
    frag = score_hook("Stop letting them")
    assert frag["score"] < 0.5, frag


# ── 2. Title/CTR scorer ab weak title ko weak keh sakta hai ───────
def test_weak_title_scores_low_ctr():
    from ctr_optimizer import describe_ctr_grade, score_title_ctr
    weak = score_title_ctr("video about things", "youtube")
    assert weak.score < 0.45, weak.score
    assert describe_ctr_grade(weak.score).startswith("D")
    strong = score_title_ctr("3 Signs You're in a Cult: Warning Psychology", "youtube")
    assert strong.score > weak.score


def test_ctr_score_works_for_all_platforms():
    # V3.4 fix: `keyword_found` undefined tha FB/IG branch mein → NameError
    from ctr_optimizer import score_title_ctr
    for plat in ("youtube", "facebook", "instagram"):
        r = score_title_ctr("Why smart people join cults", plat)
        assert 0.0 <= r.score <= 1.0


def test_ctr_variants_are_grammatical():
    from ctr_optimizer import suggest_ctr_improved_title
    variants = suggest_ctr_improved_title("Why smart people join dangerous cults", "youtube")
    # purana bug: "3 why Smart People..." jaisa toota grammar — ab har
    # variant ka pehla lafz capital hota hai aur "Why"/digit + why combo nahi
    for v in variants:
        assert not v[:1].isdigit() or v.split(" ")[1].lower() != "why", v
        assert v[0].isupper(), v


# ── 3. Full-script gate ab generic fluff ko fail karta hai ────────
def test_fluff_script_fails_gate():
    from viral_intel import score_script
    fluff = {
        "hook": "Hello everyone welcome back",
        "scenes": [
            {"caption": "In this video we will talk about many things."},
            {"caption": "It is important to remember some stuff."},
            {"caption": "Thank you for watching."},
        ],
    }
    q = score_script(fluff)
    assert q["score"] < 0.5, q
    assert any("anchor" in i for i in q["issues"]), q["issues"]


def test_concrete_script_passes_gate():
    from viral_intel import score_script
    good = {
        "hook": "Why smart people join cults",
        "scenes": [
            {"caption": "Why smart people join cults."},
            {"caption": "She wired $380,000 in ten minutes. The scammer hacked "
                         "human fear, not a computer."},
            {"caption": "Cialdini's scarcity principle explains the urgency. "
                         "If this helped, hit like and comment below."},
        ],
    }
    q = score_script(good)
    assert q["score"] >= 0.65, q


# ── 4. Reward: missing data = "unknown", pass NAHI ───────────────
def test_missing_retention_does_not_pass_gate():
    from reward import reward_from_dict
    _reward, breakdown = reward_from_dict({"views": 100, "likes": 2, "comments": 0})
    assert breakdown["quality_gate_passed"] is False
    assert breakdown["quality_gate_status"] == "unknown"   # data hi nahi tha
    assert breakdown["data_complete"] is False


def test_voice_rating_missing_is_neutral_not_perfect():
    from reward import VideoMetrics
    m = VideoMetrics(views=500)      # voice_rating None → koi evidence nahi
    assert m.effective_voice_rating() == 0.5   # pehle 1.0 (free perfect score)
    m2 = VideoMetrics(views=500, voice_rating=0.9)
    assert m2.effective_voice_rating() == 0.9


# ── 5. ML ab publish par khud ko reward nahi deta ────────────────
def test_zero_weight_reward_does_not_inflate_n(tmp_path: Path):
    ml = LearningSystem(store_path=tmp_path / "store.json")
    key = "cults::warning::morning"
    before = ml.data["arms"].setdefault(key, {"n": 0, "rewards": 0.0,
                                              "sum_sq": 0.0})["n"]
    ml.apply_reward(key, "published", weight=0.0)   # bonus_consistent = 0
    arm = ml.data["arms"][key]
    assert arm["n"] == before            # koi fake observation add nahi hua
    assert arm["rewards"] == 0.0
    assert not any(r["reason"] == "published" for r in ml.data["reward_log"])


# ── 6. Recency penalty ab SELECTION par asar karti hai ───────────
def test_recency_penalty_actually_steers_choice(tmp_path: Path):
    from ml_engine import current_day_part
    ml = LearningSystem(store_path=tmp_path / "store.json")
    ml.cfg["policy"] = "ucb"
    ml.cfg["epsilon"] = 0.0
    # pehle ek bar choose karo taake current day-part ke sab arms create hon
    ml.choose_strategy()
    dp = current_day_part()
    # har arm ko 1 real outcome do (cold-start force branch band ho jaye)
    for key in list(ml.data["arms"].keys()):
        ml.data["arms"][key] = {"n": 1, "rewards": 2.0, "sum_sq": 4.0,
                                "plays": 0, "updated": "2026-01-01T00:00:00+00:00"}
    target = f"cults::case_file::{dp}"
    recent = [k for k in ml.data["arms"] if k != target]
    chosen = ml.choose_strategy(recent_keys=recent)
    # baqi sab arms recency-penalty se aadhe ho gaye → sirf target full score
    assert chosen["arm_key"] == target, chosen["arm_key"]


# ── 7. Prior double-count ab impossible hai ─────────────────────
def test_prior_never_double_counted(tmp_path: Path):
    from bandit import posterior_from_arm
    ml = LearningSystem(store_path=tmp_path / "store.json")
    ml.apply_seed_priors()
    key = "con_artists::warning::morning"
    ml.record_outcome(key, 5.0)
    post = posterior_from_arm(ml.data["arms"][key])
    pn = ml.data["arms"][key]["prior_n"]
    # effective_n = prior_n + 1 (real) — 2x nahi
    assert post.effective_n == pn + 1


# ── 8. Legacy store migration: priors un-merge hote hain ─────────
def test_legacy_merged_prior_is_unmerged_on_load(tmp_path: Path):
    import json
    store = tmp_path / "store.json"
    store.write_text(json.dumps({
        "arms": {
            "cults::warning::morning": {
                "n": 12,                      # 7 prior + 5 real (legacy)
                "rewards": 7 * 1.2 + 5 * 3.0,  # prior block + real block
                "sum_sq": 7 * 1.2 ** 2 + 5 * 9.0,
                "prior_n": 7, "prior_mean": 1.2, "seeded": True,
                "plays": 5, "updated": "2026-01-01T00:00:00+00:00",
            },
        },
        "model_version": 3,
    }), encoding="utf-8")
    ml = LearningSystem(store_path=store)
    arm = ml.data["arms"]["cults::warning::morning"]
    assert arm["n"] == 5                       # sirf REAL outcomes
    assert arm["rewards"] == pytest.approx(15.0)
    assert arm["prior_n"] == 7                 # prior apni jagah intact
    assert ml.data.get("prior_dedup_migrated") == 1


def test_migration_is_one_time_and_never_destroys_real_data(tmp_path: Path):
    """V3.6: migration sirf EK baar chalti hai. Naye schema mein legit arm ka
    n >= prior_n ho sakta hai (real outcomes >= prior count) — dobara load
    par real data subtract NAHI hona chahiye."""
    import json
    store = tmp_path / "store.json"
    store.write_text(json.dumps({
        "arms": {
            "cults::red_flag::morning": {
                "n": 2, "rewards": -3.0, "sum_sq": 5.0, "plays": 1,
                "prior_n": 2, "prior_mean": 0.514, "seeded": True,
                "updated": "2026-01-01T00:00:00+00:00",
            },
        },
        "prior_dedup_migrated": 1,      # pehle ho chuki
        "model_version": 4,
    }), encoding="utf-8")
    ml = LearningSystem(store_path=store)
    arm = ml.data["arms"]["cults::red_flag::morning"]
    assert arm["n"] == 2               # REAL data intact
    assert arm["rewards"] == -3.0
    ml2 = LearningSystem(store_path=store)   # dobara load — phir bhi intact
    arm2 = ml2.data["arms"]["cults::red_flag::morning"]
    assert arm2["n"] == 2 and arm2["rewards"] == -3.0


def test_event_replay_skips_published_rewards(tmp_path: Path):
    """Diary se rebuild hone par legacy '<platform>_published' fake rewards
    wapas nahi aa sakte — sirf real events replay hote hain."""
    import json
    events = tmp_path / "store.json.events.jsonl"
    events.write_text("\n".join(json.dumps(e) for e in [
        {"ts": "2026-01-01T00:00:00+00:00", "type": "reward",
         "arm": "cults::warning::morning", "w": 1.0,
         "reason": "youtube_published"},
        {"ts": "2026-01-02T00:00:00+00:00", "type": "reward",
         "arm": "cults::warning::morning", "w": 2.5,
         "reason": "metrics:vid123"},
    ]), encoding="utf-8")
    ml = LearningSystem(store_path=tmp_path / "store.json")
    arm = ml.data["arms"]["cults::warning::morning"]
    assert arm["n"] == 1                # sirf metrics reward replay hua
    assert arm["rewards"] == pytest.approx(2.5)


# ── 9. Virality index bina real data ke kabhi "viral-ready" nahi ─
def test_virality_index_honest_without_performance(tmp_path: Path):
    from viral_intel import virality_index
    ml = LearningSystem(store_path=tmp_path / "store.json")
    ml.register_video({"title": "Test video", "hook": "Test",
                       "arm_key": "cults::warning::morning",
                       "text": "x", "text_sha": "abc"})
    idx = virality_index(ml.data)
    # videos hain par koi real performance nahi → index claim nahi kar sakta
    assert idx["honest"] is True
    assert "no real performance" in idx["honest_note"].lower() \
        or "real" in idx["honest_note"].lower()
    assert idx["own_fingerprint"]["avg_score"] == 0.0


# ── 10. Seeded priors ab "experience" nahi ban sakte ─────────────
def test_seeded_arms_are_not_experienced(tmp_path: Path):
    ml = LearningSystem(store_path=tmp_path / "store.json")
    ml.apply_seed_priors()
    top = ml.best_formulas(3)
    assert all(t["n_real"] == 0 for t in top)   # sab sirf belief, data nahi


# ── 11. V3.6 REALITY SWEEP: estimated ≠ measured ────────────────
def test_estimated_retention_is_discounted():
    """Guess-based retention ko MEASURED wali se kam reward milna chahiye
    aur quality gate use 'unknown' bataye — fabricated data viral credit
    nahi le sakta."""
    from reward import reward_from_dict
    r_est, b_est = reward_from_dict({
        "views": 10000, "likes": 600, "comments": 100,
        "retention": 0.85, "retention_estimated": True})
    r_meas, b_meas = reward_from_dict({
        "views": 10000, "likes": 600, "comments": 100,
        "retention": 0.85, "retention_estimated": False})
    assert r_est < r_meas                       # estimate kam value rakhta hai
    assert b_est["retention_estimated"] is True
    assert b_est["quality_gate_passed"] is False
    assert b_est["quality_gate_status"] == "unknown"   # guess ≠ measured
    assert b_meas["quality_gate_status"] == "passed"   # asli data = pass
    assert b_meas["retention_measured"] is True


def test_incomplete_data_credits_without_learning(tmp_path: Path):
    """Retention missing/estimated ho to arm par NA reward NA penalty —
    'pata nahi' se seekha nahi jata (pehle -1.0 penalty lag jati thi)."""
    ml = LearningSystem(store_path=tmp_path / "store.json")
    key = "cults::warning::morning"
    ml.record_video_id("youtube", "vid123", key, "test")
    before = dict(ml.data["arms"].get(key, {"n": 0, "rewards": 0.0}))
    ml.credit_video("vid123", {"views": 100, "likes": 2, "comments": 0,
                               "retention_estimated": True})
    arm = ml.data["arms"].get(key, {"n": 0, "rewards": 0.0})
    assert arm["n"] == before["n"]              # koi observation add nahi
    assert arm["rewards"] == before["rewards"]


def test_measured_metrics_do_train_arm(tmp_path: Path):
    from ml_engine import LearningSystem as _LS
    ml = _LS(store_path=tmp_path / "store.json")
    key = "cults::warning::morning"
    ml.record_video_id("youtube", "vid456", key, "test")
    ml.credit_video("vid456", {"views": 20000, "likes": 1500, "comments": 200,
                               "shares": 100, "retention": 0.78,
                               "retention_estimated": False})
    arm = ml.data["arms"][key]
    assert arm["n"] >= 1                        # REAL data se seekha
    assert arm["rewards"] > 0


def test_playbook_manual_checks_do_not_inflate_score():
    """Manual items (reply/pin comment) ab PASS nahi hote — sirf verifiable
    checks score banate hain."""
    from algorithm_playbook import audit_package
    pkg = {"title": "Stop Letting Them Control You",
           "description": "Psychology: how coercion works and how to "
                          "protect yourself. " * 8,
           "tags": ["psychology", "coercion", "mind control"],
           "duration_s": 48}
    a = audit_package(pkg, "youtube")
    manual = [c for c in a["checks"] if c.get("status") == "manual"]
    assert manual, "manual checks maujood hone chahiye"
    assert all(c["ok"] is None for c in manual)   # PASS ka jhoot nahi
    # score sirf machine-verifiable checks se banta hai
    assert a["verifiable"] == len(a["checks"]) - len(manual)
    assert a["passed"] <= a["verifiable"]


def test_growth_rewards_are_noop():
    """Fuzzy channel-growth attribution (V3.6) ab koi reward nahi deta —
    growth kis video se aayi ye batana impossible hai."""
    import sys

    from ml_engine import LearningSystem as _LS
    sys.path.insert(0, "scripts")
    ml = _LS(store_path="/tmp/growth_test_store.json")
    prog = {"youtube": {"last_growth": 50}, "facebook": {"last_growth": 10},
            "instagram": {"last_growth": 0}}
    before = sum(len(r) for r in [ml.data.get("reward_log", [])])
    try:
        from fetch_metrics import apply_growth_rewards
        apply_growth_rewards(ml, prog)
    except Exception as exc:   # fetch_metrics import light hai
        assert "Growth" in str(exc) or exc is None
        return
    after = sum(len(r) for r in [ml.data.get("reward_log", [])])
    assert after == before


def test_market_intel_curated_fallback_is_flagged():
    """Bina competitor data ke fallback priors BELIEF hain — flag hona chahiye."""
    from market_intel import analyze
    a = analyze([])
    assert a["source"] == "curated_patterns"
    assert a.get("curated") is True


def test_credit_estimates_never_claim_measured_yt():
    """YT estimate function ka flag reward pipeline tak pahunchta hai."""
    import sys
    sys.path.insert(0, "scripts")
    from fetch_metrics import _estimate_yt_retention
    est = _estimate_yt_retention(1000, 50, 5)
    assert 0.0 <= est <= 0.95     # estimate banta hai...
    # ...lekin reward.py mein ye measured NAHI maana jata (upar wale test)
    from reward import reward_from_dict
    _r, b = reward_from_dict({"views": 1000, "likes": 50,
                              "retention": est, "retention_estimated": True})
    assert b["retention_measured"] is False


# ── 12. Self-praise purge: purane fake publish-rewards mit jaate hain ──
def test_self_praise_rewards_are_purged_on_load(tmp_path: Path):
    import json
    store = tmp_path / "store.json"
    store.write_text(json.dumps({
        "arms": {
            "cults::warning::morning": {
                "n": 3, "rewards": 4.5, "sum_sq": 7.5, "plays": 2,
                "updated": "2026-01-01T00:00:00+00:00",
            },
        },
        "reward_log": [
            {"ts": "2026-01-01T00:00:00+00:00", "arm": "cults::warning::morning",
             "reason": "youtube_published", "reward": 1.0},
            {"ts": "2026-01-02T00:00:00+00:00", "arm": "cults::warning::morning",
             "reason": "metrics:abc123", "reward": 2.0},
            {"ts": "2026-01-03T00:00:00+00:00", "arm": "cults::warning::morning",
             "reason": "facebook_published", "reward": 1.5},
        ],
        "model_version": 3,
    }), encoding="utf-8")
    ml = LearningSystem(store_path=store)
    arm = ml.data["arms"]["cults::warning::morning"]
    # 3 observations - 2 fake publish rewards = 1 real (metrics) reh gaya
    assert arm["n"] == 1
    assert arm["rewards"] == pytest.approx(2.0)
    assert ml.data["self_praise_purged"] == 2
    reasons = [r["reason"] for r in ml.data["reward_log"]]
    assert reasons == ["metrics:abc123"]
