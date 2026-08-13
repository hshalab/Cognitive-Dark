#!/usr/bin/env python3
"""Guard verdicts + base contract.

Har guard khud apna department measure karta hai aur GuardVerdict return
karta hai. Status:
  PASS    — department ka reality-check pass (evidence ke saath)
  WARN    — pass, magar risk noted
  FAIL    — block (department fail)
  UNKNOWN — measure hi nahi ho saka → FAIL-CLOSED (block) jab tak guard
            explicitly allow_unknown na ho

GuardVerdict mein `evidence` khali hona = guard ne asal mein kuch measure
nahi kiya → supervisor isay independence violation maan kar HOLD karta hai.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("guards")


@dataclass
class GuardVerdict:
    guard: str
    status: str                      # PASS | WARN | FAIL | UNKNOWN
    reason: str = ""
    evidence: dict = field(default_factory=dict)
    fix: str = ""
    independent: bool = True

    @property
    def ok(self) -> bool:
        return self.status == "PASS"

    @property
    def blocking(self) -> bool:
        return self.status in ("FAIL", "UNKNOWN")

    def to_dict(self) -> dict:
        return {
            "guard": self.guard,
            "status": self.status,
            "reason": self.reason,
            "evidence": self.evidence,
            "fix": self.fix,
            "independent": self.independent,
        }


class BaseGuard:
    """Har independent guard ka common contract."""

    name = "base"
    required = True
    allow_unknown = False   # UNKNOWN fail-closed hota hai by default

    def __init__(self, observer=None):
        from guards.observer import IndependentObserver
        self.observer = observer or IndependentObserver()

    def check(self, payload: dict) -> GuardVerdict:
        raise NotImplementedError

    # helpers
    def _v(self, status: str, reason: str = "", evidence: dict = None,
           fix: str = "") -> GuardVerdict:
        return GuardVerdict(guard=self.name, status=status, reason=reason,
                            evidence=evidence or {}, fix=fix)
