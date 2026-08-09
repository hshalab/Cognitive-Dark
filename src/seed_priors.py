#!/usr/bin/env python3
"""
Cognitive Dark — ML warm-start priors (Forensic Social Engineering & Human-Feel Engine).

Warm-starts the Bayesian Thompson Bandit and UCB1 algorithm with high-yield
USA market intelligence priors.

PRIOR SOURCES:
  1. Forensic Social Engineering & Financial Deception ($14-$28 RPM) — Highest Priority
  2. Workplace / Corporate Power Dynamics & Quiet Firing ($16-$32 RPM) — High B2B/Career RPM
  3. Declassified FBI Behavioral Transcripts & 3s Interrogation Silence ($10-$16 RPM) — 75%+ Retention
  4. Coercive Control & Narcissistic Red Flags — Viral Saves & Shares
  5. High-Control Group & Cult Mechanics — Bingeable Curiosity
"""

# (pillar_key, hook_style) -> (mean_reward, n_prior_samples)
# Reward scale 0..~3. Higher = prioritized by Thompson sampling & UCB.
SEED_PRIORS = {
    # ── #1 FORENSIC SCAMS & FINANCIAL SOCIAL ENGINEERING (Highest RPM $14-$28) ──
    ("con_artists", "warning"):             (1.50, 7),
    ("con_artists", "red_flag"):            (1.45, 7),
    ("con_artists", "chilling_fact"):       (1.40, 6),
    ("con_artists", "case_file"):           (1.35, 6),
    ("con_artists", "question_hook"):       (1.25, 5),
    ("con_artists", "plot_twist"):          (1.10, 4),
    ("con_artists", "confession"):          (0.95, 4),
    ("con_artists", "timeline"):            (0.85, 3),

    # ── #2 CORPORATE POWER DYNAMICS & WORKPLACE RETENTION (Highest RPM $16-$32) ──
    ("coercive_control", "warning"):        (1.48, 7),
    ("coercive_control", "red_flag"):       (1.42, 7),
    ("coercive_control", "chilling_fact"):  (1.35, 6),
    ("coercive_control", "question_hook"):  (1.20, 5),
    ("coercive_control", "plot_twist"):     (1.10, 4),
    ("coercive_control", "case_file"):      (0.95, 4),
    ("coercive_control", "timeline"):       (0.85, 3),
    ("coercive_control", "confession"):     (0.75, 3),

    # ── #3 FBI INTERROGATION & STATEMENT ANALYSIS (High Retention 75%+) ──
    ("interrogation", "chilling_fact"):     (1.38, 6),
    ("interrogation", "question_hook"):     (1.30, 6),
    ("interrogation", "warning"):           (1.25, 5),
    ("interrogation", "red_flag"):          (1.20, 5),
    ("interrogation", "case_file"):         (1.15, 5),
    ("interrogation", "plot_twist"):        (1.00, 4),
    ("interrogation", "confession"):        (0.90, 4),
    ("interrogation", "timeline"):          (0.70, 3),

    # ── #4 CULTS & HIGH-CONTROL GROUPS (Documentary Bingeability) ──
    ("cults", "chilling_fact"):             (1.30, 6),
    ("cults", "warning"):                   (1.25, 5),
    ("cults", "red_flag"):                  (1.20, 5),
    ("cults", "case_file"):                 (1.15, 5),
    ("cults", "plot_twist"):                (1.05, 4),
    ("cults", "question_hook"):             (0.95, 4),
    ("cults", "confession"):                (0.85, 3),
    ("cults", "timeline"):                  (0.70, 3),

    # ── #5 DECLASSIFIED MIND CONTROL & BEHAVIORAL HISTORY ──
    ("mind_control_history", "chilling_fact"): (1.15, 5),
    ("mind_control_history", "case_file"):     (1.10, 5),
    ("mind_control_history", "confession"):    (1.00, 4),
    ("mind_control_history", "plot_twist"):    (0.90, 4),
    ("mind_control_history", "warning"):       (0.85, 3),
    ("mind_control_history", "question_hook"): (0.80, 3),
    ("mind_control_history", "timeline"):      (0.70, 3),
    ("mind_control_history", "red_flag"):      (0.65, 3),

    # ── #6 MASS PSYCHOLOGY & ALGORITHM FEED TRAPS ──
    ("mass_psychology", "chilling_fact"):   (1.25, 5),
    ("mass_psychology", "warning"):         (1.20, 5),
    ("mass_psychology", "question_hook"):   (1.10, 4),
    ("mass_psychology", "red_flag"):        (1.00, 4),
    ("mass_psychology", "plot_twist"):      (0.90, 4),
    ("mass_psychology", "case_file"):       (0.80, 3),
    ("mass_psychology", "timeline"):        (0.65, 3),
    ("mass_psychology", "confession"):      (0.60, 3),

    # ── #7 BRAINWASHING MYTHS & COGNITIVE BIASES ──
    ("brainwashing_myths", "chilling_fact"):(1.15, 5),
    ("brainwashing_myths", "question_hook"):(1.05, 4),
    ("brainwashing_myths", "warning"):      (1.00, 4),
    ("brainwashing_myths", "plot_twist"):   (0.85, 3),
    ("brainwashing_myths", "red_flag"):     (0.80, 3),
    ("brainwashing_myths", "case_file"):    (0.75, 3),
    ("brainwashing_myths", "confession"):   (0.60, 3),
    ("brainwashing_myths", "timeline"):     (0.55, 3),

    # ── #8 STOIC DEFENSE & MENTAL SHIELD ──
    ("stoic_defense", "chilling_fact"):     (1.05, 4),
    ("stoic_defense", "warning"):           (1.00, 4),
    ("stoic_defense", "question_hook"):     (0.90, 4),
    ("stoic_defense", "plot_twist"):        (0.80, 3),
    ("stoic_defense", "red_flag"):          (0.70, 3),
    ("stoic_defense", "case_file"):         (0.60, 3),
    ("stoic_defense", "timeline"):          (0.50, 3),
    ("stoic_defense", "confession"):        (0.45, 3),
}

PRIOR_VERSION = "forensic-coercion-2026-v2"
