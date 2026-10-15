import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { actions, shownSpan, signalName, useApp, type Plot, type PlotSignal } from "../store";
import { useT } from "../i18n";
import { dpr, indexSpan, PLOT_THEME, uiScale, useSize } from "./chartUtil";

/* T17c: a plain 3D plot - any three signals as X, Y, Z (a trajectory in metres, three sensor axes,
   a state space...). Nothing geographic: the map and the 3D globe are for places on Earth; "Place
   on map" puts a track there when it is one.
   The plot's signals in threes are the tracks (X, Y, Z, X, Y, Z...); Y and Z are aligned onto X's
   samples by the server. Drawn on a 2D canvas with its own orthographic camera - no extra
   library: drag rotates, Shift+drag moves, the wheel zooms, a double click resets. The timeline
   works as everywhere: the amber point is the cursor's time, "draw" / "window" show the track up
   to it. */

type Track = { id: string; t: Float64Array; x: Float32Array; y: Float32Array; z: Float32Array };
interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void; emptyText: string }
const VIEW0 = { az: -0.65, el: 0.42, zoom: 1, px: 0, py: 0 };

/** About n round tick values between lo and hi. */
function niceTicks(lo: number, hi: number, n = 4): number[] {
  const span = hi - lo;
  if (!(span > 0) || !Number.isFinite(span)) return [lo];
  const raw = span / n, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  return out;
}
const fmt = (v: number) => {
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e6)) return v.toExponential(1).replace("e+", "e");
  return String(+v.toPrecision(5));
};
/** Last sample at or before t (-1: none). */
function indexAt(ts: ArrayLike<number>, t: number): number {
  let lo = 0, hi = ts.length - 1;
  if (!ts.length || t < ts[0]) return -1;
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (ts[m] <= t) lo = m; else hi = m - 1; }
  return lo;
}

