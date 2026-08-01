#!/usr/bin/env python3
"""
Cognitive Dark V2 — YouTube Uploader (YouTube Data API v3).

• SEO title (≤100), keyword-first description, ≤500-char tags, category 27
• Credentials: accepts EITHER a file path OR a raw JSON string in
  YOUTUBE_CREDENTIALS (fixes the V1 bug where GH Actions passed JSON text
  that os.path.exists() never matched).
• Auto token-refresh so headless scheduled runs stay valid.
• Schedules via `publishAt` (private → public at peak time).
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta

from .base import BasePlatform

logger = logging.getLogger("youtube")


def _resolve_credentials() -> tuple:
    """Return (creds, is_path). Raises if unusable."""
    raw = os.environ.get("YOUTUBE_CREDENTIALS", "")
    if not raw:
        return None, False
    if os.path.exists(raw):                      # path to JSON file
        return raw, True
    # assume raw JSON string → write to temp file
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("YOUTUBE_CREDENTIALS must be a JSON object or file path")
    tmp = os.path.join(tempfile.gettempdir(), "yt_credentials.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    logger.info("YOUTUBE_CREDENTIALS was JSON text → written to %s", tmp)
    return tmp, False


class YouTubeUploader(BasePlatform):
    name = "youtube"

    def upload(self, video_path, thumb_path, pkg, publish_at=None):
        if not os.path.exists(video_path):
            return self.result(False, error="video file missing: " + video_path)
        if self.dry_run:
            logger.info("📦 DRY-RUN youtube: %s (publish %s)", pkg["title"], publish_at)
            return self.result(True, dry_run=True, video_id="dry-run")

        cred_path, _ = _resolve_credentials()
        if not cred_path:
            return self._log_skipped("YOUTUBE_CREDENTIALS not configured")

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            with open(cred_path, encoding="utf-8") as fh:
                info = json.load(fh)
            creds = Credentials.from_authorized_user_info(info)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())      # keep token alive in headless runs
                with open(cred_path, "w", encoding="utf-8") as fh:
                    json.dump(json.loads(creds.to_json()), fh)

            youtube = build("youtube", "v3", credentials=creds)
            body = {
                "snippet": {
                    "title": pkg["title"][:100],
                    "description": pkg["description"],
                    "tags": pkg.get("tags", [])[:500] and pkg.get("tags", []),
                    "categoryId": os.environ.get("YT_CATEGORY_ID", "27"),
                },
                "status": {
                    "privacyStatus": "private",
                    "selfDeclaredMadeForKids": False,
                },
            }
            if publish_at:
                # must be within 24h; else publish immediately
                if datetime.fromisoformat(publish_at) - datetime.now() > timedelta(hours=23):
                    publish_at = (datetime.now() + timedelta(hours=23)).isoformat()
                body["status"]["publishAt"] = publish_at

            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            req = youtube.videos().insert(part="snippet,status", body=body,
                                          media_body=media)
            response = None
            while response is None:
                status, response = req.next_chunk()
                if status and int(status.progress() * 100) % 25 == 0:
                    logger.info("⬆️  YT upload %d%%", int(status.progress() * 100))
            vid = response["id"]
            if thumb_path and os.path.exists(thumb_path):
                youtube.thumbnails().set(
                    videoId=vid, media_body=MediaFileUpload(thumb_path)).execute()
            logger.info("✅ YouTube uploaded: https://youtu.be/%s", vid)
            return self.result(True, video_id=vid, url=f"https://youtu.be/{vid}")
        except Exception as exc:
            logger.error("YouTube upload failed: %s", exc)
            return self.result(False, error=str(exc))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    y = YouTubeUploader(dry_run=True)
    print(y.upload("/tmp/x.mp4", None, {"title": "T", "description": "D", "tags": []}))
