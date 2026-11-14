"""Pictures of the mock-ups for the plan: dark/en with notes, light/he without (python docs/dev/mockups/shoot.py)."""
import io
import os
from PIL import Image
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
with sync_playwright() as p:
    exe = os.environ.get("SV_CHROMIUM")
    b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    for name in ("recordings", "recordings-any", "map", "sweeps", "sweeps-start", "what-changed", "map-cameras"):
        for q, sfx in (("theme=dark&lang=en", "dark_en"), ("theme=light&lang=he&notes=0", "light_he"), ("theme=dark&lang=en&notes=0", "dark_en_clean")):
            pg.goto(f"file://{HERE}/{name}.html?{q}")
            pg.wait_for_timeout(400)
            pg.evaluate("document.querySelector('.mockbar').remove()")
            Image.open(io.BytesIO(pg.screenshot())).convert("RGB").save(os.path.join(HERE, f"{name}_{sfx}.webp"), "WEBP", quality=78, method=6)
            print(name, sfx)
    b.close()
