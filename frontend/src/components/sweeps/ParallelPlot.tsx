/* The parallel plot: a vertical axis per column, a line per parameter set (or per run).

   Drawing: the lines in two layers drawn a frame at a time, put together on one canvas under the axes,
   filters, hover and the open set (see "Three layers" below); the axis names are buttons over it (their menu:
   scale, colour, reverse, hide, ranges). On an axis: drag = keep that range, Shift-drag = keep
   another range too, click = clear. Elsewhere: hover shows a line's values, click picks it.
   Zoom (owner, 2026-11-02 - to pick one line where they are dense): the wheel and the + / − / Reset
   buttons of the page around it (`zoom`, `onZoom`); dragging the empty plot pans while zoomed.
   Everything the plot keeps or shows comes in as props - the store owns it (sweeps/state.ts). */
import { useEffect, useMemo, useRef, useState } from "react";
import { category, FAILS, FLAG_COLS, HOLDS, ramp } from "../../sweeps/colors";
import { hasFilter, keptMask } from "../../sweeps/filters";
import type { Col, Density, Filter, Scale } from "../../sweeps/model";
import { labelOf, makeScale, type AxisScale } from "../../sweeps/scales";
import { NO_ZOOM, zoomAt, type Zoom } from "../../sweeps/zoom";
import { drawOrder, runProgressive, type Pass } from "../../sweeps/progressive";

export interface ParallelPlotProps {
  cols: Map<string, Col>;
  n: number;
  axes: string[];
  scaleOf: (name: string) => Scale;
  reversed: Record<string, boolean>;
  colorBy: string | null;
  filters: Record<string, Filter>;
  /** the rows left, when something else decides it (Explore's draft, S23): the filters are then
   *  only drawn; missing: the rows the filters keep */
  keep?: Uint8Array | null;
  /** above the cap (1.29): every run counted per cell of each pair of axes, drawn as shaded bands under the lines
   *  (which are then the outliers and the open set); null: every run is a line */
  density?: Density | null;
  /** how many runs the filters keep in the whole table, when not every run is a line here */
  keptTotal?: number;
  /** rows drawn on top, thick (the set open on the right; in runs mode all its runs) */
  highlight: Uint8Array | null;
  labelOf: (name: string) => string;
  onPick: (row: number) => void;
  onFilter: (name: string, f: Filter | null) => void;
  onAxisMenu: (name: string, at: DOMRect) => void;
  /** an axis's name dragged to another place */
  onMoveAxis: (from: string, toIndex: number) => void;
  height?: number;
  /** every axis in the width on screen; otherwise each axis gets MIN_AXIS and the plot scrolls sideways */
  fit?: boolean;
  /** the slider's words: axes a to b of n are on screen */
  sliderLabel?: (a: number, b: number, n: number) => string;
  /** a click on an axis's name (the Data step: colour by it); its menu is then on right-click */
  onAxisClick?: (name: string) => void;
  /** zoomed in: k times, moved by x, y pixels; with onZoom the wheel zooms and a drag pans */
  zoom?: Zoom;
  onZoom?: (z: Zoom) => void;
}


/** room for an axis's ticks and name: below it the names are cut and the ticks run into each other */
const MIN_AXIS = 110;
/** the tooltip: a line per axis, in columns when there are many */
const TIP_ROW = 18, TIP_COL = 220;
const PAD_X = 56, PAD_TOP = 40, PAD_BOTTOM = 34, MISSING_GAP = 14, NEAR_AXIS = 12, HOVER_PX = 6;
/** above this many lines they are drawn at 1 px per CSS pixel (see the layers below) */
const MANY_LINES = 20000;
/** the drawing's share of a frame: the page still answers the pointer while lines are drawn */
const FRAME_BUDGET_MS = 6;
/** lines per stroke: small enough that a chunk stays well inside the budget on a slow machine */
const LINES_PER_CHUNK = 500;

