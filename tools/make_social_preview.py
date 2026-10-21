"""B7: the repository's social preview (GitHub -> Settings -> Social preview), 1280 x 640.

The card shown when the repository link is pasted in chat, mail or LinkedIn. Built from the app
icon and a screenshot, so it is redrawn whenever the screenshots are retaken:
    python tools/make_social_preview.py        ->  docs/images/social-preview.png
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 640
BG, INK, MUTED, ACCENT = (15, 23, 33), (240, 244, 248), (160, 174, 190), (232, 160, 48)


def font(bold: bool, size: int):
    for name in (("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),):
        for d in ("/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts", "/Library/Fonts"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def main() -> str:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    icon = Image.open(os.path.join(ROOT, "assets/png/icon-256.png")).convert("RGBA").resize((88, 88))
    im.paste(icon, (64, 70), icon)
    d.text((64, 182), "Signal Viewer", font=font(True, 54), fill=INK)
    y = 262
    for line in ("Explore, compare and report on", "flight logs, test runs and", "simulation output - offline."):
        d.text((66, y), line, font=font(False, 26), fill=MUTED)
        y += 38
    y += 26
    for tag in ("ArduPilot · PX4 · MAVLink · CSV · .mat", "Compare runs · pass / fail in CI", "English · עברית"):
        d.rectangle((66, y + 9, 72, y + 15), fill=ACCENT)
        d.text((84, y), tag, font=font(False, 20), fill=INK)
        y += 34
    shot = Image.open(os.path.join(ROOT, "docs/images/01_overview.png")).convert("RGB")
    sw = 720
    shot = shot.resize((sw, round(shot.height * sw / shot.width)), Image.LANCZOS)
    x0, y0 = 520, 120
    shadow = Image.new("RGBA", (sw + 40, shot.height + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((20, 20, sw + 20, shot.height + 20), fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    im.paste(shadow, (x0 - 14, y0 - 8), shadow)
    im.paste(shot, (x0, y0))
    d.rectangle((x0, y0, x0 + sw - 1, y0 + shot.height - 1), outline=(60, 72, 88))
    out = os.path.join(ROOT, "docs/images/social-preview.png")
    im.save(out, optimize=True)
    return out


if __name__ == "__main__":
    print(main())
