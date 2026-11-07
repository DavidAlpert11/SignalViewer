import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { actions, activeTab, onTimeAxis, signalName, tabBandLanes, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { inkOn, labelsOf, labelText, stateColor } from "../values";
import { laneMenuItems } from "../lanes";
import { openMenu } from "./Overlays";

type Marks = Record<string, { points: [number, number | null][]; tooMany: boolean; end: number | null }>;
type Seg = { a: number; b: number; v: number | null };

/** The stretches of a state's marks (a value and where it holds; null = too many changes to show). */
function segsOf(m: Marks[string] | undefined): Seg[] {
  if (!m) return [];
  return m.points.map(([a, v], i) => ({ a, b: i + 1 < m.points.length ? m.points[i + 1][0] : (m.end ?? a), v }));
}
const at = (segs: Seg[], t: number) => segs.find((s) => t >= s.a && t < s.b) ?? (segs.length && t === segs[segs.length - 1].b ? segs[segs.length - 1] : undefined);

/** U3 (owner, 2026-11-07): the tab's state lanes - the flight mode on an ArduPilot tab - ONCE above
 *  its plots instead of at the bottom of each (they get the height back). It lines up with the
 *  plots' time axis and follows their zoom; cursors 1 / 2 and the pointer over a plot are lines on
 *  it, and the state under each is outlined and named. A click on a stretch puts the cursors on its
 *  edges, Shift+click zooms to it (as a lane in a plot does); right-click: where the lane is shown.
 *  A plot can show the lanes again itself (its ⋯ menu). */
export default function TabBand() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const theme = useApp((s) => s.theme);
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const dataVersion = useApp((s) => s.dataVersion);
  const cursor = useApp((s) => s.cursor);
  const tab = activeTab(ws);
  // the lanes the overview strip shows already are drawn there (with the cursors), not twice
  const inStrip = useApp((s) => s.stripLanes);
  const lanes = tabBandLanes(ws.globalStates, tab).filter((id) => runs.some((r) => r.signals.some((x) => x.id === id)) && !inStrip.includes(id));
  const first = tab.plots.find(onTimeAxis);
  const view = useApp((s) => (first ? s.xViews[first.id] : undefined));
  const hover = useApp((s) => (s.hover && tab.plots.some((p) => p.id === s.hover!.plotId) ? s.hover.t : null));
  const [marks, setMarks] = useState<Marks>({});
  const ref = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ left: number; width: number } | null>(null);
  const laneKey = lanes.join("|");

  // where the plots' drawing area is (the first time plot's; all of them share it in one column)
  useEffect(() => {
    if (!first) return;
    const measure = () => {
      const el = ref.current;
      const over = document.querySelector(`[data-plot="${first.id}"] .u-over`);
      if (!el || !over) { setBox((b) => (b ? null : b)); return; }
      const r = el.getBoundingClientRect(), o = over.getBoundingClientRect();
      const left = Math.round(o.left - r.left), width = Math.round(o.width);
      setBox((b) => (b && b.left === left && b.width === width ? b : { left, width }));
    };
    measure();
    const id = window.setInterval(measure, 400);
    window.addEventListener("resize", measure);
    return () => { window.clearInterval(id); window.removeEventListener("resize", measure); };
  }, [first?.id, laneKey]);

  useEffect(() => {
    if (!lanes.length || !view) { setMarks({}); return; }
    let gone = false;
    const h = window.setTimeout(async () => {
      try {
        const r = await api.states(lanes, view[0], view[1], Math.max(200, Math.round(box?.width ?? 800)));
        if (!gone) setMarks(r.states);
      } catch { /* the plots still work without it */ }
    }, 80);
    return () => { gone = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [laneKey, view?.[0], view?.[1], dataVersion, Math.round((box?.width ?? 0) / 100)]);

  if (!lanes.length || !first) return null;
  const [x0, x1] = view ?? [0, 1];
  const span = Math.max(x1 - x0, 1e-12);
  const pct = (x: number) => `${((Math.min(Math.max(x, x0), x1) - x0) / span) * 100}%`;
  const inView = (x: number | null): x is number => x !== null && x >= x0 && x <= x1;
  const lines: { t: number; tag: string; cls: string }[] = [
    ...(cursor.on && inView(cursor.t1) ? [{ t: cursor.t1, tag: "1", cls: "c1" }] : []),
    ...(cursor.on && cursor.dual && inView(cursor.t2) ? [{ t: cursor.t2, tag: "2", cls: "c2" }] : []),
    ...(!cursor.on && inView(hover) ? [{ t: hover, tag: "", cls: "hover" }] : []),
  ];
  const valueText = (id: string, v: number | null) => (v === null ? "…" : labelText(labelsOf(runs, id), v) ?? fmtNum(v, lang, 5));
  const pick = (e: React.MouseEvent, s: Seg) => {
    if (s.v === null || !(s.b > s.a)) return;
    if (e.shiftKey) actions.showSpan(s.a, s.b);
    else useApp.setState({ cursor: { ...useApp.getState().cursor, on: true, dual: true, t1: s.a, t2: s.b, active: 1 } });
  };

  return (
    <div className="tab-band" ref={ref} role="group" aria-label={t("bandTitle")}
      style={box ? ({ "--band-left": `${box.left}px`, "--band-width": `${box.width}px` } as React.CSSProperties) : undefined}>
      {lanes.map((id) => {
        const segs = segsOf(marks[id]);
        const name = signalName(runs, id, false);
        const under = lines.map((l) => ({ ...l, seg: at(segs, l.t) }));
        return (
          <div key={id} className="band-row" data-lane={id}>
            <button className="band-label linklike" dir="auto" title={`${name} · ${t("bandLaneMenu")}`}
              onClick={(e) => openMenu(e, laneMenuItems(first.id, id, true))}
              onContextMenu={(e) => { e.preventDefault(); openMenu(e, laneMenuItems(first.id, id, true)); }}>{name}</button>
            <div className="band-track">
              {segs.map((s, k) => {
                if (s.b < x0 || s.a > x1) return null;
                const bg = s.v === null ? undefined : stateColor(s.v, theme);
                const txt = valueText(id, s.v);
                const hit = under.some((u) => u.seg === s);
                return (
                  <button key={k} className={`band-seg${s.v === null ? " many" : ""}${hit ? " at" : ""}`}
                    style={{ left: pct(s.a), width: `calc(${pct(s.b)} - ${pct(s.a)})`, background: bg, color: bg ? inkOn(bg) : undefined }}
                    title={`${name}: ${txt} · ${fmtNum(s.a, lang, 5)} – ${fmtNum(s.b, lang, 5)} s\n${t("bandSegHint")}`}
                    onClick={(e) => pick(e, s)}><span>{txt}</span></button>
                );
              })}
              {under.map((l) => (
                <div key={l.cls} className={`band-line ${l.cls}${(l.t - x0) / span > 0.8 ? " flip" : ""}`} style={{ left: pct(l.t) }}>
                  {l.seg && <span className="band-tag" dir="auto">{l.tag ? `${l.tag} · ` : ""}{valueText(id, l.seg.v)}</span>}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
