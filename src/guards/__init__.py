"""Coercion Files — Independent Release Gate (V3.5).

Architecture (owner ke requirement ke mutabiq):

  producer (pipeline)  →  🛂 RELEASE GATE  →  upload (YT/FB/IG)

Gate ke andar:
  • IndependentObserver — RAW artifacts ki reality measure karta hai
    (video file, audio files, text, packages). Producer ke scores ko
    CHHOOTA TAK NAHI — system ke "script_quality"/"hook_score" jaisi
    self-praise gate ke andar strip ho jati hai, guards sirf asal cheez
    dekhte hain.
  • Har department ka apna independent Guard:
      script, hook, voice, caption, video,
      seo (YT/FB/IG 2026 rules), ctr, views (real performance)
  • USASupervisor — aakhri judge: kya har guard ne USA audience ke
    standard ke mutabiq INDEPENDENTLY pass kiya? Koi guard "unknown"
    hua (measure na kar saka) to fail-CLOSED — video gate se nahi guzarti.

  Video tabhi upload hoti hai jab SAB guards pass karein aur supervisor
  final RELEASE de. Warna repair hints ke saath video HELD rehti hai.

Sab verdicts data/gate_report.json + data/gate_report.md mein likhe jate
hain — poori audit trail, har guard ka evidence ke saath.
"""
