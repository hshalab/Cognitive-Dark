#!/usr/bin/env python3
"""Generate the 7 launch-week scripts as both Markdown (human) and JSON (pipeline)."""

import json
from pathlib import Path

OUT = Path(__file__).parent

CTA = "Follow Coercion Files for the psychology they don't teach you in school."

# Each scene caption = one punchy sentence block (~20-35 words → 8-14s spoken).
SCRIPTS = [
    {
        "day": 1,
        "pillar": "cults",
        "pillar_name": "Cult Psychology Decoded",
        "hook_style": "knowledge_gap",
        "title": "Why Smart People Join Dangerous Cults",
        "hook": "Why smart people join cults.",
        "visuals_mood": "dark",
        "search_term": "how cults brainwash",
        "tags": ["cult psychology", "brainwashing", "how cults work", "social psychology",
                 "manipulation tactics", "coercive control", "psychology facts", "mind control"],
        "key_points": "• Why intelligence doesn't protect you\n• The 4-step recruitment pattern\n• How to spot it early",
        "scenes": [
            {"caption": "Doctors, lawyers, teachers — smart, educated people join cults every year. "
                        "And they don't join because they're stupid.",
             "visual": "crowd of people city night"},
            {"caption": "They join because they're in pain. A breakup, a death, a lost job — "
                        "the exact moment their guard is down.",
             "visual": "person alone window rain"},
            {"caption": "Step one: love bombing. Strangers flood them with acceptance, purpose, "
                        "and a family they never had.",
             "visual": "hands together circle candle"},
            {"caption": "Step two: isolation. Old friends become 'toxic'. Family becomes "
                        "'the enemy'. Soon there is only the group.",
             "visual": "lone figure corridor shadow"},
            {"caption": "Step three: small commitments. A weekend, then money, then a confession. "
                        "Each yes makes the next one easier.",
             "visual": "contract signing dark desk"},
            {"caption": "Step four: black-and-white thinking. The leader is always right. "
                        "Doubt becomes betrayal. That's how free will quietly disappears."},
            {"caption": "Intelligence doesn't protect you. Awareness does. If a new group is "
                        "moving too fast and pulling you from family — slow down. " + CTA},
        ],
    },
    {
        "day": 2,
        "pillar": "con_artists",
        "pillar_name": "Con Artists & Scam Psychology",
        "hook_style": "pattern_interrupt",
        "title": "The Sentence Every Con Artist Uses",
        "hook": "Every con artist uses this sentence.",
        "visuals_mood": "intense",
        "search_term": "spot a scammer",
        "tags": ["scam psychology", "con artist", "social engineering", "romance scam",
                 "manipulation", "psychology facts", "fraud prevention"],
        "key_points": "• The one line that creates urgency\n• Why urgency kills your judgment\n• The 3-second rule to stay safe",
        "scenes": [
            {"caption": "There is one sentence behind almost every con, every scam, every "
                        "fraud you've ever heard of. It has four words.",
             "visual": "phone screen dark message"},
            {"caption": "\"You have to decide now.\" That's it. Pressure plus a deadline. "
                        "The moment you feel rushed, your brain stops thinking.",
             "visual": "clock ticking close up dark"},
            {"caption": "Scammers can't let you pause, because a calm mind asks questions. "
                        "A rushed mind just obeys.",
             "visual": "anxious person phone night"},
            {"caption": "So they stack urgency. The offer expires. The warrant is issued. "
                        "The account closes in ten minutes.",
             "visual": "red alert warning screen"},
            {"caption": "Notice: legitimate institutions — your bank, the government, real "
                        "companies — never demand secrecy or instant payment.",
             "visual": "bank building night"},
            {"caption": "Here's your defense. The second anyone pressures you to act now, "
                        "you stop. You hang up. You wait a full day.",
             "visual": "hand pressing stop button"},
            {"caption": "Tell a friend before you send a dollar. Real opportunities survive "
                        "one night of sleep. Scams don't. " + CTA},
        ],
    },
    {
        "day": 3,
        "pillar": "coercive_control",
        "pillar_name": "Coercive Control Awareness",
        "hook_style": "fear_based",
        "title": "Love Bombing Is Not Love",
        "hook": "This isn't love. It's a tactic.",
        "visuals_mood": "chilling",
        "search_term": "love bombing signs",
        "tags": ["love bombing", "narcissist", "coercive control", "red flags",
                 "toxic relationships", "manipulation", "psychology facts"],
        "key_points": "• What love bombing actually is\n• The pace that should scare you\n• The one boundary that exposes it",
        "scenes": [
            {"caption": "On the second date they said you were their soulmate. By the first "
                        "week, future, kids, forever. It felt like a movie. It isn't.",
             "visual": "romantic dinner candle dark"},
            {"caption": "It's called love bombing: overwhelming affection, gifts, and "
                        "promises used to rush past your judgment.",
             "visual": "flood of messages phone"},
            {"caption": "Real love grows with time. Love bombing is fast because fast "
                        "doesn't give you space to see the pattern.",
             "visual": "two silhouettes sunset sped"},
            {"caption": "Then comes the switch. The same intensity turns to anger if you "
                        "want space, if you see friends, if you say no.",
             "visual": "argument shadow silhouette"},
            {"caption": "The affection was never about you. It was a hook. Once you're "
                        "invested, the reward gets taken away to control you.",
             "visual": "fishing hook dark water"},
            {"caption": "Healthy people respect pace. They can wait. They don't need a "
                        "lifetime commitment on day three.",
             "visual": "calm person breathing window"},
            {"caption": "So set one boundary: tell them you want to slow down. A safe "
                        "person stays calm. A controller gets angry. Watch that reaction. " + CTA},
        ],
    },
    {
        "day": 4,
        "pillar": "cults",
        "pillar_name": "Cult Psychology Decoded",
        "hook_style": "question_hook",
        "title": "The 3 Questions Cults Refuse to Answer",
        "hook": "Cults hate these 3 questions.",
        "visuals_mood": "mysterious",
        "search_term": "signs of a cult",
        "tags": ["cults", "cult signs", "manipulation", "coercive control", "mind control",
                 "critical thinking", "psychology facts"],
        "key_points": "• 3 questions that test any group\n• Why anger is the real answer\n• The difference between community and control",
        "scenes": [
            {"caption": "There are three questions that separate a healthy community from "
                        "a controlling one. Ask them, and watch how the leader reacts.",
             "visual": "speaker on stage dark"},
            {"caption": "Question one: \"What exactly would make you ask me to leave?\" "
                        "Healthy groups have clear rules. Cults get defensive.",
             "visual": "person raising hand crowd"},
            {"caption": "Question two: \"Can I speak to someone who left and was happy?\" "
                        "A real community says yes. A cult attacks their character.",
             "visual": "two people talking doorway"},
            {"caption": "Question three: \"What happens if I disagree with you in public?\" "
                        "Watch closely. Anger is the answer they didn't want to say.",
             "visual": "tense meeting table"},
            {"caption": "Cults survive on uncertainty. The rules are never written, the "
                        "goalposts always move, so you keep guessing to stay safe.",
             "visual": "foggy path forest"},
            {"caption": "Healthy groups want you to think for yourself. Controlling groups "
                        "want you to stop thinking and just obey.",
             "visual": "open book candle light"},
            {"caption": "Ask the questions. If a group punishes you for asking, that isn't "
                        "family. That's evidence. " + CTA},
        ],
    },
    {
        "day": 5,
        "pillar": "coercive_control",
        "pillar_name": "Coercive Control Awareness",
        "hook_style": "red_flag_checklist",
        "title": "If They Say You're Overreacting, Watch This",
        "hook": "\"You're overreacting\" is a trap.",
        "visuals_mood": "intense",
        "search_term": "gaslighting examples",
        "tags": ["gaslighting", "emotional abuse", "manipulation", "coercive control",
                 "narcissist", "psychology facts", "red flags"],
        "key_points": "• Why 'overreacting' is a control move\n• The real name for it: gaslighting\n• A sentence that ends the game",
        "scenes": [
            {"caption": "You saw the flirty text. You heard the lie. And when you brought "
                        "it up, they looked at you and said, \"You're overreacting.\"",
             "visual": "argument couple silhouette"},
            {"caption": "In that moment two things happen. You start doubting yourself, "
                        "and they walk away unchallenged. That's the point.",
             "visual": "confused person mirror"},
            {"caption": "This is gaslighting: making you distrust your own memory and "
                        "perception so that only their version of reality counts.",
             "visual": "distorted mirror reflection"},
            {"caption": "A person who cares about you asks, \"Why do you feel that way?\" "
                        "A controller tells you how you're allowed to feel.",
             "visual": "two people tense couch"},
            {"caption": "Notice the pattern. It's never the issue. It's always your tone, "
                        "your memory, your reaction. The target keeps moving.",
             "visual": "spinning compass dark"},
            {"caption": "Your feelings are evidence about you, not proof you're crazy. "
                        "Repeated denial of what you saw is a documented tactic.",
             "visual": "notebook evidence desk"},
            {"caption": "Try one line: \"I'm not asking if I'm overreacting. I'm telling "
                        "you how this affected me.\" Then watch what they do. " + CTA},
        ],
    },
    {
        "day": 6,
        "pillar": "con_artists",
        "pillar_name": "Con Artists & Scam Psychology",
        "hook_style": "plot_twist",
        "title": "How a Romance Scam Starts (The First Message)",
        "hook": "This is how a romance scam starts.",
        "visuals_mood": "chilling",
        "search_term": "romance scam signs",
        "tags": ["romance scam", "catfish", "online dating", "scam psychology",
                 "social engineering", "psychology facts", "fraud"],
        "key_points": "• The exact first-message pattern\n• Why they move off the app fast\n• The money question that proves it",
        "scenes": [
            {"caption": "It starts with a message. Polite, flattering, almost too perfect. "
                        "They seem successful, kind, and genuinely interested in you.",
             "visual": "dating app phone dark"},
            {"caption": "Within days they're saying things you've always wanted to hear. "
                        "It feels like finally being understood. That feeling is engineered.",
             "visual": "text messages floating phone"},
            {"caption": "Then come the three red flags. First, they can never video chat. "
                        "Bad signal, broken camera, always an emergency.",
             "visual": "video call failed screen"},
            {"caption": "Second, they push you off the app to WhatsApp or text. Away from "
                        "the platform's scam filters and any record that can be reported.",
             "visual": "chat moving between apps"},
            {"caption": "Third comes the crisis. Stuck overseas. Customs hold. Emergency "
                        "surgery. They need money, gift cards, or just a small favor.",
             "visual": "airport night blurred"},
            {"caption": "Here's the test: ask for a live video call today. A real person "
                        "says yes. A scammer changes the subject or gets angry.",
             "visual": "video camera icon red"},
            {"caption": "Never send money to someone you haven't met in person. Love doesn't "
                        "ask for gift cards. " + CTA},
        ],
    },
    {
        "day": 7,
        "pillar": "cults",
        "pillar_name": "Cult Psychology Decoded",
        "hook_style": "warning",
        "title": "How Cults Isolate You From Everyone You Love",
        "hook": "This is how cults isolate you.",
        "visuals_mood": "dark",
        "search_term": "cult isolation tactics",
        "tags": ["cults", "isolation", "coercive control", "manipulation", "brainwashing",
                 "psychology facts", "mind control"],
        "key_points": "• Why isolation always comes first\n• The slow language of separation\n• How to keep your support network",
        "scenes": [
            {"caption": "No cult asks you to abandon your family on day one. That would be "
                        "too obvious. Isolation is done slowly, one sentence at a time.",
             "visual": "family dinner tense"},
            {"caption": "First it's sympathy. \"Your mom is so controlling.\" \"Your friend "
                        "is jealous of you.\" It sounds like they're on your side.",
             "visual": "two people whispering couch"},
            {"caption": "Then it's suspicion. \"Why do they always criticize me?\" A wedge "
                        "forms. You start defending the group, not your family.",
             "visual": "split screen two faces"},
            {"caption": "Then distance. You skip calls, cancel dinners, lie about where you "
                        "were. Every old relationship becomes a source of guilt.",
             "visual": "missed calls phone screen"},
            {"caption": "Soon the group is your entire world — your job, your home, your "
                        "love. No one is left to say, \"This isn't normal.\"",
             "visual": "empty chair dark room"},
            {"caption": "That isolation is the cage. A person alone will believe almost "
                        "anything, because there's no one left to challenge it.",
             "visual": "person behind window rain"},
            {"caption": "Protect one thing: one outside friendship they don't control. "
                        "Keep that door open. That door is how people get out. " + CTA},
        ],
    },
]


