/* The parallel plot: a vertical axis per column, a line per parameter set (or per run).

   Drawing is one canvas (thousands of lines); the axis names are buttons over it (their menu:
   scale, colour, reverse, hide, ranges). On an axis: drag = keep that range, Shift-drag = keep
   another range too, click = clear. Elsewhere: hover shows a line's values, click picks it.
   Everything the plot keeps or shows comes in as props - the store owns it (sweeps/state.ts). */
import { useEffect, useMemo, useRef, useState } from "react";
import { category, FAILS, HOLDS, ramp } from "../../sweeps/colors";
import { hasFilter, keptMask } from "../../sweeps/filters";
import type { Col, Filter, Scale } from "../../sweeps/model";
import { labelOf, makeScale, type AxisScale } from "../../sweeps/scales";

export interface ParallelPlotProps {
  cols: Map<string, Col>;
  n: number;
  axes: string[];
  scaleOf: (name: string) => Scale;
  reversed: Record<string, boolean>;
  colorBy: string | null;
  filters: Record<string, Filter>;
  /** rows drawn on top, thick (the set open on the right; in runs mode all its runs) */
  highlight: Uint8Array | null;
  labelOf: (name: string) => string;
  onPick: (row: number) => void;
  onFilter: (name: string, f: Filter | null) => void;
  onAxisMenu: (name: string, at: DOMRect) => void;
  height?: number;
}

const PAD_X = 56, PAD_TOP = 40, PAD_BOTTOM = 34, MISSING_GAP = 14, NEAR_AXIS = 12, HOVER_PX = 6;

