"""Screens of every main area for a design review (PLAN_2026-11-14): the app as it is, 1440x900,
dark / light and en / he. Pictures (WebP) go to docs/dev/mockups/before/ (or --out).

    SV_CHROMIUM=/path/to/chrome python tools/plan_screens.py [--out DIR] [--only welcome sweeps ...]

Uses the app start-up of tools/make_readme_media.py (an empty home, the examples)."""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_readme_media as M  # noqa: E402

M.W, M.H = 1440, 900
OUT = os.path.join(os.path.dirname(HERE), "docs", "dev", "mockups", "before")


def example(pg, ex_id):
    pg.wait_for_selector(f".ex-card[data-example={ex_id}]")
    pg.locator(f".ex-card[data-example={ex_id}]").click()


def plotted(pg):
    pg.wait_for_function("window.__sv.state().busy === 0 && window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length || (p.objects || []).length))", timeout=60000)
    pg.wait_for_timeout(1500)
    M.no_toasts(pg)
    pg.evaluate("window.__sv.setState({ startCard: null })")
    pg.wait_for_timeout(300)


def lang(pg, he):
    if he:
        pg.evaluate("window.__sv.setState({ lang: 'he' })")
        pg.wait_for_timeout(500)


def save(pg, name):
    os.makedirs(OUT, exist_ok=True)
    from PIL import Image                       # WebP: a tenth of the PNG (the repository's size matters)
    Image.open(io.BytesIO(pg.screenshot())).convert("RGB").save(os.path.join(OUT, name + ".webp"), "WEBP", quality=78, method=6)
    print(name)


def scenes(b, app, dark, he):
    sfx = ("dark" if dark else "light") + ("_he" if he else "_en")

    ctx, pg = M.page(b, app, dark=dark); lang(pg, he)
    pg.wait_for_selector(".ex-card"); pg.wait_for_timeout(800)
    save(pg, f"01_welcome_{sfx}")
    example(pg, "flight"); plotted(pg)
    save(pg, f"02_recordings_{sfx}")
    if dark and not he:
        for panel in ("analysis", "compare", "investigate", "report"):
            pg.evaluate(f"window.__sv.setState({{ panel: '{panel}' }})"); pg.wait_for_timeout(900)
            save(pg, f"03_panel_{panel}_{sfx}")
        pg.evaluate("window.__sv.setState({ panel: 'data' })")
    ctx.close()

    if dark and not he:
        ctx, pg = M.page(b, app, dark=dark)
        example(pg, "ardupilot"); plotted(pg)
        save(pg, f"04_flightlog_{sfx}")
        ctx.close()
        ctx, pg = M.page(b, app, dark=dark)
        example(pg, "twoFlights"); plotted(pg)
        M.apply_template(pg, "bi-position"); pg.wait_for_timeout(4000)
        save(pg, f"05_map_{sfx}")
        ctx.close()

    # Sweeps: the welcome, one table (its question), Common parameters, the demo
    ctx, pg = M.page(b, app, dark=dark); lang(pg, he)
    pg.evaluate("window.__sv.setState({ area: 'sweeps' })")
    pg.wait_for_selector(".sw-welcome, .sw-study-wrap"); pg.wait_for_timeout(1200)
    save(pg, f"10_sweeps_welcome_{sfx}")
    ctx.close()
    ctx, pg = M.page(b, app, dark=dark); lang(pg, he)
    example(pg, "sweepTable")
    pg.wait_for_function("!!window.__svSweeps && window.__svSweeps.idle()", timeout=60000); pg.wait_for_timeout(2500)
    M.no_toasts(pg)
    save(pg, f"11_sweeps_table_{sfx}")
    ctx.close()
    ctx, pg = M.page(b, app, dark=dark); lang(pg, he)
    example(pg, "commonGains")
    pg.wait_for_selector("[data-testid=study-panel]"); pg.wait_for_function("!window.__svStudy.state().busy", timeout=60000)
    pg.wait_for_timeout(1500); M.no_toasts(pg)
    save(pg, f"12_sweeps_common_{sfx}")
    ctx.close()
    ctx, pg = M.page(b, app, dark=dark); lang(pg, he)
    example(pg, "smartSweepDemo")
    pg.wait_for_selector("[data-testid=demo-panel]"); pg.wait_for_timeout(1500)
    if dark and not he:
        pg.locator("[data-testid=demo-panel] button", has_text="Next round").first.click()
        pg.wait_for_function("(() => { const p = window.__svStudy.state().demoProgress; return p && !p.running && p.points.length >= 1; })()", timeout=120000)
        pg.wait_for_timeout(1000)
    M.no_toasts(pg)
    save(pg, f"13_sweeps_demo_{sfx}")
    ctx.close()

    if dark and not he:
        ctx, pg = M.page(b, app, dark=dark)
        M._fleet(pg); M.no_toasts(pg)
        save(pg, f"20_fleet_{sfx}")
        ctx.close()


def main() -> int:
    global OUT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    OUT = a.out
    from playwright.sync_api import sync_playwright
    app = M.App()
    try:
        with sync_playwright() as p:
            exe = os.environ.get("SV_CHROMIUM")
            b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox"])
            for dark, he in ((True, False), (False, False), (True, True), (False, True)):
                try:
                    scenes(b, app, dark, he)
                except Exception as e:                    # one failed scene must not lose the others
                    print("FAILED", dark, he, repr(e)[:300])
            b.close()
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
