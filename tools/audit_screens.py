"""1.38 (CC, owner 2026-11-26: calm and clear): screenshots of 19 screens (dark / light, English / Hebrew) and a load
count per screen - the controls on screen, the top row's, the words of always-on explanation, the boxed elements -
written to <out>/counts.json. Run it before and after a round on the same screens and compare (docs/dev/SPEC_1_38.md
has the numbers of 1.37.0). tools/count_controls.py counts four screens only.

    python tools/audit_screens.py /tmp/audit/after            # every screen, both themes, both languages
    DARKONLY=1 ONLY=0 python tools/audit_screens.py /tmp/x     # dark English only; screens whose name starts with 0
"""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_readme_media as m
from playwright.sync_api import sync_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/audit/before"
os.makedirs(OUT, exist_ok=True)
COUNT_JS = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth; };
  const ctrls = [...document.querySelectorAll('button, select, input, textarea, [role=tab], a[href], [role=button]')].filter(vis);
  const top = [...document.querySelectorAll('header.topbar button, header.topbar select, header.topbar input')].filter(vis);
  // instruction text: visible leaf-ish blocks of >= 50 chars of prose not inside a table / plot / list of data
  const blocks = [...document.querySelectorAll('p, div, span, li, small')].filter(e => vis(e) && !e.closest('table, canvas, svg, .grid, .sig, .run-head, input, textarea, .uplot')
     && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length >= 50));
  const texts = blocks.map(e => e.innerText.trim().replace(/\\s+/g, ' ').slice(0, 160));
  const words = texts.reduce((a, t) => a + t.split(' ').length, 0);
  const boxedEls = [...document.querySelectorAll('*')].filter(e => { if (!vis(e)) return false; const s = getComputedStyle(e);
     return parseFloat(s.borderTopWidth) > 0 && parseFloat(s.borderLeftWidth) > 0 && parseFloat(s.borderRightWidth) > 0 && parseFloat(s.borderBottomWidth) > 0; });
  const borders = boxedEls.length;
  // what the eye sees as a frame: a border on all four sides in a colour that is not transparent (a button's
  // transparent border keeps its size, it draws nothing) and not the element's own fill
  const seen = c => !/rgba\([^)]*,\s*0\)$|transparent/.test(c);
  const outlinedEls = boxedEls.filter(e => { const s = getComputedStyle(e); return seen(s.borderTopColor) && seen(s.borderLeftColor) && s.borderTopColor !== s.backgroundColor; });   // a filled button's own colour is no frame
  // which kinds of element are outlined (tag.firstClass) - where to look for outlines to take away
  const boxedBy = {}; outlinedEls.forEach(e => { const k = e.tagName.toLowerCase() + '.' + ((e.className && e.className.toString().split(' ')[0]) || ''); boxedBy[k] = (boxedBy[k] || 0) + 1; });
  const region = e => { const r = e.closest('header.topbar, .stage-bar, .rail, .side-panel, .panel, aside, .inspector, .plot-head, .plot, .timeline, .statusbar, .sw-toolbar, .sw-steps, .sw-side, .dialog, .menu, .sw-main, main');
     return r ? (r.className || r.tagName).toString().split(' ')[0] : 'other'; };
  const list = ctrls.map(e => [region(e), (e.getAttribute('aria-label') || e.innerText || e.title || e.placeholder || '').trim().replace(/\\s+/g,' ').slice(0, 40)]).filter(x => x[1]);
  return { list, controls: ctrls.length, topbar: top.length, proseBlocks: texts.length, proseWords: words, boxed: borders, outlined: outlinedEls.length, boxedBy,
           topbarItems: top.map(b => (b.getAttribute('aria-label') || b.innerText || b.title || b.placeholder || '').trim().slice(0, 30)),
           prose: texts };
}"""

def he(pg):
    pg.evaluate("window.__sv.setState({ lang: 'he' })"); pg.wait_for_timeout(700)

def scenes(app):
    def welcome(pg): pg.wait_for_selector(".ex-card")
    def plots(pg): m.overview(pg, app)
    def files_only(pg): m.open_api(pg, app, "run_012.csv"); pg.evaluate("window.__sv.setState({ inspectorOpen: false })")
    def create(pg): m.open_api(pg, app, "run_012.csv"); m.sig(pg, "Speed").click(); pg.click("[aria-label='Create signals']"); pg.wait_for_timeout(600)
    def compare(pg): m.compare_view(pg, app)
    def investigate(pg): m.open_api(pg, app, "run_012.csv"); m.sig(pg, "Speed").click(); pg.evaluate("window.__sv.setState({ panel: 'investigate' })"); pg.wait_for_timeout(900)
    def messages(pg): pg.evaluate("window.__sv.setState({ panel: 'messages' })"); pg.wait_for_timeout(900)
    def report(pg): m.open_api(pg, app, "run_012.csv"); m.sig(pg, "Speed").click(); pg.evaluate("window.__sv.setState({ panel: 'report' })"); pg.wait_for_timeout(1200)
    def checks_log(pg): m.log_panel(pg, app, "Health")
    def checks_bench(pg):
        m.open_api(pg, app, "bench/pump_run_07.parquet"); pg.evaluate("window.__sv.setState({ panel: 'log', startCard: null })"); pg.wait_for_timeout(1500)
    def sweeps_welcome(pg): pg.locator(".areas .area-btn", has_text="Sweeps").click(); pg.wait_for_selector(".sw-welcome")
    def sweep_step(step):
        def f(pg):
            pg.locator(".areas .area-btn", has_text="Sweeps").click()
            pg.locator(".sw-welcome .btn", has_text="Try an example").click(); pg.wait_for_selector(".sw-steps")
            pg.locator(f".sw-step-btn[data-step='{step}']").click(); pg.wait_for_timeout(1500)
        return f
    def settings(pg): pg.evaluate("window.__sv.setState({ settingsOpen: true })"); pg.wait_for_timeout(600)
    def palette(pg): m.open_api(pg, app, "run_012.csv"); pg.keyboard.press("Control+k"); pg.wait_for_timeout(600)
    def templates(pg): m.open_api(pg, app, "run_012.csv"); pg.evaluate("window.__sv.setState({ templatesOpen: true })"); pg.wait_for_timeout(900)
    return [("01_welcome", welcome), ("02_plots_inspector", plots), ("03_files_panel", files_only), ("04_create", create),
            ("05_compare", compare), ("06_investigate", investigate), ("07_messages", messages), ("08_report", report),
            ("09_checks_flightlog", checks_log), ("10_checks_bench", checks_bench), ("11_sweeps_welcome", sweeps_welcome),
            ("12_sweeps_data", sweep_step("raw")), ("13_sweeps_columns", sweep_step("roles")), ("14_sweeps_goal", sweep_step("goals")),
            ("15_sweeps_results", sweep_step("results")), ("16_sweeps_next", sweep_step("next")),
            ("17_settings", settings), ("18_palette", palette), ("19_templates", templates)]

app = m.App()
counts = {}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("SV_CHROMIUM") or None, args=["--no-sandbox"])
        only = os.environ.get("ONLY")
        for name, fn in scenes(app):
            if only and not name.startswith(only): continue
            for theme in (("dark",) if os.environ.get("DARKONLY") else ("dark", "light")):
                for lang in (("en",) if os.environ.get("DARKONLY") else ("en", "he")):
                    if theme == "light" and lang == "he": continue
                    key = f"{name}_{theme}_{lang}"
                    try:
                        ctx, pg = m.page(b, app, dark=theme == "dark")
                        fn(pg)
                        if lang == "he": he(pg)
                        m.no_toasts(pg); pg.mouse.move(m.W - 5, m.H - 5); pg.wait_for_timeout(300)
                        pg.screenshot(path=os.path.join(OUT, key + ".png"))
                        if theme == "dark" and lang == "en": counts[name] = pg.evaluate(COUNT_JS)
                        print("ok", key, flush=True)
                    except Exception as e:
                        print("FAIL", key, str(e).splitlines()[0][:200], flush=True)
                    finally:
                        try: ctx.close()
                        except Exception: pass
finally:
    app.close()
json.dump(counts, open(os.path.join(OUT, "counts.json"), "w"), indent=1, ensure_ascii=False)
