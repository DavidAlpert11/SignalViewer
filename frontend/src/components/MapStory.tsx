import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, type StoryMoment } from "../api";
import { recordingExtent, useApp, type MapObject, type Plot } from "../store";
import { useT } from "../i18n";
import { pairOf } from "../relation";
import { trackRequest } from "../mapObjects";
import { placesSpec } from "../plotSpec";
import { replayInfo } from "../replay";
import { mapCameraNow, mapFly, mapObjectAt, type FlyTarget } from "../globeBridge";

/* P10: Story mode in the app - the same moments as the live page's (POST /api/story: svcore/story.py), played
   the same way: the app's cursor runs so the recording takes about Settings' length (x1 to x60), x1 from 3 s
   before a moment to 2 s after, a 4 s stop on it with its card over the Map, the camera flying to the moment's
   object; Esc ends it and the reader's camera comes back; a click on the card stays there. Only the cursor and
   the camera move - nothing goes into Undo. */
/** the plot as it is now (the story's closures outlive a render) */
const activeTabPlot = (id: string): Plot | undefined => {
  for (const tb of useApp.getState().ws.tabs) { const p = tb.plots.find((x) => x.id === id); if (p) return p; }
  return undefined;
};
const CLOSE: Record<string, boolean> = { steepest: true, largest_error: true, takeoff: true, landing: true };