def build_description(script):
    return (
        f"{script['title']}. {script['hook']}\n"
        f"{script['pillar_name']}: how coercion really works, why it works on you, "
        f"and exactly how to protect yourself.\n\n"
        f"WHAT YOU'LL LEARN:\n{script['key_points']}\n\n"
        f"For educational purposes only — learn to recognize and protect yourself. "
        f"Not a substitute for professional advice.\n\n"
        f"#psychology #truecrime #{script['pillar']}"
    )


def to_pipeline_script(s):
    scenes = [
        {"caption": sc["caption"],
         "caption_roman": sc["caption"],
         "visual": sc.get("visual", "dark city night cinematic"),
         "emotion": sc.get("emotion", s["visuals_mood"])}
        for sc in s["scenes"]
    ]
    return {
        "title": s["title"],
        "hook": s["hook"],
        "scenes": scenes,
        "tags": s["tags"],
        "description": build_description(s),
        "key_points": s["key_points"],
        "pillar": s["pillar"],
        "pillar_name": s["pillar_name"],
        "hook_style": s["hook_style"],
        "source": "manual_launch_week",
    }


def word_count(s):
    return sum(len(sc["caption"].split()) for sc in s["scenes"])


def main():
    index = ["# 🎬 Coercion Files — Launch Week (Days 1-7)",
             "_Ready-to-record scripts · USA English · 40-58s Shorts_", "",
             "| Day | Pillar | Title | Hook | Words |",
             "|---|---|---|---|---|"]
    for s in SCRIPTS:
        p = to_pipeline_script(s)
        slug = f"day{s['day']:02d}_{s['pillar']}"
        (OUT / f"{slug}.json").write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")
        index.append(f"| {s['day']} | {s['pillar_name']} | {s['title']} | \"{s['hook']}\" | {word_count(s)} |")

    index += ["", "## How to use",
              "- Each `.json` file is pipeline-compatible (same shape as `script_generator.py` output).",
              "- Feed it to the pipeline with `--pillar` / manual load, or read the Markdown to record by hand.",
              "- Captions are spoken English; `visual` is the stock-video search query per scene.",
              "", "## Per-video scripts", ""]

    for s in SCRIPTS:
        p = to_pipeline_script(s)
        index.append(f"---\n\n### Day {s['day']} — {s['title']}")
        index.append(f"**Pillar:** {s['pillar_name']}  ")
        index.append(f"**Hook (first 2s):** \"{s['hook']}\"  ")
        index.append(f"**YT search keyword:** {s['search_term']}  ")
        index.append(f"**Word count:** ~{word_count(s)} words\n")
        index.append("**Scene-by-scene (caption → visual query):**\n")
        for i, sc in enumerate(p["scenes"], 1):
            index.append(f"{i}. \"{sc['caption']}\"")
            index.append(f"   _visual: `{sc['visual']}` · emotion: {sc['emotion']}_\n")
        index.append(f"**Tags:** {', '.join(s['tags'])}\n")
        index.append(f"**Description:**\n```\n{p['description']}\n```\n")
        index.append(f"**Key points:**\n```\n{s['key_points']}\n```\n")

    (OUT / "LAUNCH_WEEK_SCRIPTS.md").write_text("\n".join(index), encoding="utf-8")
    print(f"Wrote {len(SCRIPTS)} scripts to {OUT}")
    for s in SCRIPTS:
        print(f"  Day {s['day']}: {word_count(s)} words — {s['title']}")


if __name__ == "__main__":
    main()
