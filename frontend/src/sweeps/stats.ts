/* Small statistics for the charts (MF02): correlation (Pearson, Spearman), histogram bins,
   quartiles for a box. Pure functions on Float32Array; NaN is left out, pairwise. */

/** Ranks with ties averaged (1-based), NaN stays NaN. */
export function ranks(v: ArrayLike<number>): Float64Array {
  const idx: number[] = [];
  for (let i = 0; i < v.length; i++) if (Number.isFinite(v[i])) idx.push(i);
  idx.sort((a, b) => v[a] - v[b]);
  const r = new Float64Array(v.length).fill(NaN);
  for (let i = 0; i < idx.length;) {
    let j = i;
    while (j + 1 < idx.length && v[idx[j + 1]] === v[idx[i]]) j++;
    const avg = (i + j) / 2 + 1;
    for (let k = i; k <= j; k++) r[idx[k]] = avg;
    i = j + 1;
  }
  return r;
}

/** Pearson's r over the rows where both are numbers (and `keep`, if given); NaN with < 3 rows or no spread. */
export function pearson(x: ArrayLike<number>, y: ArrayLike<number>, keep?: ArrayLike<number>): number {
  let n = 0, sx = 0, sy = 0;
  for (let i = 0; i < x.length; i++) if ((!keep || keep[i]) && Number.isFinite(x[i]) && Number.isFinite(y[i])) { n++; sx += x[i]; sy += y[i]; }
  if (n < 3) return NaN;
  const mx = sx / n, my = sy / n;
  let cxy = 0, cxx = 0, cyy = 0;
  for (let i = 0; i < x.length; i++) if ((!keep || keep[i]) && Number.isFinite(x[i]) && Number.isFinite(y[i])) {
    const dx = x[i] - mx, dy = y[i] - my; cxy += dx * dy; cxx += dx * dx; cyy += dy * dy;
  }
  return cxx > 0 && cyy > 0 ? cxy / Math.sqrt(cxx * cyy) : NaN;
}

/** Spearman's rho: Pearson on the ranks (of the rows both have and `keep` keeps). */
export function spearman(x: ArrayLike<number>, y: ArrayLike<number>, keep?: ArrayLike<number>): number {
  const both: number[] = [];
  for (let i = 0; i < x.length; i++) if ((!keep || keep[i]) && Number.isFinite(x[i]) && Number.isFinite(y[i])) both.push(i);
  const xs = both.map((i) => x[i]), ys = both.map((i) => y[i]);
  return pearson(ranks(xs), ranks(ys));
}

/** `bins` equal bins over [lo, hi]; counts per bin for each series (a series = rows with code k). */
export function histogram(v: ArrayLike<number>, lo: number, hi: number, bins: number, keep?: ArrayLike<number>,
  series?: ArrayLike<number>, nSeries = 1): number[][] {
  const out = Array.from({ length: nSeries }, () => new Array(bins).fill(0));
  const w = hi > lo ? (hi - lo) / bins : 1;
  for (let i = 0; i < v.length; i++) {
    if ((keep && !keep[i]) || !Number.isFinite(v[i])) continue;
    const b = Math.min(bins - 1, Math.max(0, Math.floor((v[i] - lo) / w)));
    const s = series ? series[i] : 0;
    if (Number.isFinite(s) && s >= 0 && s < nSeries) out[s][b]++;
  }
  return out;
}

/** Quartiles and whiskers (1.5 IQR, at a data point) of the numbers; null when none. */
export function boxStats(vals: number[]): { q1: number; med: number; q3: number; lo: number; hi: number; n: number; out: number[] } | null {
  const a = vals.filter(Number.isFinite).sort((x, y) => x - y);
  if (!a.length) return null;
  const q = (p: number) => { const x = (a.length - 1) * p, i = Math.floor(x), f = x - i; return i + 1 < a.length ? a[i] + (a[i + 1] - a[i]) * f : a[i]; };
  const q1 = q(0.25), med = q(0.5), q3 = q(0.75), iqr = q3 - q1;
  const lo = a.find((x) => x >= q1 - 1.5 * iqr)!, hi = [...a].reverse().find((x) => x <= q3 + 1.5 * iqr)!;
  return { q1, med, q3, lo, hi, n: a.length, out: a.filter((x) => x < lo || x > hi) };
}
