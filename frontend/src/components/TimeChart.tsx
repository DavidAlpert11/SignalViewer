import { useEffect, useMemo, useRef, useState } from "react";
import uPlot from "uplot";
import { api, type Series } from "../api";
import { actions, activeTab, DEFAULT_LINE_WIDTH, rangeKey, shownSpan, yRangeKey, useApp, type Plot, type PlotSignal, type PreviewLine, type Range, type Tab } from "../store";
import { inkOn, labelsOf, labelText, stateColor, runsDataKey } from "../values";
import { fmtNum, translate } from "../i18n";
import { signalUnit } from "../units";
import { axisStyle, tickValues, dpr, flag, PLOT_THEME, PREVIEW_DASH, reportGutter, uiScale, useGutter, useSize, WHEEL_GESTURE_MS, wheelPixels, wheelZoom } from "./chartUtil";

interface Props {
  tab: Tab; plot: Plot; index: number; onLoading: (b: boolean) => void;
  /** A preview plot of its own (not in the workspace): only these dashed lines, index -1. */
  previewOnly?: PreviewLine[];
}

type StateMarks = Record<string, { points: [number, number | null][]; tooMany: boolean; end: number | null }>;

/** Height of one state lane (CSS px) when it shares the plot with ordinary lines. */
const LANE_H = 18;
/** Height of each of n bottom lanes in a plot this tall (CSS px): 18, smaller when they would take
 *  more than a quarter of the plot (the lines keep the rest), never under 8. */
function laneCss(plotH: number, n: number): number {
  return Math.max(8, Math.min(LANE_H, (0.25 * plotH - 4) / Math.max(1, n) - 2));
}