export default function MapStory({ plot, objects }: { plot: Plot; objects: MapObject[] }) {
  const t = useT();
  const on = useApp((s) => s.mapPrefs.story === "on");
  const lang = useApp((s) => s.lang);
  const [list, setList] = useState<StoryMoment[] | null>(null);
  const [idx, setIdx] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const run = useRef({ raf: 0, last: 0, pauseUntil: 0, next: 0, saved: null as FlyTarget | null, list: [] as StoryMoment[] });
  const setCursor = (v: number) => { const c = useApp.getState().cursor; useApp.setState({ cursor: { ...c, on: true, t1: v, active: 1 } }); };
  /** The reader chose a camera that keeps to an object (On the object, Chase, Look at, Cockpit): the story only
   *  moves the time - the camera goes on doing what was chosen (it used to fly back to a general view). */
  const bound = () => {
    const p = activeTabPlot(plot.id) ?? plot;
    return !!p.followObject || p.camera === "chase" || p.camera === "lookat" || p.camera === "cockpit";
  };
  const focus = (m: StoryMoment) => {
    if (bound()) return;
    // after the cursor moved, the view has the object's position: fly there (On the object ~400 m, or near)
    window.setTimeout(() => {
      const id = objects.find((o) => o.name === m.object)?.id ?? pairOf(plot).primary ?? objects[0]?.id;
      const at = id ? mapObjectAt.get(plot.id)?.(id) : null;
      if (at) mapFly.get(plot.id)?.({ lat: at.lat, lon: at.lon, alt: at.alt ?? undefined, range: CLOSE[m.kind] ? 120 : 400, pitch: CLOSE[m.kind] ? -15 : -30 });
    }, 60);
  };
  const show = (k: number) => { const m = run.current.list[k]; if (!m) return; setIdx(k); setCursor(m.t); focus(m); };
  const end = (keep = false) => {
    cancelAnimationFrame(run.current.raf);
    setPlaying(false); setIdx(-1);
    const s = run.current.saved; run.current.saved = null;
    if (s && !keep && !bound()) mapFly.get(plot.id)?.(s);
  };
  const ext = () => recordingExtent(useApp.getState().runs) ?? [0, 0];
  const tick = (now: number) => {
    const R = run.current, dt = Math.min(0.25, (now - R.last) / 1000);
    R.last = now;
    if (now >= R.pauseUntil) {
      const [lo, hi] = ext(), span = Math.max(1e-9, hi - lo);
      const len = useApp.getState().mapPrefs.storyLength || 90;
      const rate = Math.min(60, Math.max(1, span / len));
      const cur = useApp.getState().cursor.t1 ?? lo, m = R.list[R.next], prev = R.list[R.next - 1];
      const slow = (m && cur >= m.t - 3) || (prev && cur <= prev.t + 2);
      const v = cur + dt * (slow ? 1 : rate);
      if (m && v >= m.t) { show(R.next); R.next++; R.pauseUntil = now + 4000; }
      else if (v >= hi) { setCursor(hi); end(); return; }
      else setCursor(v);
    }
    R.raf = requestAnimationFrame(tick);
  };
  const start = async () => {
    if (playing) { end(); return; }
    let ms = list;
    if (!ms) {
      const st = useApp.getState(), pair = pairOf(plot), nm = (id?: string | null) => objects.find((o) => o.id === id)?.name ?? null;
      try {
        ms = (await api.story({ objects: objects.filter((o) => !o.hidden).map((o) => ({ ...trackRequest(o, plot.objects ?? []), name: o.name })),
          places: placesSpec(), primary: nm(pair.primary), secondary: nm(pair.secondary), events: replayInfo(st.lang, true).events,
          units: st.mapPrefs.units, lang: st.lang })).moments;
      } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); return; }
      setList(ms);
    }
    if (!ms.length) { useApp.getState().toast({ kind: "info", text: t("storyNone") }); return; }
    const R = run.current;
    R.list = ms;
    R.saved = mapCameraNow.get(plot.id)?.() ?? null;
    const cur = useApp.getState().cursor.t1;
    if (cur === null || cur >= ms[ms.length - 1].t) setCursor(ext()[0]);
    const c0 = useApp.getState().cursor.t1 ?? ext()[0];
    R.next = 0; while (R.next < ms.length && ms[R.next].t < c0 - 1e-6) R.next++;
    R.pauseUntil = 0; R.last = performance.now();
    setPlaying(true);
    R.raf = requestAnimationFrame(tick);
  };
  const go = (k: number) => { const R = run.current; if (k < 0 || k >= R.list.length) return; show(k); R.next = k + 1; R.pauseUntil = performance.now() + 4000; };
  useEffect(() => {
    if (!playing) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") end(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [playing]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => cancelAnimationFrame(run.current.raf), []);
  useEffect(() => { setList(null); }, [objects.map((o) => o.id).join("|")]);   // eslint-disable-line react-hooks/exhaustive-deps
  (window as unknown as { __svStory?: unknown }).__svStory = { on: playing, index: idx, count: list?.length ?? 0 };   // for tests
  if (!on || !objects.length) return null;
  const m = idx >= 0 ? run.current.list[idx] : null;
  const host = btn.current?.closest(".globe3d, .plot-canvas") as HTMLElement | null;
  return <>
    <button ref={btn} className={`g3-toggle map-story${playing ? " on" : ""}`} aria-pressed={playing} title={t("storyHint")} onClick={() => void start()}>▶ {t("storyBtn")}</button>
    {m && host && createPortal(
      <div className={`map-story-card ${m.level}`} role="status" aria-live="polite" title={t("storyStay")} onClick={() => end(true)}
        onMouseDown={(e) => e.stopPropagation()} dir={lang === "he" ? "rtl" : "ltr"}>
        <b>{m.title}</b>
        <span>{m.kind === "event" ? `${m.t.toFixed(1)} s` : m.text}</span>
        <span className="map-story-nav" onClick={(e) => e.stopPropagation()}>
          <button className="iconbtn sm" aria-label={t("storyPrev")} title={t("storyPrev")} onClick={() => go(idx - 1)}>◀</button>
          <bdi dir="ltr">{idx + 1} / {run.current.list.length}</bdi>
          <button className="iconbtn sm" aria-label={t("storyNext")} title={t("storyNext")} onClick={() => go(idx + 1)}>▶</button>
        </span>
      </div>, host)}
  </>;
}