export default function ParallelPlot(p: ParallelPlotProps) {
  const scroller = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [viewW, setViewW] = useState(800);
  const [scrollX, setScrollX] = useState(0);
  const height = p.height ?? 360;
  const [hover, setHover] = useState<{ row: number; x: number; y: number } | null>(null);
  const [brush, setBrush] = useState<{ axis: number; y0: number; y1: number; add: boolean } | null>(null);
  const [dragAxis, setDragAxis] = useState<{ name: string; x0: number; x: number } | null>(null);
  const z = p.zoom ?? NO_ZOOM;
  const [pan, setPan] = useState<{ x0: number; y0: number; z: Zoom; moved: boolean } | null>(null);
  const zoomRef = useRef({ z, on: p.onZoom });
  zoomRef.current = { z, on: p.onZoom };

  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setViewW(Math.max(320, el.clientWidth)));
    ro.observe(el);
    // the wheel moves the plot sideways when it is wider than the screen (it has nothing to scroll
    // up or down); at either end the page scrolls as usual. Shift + wheel is the browser's own.
    const wheel = (e: WheelEvent) => {
      const zr = zoomRef.current;
      // zoom around the pointer - when the plot is wider than the screen the wheel still moves it
      // sideways (S13) and Ctrl + wheel zooms
      const wide = el.scrollWidth > el.clientWidth + 1;
      if (zr.on && !e.shiftKey && (!wide || e.ctrlKey) && Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        const cv = canvas.current;
        if (!cv) return;
        e.preventDefault();
        const r = cv.getBoundingClientRect();
        zr.on(zoomAt(zr.z, e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX - r.left, e.clientY - r.top));
        return;
      }
      if (e.shiftKey || el.scrollWidth <= el.clientWidth + 1 || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
      const dx = e.deltaY * (e.deltaMode === 1 ? 32 : e.deltaMode === 2 ? el.clientWidth : 1);
      const max = el.scrollWidth - el.clientWidth;
      if ((dx < 0 && el.scrollLeft <= 0) || (dx > 0 && el.scrollLeft >= max - 1)) return;
      e.preventDefault();
      el.scrollLeft = Math.max(0, Math.min(max, el.scrollLeft + dx));
    };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => { ro.disconnect(); el.removeEventListener("wheel", wheel); };
  }, []);

  const plotH = height - PAD_TOP - PAD_BOTTOM - MISSING_GAP;
  const k = p.axes.length;
  const width = p.fit ? viewW : Math.max(viewW, 2 * PAD_X + Math.max(0, k - 1) * MIN_AXIS);
  const axisX = (i: number) => (k <= 1 ? width / 2 : PAD_X + (i * (width - 2 * PAD_X)) / (k - 1));
  const missingY = PAD_TOP + plotH + MISSING_GAP;

  // scales and each row's y on each axis
  const scales = useMemo(() => p.axes.map((a) => {
    const c = p.cols.get(a)!;
    return makeScale(c, p.scaleOf(a), !!p.reversed[a]);
  }), [p.axes, p.cols, p.scaleOf, p.reversed]);
  const ys = useMemo(() => p.axes.map((a, i) => {
    const v = p.cols.get(a)!.values, sc = scales[i], out = new Float32Array(p.n);
    for (let r = 0; r < p.n; r++) {
      const t = sc.norm(v[r]);
      out[r] = Number.isFinite(t) ? PAD_TOP + (1 - t) * plotH : missingY;
    }
    return out;
  }), [p.axes, p.cols, scales, p.n, plotH, missingY]);
  const kept = useMemo(() => p.keep ?? keptMask(p.cols, p.filters, p.n), [p.keep, p.cols, p.filters, p.n]);
  const keptCount = useMemo(() => kept.reduce((a, b) => a + b, 0), [kept]);

  // the order lines are drawn in: shuffled, so a picture drawn in part already looks like the whole
  const order = useMemo(() => drawOrder(p.n), [p.n]);
  // a colour per row, as buckets of rows (one stroke per colour)
  const buckets = useMemo(() => {
    const groups = new Map<string, number[]>();
    const put = (key: string, r: number) => { let g = groups.get(key); if (!g) groups.set(key, (g = [])); g.push(r); };
    const c = p.colorBy ? p.cols.get(p.colorBy) : undefined;
    let colour: (r: number) => string;
    if (!c) colour = () => HOLDS;
    else if (FLAG_COLS.has(p.colorBy!)) colour = (r) => (c.values[r] === 1 ? HOLDS : FAILS);
    else if (c.kind === "cat") colour = (r) => category(c.values[r]);
    else {
      const sc: AxisScale = makeScale(c, p.scaleOf(c.name) === "log" ? "log" : "linear");
      colour = (r) => ramp(Math.round(sc.norm(c.values[r]) * 31) / 31);
    }
    for (let j = 0; j < p.n; j++) { const r = order[j]; if (kept[r]) put(colour(r), r); }
    // the holding sets last: drawn on top
    return [...groups.entries()].sort((a, b) => (a[0] === HOLDS ? 1 : 0) - (b[0] === HOLDS ? 1 : 0));
  }, [p.colorBy, p.cols, p.n, kept, p.scaleOf, order]);
  const leftOut = useMemo(() => {
    const out = new Int32Array(p.n - keptCount);
    let k2 = 0;
    for (let j = 0; j < p.n; j++) { const r = order[j]; if (!kept[r]) out[k2++] = r; }
    return out;
  }, [order, kept, keptCount, p.n]);
  const lit = useMemo(() => {
    const out: number[] = [];
    if (p.highlight) for (let r = 0; r < p.n; r++) if (p.highlight[r]) out.push(r);
    return out;
  }, [p.highlight, p.n]);
  // each axis's histogram of the kept lines - once per filter, not per hover
  // a density picture's cells as places on the plot: per pair of neighbouring axes on screen, each cell's y on
  // either axis, its count and colour series - kept and left out apart
  const dens = useMemo(() => {
    const d = p.density;
    if (!d) return null;
    const cy = d.axes.map((a) => {
      const i = p.axes.indexOf(a.column);
      if (i < 0) return null;
      const sc = scales[i];
      return { i, y: [...a.centers.map((v) => { const t = sc.norm(v); return Number.isFinite(t) ? PAD_TOP + (1 - t) * plotH : missingY; }), missingY],
        band: Math.max(1, Math.min(3, (plotH / Math.max(1, a.centers.length)) * 0.6)) };
    });
    const pairs: { ia: number; ya: number[]; yb: number[]; band: number; kept: Density["pairs"][number]["kept"]; out: Density["pairs"][number]["out"] }[] = [];
    d.pairs.forEach((pr, j) => {
      const A = cy[j], B = cy[j + 1];
      if (A && B && B.i === A.i + 1) pairs.push({ ia: A.i, ya: A.y, yb: B.y, band: Math.min(A.band, B.band), kept: pr.kept, out: pr.out });
    });
    let max = 1;
    for (const pr of pairs) for (const v of pr.kept.n) if (v > max) max = v;
    return { pairs, max, cy };
  }, [p.density, p.axes, scales, plotH, missingY]);
  const hists = useMemo(() => ys.map((y, i) => {
    const bins = new Float32Array(24);
    const at = (yy: number, k: number) => { if (yy < missingY - 1) bins[Math.min(23, Math.max(0, Math.floor(((yy - PAD_TOP) / plotH) * 24)))] += k; };
    // a density picture: every run's cell (from the pair on its right, or on its left for the last axis)
    const pr = dens?.pairs.find((x) => x.ia === i) ?? dens?.pairs.find((x) => x.ia === i - 1);
    if (pr) {
      const left = pr.ia === i;
      pr.kept.n.forEach((k, c) => at(left ? pr.ya[pr.kept.a[c]] : pr.yb[pr.kept.b[c]], k));
      return bins;
    }
    for (let r = 0; r < p.n; r++) if (kept[r]) at(y[r], 1);
    return bins;
  }), [ys, kept, p.n, missingY, plotH, dens]);

  /* Three layers (1.29): the lines left out and the lines kept are drawn - a few milliseconds a frame - into
     two canvases of their own, only when the data, axes, zoom or filters change; the canvas on screen puts
     them together under what changes often (axes, the filters, the brush, the open set, hover). A hover
     or a brush being dragged redraws only that. Many lines are drawn at 1 px per CSS pixel: twice the
     pixels at a high-DPI screen cost four times the drawing for no visible gain at that density. */
  const dpr = window.devicePixelRatio || 1;
  const lineDpr = p.n > MANY_LINES ? 1 : dpr;
  const bgLayer = useRef<HTMLCanvasElement | null>(null), fgLayer = useRef<HTMLCanvasElement | null>(null);
  const overlay = useRef<(ctx: CanvasRenderingContext2D) => void>(() => {});
  const drawing = useRef({ bg: false, fg: false });
  const composite = () => {
    const cv = canvas.current;
    if (!cv) return;
    const W = Math.round(width * dpr), H = Math.round(height * dpr);
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
    cv.style.width = `${width}px`; cv.style.height = `${height}px`;
    const ctx = cv.getContext("2d")!;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, W, H);
    for (const l of [bgLayer.current, fgLayer.current]) if (l && l.width && l.height) ctx.drawImage(l, 0, 0, W, H);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    overlay.current(ctx);
    cv.dataset.drawing = drawing.current.bg || drawing.current.fg ? "1" : "0";
  };
  const compositeRef = useRef(composite);
  compositeRef.current = composite;
  /** a line layer: sized, cleared, the zoom set; then its passes drawn a frame at a time */
  const lineLayer = (ref: React.MutableRefObject<HTMLCanvasElement | null>, which: "bg" | "fg", passes: (ctx: CanvasRenderingContext2D, xs: number[]) => Pass[]) => {
    const cv = (ref.current ??= document.createElement("canvas"));
    const W = Math.round(width * lineDpr), H = Math.round(height * lineDpr);
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
    const ctx = cv.getContext("2d")!;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.setTransform(lineDpr * z.k, 0, 0, lineDpr * z.k, lineDpr * z.x, lineDpr * z.y);
    const xs = p.axes.map((_, i) => axisX(i));
    const list = xs.length > 1 ? passes(ctx, xs) : [];
    drawing.current[which] = true;
    return runProgressive(list, {
      budgetMs: FRAME_BUDGET_MS, chunk: LINES_PER_CHUNK,
      flush: () => { ctx.getImageData(0, 0, 1, 1); },
      onFrame: () => compositeRef.current(),
      onDone: () => { drawing.current[which] = false; compositeRef.current(); },
    });
  };
  // a density series' colour, as the lines of that series are coloured
  const seriesColour = (sr: number): string => {
    const c = p.colorBy ? p.cols.get(p.colorBy) : undefined;
    if (!c || !p.density || p.density.series < 2) return HOLDS;
    if (FLAG_COLS.has(p.colorBy!)) return sr === 1 ? HOLDS : FAILS;
    return sr < (c.labels?.length ?? 0) ? category(sr) : FAILS;
  };
  /** A density picture's cells as bands: grouped by colour and by one of a few shades (log of the count), each group
   *  one stroke - every run counts: a single run is a faint band, many a dark one. */
  const bandPasses = (ctx: CanvasRenderingContext2D, xs: number[], which: "kept" | "out", colour: (s: number) => string, top: number): Pass[] => {
    if (!dens) return [];
    const LEVELS = 6, groups = new Map<string, { c: string; lv: number; w: number; seg: number[] }>();
    const lmax = Math.log1p(dens.max);
    for (const pr of dens.pairs) {
      const cells = pr[which], x0 = xs[pr.ia], x1 = xs[pr.ia + 1];
      for (let c = 0; c < cells.n.length; c++) {
        const lv = Math.min(LEVELS - 1, Math.floor((Math.log1p(cells.n[c]) / lmax) * LEVELS));
        const col = colour(cells.s[c]), key = `${col}|${lv}|${pr.band}`;
        let g = groups.get(key);
        if (!g) groups.set(key, (g = { c: col, lv, w: pr.band, seg: [] }));
        g.seg.push(x0, pr.ya[cells.a[c]], x1, pr.yb[cells.b[c]]);
      }
    }
    return [...groups.values()].sort((a, b) => a.lv - b.lv).map((g) => ({
      n: g.seg.length / 4,
      begin: () => { ctx.strokeStyle = g.c; ctx.lineWidth = g.w; ctx.globalAlpha = top * (0.04 + (0.5 * (g.lv + 1)) / LEVELS); },
      draw: (from: number, to: number) => {
        ctx.beginPath();
        for (let k = from; k < to; k++) { ctx.moveTo(g.seg[4 * k], g.seg[4 * k + 1]); ctx.lineTo(g.seg[4 * k + 2], g.seg[4 * k + 3]); }
        ctx.stroke();
      },
    }));
  };
  const strokeRows = (ctx: CanvasRenderingContext2D, xs: number[], rows: ArrayLike<number>) => (from: number, to: number) => {
    ctx.beginPath();
    for (let j = from; j < to; j++) {
      const r = rows[j];
      ctx.moveTo(xs[0], ys[0][r]);
      for (let i = 1; i < xs.length; i++) ctx.lineTo(xs[i], ys[i][r]);
    }
    ctx.stroke();
  };
  // the lines left out: faint, under the rest
  useEffect(() => lineLayer(bgLayer, "bg", (ctx, xs) => {
    const css = getComputedStyle(canvas.current!);
    const grey = css.getPropertyValue("--line-strong").trim() || "#444";
    ctx.strokeStyle = grey;
    ctx.globalAlpha = leftOut.length > 60000 ? 0.07 : 0.18; ctx.lineWidth = 1;
    return [...bandPasses(ctx, xs, "out", () => grey, 0.35), { n: leftOut.length, begin: () => { ctx.strokeStyle = grey; ctx.globalAlpha = leftOut.length > 60000 ? 0.07 : 0.18; ctx.lineWidth = 1; },
      draw: strokeRows(ctx, xs, leftOut) }];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [width, height, ys, leftOut, z.k, z.x, z.y, lineDpr, dens]);
  // the lines kept, a stroke per colour; fainter the more there are (a density picture: its bands first, under them)
  useEffect(() => lineLayer(fgLayer, "fg", (ctx, xs) => {
    const alpha = dens ? 0.9 : keptCount > 100000 ? 0.06 : keptCount > 20000 ? 0.12 : keptCount > 3000 ? 0.3 : keptCount > 300 ? 0.55 : 0.85;
    const width = dens ? 1.2 : keptCount > 3000 ? 1 : 1.4;
    return [...bandPasses(ctx, xs, "kept", seriesColour, 0.9),
      ...buckets.map(([colour, rows]) => ({ n: rows.length, begin: () => { ctx.strokeStyle = colour; ctx.globalAlpha = alpha; ctx.lineWidth = width; },
        draw: strokeRows(ctx, xs, rows) }))];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [width, height, ys, buckets, keptCount, z.k, z.x, z.y, lineDpr, dens]);

  overlay.current = (ctx: CanvasRenderingContext2D) => {
    const cv = canvas.current!;
    ctx.setTransform(dpr * z.k, 0, 0, dpr * z.k, dpr * z.x, dpr * z.y);
    const css = getComputedStyle(cv);
    const ink = css.getPropertyValue("--ink").trim() || "#ccc";
    const muted = css.getPropertyValue("--muted").trim() || "#888";
    const sel = css.getPropertyValue("--select").trim() || ink, selSoft = css.getPropertyValue("--select-soft").trim() || "rgba(128,128,128,.2)";
    const xs = p.axes.map((_, i) => axisX(i));
    const path = (r: number) => { ctx.moveTo(xs[0], ys[0][r]); for (let i = 1; i < xs.length; i++) ctx.lineTo(xs[i], ys[i][r]); };
    if (xs.length > 1) {
      if (lit.length) {
        ctx.globalAlpha = 1; ctx.lineWidth = 3; ctx.strokeStyle = css.getPropertyValue("--focus").trim() || "#6fa8ff"; ctx.beginPath();
        for (const r of lit) path(r);
        ctx.stroke();
      }
      if (hover) {
        ctx.globalAlpha = 1; ctx.lineWidth = 2.2; ctx.strokeStyle = ink; ctx.beginPath(); path(hover.row); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    // axes: histogram of the kept lines, the line, ticks, the missing-value band, filters
    p.axes.forEach((a, i) => {
      const x = xs[i], sc = scales[i], bins = hists[i];
      const top = Math.max(1, ...bins);
      if (bins.some((b) => b > 0)) {
        ctx.fillStyle = muted; ctx.globalAlpha = 0.28;
        bins.forEach((b, j) => { if (b) ctx.fillRect(x + 2, PAD_TOP + (j * plotH) / 24 + 0.5, (18 * b) / top, plotH / 24 - 1); });
        ctx.globalAlpha = 1;
      }
      ctx.strokeStyle = muted; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(x, PAD_TOP); ctx.lineTo(x, PAD_TOP + plotH); ctx.stroke();
      ctx.fillStyle = muted; ctx.font = "11px 'IBM Plex Sans', system-ui, sans-serif"; ctx.textAlign = "right"; ctx.textBaseline = "middle";
      for (const tk of sc.ticks) {
        const ty = PAD_TOP + (1 - tk.t) * plotH;
        ctx.fillRect(x - 3, ty, 3, 1);
        ctx.fillText(tk.label.length > 12 ? tk.label.slice(0, 11) + "…" : tk.label, x - 5, ty);
      }
      ctx.textAlign = "center";
      ctx.fillText("–", x, missingY);                                    // the band of missing values
      const f = p.filters[a];
      if (hasFilter(f)) {
        ctx.fillStyle = selSoft; ctx.strokeStyle = sel; ctx.lineWidth = 1;          // a filter is a selection (B7: not amber)
        const span = (y0: number, y1: number) => { ctx.fillRect(x - 6, Math.min(y0, y1), 12, Math.abs(y1 - y0) || 2); ctx.strokeRect(x - 6, Math.min(y0, y1), 12, Math.abs(y1 - y0) || 2); };
        if (f!.kind === "ranges") for (const [lo, hi] of f!.ranges) span(PAD_TOP + (1 - sc.norm(lo)) * plotH, PAD_TOP + (1 - sc.norm(hi)) * plotH);
        else for (const v of f!.values) { const ty = PAD_TOP + (1 - sc.norm(v)) * plotH; span(ty - 5, ty + 5); }
      }
      if (brush && brush.axis === i) {
        ctx.fillStyle = "rgba(111,168,255,.25)"; ctx.fillRect(x - 7, Math.min(brush.y0, brush.y1), 14, Math.abs(brush.y1 - brush.y0));
      }
    });
  };
  // what changes often: only the canvas on screen is drawn again (the line layers as they are)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => composite(), [width, height, ys, hists, lit, hover, brush, p.filters, scales, z.k, z.x, z.y, dpr]);

  // ------------------------------------------------------------------- pointer
  // the pointer in the plot's own coordinates (before the zoom)
  const local = (e: React.PointerEvent) => { const r = canvas.current!.getBoundingClientRect(); return { x: (e.clientX - r.left - z.x) / z.k, y: (e.clientY - r.top - z.y) / z.k }; };
  const axisAt = (x: number) => { for (let i = 0; i < k; i++) if (Math.abs(x - axisX(i)) < NEAR_AXIS / z.k) return i; return -1; };
  const nearest = (x: number, y: number): number => {
    if (k < 2) return -1;
    let i = 0;
    while (i < k - 2 && x > axisX(i + 1)) i++;
    const f = Math.max(0, Math.min(1, (x - axisX(i)) / (axisX(i + 1) - axisX(i))));
    const a = ys[i], b = ys[i + 1];
    let best = -1, bd = HOVER_PX / z.k;
    for (let r = 0; r < p.n; r++) {
      if (!kept[r]) continue;
      const d = Math.abs(a[r] + (b[r] - a[r]) * f - y);
      if (d < bd) { bd = d; best = r; }
    }
    return best;
  };
  const raf = useRef(0);
  const onMove = (e: React.PointerEvent) => {
    if (pan) {
      const dx = e.clientX - pan.x0, dy = e.clientY - pan.y0;
      if (pan.moved || Math.abs(dx) + Math.abs(dy) > 3) { setPan({ ...pan, moved: true }); p.onZoom?.({ k: pan.z.k, x: pan.z.x + dx, y: pan.z.y + dy }); }
      return;
    }
    const { x, y } = local(e);
    if (brush) { setBrush({ ...brush, y1: Math.max(PAD_TOP, Math.min(PAD_TOP + plotH, y)) }); return; }
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => {
      const r = axisAt(x) >= 0 ? -1 : nearest(x, y);
      setHover(r >= 0 ? { row: r, x: z.x + x * z.k, y: z.y + y * z.k } : null);
    });
  };
  const onDown = (e: React.PointerEvent) => {
    const { x, y } = local(e);
    const i = axisAt(x);
    if (i >= 0 && y >= PAD_TOP - 4 && y <= PAD_TOP + plotH + 4) {
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      setBrush({ axis: i, y0: y, y1: y, add: e.shiftKey });
    } else if (z.k > 1 && p.onZoom) {
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      setPan({ x0: e.clientX, y0: e.clientY, z, moved: false });
    }
  };
  const onUp = () => {
    if (pan) { const moved = pan.moved; setPan(null); if (moved) return; }
    if (!brush) { if (hover) p.onPick(hover.row); return; }
    const b = brush;
    setBrush(null);
    const name = p.axes[b.axis], sc = scales[b.axis], old = p.filters[name];
    if (Math.abs(b.y1 - b.y0) < 3) { if (old) p.onFilter(name, null); return; }        // a click: clear
    const t0 = 1 - (Math.min(b.y0, b.y1) - PAD_TOP) / plotH, t1 = 1 - (Math.max(b.y0, b.y1) - PAD_TOP) / plotH;
    if (sc.places) {
      const picked = sc.places.filter((v) => { const t = sc.norm(v); return t <= t0 && t >= t1; });
      const prev = b.add && old?.kind === "values" ? old.values : [];
      p.onFilter(name, { kind: "values", values: [...new Set([...prev, ...picked])] });
    } else {
      const range: [number, number] = [Math.min(sc.inv(t0), sc.inv(t1)), Math.max(sc.inv(t0), sc.inv(t1))];
      const prev = b.add && old?.kind === "ranges" ? old.ranges : [];
      p.onFilter(name, { kind: "ranges", ranges: [...prev, range] });
    }
  };

  // the tooltip in columns, inside what is on screen of a plot that scrolls
  const tipRows = Math.max(4, Math.floor((height - 24) / TIP_ROW));
  const tipCols = Math.max(1, Math.ceil(k / tipRows));
  const tipW = Math.min(viewW - 16, tipCols * TIP_COL);
  const tipH = Math.min(k, tipRows) * TIP_ROW + 18;
  // beside the pointer, on the side with room; never past what is on screen
  const tipLeft = !hover ? 0 : Math.max(scrollX + 4, Math.min(
    hover.x + 14 + tipW <= scrollX + viewW - 4 ? hover.x + 14 : hover.x - 14 - tipW, scrollX + viewW - tipW - 4));
  const tipTop = !hover ? 0 : Math.max(4, Math.min(hover.y - 10, height - tipH - 4));
  return (
    <>
    <div className="pp-scroll" ref={scroller} onScroll={(e) => setScrollX((e.currentTarget as HTMLDivElement).scrollLeft)}>
    <div className="pp" style={{ height, width }}>
      <canvas ref={canvas} className={brush ? "brushing" : pan?.moved ? "panning" : z.k > 1 ? "zoomed" : ""} onPointerMove={onMove} onPointerDown={onDown} onPointerUp={onUp}
        onPointerLeave={() => setHover(null)} role="img" data-shown={p.keptTotal ?? keptCount} data-density={p.density ? "1" : "0"} data-zoom={z.k.toFixed(2)} aria-label={p.axes.map(p.labelOf).join(", ")} />
      {p.axes.map((a, i) => {
        const dragging = dragAxis?.name === a;
        const moved = dragging && Math.abs(dragAxis!.x - dragAxis!.x0) > 4;
        return (
          <button key={a} className={`pp-axis-name${hasFilter(p.filters[a]) ? " filtered" : ""}${moved ? " dragging" : ""}`}
            style={{ left: z.x + axisX(i) * z.k + (moved ? dragAxis!.x - dragAxis!.x0 : 0),
              maxWidth: k > 1 ? Math.max(40, Math.min(160, (width - 2 * PAD_X) / (k - 1) - 8)) : 160 }}
            title={p.labelOf(a)}
            // click: the axis's menu; drag sideways: move the axis (HiPlot's way)
            onPointerDown={(e) => { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); setDragAxis({ name: a, x0: e.clientX, x: e.clientX }); }}
            onPointerMove={(e) => { if (dragAxis?.name === a) setDragAxis({ ...dragAxis, x: e.clientX }); }}
            onContextMenu={(e) => { if (!p.onAxisClick) return; e.preventDefault(); setDragAxis(null); p.onAxisMenu(a, (e.currentTarget as HTMLElement).getBoundingClientRect()); }}
            onPointerUp={(e) => {
              const d = dragAxis; setDragAxis(null);
              if (!d || d.name !== a) return;
              if (Math.abs(d.x - d.x0) <= 4) {
                if (p.onAxisClick) p.onAxisClick(a); else p.onAxisMenu(a, (e.currentTarget as HTMLElement).getBoundingClientRect());
                return;
              }
              const x = axisX(i) + (d.x - d.x0) / z.k;
              let to = 0, best = Infinity;
              for (let j = 0; j < k; j++) { const dd = Math.abs(axisX(j) - x); if (dd < best) { best = dd; to = j; } }
              if (to !== i) p.onMoveAxis(a, to);
            }}>
            {p.labelOf(a)}
          </button>
        );
      })}
      {hover && (
        <div className="pp-tip" style={{ left: tipLeft, top: tipTop, width: tipW, maxHeight: height - 8, gridTemplateColumns: `repeat(${tipCols}, minmax(0, 1fr))`, gridTemplateRows: `repeat(${Math.min(k, tipRows)}, auto)` }}>
          {p.axes.map((a) => { const c = p.cols.get(a)!; return <div key={a}><span>{p.labelOf(a)}</span><b>{labelOf(c, c.values[hover.row])}</b></div>; })}
        </div>
      )}
    </div>
    </div>
    {/* wider than the screen (S13): where the view is among the axes, and a slider that moves it */}
    {width > viewW + 1 && (() => {
      const first = Math.max(0, p.axes.findIndex((_, i) => axisX(i) >= scrollX));
      let last = first;
      for (let i = 0; i < k; i++) if (axisX(i) <= scrollX + viewW) last = i;
      const where = p.sliderLabel ? p.sliderLabel(first + 1, last + 1, k) : `${first + 1}–${last + 1} / ${k}`;
      return (
        <div className="pp-slider">
          <input type="range" min={0} max={Math.round(width - viewW)} step={1} value={Math.round(scrollX)} aria-label={where}
            onChange={(e) => { const el = scroller.current; if (el) el.scrollLeft = Number(e.target.value); }} />
          <span className="pp-slider-at">{where}</span>
        </div>
      );
    })()}
    </>
  );
}
