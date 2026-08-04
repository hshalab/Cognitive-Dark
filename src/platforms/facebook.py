#!/usr/bin/env python3
"""
Cognitive Dark V2.1 — Facebook Uploader (Graph API).

• Primary: POST /{page-id}/video_reels (Reels — 9:16, ≤90s, monetization-
  eligible for in-stream ads). Set FB_REELS_ENDPOINT=videos to fall back.
  If the Reels endpoint rejects the call, V2.1 auto-retries via /videos so
  the post still goes out.
• Multipart file upload (works from ephemeral runners — no public URL needed).
• Caption is platform-native (seo.py) → distinct from YT/IG copy.

V2.1 fixes:
  • scheduled_publish_time now sends a Unix epoch (V2 sent an ISO string →
    scheduled posts were rejected by the API).
  • FB_REELS_ENDPOINT is actually honored (V2 hardcoded /videos).
  • File handle closed via context manager.
"""

import logging
import os
from datetime import datetime, timezone

import requests

from .base import BasePlatform

logger = logging.getLogger("facebook")

GRAPH = "https://graph.facebook.com"
API_VERSION = "v25.0"


def _to_epoch(publish_at) -> str:
    """Normalize str/datetime publish_at → Unix epoch seconds string."""
    if publish_at is None:
        return ""
    pa = publish_at
    if isinstance(pa, str):
        try:
            pa = datetime.fromisoformat(pa)
        except ValueError:
            return ""
    if pa.tzinfo is None:
        pa = pa.replace(tzinfo=timezone.utc)
    return str(int(pa.timestamp()))


class FacebookUploader(BasePlatform):
    name = "facebook"

    def _post(self, url: str, data: dict, video_path: str) -> dict:
        with open(video_path, "rb") as fh:
            files = {"source": (os.path.basename(video_path), fh, "video/mp4")}
            resp = requests.post(url, data=data, files=files, timeout=600)
        resp.raise_for_status()
        return resp.json()

    def upload(self, video_path, thumb_path, pkg, publish_at=None):
        token = os.environ.get("FB_ACCESS_TOKEN", "")
        page_id = os.environ.get("FB_PAGE_ID", "")
        if not token or not page_id:
            return self._log_skipped("FB_ACCESS_TOKEN / FB_PAGE_ID not configured")
        if not os.path.exists(video_path):
            return self.result(False, error="video file missing")

        if self.dry_run:
            logger.info("📦 DRY-RUN facebook: %s", pkg["title"])
            return self.result(True, dry_run=True, video_id="dry-run")

        # V2.1: honor FB_REELS_ENDPOINT (default Reels — monetization eligible)
        endpoint = os.environ.get("FB_REELS_ENDPOINT", "video_reels").strip().lower()
        if endpoint in ("off", "video", "videos"):
            endpoint = "videos"

        data = {
            "access_token": token,
            "title": pkg["title"][:150],
            "description": pkg["description"][:6300],
        }
        epoch = _to_epoch(publish_at)
        if epoch:
            data["published"] = "false"
            data["scheduled_publish_time"] = epoch
        if endpoint == "videos":
            data.setdefault("published", data.get("published", "true"))

        url = f"{GRAPH}/{API_VERSION}/{page_id}/{endpoint}"
        try:
            out = self._post(url, data, video_path)
        except Exception as exc:
            # V2.1: Reels endpoint can reject some pages/tokens → fall back to /videos
            if endpoint == "video_reels":
                logger.warning("FB video_reels failed (%s) → retrying /videos", exc)
                try:
                    url = f"{GRAPH}/{API_VERSION}/{page_id}/videos"
                    out = self._post(url, data, video_path)
                except Exception as exc2:
                    logger.error("Facebook upload failed: %s", exc2)
                    return self.result(False, error=str(exc2))
            else:
                logger.error("Facebook upload failed: %s", exc)
                return self.result(False, error=str(exc))

        if "id" not in out:
            return self.result(False, error=f"FB API returned: {out}")
        logger.info("✅ Facebook post: https://facebook.com/%s", out["id"])
        return self.result(True, post_id=out["id"],
                           url=f"https://facebook.com/{out['id']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    f = FacebookUploader(dry_run=True)
    print(f.upload("/tmp/x.mp4", None, {"title": "T", "description": "D"}))
