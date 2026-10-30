/* Axis scales for the parallel plot: a value to 0..1 (bottom..top) and back, and the ticks.
   Linear and log for numbers; category and ordinal put each distinct value at its own place. */
import type { Col, Scale } from "./model";

export interface AxisScale {
  kind: Scale;
  /** 0 (bottom) .. 1 (top); NaN: no place (a missing value, or <= 0 on a log axis) */
  norm: (v: number) => number;
  /** back from 0..1 to a value (ranges); for category / ordinal the nearest place's value */
  inv: (t: number) => number;
  ticks: { t: number; label: string }[];
  /** category / ordinal: the values in order */
  places?: number[];
}

export function fmtValue(v: number): string {
  if (!Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e6 || a < 1e-3)) return v.toExponential(2);
  return String(+v.toPrecision(4));
}

export const labelOf = (col: Col, v: number) => (col.kind === "cat" ? (col.labels?.[v] ?? "–") : fmtValue(v));

function niceTicks(lo: number, hi: number, n = 5): number[] {
  const span = hi - lo;
  if (!(span > 0)) return [lo];
  const step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= n) ?? 10 * mag;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(12));
  return out;
}

export function makeScale(col: Col, kind: Scale, reversed = false): AxisScale {
  const vals = col.values;
  const flip = (t: number) => (reversed ? 1 - t : t);
  if (col.kind === "cat" || kind === "category" || kind === "ordinal") {
    let places: number[];
    if (col.kind === "cat") places = (col.labels ?? []).map((_, i) => i);
    else {
      const set = new Set<number>();
      for (let i = 0; i < vals.length && set.size <= 400; i++) if (Number.isFinite(vals[i])) set.add(vals[i]);
      places = [...set].sort((a, b) => a - b);
    }
    const at = new Map(places.map((v, i) => [v, i]));
    const n = Math.max(1, places.length);
    const every = Math.max(1, Math.ceil(n / 16));
    return {
      kind: col.kind === "cat" && kind !== "ordinal" ? "category" : kind === "linear" || kind === "log" ? "category" : kind,
      places,
      norm: (v) => { const i = at.get(v); return i === undefined ? NaN : flip((i + 0.5) / n); },
      inv: (t) => places[Math.max(0, Math.min(n - 1, Math.floor(flip(t) * n)))],
      ticks: places.map((v, i) => ({ t: flip((i + 0.5) / n), label: labelOf(col, v) })).filter((_, i) => i % every === 0),
    };
  }
  let lo = Infinity, hi = -Infinity;
  const log = kind === "log";
  for (let i = 0; i < vals.length; i++) {
    const v = vals[i];
    if (!Number.isFinite(v) || (log && v <= 0)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (!Number.isFinite(lo)) { lo = 0; hi = 1; }
  if (log) {
    const a = Math.log10(lo), b = Math.log10(hi) === a ? a + 1 : Math.log10(hi);
    const ticks: { t: number; label: string }[] = [];
    for (let d = Math.floor(a); d <= Math.ceil(b); d++) { const t = (d - a) / (b - a); if (t >= -1e-9 && t <= 1 + 1e-9) ticks.push({ t: flip(t), label: fmtValue(10 ** d) }); }
    return { kind: "log", norm: (v) => (v > 0 ? flip((Math.log10(v) - a) / (b - a)) : NaN), inv: (t) => 10 ** (a + flip(t) * (b - a)), ticks };
  }
  if (hi === lo) { const pad = Math.abs(lo) * 0.05 || 1; lo -= pad; hi += pad; }
  return {
    kind: "linear",
    norm: (v) => (Number.isFinite(v) ? flip((v - lo) / (hi - lo)) : NaN),
    inv: (t) => lo + flip(t) * (hi - lo),
    ticks: niceTicks(lo, hi).map((v) => ({ t: flip((v - lo) / (hi - lo)), label: fmtValue(v) })),
  };
}
