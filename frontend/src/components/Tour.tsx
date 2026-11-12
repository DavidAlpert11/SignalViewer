/* W13.8: the first-launch tour - four coach marks on the data-tour anchors (the command search, Open files,
   the signal list, Compare), 30 seconds, skippable, shown once (prefs `tourDone`) and again from Help → Tour.
   It does not start by itself under automation (navigator.webdriver: the e2e tests, the picture tool) - they
   start it from the Help menu. Nothing modal: no scrim, the app stays usable under it. */
import { useEffect, useLayoutEffect, useState } from "react";
import { useT, type TKey } from "../i18n";
import { useApp } from "../store";
import { getPrefValue, setPref } from "../prefs";

const STEPS: { anchor: string; title: TKey; text: TKey }[] = [
  { anchor: "palette", title: "tourPaletteTitle", text: "tourPaletteText" },
  { anchor: "open", title: "tourOpenTitle", text: "tourOpenText" },
  { anchor: "signals", title: "tourSignalsTitle", text: "tourSignalsText" },
  { anchor: "compare", title: "tourCompareTitle", text: "tourCompareText" },
];
const DONE_KEY = "tourDone";

const tour = { step: -1, listeners: new Set<() => void>() };
const emit = () => { for (const f of tour.listeners) f(); };
const shown = (i: number) => !!document.querySelector(`[data-tour="${STEPS[i]?.anchor}"]`);
/** the next step at or after i whose anchor is on screen (-1: none - the tour ends) */
const nextFrom = (i: number) => { for (let k = i; k < STEPS.length; k++) if (shown(k)) return k; return -1; };

export function startTour(): void { tour.step = nextFrom(0); emit(); }
function endTour(): void { tour.step = -1; setPref(DONE_KEY, true); emit(); }

/** At start: the tour once, for a new user, on the welcome screen. */
export function maybeStartTour(): void {
  if (getPrefValue(DONE_KEY) || (navigator as { webdriver?: boolean }).webdriver) return;
  window.setTimeout(() => { if (!useApp.getState().runs.length) startTour(); }, 800);
}

export default function Tour() {
  const t = useT();
  const [step, setStep] = useState(tour.step);
  const [box, setBox] = useState<DOMRect | null>(null);
  useEffect(() => { const f = () => setStep(tour.step); tour.listeners.add(f); return () => { tour.listeners.delete(f); }; }, []);
  useLayoutEffect(() => {
    if (step < 0) { setBox(null); return; }
    const place = () => setBox(document.querySelector(`[data-tour="${STEPS[step].anchor}"]`)?.getBoundingClientRect() ?? null);
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [step]);
  useEffect(() => {
    if (step < 0) return;
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") endTour(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [step]);
  if (step < 0 || !box) return null;
  const s = STEPS[step];
  const next = nextFrom(step + 1);
  // below the anchor when there is room, else above; kept inside the window
  const W = 300, below = box.bottom + 160 < window.innerHeight;
  const left = Math.max(8, Math.min(window.innerWidth - W - 8, box.left + box.width / 2 - W / 2));
  const style = below ? { top: box.bottom + 10, left, width: W } : { bottom: window.innerHeight - box.top + 10, left, width: W };
  return (
    <>
      <div className="tour-ring" aria-hidden="true" style={{ top: box.top - 4, left: box.left - 4, width: box.width + 8, height: box.height + 8 }} />
      <section className={`tour-card ${below ? "below" : "above"}`} role="dialog" aria-label={t(s.title)} style={style} data-step={step}>
        <h3>{t(s.title)}</h3>
        <p>{t(s.text)}</p>
        <div className="tour-foot">
          <span className="tour-dots" aria-hidden="true">{STEPS.map((_, i) => <i key={i} className={i === step ? "on" : ""} />)}</span>
          <button className="linkbtn tour-skip" onClick={endTour}>{t("tourSkip")}</button>
          <button className="btn primary sm tour-next" autoFocus onClick={() => (next < 0 ? endTour() : (tour.step = next, emit()))}>
            {next < 0 ? t("tourDone") : t("tourNext")}</button>
        </div>
      </section>
    </>
  );
}
