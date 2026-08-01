#!/usr/bin/env python3
"""Base platform interface — all uploaders share this contract."""

import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger("platforms")


class BasePlatform(ABC):
    name = "base"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run or os.environ.get("CD_DRY_RUN") == "1"

    @abstractmethod
    def upload(self, video_path: str, thumb_path: str, pkg: dict,
               publish_at=None) -> dict:
        """Upload a video. pkg = SEO package from seo.build_platform_package."""

    # helpers
    def result(self, ok: bool, **kw) -> dict:
        r = {"platform": self.name, "ok": ok, "dry_run": self.dry_run}
        r.update(kw)
        return r

    def _log_skipped(self, reason: str) -> dict:
        logger.warning("⏭️  %s skipped: %s", self.name.upper(), reason)
        return self.result(False, skipped=True, reason=reason)
