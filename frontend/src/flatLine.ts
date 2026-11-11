/**
 * A line that would look flat on a value axis it shares with much larger ones: a current of 12 A
 * beside 3000 rpm is a line along the bottom. T47 offers the right axis when the UNITS differ; many
 * files (a CSV with no units) say nothing there, so the same offer is also made from the values'
 * ranges. Names only: the ranges come from the file list's small pictures (`api.sparks`).
 */
export type Range = [number, number] | null;

/** Below this share of the axis a line's whole movement is a few pixels of a plot's height. */
export const FLAT_SHARE = 0.04;

/** The range of a small picture's slices (null when it has no value). */
export function rangeOf(sp: { lo: (number | null)[]; hi: (number | null)[] } | null | undefined, scale = 1, offset = 0): Range {
  if (!sp) return null;
  let mn = Infinity, mx = -Infinity;
  for (const v of sp.lo) if (v !== null && Number.isFinite(v)) mn = Math.min(mn, v);
  for (const v of sp.hi) if (v !== null && Number.isFinite(v)) mx = Math.max(mx, v);
  if (!(mx >= mn)) return null;
  const a = mn * scale + offset, b = mx * scale + offset;
  return [Math.min(a, b), Math.max(a, b)];
}

/**
 * Who looks flat when `added` joins `others` on one axis: the added line ("added"), every line that
 * was there ("others"), or nobody (null). A constant is flat on any axis - it is never the reason.
 */
export function flatOnSharedAxis(added: Range, others: Range[], share = FLAT_SHARE): "added" | "others" | null {
  const rest = others.filter((r): r is [number, number] => r !== null);
  if (!added || !rest.length) return null;
  const lo = Math.min(added[0], ...rest.map((r) => r[0])), hi = Math.max(added[1], ...rest.map((r) => r[1]));
  const axis = hi - lo;
  if (!(axis > 0)) return null;
  const span = (r: [number, number]) => r[1] - r[0];
  if (span(added) > 0 && span(added) < share * axis) return "added";
  const moving = rest.filter((r) => span(r) > 0);
  if (moving.length && moving.every((r) => span(r) < share * axis)) return "others";
  return null;
}
