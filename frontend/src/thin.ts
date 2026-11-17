/* Which samples to draw so that no excursion is lost (CLAUDE.md: no point is ever left out of a picture) - the
   page's twin of backend svcore/decimate.path_thin: the samples cut into chunks, and of each chunk the first, the
   last and the samples of the smallest and the largest value of every column kept, in order. About nOut indices;
   every one when there are fewer. Never a plain stride: a stride skips the one sample that shows the problem. */
export function pathThin(cols: ArrayLike<number>[], n: number, nOut: number): number[] {
  const per = 2 + 2 * cols.length;
  if (nOut <= 0 || n <= nOut || n <= per) return Array.from({ length: n }, (_, i) => i);
  const k = Math.max(2, Math.ceil((n * per) / nOut));
  const keep = new Uint8Array(n);
  for (let s = 0; s < n; s += k) {
    const e = Math.min(n, s + k);
    keep[s] = 1; keep[e - 1] = 1;
    for (const c of cols) {
      let lo = -1, hi = -1;
      for (let i = s; i < e; i++) {
        const v = c[i];
        if (!Number.isFinite(v)) continue;
        if (lo < 0 || v < c[lo]) lo = i;
        if (hi < 0 || v > c[hi]) hi = i;
      }
      if (lo >= 0) { keep[lo] = 1; keep[hi] = 1; }
    }
  }
  const out: number[] = [];
  for (let i = 0; i < n; i++) if (keep[i]) out.push(i);
  return out;
}
