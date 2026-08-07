#!/usr/bin/env python3
"""
Cognitive Dark — ML warm-start priors (expert-seeded, NOT fake channel data).

Yeh UCB1 bandit ko zero se shuru karne ke bajaye halki "prior evidence" deta
hai taake naye channel ki pehli videos un patterns par banein jo is niche mein
documented taur par chalte hain.

IMPORTANT (honesty):
  • Hum kisi "500 winner channels" ka data nahi rakhte aur na hi gharalte hain.
    Aisa karna bandit ko gumraah karega.
  • Yeh priors do cheezon se aate hain:
      1. AAPKE apne proven winners — aapki purani videos 314/269/239 views le
         chuki hain. Un ka style: personal, relatable, ek direct claim
         ("that feeling is a lie", "if they scared you... they manipulated you").
      2. Documented Shorts/Reels retention research — pehle 2s pattern
         interrupt, red-flag lists, scam warnings zyada watch-through lete
         hain; lambi documentary/"case file" hooks shuru mein kamzor hote hain.
  • Priors ko JAAN-BOOJH kar halki rakha gaya hai (n=3..6) taake aapki asli
    videos ka real data inhein 10-15 uploads mein hi override kar de. Yeh
    bandit ko theek direction deta hai, usay qaid nahi karta.
  • Har seed ka source store mein darj hota hai ("seeded_priors").
"""

# (pillar_key, hook_style) -> (mean_reward, n_prior_samples)
# reward scale 0..~3 (dekhiye ml_engine: bonus_viral=3.0, penalty=-2).
# Higher = pehle explore karne layeq; lower = tab try karo jab baqi thak jayein.
SEED_PRIORS = {
    # ── relatable "protect yourself" + direct claim — aapke winners ka style ──
    ("coercive_control", "warning"):        (1.35, 6),
    ("coercive_control", "red_flag"):       (1.30, 6),
    ("coercive_control", "chilling_fact"):  (1.10, 5),
    ("coercive_control", "question_hook"):  (0.95, 4),
    ("coercive_control", "plot_twist"):     (0.85, 4),
    ("coercive_control", "timeline"):       (0.70, 3),
    ("coercive_control", "confession"):     (0.55, 3),
    ("coercive_control", "case_file"):      (0.45, 3),

    # ── scams: urgency/red-flag hooks search aur dono platforms par chalte hain ──
    ("con_artists", "warning"):             (1.30, 6),
    ("con_artists", "chilling_fact"):       (1.15, 5),
    ("con_artists", "red_flag"):            (1.10, 5),
    ("con_artists", "question_hook"):       (1.00, 4),
    ("con_artists", "plot_twist"):          (0.80, 3),
    ("con_artists", "case_file"):           (0.60, 3),
    ("con_artists", "confession"):          (0.55, 3),
    ("con_artists", "timeline"):            (0.50, 3),

    # ── mass psychology / feed manipulation — relatable, shareable ──
    ("mass_psychology", "chilling_fact"):   (1.20, 5),
    ("mass_psychology", "warning"):         (1.10, 5),
    ("mass_psychology", "question_hook"):   (0.95, 4),
    ("mass_psychology", "plot_twist"):      (0.80, 3),
    ("mass_psychology", "red_flag"):        (0.75, 3),
    ("mass_psychology", "timeline"):        (0.55, 3),
    ("mass_psychology", "confession"):      (0.50, 3),
    ("mass_psychology", "case_file"):       (0.40, 3),

    # ── brainwashing/mind-control: "your brain does X" curiosity hooks ──
    ("brainwashing_myths", "chilling_fact"):(1.05, 4),
    ("brainwashing_myths", "question_hook"):(0.90, 4),
    ("brainwashing_myths", "warning"):      (0.85, 3),
    ("brainwashing_myths", "plot_twist"):   (0.70, 3),
    ("brainwashing_myths", "red_flag"):     (0.60, 3),
    ("brainwashing_myths", "case_file"):    (0.45, 3),
    ("brainwashing_myths", "confession"):   (0.40, 3),
    ("brainwashing_myths", "timeline"):     (0.40, 3),

    # ── mind control history / declassified — documentary feel, thora dheema ──
    ("mind_control_history", "chilling_fact"): (0.85, 3),
    ("mind_control_history", "case_file"):     (0.70, 3),
    ("mind_control_history", "confession"):    (0.65, 3),
    ("mind_control_history", "plot_twist"):    (0.60, 3),
    ("mind_control_history", "timeline"):      (0.55, 3),
    ("mind_control_history", "warning"):       (0.55, 3),
    ("mind_control_history", "question_hook"): (0.50, 3),
    ("mind_control_history", "red_flag"):      (0.45, 3),

    # ── cults: curiosity zyada, lekin USha pe documentary wording kamzor ──
    ("cults", "chilling_fact"): (0.95, 4),
    ("cults", "warning"):       (0.90, 4),
    ("cults", "red_flag"):      (0.85, 3),
    ("cults", "plot_twist"):    (0.80, 3),
    ("cults", "question_hook"): (0.75, 3),
    ("cults", "case_file"):     (0.55, 3),
    ("cults", "confession"):    (0.55, 3),
    ("cults", "timeline"):      (0.50, 3),

    # ── interrogation — achha niche lekin thora narrow, dheemay priors ──
    ("interrogation", "question_hook"):  (0.80, 3),
    ("interrogation", "chilling_fact"):  (0.75, 3),
    ("interrogation", "red_flag"):       (0.65, 3),
    ("interrogation", "warning"):        (0.60, 3),
    ("interrogation", "case_file"):      (0.55, 3),
    ("interrogation", "plot_twist"):     (0.50, 3),
    ("interrogation", "confession"):     (0.45, 3),
    ("interrogation", "timeline"):       (0.40, 3),

    # ── stoicism/mental immunity: evergreen lekin breakout kam, sasta baseline ──
    ("stoic_defense", "chilling_fact"): (0.70, 3),
    ("stoic_defense", "question_hook"): (0.60, 3),
    ("stoic_defense", "warning"):       (0.55, 3),
    ("stoic_defense", "plot_twist"):    (0.45, 3),
    ("stoic_defense", "red_flag"):      (0.40, 3),
    ("stoic_defense", "timeline"):      (0.35, 3),
    ("stoic_defense", "confession"):    (0.30, 3),
    ("stoic_defense", "case_file"):     (0.30, 3),
}

PRIOR_VERSION = "coercion-files-2026-08-v1"
