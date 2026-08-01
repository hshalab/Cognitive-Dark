#!/usr/bin/env python3
"""
Cognitive Dark V2 — Facebook Uploader (Graph API).

• Primary: POST /{page-id}/video_reels (Reels — 9:16, ≤90s, monetization-
  eligible for in-stream ads). Falls back to /videos if FB_REELS_ENDPOINT=off.
• Multipart file upload (works from ephemeral runners — no public URL needed).
• Caption is platform-native (seo.py) → distinct from YT/IG copy.
"""

import logging
import os

import requests

from .base import BasePlatform

logger = logging.getLogger("facebook")

GRAPH = "https://graph.facebook.com"
API_VERSION = "v25.0"


class FacebookUploader(BasePlatform):
    name = "facebook"

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

        use_reels = os.environ.get("FB_REELS_ENDPOINT", "on").lower() != "off"
        endpoint = "video_reels" if use_reels else "videos"
        url = f"{GRAPH}/{API_VERSION}/{page_id}/{endpoint}"

        data = {
            "access_token": token,
            "title": pkg["title"][:150],
            "description": pkg["description"][:6300],
        }
        if publish_at:
            data["published"] = "false"
            data["scheduled_publish_time"] = str(int(
                publish_at.timestamp())) if hasattr(publish_at, "timestamp") else str(publish_at)
        files = {"source": (os.path.basename(video_path), open(video_path, "rb"),
                            "video/mp4")}
        try:
            resp = requests.post(url, data=data, files=files, timeout=600)
            resp.raise_for_status()
            out = resp.json()
            if "id" not in out:
                raise RuntimeError(f"FB API returned: {out}")
            logger.info("✅ Facebook post: https://facebook.com/%s", out["id"])
            return self.result(True, post_id=out["id"],
                               url=f"https://facebook.com/{out['id']}")
        except Exception as exc:
            logger.error("Facebook upload failed: %s", exc)
            return self.result(False, error=str(exc))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    f = FacebookUploader(dry_run=True)
    print(f.upload("/tmp/x.mp4", None, {"title": "T", "description": "D"}))