export default function ParallelPlot(p: ParallelPlotProps) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(800);
  const height = p.height ?? 360;
  const [hover, setHover] = useState<{ row: number; x: number; y: number } | null>(null);
  const [brush, setBrush] = useState<{ axis: number; y0: number; y1: number; add: boolean } | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(Math.max(320, el.clientWidth)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const plotH = height - PAD_TOP - PAD_BOTTOM - MISSING_GAP;
  const k = p.axes.length;
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
  const kept = useMemo(() => keptMask(p.cols, p.filters, p.n), [p.cols, p.filters, p.n]);

  // a colour per row, as buckets of rows (one stroke per colour)
  const buckets = useMemo(() => {
    const groups = new Map<string, number[]>();
    const put = (key: string, r: number) => { let g = groups.get(key); if (!g) groups.set(key, (g = [])); g.push(r); };
    const c = p.colorBy ? p.cols.get(p.colorBy) : undefined;
    let colour: (r: number) => string;
    if (!c) colour = () => HOLDS;
    else if (p.colorBy === "#holds") colour = (r) => (c.values[r] === 1 ? HOLDS : FAILS);
    else if (c.kind === "cat") colour = (r) => category(c.values[r]);
    else {
      const sc: AxisScale = makeScale(c, p.scaleOf(c.name) === "log" ? "log" : "linear");
      colour = (r) => ramp(Math.round(sc.norm(c.values[r]) * 31) / 31);
    }
    for (let r = 0; r < p.n; r++) if (kept[r]) put(colour(r), r);
    // the holding sets last: drawn on top
    return [...groups.entries()].sort((a, b) => (a[0] === HOLDS ? 1 : 0) - (b[0] === HOLDS ? 1 : 0));
  }, [p.colorBy, p.cols, p.n, kept, p.scaleOf]);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(width * dpr); cv.height = Math.round(height * dpr);
    cv.style.width = `${width}px`; cv.style.height = `${height}px`;
    const ctx = cv.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const css = getComputedStyle(cv);
    const ink = css.getPropertyValue("--ink").trim() || "#ccc";
    const muted = css.getPropertyValue("--muted").trim() || "#888";
    const line = css.getPropertyValue("--line-strong").trim() || "#444";
    const xs = p.axes.map((_, i) => axisX(i));
    const path = (r: number) => { ctx.moveTo(xs[0], ys[0][r]); for (let i = 1; i < xs.length; i++) ctx.lineTo(xs[i], ys[i][r]); };
    const keptCount = kept.reduce((a, b) => a + b, 0);
    // the lines left out: faint, under the rest (skipped when there are very many)
    if (xs.length > 1 && p.n - keptCount > 0 && p.n <= 60000) {
      ctx.strokeStyle = line; ctx.globalAlpha = 0.18; ctx.lineWidth = 1; ctx.beginPath();
      for (let r = 0; r < p.n; r++) if (!kept[r]) path(r);
      ctx.stroke();
    }
    if (xs.length > 1) {
      ctx.globalAlpha = keptCount > 20000 ? 0.12 : keptCount > 3000 ? 0.3 : keptCount > 300 ? 0.55 : 0.85;
      ctx.lineWidth = keptCount > 3000 ? 1 : 1.4;
      for (const [colour, rows] of buckets) {
        ctx.strokeStyle = colour; ctx.beginPath();
        for (const r of rows) path(r);
        ctx.stroke();
      }
      if (p.highlight) {
        ctx.globalAlpha = 1; ctx.lineWidth = 3; ctx.strokeStyle = css.getPropertyValue("--focus").trim() || "#6fa8ff"; ctx.beginPath();
        for (let r = 0; r < p.n; r++) if (p.highlight[r]) path(r);
        ctx.stroke();
      }
      if (hover) {
        ctx.globalAlpha = 1; ctx.lineWidth = 2.2; ctx.strokeStyle = ink; ctx.beginPath(); path(hover.row); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    // axes: histogram of the kept lines, the line, ticks, the missing-value band, filters
    p.axes.forEach((a, i) => {
      const x = xs[i], sc = scales[i], y = ys[i];
      const bins = new Float32Array(24);
      let any = 0;
      for (let r = 0; r < p.n; r++) if (kept[r] && y[r] < missingY - 1) { bins[Math.min(23, Math.floor(((y[r] - PAD_TOP) / plotH) * 24))]++; any++; }
      const top = Math.max(1, ...bins);
      if (any) {
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
        ctx.fillStyle = "rgba(242,169,59,.22)"; ctx.strokeStyle = "#f2a93b"; ctx.lineWidth = 1;
        const span = (y0: number, y1: number) => { ctx.fillRect(x - 6, Math.min(y0, y1), 12, Math.abs(y1 - y0) || 2); ctx.strokeRect(x - 6, Math.min(y0, y1), 12, Math.abs(y1 - y0) || 2); };
        if (f!.kind === "ranges") for (const [lo, hi] of f!.ranges) span(PAD_TOP + (1 - sc.norm(lo)) * plotH, PAD_TOP + (1 - sc.norm(hi)) * plotH);
        else for (const v of f!.values) { const ty = PAD_TOP + (1 - sc.norm(v)) * plotH; span(ty - 5, ty + 5); }
      }
      if (brush && brush.axis === i) {
        ctx.fillStyle = "rgba(111,168,255,.25)"; ctx.fillRect(x - 7, Math.min(brush.y0, brush.y1), 14, Math.abs(brush.y1 - brush.y0));
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, height, ys, buckets, kept, p.highlight, hover, brush, p.filters, scales]);

  // ------------------------------------------------------------------- pointer
  const local = (e: React.PointerEvent) => { const r = canvas.current!.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  const axisAt = (x: number) => { for (let i = 0; i < k; i++) if (Math.abs(x - axisX(i)) < NEAR_AXIS) return i; return -1; };
  const nearest = (x: number, y: number): number => {
    if (k < 2) return -1;
    let i = 0;
    while (i < k - 2 && x > axisX(i + 1)) i++;
    const f = Math.max(0, Math.min(1, (x - axisX(i)) / (axisX(i + 1) - axisX(i))));
    const a = ys[i], b = ys[i + 1];
    let best = -1, bd = HOVER_PX;
    for (let r = 0; r < p.n; r++) {
      if (!kept[r]) continue;
      const d = Math.abs(a[r] + (b[r] - a[r]) * f - y);
      if (d < bd) { bd = d; best = r; }
    }
    return best;
  };
  const raf = useRef(0);
  const onMove = (e: React.PointerEvent) => {
    const { x, y } = local(e);
    if (brush) { setBrush({ ...brush, y1: Math.max(PAD_TOP, Math.min(PAD_TOP + plotH, y)) }); return; }
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => {
      const r = axisAt(x) >= 0 ? -1 : nearest(x, y);
      setHover(r >= 0 ? { row: r, x, y } : null);
    });
  };
  const onDown = (e: React.PointerEvent) => {
    const { x, y } = local(e);
    const i = axisAt(x);
    if (i >= 0 && y >= PAD_TOP - 4 && y <= PAD_TOP + plotH + 4) {
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      setBrush({ axis: i, y0: y, y1: y, add: e.shiftKey });
    }
  };
  const onUp = () => {
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

  return (
    <div className="pp" ref={wrap} style={{ height }}>
      <canvas ref={canvas} className={brush ? "brushing" : ""} onPointerMove={onMove} onPointerDown={onDown} onPointerUp={onUp}
        onPointerLeave={() => setHover(null)} role="img" aria-label={p.axes.map(p.labelOf).join(", ")} />
      {p.axes.map((a, i) => (
        <button key={a} className={`pp-axis-name${hasFilter(p.filters[a]) ? " filtered" : ""}`}
          style={{ left: axisX(i), maxWidth: k > 1 ? Math.max(40, Math.min(160, (width - 2 * PAD_X) / (k - 1) - 8)) : 160 }}
          title={p.labelOf(a)} onClick={(e) => p.onAxisMenu(a, (e.currentTarget as HTMLElement).getBoundingClientRect())}>
          {p.labelOf(a)}
        </button>
      ))}
      {hover && (
        <div className="pp-tip" style={{ left: Math.min(hover.x + 14, width - 240), top: Math.max(4, hover.y - 10) }}>
          {p.axes.map((a) => { const c = p.cols.get(a)!; return <div key={a}><span>{p.labelOf(a)}</span><b>{labelOf(c, c.values[hover.row])}</b></div>; })}
        </div>
      )}
    </div>
  );
}
