#!/usr/bin/env python3
"""
Cognitive Dark V2 — Compatibility shims.

MoviePy 1.0.3 was built against older Pillow (uses Image.ANTIALIAS which was
removed in Pillow 10). Patch it at import time so the pinned moviepy works
with modern Pillow. Import this BEFORE importing moviepy anywhere.
"""

from PIL import Image

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS  # removed in Pillow 10 → map to LANCZOS