export default function TimeChart({ tab, plot, index, onLoading, previewOnly }: Props) {
  const theme = useApp((s) => s.theme);
  const scale = useApp((s) => s.uiScale);
  const runs = useApp((s) => s.runs);
  const dataVersion = useApp((s) => s.dataVersion);
  const gutter = useGutter(tab, plot.id, !previewOnly);
  const key = rangeKey(tab, plot);
  const yKey = yRangeKey(tab, plot);
  const yZoom = useApp((s) => s.yRanges[yKey] ?? null);
  const zoomMode = useApp((s) => s.zoomMode);
  const yZoomRef = useRef<Range>(yZoom);
  /* flight-log events (ArduPilot .bin) of the files in this plot, as markers along the top */
  const logs = useApp((s) => s.logs);
  const logMarkers = useApp((s) => s.logMarkers);
  const notes = useApp((s) => s.ws.notes);
  const markRef = useRef<{ t: number; t2?: number; text: string; level: string }[]>([]);
  yZoomRef.current = yZoom;
  const storeRange = useApp((s) => s.ranges[key]);
  const range = storeRange === undefined ? (plot.xlim ?? null) : storeRange;
  const rangeRef = useRef(range);
  rangeRef.current = range;
  const cursor = useApp((s) => s.cursor);
  const storePreview = useApp((s) => (s.preview && !s.preview.separate && s.preview.plotId === plot.id ? s.preview : null));
  const preview = previewOnly ? { lines: previewOnly } : storePreview;
  const valuesOnPlot = useApp((s) => s.valuesOnPlot);
  const cvals = useApp((s) => s.cvals);
  const linkY = !!tab.linkY;
  const yUnion = useApp((s) => {
    if (!tab.linkY) return null;
    let lo = Infinity, hi = -Infinity;
    for (const p of tab.plots) {
      if ((p.mode ?? "time") !== "time" || p.ylim) continue;
      const e = s.yExtents[p.id];
      if (e) { lo = Math.min(lo, e[0]); hi = Math.max(hi, e[1]); }
    }
    return Number.isFinite(lo) && hi > lo ? `${lo}|${hi}` : null;
  });
  const playMode = useApp((s) => s.playMode);
  const windowSec = useApp((s) => s.windowSec);
  const valRef = useRef({ cvals, valuesOnPlot, signals: plot.signals, playMode, windowSec });
  valRef.current = { cvals, valuesOnPlot, signals: plot.signals, playMode, windowSec };

  const wrapRef = useRef<HTMLDivElement>(null);
  const uRef = useRef<uPlot | null>(null);
  const overlayRef = useRef<((u: uPlot) => void) | null>(null);
  const cursorRef = useRef(cursor);
  const gestRef = useRef<"x" | "y" | "xy">("x");             // T19: the mode of the drag in progress
  cursorRef.current = cursor;
  const size = useSize(wrapRef);
  const [series, setSeries] = useState<Series[]>([]);
  const [states, setStates] = useState<StateMarks>({});
  const statesRef = useRef(states);
  statesRef.current = states;
  // named conditions shown on this plot: their stretches in the files this plot draws from
  const condRef = useRef<{ color: string; focus: boolean; iv: [number, number][] }[]>([]);
  const conditions = useApp((s) => s.ws.conditions);
  const condResults = useApp((s) => s.condResults);
  const condFocus = useApp((s) => s.condFocus);
  const stripSel = useApp((s) => s.stripSel);
  const barRef = useRef<HTMLDivElement>(null);
  const changeMarks = useApp((s) => s.changeMarks);
  const changeRef = useRef<{ t: number; color: string }[]>([]);

  const sigIds = plot.signals.map((s) => s.sig);
  const sigKey = sigIds.join("|");
  // the tab's shared lanes (e.g. the flight mode on every plot) and the ones on every plot of every
  // tab, unless this plot already shows them - each lane once
  const globalStates = useApp((s) => s.ws.globalStates);
  const shared = [...new Set([...(globalStates ?? []), ...(tab.sharedStates ?? [])])].filter((id) => !plot.signals.some((s) => s.sig === id));
  const stateIds = [...plot.signals.filter((s) => s.state).map((s) => s.sig), ...shared];
  const stateKey = stateIds.join("|");
  const runsKey = runsDataKey(runs);
  const runsRef = useRef(runs);
  runsRef.current = runs;
  const labelsKey = sigIds.map((id) => Object.keys(labelsOf(runs, id) ?? {}).length).join("|");

  /* ------------------------ fetch display points ------------------------ */
  const widthBucket = Math.max(400, Math.ceil(size.w / 200) * 200);
  useEffect(() => {
    if (!sigIds.length) { setSeries([]); return; }
    let cancelled = false;
    const h = window.setTimeout(async () => {
      onLoading(true);
      try {
        // signals with their own time offset are fetched for their shifted window
        const groups = new Map<number, string[]>();
        plot.signals.forEach((ps) => { const o = ps.tOffset ?? 0; groups.set(o, [...(groups.get(o) ?? []), ps.sig]); });
        const parts = await Promise.all(Array.from(groups, ([off, ids]) =>
          api.data(ids, range ? range[0] - off : null, range ? range[1] - off : null, widthBucket * 2)));
        if (!cancelled) setSeries(parts.flat());
      } catch (e) {
        if (!cancelled) useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      } finally {
        if (!cancelled) onLoading(false);
      }
    }, 60);
    return () => { cancelled = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sigKey, range?.[0], range?.[1], widthBucket, dataVersion, runsKey, plot.signals.map((p) => p.tOffset ?? 0).join("|")]);

  /* state transitions in the visible range */
  useEffect(() => {
    if (!stateIds.length) { setStates({}); return; }
    let cancelled = false;
    const h = window.setTimeout(async () => {
      try {
        const r = await api.states(stateIds, range?.[0] ?? null, range?.[1] ?? null, Math.max(200, Math.round(size.w)));
        if (!cancelled) setStates(r.states);
      } catch { /* non-fatal: line still drawn */ }
    }, 80);
    return () => { cancelled = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateKey, range?.[0], range?.[1], dataVersion, runsKey, Math.round(size.w / 100)]);

  useEffect(() => {
    const shown = series.reduce((a, s) => a + s.n, 0), total = series.reduce((a, s) => a + s.total, 0);
    const st = useApp.getState();
    useApp.setState({ decimation: { ...st.decimation, [plot.id]: { shown, total } } });
  }, [series, plot.id]);

  /* ------------------------- build aligned data ------------------------- */
  const styleKey = plot.signals.map((s) => `${s.sig}:${s.color}:${s.width}:${s.scale}:${s.offset}:${s.state ? 1 : 0}:${s.tOffset ?? 0}:${s.limits?.lo ?? ""}:${s.limits?.hi ?? ""}:${s.axis ?? ""}`).join("|");
  const aligned = useMemo(() => {
    const ok = plot.signals
      .map((ps) => ({ ps, s: series.find((x) => x.id === ps.sig) }))
      .filter((v): v is { ps: typeof v.ps; s: Series } => !!v.s && !v.s.missing && v.s.n > 0);
    const pv = preview?.lines.filter((l) => l.x.length) ?? [];
    if (!ok.length && !pv.length) return null;           // an empty plot still shows a preview
    const tables = ok.map(({ ps, s }) => {
      const y: (number | null)[] = new Array(s.n);
      for (let i = 0; i < s.n; i++) {
        const v = s.y[i];
        y[i] = Number.isFinite(v) ? v * ps.scale + ps.offset : null;
      }
      const off = ps.tOffset ?? 0;
      return [off ? Array.from(s.x, (v) => v + off) : Array.from(s.x), y] as uPlot.AlignedData;
    });
    const sigs = ok.map((v) => v.ps);
    for (const l of pv) tables.push([Array.from(l.x), Array.from(l.y, (v) => (Number.isFinite(v) ? v : null))] as uPlot.AlignedData);
    const data = tables.length === 1 ? tables[0] : uPlot.join(tables, tables.map(() => [1]));
    // dense: about a point per pixel or more (decimated min/max) - see lineWidth below
    const dense = ok.map(({ s }) => s.decimated || s.n >= widthBucket * 0.75);
    return { data, sigs, dense, previewLabels: pv.map((l) => l.label) };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, styleKey, preview, widthBucket]);
  const alignedRef = useRef(aligned);
  alignedRef.current = aligned;
  const builtWith = useRef<typeof aligned>(null);
  /* what the plot is BUILT from (series, their styles, a preview line): new data alone is set
     into the existing plot instead of destroying and recreating it on every zoom step */
  const structKey = aligned
    // limits too: they are drawn by a hook that reads the sigs the plot was built with - a new limit
    // alone set no new data, so its dashed line never appeared (only after another style change)
    ? aligned.sigs.map((s) => `${s.sig}:${s.color}:${s.width}:${s.state ? 1 : 0}:${s.axis === "right" ? "R" : ""}:${s.limits?.lo ?? ""}:${s.limits?.hi ?? ""}`).join("|") + `|${aligned.previewLabels.join("|")}`
    : "none";
  /* a dense line at the default width is drawn 1 device pixel wide (the canvas fast path: a wider
     stroke over a dense zig-zag cost ~7x per redraw without a GPU). A width the user chose is always
     kept - on a smooth signal it is visible, and ignoring it looked like a broken setting */
  const lineWidth = (a: NonNullable<typeof aligned>, k: number) =>
    (a.dense[k] && a.sigs[k].width <= DEFAULT_LINE_WIDTH ? 1 / dpr() : a.sigs[k].width);

  /* report this plot's visible value range (for linked value axes) */
  useEffect(() => {
    if (!aligned) return;
    const d = aligned.data;
    const xs = d[0] as number[];
    const lo0 = range ? range[0] : -Infinity, hi0 = range ? range[1] : Infinity;
    let lo = Infinity, hi = -Infinity;
    for (let k = 1; k < d.length; k++) {
      const ys = d[k] as (number | null)[];
      for (let i = 0; i < xs.length; i++) {
        const v = ys[i];
        if (v === null || v === undefined || xs[i] < lo0 || xs[i] > hi0) continue;
        if (v < lo) lo = v; if (v > hi) hi = v;
      }
    }
    if (!Number.isFinite(lo)) return;
    const st = useApp.getState();
    const cur = st.yExtents[plot.id];
    if (!cur || cur[0] !== lo || cur[1] !== hi) useApp.setState({ yExtents: { ...st.yExtents, [plot.id]: [lo, hi] } });
  }, [aligned, range?.[0], range?.[1], plot.id]);

  /* ----------------------------- create uPlot ----------------------------- */
  useEffect(() => {
    const host = wrapRef.current;
    uRef.current?.destroy();
    uRef.current = null;
    const aligned = alignedRef.current;
    builtWith.current = aligned;
    if (!host || !aligned || size.w < 50 || size.h < 50) return;

    const pt = PLOT_THEME[theme];
    const axis = axisStyle(theme);
    const sigs = aligned.sigs;

    /* State signals: one lane each, a coloured block per state with its text (or value) inside.
       Shared with ordinary lines: thin lanes along the bottom (the value axis makes room for them).
       Only states in the plot: the lanes fill it, one under the other, each with its name. */
    const ownStates = sigs.filter((s) => s.state);
    const onlyStates = ownStates.length > 0 && ownStates.length === sigs.length;
    const stateSigs = [...ownStates, ...shared.filter((id) => runsRef.current.some((r) => r.signals.some((x) => x.id === id)))
      .map((id) => ({ sig: id, color: "#8B949E", width: 1, scale: 1, offset: 0, state: true, shared: true } as typeof sigs[number] & { shared: boolean }))];
    const laneLayout = (u: uPlot) => {
      const { top, height } = u.bbox, d = dpr() * uiScale();
      const n = stateSigs.length;
      if (onlyStates) {
        const gap = 6 * d, h = Math.min(56 * d, (height - gap * (n - 1)) / Math.max(1, n));
        return stateSigs.map((_, k) => ({ y: top + k * (h + gap), h }));
      }
      const h = laneCss(height / d, n) * d, gap = 2 * d;
      return stateSigs.map((_, k) => ({ y: top + height - (n - k) * (h + gap) + gap, h }));
    };
    /* named conditions: the one in focus shaded over the whole height; every other shown one a thin
       strip along the top, one under the other (they never hide the lines) */
    const drawConds = (u: uPlot) => {
      const list = condRef.current;
      if (!list.length && !changeRef.current.length) return;
      const ctx = u.ctx, { left, top, width, height } = u.bbox, d = dpr() * uiScale();
      const x0 = u.scales.x.min!, x1 = u.scales.x.max!;
      ctx.save();
      ctx.beginPath(); ctx.rect(left, top, width, height); ctx.clip();
      let k = 0;
      for (const c of list) {
        const row = c.focus ? -1 : k++;
        for (const [a, b] of c.iv) {
          if (b < x0 || a > x1) continue;
          const xa = Math.max(left, u.valToPos(a, "x", true)), xb = Math.min(left + width, Math.max(u.valToPos(b, "x", true), u.valToPos(a, "x", true) + 2 * d));
          ctx.fillStyle = c.color;
          if (row < 0) {
            ctx.globalAlpha = 0.13; ctx.fillRect(xa, top, xb - xa, height);
            ctx.globalAlpha = 0.9; ctx.fillRect(xa, top, xb - xa, 3 * d);
          } else {
            ctx.globalAlpha = 0.85; ctx.fillRect(xa, top + row * 5 * d, xb - xa, 4 * d);
          }
        }
      }
      ctx.restore();
      // "What changed?": where each signal of this plot first left its usual range (dashed, its colour)
      if (changeRef.current.length) {
        ctx.save();
        ctx.beginPath(); ctx.rect(left, top, width, height); ctx.clip();
        ctx.setLineDash([5 * d, 4 * d]); ctx.lineWidth = 1.5 * d;
        for (const m of changeRef.current) {
          if (m.t < x0 || m.t > x1) continue;
          const x = u.valToPos(m.t, "x", true);
          ctx.strokeStyle = m.color; ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + height); ctx.stroke();
        }
        ctx.restore();
      }
    };
    let hatch: CanvasPattern | null = null;
    const drawLogMarks = (u: uPlot) => {
      const marks = markRef.current;
      if (!marks.length) return;
      const ctx = u.ctx, { left, top, width, height } = u.bbox, d = dpr() * uiScale();
      const x0 = u.scales.x.min!, x1 = u.scales.x.max!;
      // T23: a note over a time range is a shaded span (its marker and text at the start)
      const noteCol = theme === "dark" ? "#6cb6ff" : "#0969da";
      for (const m of marks) {
        if (m.t2 === undefined || m.t2 < x0 || m.t > x1) continue;
        const a = Math.max(left, u.valToPos(m.t, "x", true)), b = Math.min(left + width, u.valToPos(m.t2, "x", true));
        if (b <= a) continue;
        ctx.save();
        ctx.globalAlpha = 0.1; ctx.fillStyle = noteCol; ctx.fillRect(a, top, b - a, height);
        ctx.globalAlpha = 0.5; ctx.strokeStyle = noteCol; ctx.lineWidth = Math.max(1, dpr());
        if (m.t2 <= x1) { const xe = Math.round(b) + 0.5; ctx.beginPath(); ctx.moveTo(xe, top); ctx.lineTo(xe, top + height); ctx.stroke(); }
        ctx.restore();
      }
      // events on the same pixels become one marker: texts joined, the most severe colour
      const rank = (l: string) => (l === "note" ? 3 : l === "error" ? 2 : l === "warning" ? 1 : 0);
      const vis: { t: number; text: string; level: string }[] = [];
      let lastX = -Infinity;
      for (const m of marks) {
        if (m.t < x0 || m.t > x1) continue;
        const px = u.valToPos(m.t, "x", true);
        const prev = vis[vis.length - 1];
        if (prev && px - lastX < 3 * d) {
          prev.text += " · " + m.text;
          if (rank(m.level) > rank(prev.level)) prev.level = m.level;
        } else { vis.push({ ...m }); lastX = px; }
      }
      if (!vis.length) return;
      ctx.save();
      ctx.beginPath(); ctx.rect(left, top, width, height); ctx.clip();
      ctx.font = `${Math.round(10.5 * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
      ctx.textBaseline = "middle"; ctx.textAlign = "left";
      const xs = vis.map((m) => Math.round(u.valToPos(m.t, "x", true)) + 0.5);
      const font = ctx.font;
      vis.forEach((m, i) => {
        const x = xs[i];
        ctx.font = font;
        const col = m.level === "note" ? (theme === "dark" ? "#6cb6ff" : "#0969da")
          : m.level === "error" ? (theme === "dark" ? "#f47067" : "#cf222e") : m.level === "warning" ? pt.amber : pt.axis;
        ctx.strokeStyle = col; ctx.lineWidth = Math.max(1, dpr());
        ctx.globalAlpha = m.level === "info" ? 0.3 : m.level === "note" ? 0.8 : 0.55;
        ctx.setLineDash(m.level === "note" ? [] : [3 * d, 3 * d]);
        ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + height); ctx.stroke();
        ctx.setLineDash([]); ctx.globalAlpha = 1;
        ctx.fillStyle = col;
        ctx.beginPath(); ctx.moveTo(x - 5 * d, top); ctx.lineTo(x + 5 * d, top); ctx.lineTo(x, top + 7 * d); ctx.closePath(); ctx.fill();
        // the text, when there is room before the next marker
        const room = (i + 1 < xs.length ? xs[i + 1] : left + width) - x - 10 * d;
        if (room < 34 * d) return;
        let txt = m.text;
        const maxW = Math.min(room, 220 * d);
        if (ctx.measureText(txt).width > maxW) {
          while (txt.length > 2 && ctx.measureText(txt + "…").width > maxW) txt = txt.slice(0, -1);
          txt += "…";
        }
        const tw = ctx.measureText(txt).width;
        ctx.globalAlpha = 0.85; ctx.fillStyle = pt.bg; ctx.fillRect(x + 4 * d, top + 3 * d, tw + 8 * d, 14 * d);
        ctx.globalAlpha = 1; ctx.fillStyle = m.level === "info" ? pt.text : col;
        if (m.level === "note") ctx.font = `600 ${Math.round(10.5 * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
        ctx.fillText(txt, x + 8 * d, top + 10 * d);
      });
      ctx.restore();
    };
    const drawStates = (u: uPlot) => {
      if (!stateSigs.length) return;
      const marks = statesRef.current;
      const ctx = u.ctx, { left, width } = u.bbox, d = dpr() * uiScale();
      if (!hatch) {
        const c = document.createElement("canvas"); c.width = c.height = Math.round(8 * dpr());
        const g = c.getContext("2d")!;
        g.strokeStyle = pt.axis; g.globalAlpha = 0.55; g.lineWidth = dpr();
        g.beginPath(); g.moveTo(0, c.height); g.lineTo(c.width, 0); g.stroke();
        hatch = ctx.createPattern(c, "repeat");
      }
      const lanes = laneLayout(u);
      ctx.save();
      ctx.beginPath(); ctx.rect(left, u.bbox.top, width, u.bbox.height); ctx.clip();
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";                  // uPlot leaves its axis alignment on the context
      stateSigs.forEach((s, k) => {
        const m = marks[s.sig];
        const { y, h } = lanes[k];
        if (!onlyStates) { ctx.fillStyle = pt.bg; ctx.globalAlpha = 0.85; ctx.fillRect(left, y, width, h); ctx.globalAlpha = 1; }
        if (!m || !m.points.length) return;
        const labels = labelsOf(runsRef.current, s.sig);
        ctx.font = `${Math.round((onlyStates ? 12 : 11) * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
        const pts = m.points;
        for (let i = 0; i < pts.length; i++) {
          const [t0, v] = pts[i];
          const t1 = i + 1 < pts.length ? pts[i + 1][0] : (m.end ?? t0);
          let x0 = u.valToPos(t0, "x", true), x1 = u.valToPos(t1, "x", true);
          if (x1 < left || x0 > left + width) continue;
          x0 = Math.max(left - 1, x0); x1 = Math.min(left + width + 1, x1);
          const w = Math.max(1, x1 - x0);
          if (v === null) {                       // too many changes here to draw one by one
            ctx.fillStyle = hatch ?? pt.grid; ctx.fillRect(x0, y, w, h);
            continue;
          }
          const col = stateColor(v, theme);
          ctx.fillStyle = col; ctx.fillRect(x0, y, w, h);
          ctx.fillStyle = pt.bg; ctx.fillRect(Math.round(x0), y, Math.max(1, Math.round(dpr())), h);   // separator
          const txt = labelText(labels, v) ?? (Number.isInteger(v * s.scale + s.offset) ? String(v * s.scale + s.offset) : fmtNum(v * s.scale + s.offset, "en", 4));
          const room = w - 8 * d;
          if (room < 10 * d || h < 11 * d) continue;       // too small for a word: the colour alone
          let shown = txt;
          if (ctx.measureText(shown).width > room) {
            while (shown.length > 1 && ctx.measureText(shown + "…").width > room) shown = shown.slice(0, -1);
            shown += "…";
            if (shown.length < 3) continue;
          }
          ctx.fillStyle = inkOn(col);
          const tw = ctx.measureText(shown).width;
          const cx = Math.min(Math.max(x0 + w / 2, left + tw / 2 + 4 * d), left + width - tw / 2 - 4 * d);
          ctx.fillText(shown, cx - tw / 2, y + h / 2 + 0.5);
        }
        // which signal this lane is: its colour along the left edge (and its name when lanes fill the plot)
        ctx.fillStyle = s.color; ctx.fillRect(left, y, 3 * d, h);
        if (onlyStates) {
          const nm = s.label || s.sig.slice(s.sig.indexOf("/") + 1);
          ctx.font = `600 ${Math.round(10.5 * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
          const tw = ctx.measureText(nm).width;
          ctx.fillStyle = pt.bg; ctx.globalAlpha = 0.82;
          ctx.fillRect(left + 3 * d, y, tw + 10 * d, 15 * d); ctx.globalAlpha = 1;
          ctx.fillStyle = pt.text; ctx.textBaseline = "middle";
          ctx.fillText(nm, left + 8 * d, y + 7.5 * d);
        }
      });
      ctx.restore();
      /* thin lanes under lines: the name in the margin left of the lane, never over the data - drawn
         over the plot it hid the last stretch of the state, which then looked like one more state
         with an unclear text. The value axis has no meaning beside the lanes (the lines are above). */
      if (!onlyStates) {
        ctx.save();
        ctx.textBaseline = "middle"; ctx.textAlign = "right";
        stateSigs.forEach((s, k) => {
          const { y, h } = lanes[k];
          const room = left - 6 * d;
          if (room < 16 * d) return;
          ctx.fillStyle = pt.bg; ctx.fillRect(0, y - d, left - 1, h + 2 * d);
          ctx.font = `${Math.round(Math.min(10, Math.max(8, h / d - 4)) * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
          let nm = s.label || s.sig.slice(s.sig.indexOf("/") + 1);
          if (ctx.measureText(nm).width > room) {
            while (nm.length > 1 && ctx.measureText(nm + "…").width > room) nm = nm.slice(0, -1);
            nm += "…";
          }
          ctx.fillStyle = pt.axis;
          ctx.fillText(nm, left - 4 * d, y + h / 2 + 0.5);
        });
        ctx.restore();
      }
    };

    const drawCursor = (u: uPlot, ctx: CanvasRenderingContext2D) => {
      const c = cursorRef.current;
      if (!c.on) return;
      const { left, top, width, height } = u.bbox;
      ctx.save();
      for (const [tv, tag] of [[c.t1, "1"], [c.dual ? c.t2 : null, "2"]] as [number | null, string][]) {
        if (tv === null) continue;
        const x = Math.round(u.valToPos(tv, "x", true)) + 0.5;
        if (x < left - 1 || x > left + width + 1) continue;
        ctx.strokeStyle = pt.amber;
        ctx.lineWidth = dpr() * (tag === "1" ? 1.5 : 1.25);
        ctx.setLineDash(tag === "1" ? [] : [5 * dpr(), 4 * dpr()]);
        ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + height); ctx.stroke();
        ctx.setLineDash([]);
        // cursor 1's flag at the top, cursor 2's at the bottom: they never overlap
        const fy = tag === "1" ? top : top + height - 17 * dpr() * uiScale();
        flag(ctx, x, fy, (c.dual ? `${tag}  ` : "") + fmtNum(tv, "en", 7), pt.amber, pt.amberInk, { left, width });
      }
      ctx.restore();
    };

    /* draw-mode playback: series are clipped at the cursor, so the plot "draws itself" */
    let clipped = false;
    // the timeline's mode: the series only up to the time ("draw") or over the last seconds ("window")
    const clipStart = (u: uPlot) => {
      const span = shownSpan({ playMode: valRef.current.playMode, windowSec: valRef.current.windowSec, cursor: cursorRef.current });
      if (!span) return;
      const { left, top, width, height } = u.bbox;
      const px = (v: number) => (Number.isFinite(v) ? Math.max(left, Math.min(left + width, u.valToPos(v, "x", true))) : left);
      const a = px(span[0]), b = px(span[1]);
      u.ctx.save();
      u.ctx.beginPath();
      u.ctx.rect(a, top, Math.max(0, b - a), height);
      u.ctx.clip();
      clipped = true;
    };
    const clipEnd = (u: uPlot) => { if (clipped) { u.ctx.restore(); clipped = false; } };

    const drawValues = (u: uPlot, ctx: CanvasRenderingContext2D) => {
      const c = cursorRef.current;
      const { cvals: cv, valuesOnPlot: on, signals } = valRef.current;
      if (!on || !c.on || c.t1 === null) return;
      const { left, width, top, height } = u.bbox;
      const x = Math.round(u.valToPos(c.t1, "x", true));
      if (x < left || x > left + width) return;
      ctx.save();
      signals.forEach((s) => {
        const raw = cv[s.sig]?.[0];
        if (raw === null || raw === undefined) return;
        if (s.state) return;                     // a lane already shows its state at every time
        const v = raw * s.scale + s.offset;
        const y = u.valToPos(v, s.axis === "right" ? "y2" : "y", true);
        if (y < top || y > top + height) return;
        ctx.beginPath(); ctx.arc(x, y, 3.5 * dpr(), 0, Math.PI * 2); ctx.fillStyle = s.color; ctx.fill();
        flag(ctx, x + 4 * dpr(), y - 9 * dpr(), labelText(labelsOf(runsRef.current, s.sig), raw) ?? fmtNum(v, "en", 5), s.color, "#ffffff", { left, width }, 0.92);
      });
      ctx.restore();
    };

    /* The cursor, its flag and the values at it live on their own canvas over the plot: moving the
       cursor clears and redraws only that, instead of every series (a full redraw per move made
       dragging and cursor playback crawl). */
    const overlay = document.createElement("canvas");
    overlay.className = "u-cursor-layer";
    overlay.style.cssText = "position:absolute;left:0;top:0;pointer-events:none";
    const octx = overlay.getContext("2d")!;
    const syncOverlay = (u: uPlot) => {
      const c = u.ctx.canvas;
      if (overlay.width !== c.width || overlay.height !== c.height) { overlay.width = c.width; overlay.height = c.height; }
      overlay.style.width = c.style.width; overlay.style.height = c.style.height;
      overlay.style.left = c.offsetLeft + "px"; overlay.style.top = c.offsetTop + "px";
    };
    /* T13: limits as dashed lines in the signal's colour (on the plotted value) */
    const drawLimits = (u: uPlot) => {
      const lim = sigs.filter((s) => !s.state && s.limits && (s.limits.lo != null || s.limits.hi != null));
      if (!lim.length) return;
      const ctx = u.ctx, { left, top, width, height } = u.bbox, d = dpr() * uiScale();
      ctx.save();
      ctx.beginPath(); ctx.rect(left, top, width, height); ctx.clip();
      ctx.setLineDash([6 * d, 4 * d]); ctx.lineWidth = 1.25 * d; ctx.globalAlpha = 0.9;
      lim.forEach((s) => [s.limits!.lo, s.limits!.hi].forEach((v) => {
        if (v == null || !Number.isFinite(v)) return;
        const y = Math.round(u.valToPos(v, s.axis === "right" ? "y2" : "y", true)) + 0.5;
        if (y < top || y > top + height) return;
        ctx.strokeStyle = s.color; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + width, y); ctx.stroke();
      }));
      ctx.restore();
    };
    /* the selection (both cursors) in the active plot: a small bar of what to do with it, above the
       middle of the span - the eyes are already there */
    const placeBar = (u: uPlot) => {
      const bar = barRef.current;
      if (!bar) return;
      const c = cursorRef.current;
      // the active plot as it is now (the plot is built once; `tab` here is from then)
      const active = useApp.getState().ws.tabs.find((x) => x.id === tab.id)?.active ?? tab.active;
      const show = !previewOnly && index >= 0 && active === index && c.on && c.dual && c.t1 !== null && c.t2 !== null && c.t1 !== c.t2;
      if (!show) { bar.hidden = true; return; }
      const a = Math.min(c.t1!, c.t2!), b = Math.max(c.t1!, c.t2!);
      const x0 = u.scales.x.min!, x1 = u.scales.x.max!;
      if (b < x0 || a > x1) { bar.hidden = true; return; }
      bar.hidden = false;
      const mid = (u.valToPos(Math.max(a, x0), "x") + u.valToPos(Math.min(b, x1), "x")) / 2 + u.over.offsetLeft;
      const w = bar.offsetWidth || 220;
      bar.style.left = `${Math.max(4, Math.min(mid - w / 2, (wrapRef.current?.clientWidth ?? w) - w - 4))}px`;
      bar.style.top = `${u.over.offsetTop + 6}px`;
    };
    const drawOverlay = (u: uPlot) => {
      placeBar(u);
      syncOverlay(u);
      octx.clearRect(0, 0, overlay.width, overlay.height);
      drawCursor(u, octx);
      drawValues(u, octx);
    };
    overlayRef.current = drawOverlay;

    let hoverIdx = -1, hoverRaf = 0;
    // T47: signals on the right axis have their own scale ("y2"), range and unit label
    const onRight = (s: PlotSignal) => s.axis === "right" && !s.state;
    const hasRight = sigs.some(onRight);
    const unitOfSig = (s: PlotSignal) => signalUnit(runsRef.current, s.sig, s.label);   // a converted signal: its new unit
    const units = sigs.filter((s) => !onRight(s) && !(hasRight && s.state)).map(unitOfSig);
    const commonUnit = units.length && units.every((x) => x && x === units[0]) ? units[0] : null;
    const rUnits = sigs.filter(onRight).map(unitOfSig);
    const rightUnit = rUnits.length && rUnits.every((x) => x && x === rUnits[0]) ? rUnits[0] : null;
    const yFixed = plot.ylim ?? (linkY && yUnion ? (yUnion.split("|").map(Number) as [number, number]) : null);
    // text values on the value axis: when every line in the plot uses the same texts (e.g. a mode)
    const lineSigs = sigs.filter((s) => !s.state && !onRight(s));
    const lineLabels = lineSigs.map((s) => (s.scale === 1 && s.offset === 0 ? labelsOf(runsRef.current, s.sig) : undefined));
    const axisLabels = lineLabels.length && lineLabels.every((l) => l && JSON.stringify(l) === JSON.stringify(lineLabels[0])) ? lineLabels[0]! : null;
    const axisCodes = axisLabels ? Object.keys(axisLabels).map(Number).sort((a, b) => a - b) : [];
    const longest = axisLabels ? Math.max(...Object.values(axisLabels).map((v) => v.length)) : 0;
    const laneFrac = () => {                     // share of the plot height the bottom lanes take
      if (!stateSigs.length || onlyStates) return 0;
      const plotH = Math.max(60, size.h - 50);
      return Math.min(0.6, (stateSigs.length * (laneCss(plotH, stateSigs.length) + 2) + 4) / plotH);
    };
    // T50: a short plot (many plots in a small window) kept one value label ("0"): the labels may
    // come closer there, so there are about four of them
    const valueSpace = (_u: uPlot, _i: number, _mn: number, _mx: number, dim: number) => Math.max(12, Math.min(30, dim / 4));
    const yAxis: uPlot.Axis = onlyStates
      ? { ...axis, size: 12, values: () => [], ticks: { show: false }, grid: { show: false } }
      : axisLabels && axisCodes.length <= 40
        ? { ...axis, size: Math.min(150, 18 + longest * 7.2),
            splits: (_u, _i, mn, mx) => axisCodes.filter((c) => c >= mn && c <= mx),
            values: (_u, splits) => splits.map((v) => axisLabels[String(v)] ?? String(v)) }
        : { ...axis, size: commonUnit ? 64 : 56, values: tickValues, space: valueSpace, ...(commonUnit ? { label: commonUnit, labelSize: 14, labelGap: 0 } : {}) };
    // F24: the column's plots share the room left and right of the plot area, so their time axes line up
    // (uPlot puts an axis label's labelSize next to the axis size: both count)
    const rightSize = hasRight ? (rightUnit ? 64 : 56) : 0, rightLabel = hasRight && rightUnit ? 14 : 0;
    const leftLabel = yAxis.label ? (yAxis.labelSize ?? 0) : 0;
    const natL = 4 + (yAxis.size as number) + leftLabel, natR = 12 + rightSize + rightLabel;
    if (!previewOnly) reportGutter(plot.id, natL, natR);
    const useL = previewOnly ? natL : Math.max(natL, gutter[0]), useR = previewOnly ? natR : Math.max(natR, gutter[1]);
    yAxis.size = useL - 4 - leftLabel;
    const opts: uPlot.Options = {
      width: size.w,
      height: size.h,
      padding: [8, useR - rightSize - rightLabel, 0, 4],
      legend: { show: false },
      cursor: { y: false, points: { size: 6 },
        // zoom by dragging: a time window, a value window, or a box (a nearly flat drag zooms one axis)
        drag: { x: zoomMode !== "y", y: zoomMode !== "x", uni: zoomMode === "xy" ? 20 : undefined, setScale: false } },
      scales: {
        // the time window is read when drawing (the plot is no longer rebuilt for each new window)
        x: { time: false, auto: () => !rangeRef.current,
          range: (_u, mn, mx): uPlot.Range.MinMax => (rangeRef.current ? [rangeRef.current[0], rangeRef.current[1]] : [mn, mx]) },
        y: {
          // a value zoom or fixed limits keep the axis still while the time window changes
          auto: () => !yZoomRef.current && !yFixed,
          range: (_u, mn, mx): uPlot.Range.MinMax => {
            const z = yZoomRef.current;
            if (z) return [z[0], z[1]];
            if (yFixed) {
              const pad = (yFixed[1] - yFixed[0]) * (plot.ylim ? 0 : 0.04);
              return [yFixed[0] - pad, yFixed[1] + pad];
            }
            if (!Number.isFinite(mn) || !Number.isFinite(mx)) return [0, 1];
            if (axisLabels && axisCodes.length) { mn = Math.min(mn, axisCodes[0]); mx = Math.max(mx, axisCodes[axisCodes.length - 1]); }
            const r = uPlot.rangeNum(mn, mx, 0.1, true) as [number, number];
            const f = laneFrac();
            if (f > 0) r[0] -= ((r[1] - r[0]) * f) / (1 - f);      // room for the state lanes at the bottom
            return r;
          },
        },
        ...(hasRight ? {
          y2: {
            auto: true,
            range: (_u: uPlot, mn: number, mx: number): uPlot.Range.MinMax => {
              if (!Number.isFinite(mn) || !Number.isFinite(mx)) return [0, 1];
              const r = uPlot.rangeNum(mn, mx, 0.1, true) as [number, number];
              const f = laneFrac();
              if (f > 0) r[0] -= ((r[1] - r[0]) * f) / (1 - f);
              return r;
            },
          },
        } : {}),
      },
      axes: [{ ...axis, size: 34 }, yAxis,
        ...(hasRight ? [{ ...axis, scale: "y2", side: 1, size: rightSize, values: tickValues, space: valueSpace, grid: { show: false },
          ...(rightUnit ? { label: rightUnit, labelSize: 14, labelGap: 0 } : {}) } as uPlot.Axis] : [])],
      series: [
        {},
        ...sigs.map((s, k) => ({
          stroke: s.color,
          scale: onRight(s) ? "y2" : "y",
          width: lineWidth(aligned, k),
          spanGaps: false,
          points: { show: false },
          show: !s.state,                       // a state signal is drawn as a lane (no line)
          // states and text values hold until the next change: draw them as steps
          ...(s.state || labelsOf(runsRef.current, s.sig) ? { paths: uPlot.paths.stepped!({ align: 1 }) } : {}),
        })),
        // preview lines: one neutral colour, told apart by their dash (axis 1, 2, 3 of a frame conversion)
        ...aligned.previewLabels.map((label, k) => ({ stroke: PLOT_THEME[theme].axis, width: 1.5, dash: PREVIEW_DASH[k % PREVIEW_DASH.length],
          spanGaps: false, points: { show: false }, label })),
      ],
      hooks: {
        setCursor: [
          (u) => {
            const idx = u.cursor.idx;
            if (idx === null || idx === undefined || cursorRef.current.on) {
              if (useApp.getState().hover?.plotId === plot.id) useApp.setState({ hover: null });
              return;
            }
            if (hoverIdx === idx) return;
            hoverIdx = idx;
            if (hoverRaf) return;
            hoverRaf = requestAnimationFrame(() => {
              hoverRaf = 0;
              const i = hoverIdx;
              const xs = u.data[0] as number[];
              const vals: Record<string, number | null> = {};
              sigs.forEach((s, k) => {
                const ys = u.data[k + 1] as (number | null | undefined)[];
                // joined series have gaps where other series have samples: take the nearest real one
                let v: number | null | undefined = ys[i];
                for (let d = 1; (v === undefined) && d < 64; d++) v = ys[i - d] ?? ys[i + d];
                vals[s.sig] = v ?? null;
              });
              useApp.setState({ hover: { plotId: plot.id, t: xs[i], vals } });
            });
          },
        ],
        drawAxes: [clipStart],
        draw: [clipEnd, drawConds, drawStates, drawLimits, drawLogMarks, (u) => drawOverlay(u)],
        setSize: [(u) => syncOverlay(u)],
        setSelect: [
          (u) => {
            const sel = { ...u.select };           // a copy: setSelect below resets u.select itself
            const W = u.over.clientWidth, H = u.over.clientHeight;
            const g = gestRef.current;                 // this drag's mode (the zoom mode, or by its modifier key)
            const useX = g !== "y" && sel.width >= 4 && sel.width < W - 1;
            const useY = g !== "x" && sel.height >= 4 && sel.height < H - 1;
            u.setSelect({ left: 0, top: 0, width: 0, height: 0 }, false);
            if (!useX && !useY) return;
            const xr: Range | undefined = useX ? [u.posToVal(sel.left, "x"), u.posToVal(sel.left + sel.width, "x")] : undefined;
            const yr: Range | undefined = useY ? [u.posToVal(sel.top + sel.height, "y"), u.posToVal(sel.top, "y")] : undefined;
            actions.setView(key, xr, yKey, yr);
          },
        ],
      },
    };
    const u = new uPlot(opts, aligned.data, host);
    uRef.current = u;
    u.ctx.canvas.after(overlay);
    drawOverlay(u);
    u.over.addEventListener("mouseleave", () => { if (useApp.getState().hover?.plotId === plot.id) useApp.setState({ hover: null }); });

    /* wheel: over the value axis -> values only; over the time axis -> time only; inside the plot ->
       the zoom mode (X / Y / XY); for one gesture Shift = values only, Ctrl / Cmd = both, Alt = time
       only - the same keys as for dragging (T19) */
    let lastWheel = 0;
    const onWheel = (e: WheelEvent) => {
      const rect = u.over.getBoundingClientRect();
      const onYAxis = e.clientX < rect.left || e.clientX > rect.right;
      const onXAxis = e.clientY > rect.bottom;
      if (!onYAxis && !onXAxis && (e.clientY < rect.top)) return;
      e.preventDefault();
      // F27: one gesture (a trackpad sends dozens of events) is one step back with Backspace
      const now = performance.now(), history = now - lastWheel > WHEEL_GESTURE_MS;
      lastWheel = now;
      const f = wheelZoom(e);
      if (f === null) {
        // a sideways swipe / tilt wheel moves along the time axis (it zoomed out before)
        const { dx } = wheelPixels(e);
        if (!dx || onYAxis) return;
        const min = u.scales.x.min!, max = u.scales.x.max!;
        const dv = (dx / Math.max(1, rect.width)) * (max - min);
        actions.setView(key, [min + dv, max + dv], yKey, undefined, { history });
        return;
      }
      let doX = zoomMode !== "y", doY = zoomMode !== "x";
      if (onYAxis || e.shiftKey) { doX = false; doY = true; }
      else if (onXAxis || e.altKey) { doX = true; doY = false; }
      else if (e.ctrlKey || e.metaKey) { doX = true; doY = true; }
      let xr: Range | undefined, yr: Range | undefined;
      if (doX) {
        const xv = u.posToVal(Math.min(rect.width, Math.max(0, e.clientX - rect.left)), "x");
        const min = u.scales.x.min!, max = u.scales.x.max!;
        xr = [xv - (xv - min) * f, xv + (max - xv) * f];
      }
      if (doY && !onlyStates) {
        const yv = u.posToVal(Math.min(rect.height, Math.max(0, e.clientY - rect.top)), "y");
        const min = u.scales.y.min!, max = u.scales.y.max!;
        yr = [yv - (yv - min) * f, yv + (max - yv) * f];
      }
      if (xr || yr) actions.setView(key, xr, yKey, yr, { history });
    };
    const onDbl = () => actions.setView(key, null, yKey, null);
    // T49 item 12: a right-click hands the moment under the pointer to the plot's menu (PlotView)
    const onCtx = (e: MouseEvent) => {
      const rect = u.over.getBoundingClientRect();
      (e as MouseEvent & { svTime?: number }).svTime = u.posToVal(e.clientX - rect.left, "x");
      const lane = laneAt(e);                          // a lane's own menu: where it is shown (PlotView)
      if (lane) (e as MouseEvent & { svLane?: string }).svLane = lane.sig;
    };
    u.over.addEventListener("contextmenu", onCtx);
    host.addEventListener("wheel", onWheel, { passive: false });
    // hovering a lane: its name, the state there and its stretch, and where the lane is shown
    const laneAt = (e: MouseEvent): { sig: string; k: number } | null => {
      if (!stateSigs.length) return null;
      const rect = u.over.getBoundingClientRect();
      const yc = (e.clientY - rect.top) * dpr() + u.bbox.top;
      const k = laneLayout(u).findIndex((l) => yc >= l.y && yc <= l.y + l.h);
      return k < 0 ? null : { sig: stateSigs[k].sig, k };
    };
    const laneTip = (e: MouseEvent): string => {
      const lane = laneAt(e);
      if (!lane) return "";
      const s = stateSigs[lane.k];
      const st = useApp.getState();
      const nm = s.label || s.sig.slice(s.sig.indexOf("/") + 1);
      const scope = (st.ws.globalStates ?? []).includes(s.sig) ? translate(st.lang, "laneTipAll")
        : (tab.sharedStates ?? []).includes(s.sig) ? translate(st.lang, "laneTipTab") : "";
      const m = statesRef.current[s.sig];
      const tv = u.posToVal(e.clientX - u.over.getBoundingClientRect().left, "x");
      let what = "";
      if (m) for (let i = m.points.length - 1; i >= 0; i--) {
        if (m.points[i][0] <= tv) {
          const v = m.points[i][1], b = i + 1 < m.points.length ? m.points[i + 1][0] : (m.end ?? m.points[i][0]);
          if (v !== null) what = `${labelText(labelsOf(runsRef.current, s.sig), v) ?? fmtNum(v, "en", 6)} · ${fmtNum(m.points[i][0], "en", 6)}–${fmtNum(b, "en", 6)} s`;
          break;
        }
      }
      return [nm + (what ? `: ${what}` : ""), scope].filter(Boolean).join(" · ");
    };
    // hovering a log marker shows its full text
    const onMoveTip = (e: MouseEvent) => {
      const lt = laneTip(e);
      if (lt) { if (u.over.title !== lt) u.over.title = lt; return; }
      if (!markRef.current.length) { if (u.over.title) u.over.title = ""; return; }
      const x = e.clientX - u.over.getBoundingClientRect().left;
      let best: { t: number; text: string } | null = null, bd = 6;
      for (const m of markRef.current) {
        const dd = Math.abs(u.valToPos(m.t, "x") - x);
        if (dd < bd) { bd = dd; best = m; }
      }
      const tip = best ? `${fmtNum(best.t, "en", 7)} s · ${best.text}` : "";
      if (u.over.title !== tip) u.over.title = tip;
    };
    u.over.addEventListener("mousemove", onMoveTip);
    u.over.addEventListener("dblclick", onDbl);

    /* cursor: click to place, drag the line to move (capture phase beats uPlot's drag-zoom) */
    let downX = 0;
    const posOf = (e: MouseEvent) => e.clientX - u.over.getBoundingClientRect().left;
    /* a click on a state lane picks that stretch of the state: both cursors on its edges (the
       statistics then cover exactly it); Shift+click also zooms to it */
    let laneClick = false;
    const laneHit = (e: MouseEvent): { a: number; b: number } | null => {
      if (!stateSigs.length || e.button !== 0) return null;
      const rect = u.over.getBoundingClientRect();
      const d = dpr();
      const yc = (e.clientY - rect.top) * d + u.bbox.top, xc = (e.clientX - rect.left) * d + u.bbox.left;
      if (e.clientX < rect.left || e.clientX > rect.right) return null;
      const lanes = laneLayout(u);
      const k = lanes.findIndex((l) => yc >= l.y && yc <= l.y + l.h);
      if (k < 0) return null;
      const m = statesRef.current[stateSigs[k].sig];
      if (!m || !m.points.length) return null;
      const tv = u.posToVal((xc - u.bbox.left) / d, "x");
      for (let i = m.points.length - 1; i >= 0; i--) {
        if (m.points[i][0] <= tv) {
          const b = i + 1 < m.points.length ? m.points[i + 1][0] : (m.end ?? m.points[i][0]);
          return m.points[i][1] === null ? null : { a: m.points[i][0], b };
        }
      }
      return null;
    };
    const onDown = (e: MouseEvent) => {
      if (index >= 0) actions.setActivePlot(index);
      downX = e.clientX;
      const seg = laneHit(e);
      if (seg && seg.b > seg.a) {
        e.stopPropagation(); e.preventDefault();
        laneClick = true;                          // the mouseup that follows must not move the cursor
        if (e.shiftKey) actions.showSpan(seg.a, seg.b);
        else {
          const c = useApp.getState().cursor;
          useApp.setState({ cursor: { ...c, on: true, dual: true, t1: seg.a, t2: seg.b, active: 1 } });
        }
        return;
      }
      // T19: a drag zooms by the zoom mode, or for this one gesture Shift = values (Y), Ctrl / Cmd =
      // a box (XY); uPlot reads these drag settings live, the selection rectangle follows
      const g: "x" | "y" | "xy" = e.shiftKey ? "y" : e.ctrlKey || e.metaKey ? "xy" : zoomMode;
      gestRef.current = g;
      u.cursor.drag!.x = g !== "y"; u.cursor.drag!.y = g !== "x"; u.cursor.drag!.uni = g === "xy" ? 20 : undefined;
      if (e.altKey && !cursorRef.current.on || e.button === 1) {       // pan (Alt + drag, or the middle button)
        e.stopPropagation(); e.preventDefault();
        // pan follows the zoom mode: time, values, or both
        const panX = zoomMode !== "y", panY = zoomMode !== "x" && !onlyStates;
        const x0 = e.clientX, y0 = e.clientY, min0 = u.scales.x.min!, max0 = u.scales.x.max!;
        const ymin0 = u.scales.y.min!, ymax0 = u.scales.y.max!;
        const rect0 = u.over.getBoundingClientRect();
        const w = rect0.width || 1, h = rect0.height || 1;
        const st0 = useApp.getState();
        const before = st0.ranges[key] ?? null, beforeY = st0.yRanges[yKey] ?? null;
        let moved = false;
        const move = (ev: MouseEvent) => {
          const dx = ((x0 - ev.clientX) / w) * (max0 - min0);
          const dy = ((ev.clientY - y0) / h) * (ymax0 - ymin0);
          moved = true;
          actions.setView(key, panX ? [min0 + dx, max0 + dx] : undefined, yKey, panY ? [ymin0 + dy, ymax0 + dy] : undefined, { history: false });
        };
        const up = () => {
          window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up);
          if (moved) actions.pushZoomStep(key, { x: before, ...(panY ? { y: { key: yKey, r: beforeY } } : {}) });   // one step per gesture
        };
        window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
        return;
      }
      const c = cursorRef.current;
      if (!c.on || e.button !== 0) return;
      const px = posOf(e);
      const near = (tv: number | null) => tv !== null && Math.abs(u.valToPos(tv, "x") - px) < 7;
      const dragging: "t1" | "t2" | null = near(c.t1) ? "t1" : c.dual && near(c.t2) ? "t2" : null;
      if (!dragging) return;
      e.stopPropagation();
      e.preventDefault();
      useApp.setState({ cursor: { ...useApp.getState().cursor, active: dragging === "t2" ? 2 : 1 } });
      const move = (ev: MouseEvent) =>
        useApp.setState({ cursor: { ...useApp.getState().cursor, [dragging]: u.posToVal(posOf(ev), "x") } });
      const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    };
    const onUp = (e: MouseEvent) => {
      if (laneClick) { laneClick = false; return; }
      const c = cursorRef.current;
      if (!c.on || Math.abs(e.clientX - downX) > 3 || e.button !== 0) return;
      const v = u.posToVal(posOf(e), "x");
      if (e.shiftKey || (c.dual && c.t2 !== null && c.t1 !== null && Math.abs(v - c.t2) < Math.abs(v - c.t1))) {
        useApp.setState({ cursor: { ...c, dual: true, t2: v, active: 2 } });
      } else useApp.setState({ cursor: { ...c, t1: v, active: 1 } });
    };
    host.addEventListener("mousedown", onDown, true);
    u.over.addEventListener("mouseup", onUp);
    return () => {
      host.removeEventListener("mousedown", onDown, true);
      host.removeEventListener("wheel", onWheel);
      u.destroy();
      uRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structKey, theme, scale, size.w > 0 && size.h > 0, plot.ylim?.[0], plot.ylim?.[1], linkY, yUnion, zoomMode, stateKey, labelsKey, gutter[0], gutter[1]]);

  /* new data for the same series: into the existing plot (no rebuild) */
  useEffect(() => {
    const u = uRef.current;
    if (!u || !aligned || builtWith.current === aligned) return;
    builtWith.current = aligned;
    aligned.sigs.forEach((_s, k) => { if (u.series[k + 1]) u.series[k + 1].width = lineWidth(aligned, k); });
    u.setData(aligned.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aligned]);

  useEffect(() => { uRef.current?.setSize({ width: size.w, height: size.h }); }, [size]);
  useEffect(() => {
    const u = uRef.current;
    if (u && range) u.setScale("x", { min: range[0], max: range[1] });
  }, [range?.[0], range?.[1]]);
  // cursor / values: only the overlay - except in draw-mode playback, where the series are cut at the cursor
  useEffect(() => {
    const u = uRef.current;
    if (!u) return;
    if (playMode !== "cursor" && cursor.on) u.redraw(false);
    else overlayRef.current?.(u);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cursor, cvals, valuesOnPlot]);
  useEffect(() => { uRef.current?.redraw(false); }, [states, playMode, windowSec]);
  useEffect(() => {
    const rids = new Set(sigIds.map((id) => id.slice(0, id.indexOf("/"))));
    const shown = (conditions ?? []).filter((c) => c.visible);
    condRef.current = shown.map((c) => ({ color: c.color, focus: c.id === condFocus,
      iv: Object.entries(condResults[c.id] ?? {}).filter(([rid]) => rids.has(rid)).flatMap(([, r]) => r.intervals ?? []) }))
      .sort((p, q) => Number(p.focus) - Number(q.focus));
    // a selection made on the overview strip: shaded like the condition in focus, in its run's plots
    if (stripSel && rids.has(stripSel.rid)) condRef.current = [...condRef.current.map((c) => ({ ...c, focus: false })), { color: "#E5534B", focus: true, iv: stripSel.iv }];
    uRef.current?.redraw(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conditions, condResults, condFocus, stripSel, sigIds.join("|")]);
  useEffect(() => {
    changeRef.current = changeMarks ? plot.signals.filter((s) => changeMarks[s.sig] !== undefined).map((s) => ({ t: changeMarks[s.sig], color: s.color })) : [];
    uRef.current?.redraw(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [changeMarks, sigIds.join("|")]);
  useEffect(() => {
    const out: { t: number; t2?: number; text: string; level: string }[] = [];
    if (logMarkers !== "off") {
      for (const rid of new Set(sigIds.map((id) => id.slice(0, id.indexOf("/"))))) {
        const L = logs[rid];
        if (!L) continue;
        for (const e of L.events) {
          if (e.kind === "mode") continue;                // modes already have their lane
          if (logMarkers === "important" && e.level === "info") continue;
          out.push({ t: e.t + (L.timeOffset || 0), text: e.text, level: e.level });
        }
      }
    }
    for (const n of notes ?? []) out.push({ t: n.t, t2: n.t2, text: "✎ " + n.text, level: "note" });   // the user's notes (T23: t2 = a range)
    out.sort((a, b) => a.t - b.t);
    markRef.current = out;
    uRef.current?.redraw(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logs, logMarkers, sigIds.join("|"), notes]);
  /* value zoom changed (wheel, drag, Backspace, R): move the value axis without rebuilding the plot */
  useEffect(() => {
    const u = uRef.current;
    if (!u) return;
    if (yZoom) u.setScale("y", { min: yZoom[0], max: yZoom[1] });
    else if (plot.ylim) u.setScale("y", { min: plot.ylim[0], max: plot.ylim[1] });
    else u.setScale("x", { min: u.scales.x.min!, max: u.scales.x.max! });   // re-runs the automatic value range
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [yZoom?.[0], yZoom?.[1]]);

  // "Find similar": a condition from the selection. Of the signals on this tab's time plots, the one
  // most unusual inside the selection (the server reads each one's usual level before it) - not just
  // this plot's first line, which is often not what the user marked. Without an answer: this plot's
  // first line, above (or below) half way from its level before the selection to its peak inside it.
  const findSimilar = async () => {
    const c = useApp.getState().cursor;
    if (c.t1 === null || c.t2 === null) return;
    const a = Math.min(c.t1, c.t2), b = Math.max(c.t1, c.t2);
    const tb = activeTab(useApp.getState().ws);
    const sigs = [...new Set(tb.plots.filter((p) => (p.mode ?? "time") === "time")
      .flatMap((p) => p.signals.filter((s) => !s.state).map((s) => s.sig)))];
    try {
      const s = await api.suggestCondition(a, b, sigs);
      if (s.id && s.text && s.name) {
        useApp.setState({ panel: "investigate", condEdit: { id: "new", draft: { name: `${s.name} ${s.up ? "↑" : "↓"}`, text: s.text } } });
        return;
      }
    } catch { /* this plot's own line, below */ }
    findSimilarHere(a, b);
  };
  const findSimilarHere = (a: number, b: number) => {
    const u = uRef.current;
    if (!u) return;
    const w = b - a;
    const xs = u.data[0] as number[];
    const k = plot.signals.findIndex((x) => !x.state);
    const ps = plot.signals[k];
    const draft: { name?: string; text?: string } = {};
    if (ps) {
      const ys = u.data[k + 1] as (number | null)[];
      const inside: number[] = [], before: number[] = [];
      xs.forEach((x, i) => { const v = ys?.[i]; if (v === null || v === undefined || !Number.isFinite(v)) return;
        if (x >= a && x <= b) inside.push(v); else if (x >= a - w && x < a) before.push(v); });
      const name = ps.sig.slice(ps.sig.indexOf("/") + 1);
      const ref = /^[A-Za-z_][\w.]*$/.test(name) ? name : `{${name}}`;
      if (inside.length) {
        const base = before.length ? before.reduce((p, q) => p + q, 0) / before.length : Math.min(...inside);
        const hi = Math.max(...inside), lo = Math.min(...inside);
        const up = hi - base >= base - lo;
        const th = up ? base + (hi - base) / 2 : base - (base - lo) / 2;
        draft.text = `${ref} ${up ? ">" : "<"} ${Number(th.toPrecision(4))}`;
      } else draft.text = `${ref} > `;
      draft.name = `${name} ${draft.text.includes(">") ? "↑" : "↓"}`;
    }
    useApp.setState({ panel: "investigate", condEdit: { id: "new", draft } });
  };

  return (
    <div className="plot-canvas" ref={wrapRef}>
      <div ref={barRef} className="sel-bar" hidden role="toolbar" aria-label={translate(useApp.getState().lang, "selBar")}
        onMouseDown={(e) => e.stopPropagation()}>
        <button className="btn sm" onClick={() => actions.addNoteAtCursor()}>✎ {translate(useApp.getState().lang, "selNote")}</button>
        <button className="btn sm sel-find" onClick={findSimilar}>⌕ {translate(useApp.getState().lang, "selFindSimilar")}</button>
        <button className="btn sm sel-changed" onClick={() => {
          const c = useApp.getState().cursor;
          if (c.t1 === null || c.t2 === null) return;
          useApp.setState({ panel: "investigate", whatChanged: { a: Math.min(c.t1, c.t2), b: Math.max(c.t1, c.t2) } });
        }}>? {translate(useApp.getState().lang, "selWhatChanged")}</button>
      </div>
    </div>
  );
}
