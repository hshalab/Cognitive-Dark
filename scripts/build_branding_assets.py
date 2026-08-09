#!/usr/bin/env python3
"""
Coercion Files — Master Brand Asset Builder.

Generates pixel-perfect branding graphics:
  1. Profile Picture / Avatar (1024x1024) — YouTube / Facebook / Instagram
  2. YouTube Channel Banner (2560x1440) — Safe-zone aligned (1546x423)
  3. Facebook Page Cover (1640x624) — High-definition header
  4. Video Watermark / Corner Seal (400x400 transparent PNG)
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "assets" / "branding"
BRAND_DIR.mkdir(parents=True, exist_ok=True)

FONTS = [
    ROOT / "assets" / "fonts" / "Anton-Regular.ttf",
    ROOT / "assets" / "fonts" / "BebasNeue-Regular.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
]


def load_font(size: int, font_idx: int = 0):
    candidates = FONTS[font_idx:] + FONTS[:font_idx]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


# ─────────────────────────────────────────────────────────────
# 1. Profile Picture / Logo (1024x1024)
# ─────────────────────────────────────────────────────────────
def build_profile_avatar():
    size = (1024, 1024)
    raw_logo_path = BRAND_DIR / "coercion_files_logo_raw.png"
    
    if raw_logo_path.exists():
        base = Image.open(raw_logo_path).convert("RGBA").resize(size, Image.LANCZOS)
    else:
        base = Image.new("RGBA", size, (10, 10, 14, 255))
        draw = ImageDraw.Draw(base)
        draw.ellipse([100, 100, 924, 924], fill=(18, 18, 24, 255), outline=(180, 20, 20, 255), width=8)

    # Enhance contrast and add subtle dark vignette
    enhancer = ImageEnhance.Contrast(base)
    base = enhancer.enhance(1.15)
    
    # Overlay outer luxury circular border
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    
    # Subtle outer ring
    d.ellipse([24, 24, 1000, 1000], outline=(190, 25, 25, 200), width=6)
    d.ellipse([36, 36, 988, 988], outline=(50, 50, 60, 150), width=2)
    
    # Bottom Badge Text "COERCION FILES"
    font_bold = load_font(72, 0)
    text = "COERCION FILES"
    tw = d.textlength(text, font=font_bold)
    
    badge_w = tw + 80
    badge_h = 96
    bx = (1024 - badge_w) / 2
    by = 840
    
    # Badge backdrop
    d.rounded_rectangle([bx, by, bx + badge_w, by + badge_h], radius=18, fill=(10, 10, 14, 235), outline=(190, 25, 25, 255), width=3)
    d.text(((1024 - tw) / 2, by + 12), text, font=font_bold, fill=(255, 255, 255, 255))

    final = Image.alpha_composite(base, overlay).convert("RGB")
    out_path = BRAND_DIR / "coercion_files_avatar_1024x1024.png"
    final.save(out_path, quality=95)
    print(f"✅ Created Profile Picture: {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────
# 2. YouTube Channel Banner (2560x1440)
# ─────────────────────────────────────────────────────────────
def build_youtube_banner():
    width, height = 2560, 1440
    bg_path = BRAND_DIR / "banner_bg.png"
    
    if bg_path.exists():
        bg = Image.open(bg_path).convert("RGBA").resize((width, height), Image.LANCZOS)
    else:
        bg = Image.new("RGBA", (width, height), (12, 12, 16, 255))

    # Darken for safe-zone readability
    dim = Image.new("RGBA", (width, height), (0, 0, 0, 160))
    bg = Image.alpha_composite(bg, dim)
    
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Safe zone is Y: 508 to 931 (height 423) in center
    cy = 720
    
    # Header classified badge
    badge_font = load_font(42, 1)
    tag_font = load_font(46, 1)
    title_font = load_font(148, 0)
    sub_font = load_font(52, 1)
    
    badge_text = "CLASSIFIED // FORENSIC CASE ARCHIVE"
    bw = draw.textlength(badge_text, font=badge_font)
    draw.rounded_rectangle([(width - bw) / 2 - 30, cy - 180, (width + bw) / 2 + 30, cy - 130],
                           radius=8, fill=(170, 20, 20, 230))
    draw.text(((width - bw) / 2, cy - 176), badge_text, font=badge_font, fill=(255, 255, 255, 255))

    # Main Title
    title = "COERCION FILES"
    tw = draw.textlength(title, font=title_font)
    # Drop shadow
    draw.text(((width - tw) / 2 + 6, cy - 100 + 6), title, font=title_font, fill=(0, 0, 0, 240))
    draw.text(((width - tw) / 2, cy - 100), title, font=title_font, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(180, 20, 20))

    # Subtitle
    sub = "THE FORENSIC PSYCHOLOGY OF SCAMS, DECEPTION & POWER DYNAMICS"
    sw = draw.textlength(sub, font=sub_font)
    draw.text(((width - sw) / 2 + 3, cy + 60 + 3), sub, font=sub_font, fill=(0, 0, 0, 220))
    draw.text(((width - sw) / 2, cy + 60), sub, font=sub_font, fill=(255, 210, 60, 255))

    # Schedule / CTA bar
    sched = "NEW CASE FILES WEEKLY  •  SUBSCRIBE FOR PSYCHOLOGICAL DEFENSE"
    scw = draw.textlength(sched, font=tag_font)
    draw.text(((width - scw) / 2, cy + 135), sched, font=tag_font, fill=(200, 200, 210, 230))

    final = Image.alpha_composite(bg, overlay).convert("RGB")
    out_path = BRAND_DIR / "youtube_banner_2560x1440.png"
    final.save(out_path, quality=95)
    print(f"✅ Created YouTube Banner: {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────
# 3. Facebook Page Cover (1640x624)
# ─────────────────────────────────────────────────────────────
def build_facebook_cover():
    width, height = 1640, 624
    bg_path = BRAND_DIR / "banner_bg.png"
    
    if bg_path.exists():
        bg = Image.open(bg_path).convert("RGBA").resize((width, height), Image.LANCZOS)
    else:
        bg = Image.new("RGBA", (width, height), (12, 12, 16, 255))

    dim = Image.new("RGBA", (width, height), (0, 0, 0, 150))
    bg = Image.alpha_composite(bg, dim)
    
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    title_font = load_font(110, 0)
    sub_font = load_font(42, 1)
    tag_font = load_font(34, 1)
    
    # Left aligned layout for Facebook (Profile picture is on left or center on mobile)
    cx = width / 2
    cy = height / 2 - 10
    
    title = "COERCION FILES"
    tw = draw.textlength(title, font=title_font)
    draw.text(((width - tw) / 2 + 4, cy - 80 + 4), title, font=title_font, fill=(0, 0, 0, 230))
    draw.text(((width - tw) / 2, cy - 80), title, font=title_font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(180, 20, 20))

    sub = "FORENSIC PSYCHOLOGY • SCAMS & SOCIAL ENGINEERING • SELF-DEFENSE"
    sw = draw.textlength(sub, font=sub_font)
    draw.text(((width - sw) / 2, cy + 45), sub, font=sub_font, fill=(255, 210, 60, 255))

    sched = "FOLLOW FOR DAILY CASE BREAKDOWNS"
    scw = draw.textlength(sched, font=tag_font)
    draw.text(((width - scw) / 2, cy + 105), sched, font=tag_font, fill=(210, 210, 220, 220))

    final = Image.alpha_composite(bg, overlay).convert("RGB")
    out_path = BRAND_DIR / "facebook_cover_1640x624.png"
    final.save(out_path, quality=95)
    print(f"✅ Created Facebook Cover: {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────
# 4. Transparent Watermark Seal (400x400)
# ─────────────────────────────────────────────────────────────
def build_watermark_seal():
    size = (400, 400)
    seal = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(seal)
    
    # Circular emblem
    d.ellipse([20, 20, 380, 380], outline=(220, 30, 30, 220), width=6)
    d.ellipse([32, 32, 368, 368], outline=(255, 255, 255, 140), width=2)
    
    font = load_font(42, 0)
    t1 = "COERCION"
    t2 = "FILES"
    
    w1 = d.textlength(t1, font=font)
    w2 = d.textlength(t2, font=font)
    
    d.text(((400 - w1) / 2, 135), t1, font=font, fill=(255, 255, 255, 240))
    d.text(((400 - w2) / 2, 195), t2, font=font, fill=(255, 210, 60, 240))

    out_path = BRAND_DIR / "watermark_seal_400x400.png"
    seal.save(out_path)
    print(f"✅ Created Transparent Watermark Seal: {out_path}")
    return out_path


def main():
    print("🎨 BUILDING MASTER BRANDING ASSETS FOR COERCION FILES...")
    build_profile_avatar()
    build_youtube_banner()
    build_facebook_cover()
    build_watermark_seal()
    print("🎉 ALL BRAND ASSETS SUCCESSFULLY GENERATED IN assets/branding/!")


if __name__ == "__main__":
    main()