export default function XYZChart({ plot, index, onLoading, emptyText }: Props) {
  const t = useT();
  const runs = useApp((s) => s.runs);
  const dataVersion = useApp((s) => s.dataVersion);
  const [tracks, setTracks] = useState<Track[]>([]);

  const trios = useMemo(() => {
    const s = plot.signals, out: [PlotSignal, PlotSignal, PlotSignal][] = [];
    for (let k = 0; k + 2 < s.length; k += 3) out.push([s[k], s[k + 1], s[k + 2]]);
    return out;
  }, [plot.signals]);
  const trioKey = trios.map((tr) => tr.map((s) => s.sig).join(",")).join("|");
  const runsKey = runs.map((r) => `${r.id}:${r.timeOffset}:${r.samples}:${r.signals.length}`).join("|");

  useEffect(() => {
    if (!trios.length) { setTracks([]); return; }
    let cancelled = false;
    const h = window.setTimeout(async () => {
      onLoading(true);
      try {
        const r = await api.xyz(trios.map(([x, y, z]) => ({ x: x.sig, y: y.sig, z: z.sig })), plot.xyAlign ?? "linear");
        if (!cancelled) setTracks(r.map((tr): Track => (tr.t ? { id: tr.id, t: tr.t, x: tr.x, y: tr.y, z: tr.z }
          : { id: tr.id, t: new Float64Array(), x: new Float32Array(), y: new Float32Array(), z: new Float32Array() })));
      } catch (e) {
        if (!cancelled) useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      } finally { if (!cancelled) onLoading(false); }
    }, 60);
    return () => { cancelled = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trioKey, plot.xyAlign, dataVersion, runsKey]);

  /* the values as plotted (scale / offset of each axis signal) */
  const shown = useMemo(() => tracks.map((tr, k): Shown | null => {
    const trio = trios[k];
    if (!trio) return null;
    const sc = (a: Float32Array, i: number) => Float64Array.from(a, (v) => v * trio[i].scale + trio[i].offset);
    return { t: tr.t, v: [sc(tr.x, 0), sc(tr.y, 1), sc(tr.z, 2)], color: trio[0].color, width: trio[0].width,
      names: trio.map((s) => signalName(runs, s.sig, false)) };
  }).filter((x): x is Shown => !!x), [tracks, trios, runs]);

  const leftover = plot.signals.length % 3;
  const noData = trios.length > 0 && tracks.length > 0 && !shown.some((tr) => tr.v[0].some(Number.isFinite));
  return (
    <XYZCanvas shown={shown} equal={plot.xyzEqual !== false} flipZ={!!plot.xyzFlipZ} index={index}
      hint={leftover ? t("xyzLeftover", { n: leftover }) : t("xyzControls")}>
      {!trios.length && <div className="plot-empty">{emptyText}</div>}
      {noData && <div className="plot-empty">{t("xyzNoOverlap")}</div>}
    </XYZCanvas>
  );
}

/** A track ready to draw: values as plotted, its colour and the names of its three axes. */
export type Shown = { t: Float64Array; v: [Float64Array, Float64Array, Float64Array]; color: string; width: number; names: string[]; label?: string };
interface CanvasProps { shown: Shown[]; equal: boolean; flipZ: boolean; index: number; hint: string; children?: React.ReactNode;
  letters?: string[];      // the axes in the readout (default X, Y, Z)
  legendTop?: number;      // px from the top for the legend (room for a note above it)
}

/** The drawing and the camera, shared by the XYZ plot and the 3D view without WebGL. */
export function XYZCanvas({ shown, equal, flipZ, index, hint, children, letters = ["X", "Y", "Z"], legendTop = 8 }: CanvasProps) {
  const t = useT();
  const theme = useApp((s) => s.theme);
  const cursor = useApp((s) => s.cursor);
  const playMode = useApp((s) => s.playMode);
  const windowSec = useApp((s) => s.windowSec);
  const scale = useApp((s) => s.uiScale);
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const size = useSize(wrapRef);
  const view = useRef({ ...VIEW0 });
  const box = useMemo(() => {
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const tr of shown) for (let a = 0; a < 3; a++) for (const v of tr.v[a]) if (Number.isFinite(v)) { if (v < lo[a]) lo[a] = v; if (v > hi[a]) hi[a] = v; }
    if (!lo.every(Number.isFinite)) return null;
    const half = lo.map((l, a) => (hi[a] - l) / 2);
    const big = Math.max(...half);
    const h = half.map((x, a) => {
      const v = equal ? big : x;
      return v > 0 ? v : Math.max(Math.abs(lo[a]) * 0.1, 1);       // a flat axis still gets a size
    });
    return { c: lo.map((l, a) => (l + hi[a]) / 2), h };
  }, [shown, equal]);

  const draw = useCallback(() => {
    const cv = canvasRef.current;
    if (!cv || size.w < 50 || size.h < 50) return;
    const r = dpr(), W = size.w * r, H = size.h * r;
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
    const ctx = cv.getContext("2d")!;
    ctx.clearRect(0, 0, W, H);
    if (!box) return;
    const pt = PLOT_THEME[theme], fs = 11 * r * uiScale(), font = getComputedStyle(document.body).fontFamily;
    const { az, el, zoom, px, py } = view.current;
    const flip = flipZ;
    const S = Math.min(W, H) * 0.3 * zoom, cx = W / 2 + px * r, cy = H / 2 + py * r;
    const ca = Math.cos(az), sa = Math.sin(az), ce = Math.cos(el), se = Math.sin(el);
    /* n: -1..1 box coordinates (z already flipped for display). Screen x, y and the depth (bigger: farther) */
    const proj = (nx: number, ny: number, nz: number): [number, number, number] => {
      const u = nx * ca + ny * sa, d = -nx * sa + ny * ca;
      return [cx + S * u, cy - S * (nz * ce + d * se), d * ce - nz * se];
    };
    const norm = (v: number, a: number) => (v - box.c[a]) / box.h[a];
    const nz = (v: number) => (flip ? -norm(v, 2) : norm(v, 2));
    const P = (x: number, y: number, z: number) => proj(norm(x, 0), norm(y, 1), nz(z));

    /* the three walls farthest from the eye, with grid lines at the ticks */
    const xb = proj(1, 0, 0)[2] > proj(-1, 0, 0)[2] ? 1 : -1;
    const yb = proj(0, 1, 0)[2] > proj(0, -1, 0)[2] ? 1 : -1;
    const zb = proj(0, 0, 1)[2] > proj(0, 0, -1)[2] ? 1 : -1;
    const ticks = [0, 1, 2].map((a) => niceTicks(box.c[a] - box.h[a], box.c[a] + box.h[a]));
    const tn = (a: number, v: number) => (a === 2 ? nz(v) : norm(v, a));
    const line = (p: number[][], color: string, w = 1) => {
      ctx.beginPath(); p.forEach(([x, y, z], i) => { const q = proj(x, y, z); if (i) ctx.lineTo(q[0], q[1]); else ctx.moveTo(q[0], q[1]); });
      ctx.strokeStyle = color; ctx.lineWidth = w * r; ctx.stroke();
    };
    ctx.save();
    const walls: [number, number, number][] = [[xb, NaN, NaN], [NaN, yb, NaN], [NaN, NaN, zb]];
    for (const wall of walls) {
      const fixed = wall.findIndex((v) => !Number.isNaN(v));
      const others = [0, 1, 2].filter((a) => a !== fixed);
      const pt3 = (vals: Record<number, number>) => [0, 1, 2].map((a) => (a === fixed ? wall[fixed] : vals[a]));
      for (const a of others) {
        const b = others.find((o) => o !== a)!;
        for (const tv of ticks[a]) line([pt3({ [a]: tn(a, tv), [b]: -1 }), pt3({ [a]: tn(a, tv), [b]: 1 })], pt.grid);
      }
      line([pt3({ [others[0]]: -1, [others[1]]: -1 }), pt3({ [others[0]]: 1, [others[1]]: -1 }),
        pt3({ [others[0]]: 1, [others[1]]: 1 }), pt3({ [others[0]]: -1, [others[1]]: 1 }), pt3({ [others[0]]: -1, [others[1]]: -1 })], pt.axis, 0.75);
    }
    /* tick labels on the front edges of the floor (X, Y) and on the left-most back vertical edge (Z) */
    ctx.font = `${fs}px ${font}`; ctx.fillStyle = pt.axis;
    const labelEdge = (a: number, at: (n: number) => number[], name: string) => {
      const c0 = proj(0, 0, 0);
      for (const tv of ticks[a]) {
        const q = proj(...(at(tn(a, tv)) as [number, number, number]));
        const dx = q[0] - c0[0], dy = q[1] - c0[1], L = Math.hypot(dx, dy) || 1;
        const lx = q[0] + (dx / L) * 14 * r, ly = q[1] + (dy / L) * 14 * r;
        ctx.textAlign = dx > 4 ? "left" : dx < -4 ? "right" : "center"; ctx.textBaseline = "middle";
        ctx.fillText(fmt(tv), lx, ly);
      }
      const mid = proj(...(at(0) as [number, number, number]));
      const dx = mid[0] - c0[0], dy = mid[1] - c0[1], L = Math.hypot(dx, dy) || 1;
      ctx.save(); ctx.fillStyle = pt.label; ctx.font = `600 ${fs}px ${font}`;
      ctx.textAlign = dx > 4 ? "left" : dx < -4 ? "right" : "center";
      ctx.fillText(name.length > 28 ? name.slice(0, 27) + "…" : name, mid[0] + (dx / L) * 44 * r, mid[1] + (dy / L) * 44 * r);
      ctx.restore();
    };
    const names = shown[0]?.names ?? ["X", "Y", "Z"];
    labelEdge(0, (n) => [n, -yb, zb], names[0]);
    labelEdge(1, (n) => [-xb, n, zb], names[1]);
    const zEdges: [number, number][] = [[xb, -yb], [-xb, yb]];
    const [zx, zy] = zEdges.sort((p, q) => proj(p[0], p[1], 0)[0] - proj(q[0], q[1], 0)[0])[0];
    labelEdge(2, (n) => [zx, zy, n], names[2] + (flip ? " ↓" : ""));
    ctx.restore();

    /* the tracks (as the timeline shows them), their shadow on the floor, start and current points */
    const span = shownSpan({ playMode, windowSec, cursor });
    const tNow = cursor.on && cursor.t1 !== null ? cursor.t1 : null;
    let readout: { name: string; v: number[]; color: string } | null = null;
    shown.forEach((tr, k) => {
      const [i0, i1] = indexSpan(tr.t, span);
      const path = (floor: boolean) => {
        ctx.beginPath();
        let pen = false;
        for (let i = i0; i < i1; i++) {
          const x = tr.v[0][i], y = tr.v[1][i], z = tr.v[2][i];
          if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) { pen = false; continue; }
          const q = floor ? proj(norm(x, 0), norm(y, 1), zb) : P(x, y, z);
          if (pen) ctx.lineTo(q[0], q[1]); else { ctx.moveTo(q[0], q[1]); pen = true; }
        }
      };
      ctx.save();
      ctx.lineJoin = "round";
      path(true); ctx.strokeStyle = tr.color + "40"; ctx.lineWidth = 1 * r; ctx.stroke();
      path(false); ctx.strokeStyle = tr.color; ctx.lineWidth = (tr.width || 1.5) * r; ctx.stroke();
      for (let i = i0; i < i1; i++) {
        if ([0, 1, 2].every((a) => Number.isFinite(tr.v[a][i]))) {
          const q = P(tr.v[0][i], tr.v[1][i], tr.v[2][i]);
          ctx.beginPath(); ctx.arc(q[0], q[1], 3 * r, 0, Math.PI * 2); ctx.fillStyle = pt.bg; ctx.fill();
          ctx.lineWidth = 1.5 * r; ctx.strokeStyle = tr.color; ctx.stroke();
          break;
        }
      }
      if (tNow !== null) {
        const i = indexAt(tr.t, tNow);
        if (i >= 0 && [0, 1, 2].every((a) => Number.isFinite(tr.v[a][i]))) {
          const v = [tr.v[0][i], tr.v[1][i], tr.v[2][i]];
          const q = P(v[0], v[1], v[2]), f = proj(norm(v[0], 0), norm(v[1], 1), zb);
          ctx.setLineDash([3 * r, 3 * r]); ctx.beginPath(); ctx.moveTo(q[0], q[1]); ctx.lineTo(f[0], f[1]);
          ctx.strokeStyle = pt.amber; ctx.lineWidth = 1 * r; ctx.stroke(); ctx.setLineDash([]);
          ctx.beginPath(); ctx.arc(q[0], q[1], 5 * r, 0, Math.PI * 2); ctx.fillStyle = pt.amber; ctx.fill();
          ctx.lineWidth = 1.5 * r; ctx.strokeStyle = pt.amberInk; ctx.stroke();
          if (k === 0) readout = { name: tr.names.join(" / "), v, color: tr.color };
        }
      }
      ctx.restore();
    });

    /* legend (several tracks) and the values at the cursor (first track) */
    ctx.font = `${fs}px ${font}`; ctx.textBaseline = "top";
    let ly = legendTop * r;
    if (shown.length > 1) {
      ctx.textAlign = "left";
      for (const tr of shown) {
        ctx.fillStyle = tr.color; ctx.fillRect(8 * r, ly + 3 * r, 10 * r, 3 * r);
        ctx.fillStyle = pt.text; ctx.fillText(tr.label ?? tr.names.join(" / "), 24 * r, ly);
        ly += fs * 1.4;
      }
    }
    const ro = readout as { name: string; v: number[]; color: string } | null;
    if (ro) {
      ctx.textAlign = "right"; ctx.fillStyle = pt.text;
      letters.forEach((a, i) => ctx.fillText(`${a} ${fmt(ro.v[i])}`, W - 8 * r, 8 * r + i * fs * 1.4));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [box, shown, size.w, size.h, theme, flipZ, cursor, playMode, windowSec, letters.join(), legendTop]);

  useEffect(() => { draw(); }, [draw, scale]);

  /* camera: drag rotates (Shift: moves), wheel zooms, double click resets */
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    let drag: { x: number; y: number; pan: boolean } | null = null, raf = 0;
    const redraw = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); };
    const down = (e: PointerEvent) => {
      actions.setActivePlot(index);
      if (e.button !== 0) return;
      drag = { x: e.clientX, y: e.clientY, pan: e.shiftKey };
      cv.setPointerCapture(e.pointerId);
    };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      drag.x = e.clientX; drag.y = e.clientY;
      const v = view.current;
      if (drag.pan) { v.px += dx; v.py += dy; } else {
        v.az -= dx * 0.008;
        v.el = Math.max(-1.55, Math.min(1.55, v.el + dy * 0.008));
      }
      redraw();
    };
    const up = () => { drag = null; };
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const v = view.current;
      v.zoom = Math.max(0.25, Math.min(12, v.zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
      redraw();
    };
    const reset = () => { view.current = { ...VIEW0 }; redraw(); };
    cv.addEventListener("pointerdown", down);
    cv.addEventListener("pointermove", move);
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", up);
    cv.addEventListener("wheel", wheel, { passive: false });
    cv.addEventListener("dblclick", reset);
    return () => {
      cancelAnimationFrame(raf);
      cv.removeEventListener("pointerdown", down); cv.removeEventListener("pointermove", move);
      cv.removeEventListener("pointerup", up); cv.removeEventListener("pointercancel", up);
      cv.removeEventListener("wheel", wheel); cv.removeEventListener("dblclick", reset);
    };
  }, [draw, index]);

  return (
    <div className="plot-canvas xyz-wrap" ref={wrapRef}>
      <canvas ref={canvasRef} className="xyz-canvas" style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }}
        aria-label={t("modeXyz")} role="img" />
      {children}
      <div className="xyz-hint" dir="auto">{hint}</div>
    </div>
  );
}
