"""W16: how many controls a new user sees without opening anything, on four screens - the welcome screen, one
plotted tab (the drone-flight example), the Sweeps area, the Settings dialog. Counts every visible button,
input, select, textarea and [role=button] (not inside a closed menu or a hidden element).

    python tools/count_controls.py [--root <checkout>] [--json]

Run it on the base and on the result (a `git worktree` of the base as --root) to compare. Uses the app
start-up of tools/make_readme_media.py (an empty home, the examples) and SV_CHROMIUM if set."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNT = """() => [...document.querySelectorAll('button, input, select, textarea, [role=button]')].filter((e) => {
  const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return false;
  if (e.checkVisibility && !e.checkVisibility({ visibilityProperty: true, contentVisibilityAuto: true })) return false;   // a closed <details> too
  return r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth;
}).length"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(HERE), help="the checkout to start (default: this one)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    import make_readme_media as M
    M.ROOT = os.path.abspath(a.root)
    from playwright.sync_api import sync_playwright
    app = M.App()
    out = {}
    try:
        with sync_playwright() as p:
            exe = os.environ.get("SV_CHROMIUM")
            b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox"])
            ctx, pg = M.page(b, app)
            pg.wait_for_selector(".examples-line button")
            out["welcome"] = pg.evaluate(COUNT)
            pg.locator(".examples-line button", has_text="a drone flight").click()
            pg.wait_for_function("window.__sv.state().busy === 0 && window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length || (p.objects || []).length))", timeout=60000)
            pg.wait_for_timeout(1500)
            M.no_toasts(pg)
            pg.evaluate("window.__sv.setState({ startCard: null })")
            pg.wait_for_timeout(300)
            out["plotted"] = pg.evaluate(COUNT)
            pg.click(".topbar [aria-label='Settings']")
            pg.wait_for_selector(".dialog.settings")
            out["settings"] = pg.evaluate("(() => { const d = document.querySelector('.dialog.settings'); return [...d.querySelectorAll('button, input, select, textarea, [role=button]')].filter((e) => e.getBoundingClientRect().height > 1 && (!e.checkVisibility || e.checkVisibility({ visibilityProperty: true }))).length; })()")
            pg.keyboard.press("Escape")
            pg.evaluate("window.__sv.setState({ area: 'sweeps' })")
            pg.wait_for_timeout(1500)
            out["sweeps"] = pg.evaluate(COUNT)
            b.close()
    finally:
        app.close()
    print(json.dumps(out) if a.json else "  ".join(f"{k}: {v}" for k, v in out.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
