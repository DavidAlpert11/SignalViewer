/**
 * R3: the timeline as a map of the recording - the active plot's first line drawn faintly behind the
 * track (its shape over the whole recording), and what the plots show as a window on it that is dragged
 * to move along the recording and pulled at its edges to zoom. Pure functions; Timeline.tsx draws.
 */
export type Span = [number, number];

/** An SVG path (viewBox 0 0 1000 100) of min / max points over [t0, t1]: the line's shape, top to bottom. */
export function envelopePath(x: ArrayLike<number>, y: ArrayLike<number>, t0: number, t1: number): string {
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i < y.length; i++) { const v = y[i]; if (Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; } }
  const span = t1 - t0;
  if (!(hi >= lo) || !(span > 0)) return "";
  const h = hi - lo || 1, flat = hi === lo;
  let d = "", pen = false;
  for (let i = 0; i < x.length; i++) {
    const v = y[i];
    if (!Number.isFinite(v) || !Number.isFinite(x[i])) { pen = false; continue; }
    const px = ((x[i] - t0) / span) * 1000, py = flat ? 50 : 92 - ((v - lo) / h) * 84;   // a margin top and bottom
    d += `${pen ? "L" : "M"}${px.toFixed(1)} ${py.toFixed(1)}`;
    pen = true;
  }
  return d;
}

/** The window moved by dt, kept inside the recording (its width unchanged). */
export function panSpan(r: Span, dt: number, ext: Span): Span {
  const w = r[1] - r[0];
  const a = Math.min(ext[1] - w, Math.max(ext[0], r[0] + dt));
  return [a, a + w];
}

/** One edge of the window pulled to t (inside the recording; never narrower than `minW`). */
export function pullEdge(r: Span, edge: 0 | 1, t: number, ext: Span, minW: number): Span {
  const v = Math.min(ext[1], Math.max(ext[0], t));
  return edge === 0 ? [Math.min(v, r[1] - minW), r[1]] : [r[0], Math.max(v, r[0] + minW)];
}

/** A window worth drawing: set, finite and narrower than (almost) the whole recording. */
export function shownWindow(r: Span | null | undefined, ext: Span): Span | null {
  if (!r || !Number.isFinite(r[0]) || !Number.isFinite(r[1]) || r[1] <= r[0]) return null;
  const a = Math.max(ext[0], r[0]), b = Math.min(ext[1], r[1]);
  if (b <= a) return null;
  return b - a >= (ext[1] - ext[0]) * 0.98 ? null : [a, b];
}
