import { useEffect, useState } from "react";
import type uPlot from "uplot";

/* Plot colors per theme. Read from this table (not from CSS) because React runs
   chart effects before App sets <html data-theme>. Keep in sync with index.css. */
export const PLOT_THEME = {
  dark: { axis: "#8e9cad", grid: "#222c39", amber: "#f2a93b", amberInk: "#1b1305", label: "#dde4ec", bg: "#121820", text: "#dde4ec" },
  light: { axis: "#5a6979", grid: "#e6ebf0", amber: "#945d0b", amberInk: "#ffffff", label: "#1f2a36", bg: "#ffffff", text: "#1f2a36" },
} as const;

/** Dash patterns of preview lines, in order: axis 1, 2, 3 of a frame conversion are told apart by
 *  these (in the plot, in the separate preview charts and in their key in the panel). */
export const PREVIEW_DASH = [[6, 4], [2, 3], [12, 3, 2, 3]];

export type ThemeName = keyof typeof PLOT_THEME;

/** UI text scale (accessibility): canvas text follows the same setting as the page. */
export const uiScale = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-scale")) || 1;

export function axisStyle(theme: ThemeName): uPlot.Axis {
  const pt = PLOT_THEME[theme];
  const font = `${Math.round(11 * uiScale())}px ${getComputedStyle(document.body).fontFamily}`;
  return { stroke: pt.axis, grid: { stroke: pt.grid, width: 1 }, ticks: { stroke: pt.grid, width: 1 }, font, labelFont: font };
}

export function useSize(ref: React.RefObject<HTMLElement | null>) {
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => {
      const w = Math.floor(e.contentRect.width), h = Math.floor(e.contentRect.height);
      setSize((s) => (s.w === w && s.h === h ? s : { w, h }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

export const dpr = () => window.devicePixelRatio || 1;

/** Draw a small filled label (used for the cursor flag and state values). */
export function flag(ctx: CanvasRenderingContext2D, x: number, top: number, text: string, bg: string, fg: string,
  bounds: { left: number; width: number }, alpha = 1) {
  const r = dpr();
  ctx.font = `${11 * r * uiScale()}px ${getComputedStyle(document.body).fontFamily}`;
  ctx.textBaseline = "middle";
  ctx.textAlign = "left"; // uPlot leaves textAlign set by its axis labels
  const tw = ctx.measureText(text).width + 10 * r, th = 17 * r * uiScale();
  let fx = x + 1;
  if (fx + tw > bounds.left + bounds.width) fx = x - tw;
  ctx.globalAlpha = alpha;
  ctx.fillStyle = bg;
  ctx.fillRect(fx, top, tw, th);
  ctx.globalAlpha = 1;
  ctx.fillStyle = fg;
  ctx.fillText(text, fx + 5 * r, top + th / 2 + r);
}

/** Lines that connect points in the given order (X need not be monotonic). For X-Y plots. */
/** Index range [i0, i1) of the samples whose time is within `span` (times ascending), or everything. */
export function indexSpan(times: ArrayLike<number>, span: [number, number] | null): [number, number] {
  const n = times.length;
  if (!span || !n) return [0, n];
  const find = (v: number) => {                     // first index with times[i] >= v
    let lo = 0, hi = n;
    while (lo < hi) { const m = (lo + hi) >> 1; if (times[m] < v) lo = m + 1; else hi = m; }
    return lo;
  };
  const a = Number.isFinite(span[0]) ? find(span[0]) : 0;
  let b = find(span[1]);
  while (b < n && times[b] === span[1]) b++;        // include samples exactly at the time
  return [a, Math.max(a, b)];
}

/** orderedLines limited to an index range per series (the timeline's "up to the time" / window). */
export const orderedLinesIn = (range: (si: number) => [number, number]): uPlot.Series.PathBuilder => (u, si) => {
  const [i0, i1] = range(si);
  return orderedLinesFrom(u, si, i0, i1);
};

export const orderedLines: uPlot.Series.PathBuilder = (u, si) => orderedLinesFrom(u, si, 0, Infinity);

function orderedLinesFrom(u: uPlot, si: number, i0: number, i1: number) {
  const [xs, ys] = u.data[si] as unknown as [ArrayLike<number>, ArrayLike<number | null>];
  const stroke = new Path2D();
  let pen = false;
  for (let i = Math.max(0, i0); i < Math.min(xs.length, i1); i++) {
    const y = ys[i];
    if (y === null || y === undefined || !Number.isFinite(y)) { pen = false; continue; }
    const cx = u.valToPos(xs[i], "x", true), cy = u.valToPos(y, "y", true);
    if (pen) stroke.lineTo(cx, cy); else { stroke.moveTo(cx, cy); pen = true; }
  }
  const { left, top, width, height } = u.bbox;
  const clip = new Path2D();
  clip.rect(left, top, width, height);
  return { stroke, fill: null, clip, band: null, gaps: null, flags: 0 } as unknown as uPlot.Series.Paths;
}

/** Tick labels that stay readable on log axes (1e-5 instead of "0"). */
export function tickValues(_u: uPlot, splits: number[]): string[] {
  return splits.map((v) => {
    if (v === null || v === undefined || !Number.isFinite(v)) return "";
    const a = Math.abs(v);
    if (a !== 0 && (a < 1e-3 || a >= 1e6)) return v.toExponential(0).replace("e+", "e");
    return String(+v.toPrecision(6));
  });
}
